# OSAI_LLM_TRANSCRIPTS — Operational Sign-Off & Self-Redteam Preflight

> Enabling `OSAI_LLM_TRANSCRIPTS` sends **learner attack transcripts** (and their written
> findings) to the Anthropic API for an optional report critique. That crosses into
> sensitive territory — learner inputs, lab attempts, possible flags/PII, provider-side
> retention — so it is treated as an **operational security release**, not a normal
> feature. This is the **GO/NO-GO artifact**: the feature stays OFF until every blocker
> here passes and the self-redteam is clean. Companions:
> [11-safety-legal-ethics.md](11-safety-legal-ethics.md),
> [13-platform-threat-model.md](13-platform-threat-model.md),
> [04-evaluation-harness.md](04-evaluation-harness.md) §6.
>
> Framing: NIST AI RMF / AI 600-1 (generative-AI risk management) and the OWASP GenAI
> project (LLM Top 10, AI red-teaming) — data-flow, consent, redaction, audit, retention,
> rollback, and a preflight gate before the capability is turned on.

## 1. Purpose & scope

Two opt-in gates guard the generative layer ([`llm.py`](spine/osai_spine/llm.py)):
`llm.enabled()` (`OSAI_LLM=1` + key + SDK) for the **low-risk public-corpus tutor**, and
`llm.transcripts_enabled()` (that **plus** `OSAI_LLM_TRANSCRIPTS=1`) for any path that would
send **learner content** — today only the optional report critique
(`POST /reports/review` → `report.judge_report_narrative`). This document governs the
second gate only. Default posture: **both off; deterministic, offline, no key**.

## 2. GO / NO-GO decision checklist

Run `python -m osai_spine.cli signoff-preflight`. It prints every check and a verdict, and
exits non-zero unless **all blockers pass and the self-redteam is clean**. It never makes a
network call. Blockers (from [`signoff.py`](spine/osai_spine/signoff.py)):

| id | what it asserts |
|---|---|
| `base_gate_key` | `OSAI_LLM=1` **and** an Anthropic key resolvable (env or `ANTHROPIC_API_KEY_FILE`) |
| `anthropic_sdk_installed` | the official `anthropic` SDK imports |
| `auth_required_for_consent` | `OSAI_AUTH=1` — consent binds to a **verified** subject, not a client-supplied id |
| `base_url_allowlisted` | resolved base URL is **https + official/approved** (§10) |
| `retention_policy_configured` | `OSAI_LLM_TRANSCRIPT_RETENTION_DAYS` explicitly set, int, in [1,90] |
| `transcript_db_durable` | `OSAI_TRANSCRIPT_DB` is a durable file (consent + retention survive restarts) |
| `audit_db_durable` | `OSAI_AUDIT_DB` is a durable file (the audit trail survives restarts) |
| `no_live_judging_in_ci` | in CI, judging is OFF and no key is present |
| `residual_scanner_detects` / `redaction_clears_all_fields` / `finding_redacted` | the redaction pipeline detects and clears every family, in every field, including the finding |
| `retain_refuses_dirty` / `retained_store_clean` | the store fails closed on residual secrets |
| `purge_available_and_audited` | purge exists and emits an audit event |

