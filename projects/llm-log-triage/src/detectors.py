"""Detection engine for adversarial LLM activity.

Each detector is a small, auditable unit that scans one normalized log event
and emits zero or more :class:`Finding` objects. Findings are mapped to:

  * OWASP Top 10 for LLM Applications (2025) — the canonical vulnerability
    taxonomy interviewers expect you to speak fluently.
  * MITRE ATLAS — adversary tactics/techniques against AI systems.

Design goals (these mirror the day-to-day of a Technical Intelligence Analyst):
  * **Explainable** — every Finding carries the exact matched snippet and a
    plain-English rationale, so a human can confirm the call in seconds.
  * **Composable** — detectors are independent; adding one is a new entry in
    ``ALL_DETECTORS`` with no changes elsewhere.
  * **Channel-aware** — *who* said it matters. The same imperative string is a
    benign user request in a chat turn but an *indirect prompt injection* when
    it arrives inside retrieved (RAG) or tool content.
  * **Evasion-resistant** — input is normalized (NFKC, zero-width stripping,
    spaced-letter and leetspeak folding) and candidate base64/hex payloads are
    decoded before matching, so trivial obfuscation does not defeat the rules.

This is a heuristic triage engine for log analysis, NOT a production WAF.
"""

from __future__ import annotations

import base64
import binascii
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Optional, Pattern

# Bound the output a single adversarial event can produce.
MAX_FINDINGS_PER_EVENT = 50

# --------------------------------------------------------------------------- #
# Severity model
# --------------------------------------------------------------------------- #

# Ordered low -> critical so we can take a max() over an event's findings.
SEVERITY_ORDER = ("info", "low", "medium", "high", "critical")
_SEV_RANK = {name: i for i, name in enumerate(SEVERITY_ORDER)}


def severity_rank(sev: str) -> int:
    """Numeric rank for a severity label (higher == worse)."""
    return _SEV_RANK.get(sev, 0)


def max_severity(severities: Iterable[str]) -> str:
    """Return the worst severity in an iterable, or ``"info"`` if empty."""
    worst = "info"
    for s in severities:
        if severity_rank(s) > severity_rank(worst):
            worst = s
    return worst


def event_severity(findings: list) -> str:
    """Roll up a list of Findings to a single per-event severity verdict."""
    return max_severity(f.severity for f in findings)


# --------------------------------------------------------------------------- #
# Finding
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Finding:
    """A single detection on a single event."""

    detector: str          # stable rule name, e.g. "direct_prompt_injection"
    owasp_id: str          # e.g. "LLM01:2025"
    owasp_name: str        # e.g. "Prompt Injection"
    atlas_technique: str   # e.g. "AML.T0051.000"
    atlas_name: str        # e.g. "LLM Prompt Injection: Direct"
    severity: str          # one of SEVERITY_ORDER
    score: float           # 0.0 - 1.0 confidence-ish weight
    matched_snippet: str   # the substring that triggered the rule
    rationale: str         # plain-English why-this-fired

    def as_row(self, event_id: str) -> dict:
        """Flatten to a dict suitable for DB insertion."""
        return {
            "event_id": event_id,
            "detector": self.detector,
            "owasp_id": self.owasp_id,
            "owasp_name": self.owasp_name,
            "atlas_technique": self.atlas_technique,
            "atlas_name": self.atlas_name,
            "severity": self.severity,
            "score": round(self.score, 4),
            "matched_snippet": self.matched_snippet[:500],
            "rationale": self.rationale,
        }


# --------------------------------------------------------------------------- #
# Channel semantics
# --------------------------------------------------------------------------- #

# Channels whose content originates from *outside* the trust boundary. Imperative
# instructions arriving here are the signature of INDIRECT prompt injection: the
# user never typed them, they rode in on retrieved documents or tool output.
UNTRUSTED_SOURCES = frozenset({"rag", "retrieval", "tool", "plugin", "document", "web", "email"})


# --------------------------------------------------------------------------- #
# Evasion-resistant text normalization
# --------------------------------------------------------------------------- #

