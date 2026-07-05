# Friction Diary

A portable, hardened "operational friction diary": a place to record *"I just
did something manually that I've done before or will do again"* as a
structured, trackable entry — with an automated, formula-driven gate for
deciding when recurring friction has earned an automation project, instead
of relying on a human eyeballing a table once a week.

This component is designed to be dropped into any project (a web app, an
infra repo, a data pipeline, anything with recurring human toil) with zero
code changes — only `threshold_config.yml` and the contents of each entry's
`domain_extensions` bucket are project-specific.

## Why this exists

Two failure modes show up constantly around recurring operational toil:

1. **Premature automation** — someone hits a one-off problem once, gets
   annoyed, and builds tooling for something that will never happen again.
   That tooling then rots, unmaintained, solving a problem nobody has.
2. **Permanent manual toil** — something recurs constantly (weekly, even
   daily), everyone individually notices it's annoying, nobody writes it
   down anywhere durable, and it never crosses the threshold of "this is
   worth 3 hours of someone's time to fix" because there's no aggregate
   record showing it's happened 12 times this quarter.

The friction diary is the durable record that sits between those two
failure modes: log friction the first time you notice it, keep a lightweight
count and evidence trail every time it recurs, and let an explicit,
tunable, two-factor formula (not vibes) decide when it's crossed into
"worth automating."

## Why JSONL-as-source-of-truth + generated Markdown, not a database

- **Append-only and diffable.** A new entry, or a bump, is a one-line
  addition or a single-line replace. `git diff` on the log file shows
  exactly what changed, in plain text, in every PR review.
- **Git-merge-friendly across concurrent sessions.** If two people (or two
  agent sessions in two worktrees) both add entries the same day, JSONL's
  line-oriented structure means the merge is a trivial union of new lines
  in the common case, and a small, readable conflict in the rare case where
  the exact same line was edited by both — nothing like the opaque
  merge-conflict-on-a-binary-blob problem a SQLite file or a spreadsheet
  would produce.
- **No server, no schema migration ceremony.** Any tool that can read a text
  file line-by-line can consume this. No database driver, no lock file, no
  "which version of the schema is this DB on."
- **The Markdown view is generated, never hand-edited.** Humans read
  `FRICTION_DIARY.md`; humans and scripts *write* `friction_log.jsonl`. This
  mirrors the same discipline used for other generated-doc systems (e.g. a
  codebase index): the source of truth is structured and machine-writable,
  the human-facing artifact is regenerated on demand and clearly marked as
  such, and nobody edits the generated file directly because it will be
  silently overwritten the next time it's regenerated.

## Files

| File | Purpose |
|---|---|
| `SCHEMA.md` | Canonical entry schema. Read this first — everything else conforms to it. |
| `friction_log.example.jsonl` | 5 example entries showing every status in the lifecycle, in a generic web-app-deploy example domain. |
| `threshold_config.example.yml` | Example pluggable build-threshold config. Copy to `threshold_config.yml` and tune per project. |
| `friction_cli.py` | The CLI: `log`, `bump`, `review`, `promote`. |
| `friction_render.py` | Renders the JSONL log into a human-readable `FRICTION_DIARY.md`. |
| `tests/test_friction_cli_self.py` | Self-test exercising the full lifecycle end-to-end. |

## Schema, in brief

See `SCHEMA.md` for the full field-by-field spec. The load-bearing ideas:

- **`domain_extensions`** is the *only* place project-specific taxonomy
  lives (e.g. `{"plane": "ci-cd", "team": "checkout"}`). No script here
  ever reads a key out of it — that's what keeps the CLI and renderer
  portable across projects with completely different classification
  vocabularies.
- **`golden_rule_answer`** (required boolean) answers *"would this recur
  next week if nothing changed?"* If the honest answer is no, this doesn't
  belong in the diary — it's one-off incident/forensic work, and the CLI
  refuses to create the entry, printing a note to file it elsewhere.
- **`falsifiability_gate`** (required string) forces every entry to state
  what evidence would prove it *wrong* — not just what evidence supports it.
