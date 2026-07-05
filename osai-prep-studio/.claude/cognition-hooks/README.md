# Cognition OS Toolkit — Hooks

Portable Claude Code lifecycle hooks extracted and generalized from the
Sauron repo's `~/.claude/hooks/` scripts. Every hook here is domain-agnostic:
no Sauron paths, no Sauron tool names, no trading vocabulary. Behavior is
opt-in per project via small JSON config files under
`.claude/hooks-config/`. **A project with no config files sees zero
behavior change from any of these hooks** — each one no-ops cleanly.

All scripts are POSIX-compatible bash, executable (`chmod +x`), and use
`set +e` (fail-open) so a hook error never blocks a session or tool call.
The two exceptions to "never blocks" are `preferred-tool-gate`'s deliberate
`exit 2` (a one-time nudge, not a real block — see below) — everything else
always exits 0.

**Dependency: [`jq`](https://jqlang.org/).** Every hook that reads a JSON
config checks for `jq` first; if it's missing, the hook prints a one-line
stderr note and no-ops rather than erroring. Install `jq` if you want the
config-driven behavior; hooks remain harmless (silent no-op) without it.

## The hooks

### 1. `preferred-tool-gate` (PreToolUse)

Nudges the agent toward project-preferred tools (e.g. an MCP-based code
indexer) instead of raw text tools, exactly once per session, per matching
tool class.

- Reads `.claude/hooks-config/preferred-tools.json`.
- Mechanism (unchanged from the Sauron original): a **PID-keyed sentinel
  file** (`$TMPDIR/preferred-tool-gate-$PPID`) blocks the **first** matching
  tool call in a session — the hook exits `2` and prints the configured
  `hint_message` to stderr, which Claude Code surfaces as a blocked-call
  message and lets the agent retry. Every subsequent matching call in the
  same session exits `0` silently (the sentinel already exists).
- Self-cleans sentinel files older than 1 day on every invocation.
- No config file present → exits `0` immediately, no output, no sentinel.

### 2. `preferred-tool-reminder` (SessionStart)

Prints a plain-text banner at session start listing each configured rule's
`trigger_matcher`, `preferred_tools`, and `hint_message`, so the agent sees
the policy proactively instead of only discovering it via a block.

- Reads the same `.claude/hooks-config/preferred-tools.json`.
- No config file present → exits `0`, no output.

### 3. `datetime-sync` (SessionStart)

Always prints a wall-clock context block (UTC, local time, day-of-week,
weekday/weekend classification) — this part is domain-agnostic and always
runs, closing the "day-of-week isn't in the model's context" gap.

Optionally, if `.claude/hooks-config/calendar-provider.json` exists and
declares a `command`, the hook execs that command and appends its stdout,
line-by-line, under a **"Project calendar (authoritative)"** section, using
forgiving `key: value` / `key:value` parsing (unrecognized lines are passed
through verbatim). This lets a project plug in its own "what business day
is it" CLI (fiscal calendar, release-train calendar, trading calendar,
whatever the domain needs) without the hook knowing anything about it.

- Fail-open: if the provider command errors, times out, or prints nothing,
  the hook prints a one-line failure note and continues — it **never**
  aborts the session. Always exits `0`.
- No calendar config present → prints the wall-clock section only, no
  error, no missing-section noise.

### 4. `friction-diary-signal` (SessionStart)

Config-driven summarizer for one or more "status diary" files (a friction
log, a gap ledger, an ADR queue — anything with a recurring status field).

- Reads `.claude/hooks-config/diaries.json`, a list of diary entries. Each
  entry independently supports two formats:
  - **`"format": "markdown"`** — greps for anchored `"<status_field>: "`
    lines, counts occurrences per configured `values`, detects duplicate
    IDs via `id_regex` (default: a generic `[YYYY-MM-DD] ID-NNN` pattern),
    and lists the most recent dated entries.
  - **`"format": "jsonl"`** — parses each line as a standalone JSON object
    and reads `status_field` as a **top-level JSON key** instead of a
    markdown line; malformed lines are skipped, not fatal.
- Each diary entry can set `headline_value` to call out one status value
  specially (e.g. a "ready to build" or "urgent" state) with a `[HEADLINE]`
  line.
- Skips (does not error) any configured diary whose `path` doesn't exist,
  or whose `format` is unrecognized — the rest of the config still runs.
- No config file present → exits `0`, no output.

The JSONL-mode support exists so this hook works whether a project renders
its friction log as markdown prose or as an append-only JSONL log (see the
sibling `friction-diary/` component in this toolkit for a JSONL-based
friction-log format).

### 5. `workspace-state-sync` (SessionStart) — NEW

Not present in Sauron's original hook set; added here to close a real,
previously-manual gap. Fast, **read-only** git/gh checks, printed as a
short digest box:

- current branch name, and whether it matches the repo's default branch
- working-tree dirty count (`git status --porcelain | wc -l`)
- commits local `HEAD` is behind the remote default branch, computed from
  already-cached remote-tracking refs (**does not run `git fetch`** — a
  read-only hook should not perform even a soft network side effect on
  every session start; it reports drift as of the last fetch and expects
  the agent/operator to run `git fetch` if that number looks stale)