# Zero-width / format characters attackers wedge between letters to break regexes.
_ZERO_WIDTH_RE = re.compile(
    "[​‌‍‎‏‪-‮⁠⁡⁢⁣﻿]"
)

# Leetspeak / homoglyph folding (encoded chars -> ascii letter). Only digits and
# symbols are folded, so ordinary alphabetic text is untouched.
_LEET_MAP = str.maketrans({
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s",
    "7": "t", "@": "a", "$": "s", "|": "l",
})

# A run of single-character tokens separated by a SINGLE space ("i g n o r e").
# Using a single-space separator means a 2+ space gap is treated as a word
# boundary, so "i g n o r e   a l l" collapses to "ignore   all" (two words),
# not the merged "ignoreall" — preserving the whitespace the phrase regexes need.
_SPACED_LETTERS_RE = re.compile(r"(?:\b\w\b[ \t]){2,}\b\w\b")


def _collapse_spaced_letters(text: str) -> str:
    """Join "i g n o r e" -> "ignore" while leaving normal prose intact."""
    return _SPACED_LETTERS_RE.sub(lambda m: re.sub(r"[ \t]", "", m.group(0)), text)


def _normalize_text(text: str) -> str:
    """NFKC + zero-width strip + spaced-letter collapse (no leet yet)."""
    t = unicodedata.normalize("NFKC", text)
    t = _ZERO_WIDTH_RE.sub("", t)
    t = _collapse_spaced_letters(t)
    return t


def match_variants(content: str) -> list[tuple[str, str]]:
    """Return [(text, label)] variants to match against.

    Always includes the raw text; adds a normalized variant (if it differs) and
    a leet-folded variant (if it differs). Matching against any variant counts
    as a hit, which is what makes the engine resistant to spacing / unicode /
    leetspeak evasion without changing the stored event content.
    """
    variants = [(content, "raw")]
    norm = _normalize_text(content)
    if norm != content:
        variants.append((norm, "normalized"))
    leet = norm.translate(_LEET_MAP)
    if leet != norm:
        variants.append((leet, "leet-folded"))
    return variants


def _clip(text: str, start: int, end: int, pad: int = 24) -> str:
    """Return a readable window of ``text`` around [start:end]."""
    a = max(0, start - pad)
    b = min(len(text), end + pad)
    prefix = "…" if a > 0 else ""
    suffix = "…" if b < len(text) else ""
    return f"{prefix}{text[a:b].strip()}{suffix}"


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = Counter(s)
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _luhn_ok(digits: str) -> bool:
    """Luhn checksum — distinguishes real card numbers from arbitrary id digits."""
    ds = [int(c) for c in digits if c.isdigit()]
    if len(ds) < 13:
        return False
    total, parity = 0, len(ds) % 2
    for i, d in enumerate(ds):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _cap(findings: list) -> list:
    """Keep the highest-scoring findings, bounded by MAX_FINDINGS_PER_EVENT."""
    if len(findings) <= MAX_FINDINGS_PER_EVENT:
        return findings
    return sorted(findings, key=lambda f: f.score, reverse=True)[:MAX_FINDINGS_PER_EVENT]


# --------------------------------------------------------------------------- #
# Base detector
# --------------------------------------------------------------------------- #


@dataclass
class Detector:
    """Base class. Subclasses override :meth:`scan`."""

    name: str
    owasp_id: str
    owasp_name: str
    atlas_technique: str
    atlas_name: str
    severity: str
    description: str = ""

    def scan(self, event: dict) -> list[Finding]:  # pragma: no cover - abstract
        raise NotImplementedError

    def _finding(self, snippet: str, rationale: str, score: float,
                 severity: Optional[str] = None, detector: Optional[str] = None) -> Finding:
        return Finding(
            detector=detector or self.name,
            owasp_id=self.owasp_id,
            owasp_name=self.owasp_name,
            atlas_technique=self.atlas_technique,
            atlas_name=self.atlas_name,
            severity=severity or self.severity,
            score=score,
            matched_snippet=snippet,
            rationale=rationale,
        )


