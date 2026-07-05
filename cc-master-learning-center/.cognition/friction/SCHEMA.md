# Friction Diary — Canonical Entry Schema

This document is the single shared spec. Both the JSONL storage format
(`friction_log.jsonl`) and the generated Markdown view (`friction_render.py`
output) MUST conform to it. If you change a field here, update both
`friction_cli.py` and `friction_render.py` in the same change.

Each JSONL line is one JSON object with exactly the fields below (nullable
fields must still be present, set to `null`, until populated).

## Field reference

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | Project-chosen prefix + incrementing number, e.g. `"GAP-7"`. Derived as `max(existing numeric suffix for that prefix) + 1`. **Never reused**, even if an entry is later `DISQUALIFIED`. |
| `title` | string | yes | One-line summary. |
| `status` | enum | yes | See **Status lifecycle** below. |
| `created_date` | string (`YYYY-MM-DD`) | yes | ISO date the entry was first logged. |
| `last_seen_date` | string (`YYYY-MM-DD`) | yes | ISO date of the most recent evidence (mirrors the last `evidence_log` entry's date; also bumped on creation). |
| `affected_component` | string (free text) | yes | What part of the system this touches. Generic tooling never parses this — it's for humans and for `review`'s keyword search. |
| `domain_extensions` | object | yes (may be `{}`) | **Open bucket** for project-specific taxonomy (e.g. `"plane"`, `"program"`, `"team"`). Generic tooling (CLI, render, threshold config) MUST NOT depend on any key inside this object. This is what makes the schema portable across projects with different classification vocabularies. |
| `recurrence_count` | integer | yes | Starts at `1` on creation (the act of logging it is itself the first observation). Incremented by `bump`. |
| `evidence_log` | array of `{date, note}` | yes (may be `[]` at creation, but `log` seeds one entry) | One entry per time the friction was observed. `date` is `YYYY-MM-DD`, `note` is free text (what happened, what was manually done that time). |
| `manual_procedure` | string | yes | What is done by hand today, and *why* it's currently manual. |
| `proposed_fix` | string | yes | Forward-looking one-paragraph sketch of what the automation would look like. Does not need to be a full design. |
| `recurrence_signal` | string | yes | Normalized frequency label. **This implementation uses `recurrence_count` as the quantitative signal and `recurrence_signal` as a human-facing qualitative label** (`daily`/`weekly`/`monthly`/`rare`) — it is descriptive/advisory only and is NOT read by the threshold formula in `friction_cli.py`. The formula reads `recurrence_count` + date span. See `threshold_config.example.yml` for why: a numeric count plus an elapsed-days guard is more falsifiable than a self-reported cadence label. Keep both: the label helps a human skim the rollup table; the count is what the formula computes on. |
| `severity_signal` | string (enum, project-defined) | yes | Values come from the project's `threshold_config.yml` (`severity_values` list), e.g. `critical_path` / `normal` / `low`. The generic tooling does not hardcode this enum — it validates against whatever `threshold_config.yml` declares. |
| `falsifiability_gate` | string | **yes (required)** | What concrete evidence would prove this entry is *wrong* — i.e., that the friction is not real or not recurring. Example: `"if the same query returns near-zero occurrences over the next 30 days"`. Forces every entry to be falsifiable, not just asserted. |
| `golden_rule_answer` | boolean | **yes (required)** | Answers: *"Would this recur next week if nothing changed?"* Must be `true` to log an entry at all — see **Golden-rule intake filter** below. |
| `built_as` | string or `null` | yes (nullable) | Filled in once `status` reaches `BUILT` — name/path of the thing that was built (script, PR title, tool name). |
| `built_pr` | string or `null` | yes (nullable) | Filled in once `status` reaches `BUILT` — PR/MR reference. |
| `post_build_check` | object or `null` | yes (nullable) | `{due_date, procedure, result}`. Generalizes "verify the automation is actually adopted N days later." `result` is `null` until the check is actually performed (then e.g. `"PASS"` / `"FAIL"` / free text). A `BUILT` entry with `post_build_check: null` is a schema smell — `friction_render.py` flags it in the rollup. |

## Status lifecycle

```
CANDIDATE -> QUALIFYING -> BUILD_ELIGIBLE -> BUILT
     \            \              \
      -> DISQUALIFIED (off-ramp, any state before BUILT)
      -> DEFERRED     (off-ramp, any state before BUILT)
```

- Forward transitions happen **one step at a time** (`promote` refuses to skip
  states — e.g. `CANDIDATE -> BUILD_ELIGIBLE` directly is rejected).
- `DISQUALIFIED` and `DEFERRED` are off-ramps reachable from any pre-`BUILT`
  state (the entry turned out to be a one-off, evidence stopped recurring, or
  priority changed). They are terminal for the purposes of the build pipeline
  but the row is kept (never deleted) for audit trail.
- `BUILT` is not a permanent unverified end-state: a `BUILT` entry should carry
  a `post_build_check` with a `due_date`; until `result` is filled in, treat
  the automation as *claimed*, not *confirmed*.

## Two-factor build threshold

An entry becomes `BUILD_ELIGIBLE` only when **both** a recurrence signal and a
severity signal clear a configured bar — never recurrence alone, never
severity alone. The exact numbers are per-project, pluggable via
`threshold_config.yml` (see that file's own docs), but the shape is fixed:

1. `recurrence_count >= min_recurrence_count`
2. `severity_signal` is one of `required_severity_values`
3. `(last_seen_date - created_date in days) >= min_days_between_first_and_last`
   — guards against 3 occurrences in one afternoon counting the same as 3
   occurrences spread over a month.

All three must hold. `friction_cli.py review` computes this and diffs it
against the stored `status`; it never auto-mutates status.

## Golden-rule intake filter (mandatory)

Before an entry can be created, the CLI requires an explicit,
non-defaulted answer to: **"Would this recur next week if nothing changed?"**

- If the honest answer is **false**, the entry must **not** be logged here at
  all — it is one-off forensic/incident work and belongs in incident
  documentation instead. `friction_cli.py log` REFUSES to create an entry
  unless `--golden-rule-yes` is passed explicitly as `true`, and prints a note
  redirecting one-off work elsewhere.
- This is the schema's primary defense against **premature automation
  pressure from a single incident** — the diary is for *recurring* friction
  only.

## Falsifiability gate + verifier/proposer separation (folded in as required)

Two properties from the more rigorous of the two source instances are folded
into the generalized schema as **required**, not optional:

- **`falsifiability_gate`** (field, required) — every entry must state what
  evidence would prove it wrong. An entry that cannot be falsified cannot be
  trusted to self-correct.
- **Verifier/proposer separation** (process rule, enforced by CLI shape, not
  a field) — a session cannot be the sole authority that declares its own
  threshold crossed:
  - `review` only **prints a diff** between the recomputed formula and the
    stored `status`. It never writes to the log.
  - `promote` is a **separate, explicit** command a human/second session runs
    deliberately. The `QUALIFYING -> BUILD_ELIGIBLE` step specifically
    requires a mandatory `--evidence` string — you must write down what proof
    justifies the promotion, not just flip the enum.
  - In practice: one session (or the automated `review` pass) proposes ("the
    numbers say X is build-eligible"); a human, or a distinct second review
    pass, runs `promote --evidence "..."` to actually confirm it. This is the
    generic-tooling encoding of "no self-attestation."

## `domain_extensions` — keeping generic tooling domain-free

`domain_extensions` is the **only** place project-specific taxonomy may live
(e.g. `{"plane": "data-pipeline", "program": "checkout-v2"}`). Every other
field is generic. This is what makes `friction_cli.py` / `friction_render.py`
/ `SCHEMA.md` copy-pasteable into an unrelated project without touching a
line of code — only `threshold_config.yml` and the contents of
`domain_extensions` change per project.
