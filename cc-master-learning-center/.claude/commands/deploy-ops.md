---
description: Deployed-environment operations safety rail — load canonical facts once, then dispatch to the right pre-check for the operation type before any mutation.
argument-hint: <operation: deploy | query | data-mutation | health-probe>
---

> **NOT APPLICABLE to this project (confirmed 2026-07-07).** CC Master Learning Center
> is a content-authoring/validation system with a JSON fact store — no deployed
> service, no host to SSH into, no runtime identity to check (see `PROJECT_FACTS.yml`).
> Do not invoke this command for this project; the placeholders below were never
> filled in because there is no deploy surface to fill them with. If this project ever
> gains one, fill in every `<LIKE_THIS>` token first.

**Purpose.** Front-load the canonical facts about a project's deployed/remote
environment once per session, instead of re-deriving them from scratch or guessing.
Then route the requested operation to the correct pre-check before any mutation
happens. Operation: $ARGUMENTS

---

## Canonical facts (fill in once per project — do not re-derive per session)

Read these from the project's facts file rather than restating them ad hoc:
`<PROJECT_FACTS_FILE_PATH>`. At minimum it should define:

- **Access convention.** How to reach the deployed/remote environment (e.g. an SSH
  target, a cloud console, a CLI context) and which credential/user identity to use.
  `<DEPLOY_HOST_ACCESS_COMMAND>`. If the project has retired a legacy access identity
  (e.g. an old admin/root account that no longer works), name that explicitly here so
  it never gets reused out of an old doc.
- **App/working directory on the remote environment.** `not-applicable`.
- **Routing between components,** if more than one process/container/service exists on
  the same host and only one of them is the "real" one for a given kind of operation
  (e.g. "use component A for direct queries, component B for scripts; a third,
  legacy surface is stale and must never be used"). `<COMPONENT_ROUTING_TABLE>`.
- **Secret storage locations.** Never put a secret value in chat, logs, or a committed
  file — always reference where it lives: `<SECRET_STORAGE_LOCATIONS>`.

## Invariant: two runtime identities can look the same but deploy independently

If this project has more than one independently-deployable runtime identity sharing the
same host or codebase (e.g. a lightweight host-level process that deploys via a simple
pull, versus a containerized/build-artifact process that deploys via a full rebuild),
name both here and be explicit about which deploy action affects which:
`<RUNTIME_IDENTITY_MAP>`. A mismatch between their reported versions is often
**intentional**, not a bug — confirm against this map before treating a version
mismatch as a problem. Conversely, never rebuild the heavier artifact (e.g. restarting
a live scheduler or service) just to ship a change that only touches the lighter
identity — check the map first.

## Concurrency check

For any deploy, migration, or otherwise state-changing operation, run the shared check
first: see `.claude/commands/_shared/concurrency-check.md`. If another
session/teammate already owns this track, stay read-only unless you have explicit
ownership.

---

## Dispatch by operation type

### `query` (read-only lookup against a live/production data store)

Low risk — proceed directly via the documented routing:
`<READ_ONLY_QUERY_COMMAND_TEMPLATE>`.
If the operation instead requires running a script (not a single query) against the
live data store, and the remote execution environment does not inherit the same
environment variables the main service process uses, reconstruct any needed connection
details from their documented secret-storage location rather than guessing at defaults —
see `<CONNECTION_RECONSTRUCTION_RUNBOOK>` if the project has one. Read-only by default;
treat any write as a `data-mutation` operation instead (see below).

### `deploy` (shipping a build/artifact to the remote environment)

**Refuse to build/deploy if the source checkout that will be deployed does not exactly
match the remote default branch** (neither ahead nor behind) — check divergence first:
`<DIVERGENCE_CHECK_COMMAND>`. If diverged, resolve it (fetch/pull, or push pending
commits per the project's transfer runbook) before deploying; do not deploy a diverged
state and call it done.

- Lightweight/host-level identity → the simple pull/refresh path only; do NOT trigger a
  full rebuild for this. `<HOST_LEVEL_DEPLOY_COMMAND>`.
- Heavier/build-artifact identity → the full build+recreate path, itself divergence-
  gated, with an explicit emergency-only override flag if the project has one:
  `<ARTIFACT_BUILD_DEPLOY_COMMAND>` (emergency override: `<EMERGENCY_OVERRIDE_FLAG>` —
  use only when a human has explicitly authorized bypassing the divergence guard).
- Schema/state change → do not deploy it here; use `migration.md` instead.

**STOP POINT:** do not deploy anything while the source is diverged from the remote
default branch, except via the explicit emergency override with human authorization.

### `data-mutation` (a one-off correction, backfill, or any write against live data)

This requires your project's ops-lease / mutation-authorization convention before
proceeding — do not perform a live data mutation on the strength of this command alone.
See `<OPS_LEASE_OR_MUTATION_AUTHORIZATION_RUNBOOK>` (referenced from the project's core
operating rules) for: checking who else might be mutating the same surface, capturing a
pre-mutation snapshot/hash, declaring an explicit lease/lock, re-verifying nothing
changed immediately before the mutation executes, and releasing the lease afterward.

If this project also has a large-scope-backfill threshold (e.g. "any backfill over N
days/rows needs its own preflight"), name it here: `<LARGE_MUTATION_PREFLIGHT_THRESHOLD>`.

### `health-probe` (checking whether a service/process is actually healthy)

Read-only, safe by default: `<HEALTH_PROBE_COMMAND>`. Interpret the result against the
project's documented healthy/unhealthy signatures rather than assuming "no response" and
"slow response" mean the same thing — they usually indicate different root causes
(e.g. a hard failure vs. a slow dependency). If the probe result doesn't match a known
pattern, do not guess at a root cause — say so explicitly and stop.

---

## Other standing invariants

- **Never put a secret in chat, logs, or a committed file.** Always reference its
  storage location instead of echoing its value.
- **Deploying a script that itself contains embedded query text with quoting that would
  break a heredoc** → write the file locally and transfer it as a file (e.g. via a
  secure copy), never assemble it via an inline heredoc that could mangle embedded
  quotes. Verify the transfer with a checksum comparison on both sides.
- **If the remote environment's write access is read-only** (e.g. a deploy credential
  that can pull but not push), any commits made directly on that environment need a
  patch-transfer path back to the shared remote — see the project's bundle/patch-
  transfer runbook: `<COMMIT_TRANSFER_RUNBOOK>`. Never attempt a direct push from a
  known-read-only credential and treat the failure as a mystery.

State the exact command(s) you will run and confirm the relevant facts BEFORE mutating
anything.

---

## What this replaces / why it exists

This generalizes an operations safety rail built after two recurring problems: canonical
facts (host, routing, secret locations) being re-derived or guessed at fresh each
session instead of read from one place, and a rebuild/restart of a heavier runtime
identity being triggered for a change that only needed the lighter identity's simple
deploy path — an unnecessary blast-radius expansion. The divergence-gate-before-deploy
rule generalizes the plain fact that deploying a source state that doesn't match what
was reviewed is not the same operation as deploying what was reviewed, even if the
files look similar.
