"""Operational data-handling controls for learner-transcript processing.

The generative seam has two gates (``llm.enabled`` for the low-risk public-corpus
tutor, and ``llm.transcripts_enabled`` for paths that would send *learner attack
transcripts* to the API). The second gate is held OFF until the controls in this module
are in place; this module IS those controls, so the gate can be flipped safely:

  1. **Consent** — a learner's transcripts are never processed without a recorded,
     revocable consent (``TranscriptStore``).
  2. **Redaction** — content is scrubbed of flags / secrets / PII (``llm.redact_*``)
     and re-checked here (defense in depth) before anything can leave the box.
  3. **Bounded retention** — any retained (already-redacted) transcript carries a
     timestamp and is purgeable after ``OSAI_LLM_TRANSCRIPT_RETENTION_DAYS`` (default 7);
     ``purge_expired`` actually deletes.
  4. **Audit** — every judging/consent/purge action is recorded (actor + counts, never
     content) via the shared :class:`~osai_spine.audit.AuditLog`.

``prepare_for_judging`` is the single enforcement choke point every transcript-sending
path MUST call — it fails closed (raises) unless the gate is on, consent exists, and
redaction is verified. Stdlib only.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time

from . import llm

_TRUTHY = {"1", "true", "on", "yes"}
RETENTION_DAYS_DEFAULT = 7

# Audit event names (recorded via audit.AuditLog; free-form is accepted there).
TRANSCRIPT_JUDGE = "transcript.judge"
TRANSCRIPT_CONSENT_GRANT = "transcript.consent_grant"
TRANSCRIPT_CONSENT_REVOKE = "transcript.consent_revoke"
TRANSCRIPT_PURGE = "transcript.purge"

class TranscriptsDisabled(RuntimeError):
    """Raised when transcript judging is attempted while the gate is off."""


class ConsentRequired(RuntimeError):
    """Raised when a learner has not consented to transcript processing."""


class RedactionFailed(RuntimeError):
    """Raised when a flag/secret survives redaction — the transcript is not sent."""


def retention_days() -> int:
    """Retention window for redacted transcripts, from
    ``OSAI_LLM_TRANSCRIPT_RETENTION_DAYS`` (default 7, floor 1)."""
    try:
        d = int(os.environ.get("OSAI_LLM_TRANSCRIPT_RETENTION_DAYS", RETENTION_DAYS_DEFAULT))
    except ValueError:
        d = RETENTION_DAYS_DEFAULT
    return max(1, d)


class TranscriptStore:
    """SQLite-backed consent registry + bounded store of redacted transcripts."""

    def __init__(self, db_path: str = ":memory:"):
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self._lock:
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS consent ("
                "  learner    TEXT PRIMARY KEY,"
                "  granted_ts REAL,"
                "  revoked_ts REAL)"
            )
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS retained ("
                "  id         INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  learner    TEXT NOT NULL,"
                "  created_ts REAL NOT NULL,"
                "  content    TEXT NOT NULL)"       # already redacted before it gets here
            )
            self.conn.commit()

    # --- consent -----------------------------------------------------------
    def record_consent(self, learner: str, now: float | None = None) -> None:
        now = float(now) if now is not None else time.time()
        with self._lock:
            self.conn.execute(
                "INSERT INTO consent(learner,granted_ts,revoked_ts) VALUES(?,?,NULL) "
                "ON CONFLICT(learner) DO UPDATE SET granted_ts=?, revoked_ts=NULL",
                (learner, now, now),
            )
            self.conn.commit()

    def revoke_consent(self, learner: str, now: float | None = None) -> int:
        """Revoke consent AND erase that learner's already-retained (redacted) transcripts
        — revocation should stop future processing and remove prior retained data. Returns
        the number of retained rows deleted."""
        now = float(now) if now is not None else time.time()
        with self._lock:
            self.conn.execute(
                "UPDATE consent SET revoked_ts=? WHERE learner=?", (now, learner)
            )
            cur = self.conn.execute("DELETE FROM retained WHERE learner=?", (learner,))
            self.conn.commit()
            return int(cur.rowcount)

    def has_consent(self, learner: str) -> bool:
        if not learner:
            return False
        row = self.conn.execute(
            "SELECT granted_ts, revoked_ts FROM consent WHERE learner=?", (learner,)
        ).fetchone()
        return bool(row and row["granted_ts"] is not None and row["revoked_ts"] is None)

    # --- retention ---------------------------------------------------------
    def retain(self, learner: str, redacted_transcript, now: float | None = None) -> int:
        """Persist an ALREADY-REDACTED transcript with a timestamp for later purge.
        Returns the row id. The store enforces its OWN invariant (defense in depth): it
        re-scans the whole record and **refuses** (``RedactionFailed``) if any secret/PII
        survives — so the 'already redacted' guarantee cannot be silently violated."""
        import json
        residual = llm.residual_secrets(redacted_transcript)
        if residual:
            raise RedactionFailed(
                f"refusing to retain a transcript with residual secrets ({', '.join(residual)})"
            )
        now = float(now) if now is not None else time.time()
        payload = json.dumps(redacted_transcript, separators=(",", ":"))
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO retained(learner,created_ts,content) VALUES(?,?,?)",
                (learner, now, payload),
            )
            self.conn.commit()
            return int(cur.lastrowid)

    def count_retained(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM retained").fetchone()[0])

    def oldest_retained_ts(self) -> float | None:
        row = self.conn.execute("SELECT MIN(created_ts) AS t FROM retained").fetchone()
        return row["t"] if row and row["t"] is not None else None

    def purge_expired(self, now: float | None = None, days: int | None = None, audit=None) -> int:
        """Delete retained transcripts older than the retention window. Records a
        ``transcript.purge`` audit event (counts only) when an ``audit`` log is given.
        Returns the number of rows purged."""
        now = float(now) if now is not None else time.time()
        days = retention_days() if days is None else days
        cutoff = now - days * 86400
        with self._lock:
            cur = self.conn.execute("DELETE FROM retained WHERE created_ts < ?", (cutoff,))
            self.conn.commit()
            n = int(cur.rowcount)
        if audit is not None:
            audit.record(TRANSCRIPT_PURGE, actor="system",
                         detail={"purged": n, "reason": "expired", "retention_days": days}, now=now)
        return n

    def purge_all(self, audit=None, now: float | None = None) -> int:
        """Delete ALL retained transcripts immediately — the incident rollback / kill
        switch (24-transcript-judging-signoff.md §13). Returns the number purged."""
        with self._lock:
            cur = self.conn.execute("DELETE FROM retained")
            self.conn.commit()
            n = int(cur.rowcount)
        if audit is not None:
            audit.record(TRANSCRIPT_PURGE, actor="system",
                         detail={"purged": n, "reason": "kill_switch"}, now=now)
        return n


def prepare_for_judging(transcript, learner: str, *, store: TranscriptStore,
                        audit=None, now: float | None = None, retain: bool = True):
    """The single enforcement choke point for any path that would send a learner
    transcript to the API. Fails closed:

      * ``TranscriptsDisabled`` if ``llm.transcripts_enabled()`` is False;
      * ``ConsentRequired`` if the learner has no active consent;
      * ``RedactionFailed`` if a flag survives redaction.

    On success returns ``(redacted_transcript, retained_id_or_None)`` and records a
    ``transcript.judge`` audit event (counts only, never content)."""
    if not llm.transcripts_enabled():
        raise TranscriptsDisabled(
            "transcript judging is disabled — enable OSAI_LLM (+key/SDK) and "
            "OSAI_LLM_TRANSCRIPTS only once these data-handling controls are signed off"
        )
    if not store.has_consent(learner):
        raise ConsentRequired(
            f"learner {learner!r} has not consented to transcript processing"
        )
    redacted = llm.redact_transcript(transcript)
    # Defense-in-depth: re-verify EVERY secret/PII family across ALL fields (not just a
    # surviving flag in 'content'); a residual hit fails closed — nothing is sent or kept.
    residual = llm.residual_secrets(redacted)
    if residual:
        raise RedactionFailed(
            f"secrets survived redaction ({', '.join(residual)}); refusing to send the transcript"
        )
    rec_id = store.retain(learner, redacted, now=now) if retain else None
    if audit is not None:
        audit.record(
            TRANSCRIPT_JUDGE, actor=learner,
            detail={"events": len(redacted), "retention_days": retention_days(),
                    "record_id": rec_id, "retained": bool(retain)},
            now=now,
        )
    return redacted, rec_id


def policy_status(store: TranscriptStore | None = None) -> dict:
    """Operator-facing summary of the data-handling posture (no content)."""
    return {
        "transcripts_enabled": llm.transcripts_enabled(),
        "consent_required": True,
        "retention_days": retention_days(),
        "redaction": "flags/secrets/PII scrubbed and re-verified (all fields) before send",
        "retained_count": store.count_retained() if store is not None else None,
        "oldest_retained_ts": store.oldest_retained_ts() if store is not None else None,
        "base_url_approved": llm.base_url_approved(),
    }
