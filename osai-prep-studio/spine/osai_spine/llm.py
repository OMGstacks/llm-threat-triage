"""LLM provider seam — the model router from 07-architecture-and-stack.md.

**Optional.** The platform runs fully offline without it: the tutor falls back to
its extractive answer and lab targets to the deterministic mocks, so CI is green
with no key and no network. When the operator sets ``ANTHROPIC_API_KEY`` *and*
installs the official ``anthropic`` SDK *and* opts in with ``OSAI_LLM=1``, this
wires the highest-quality paths (the grounded tutor answer first) to Claude.

The key is read from the environment ONLY — never hardcoded, never logged.

Defaults follow the project's model recommendation:
  * ``claude-opus-4-8`` for the quality paths (grounded tutor answers, report-judge
    prose grading, Socratic depth) — the best-experience default;
  * a cheaper ``claude-haiku-4-5`` tier for high-volume generation (flashcards,
    scenario assembly);
  * adaptive thinking, streaming via ``get_final_message()``, and prompt caching on
    the fixed retrieved-corpus prefix.

Both model ids are overridable via ``OSAI_LLM_MODEL`` / ``OSAI_LLM_MODEL_BULK``.
"""

from __future__ import annotations

import os
import re
import time
from collections import deque
from pathlib import Path

# Quality tier (default) and bulk tier (cheap, high-volume) — overridable via env.
MODEL_QUALITY = os.environ.get("OSAI_LLM_MODEL", "claude-opus-4-8")
MODEL_BULK = os.environ.get("OSAI_LLM_MODEL_BULK", "claude-haiku-4-5")

# A simple spend guard: cap live API calls per rolling minute (per process). A
# runaway loop or a hammered /tutor/ask degrades to the offline extractive answer
# instead of quietly running up the bill. Override via OSAI_LLM_MAX_CALLS_PER_MIN
# (0 disables the cap).
MAX_CALLS_PER_MIN = int(os.environ.get("OSAI_LLM_MAX_CALLS_PER_MIN", "20"))

_TRUTHY = {"1", "true", "on", "yes"}


class LLMRateLimited(RuntimeError):
    """Raised when the per-minute call cap is hit; callers fall back to offline."""


class _RateLimiter:
    """Sliding-window call limiter. ``now`` is injectable for deterministic tests."""

    def __init__(self, max_calls: int, window_s: float = 60.0):
        self.max_calls = max_calls
        self.window_s = window_s
        self._calls: deque = deque()

    def allow(self, now: float) -> bool:
        if not self.max_calls:  # 0 => disabled
            return True
        while self._calls and now - self._calls[0] >= self.window_s:
            self._calls.popleft()
        if len(self._calls) >= self.max_calls:
            return False
        self._calls.append(now)
        return True

# Patterns scrubbed before any learner content leaves the box (defense in depth — the
# range plants only fake secrets, but the API call must not carry tokens/PII anyway).
# See docs/security/api-key-and-data-handling.md.
_REDACTIONS = [
    (re.compile(r"OSAI\{[^}]*\}"), "[REDACTED_FLAG]"),
    # A flag whose closing brace was lost (truncation/typo) must still be scrubbed.
    (re.compile(r"OSAI\{[^}\s]{2,}"), "[REDACTED_FLAG]"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[REDACTED_EMAIL]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"\bsk-[A-Za-z0-9._-]{16,}\b"), "[REDACTED_API_KEY]"),
    # Common provider/VCS tokens (GitHub, Slack) that are secrets like any API key.
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b"), "[REDACTED_TOKEN]"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "[REDACTED_TOKEN]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
                re.S), "[REDACTED_PRIVATE_KEY]"),
    # Payment card number — allow spaces, dashes OR dots between digit groups.
    (re.compile(r"\b(?:\d[ .\-]*?){13,16}\b"), "[REDACTED_PAN]"),
]


def sdk_available() -> bool:
    """True iff the official anthropic SDK can be imported."""
    try:
        import anthropic  # noqa: F401
        return True
    except Exception:  # pragma: no cover - depends on the install env
        return False


