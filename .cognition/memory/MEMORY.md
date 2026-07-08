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

- **Cognition OS toolkit instantiated at repo root, scoped to `projects/llm-log-triage`
  (2026-07-07).** The toolkit's own install commit framed this root-level `.cognition/` as
  belonging to "Root (CC Cert / llm-log-triage)" — i.e. it's physically at the repo root but
  conceptually scoped to the flagship project, matching the fact that root
  `.github/workflows/ci.yml` has exactly one job and it's scoped entirely to
  `projects/llm-log-triage`. (Root `README.md` is likewise primarily about that project, but
  — as of the cognition-substrate work itself — now also links out to `PROJECTS.md` for the
  other two; it is not exclusively single-project the way `ci.yml` is.) This `MEMORY.md`, a
  `cognition_inventory` codebase-index generator, and the
  concurrency claims registry (`.cognition/active-work/claims_cli.py`) are now real — ported
  from the pattern first proven on this repo's `cc-master-learning-center` project. See the
  generated inventory (regenerate: `python3 cli.py --write --only cognition_inventory` from
  `.cognition/codebase-index/`) for the live per-subsystem count.
- **All 5 subsystems now instantiated + hooks fixed to be portable (2026-07-07, same-day
  follow-up).** A concurrent session authored `.cognition/friction/friction_log.jsonl` +
  `.cognition/ci-governance/gates.yml` here (previously template-only) and fixed
  `.claude/settings.json`'s
  hook commands from a hardcoded Windows path to `$CLAUDE_PROJECT_DIR`-relative — portable
  across every clone/CI runner now, not just the original author's machine. That direct-to-main
  push regenerated `cc-master-learning-center`'s committed `cognition_inventory.md`/`.json` but
  not this project's or `osai-prep-studio`'s, leaving `codebase-index-gate` red on `main` until
  a follow-up commit ran `--write` here too — exactly the drift the generator's `--check` gate
  exists to catch, once someone actually re-ran it.
- **Scope caveat for `cognition_inventory`'s `env_var_index` demo generator:** at repo root,
  `PROJECT_ROOT` is the whole repo, not just `projects/llm-log-triage/` — the env-var-scanning
  demo generator (kept registered, never gated/committed — see `cli.py`'s NOTE) would scan
  every project's Python files if run, not just the flagship's. Harmless since it's a
  read-only demo never wired into CI, but worth knowing before running it manually.
- **No `feedback_*.md` lessons exist yet.** No session porting this toolkit has direct
  visibility into a specific `llm-log-triage` mistake worth generalizing into a standing
  rule. Add one the first time a real review catches a recurring pattern here — don't
  backfill a placeholder just to fill the section.

## Reference

<!-- No reference_*.md topic files yet. -->

## Lessons & Standing Rules

<!-- Empty on purpose -- see "No feedback_*.md lessons exist yet" above. Add an entry only
     when a real, observed mistake generalizes into a standing rule; do not seed this with
     a plausible-sounding lesson that didn't actually happen here. -->

## Closed / Historical

<!-- Nothing closed yet — this file was just instantiated from MEMORY.template.md. -->
