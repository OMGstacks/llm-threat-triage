---
description: Session-start situational report — one read-only pass over runtime, deploy-surface, and open work ("what is true right now?").
argument-hint: [optional focus area]
---

> Fill in every placeholder token (`<LIKE_THIS>`) before this command is safe to use in
> a new project.

**Purpose.** Answer "what is actually true right now?" at the start of a session, before
any recommendation is made — read-only by construction. This command changes nothing;
it only gathers and reports. Optional focus: $ARGUMENTS

If any individual step errors, note it and continue — never let one failed check block
the whole report.

---

## Step 1 — evidence contract

Before emitting any recommendation, declare one of the three evidence states defined in
`<TOOLKIT_ROOT>/commands/_shared/evidence-contract.md`:
`EVIDENCE_CURRENT` / `EVIDENCE_STALE` / `EVIDENCE_UNAVAILABLE`.

## Step 2 — capability staleness check

Before relying on any introspection tool/capability, check whether it might have been
registered or deployed **after** this session started, making it invisible right now.
If the project has a way to compare "how many capabilities exist" vs "how many this
session can see," use it: `<CAPABILITY_COUNT_CHECK_COMMAND_OR_TOOL>`. If a mismatch is
found, declare `EVIDENCE_UNAVAILABLE` for anything that depends on the missing
capability and suggest starting a fresh session rather than guessing around the gap.

## Step 3 — runtime status

Gather, preferring dedicated read-only introspection tools where the project has them,
falling back to documented manual commands otherwise:

- Health/uptime of the running service(s): `<HEALTH_CHECK_TOOL_OR_ENDPOINT>`
- Running version/build identifier vs. the default branch: `<RUNNING_VERSION_CHECK>`
- Any staleness/freshness signal the project tracks (see the evidence-contract's note
  on frozen-vs-aging signals if this applies): `<FRESHNESS_SIGNAL_SOURCE>`
- Recent errors/events: `<RECENT_EVENTS_LOG_SOURCE>` (widen the time window if errors
  are found near the edge of the default window)
- Cross-session/teammate work-in-progress map, if the project has one:
  `<ACTIVE_WORK_REGISTRY_TOOL>` — otherwise fall back to the concurrency-check steps in
  `<TOOLKIT_ROOT>/commands/_shared/concurrency-check.md`.

If dedicated tools are absent, declare `EVIDENCE_UNAVAILABLE` for that specific gap
rather than silently reporting nothing.

## Step 4 — deploy-surface truth

If the project has more than one independently-deployable runtime identity (e.g. a
host-process component and a separately-rebuilt container/artifact — two things that can
look related but move on different schedules), check each one's actual deployed version
against the default branch, not just against each other:

```
<REMOTE_ACCESS_COMMAND> 'cd <REMOTE_APP_DIR> && git fetch <REMOTE_NAME> <DEFAULT_BRANCH> --quiet && echo HOST=$(git rev-parse --short HEAD) DEFAULT=$(git rev-parse --short <REMOTE_NAME>/<DEFAULT_BRANCH>) && git log --oneline <REMOTE_NAME>/<DEFAULT_BRANCH>..HEAD && echo ARTIFACT=$(<ARTIFACT_VERSION_CHECK_COMMAND>)'
```

Flag: host/environment behind the default branch => a deploy is pending; host AHEAD =>
unpushed commits sitting on that environment (needs the bundle/patch-transfer runbook
before anything else touches it). Two runtime identities differing from each other is
often intentional — confirm against the project's documented deploy-surface facts before
treating a mismatch as a problem.

## Step 5 — open work

- Read the project's persistent cross-session memory (if any) for the current
  arc/state and any explicitly held/gated next step: `<PERSISTENT_MEMORY_PATH>`.
- Search for open incidents or problem-reports: `<OPEN_INCIDENT_SEARCH_COMMAND>`.

## Step 6 — intent drill

Pull additional targeted evidence based on the session's actual focus. Fill in this
table with your project's real sources — it should map "what kind of question is this"
to "which read-only source answers it," so the drill doesn't require re-deriving the
mapping every session:

| Question class | Pull before advising |
|---|---|
| Deploy / runtime change | `<RUNTIME_VERSION_TOOL>` + `<HEALTH_CHECK_TOOL>` + deploy-surface check (Step 4) |
| Incident / problem-report work | `<INCIDENT_STATUS_TOOL>` + `<RECENT_EVENTS_LOG_SOURCE>` |
| Data/pipeline quality | `<FRESHNESS_SIGNAL_SOURCE>` + `<RECENT_EVENTS_LOG_SOURCE>` + `<SCHEDULE_TRUTH_SOURCE>` |
| Scheduler/cron truth | `<SCHEDULE_TRUTH_SOURCE>` + `<RECENT_EVENTS_LOG_SOURCE>` |
| Cross-session coordination | `<ACTIVE_WORK_REGISTRY_TOOL>` (fallback: concurrency-check.md) |
| Code scope/ownership | `<CODEBASE_INDEX_TOOL>` |
| Pure design/doc-only | evidence optional — but `EVIDENCE_STALE`/`EVIDENCE_UNAVAILABLE` disclosure still required if the recommendation references runtime state |

If a focus area was given in `$ARGUMENTS`, drill into the matching row above.

---

## Report — fixed one-screen shape

- Evidence state declaration.
- One line each: service health · running version vs. default branch · freshness/staleness
  (anything stale?) · recent errors.
- Deploy-surface: each runtime identity's version vs. the default branch, and "in sync"
  or "deploy pending / environment ahead."
- Open incidents/problem-reports + the single most relevant "where we left off / next
  gated step" from persistent memory.
- Intent-drill findings, if the drill triggered.
- One-line VERDICT: clear to proceed, or the top blocker to resolve first.

Then stop. Make no changes.

---

## What this replaces / why it exists

This generalizes a session-opening pattern built to stop two recurring failures: acting
on a recommendation built from stale or absent evidence without disclosing that, and
missing a newly-available capability because it was registered mid-session and is
invisible until a fresh session starts. The fixed report shape exists so "what's true
right now" is always answered the same way, instead of being re-derived ad hoc (and
inconsistently) every session.