def _read_key() -> str | None:
    """The Anthropic key, from the env var OR the Docker/secret-file convention.

    Docker/K8s secrets are mounted as *files*, not env vars — so ``ANTHROPIC_API_KEY_FILE``
    (e.g. ``/run/secrets/anthropic_api_key``) is read and its contents used as the key.
    The direct env var wins when both are set. The value is never logged."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key.strip() or None
    key_file = os.environ.get("ANTHROPIC_API_KEY_FILE")
    if key_file:
        try:
            # utf-8-sig strips a leading BOM (common when the file is written by a
            # Windows editor/PowerShell) that str.strip() would otherwise leave in.
            return (Path(key_file).read_text(encoding="utf-8-sig").strip() or None)
        except OSError:
            return None
    return None


def key_present() -> bool:
    return bool(_read_key())


def key_source() -> str:
    """Where the key came from — 'env', 'file', or 'none'. Never the value."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "env"
    kf = os.environ.get("ANTHROPIC_API_KEY_FILE")
    if kf and Path(kf).is_file():
        return "file"
    return "none"


def enabled() -> bool:
    """The generative layer is OFF unless explicitly opted in AND actually usable.
    This keeps the default, no-key experience deterministic and offline. Governs the
    low-risk tutor path (query + public reference corpus)."""
    opted_in = os.environ.get("OSAI_LLM", "").strip().lower() in _TRUTHY
    return opted_in and key_present() and sdk_available()


def transcripts_enabled() -> bool:
    """A SECOND, separate opt-in gate for paths that would send *learner attack
    transcripts* to the API (report-judge, attacker-LLM). Requires the base gate AND
    an explicit OSAI_LLM_TRANSCRIPTS=1. Flip it only once the operational controls in
    ``datahandling`` (mandatory consent, bounded retention + purge, audit) are in
    place — those are the enforcement choke point (``datahandling.prepare_for_judging``),
    which also redacts and re-verifies content before any API call."""
    opted_in = os.environ.get("OSAI_LLM_TRANSCRIPTS", "").strip().lower() in _TRUTHY
    return enabled() and opted_in


def redact_text(text: str) -> str:
    """Scrub flags / secrets / PII from a string before it can leave the box."""
    for pattern, repl in _REDACTIONS:
        text = pattern.sub(repl, text or "")
    return text


def redact_obj(obj):
    """Recursively redact EVERY string leaf of a dict / list / tuple / str. Used so a
    secret placed in any nested field (not just 'content') is scrubbed before egress."""
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, dict):
        return {k: redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact_obj(v) for v in obj]
    return obj


def _iter_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _iter_strings(v)


def residual_secrets(obj) -> list:
    """The category labels of any flag/secret/PII family STILL present in ``obj`` after
    redaction, scanning every nested string leaf. A non-empty result means redaction
    missed something (a field it didn't reach, or a format the regexes don't cover) —
    the caller MUST fail closed and refuse to send/retain. This is the defense-in-depth
    tripwire behind ``redact_obj`` (05/13/24-*)."""
    hits = set()
    for s in _iter_strings(obj):
        for pattern, repl in _REDACTIONS:
            if pattern.search(s or ""):
                hits.add(repl.strip("[]"))
    return sorted(hits)


def redact_transcript(transcript) -> list:
    """Return a copy of a transcript with EVERY string field of every event redacted
    (content, tool_call, source, role, and any nested/extra field) — not just 'content' —
    so a secret placed in any field cannot leave the box. The learner-content LLM paths
    MUST pass transcripts through this before any API call."""
    return [redact_obj(dict(event)) for event in (transcript or [])]


# --- provider base-URL policy (24-transcript-judging-signoff.md §10) -------- #
# The transcript-judging path may send learner content, so its outbound endpoint must
# be the official Anthropic endpoint by default; a custom/proxy URL is high-risk and
# must be explicitly approved (OSAI_APPROVED_BASE_URLS) before it is honored.
OFFICIAL_BASE_URL = "https://api.anthropic.com"


