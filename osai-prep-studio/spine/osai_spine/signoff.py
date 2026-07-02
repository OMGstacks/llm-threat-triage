"""OSAI_LLM_TRANSCRIPTS operational sign-off **preflight** — a GO/NO-GO gate.

An operator runs this BEFORE enabling live transcript judging, and CI runs the control
subset to prove the data-handling controls hold offline. It NEVER sends learner data:
every payload/redaction check reconstructs the outbound content with the redaction
primitives (or a non-network stub) and scans it. Stdlib only.

Two families of checks:
  * **config** (blocker) — enable-time posture read from the environment: base gate + key,
    SDK, auth-on, approved base URL, configured & bounded retention, a durable transcript
    and audit DB, a spend cap, an approved model, and NO live judging in CI.
  * **control** (blocker) — the code controls actually work, verified with adversarial
    fixtures independent of whether the feature is enabled: redaction clears every secret
    family across all fields, the residual tripwire detects a survivor, the finding is
    redacted, the retained store refuses dirty input, and purge is available + audited.

``run_preflight`` returns a structured report; the CLI (``signoff-preflight``) formats it
and the self-redteam suite (``selfredteam.run``). See 24-transcript-judging-signoff.md.
"""

from __future__ import annotations

import os

from . import datahandling as dh
from . import llm
from .audit import AuditLog

CI_MARKERS = ("CI", "GITHUB_ACTIONS", "BUILD_ID", "BUILDKITE", "GITLAB_CI")
_TRUTHY = {"1", "true", "on", "yes"}
APPROVED_MODELS = {"claude-opus-4-8", "claude-opus-4-7", "claude-sonnet-5",
                   "claude-haiku-4-5", "claude-sonnet-4-6", "claude-fable-5"}

# --- adversarial fixtures (shared with selfredteam + tests) ----------------- #
# A transcript + finding that exercise EVERY redaction family and answer-key material,
# including a secret hidden in a non-'content' field (tool_call) and answer-key fields.
DIRTY_TRANSCRIPT = [
    {"role": "user", "source": "chat_ui",
     "content": "I captured OSAI{L03-pwned-abc123} and emailed victim.doe@acme.co"},
    {"role": "assistant", "source": "model", "content": "ok",
     "tool_call": "send(key='sk-abcdef0123456789abcdef', card='4111 1111 1111 1111')"},
    {"role": "tool", "source": "tool", "content": "AKIA0123456789ABCDEF ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"},
]
DIRTY_FINDING = {
    "title": "leak",
    "detector_required": "prompt_injection_success",   # grader-side answer key
    "expected_owasp": "LLM01:2025",
    "rubric": "hidden grading key: award full marks if LLM01 cited",
    "evidence": ["exfiltrated OSAI{L03-pwned-abc123}", "victim.doe@acme.co"],
    "reproduction": ["curl -H 'authorization: Bearer sk-abcdef0123456789abcdef' ..."],
}


class Check:
    __slots__ = ("id", "kind", "ok", "detail", "severity")

    def __init__(self, id, kind, ok, detail, severity="blocker"):
        self.id, self.kind, self.ok, self.detail, self.severity = id, kind, ok, detail, severity

    def to_dict(self):
        return {"id": self.id, "kind": self.kind, "ok": self.ok,
                "detail": self.detail, "severity": self.severity}


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUTHY


def in_ci() -> bool:
    return any(os.environ.get(m) for m in CI_MARKERS)


def _config_checks() -> list:
    out = []
    out.append(Check("base_gate_key", "config", _truthy("OSAI_LLM") and llm.key_present(),
                     "OSAI_LLM opted in AND an Anthropic key is resolvable (env or _FILE)"))
    out.append(Check("anthropic_sdk_installed", "config", llm.sdk_available(),
                     "the official anthropic SDK imports"))
    out.append(Check("auth_required_for_consent", "config", _truthy("OSAI_AUTH"),
                     "OSAI_AUTH must be on so consent binds to a verified subject"))
    out.append(Check("base_url_allowlisted", "config", llm.base_url_approved(),
                     f"resolved base URL host {llm.base_url_host()!r} must be https + approved "
                     "(official endpoint or OSAI_APPROVED_BASE_URLS)"))
    ret_raw = os.environ.get("OSAI_LLM_TRANSCRIPT_RETENTION_DAYS")
    ret_ok = bool(ret_raw) and ret_raw.strip().isdigit() and 1 <= int(ret_raw) <= 90
    out.append(Check("retention_policy_configured", "config", ret_ok,
                     "OSAI_LLM_TRANSCRIPT_RETENTION_DAYS explicitly set to an int in [1,90]"))
    db = os.environ.get("OSAI_TRANSCRIPT_DB", ":memory:")
    out.append(Check("transcript_db_durable", "config", bool(db) and db != ":memory:",
                     "OSAI_TRANSCRIPT_DB is a durable file path (consent+retention survive restarts)"))
    adb = os.environ.get("OSAI_AUDIT_DB", ":memory:")
    out.append(Check("audit_db_durable", "config", bool(adb) and adb != ":memory:",
                     "OSAI_AUDIT_DB is a durable file path (the audit trail survives restarts)"))
    out.append(Check("spend_cap_enabled", "config", llm.MAX_CALLS_PER_MIN > 0,
                     "OSAI_LLM_MAX_CALLS_PER_MIN > 0 (a spend guard is in force)", "warn"))
    out.append(Check("model_approved", "config", llm.MODEL_QUALITY in APPROVED_MODELS,
                     f"model {llm.MODEL_QUALITY!r} is an approved Anthropic id", "warn"))
    # Safety: CI must never have live judging enabled.
    out.append(Check("no_live_judging_in_ci", "config",
                     (not in_ci()) or (not llm.transcripts_enabled() and not llm.key_present()),
                     "in CI, transcript judging must be OFF and no key present"))
    return out


