"""IP-boundary guard — support-span limits (spec section 3.5).

Stdlib-only, fail-closed. Enforces the numeric support-span limits that make
the ISC2 and course-transcript IP boundaries concrete:

* structured (tier 0/1): exact field value only — single line, short.
* markdown (tier 2): one heading excerpt or <= 50 words.
* transcript (tier 3): <= 25 words unless explicitly authorized.

No support span may reproduce a full multiple-choice item or answer key.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import ingest

_WORD_RE = re.compile(r"\S+")

# Word ceilings by source tier. Structured sources should be an exact field
# value, so they get the tightest ceiling and must be single-line.
_TIER_WORD_LIMIT = {0: 20, 1: 20, 2: 50, 3: 25, 4: 25}
_STRUCTURED_TIERS = {0, 1}


def count_words(text: str) -> int:
    return len(_WORD_RE.findall(text))


def check_support_span(support: str, source_tier: int) -> list[str]:
    problems: list[str] = []
    if not isinstance(support, str):
        return ["support must be a string"]
    limit = _TIER_WORD_LIMIT.get(source_tier, 25)
    words = count_words(support)
    if words > limit:
        problems.append(
            f"support span is {words} words; tier {source_tier} limit is {limit}"
        )
    if source_tier in _STRUCTURED_TIERS and "\n" in support:
        problems.append("structured (tier 0/1) support must be a single-line field value")
    if ingest.contains_full_mcq(support):
        problems.append("support span appears to reproduce a full multiple-choice item")
    return problems


def scan_facts(facts_dir: Path) -> list[str]:
    failures: list[str] = []
    for path in sorted(Path(facts_dir).glob("*.json")):
        try:
            cards = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            failures.append(f"{path.name}: could not load: {exc}")
            continue
        if not isinstance(cards, list):
            failures.append(f"{path.name}: expected a list of fact cards")
            continue
        for card in cards:
            fact_id = card.get("fact_id", "<no fact_id>")
            for problem in check_support_span(card.get("support", ""), card.get("source_tier", 3)):
                failures.append(f"{path.name}:{fact_id}: {problem}")
    return failures


def scan_notes(notes_dir: Path) -> list[str]:
    """Check published (status: reviewed) notes for over-length verbatim spans.

    Draft ingestion artifacts are not published notes and are not scanned; only
    reviewed notes checked into notes/ are subject to the transcript limit.
    """
    failures: list[str] = []
    notes_path = Path(notes_dir)
    for path in sorted(notes_path.glob("*.md")):
        if path.name.upper() == "README.MD":
            continue
        text = path.read_text(encoding="utf-8")
        keys = ingest.parse_frontmatter_keys(text)
        if not keys:
            failures.append(f"{path.name}: published note is missing a front-matter block")
            continue
        if re.search(r"^status:\s*reviewed\b", text, re.MULTILINE) is None:
            continue  # draft notes are not yet subject to the published-span gate
        body = text.split("---", 2)[-1]
        for para in ingest._PARA_SPLIT_RE.split(body):
            stripped = para.strip()
            if stripped.startswith((">", "#")) or not stripped:
                continue
            if count_words(stripped) > _TIER_WORD_LIMIT[3]:
                failures.append(
                    f"{path.name}: reviewed note paragraph exceeds transcript span limit "
                    f"({count_words(stripped)} words > {_TIER_WORD_LIMIT[3]})"
                )
    return failures