def _applies(event: dict, roles: frozenset, sources: frozenset) -> bool:
    role = (event.get("role") or "").lower()
    source = (event.get("source") or "").lower()
    if roles and role not in roles:
        return False
    if sources and source not in sources:
        return False
    return True


@dataclass
class RegexDetector(Detector):
    """Fires when any compiled pattern matches the event content.

    ``applies_to_roles`` / ``applies_to_sources`` gate *where* the rule looks.
    An empty set means "any". Matching runs against every evasion variant of the
    content (raw / normalized / leet-folded).
    """

    patterns: list[Pattern] = field(default_factory=list)
    applies_to_roles: frozenset = frozenset()
    applies_to_sources: frozenset = frozenset()
    base_score: float = 0.7
    per_match_bonus: float = 0.08

    def scan(self, event: dict) -> list[Finding]:
        if not _applies(event, self.applies_to_roles, self.applies_to_sources):
            return []
        content = event.get("content") or ""
        if not content:
            return []

        findings: list[Finding] = []
        seen: set = set()  # dedup key = (pattern, variant_label, match-span)
        for variant_text, label in match_variants(content):
            for pat in self.patterns:
                for m in pat.finditer(variant_text):
                    # collapse the same logical match seen via different variants
                    span_key = (pat.pattern, m.group(0))
                    if span_key in seen:
                        continue
                    seen.add(span_key)
                    n_matches = sum(1 for _ in pat.finditer(variant_text))
                    score = min(1.0, self.base_score + self.per_match_bonus * (n_matches - 1))
                    evasion = "" if label == "raw" else f" (detected after {label} normalization)"
                    snippet = _clip(variant_text, m.start(), m.end())
                    rationale = (
                        f"{self.description} Pattern matched in a "
                        f"'{event.get('role')}' message on the "
                        f"'{event.get('source')}' channel{evasion}."
                    )
                    findings.append(self._finding(snippet, rationale, score))
                    break  # one finding per pattern is enough
        return findings