- count of local `git worktree`s
- if the `gh` CLI is present and authenticated: count of open PRs authored
  by the current user (silently skipped if `gh` is absent or unauthenticated)

Every individual check is independently wrapped so a single failing check
(no remote configured, `gh` missing, detached HEAD, etc.) is skipped with a
one-line `[note]` in the digest rather than aborting the whole hook. Always
exits `0`. Performs **zero mutations** — read-only by design.

This operationalizes the single-writer-discipline and
stale-local-checkout lessons (don't rely on remembering to check
`git status` / `git log HEAD..origin/main` / `git worktree list` by hand
every session) into an automatic, always-visible fact surface.

## Registering the hooks in `settings.json`

Add a `hooks` block to your project's `.claude/settings.json` (or your user
`~/.claude/settings.json` for a global install). `SessionStart` hooks run
on session startup/resume/clear/compact; `PreToolUse` hooks run before a
matching tool call, and a hook exiting `2` blocks that call (stderr is
shown to the agent as the reason).

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          { "type": "command", "command": "/path/to/hooks/datetime-sync" },
          { "type": "command", "command": "/path/to/hooks/preferred-tool-reminder" },
          { "type": "command", "command": "/path/to/hooks/friction-diary-signal" },
          { "type": "command", "command": "/path/to/hooks/workspace-state-sync" }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Grep|Glob|Read|Bash",
        "hooks": [
          { "type": "command", "command": "/path/to/hooks/preferred-tool-gate" }
        ]
      }
    ]
  }
}
```

Notes:
- The `PreToolUse` matcher should cover the **union** of every
  `trigger_matcher` regex you configure in `preferred-tools.json` — the
  hook itself does the fine-grained per-rule matching once it receives
  control; the `settings.json` matcher just decides whether the hook is
  invoked at all for a given tool call.
- Use absolute paths to the hook scripts (or a path relative to a known
  install location) — `settings.json` does not expand `~` in all Claude
  Code versions; prefer a fully resolved path.
- All five hooks are independent — install any subset. `datetime-sync` and
  `workspace-state-sync` are unconditionally useful with zero config.
  `preferred-tool-gate`/`-reminder` and `friction-diary-signal` are inert
  until you add their config files.

## Opting in per project

Each config-driven hook activates only when its config file exists under
`.claude/hooks-config/` in the **repo root** (resolved via
`git rev-parse --show-toplevel`, falling back to the current working
directory if not inside a git repo):

| Hook(s) | Config file | Example |
|---|---|---|
| `preferred-tool-gate`, `preferred-tool-reminder` | `.claude/hooks-config/preferred-tools.json` | [`config/preferred-tools.example.json`](config/preferred-tools.example.json) |
| `datetime-sync` (calendar extension only) | `.claude/hooks-config/calendar-provider.json` | [`config/calendar-provider.example.json`](config/calendar-provider.example.json) |
| `friction-diary-signal` | `.claude/hooks-config/diaries.json` | [`config/diaries.example.json`](config/diaries.example.json) |

To opt in: copy the relevant example file into your project's
`.claude/hooks-config/` directory (dropping `.example` from the filename)
and edit the fields for your project. To opt back out: delete (or rename)
the config file — the corresponding hook(s) revert to a silent no-op on the
very next session start, no script edits required.

### Config field reference

**`preferred-tools.json`** — array of rules:

| Field | Required | Meaning |
|---|---|---|
| `trigger_matcher` | yes | Regex (anchored `^(...)$` internally) matched against the tool name about to run |
| `preferred_tools` | no | Array of tool names to suggest instead |
| `hint_message` | no | Free-text explanation shown on the first block / in the reminder banner |

**`calendar-provider.json`** — single object:

| Field | Required | Meaning |
|---|---|---|
| `command` | yes | Shell command to exec; stdout is parsed as forgiving `key: value` lines and appended verbatim |

**`diaries.json`** — array of diary entries:

| Field | Required | Meaning |
|---|---|---|
| `path` | yes | Path to the diary file, relative to repo root (or absolute) |
| `status_field` | no (default `"status"`) | Field name to count occurrences of |
| `values` | yes | Array of valid enum values for `status_field` |
| `headline_value` | no | One value to call out specially with `[HEADLINE]` |
| `id_regex` | no (has a generic default) | Regex identifying a dated entry ID, markdown mode only |
| `label` | no (default `"Diary"`) | Display name in the summary box header |
| `format` | no (default `"markdown"`) | `"markdown"` or `"jsonl"` |

## Testing a hook manually

Every hook is a plain script — run it directly to see its output without
going through Claude Code:

```bash
cd /path/to/your/project
/path/to/hooks/datetime-sync
/path/to/hooks/workspace-state-sync
```

For `preferred-tool-gate`, note the PID-keyed sentinel is keyed on `$PPID`
(the parent shell's PID) — running it twice from the same shell will show
the "second call is silent" behavior; open a new shell to see the
first-call block again.
