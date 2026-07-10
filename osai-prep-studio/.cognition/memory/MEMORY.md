# Memory Index

> Index only — one line per entry, detail in linked topic files. Keep this file under its
> size budget (see `.memory-lint.yml` / `check_memory_size.py`; default 24 KB, soft warning
> at 22 KB). **Authoring rule:** reference a *source file* with a backtick code path that
> includes a directory component, e.g. `` `.cognition/memory/check_memory_decay.py` `` —
> never wrap a source path in Markdown-link syntax. Reference a *topic file* (once one
> exists — see `memory_types_guide.md` for the `feedback_*.md` / `project_*.md` /
> `reference_*.md` naming convention) using square-bracket-then-parenthesis Markdown-link
> syntax instead, so `check_memory_size.py`'s link-integrity checker can verify it resolves
> — a source path wrapped the same way would be misparsed as a broken topic-file link.

## Current State

- **Cognition OS toolkit instantiated for osai-prep-studio (2026-07-07).** `.cognition/`
  (memory, codebase-index, active-work) now has real content — this `MEMORY.md`, a
  `cognition_inventory` codebase-index generator, and the concurrency claims registry
  (`.cognition/active-work/claims_cli.py`) — ported from the pattern first proven on this
  repo's `cc-master-learning-center` project (see that project's own memory file for its
  history; not linked here as a path since it lives outside this project's repo-root). See
  the generated inventory (regenerate: `python3 cli.py --write --only cognition_inventory`
  from `.cognition/codebase-index/`) for the live per-subsystem count.
- **All 5 subsystems now instantiated + hooks fixed to be portable (2026-07-07, same-day
  follow-up).** A concurrent session authored `.cognition/friction/friction_log.jsonl` +
  `.cognition/ci-governance/gates.yml` here (previously template-only) and fixed
  `.claude/settings.json`'s
  hook commands from a hardcoded Windows path to `$CLAUDE_PROJECT_DIR`-relative — portable
  across every clone/CI runner now, not just the original author's machine. That direct-to-main
  push regenerated `cc-master-learning-center`'s committed `cognition_inventory.md`/`.json` but
  not this project's or root's, leaving `codebase-index-gate` red on `main` until a follow-up
  commit ran `--write` here too — exactly the drift the generator's `--check` gate exists to
  catch, once someone actually re-ran it.
- **This project's primary decision-trail is its numbered planning-doc series** (`00a-vision.md`
  through `26-completion-plan-750.md` and growing), not this `MEMORY.md`. That convention
  predates the toolkit install and is intentionally left in place — this file is a narrower
  complement for cross-session *operational* lessons and quick-reference state, not a
  replacement for the numbered docs' design-decision record.
- **No `feedback_*.md` lessons exist yet.** Unlike `cc-master-learning-center`'s memory
  (seeded from a session with direct visibility into its PR-10/PR-11 review history), no
  session porting this toolkit has direct visibility into a specific osai-prep-studio
  mistake worth generalizing into a standing rule. Add one the first time a real review
  catches a recurring pattern here — don't backfill a placeholder just to fill the section.

## Reference

<!-- No reference_*.md topic files yet. -->

## Lessons & Standing Rules

<!-- Empty on purpose -- see "No feedback_*.md lessons exist yet" above. Add an entry only
     when a real, observed mistake generalizes into a standing rule; do not seed this with
     a plausible-sounding lesson that didn't actually happen here. -->

## Closed / Historical

<!-- Nothing closed yet — this file was just instantiated from MEMORY.template.md. -->
