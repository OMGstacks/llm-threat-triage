---
description: Schema/state-change preflight + gated apply — collision-free identifier, no dry-run-wrapper trap, separated author/validate from apply, hot-table lock discipline.
argument-hint: <migration topic>
---

> **NOT APPLICABLE to this project (confirmed 2026-07-07).** The LLM-threat-triage
> portfolio project has one schema file
> (`projects/llm-log-triage/sql/schema.sql`), applied fresh on every run by
> `python -m src.cli run` — not a versioned migration chain with incremental
> apply-in-order semantics. There is no `migrations/` directory, no prefix-collision
> risk, and no live production database to gate an apply against. Do not invoke this
> command for this project; the placeholders below were never filled in because there
> is no migration surface to fill them with. If this project ever adopts versioned
> migrations, fill in every `<LIKE_THIS>` token first.

**Purpose.** Any migration or schema/state-change file goes through this discipline
before it is written, and again before it is applied to a live/production system. The
two are separate gates with separate authorization requirements — writing a migration
file is safe; applying it to a shared live system is not, and must never be conflated
with "just running it to see." Topic: $ARGUMENTS

---

## Step 0 — concurrency check

Before reserving an identifier or writing anything, run the shared check: see
`.claude/commands/_shared/concurrency-check.md`. Is another session already
authoring a migration or holding a claim on the next identifier (e.g. a
branch/topic name suggesting an in-flight migration)? If so, coordinate — do not open a
competing migration that will collide.

---

## Phase A — before writing

1. **Reserve a collision-free identifier against the REMOTE default branch, not local
   disk.** Local disk may be stale relative to what other sessions/teammates have
   already merged. Use a project-provided identifier-reservation tool if one exists:
   `<NEXT_MIGRATION_IDENTIFIER_TOOL>`. If none exists, derive it from
   `origin/main` directly (e.g. list existing migration
   identifiers there and take max+1), not from your local checkout's file listing.
2. **No self-recording of apply-state inside the migration file itself**, if your
   project's apply tooling records migration state automatically (a ledger/tracking
   table it writes to at apply time). Duplicating that write inside the migration file
   itself creates a drift/contract violation between the two. Confirm your project's
   convention: `<MIGRATION_APPLY_TOOL_STATE_RECORDING_BEHAVIOR>`.
3. **Idempotent by construction** — use your schema system's "create or replace" /
   "if exists" / guarded-creation constructs so a re-apply (e.g. after a partial
   failure) is safe rather than destructive.
4. **Non-blocking index/schema operations, applied at the correct transaction scope.**
   Some schema systems forbid certain operations (e.g. concurrent index builds) inside
   a transaction block — know your system's constraint here and apply such operations
   at top level, outside a wrapping transaction, per your tool's documented invocation:
   `<NON_TRANSACTIONAL_DDL_INVOCATION>`.
5. Confirm the file's own header/identifier matches the reserved prefix, and that any
   migration it references as a dependency actually exists, per your project's
   migration-reference linter if one exists: `<MIGRATION_REFERENCE_LINT_COMMAND>`.

**Known trap — never "dry run" by wrapping the migration in a transaction you intend to
roll back.** If the migration file itself contains a commit (explicit or implicit, e.g.
via a DDL statement that auto-commits in your schema system), a wrapping
begin/rollback becomes a no-op — the rollback does not undo what already committed
inside. This is not a theoretical risk: this exact pattern has caused an accidental
destructive execution in production in at least one real incident this rule is modeled
on. **Validate a migration by reading it and running your linters/tests, never by
wrapping it in a transaction and hoping the rollback holds.**

## Phase B — validate

Run your project's reference linter, identifier-uniqueness check, and fast local
verification suite: `<MIGRATION_REFERENCE_LINT_COMMAND>` + `<IDENTIFIER_UNIQUENESS_CHECK>`
+ `not applicable — no local-CI mirror script exists; CI IS the check`.

**STOP POINT:** do not proceed to Phase C until Phase B is fully green. A migration that
hasn't passed its own linters has no business being scheduled for a live apply.

## Phase C — apply gate (production/live change — only when explicitly authorized)

This phase never runs as an automatic continuation of Phase A/B. It requires an
explicit, separate human go-ahead.

1. Confirm the target environment's checkout is exactly at the default branch (no
   divergence either direction) and has a clean working tree — use your project's
   divergence-gated pull convention: `<DIVERGENCE_GATED_PULL_COMMAND>`.
2. **Hot/live-table discipline.** If the migration touches a table that is written to
   continuously by a live process (a streamer, a scheduler, a hot API path), a schema
   change takes an exclusive-style lock that can queue behind in-flight writers and then
   block everything behind it. Always set a short lock timeout so the DDL fails fast
   instead of piling up:
   ```
   SET lock_timeout = '<SHORT_LOCK_TIMEOUT e.g. 2s>';
   SET statement_timeout = '<SHORT_STATEMENT_TIMEOUT e.g. 30s>';
   -- then the schema-change statement
   ```
   Preflight for existing lock contention before applying:
   `<LOCK_CONTENTION_PREFLIGHT_QUERY>`. If the lock_timeout aborts, do not blind-retry
   into the same contention — diagnose what's actually holding the lock, and do not
   assume it's your own migration if another concurrent change-track is active.
3. Apply through the project's designated apply path (the correct database/service
   endpoint, not a stale or side-channel one): `<APPLY_COMMAND>`, piping the migration
   content from a known-good file rather than an inline heredoc if the migration
   contains characters your shell would mangle (e.g. embedded quotes).
4. **Verify, don't assume.** Check the exact expected post-condition: the resulting
   schema/contract matches exactly (columns, order, types), any negative assertion the
   change implies (e.g. a redaction should now show zero rows of the old shape), that
   the consuming role/credential can actually read/write what it needs to, and that the
   apply-tracking ledger (if your project has one) now shows this identifier as applied.
5. **Write an apply receipt before claiming success.** At minimum: `reason` (why this
   migration, why now) · `evidence` (the verification results from step 4) ·
   `rollback plan` (how to undo, and whether it's been tested) · `verification`
   (the exact check(s) proving it worked). No "done" claim is valid without this receipt.

Ship the migration file itself through `ship.md` as a normal reviewed change — writing
and reviewing the file is a separate act from applying it, and Phase C above is a
distinct, separately-gated step that happens only after the file has merged (or, if your
project's convention allows, is explicitly staged for apply).

---

## What this replaces / why it exists

This generalizes a migration discipline built around two real failure modes: (1) two
independent work-tracks choosing the same identifier because both derived it from their
own stale local state instead of the shared remote, discovered only after a collision at
review time, and (2) an accidental destructive execution caused by wrapping a migration
in a begin/rollback "dry run" that didn't actually roll back because the file's own
statement had already committed. The hot-table lock-timeout rule generalizes an incident
where a schema change queued behind live writers and stalled a production write path
until the apply was aborted.
