"""Deterministic transcript ingestion + suggest-only correction engine.

Stdlib-only. Two guarantees the governance spec (section 6) requires:

* **Deterministic**: same source bytes + same dictionary version produce a
  byte-identical note. No wall-clock, no randomness, ordered iteration only.
* **Suggest-only**: corrections are emitted as a reviewable diff and logged
  into the note front-matter. The engine never silently rewrites source text;
  the original wording is preserved in the note body.

The engine runs on synthetic fixtures in PR-2. Real course-transcript
ingestion is gated on explicit authorization (spec section 3, PR-5).
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_W = f"{{{W_NS}}}"

_WS_RE = re.compile(r"\s+")
_PARA_SPLIT_RE = re.compile(r"\n\s*\n")
_MCQ_RE = re.compile(r"\bA\)\s.*\bB\)\s.*\bC\)\s", re.DOTALL)

REQUIRED_FRONTMATTER = (
    "source_doc_id", "source_tier", "dictionary_version", "outline_version",
    "reviewed_by", "status", "corrections_applied", "corrections_flagged",
)

# Confidence levels that are flagged for human verification rather than
# offered as a confident suggestion.
_VERIFY_CONFIDENCE = {"low", "never_auto"}


@dataclass(frozen=True)
class Paragraph:
    index: int
    paragraph_id: str
    text: str
    heading_level: int | None = None
    style: str | None = None


@dataclass(frozen=True)
class Suggestion:
    paragraph_index: int
    paragraph_id: str
    start: int
    end: int
    wrong: str
    right: str
    confidence: str
    verify: bool
    reason: str = ""


# --------------------------------------------------------------------------
# Determinism helpers
# --------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """Lowercase and collapse whitespace — the canonical form for hashing."""
    return _WS_RE.sub(" ", text.strip().lower())


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def paragraph_id(source_doc_id: str, index: int, text: str) -> str:
    """Stable id: source_doc_id + paragraph_index + normalized content hash."""
    return f"{source_doc_id}#{index:04d}#{_sha256(normalize_text(text))[:12]}"


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------

def _open_zip(source) -> zipfile.ZipFile:
    if isinstance(source, (bytes, bytearray)):
        return zipfile.ZipFile(io.BytesIO(bytes(source)))
    if hasattr(source, "read"):
        return zipfile.ZipFile(source)
    return zipfile.ZipFile(str(source))


def _heading_from_style(style: str | None) -> int | None:
    if not style:
        return None
    match = re.match(r"Heading([1-9])$", style)
    if match:
        return int(match.group(1))
    if style in ("Title",):
        return 0
    return None


def extract_docx(source, source_doc_id: str) -> list[Paragraph]:
    """Extract paragraphs from a .docx in document order (deterministic).

    ``source`` may be a path, a file-like object, or raw bytes. Only
    ``word/document.xml`` is read; paragraph style drives heading detection.
    """
    import xml.etree.ElementTree as ET

    with _open_zip(source) as zf:
        document_xml = zf.read("word/document.xml")
    root = ET.fromstring(document_xml)
    body = root.find(f"{_W}body")
    paragraphs: list[Paragraph] = []
    if body is None:
        return paragraphs
    kept = 0
    for para in body.findall(f"{_W}p"):
        runs = [node.text or "" for node in para.iter(f"{_W}t")]
        text = _WS_RE.sub(" ", "".join(runs)).strip()
        if not text:
            continue
        style_node = para.find(f"{_W}pPr/{_W}pStyle")
        style = style_node.get(f"{_W}val") if style_node is not None else None
        paragraphs.append(Paragraph(
            index=kept,
            paragraph_id=paragraph_id(source_doc_id, kept, text),
            text=text,
            heading_level=_heading_from_style(style),
            style=style,
        ))
        kept += 1
    return paragraphs


def extract_text(source, source_doc_id: str) -> list[Paragraph]:
    """Extract paragraphs from a plain-text transcript (blank-line separated)."""
    if isinstance(source, (bytes, bytearray)):
        raw = bytes(source).decode("utf-8")
    elif hasattr(source, "read"):
        raw = source.read()
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8")
    else:
        raw = Path(str(source)).read_text(encoding="utf-8")
    paragraphs: list[Paragraph] = []
    kept = 0
    for block in _PARA_SPLIT_RE.split(raw):
        text = _WS_RE.sub(" ", block).strip()
        if not text:
            continue
        paragraphs.append(Paragraph(
            index=kept,
            paragraph_id=paragraph_id(source_doc_id, kept, text),
            text=text,
        ))
        kept += 1
    return paragraphs


def extract(source, source_doc_id: str) -> list[Paragraph]:
    """Dispatch on file extension; bytes/file-like default to plain text."""
    if isinstance(source, (str, Path)) and str(source).lower().endswith(".docx"):
        return extract_docx(source, source_doc_id)
    return extract_text(source, source_doc_id)


# --------------------------------------------------------------------------
# Correction engine (suggest-only)
# --------------------------------------------------------------------------

def dictionary_version(dictionary: dict) -> str:
    return str(dictionary.get("schema_version", "unknown"))


def _entry_pattern(entry: dict) -> re.Pattern:
    wrong = entry["wrong"]
    if entry.get("match") == "phrase":
        core = re.escape(wrong)
    else:
        core = r"\b" + re.escape(wrong) + r"\b"
    flags = 0 if entry.get("case_sensitive") else re.IGNORECASE
    return re.compile(core, flags)


def _context_ok(entry: dict, paragraph_text: str) -> bool:
    pattern = entry.get("context_regex")
    if not pattern:
        return True
    flags = 0 if entry.get("case_sensitive") else re.IGNORECASE
    return re.search(pattern, paragraph_text, flags) is not None


def _guard_blocks(entry: dict, text: str, start: int, end: int) -> bool:
    """True if a never_before/never_after guard suppresses this match."""
    flags = 0 if entry.get("case_sensitive") else re.IGNORECASE
    before = entry.get("never_before")
    if before and re.match(r"\W+(?:" + before + r")\b", text[end:], flags):
        return True
    after = entry.get("never_after")
    if after and re.search(r"\b(?:" + after + r")\W+$", text[:start], flags):
        return True
    return False


def suggest_for_paragraph(paragraph: Paragraph, dictionary: dict,
                          domains: set[str] | None = None) -> list[Suggestion]:
    text = paragraph.text
    found: list[Suggestion] = []
    for entry in dictionary.get("entries", []):
        if entry.get("status") == "retired":
            continue
        if domains and entry.get("domains") and not (domains & set(entry["domains"])):
            continue
        if not _context_ok(entry, text):
            continue
        pattern = _entry_pattern(entry)
        for match in pattern.finditer(text):
            if _guard_blocks(entry, text, match.start(), match.end()):
                continue
            confidence = entry.get("confidence", "low")
            found.append(Suggestion(
                paragraph_index=paragraph.index,
                paragraph_id=paragraph.paragraph_id,
                start=match.start(),
                end=match.end(),
                wrong=match.group(0),
                right=entry["right"],
                confidence=confidence,
                verify=confidence in _VERIFY_CONFIDENCE,
                reason=entry.get("false_positive_notes", ""),
            ))
    found.sort(key=lambda s: (s.start, s.wrong.lower()))
    return found


def suggest_corrections(paragraphs: list[Paragraph], dictionary: dict,
                        domains: set[str] | None = None) -> list[Suggestion]:
    out: list[Suggestion] = []
    for para in paragraphs:
        out.extend(suggest_for_paragraph(para, dictionary, domains))
    return out


# --------------------------------------------------------------------------
# Note building (front-matter audit trail + suggest-only body)
# --------------------------------------------------------------------------

def _fmt_applied(sug: Suggestion) -> str:
    return (f'  - {{wrong: "{sug.wrong}", right: "{sug.right}", '
            f'paragraph: {sug.paragraph_index}, confidence: "{sug.confidence}"}}')


def _fmt_flagged(sug: Suggestion) -> str:
    return (f'  - {{wrong: "{sug.wrong}", suggested: "{sug.right}", '
            f'paragraph: {sug.paragraph_index}, confidence: "{sug.confidence}"}}')


def build_note(paragraphs: list[Paragraph], suggestions: list[Suggestion], *,
               source_doc_id: str, source_tier: int, dictionary_version: str,
               outline_version: str = "2025-10", reviewed_by: str | None = None,
               status: str = "draft") -> str:
    """Render a deterministic ingestion draft: front-matter audit trail + body.

    The body preserves the original wording (suggest-only); corrections appear
    as annotations and in the front-matter, never applied in place. Contains no
    wall-clock value, so the output is reproducible.
    """
    by_para: dict[int, list[Suggestion]] = {}
    for sug in suggestions:
        by_para.setdefault(sug.paragraph_index, []).append(sug)

    applied = [s for s in suggestions if not s.verify]
    flagged = [s for s in suggestions if s.verify]

    lines: list[str] = ["---"]
    lines.append(f"source_doc_id: {source_doc_id}")
    lines.append(f"source_tier: {source_tier}")
    lines.append(f"dictionary_version: {dictionary_version}")
    lines.append(f"outline_version: {outline_version}")
    lines.append(f"reviewed_by: {reviewed_by if reviewed_by else 'null'}")
    lines.append(f"status: {status}")
    if applied:
        lines.append("corrections_applied:")
        lines.extend(_fmt_applied(s) for s in applied)
    else:
        lines.append("corrections_applied: []")
    if flagged:
        lines.append("corrections_flagged:")
        lines.extend(_fmt_flagged(s) for s in flagged)
    else:
        lines.append("corrections_flagged: []")
    lines.append("---")
    lines.append("")

    for para in paragraphs:
        if para.heading_level and para.heading_level >= 1:
            lines.append(f"{'#' * min(para.heading_level, 6)} {para.text}")
        else:
            lines.append(para.text)
        for sug in by_para.get(para.index, []):
            if sug.verify:
                note = f' — {sug.reason}' if sug.reason else ''
                lines.append(f'> [VERIFY] "{sug.wrong}" -> "{sug.right}" '
                             f'({sug.confidence}){note}')
            else:
                lines.append(f'> suggestion: "{sug.wrong}" -> "{sug.right}" '
                             f'({sug.confidence})')
        lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


def ingest(source, source_doc_id: str, dictionary: dict, *, source_tier: int = 3,
           outline_version: str = "2025-10", reviewed_by: str | None = None,
           status: str = "draft", domains: set[str] | None = None) -> str:
    """End-to-end: extract, suggest, build the deterministic note artifact."""
    paragraphs = extract(source, source_doc_id)
    suggestions = suggest_corrections(paragraphs, dictionary, domains)
    return build_note(
        paragraphs, suggestions,
        source_doc_id=source_doc_id, source_tier=source_tier,
        dictionary_version=dictionary_version(dictionary),
        outline_version=outline_version, reviewed_by=reviewed_by, status=status,
    )


# --------------------------------------------------------------------------
# Front-matter validation (notes/README.md contract)
# --------------------------------------------------------------------------

def parse_frontmatter_keys(note_text: str) -> set[str]:
    """Return the set of top-level front-matter keys in a produced note."""
    lines = note_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return set()
    keys: set[str] = set()
    for line in lines[1:]:
        if line.strip() == "---":
            break
        match = re.match(r"([A-Za-z_][A-Za-z0-9_]*):", line)
        if match:
            keys.add(match.group(1))
    return keys


def validate_note_frontmatter(note_text: str) -> list[str]:
    keys = parse_frontmatter_keys(note_text)
    if not keys:
        return ["note is missing a '---' front-matter block"]
    return [f"front-matter missing required key: {key}"
            for key in REQUIRED_FRONTMATTER if key not in keys]


def contains_full_mcq(text: str) -> bool:
    """Heuristic tripwire: does a span reproduce a full multiple-choice item?"""
    return _MCQ_RE.search(text) is not None
