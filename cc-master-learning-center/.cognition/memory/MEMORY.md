# Memory Index

> Index only — one line per entry, detail in linked topic files. Keep this file under its
> size budget (see `.memory-lint.yml` / `check_memory_size.py`; default 24 KB, soft warning
> at 22 KB). **Authoring rule:** reference a *source file* with a backtick code path that
> includes a directory component, e.g. `` `.cognition/memory/check_memory_decay.py` `` —
> never wrap a source path in Markdown-link syntax. Reference a *topic file* with
> Markdown-link syntax instead, the way the Lessons section below links to
> [overstated enforcement claims](feedback_overstated_enforcement_claims.md) — that is the
> syntax `check_memory_size.py`'s link-integrity checker resolves as a topic-file pointer;
> a source path wrapped the same way would be misparsed as a broken one.

## Current State

- **This branch carries cognition-substrate infrastructure only, not CC application code
  (2026-07-07).** `cc-master-learning-center`'s real source (`spine/cc_spine/*.py`, its test
  suite, and its `cc-spine.yml` CI workflow) exists only on the unmerged
  `claude/cc-cert-learning-plan-xqo5g7` branch — it was never merged into `main`, and this
  branch (`claude/cognition-substrate`) was cut from `main`. Do not assume any `spine/`
  source file exists here without checking; `git status` on `cc-master-learning-center/spine`
  will show it untracked/absent until that branch merges.
- **Cognition OS toolkit re-activated for cc-master-learning-center (2026-07-07).** Restored
  via cherry-pick of the original install/activate commits (`fbb0fca`, `72e1e76`) onto this
  branch — `.cognition/` (memory, codebase-index, friction, ci-governance) and `.claude/`
  (commands, hooks, settings) are present; this `MEMORY.md` and the `feedback_*.md` files
  linked below are the first real (non-template) content in it.
- **Hook-path fix + full content-authoring pass (2026-07-07).** `.claude/settings.json`'s
  hook commands were a hardcoded absolute Windows path (author-machine-only); fixed
  upstream (`cognition-os-toolkit` commit `b7365a7`) to `$CLAUDE_PROJECT_DIR`-relative,
  portable across every clone/CI runner — propagated here and to the sibling installs.
  Same session: `ci-governance/gates.yml` authored + schema-validated (captures
  `cc-cognition-substrate.yml`'s 8 real jobs; NOT yet adopted as that workflow's
  generator — needs `jsonschema` + a `gen_ci.py --write` run, separate step);
  `PROJECT_FACTS.yml` and `.claude/commands/*.md` placeholders filled or marked N/A
  (`deploy-ops.md`/`migration.md` genuinely not applicable — flat-JSON fact store, no
  deploy target); `sitrep.md` now points at the real `claims_cli.py` instead of a
  generic placeholder; `friction_log.jsonl` + `threshold_config.yml` initialized;
  `cognition_inventory` regenerated (5/5 instantiated, up from 3/5). `PROJECTS.md` and
  this repo's CI-workflow comment updated to match (both previously overstated
  ci-governance/`.claude` as fully un-instantiated).

## Reference

<!-- No reference_*.md topic files yet. -->

## Lessons & Standing Rules

- **Verify enforcement claims against code, not intent, in the same pass that writes them.**
  [overstated enforcement claims](feedback_overstated_enforcement_claims.md)
- **Never assert a CSS class rendered from a bare substring match on page output.**
  [CSS-class-substring test false positive](feedback_css_class_substring_test_false_positive.md)
- **Grep content-gates need compound identifiers, tested against real output, never bare
  words.** [grep-gate bare-word false positive](feedback_grep_gate_bare_word_false_positive.md)
- **Missing data must sort/render distinctly from worst-case data, never default to it.**
  [defaulting missing data to worst-case](feedback_default_missing_data_to_worst_case.md)

## Closed / Historical

<!-- Nothing closed yet — this file was just instantiated from MEMORY.template.md. -->