def _compile(*patterns: str) -> list[Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


# --------------------------------------------------------------------------- #
# Concrete detectors (input side)
# --------------------------------------------------------------------------- #

# LLM01:2025 — Prompt Injection (DIRECT). The user themself tries to override
# the system / developer instructions.
DIRECT_PROMPT_INJECTION = RegexDetector(
    name="direct_prompt_injection",
    owasp_id="LLM01:2025",
    owasp_name="Prompt Injection",
    atlas_technique="AML.T0051.000",
    atlas_name="LLM Prompt Injection: Direct",
    severity="high",
    description="User attempts to override prior/system instructions.",
    applies_to_roles=frozenset({"user"}),
    base_score=0.8,
    patterns=_compile(
        r"\bignore\s+(?:all\s+|the\s+)?(?:previous|prior|above|earlier|preceding)\s+(?:instructions?|prompts?|rules?|directions?)",
        # qualifier is now REQUIRED (previous|prior|above|system|safety) to avoid
        # matching benign "disregard the formatting rules".
        r"\bdisregard\s+(?:all\s+|the\s+|your\s+)?(?:previous|prior|above|system|safety)\s+(?:instructions?|rules?|guidelines?|prompts?|policy)",
        r"\bforget\s+(?:everything|all|your)\b.{0,40}\b(?:instructions?|rules?|told|above)\b",
        r"\b(?:new|updated|revised)\s+(?:instructions?|system\s+prompt|rules?)\s*:",
        r"\boverride\s+(?:the\s+)?(?:system|safety|previous|your)\b",
        r"\byou\s+are\s+no\s+longer\b",
        r"\bdo\s+not\s+(?:follow|obey|adhere\s+to)\b.{0,30}\b(?:instructions?|rules?|guidelines?|policy)\b",
        r"\bfrom\s+now\s+on\b.{0,40}\b(?:ignore|disregard|no\s+rules?|no\s+restrictions?)\b",
    ),
)

# LLM01:2025 — Prompt Injection (INDIRECT). Injection rides in on content from an
# untrusted channel (RAG document, tool output, fetched web page, email).
INDIRECT_PROMPT_INJECTION = RegexDetector(
    name="indirect_prompt_injection",
    owasp_id="LLM01:2025",
    owasp_name="Prompt Injection",
    atlas_technique="AML.T0051.001",
    atlas_name="LLM Prompt Injection: Indirect",
    severity="critical",
    description="Instructions aimed at the assistant embedded in untrusted retrieved/tool content.",
    applies_to_sources=UNTRUSTED_SOURCES,
    base_score=0.85,
    patterns=_compile(
        r"\b(?:ignore|disregard|forget)\s+(?:all\s+|the\s+)?(?:previous|prior|above|system)\s*(?:instructions?|prompts?|rules?)",
        r"\b(?:assistant|ai|model|system|chatbot)\s*[:,]\s*(?:please\s+)?(?:do|ignore|send|reveal|print|forward|execute|run|email)\b",
        r"<!--.{0,120}\b(?:instruction|prompt|system|ignore|exfiltrate|send)\b.{0,120}-->",
        r"\bwhen\s+you\s+(?:read|see|process)\s+this\b.{0,60}\b(?:do|send|include|reveal|ignore)\b",
        r"\bimportant\s+(?:instruction|note|system\s+message)\s*(?:for\s+(?:the\s+)?(?:ai|assistant|model))?\s*:",
        r"\b(?:append|include|insert)\s+the\s+following\b.{0,40}\b(?:to|in)\s+your\s+(?:response|answer|reply|output)\b",
    ),
)

# LLM01:2025 — Jailbreak / persona override (roleplay attacks, "DAN", etc.).
# Most patterns are case-insensitive; the DAN acronym is case-SENSITIVE and
# context-gated via (?-i:DAN) so the common name "Dan" is not a false positive.
JAILBREAK = RegexDetector(
    name="jailbreak_persona_override",
    owasp_id="LLM01:2025",
    owasp_name="Prompt Injection",
    atlas_technique="AML.T0054",
    atlas_name="LLM Jailbreak",
    severity="high",
    description="Attempt to bypass safety guardrails via persona/roleplay.",
    applies_to_roles=frozenset({"user"}),
    base_score=0.78,
    patterns=(
        _compile(
            r"\bdo\s+anything\s+now\b",
            r"\bdeveloper\s+mode\b",
            r"\b(?:enable|activate|turn\s+on)\b.{0,20}\b(?:jailbreak|unrestricted|uncensored|god)\s*mode\b",
            r"\bpretend\s+(?:you|to\s+be)\b.{0,40}\b(?:no\s+(?:rules?|restrictions?|filters?|guidelines?)|unrestricted|uncensored)\b",
            r"\byou\s+(?:have\s+no|are\s+free\s+from|are\s+without)\b.{0,30}\b(?:restrictions?|rules?|guidelines?|ethical|safety|filters?)\b",
            r"\bact\s+as\b.{0,40}\b(?:unfiltered|uncensored|unrestricted|amoral|evil)\b",
            r"\bhypothetically\b.{0,60}\b(?:no\s+(?:rules?|safety)|illegal|harmful)\b",
            r"\bopposite\s+(?:day|mode)\b",
            r"\bjailbreak\s+mode\b",
        )
        + [
            # DAN: case-sensitive token, must be near a jailbreak cue.
            re.compile(r"\b(?-i:DAN)\s+mode\b", re.IGNORECASE),
            re.compile(
                r"\b(?-i:DAN)\b(?=.{0,40}(?:do anything now|no restrictions?|unrestricted|uncensored|jailbreak))",
                re.IGNORECASE,
            ),
        ]
    ),
)

# LLM07:2025 — System Prompt Leakage (the *attempt* to extract it).
SYSTEM_PROMPT_EXTRACTION = RegexDetector(
    name="system_prompt_extraction",
    owasp_id="LLM07:2025",
    owasp_name="System Prompt Leakage",
    atlas_technique="AML.T0056",
    atlas_name="LLM Meta Prompt Extraction",
    severity="medium",
    description="User probing to reveal the hidden system/developer prompt.",
    applies_to_roles=frozenset({"user"}),
    base_score=0.7,
    patterns=_compile(
        r"\b(?:what|show|tell|reveal|print|repeat|output|give)\b.{0,40}\b(?:your|the)\s+(?:system\s+prompt|initial\s+(?:instructions?|prompt)|original\s+instructions?|developer\s+(?:message|prompt))\b",
        r"\brepeat\s+(?:the\s+)?(?:words?|text|everything)\s+(?:above|before)\b",
        r"\bprint\s+everything\s+above\b",
        r"\bwhat\s+(?:were\s+you\s+(?:told|instructed)|instructions?\s+were\s+you\s+given)\b",
        r"\bbegin(?:ning)?\s+of\s+(?:your\s+)?(?:prompt|instructions?)\b",
        # instruction-laundering and indirection phrasings
        r"\b(?:everything|all\s+text)\s+(?:before|above)\s+(?:this\s+)?(?:line|message|conversation|point)\b",
        r"\b(?:rules?|instructions?|guidelines?)\s+you\s+(?:must|have\s+to|need\s+to)\s+follow\b",
        r"\b(?:translate|summari[sz]e|encode|rephrase)\s+(?:your|the)\s+(?:instructions?|system\s+prompt|rules?)\b",
    ),
)

# LLM06:2025 — Excessive Agency (probing connected tools to take real-world
# actions beyond intended scope). INPUT-side: only scan user / untrusted content.
EXCESSIVE_AGENCY_PROBE = RegexDetector(
    name="excessive_agency_probe",
    owasp_id="LLM06:2025",
    owasp_name="Excessive Agency",
    atlas_technique="AML.T0053",
    atlas_name="AI Agent Tool Invocation",
    severity="high",
    description="Attempt to coerce connected tools/plugins into unintended actions.",
    applies_to_roles=frozenset({"user"}),
    applies_to_sources=frozenset(),  # role gate is enough; user on any channel
    base_score=0.72,
    patterns=_compile(
        # allow an intervening noun: "use the database plugin to drop..."
        r"\b(?:use|call|invoke)\s+(?:the\s+)?(?:\w+\s+)?(?:tool|plugin|function|api)\b.{0,50}\b(?:to\s+)?(?:delete|drop|transfer|send\s+money|wire|email\s+all|exfiltrate|rm\s+-rf)\b",
        r"\b(?:send|forward|email|post)\b.{0,30}\b(?:all|every|the\s+entire)\b.{0,30}\b(?:contacts?|emails?|files?|database|records?)\b.{0,30}\bto\b",
        r"\bexecute\b.{0,20}\b(?:shell|system|os)\s+command\b",
    ),
)


# --------------------------------------------------------------------------- #
# Encoded-payload detector (decodes base64/hex, then re-checks for injection)
# --------------------------------------------------------------------------- #

# Injection signatures re-applied to *decoded* content.
_INJECTION_SIGNATURES = (
    DIRECT_PROMPT_INJECTION.patterns
    + INDIRECT_PROMPT_INJECTION.patterns
    + _compile(r"\bdo\s+anything\s+now\b", r"\bsystem\s+prompt\b", r"\bexfiltrate\b")
)

_B64_TOKEN = re.compile(r"[A-Za-z0-9+/]{16,}={0,2}")
_HEX_TOKEN = re.compile(r"(?:[0-9a-fA-F]{2}){10,}")


@dataclass
class EncodedPayloadDetector(Detector):
    """LLM01:2025 — injection smuggled through base64/hex encoding.

    Two behaviours:
      * On *untrusted* channels, a long high-entropy base64/hex blob is itself
        suspicious (medium).
      * On any user/untrusted content, decode candidate tokens (bounded) and, if
        the decoded text trips an injection signature, raise a critical finding.
    """

    applies_to_roles: frozenset = frozenset({"user"})
    applies_to_sources: frozenset = UNTRUSTED_SOURCES
    max_tokens: int = 25
    max_decoded: int = 8192

    def _decode(self, token: str) -> Optional[str]:
        # base64
        try:
            pad = token + "=" * (-len(token) % 4)
            raw = base64.b64decode(pad, validate=True)
            text = raw.decode("utf-8", errors="strict")
            if text.isprintable() or any(c.isalpha() for c in text):
                return text[: self.max_decoded]
        except (binascii.Error, ValueError, UnicodeDecodeError):
            pass
        # hex
        try:
            if len(token) % 2 == 0:
                raw = bytes.fromhex(token)
                text = raw.decode("utf-8", errors="strict")
                return text[: self.max_decoded]
        except (ValueError, UnicodeDecodeError):
            pass
        return None

    def scan(self, event: dict) -> list[Finding]:
        role = (event.get("role") or "").lower()
        source = (event.get("source") or "").lower()
        is_user = role in self.applies_to_roles
        is_untrusted = source in self.applies_to_sources
        if not (is_user or is_untrusted):
            return []
        content = event.get("content") or ""
        if not content:
            return []

        findings: list[Finding] = []
        tokens = (_B64_TOKEN.findall(content) + _HEX_TOKEN.findall(content))[: self.max_tokens]
        for token in tokens:
            decoded = self._decode(token)
            if not decoded:
                continue
            hit = any(sig.search(decoded) for sig in _INJECTION_SIGNATURES)
            if hit:
                findings.append(self._finding(
                    snippet=(token[:40] + "…  ->  " + decoded[:120]),
                    rationale=("Encoded payload decoded to text containing an injection "
                               "signature — obfuscated prompt injection."),
                    score=0.92,
                    severity="critical",
                    detector="encoded_injection_payload",
                ))
            elif is_untrusted and len(token) >= 32 and _shannon_entropy(token) >= 4.0:
                findings.append(self._finding(
                    snippet=token[:60] + "…",
                    rationale=("Long high-entropy encoded blob in untrusted content — "
                               "possible smuggled payload (decode did not resolve to text)."),
                    score=0.5,
                    severity="medium",
                    detector="suspicious_encoded_blob",
                ))
        return findings


# --------------------------------------------------------------------------- #
# Output / content secret + exfil detectors
# --------------------------------------------------------------------------- #


@dataclass
class SecretLeakDetector(Detector):
    """LLM02:2025 — Sensitive Information Disclosure.

    Scans for secrets / PII. Two instances exist: one scoped to assistant OUTPUT
    (the model disclosing data), one scoped to UNTRUSTED inbound content (secrets
    arriving via RAG/tool/document that feed an exfil chain).
    """

    scan_roles: frozenset = frozenset({"assistant"})
    scan_sources: frozenset = frozenset()
    detector_prefix: str = "sensitive_disclosure"
    rationale_prefix: str = "Assistant output contains"

    # (label, pattern, severity, luhn_required, entropy_min)
    _SECRET_PATTERNS = [
        ("openai_api_key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{20,}\b"), "critical", False, 0.0),
        ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "critical", False, 0.0),
        ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "critical", False, 0.0),
        ("slack_token", re.compile(r"\bxox[baprs]-[0-9A-Za-z\-]{10,}\b"), "critical", False, 0.0),
        ("stripe_key", re.compile(r"\b[rs]k_live_[0-9A-Za-z]{16,}\b"), "critical", False, 0.0),
        ("gitlab_pat", re.compile(r"\bglpat-[0-9A-Za-z_\-]{20,}\b"), "critical", False, 0.0),
        ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[0-9A-Za-z_]{22,})\b"), "critical", False, 0.0),
        ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"), "critical", False, 0.0),
        ("bearer_token", re.compile(r"\b[Bb]earer\s+[A-Za-z0-9\-._~+/]{20,}={0,2}"), "high", False, 0.0),
        ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"), "high", False, 0.0),
        ("generic_secret_assignment", re.compile(r"(?i)\b(?:api[_-]?key|secret|password|passwd|token)\b\s*[=:]\s*['\"]?([A-Za-z0-9_\-/+]{12,})"), "high", False, 3.0),
        ("us_ssn", re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"), "high", False, 0.0),
        ("credit_card", re.compile(r"\b(?:4\d{12}(?:\d{3})?|5[1-5]\d{14}|3[47]\d{13})\b"), "high", True, 0.0),
        ("email_address", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), "info", False, 0.0),
    ]
    # role-alias local-parts that are not, by themselves, sensitive PII.
    _BENIGN_EMAIL_LOCALS = frozenset({"support", "info", "sales", "noreply", "no-reply", "help", "contact", "admin"})

    def scan(self, event: dict) -> list[Finding]:
        if not _applies(event, self.scan_roles, self.scan_sources):
            return []
        content = event.get("content") or ""
        if not content:
            return []
        findings: list[Finding] = []
        for label, pat, sev, needs_luhn, entropy_min in self._SECRET_PATTERNS:
            for m in pat.finditer(content):
                value = m.group(1) if (pat.groups and m.groups()) else m.group(0)
                if needs_luhn and not _luhn_ok(m.group(0)):
                    continue
                if entropy_min and _shannon_entropy(value) < entropy_min:
                    continue
                if label == "email_address":
                    local = m.group(0).split("@", 1)[0].lower()
                    if local in self._BENIGN_EMAIL_LOCALS:
                        continue
                score = {"critical": 0.95, "high": 0.8, "medium": 0.6, "info": 0.3}.get(sev, 0.5)
                findings.append(
                    Finding(
                        detector=f"{self.detector_prefix}_{label}",
                        owasp_id=self.owasp_id,
                        owasp_name=self.owasp_name,
                        atlas_technique=self.atlas_technique,
                        atlas_name=self.atlas_name,
                        severity=sev,
                        score=score,
                        matched_snippet=_clip(content, m.start(), m.end()),
                        rationale=(
                            f"{self.rationale_prefix} a {label.replace('_', ' ')}. "
                            "Possible sensitive-data exposure."
                        ),
                    )
                )
                break  # one finding per secret type per message
        return findings


