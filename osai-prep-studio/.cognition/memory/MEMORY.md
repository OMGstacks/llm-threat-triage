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
  from `.cognition/codebase-index/`) for which subsystems are instantiated vs. still
  template-only — `friction/` and `ci-governance/` remain template-only as of this note.
  **`.claude/`'s hooks are not actually functional here**: `.claude/settings.json` registers
  them, but each hook command is a hardcoded Windows path (`C:/Users/izuuh/...`) left over
  from the original install, which doesn't resolve on this or any other non-original-author
  machine — "registered" is true, "wired" would overstate it. Same known issue as
  `cc-master-learning-center`'s copy; fixing it is out of scope for this slice.
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
