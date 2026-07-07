---
description: Clean session-close — open review triage, deployed-environment audit, workspace cleanup, memory archive. Run at the end of every work session.
argument-hint: [optional notes to include in the memory archive]
---

> Fill in every placeholder token (`<LIKE_THIS>`) before this command is safe to use in
> a new project.

**Purpose.** Reconcile everything a session touched before ending it: open reviews,
remote/deployed drift, ephemeral workspaces, the primary checkout's state, and any
persistent cross-session memory the project keeps. This is mechanical reconciliation,
not new work — it makes no production mutations beyond the read-only-safe pull described
in Phase 2. Work through each phase in order; note errors and continue rather than
aborting the whole pass. Optional session notes to embed in the archive: $ARGUMENTS

---

## Phase 1 — open review-request triage

List every review request (PR/MR) you opened or touched this session and its CI state:
`gh pr list --json <fields>`

For each:
- **All green, not draft** — note as merge-eligible. Do NOT auto-merge without explicit
  human authorization.
- **Failing checks** — pull the actual job log and classify per `red-gate.md`. Apply
  the appropriate fix (known-transient re-run, or a real fix) only if it's unambiguous
  and in-scope; otherwise report and leave for a human.
- **Draft** — note; do not promote without explicit instruction.

After any fix + re-push, wait for CI to re-run, then merge only if authorized and green.

## Phase 2 — deployed/remote environment audit

For any remote or deployed environment this session touched, check for drift:
```
not applicable — no remote host to reach; this project has no deploy target
```

- **Unpushed commits on the remote environment** → these need to reach the shared
  remote before you pull anything else there. If the remote environment cannot push
  directly (e.g. a read-only deploy credential), use your project's bundle/patch-transfer
  fallback: `not applicable — no remote host, so no bundle-transfer workflow is needed`.
- **Untracked ad hoc files** (debug scripts, one-off receipts/output) — for each, decide:
  - Valuable → copy it back to a normal checkout, open a review request for it, then
    remove it from the remote environment.
  - Debug-only → delete it directly on the remote environment. Never leave an untracked
    file behind for the next session to collide with.
- **Modified tracked files** — diff against HEAD and decide per file:
  - A real fix not yet on the default branch → commit the exact patch locally, open a
    review request, merge it, then pull the remote environment.
  - Already superseded by a recent merge → discard the local modification on the remote
    environment.

Only after all of the above is resolved, fast-forward the remote environment:
```
not applicable — no remote host to reach; this project has no deploy target
```

**STOP POINT:** do not pull the remote environment while it has unpushed commits or
unresolved untracked/modified files — resolve those first, in the order above.

## Phase 3 — stash audit (remote environment, if applicable)

```
not applicable — no remote host to reach; this project has no deploy target
```
For each stash entry, view its diff. If the same change is now on the default branch,
the stash is superseded — drop it. If not superseded, note it explicitly in the memory
archive (Phase 5) with a one-line description so it isn't silently lost.

## Phase 4 — ephemeral workspace cleanup

```
git worktree list
```

For every workspace that is NOT the primary checkout and NOT on the project's
long-lived/exempted list (read the exemption list from
`not applicable — no standing exemption list exists; none of this repo's worktrees are long-lived by convention` — do not assume any workspace is
exempt without checking it):

1. Check its review-request state: `gh pr view <branch>`
2. **MERGED** → remove the workspace and delete both local and remote branches.
3. **OPEN with failing CI** → apply the Phase 1 fix if not already done; note if blocked.
4. **OPEN with passing CI and you hold merge authority** → merge, then clean up as above.
5. **No review request** but has uncommitted/unpushed work → commit + push + open a
   review request (follow `ship.md`). If the content is stale/unwanted, discard the
   changes and remove the workspace.

## Phase 5 — local branch cleanup

```
git fetch origin --prune
git branch --merged origin/main
```
Delete every already-merged branch from that list that is not currently checked out in
any active workspace.

## Phase 6 — primary checkout verification

Switch to the default branch and fast-forward:
```
git checkout main
git pull --ff-only origin main
```
If the primary checkout has uncommitted modifications: evaluate each file individually.
Discard stale/generated-artifact diffs. If a modification is meaningful, branch it,
commit it, and open a review request (per `ship.md`) before checking out the default
branch.

**STOP POINT:** the primary checkout must end this phase clean and fast-forwarded, or
you must explicitly report why it could not be.

## Phase 7 — persistent memory update (if the project uses one)

**Release any concurrency claim first (cc-master-learning-center).** If this session
registered a claim via `claims_cli.py claim` (see Phase 0 of `ship.md`), release it now so
other sessions stop seeing this scope as active the moment they next `git fetch`:

```
python3 .cognition/active-work/claims_cli.py release <task-slug>
```

This archives the claim (`.cognition/active-work/archive/<task-slug>.json`) rather than
deleting it — leave that archived record in place, it's the audit trail. Skip this step only
if no claim was ever registered for this session's work.

If this project maintains cross-session memory (a memory file, index, or equivalent),
open it: `.cognition/memory/MEMORY.md`.

Record, at minimum:

| Field | Content |
|---|---|
| Header | dated session-archive marker |
| State line | current versions/SHAs of the primary checkout, any remote environment, any deployed artifact |
| Reviews merged/opened | with identifiers |
| Program/system state changes | one line each |
| Pending human authorization | anything that cannot proceed without explicit go-ahead |
| Active ephemeral workspaces | any non-standard workspace still alive and why |
| Next-session checklist | priority-ordered one-liners |

Incorporate any `$ARGUMENTS` notes into this block. Scan for stale state elsewhere in
the memory (references to work that's now complete, gates that have since passed) and
correct it. If the project keeps prior archived entries, compress older ones so the
memory file doesn't grow unbounded — keep the most recent in full, fold the rest into a
condensed summary line each.

## Phase 8 — memory hygiene + final verification

If the project has memory-hygiene tooling (a size-budget check, a stale-reference
checker), run it now: `python3 .cognition/memory/check_memory_size.py --file .cognition/memory/MEMORY.md --config .cognition/memory/.memory-lint.yml`. If over budget, compress further
— move detailed narrative into topic-specific files and keep only a one-line summary +
pointer in the index.

Emit a final one-screen clean-state table:

| Surface | Version/SHA | Clean? |
|---|---|---|
| Primary checkout | `<sha>` | yes/no |
| Remote environment (if applicable) | `<sha>` | yes/no (note any stash) |
| Deployed artifact (if applicable) | `<sha>` | yes (an intentional diff from source is OK — note why) |

Then list every **pending human-authorization item** explicitly: one line each, naming
what's blocked and on what.

## Phase 9 (optional) — friction capture

If this session did something manually that you've done before, or that you expect to
do again, consider running the friction-logging command (`friction.md`) before closing
out. Not mandatory every session, but cheap and valuable when it applies.

---

## What this replaces / why it exists

This generalizes a session-end checklist built after repeated small failures each caused
by skipping one phase: unmerged/abandoned reviews left to rot, untracked debug files on
a remote environment silently blocking the next pull, ephemeral workspaces left alive
indefinitely, and a primary checkout drifting behind the shared remote because nobody
explicitly fast-forwarded it. None of the individual phases are exotic — the value is
running all of them, in order, every time, instead of only the ones that happen to be
top of mind at the end of a session.