@dataclass
class MarkdownExfilDetector(Detector):
    """LLM05:2025 — Improper Output Handling / data exfiltration.

    The classic indirect-injection payoff: the model is steered into rendering a
    markdown image/link, bare URL, or HTML attribute whose URL smuggles data to
    an attacker host, or into emitting active content a naive renderer executes.
    """

    _MD_LINK = re.compile(r"!?\[[^\]]*\]\((?P<url>[^)\s]+)[^)]*\)")
    _HTML_ATTR = re.compile(r"(?:href|src)\s*=\s*['\"]?(?P<url>[^'\"\s>]+)", re.IGNORECASE)
    _BARE_URL = re.compile(r"(?P<url>(?:https?|data|blob|javascript):[^\s)<>\"']+)", re.IGNORECASE)
    _ACTIVE_CONTENT = re.compile(
        r"<script\b|javascript:|onerror\s*=|onload\s*=|<img\b[^>]*\bsrc\s*=|data:text/html",
        re.IGNORECASE,
    )
    _SUSPICIOUS_QUERY = re.compile(r"[?&][^\s)]*[A-Za-z0-9%+/_\-]{12,}")

    def _url_is_suspicious(self, url: str) -> bool:
        low = url.lower()
        if low.startswith(("javascript:", "data:", "blob:")):
            return True
        if self._SUSPICIOUS_QUERY.search(url):
            return True
        return False

    def scan(self, event: dict) -> list[Finding]:
        content = event.get("content") or ""
        if not content:
            return []
        findings: list[Finding] = []
        seen_urls: set = set()

        for rx in (self._MD_LINK, self._HTML_ATTR, self._BARE_URL):
            for m in rx.finditer(content):
                url = m.group("url")
                if url in seen_urls:
                    continue
                if self._url_is_suspicious(url):
                    seen_urls.add(url)
                    findings.append(self._finding(
                        snippet=_clip(content, m.start(), m.end()),
                        rationale=("Output contains a URL carrying an encoded query payload "
                                   "or an active scheme — a data-exfiltration channel if "
                                   "auto-rendered by the client."),
                        score=0.9,
                    ))

        am = self._ACTIVE_CONTENT.search(content)
        if am:
            findings.append(self._finding(
                snippet=_clip(content, am.start(), am.end()),
                rationale=("Output embeds active/HTML content (script/onerror/javascript:) "
                           "that an unsanitized downstream renderer could execute — "
                           "improper output handling."),
                score=0.85,
            ))
        return findings