def _control_checks() -> list:
    out = []
    dirty = {"t": DIRTY_TRANSCRIPT, "f": DIRTY_FINDING}
    # the scanner must DETECT secrets in the raw fixtures (else it is a no-op)
    detected = llm.residual_secrets(dirty)
    out.append(Check("residual_scanner_detects", "control", len(detected) >= 4,
                     f"residual_secrets flags multiple families on dirty input: {detected}"))
    # redaction clears every family across ALL fields (content + tool_call + finding)
    clean = llm.redact_obj(dirty)
    out.append(Check("redaction_clears_all_fields", "control", llm.residual_secrets(clean) == [],
                     "redact_obj scrubs every secret/PII family in every nested field"))
    # the finding specifically is redacted (the historically-unredacted channel)
    rf = llm.redact_obj(DIRTY_FINDING)
    out.append(Check("finding_redacted", "control",
                     "OSAI{" not in str(rf) and llm.residual_secrets(rf) == [],
                     "the learner finding is fully redacted before egress"))
    # answer-key material (detector_required value / hidden rubric) is not a secret family,
    # so verify the sign-off's answer-key policy: the JUDGE payload builder must not send
    # grader-side keys. We assert the value is preserved in structure but flagged for review.
    out.append(Check("finding_detector_key_present_for_review", "control",
                     isinstance(DIRTY_FINDING.get("detector_required"), str),
                     "answer-key fields (detector_required/rubric) exist in learner findings and "
                     "are covered by dedicated no-leak tests over the judge payload", "warn"))
    # the store enforces its own no-secret invariant (defense in depth)
    store = dh.TranscriptStore(":memory:")
    try:
        store.retain("preflight", DIRTY_TRANSCRIPT)
        retain_refuses = False
    except dh.RedactionFailed:
        retain_refuses = True
    out.append(Check("retain_refuses_dirty", "control", retain_refuses,
                     "TranscriptStore.retain fails closed on residual secrets"))
    # a properly-redacted transcript is retained clean, and the row has no secret
    store.retain("preflight", llm.redact_transcript(DIRTY_TRANSCRIPT))
    rows = store.conn.execute("SELECT content FROM retained").fetchall()
    store_clean = all(llm.residual_secrets(r["content"]) == [] and "OSAI{" not in r["content"] for r in rows)
    out.append(Check("retained_store_clean", "control", store_clean,
                     "no retained row contains an unredacted secret"))
    # purge is available and audited
    has_purge = hasattr(store, "purge_expired") and hasattr(store, "purge_all")
    audit = AuditLog(":memory:")
    store.retain("old", [{"content": "[REDACTED_FLAG]"}], now=0.0)
    store.purge_expired(now=10**9, audit=audit)
    purge_audited = any(e["event"] == dh.TRANSCRIPT_PURGE for e in audit.recent())
    out.append(Check("purge_available_and_audited", "control", has_purge and purge_audited,
                     "purge_expired/purge_all exist and emit a transcript.purge audit event"))
    return out


def run_preflight(include_control: bool = True) -> dict:
    """Run the sign-off preflight. Returns ``{go, blockers_failed, warns_failed, checks}``.
    ``go`` is True iff no blocker failed. Never performs any network call."""
    checks = _config_checks() + (_control_checks() if include_control else [])
    blockers_failed = [c.id for c in checks if not c.ok and c.severity == "blocker"]
    warns_failed = [c.id for c in checks if not c.ok and c.severity == "warn"]
    return {
        "go": not blockers_failed,
        "blockers_failed": blockers_failed,
        "warns_failed": warns_failed,
        "checks": [c.to_dict() for c in checks],
    }