def _approved_base_urls() -> set:
    approved = {OFFICIAL_BASE_URL}
    for u in os.environ.get("OSAI_APPROVED_BASE_URLS", "").split(","):
        u = u.strip().rstrip("/")
        if u:
            approved.add(u)
    return approved


def resolve_base_url() -> str:
    """The effective outbound base URL the client would use: OSAI_ANTHROPIC_BASE_URL,
    then ANTHROPIC_BASE_URL (which the SDK itself honors), then the official default."""
    for var in ("OSAI_ANTHROPIC_BASE_URL", "ANTHROPIC_BASE_URL"):
        v = os.environ.get(var)
        if v and v.strip():
            return v.strip().rstrip("/")
    return OFFICIAL_BASE_URL


def base_url_host() -> str:
    from urllib.parse import urlparse
    return urlparse(resolve_base_url()).hostname or ""


def base_url_approved() -> bool:
    """True iff the resolved base URL is the official endpoint or explicitly allowlisted
    AND uses https. Non-approved / non-https endpoints must block the transcript path."""
    url = resolve_base_url()
    return url.startswith("https://") and url.rstrip("/") in _approved_base_urls()


def status() -> dict:
    """A small introspection blob for /health so the operator can see whether their
    key is live without leaking it. Never includes the value/prefix/suffix/length."""
    return {
        "enabled": enabled(),
        "transcripts_enabled": transcripts_enabled(),
        "sdk_installed": sdk_available(),
        "key_present": key_present(),
        "key_source": key_source(),
        "base_url_override": bool(os.environ.get("OSAI_ANTHROPIC_BASE_URL")
                                  or os.environ.get("ANTHROPIC_BASE_URL")),
        "base_url_host": base_url_host(),        # resolved host, never a secret
        "base_url_approved": base_url_approved(),
        "max_calls_per_min": MAX_CALLS_PER_MIN,
        "model_quality": MODEL_QUALITY,
        "model_bulk": MODEL_BULK,
    }


class LLMProvider:
    """Thin wrapper over the Anthropic Messages API. Constructed only when the seam
    is enabled; callers always wrap ``complete`` with their own offline fallback."""

    def __init__(self, model: str | None = None, base_url: str | None = None,
                 max_calls_per_min: int | None = None):
        self.model = model or MODEL_QUALITY
        # In some hosts (e.g. a Claude Code session) ANTHROPIC_BASE_URL points at the
        # agent's proxy; OSAI_ANTHROPIC_BASE_URL lets the app target its own endpoint
        # (e.g. https://api.anthropic.com) independently of that.
        self.base_url = base_url or os.environ.get("OSAI_ANTHROPIC_BASE_URL") or None
        self._limiter = _RateLimiter(
            MAX_CALLS_PER_MIN if max_calls_per_min is None else max_calls_per_min
        )
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from anthropic import Anthropic
            kwargs = {}
            key = _read_key()  # env var or the ANTHROPIC_API_KEY_FILE secret convention
            if key:
                kwargs["api_key"] = key
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = Anthropic(**kwargs)
        return self._client

    def complete(self, system: str, user: str, *, model: str | None = None,
                 max_tokens: int = 700, cached_prefix: str | None = None) -> str:
        """One grounded completion. ``cached_prefix`` is a large fixed context block
        (e.g. the retrieved corpus) marked for prompt caching so repeat calls over
        the same sources are cheap. Streams (adaptive thinking can run long) and
        returns the final assistant text. Raises ``LLMRateLimited`` past the per-minute
        cap, or on API error — callers wrap with their own offline fallback."""
        if not self._limiter.allow(time.monotonic()):
            raise LLMRateLimited(f"LLM call cap reached ({self._limiter.max_calls}/min)")
        system_blocks = [{"type": "text", "text": system}]
        if cached_prefix:
            system_blocks.append({
                "type": "text",
                "text": cached_prefix,
                "cache_control": {"type": "ephemeral"},
            })
        with self.client.messages.stream(
            model=model or self.model,
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            system=system_blocks,
            messages=[{"role": "user", "content": user}],
        ) as stream:
            msg = stream.get_final_message()
        return "".join(
            block.text for block in msg.content
            if getattr(block, "type", None) == "text"
        ).strip()
