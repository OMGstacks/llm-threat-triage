"""Retrieval-grounded tutor core (pillar 6) — the offline-verifiable foundation of
03-tutor-examiner-bot.md.

Realizes the load-bearing properties without an LLM call, so it runs and is tested
in CI:
  * retrieval-first over a curated Source Library (09a-source-library.md),
  * "no source, no confident answer" abstention,
  * citation enforcement (every grounded answer carries its sources + tiers),
  * taxonomy anti-hallucination (any LLMxx/AML.Txxxx the answer mentions must be real).

The answer is **extractive** here (grounded passage + citations); a generative LLM
can be slotted in behind the same ``Tutor.ask`` seam later (the retrieval, grounding
gate, citation, and validation stay identical). Stdlib-only TF-IDF retrieval.
"""

from __future__ import annotations

import math
import os
import re
from collections import Counter
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]

# (path relative to repo root, authority tier) — see 09a-source-library.md
DEFAULT_SOURCES = [
    ("reference/owasp-llm-top-10.md", "A1"),
    ("reference/mitre-atlas.md", "A1"),
    ("reference/glossary.md", "A3"),
]

ABSTAIN_THRESHOLD = 0.07  # min cosine similarity to answer rather than abstain
# Ignore very-common terms (idf below this) so generic words like "what/the/high"
# don't create spurious similarity — only distinctive content terms drive retrieval.
IDF_FLOOR = 1.8

_WORD = re.compile(r"[a-z0-9]+")
_TAXONOMY_ID = re.compile(r"\bLLM\d{2}:2025\b|\bAML\.T(?:A)?\d{4}(?:\.\d{3})?\b")

# Generic English filler — dropped so it can't ground a security answer. (Domain
# terms like "high"/"injection" are deliberately NOT here; the IDF floor + the
# >=2-distinctive-overlap rule handle those.)
_STOPWORDS = frozenset("""
a an the is are was were be been being am do does did doing have has had having
what which who whom whose how why when where this that these those it its
to of in on for with and or but if then else at by from as about into over under
again i you your yours we our ours they them their he she his her my me mine us
can could should would will shall may might must not no nor yes so than too very
just only also more most less least some any all each both few many much such own
same other another please tell show explain describe give get make use using best
good better worst great recipe bread how's let lets want need know
""".split())


def _tokenize(text: str):
    return [w for w in _WORD.findall(text.lower()) if w not in _STOPWORDS]


def validate_taxonomy_ids(text: str, registry) -> list:
    """Return any framework ids in ``text`` that are NOT real (anti-hallucination)."""
    bad = []
    for tid in _TAXONOMY_ID.findall(text):
        if tid.startswith("LLM"):
            if not registry.is_owasp(tid):
                bad.append(tid)
        elif not registry.is_atlas(tid):
            bad.append(tid)
    return bad


class _Chunk:
    __slots__ = ("source", "title", "text", "tier", "tf")

    def __init__(self, source, title, text, tier):
        self.source = source
        self.title = title
        self.text = text
        self.tier = tier
        self.tf = Counter(_tokenize(title + " " + text))


def _split_markdown(md_text: str):
    """Split a markdown doc into (heading, body) sections."""
    sections, title, buf = [], "(intro)", []
    for line in md_text.splitlines():
        if line.lstrip().startswith("#"):
            if buf:
                sections.append((title, "\n".join(buf)))
                buf = []
            title = line.lstrip("#").strip() or title
        else:
            buf.append(line)
    if buf:
        sections.append((title, "\n".join(buf)))
    return sections


class SourceLibrary:
    """A small TF-IDF index over curated markdown sources."""

    def __init__(self, sources=None, root=None):
        # OSAI_CORPUS_ROOT lets a container relocate the source corpus.
        self.root = Path(root or os.environ.get("OSAI_CORPUS_ROOT") or _REPO_ROOT)
        self.chunks: list[_Chunk] = []
        for rel, tier in (sources or DEFAULT_SOURCES):
            path = self.root / rel
            if not path.is_file():
                continue
            for title, body in _split_markdown(path.read_text(encoding="utf-8")):
                body = body.strip()
                if len(body) < 40:
                    continue
                self.chunks.append(_Chunk(rel, title, body[:1600], tier))
        self._build_idf()

    def _build_idf(self):
        n = len(self.chunks) or 1
        df = Counter()
        for chunk in self.chunks:
            for term in set(chunk.tf):
                df[term] += 1
        self.idf = {t: math.log((n + 1) / (d + 1)) + 1 for t, d in df.items()}

    def _vector(self, tf):
        return {
            t: f * self.idf[t]
            for t, f in tf.items()
            if self.idf.get(t, 0.0) >= IDF_FLOOR
        }

    def distinctive_terms(self, text: str) -> set:
        return {t for t in _tokenize(text) if self.idf.get(t, 0.0) >= IDF_FLOOR}

    def distinctive_overlap(self, query: str, chunk) -> int:
        chunk_terms = {t for t in chunk.tf if self.idf.get(t, 0.0) >= IDF_FLOOR}
        return len(self.distinctive_terms(query) & chunk_terms)

    def retrieve(self, query: str, k: int = 3):
        q = self._vector(Counter(_tokenize(query)))
        qn = math.sqrt(sum(v * v for v in q.values())) or 1.0
        scored = []
        for chunk in self.chunks:
            cv = self._vector(chunk.tf)
            cn = math.sqrt(sum(v * v for v in cv.values())) or 1.0
            dot = sum(q.get(t, 0.0) * v for t, v in cv.items())
            scored.append((dot / (qn * cn), chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:k]


def _lead(text: str, limit: int = 600) -> str:
    text = " ".join(text.split())
    return text[:limit] + ("…" if len(text) > limit else "")


class Tutor:
    """Retrieval-first, citation-enforced, abstaining tutor (extractive answerer)."""

    def __init__(self, library=None, registry=None):
        self.library = library or SourceLibrary()
        self.registry = registry

    def ask(self, query: str, mode: str = "tutor", k: int = 3) -> dict:
        hits = self.library.retrieve(query, k)
        top = hits[0][0] if hits else 0.0
        # A lone common-ish term must not ground a security answer: require >=2
        # distinctive shared terms, unless the single-term match is strong.
        overlap = self.library.distinctive_overlap(query, hits[0][1]) if hits else 0
        grounded = bool(hits) and top >= ABSTAIN_THRESHOLD and (overlap >= 2 or top >= 0.35)

        # Grounding gate — "no source, no confident answer".
        if not grounded:
            return {
                "abstained": True,
                "mode": mode,
                "answer": (
                    "No source in the library supports a confident answer. Rephrase, "
                    "or add a source to the corpus — I will not guess on security facts."
                ),
                "citations": [],
                "top_score": round(top, 4),
            }

        best = hits[0][1]
        answer = _lead(best.text)
        citations = [
            {"source": c.source, "title": c.title, "tier": c.tier, "score": round(s, 4)}
            for s, c in hits
            if s >= ABSTAIN_THRESHOLD
        ]
        result = {
            "abstained": False,
            "mode": mode,
            "answer": answer,
            "citations": citations,
            "top_score": round(top, 4),
        }
        # Anti-hallucination: any framework id in the answer must be real.
        if self.registry is not None:
            bad = validate_taxonomy_ids(answer, self.registry)
            result["taxonomy_ids_valid"] = not bad
            if bad:
                result["invalid_ids"] = bad
        return result
