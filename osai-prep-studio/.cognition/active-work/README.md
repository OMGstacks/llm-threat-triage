# Concurrency Claims Registry

A live, git-native "who's working on what" signal — the piece
`.claude/commands/_shared/concurrency-check.md` names but doesn't provide:
that doc's own words are "[a live registry] would be strictly better... but
none exists yet." This is that registry.

## Why this exists

`_shared/concurrency-check.md`'s existing protocol is a manual, three-step
grep: search open PRs, search remote branch names, check worktrees. It works,
but only if every session remembers to run it, correctly, before starting
work — and it produces no artifact a *later* session can check against. This
registry is ported from the pattern first proven on this repo's
`cc-master-learning-center` project, which already hit the failure mode this
is meant to prevent: two toolkit install commits landed mid-session from a
different actor while another session was actively committing PR work on
the same branch. Nothing broke that time only because it was caught by hand
on every rebase — exactly the kind of luck a live registry shouldn't be
required for.

## How it works

Each active task gets one committed JSON file under this directory:

```json
{
  "task_slug": "slice-4-claims-registry",
  "owner": "alice",
  "session_id": "...",
  "task_description": "one-line summary",
  "branch": "claude/cognition-substrate-slice5",
  "files_scope": ["osai-prep-studio/.cognition/active-work/"],
  "claimed_at": "2026-07-07T18:32:00+00:00",
  "expires_at": "2026-07-08T18:32:00+00:00"
}
```

Because the file is committed (not gitignored — unlike learner-state, this
*must* be shared across checkouts), any session that runs `git fetch` sees
every other active claim without needing write access to a shared service.
No lock server, no daemon — the medium is git itself, the same one
`concurrency-check.md`'s manual protocol already uses.

## CLI

```sh
# Claim a task's file scope before starting work. Reports (but does not
# block) any overlap with other currently-active claims, and exits 1 if
# an overlap was found so a calling script/CI step can fail loudly.
python3 claims_cli.py claim <task-slug> --owner <name> \
  --scope <path> [<path> ...] --branch <branch> [--ttl-hours 24]

# List every active (unexpired) claim and every overlapping pair --
# the actual clobber-prevention check.
python3 claims_cli.py status

# Archive a claim when the task is done (moves it to archive/, never a
# silent delete).
python3 claims_cli.py release <task-slug>
```

Run `python3 tests/test_claims_cli_self.py` for the self-test (subprocess,
temp directory, never touches real claim files).

## Known limitation

The registry is only as fresh as the last `git fetch` — a claim made and
pushed by another session is invisible until you fetch. This is the same
staleness window the manual grep protocol already had; the improvement here
is that the check is now a single machine-runnable command instead of a
three-step manual routine easy to skip under time pressure.
