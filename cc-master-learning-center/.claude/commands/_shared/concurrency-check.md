# Shared snippet: Concurrency Check ("is someone else already doing this")

> Fill in every placeholder token before this command is safe to use in a new project.
> This is NOT a standalone command — `ship.md`, `migration.md`, `deploy-ops.md`, and
> `session-close.md` reference this file by path instead of restating a bespoke version.

Before starting any track of work that mutates shared state (a branch, a migration, a
deploy, a long-running cleanup), check whether a concurrent session or teammate is
already on the same track. Do this BEFORE creating new branches, worktrees, or claiming
identifiers — not after.

## The three checks, in order

1. **Open reviews by keyword** — search open pull/merge requests for the topic:
   `<CODE_HOST_CLI> <list-open-reviews-command> --search "<keyword>"`
   (e.g. a GitHub-flavored example: `gh pr list --state open --search "<keyword>" --json number,title,headRefName`)
2. **Remote branches by keyword** — search remote branch names for the topic:
   `git ls-remote --heads origin | grep -i "<keyword>"`
3. **Local worktrees on the same topic** — check whether your own environment already
   has an isolated workspace for this:
   `git worktree list`

If any of the three surfaces a hit: **do not open a competing/duplicate track.**
Instead, either:
- Coordinate read-only (review what exists, comment, or wait), or
- If you have clear ownership/authorization to proceed anyway, say so explicitly and
  proceed with awareness of the collision risk, or
- If the existing track is stale/abandoned, confirm that explicitly (e.g. last-updated
  timestamp, an explicit abandonment note) before treating the field as clear.

## When a project has a live registry

If the project has a single-call live registry of "who is working on what right now"
(a dashboard, a tool, a status board), prefer it over the three manual greps above —
it should collapse this three-step manual check into one call. Reference it here:
`<ACTIVE_WORK_REGISTRY_TOOL_OR_DOC>`. Until such a registry exists, the three-step
manual check above is the fallback and should not be skipped.

## Why this exists

A concurrency collision on shared mutable state (two sessions independently branching
the same fix, claiming the same identifier, or editing the same live host surface) is
expensive to unwind after the fact — it can require a force-push history rebuild or a
race between two writers on a production system. A cheap, three-command check up front
is far cheaper than the cleanup. This check is mechanical and should never be skipped
"because it's probably fine."
