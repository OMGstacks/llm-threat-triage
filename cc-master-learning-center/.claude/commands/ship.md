---
description: Ship a scoped change through single-writer PR discipline — isolated workspace off the fresh default branch, scope-gate, tests, push, open a review request. Never self-approve or self-merge without explicit authorization.
argument-hint: <what to change / change intent>
---

> Fill in every placeholder token (`<LIKE_THIS>`) before this command is safe to use in
> a new project.

**Purpose.** Ship one tightly-scoped change as a reviewable unit, without ever mutating
the shared/primary workspace directly and without ever merging your own unreviewed work.
The discipline exists because concurrent writers on the same working tree, or diffs that
silently drift outside their declared scope, are cheap to prevent up front and expensive
to unwind after the fact.

Change intent: $ARGUMENTS

---

## Phase 0 — concurrency check

Before creating anything, run the shared check: see
`<TOOLKIT_ROOT>/commands/_shared/concurrency-check.md`. Is another session/teammate
already shipping this same change? If so, coordinate instead of duplicating.

**Automated registry check (cc-master-learning-center; run after the fresh fetch, before
touching anything).** The manual grep above only catches what's already visible in PR/branch
names. Also check and register against the live claims registry
(`.cognition/active-work/`, see its `README.md`):

```
python3 .cognition/active-work/claims_cli.py status
```

If this shows an unexpired claim whose `files_scope` overlaps the files this task will touch,
STOP and coordinate with that claim's owner instead of proceeding. Otherwise, claim this
task's scope before starting work so a concurrent session sees it on their next `git fetch`:

```
python3 .cognition/active-work/claims_cli.py claim <task-slug> --owner <you> \
  --scope <path> [<path> ...] --branch <descriptive-branch-name>
```

A nonzero exit from `claim` means it detected an overlap with another active claim even if
`status` looked clear a moment earlier (a race) — treat that the same as a manual-grep hit:
stop and coordinate.

## Phase 1 — isolate the workspace

Never write directly in the primary/shared checkout if concurrent writers are possible.

1. Inspect the primary checkout's current state (branch, divergence) without touching it:
   `git -C <PRIMARY_CHECKOUT_PATH> worktree list`
2. Fetch the default branch fresh (not local disk, which may be stale):
   `git -C <PRIMARY_CHECKOUT_PATH> fetch <REMOTE_NAME> <DEFAULT_BRANCH> --quiet`
3. Create an ISOLATED workspace (a worktree, a separate clone, or your project's
   equivalent) branched off that fresh fetch — not off local HEAD:
   `git -C <PRIMARY_CHECKOUT_PATH> worktree add -b <descriptive-branch-name> <ISOLATED_WORKSPACE_PATH> <REMOTE_NAME>/<DEFAULT_BRANCH>`

Do ALL edits in the isolated workspace via absolute paths. Do not edit the primary
checkout for this task.

**STOP POINT:** do not write a single line of the change until the isolated workspace
exists and is confirmed to be based on the fresh default branch, not stale local state.

## Phase 2 — build

Make the change in the isolated workspace. Keep it scoped to ONE task — resist folding
in unrelated cleanups; flag those separately (see the friction/gap-hunt tooling if this
toolkit has one installed) rather than bundling them into this diff.

## Phase 3 — the scope gate (mandatory before any commit)

All of the following must hold. This is a hard gate, not a suggestion:

1. **Scope.** `git -C <ISOLATED_WORKSPACE_PATH> status --porcelain` and
   `git -C <ISOLATED_WORKSPACE_PATH> diff --name-only` must contain ONLY files this task
   owns. A foreign path or stray file FAILS the gate — go back and unstage/revert it.
   This check exists because a diff that silently touches files outside its declared
   ownership is exactly the failure mode that turns a small change into a
   cross-contamination incident.
2. **Tests/linters.** Run the relevant test suite and any project-defined gate the
   change touches: `<TEST_COMMAND>`, `<LINT_COMMAND>`, or the project's fast local CI
   equivalent: `<LOCAL_CI_FALLBACK_COMMAND>`.
3. **Secrets.** No credential, token, connection string, or `.env`-style secret appears
   anywhere in the diff.

**STOP POINT:** do not commit until all three gate conditions pass. A scope failure is
not something to "fix up later in review" — fix it before the commit exists.

## Phase 4 — commit and open a review request

4. Stage SPECIFIC files by name. **Never** use a blanket add-everything command — that
   is how out-of-scope files sneak into a commit. Commit with a concise, why-focused
   message (plus any project-required co-author/attribution trailer).
   Push to the remote: `git push -u <REMOTE_NAME> <descriptive-branch-name>`.
5. Open a review request (pull/merge request) with a summary and a test plan:
   `<CODE_HOST_CLI> <open-review-command>`.
   **Do NOT self-approve. Do NOT self-merge.** Report the review URL and CI status, then
   STOP.

**STOP POINT:** merging is a separate, later, explicitly-authorized step. Do not proceed
past opening the review request in the same invocation unless a human has explicitly
authorized an immediate merge.

## Phase 5 — merge (only on separate, explicit authorization)

Only perform this phase when explicitly told to merge — never as a default continuation
of Phase 4.

7. **Re-verify scope, not just the first time:** `<CODE_HOST_CLI> <diff-review-command> --name-only`
   must still show only this task's files (a review can drift via force-pushes or
   additional commits). Confirm CI is green and the review is actually approved/mergeable
   (`<CODE_HOST_CLI> <check-status-command>`), not just "not failing yet."
8. Merge: `<CODE_HOST_CLI> <merge-command>`. If your project's merge tool cannot also
   delete the remote branch when the primary checkout holds the default branch, do the
   cleanup explicitly and separately:
   ```
   git -C <PRIMARY_CHECKOUT_PATH> worktree remove --force <ISOLATED_WORKSPACE_PATH>
   git -C <PRIMARY_CHECKOUT_PATH> branch -D <descriptive-branch-name>
   git push <REMOTE_NAME> --delete <descriptive-branch-name>
   ```
   Confirm the merge commit landed on the remote default branch. Update any persistent
   cross-session memory the project keeps if this change shifts program/system state.

---

## What this replaces / why it exists

This generalizes a "single-writer discipline" pattern that emerged after a concurrency
incident: two agents/sessions editing the same shared working tree simultaneously
cross-contaminated an unrelated branch, requiring a history rebuild to recover. The
scope gate generalizes a related near-miss where a diff silently included files outside
its task's ownership. The never-self-merge rule generalizes the plain fact that review
is only meaningful if the author isn't also the sole approver. None of these are
project-specific — they hold for any team or agent operating on a shared version-control
remote with more than one writer.
