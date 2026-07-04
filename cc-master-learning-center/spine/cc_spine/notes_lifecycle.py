"""Note review-state lifecycle (spec section 6; reviewer R&D-4).

Cleaned domain notes move through a declared state machine; only reviewed or
promoted notes may ground fact cards. The states and transitions are data here
and mirrored as a table in ``notes/README.md`` — one source of truth for the
validator, one human-readable contract.

    draft     -> reviewed | rejected
    reviewed  -> promoted | deprecated | draft   (draft = manual edit, re-review)
    promoted  -> deprecated
    rejected  -> (terminal)
    deprecated-> (terminal)

Fail-closed: a note with a missing or unknown status can never ground a card.
Full pipeline enforcement (ingestion -> review -> promotion) wires up in PR-5;
PR-3 ships the state machine plus the factstore's grounding-eligibility seed.

This module must never import factstore (factstore imports it).
"""

from __future__ import annotations

import re

STATES = {"draft", "reviewed", "promoted", "rejected", "deprecated"}

ALLOWED_TRANSITIONS = {
    "draft": {"reviewed", "rejected"},
    "reviewed": {"promoted", "deprecated", "draft"},
    "promoted": {"deprecated"},
    "rejected": set(),
    "deprecated": set(),
}

# Only these note states may ground fact cards.
GROUNDING_ELIGIBLE = {"reviewed", "promoted"}

_STATUS_RE = re.compile(r"^status:\s*(\S+)\s*$", re.MULTILINE)


def validate_transition(old: str, new: str) -> list[str]:
    """Errors for a proposed state transition ([] == legal)."""
    problems = []
    if old not in STATES:
        problems.append(f"unknown source state {old!r}")
    if new not in STATES:
        problems.append(f"unknown target state {new!r}")
    if problems:
        return problems
    if new not in ALLOWED_TRANSITIONS[old]:
        problems.append(f"transition {old!r} -> {new!r} is not allowed")
    return problems


def grounding_allowed(status) -> bool:
    return status in GROUNDING_ELIGIBLE


def note_status(note_text: str):
    """Extract the front-matter ``status:`` value from a note, or None.

    Only looks inside the leading '---' front-matter block (fail-closed: a
    'status:' line in the body does not count).
    """
    lines = note_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    try:
        end = next(i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration:
        return None
    match = _STATUS_RE.search("\n".join(lines[1:end]))
    return match.group(1) if match else None


def validate_note_status(note_text: str) -> list[str]:
    """Errors for a note's status field ([] == present and known)."""
    status = note_status(note_text)
    if status is None:
        return ["note has no front-matter status (fail-closed: cannot ground cards)"]
    if status not in STATES:
        return [f"note has unknown status {status!r} (fail-closed: cannot ground cards)"]
    return []