- **Two-factor build threshold**: recurrence count, severity, *and* elapsed
  time between first and last observation must all clear a bar (see
  `threshold_config.example.yml`) before an entry is build-eligible. Any one
  factor alone is not enough — this is what stops "3 occurrences in one
  afternoon" from reading the same as "3 occurrences over a month."
- **Verifier/proposer separation.** `review` only *prints a diff* between
  what the formula says and what's stored — it never mutates anything.
  `promote` is a distinct, deliberate command a human (or a separate review
  pass) runs; the `QUALIFYING -> BUILD_ELIGIBLE` step specifically requires
  `--evidence`, so promotion is never just a proposing session flipping its
  own flag.

## The CLI

All commands operate on a JSONL log path (`--log`, default
`friction_log.jsonl`) and support `--json` for machine-readable output.

### `log <title>`

Searches existing entries (simple token-overlap scoring across `title`,
`affected_component`, `manual_procedure` — no ML dependency) and prints the
top 3 candidate matches. Never silently merges:

- If a match is confirmed (interactively, or via `--match-id <id>` for
  scripted use), it delegates to `bump` on that entry.
- Otherwise, it creates a new entry — but only if every required field is
  supplied (`--affected-component`, `--manual-procedure`, `--proposed-fix`,
  `--severity`, `--falsifiability-gate`) **and** `--golden-rule-yes true` is
  passed explicitly. Omitting or falsifying that flag is a hard refusal.

The new entry's ID is derived as `max(existing numeric suffix for the
prefix) + 1`, scanned from the actual log file — never guessed, never
reused.

```bash
python friction_cli.py log "Manual restart of worker after deploy" \
  --golden-rule-yes true \
  --affected-component "worker fleet" \
  --manual-procedure "ssh in and restart the process by hand" \
  --proposed-fix "add a supervised auto-restart hook" \
  --severity normal \
  --falsifiability-gate "if this stops recurring over the next 30 days" \
  --non-interactive
```

### `bump <id>`

Appends one `{date, note}` to `evidence_log` and increments
`recurrence_count`. Rewrites *only* that entry's JSONL line — a targeted
line replace, not a full-file rewrite — so unrelated entries never show up
in the diff.

```bash
python friction_cli.py bump GAP-1 --note "third occurrence, during v2.16 deploy"
```

### `review`

Loads `threshold_config.yml` (or `--config`), recomputes build-eligibility
for every `CANDIDATE`/`QUALIFYING` entry, and prints a diff against the
entry's stored `status`. This is what catches manual-eyeball drift: a human
made a judgment call weeks ago, the numbers have since moved, and nobody
re-checked. **Read-only** — never mutates the log.

```bash
python friction_cli.py review --config threshold_config.yml
```

### `promote <id>`

Moves `status` forward exactly one lifecycle step
(`CANDIDATE -> QUALIFYING -> BUILD_ELIGIBLE -> BUILT`), or sideways to an
off-ramp (`DISQUALIFIED` / `DEFERRED`). Refuses to skip states. The
`QUALIFYING -> BUILD_ELIGIBLE` step requires `--evidence "..."` citing
concrete proof. Promoting to `BUILT` requires `--built-as` and `--built-pr`,
and accepts `--post-build-due` / `--post-build-procedure` to seed a
`post_build_check` so `BUILT` doesn't become a permanent unverified
end-state.

```bash
python friction_cli.py promote GAP-1 --evidence "review run 2026-07-05: recurrence_count=4, severity=critical_path, days_span=34, all thresholds cleared"
python friction_cli.py promote GAP-1 --built-as scripts/worker_autorestart.py --built-pr PR-501 \
  --post-build-due 2026-08-05 --post-build-procedure "confirm the hook fired on the next 3 worker crashes"
