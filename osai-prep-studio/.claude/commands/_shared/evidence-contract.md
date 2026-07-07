# Shared snippet: Evidence Contract

> Fill in every placeholder token before this command is safe to use in a new project.
> This is NOT a standalone command — other commands reference it by path instead of
> restating the enum. If you need to change the contract, change it here once.

Any command that produces a recommendation touching runtime, deploy, or production state
must first declare exactly one of these three evidence states. This is the single
authoritative definition — do not copy/paste this enum into another command file.

## The enum

- **`EVIDENCE_CURRENT`** — the relevant evidence source(s) were queried in this same
  response/session, and are recent enough to support the decision at hand. Proceed normally.
- **`EVIDENCE_STALE`** — evidence exists but either predates a recent change (deploy,
  migration, config edit) or was pulled earlier in a longer session and may no longer
  reflect current state. Disclose the staleness explicitly. Do not recommend
  high-mutation actions (deploy, apply, incident-close, production write) from stale
  evidence alone — re-pull first, or get explicit human sign-off to proceed anyway.
- **`EVIDENCE_UNAVAILABLE`** — the tools/sources needed are absent, unreachable, or the
  session predates a capability being registered (see the tool-staleness check below).
  Disclose why. Proceed only for pure design/documentation work that makes no runtime
  claim; do not silently substitute a guess for a missing evidence pull.

## Tool/capability staleness check

Before trusting a "no evidence available" conclusion, check whether the missing
capability was registered/deployed **after** this session started — if so, it is
invisible to the current session, not actually absent. A capability registered mid-session
requires a **fresh session** to become visible. If a project has a way to compare
"how many capabilities does the source know about" vs "how many does this session see,"
use it here: `not applicable — no such tool exists for this project; use the documented fallback above`.

## Which recommendation types require which evidence tier

| Recommendation type | Minimum evidence tier required |
|---|---|
| Read-only status report / situational summary | `EVIDENCE_CURRENT` preferred; `EVIDENCE_STALE` acceptable if disclosed |
| Doc/design-only change, no runtime claim | `EVIDENCE_UNAVAILABLE` acceptable, but say so |
| Merge a reviewed, green-CI change | `EVIDENCE_CURRENT` on CI/review status specifically |
| Deploy / release / rebuild | `EVIDENCE_CURRENT` on divergence-from-default-branch check |
| Schema/state migration apply | `EVIDENCE_CURRENT` on prior-apply state + lock/contention check |
| Data-mutation / backfill / correction | `EVIDENCE_CURRENT`, plus the project's mutation-authorization convention (see `deploy-ops.md`) |
| Incident close-out | `EVIDENCE_CURRENT` on the specific signal that defines "resolved" |

## Forbidden pattern

Never let a stale or frozen "looks fine" signal silently override a fresher, worse signal
computed a different way (e.g. a heartbeat/liveness flag that never ages vs. a computed
lag/staleness metric that does age). If a project has two sources of truth for the same
question, the one that mechanically ages with time is the decision source; the one that
is a static/write-instant flag is diagnostic-only. Name both sources explicitly in
`PROJECT_FACTS.yml` if this pattern applies to your project.