Warnings (record, don't block): `spend_cap_enabled`, `model_approved`,
`finding_detector_key_present_for_review`.

**Record in the artifact** (the boolean `/health` fields are not enough — capture manually):
provider, resolved **model id**, resolved **base_url host**, **retention posture** (§9),
**review_date**, an **expiry**, and the **approver**.

## 3. Data-flow diagram

```mermaid
flowchart LR
  L[Learner: transcript + written finding] --> R[POST /reports/review]
  R --> RUB[ReportReviewer.review — deterministic rubric card (always, offline)]
  R -->|only if provider + OSAI_LLM_TRANSCRIPTS + consent| CK[datahandling.prepare_for_judging]
  CK -->|gate off| X1[TranscriptsDisabled → rubric only]
  CK -->|no consent| X2[ConsentRequired → rubric only]
  CK -->|redact all fields + residual tripwire| RED[redacted transcript]
  RED --> RET[(retained ≤ N days, redacted-only, audited)]
  RED --> J[report.judge_report_narrative]
  J -->|gate + approved base-url + redact FINDING + re-verify both| P[Anthropic API]
  J -->|any failure| X3[fail closed → rubric only]
  P --> N[narrative critique in the HTTP response]
```

## 4. Consent & learner disclosure

Consent is **required, revocable, and bound to a verified subject** (`OSAI_AUTH` on).
API: `GET/POST/DELETE /auth/consent`; store `datahandling.TranscriptStore`. Revocation
**erases** that learner's already-retained rows (`revoke_consent` returns the count).
The disclosure copy shown before consent must state, plainly: what is sent (the **redacted
transcript and the finding**), that it goes to a **third-party model provider (Anthropic)**,
that provider-side **retention and possible human review** apply per the current terms
(§9 — do **not** promise zero-retention), the on-box retention window, and how to revoke.

## 5. Redaction review (as built)

`llm.redact_obj` recursively scrubs **every string leaf and every string dict key** of a
finding/transcript (content, `tool_call`, `source`, nested dicts/lists, and keys) — not
just `content`. Families (`llm._REDACTIONS`): `OSAI{…}` flags (incl. an **unclosed** flag),
emails, AWS `AKIA`, `sk-`/`sk_live_`/`rk_`/`pk_` API keys, GitHub classic + `github_pat_`
tokens, Slack `xox`/`xapp-` tokens, PEM private-key blocks (incl. a **truncated** header),
and PANs (space/dash/**dot** separated). `redact_transcript` and the finding path both go
through it. **Grader-side answer-key fields** (`detector_required`, `rubric`, …) are
**stripped** from the finding before egress (`report._strip_grader_keys`); the learner's own
OWASP claim is kept for the critique.

## 6. Post-redaction re-verification & closed gaps

`llm.residual_secrets(obj)` re-scans **all fields, all string keys, and the fully-serialized
form** (`json.dumps(default=str)`) for every family, and returns any survivors; a non-empty
result **fails closed** everywhere it is used. The serialized scan catches what a string-leaf
walk cannot — a secret in a **dict key**, or a **non-string leaf** (e.g. a PAN sent as a JSON
number that `default=str` would stringify onto the wire) — so such a finding is **rejected**,
not sent. Gaps found in the pre-sign-off enumeration **and** the adversarial verification
pass, all **closed here**:

- **finding was sent unredacted** → `judge_report_narrative` now strips grader keys, redacts
  the finding, and re-verifies it (and the transcript) before building the payload.
- **only `content` was redacted** → all fields **and dict keys** are redacted (a secret in
  `tool_call` or a key can't leave the box or land in the store).
- **flag-only tripwire** → every secret/PII family is re-checked, across all fields, keys,
  and the serialized form, on the wire **and** before retention.
- **non-string / key secrets bypassed both layers** → the serialized residual scan catches
  them and fails closed.
- **`judge_report_narrative` was a footgun** → it self-enforces the gate + approved base URL
  + grader-key stripping + redaction; **consent** is enforced upstream by
  `prepare_for_judging` (this seam has no store/learner).
- **base URL unvalidated** → allowlist + preflight enforcement (§10).

## 7. Audit trail

`audit.AuditLog` records `transcript.judge`, `transcript.consent_grant/revoke`, and
`transcript.purge` with **actor + counts only, never content** (verified by a test). Requires
a durable `OSAI_AUDIT_DB`.

## 8. Retention & deletion (on-box)

Only **redacted** transcripts are retained, timestamped, bounded by
`OSAI_LLM_TRANSCRIPT_RETENTION_DAYS` (default 7). `purge_expired` deletes past the window
(audited); consent revocation erases per-learner rows. `oldest_retained_ts` is surfaced for
posture checks.

## 9. Provider / API data-handling checklist (verify AT ENABLE TIME)

> **Do not assert "Anthropic zero-retention" as a fact.** Retention varies by plan/contract;
> consumer/model-improvement data may be retained de-identified for up to ~5 years, and
> policy-flagged content up to ~2 years; commercial/API terms differ; ZDR is a
> per-account/contract configuration, not a default — and some models are unavailable under
> ZDR. Because the outbound payload includes the learner **finding**, provider retention
> directly governs how long real learner content persists off-box.

- [ ] Verify the **current commercial/API terms + DPA** for **this** account/org/workspace as of `review_date` (the load-bearing GO condition, not a formality).
- [ ] Confirm **in writing** whether prompts **and** outputs are retained for (a) safety/abuse review, (b) operational logging, (c) legal hold — and for how long each.
- [ ] Confirm whether inputs/outputs are used for **training / model improvement**; record the specific term.
- [ ] Confirm whether **ZDR** applies to this org/key/workspace, and that the **chosen model** is available under it.
- [ ] Verify **data residency / region** and the **sub-processor list** meet requirements; record the pinned region.
- [ ] Confirm the API credential is scoped to the intended workspace and loaded from env or `ANTHROPIC_API_KEY_FILE` **only** — never hardcoded/logged (`cli llm` / `/health` print presence only).
- [ ] Establish the **abuse/T&S escalation path**; ensure the consent copy covers provider-side human review + extended retention for flagged content.
- [ ] Confirm the tier's **cost/rate limits** and that the `MAX_CALLS_PER_MIN` spend guard is in force.
- [ ] Record **provider + model + base_url + retention_posture + review_date + expiry + approver** in the artifact; set a **re-review cadence** (renewal / terms change).

## 10. Base-URL policy & preflight gate

The transcript path may carry learner content, so its endpoint must be **the official
Anthropic endpoint by default**. `llm.resolve_base_url()` resolves in precedence order
(`OSAI_ANTHROPIC_BASE_URL` → `ANTHROPIC_BASE_URL` → official) and `llm.base_url_approved()`
requires **https + official-or-allowlisted**. `judge_report_narrative` and the preflight
**fail closed** on a non-approved URL. A custom/proxy base URL is a **new sub-processor**:
forbidden until the exact URL is listed in `OSAI_APPROVED_BASE_URLS` **and** passed its own
provider review. Any base-URL change after sign-off **invalidates** it. `/health` and the
preflight surface the resolved **host** (never a secret). In an agent-proxy host (e.g. a
Claude Code session), `ANTHROPIC_BASE_URL` points at the proxy — so the default is **not**
official there and the preflight will (correctly) refuse until the operator approves it.

## 11. Cost, rate limits & abuse controls

`MAX_CALLS_PER_MIN` (default 20; `0` disables — a warn) caps live calls per rolling minute;
a hammered `/reports/review` degrades to **rubric-only**, not unbounded egress. Record the
account's model-tier cost/limits.

## 12. Fail-closed behavior

Every failure path defaults to the deterministic rubric card, never a silent send:
gate off (`TranscriptsDisabled`), no consent (`ConsentRequired`), unapproved base URL
(`TranscriptsDisabled`), residual secret (`RedactionFailed`), rate-limited / API error →
caught by `api.py`, `narrative_critique = None`.

## 13. Incident response: rollback & kill-switch

- **Disable instantly:** unset `OSAI_LLM_TRANSCRIPTS` (or `OSAI_LLM`) → `transcripts_enabled()`
  is False → all sends fail closed. Restart not required for new requests.
- **Erase retained data:** `python -m osai_spine.cli transcripts purge-all --db $OSAI_TRANSCRIPT_DB`
  (`TranscriptStore.purge_all`, audited) deletes every retained row. Per-learner: revoke consent.
- **Off-box data:** already-sent payloads are governed by provider retention (§9) — file the
  provider deletion/abuse path if required.

## 14. Sign-off record & re-review cadence

The artifact must carry: provider, model id, resolved base_url host, retention posture,
`review_date`, **expiry**, approver, and the preflight/self-redteam run output. **Past
expiry, transcript-judging must be treated as OFF until re-reviewed.** Re-run the preflight
and re-verify §9 at every contract renewal, terms change, or base-URL change.

## Enforcement (CI)

The control subset runs offline in CI ([`tests/test_transcript_signoff.py`](spine/tests/test_transcript_signoff.py)
+ [`selfredteam.py`](spine/osai_spine/selfredteam.py)): redaction covers every field/family,
the store + choke point fail closed, the judge payload and retained store carry no secret,
the base-URL allowlist holds, and the self-redteam (tutor + payload + storage) is clean —
**the build fails on any leak**. The operator-time config blockers (key, auth, durable DBs,
approved base URL) are verified by `signoff-preflight` at enable time.

## Cross-references
[03-tutor-examiner-bot.md](03-tutor-examiner-bot.md) · [04-evaluation-harness.md](04-evaluation-harness.md) · [08-reporting-and-canva.md](08-reporting-and-canva.md) · [11-safety-legal-ethics.md](11-safety-legal-ethics.md) · [13-platform-threat-model.md](13-platform-threat-model.md)