```

## `friction_render.py`

Regenerates a human-readable Markdown view from the JSONL log:

```bash
python friction_render.py --log friction_log.jsonl --config threshold_config.yml --out FRICTION_DIARY.md
```

The output starts with an aggregate rollup table of every non-`BUILT`,
non-`DISQUALIFIED` entry (status, recurrence, severity, days span, and
whether `review`'s recomputed verdict agrees with the stored status),
followed by a full per-entry block for every entry in the log. The
generated file's header comment says, in effect, *"do not hand-edit this;
regenerate it instead"* — the same convention used by other generated-doc
systems, so a human never loses an edit by hand-patching a file that gets
silently overwritten on the next run.

## `threshold_config.yml` — tuning per project

Copy `threshold_config.example.yml` to `threshold_config.yml` and edit
three things, without touching any script:

- `severity_values` — the full enum your project allows for
  `severity_signal`.
- `required_severity_values` — the subset of that enum that counts toward
  build-eligibility (e.g. maybe only `critical_path` counts, or maybe
  `critical_path` and `normal` both do).
- `min_recurrence_count` / `min_days_between_first_and_last` — the numeric
  bars. A fast-moving on-call rotation might tighten the day-span and loosen
  the count; a slow quarterly process might do the opposite.

## Worked example walkthrough

```bash
# 1. Log the friction the first time you notice it.
python friction_cli.py log "Manual restart of worker after deploy" \
  --golden-rule-yes true \
  --affected-component "worker fleet" \
  --manual-procedure "ssh in and restart the process by hand" \
  --proposed-fix "add a supervised auto-restart hook" \
  --severity critical_path \
  --falsifiability-gate "if this stops recurring over the next 30 days" \
  --non-interactive
# -> Created GAP-1: Manual restart of worker after deploy (status=CANDIDATE)

# 2. It happens again, weeks later. `log` finds the near-duplicate and
#    surfaces it instead of creating a second entry for the same friction.
python friction_cli.py log "Worker needed a manual restart again after deploy" --non-interactive
# -> lists GAP-1 as a candidate match, refuses to auto-create, tells you to
#    pass --match-id GAP-1 (or --no-search to force a new entry).

python friction_cli.py log "Worker needed a manual restart again after deploy" --match-id GAP-1
# -> delegates to bump: GAP-1 recurrence_count=2

# 3. It happens twice more over the following weeks.
python friction_cli.py bump GAP-1 --note "third occurrence"
python friction_cli.py bump GAP-1 --note "fourth occurrence, a month after the first"

# 4. Run review. The numbers now clear the configured threshold
#    (recurrence_count=4 >= 3, severity=critical_path is required,
#    days_span comfortably >= 7) but GAP-1 is still stored as CANDIDATE
#    because nobody has promoted it yet.
python friction_cli.py review --config threshold_config.yml
# -> [DRIFT] GAP-1  stored=CANDIDATE  recomputed=BUILD_ELIGIBLE  ...
#    1 entry flagged for drift ...

# 5. A human (or a distinct review pass) confirms the promotion, writing
#    down the evidence rather than just flipping the flag.
python friction_cli.py promote GAP-1
# -> CANDIDATE -> QUALIFYING (one step at a time)
python friction_cli.py promote GAP-1 --evidence "review 2026-07-05 confirms all 3 threshold conditions"
# -> QUALIFYING -> BUILD_ELIGIBLE

# 6. Eventually the automation ships.
python friction_cli.py promote GAP-1 \
  --built-as scripts/worker_autorestart.py --built-pr PR-501 \
  --post-build-due 2026-08-05 \
  --post-build-procedure "confirm the hook fired automatically on the next 3 worker crashes, with no manual SSH restart"
# -> BUILD_ELIGIBLE -> BUILT

# 7. Regenerate the human-readable view.
python friction_render.py --log friction_log.jsonl --config threshold_config.yml --out FRICTION_DIARY.md
```

At this point `FRICTION_DIARY.md` shows GAP-1 as `BUILT`, with its
`post_build_check` due date still pending a result — a visible reminder
that "built" isn't the same as "confirmed adopted," until someone comes
back on or after `2026-08-05` and fills in whether the hook actually fired.

## Testing

```bash
python tests/test_friction_cli_self.py
# or
pytest tests/test_friction_cli_self.py -v
```

The self-test runs the full lifecycle in a temp directory: entry creation
(including the golden-rule refusal path), duplicate detection, `bump`
targeted-line-replace behavior, `review`'s drift detection, `promote`'s
state-skip refusal and evidence requirements, and a final render pass.

---

This design is modeled on real operational lessons from a production
trading system, where two independently-evolved, hand-maintained Markdown
friction diaries converged on the same shape by necessity — this component
generalizes and hardens that shape into portable, automated tooling.