SECRET_LEAK_OUTPUT = SecretLeakDetector(
    name="sensitive_information_disclosure",
    owasp_id="LLM02:2025",
    owasp_name="Sensitive Information Disclosure",
    atlas_technique="AML.T0057",
    atlas_name="LLM Data Leakage",
    severity="high",
    description="Secrets or PII present in model output.",
    scan_roles=frozenset({"assistant"}),
    detector_prefix="sensitive_disclosure",
    rationale_prefix="Assistant output contains",
)

SECRET_LEAK_INBOUND = SecretLeakDetector(
    name="sensitive_information_inbound",
    owasp_id="LLM02:2025",
    owasp_name="Sensitive Information Disclosure",
    atlas_technique="AML.T0057",
    atlas_name="LLM Data Leakage",
    severity="high",
    description="Secrets present in untrusted inbound content.",
    scan_roles=frozenset(),
    scan_sources=UNTRUSTED_SOURCES,
    detector_prefix="inbound_secret",
    rationale_prefix="Untrusted inbound content contains",
)

ENCODED_PAYLOAD = EncodedPayloadDetector(
    name="encoded_injection_payload",
    owasp_id="LLM01:2025",
    owasp_name="Prompt Injection",
    atlas_technique="AML.T0051.001",
    atlas_name="LLM Prompt Injection: Indirect",
    severity="critical",
    description="Injection smuggled via base64/hex encoding.",
)

