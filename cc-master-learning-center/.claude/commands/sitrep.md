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
`.claude/commands/_shared/evidence-contract.md`:
`EVIDENCE_CURRENT` / `EVIDENCE_STALE` / `EVIDENCE_UNAVAILABLE`.

## Step 2 — capability staleness check

Before relying on any introspection tool/capability, check whether it might have been
registered or deployed **after** this session started, making it invisible right now.
If the project has a way to compare "how many capabilities exist" vs "how many this
session can see," use it: `not applicable — no such tool exists for this project; use the documented fallback above`. If a mismatch is
found, declare `EVIDENCE_UNAVAILABLE` for anything that depends on the missing
capability and suggest starting a fresh session rather than guessing around the gap.

## Step 3 — runtime status

Gather, preferring dedicated read-only introspection tools where the project has them,
falling back to documented manual commands otherwise:

- Health/uptime of the running service(s): `not applicable — no such tool exists for this project; use the documented fallback above`
- Running version/build identifier vs. the default branch: `not applicable — no such tool exists for this project; use the documented fallback above`
- Any staleness/freshness signal the project tracks (see the evidence-contract's note
  on frozen-vs-aging signals if this applies): `not applicable — no data-freshness ledger/pipeline in this project`
- Recent errors/events: `gh run list --limit 20 (recent CI activity is the closest equivalent)` (widen the time window if errors
  are found near the edge of the default window)
- Cross-session/teammate work-in-progress map, if the project has one:
  `python3 .cognition/active-work/claims_cli.py status` (live for this project) —
  otherwise fall back to the concurrency-check steps in
  `.claude/commands/_shared/concurrency-check.md`.

If dedicated tools are absent, declare `EVIDENCE_UNAVAILABLE` for that specific gap
rather than silently reporting nothing.

## Step 4 — deploy-surface truth

If the project has more than one independently-deployable runtime identity (e.g. a
host-process component and a separately-rebuilt container/artifact — two things that can
look related but move on different schedules), check each one's actual deployed version
against the default branch, not just against each other:

```
not applicable — no remote host to reach; this project has no deploy target
```

Flag: host/environment behind the default branch => a deploy is pending; host AHEAD =>
unpushed commits sitting on that environment (needs the bundle/patch-transfer runbook
before anything else touches it). Two runtime identities differing from each other is
often intentional — confirm against the project's documented deploy-surface facts before
treating a mismatch as a problem.

## Step 5 — open work

- Read the project's persistent cross-session memory (if any) for the current
  arc/state and any explicitly held/gated next step: `.cognition/memory/MEMORY.md`.
- Search for open incidents or problem-reports: `gh issue list --state open --search "<keyword>"`.

## Step 6 — intent drill

Pull additional targeted evidence based on the session's actual focus. Fill in this
table with your project's real sources — it should map "what kind of question is this"
to "which read-only source answers it," so the drill doesn't require re-deriving the
mapping every session:

| Question class | Pull before advising |
|---|---|
| Deploy / runtime change | `not applicable — no such tool exists for this project; use the documented fallback above` + `not applicable — no such tool exists for this project` + deploy-surface check (Step 4) |
| Incident / problem-report work | `not applicable — no incident-tracking system; use gh issue list` + `gh run list --limit 20 (recent CI activity is the closest equivalent)` |
| Data/pipeline quality | `not applicable — no data-freshness ledger/pipeline in this project` + `gh run list --limit 20 (recent CI activity is the closest equivalent)` + `not applicable — no scheduler/cron in this project` |
| Scheduler/cron truth | `not applicable — no scheduler/cron in this project` + `gh run list --limit 20 (recent CI activity is the closest equivalent)` |
| Cross-session coordination | `python3 .cognition/active-work/claims_cli.py status` (live for this project; fallback: concurrency-check.md) |
| Code scope/ownership | `python3 .cognition/codebase-index/cli.py --list (this project's own installed instance)` |
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
