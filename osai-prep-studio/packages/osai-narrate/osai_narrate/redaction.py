"""Secret/flag/PII redaction — a self-contained copy of the vetted tripwire so the package
has **no course-app dependency**. A narration script is authored content and should never
carry a secret; ``residual_secrets`` is the fail-closed check before any egress (a cloud
render). Kept in step with the OSAI spine's ``llm.py`` patterns.
"""

from __future__ import annotations

import json
import re

# Scrubbed before any text can leave the box. Ordered; broad-but-safe.
_REDACTIONS = [
    (re.compile(r"OSAI\{[^}]*\}"), "[REDACTED_FLAG]"),
    (re.compile(r"OSAI\{[^}\s]{2,}"), "[REDACTED_FLAG]"),          # truncated flag (lost brace)
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[REDACTED_EMAIL]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"\bsk-[A-Za-z0-9._-]{16,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\b(?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{16,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b"), "[REDACTED_TOKEN]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "[REDACTED_TOKEN]"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "[REDACTED_TOKEN]"),
    (re.compile(r"\bxapp-[A-Za-z0-9-]{10,}\b"), "[REDACTED_TOKEN]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
                re.S), "[REDACTED_PRIVATE_KEY]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),
    (re.compile(r"\b(?:\d[ .\-]*?){13,16}\b"), "[REDACTED_PAN]"),
]


def redact_text(text: str) -> str:
    """Scrub flags / secrets / PII from a string before it can leave the box."""
    for pattern, repl in _REDACTIONS:
        text = pattern.sub(repl, text or "")
    return text


def _iter_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str):
                yield k                     # keys are content too
            yield from _iter_strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _iter_strings(v)


def residual_secrets(obj) -> list:
    """The category labels of any flag/secret/PII family present in ``obj``. Scans every
    nested string leaf **and dict key**, plus the serialized form (catches non-string
    leaves). A non-empty result means the caller MUST fail closed and refuse to send."""
    candidates = list(_iter_strings(obj))
    try:
        candidates.append(json.dumps(obj, default=str))
    except Exception:  # pragma: no cover - exotic non-serializable object
        candidates.append(str(obj))
    hits = set()
    for s in candidates:
        for pattern, repl in _REDACTIONS:
            if pattern.search(s or ""):
                hits.add(repl.strip("[]"))
    return sorted(hits)