MARKDOWN_EXFIL = MarkdownExfilDetector(
    name="improper_output_handling",
    owasp_id="LLM05:2025",
    owasp_name="Improper Output Handling",
    atlas_technique="AML.T0024",
    atlas_name="Exfiltration via AI Inference API",
    severity="high",
    description="Output smuggles data or active content.",
)


# --------------------------------------------------------------------------- #
# Registry + top-level API
# --------------------------------------------------------------------------- #

ALL_DETECTORS: list[Detector] = [
    DIRECT_PROMPT_INJECTION,
    INDIRECT_PROMPT_INJECTION,
    JAILBREAK,
    SYSTEM_PROMPT_EXTRACTION,
    EXCESSIVE_AGENCY_PROBE,
    ENCODED_PAYLOAD,
    SECRET_LEAK_OUTPUT,
    SECRET_LEAK_INBOUND,
    MARKDOWN_EXFIL,
]


def detect(event: dict, detectors: Optional[list[Detector]] = None) -> list[Finding]:
    """Run every applicable detector against one normalized event."""
    findings: list[Finding] = []
    for det in detectors if detectors is not None else ALL_DETECTORS:
        findings.extend(det.scan(event))
    return _cap(findings)


def detect_many(events: Iterable[dict]) -> list[tuple[dict, list[Finding], str]]:
    """Run detection across many events.

    Returns (event, findings, event_severity) triples — the per-event severity
    rollup is the analyst's headline verdict for the row.
    """
    out = []
    for ev in events:
        f = detect(ev)
        out.append((ev, f, event_severity(f)))
    return out


def detector_catalog() -> list[dict]:
    """Machine-readable inventory of detectors -> OWASP/ATLAS mapping."""
    return [
        {
            "name": d.name,
            "owasp_id": d.owasp_id,
            "owasp_name": d.owasp_name,
            "atlas_technique": d.atlas_technique,
            "atlas_name": d.atlas_name,
            "severity": d.severity,
            "description": d.description,
        }
        for d in ALL_DETECTORS
    ]
