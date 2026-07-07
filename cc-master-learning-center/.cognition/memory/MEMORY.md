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
  linked below are the first real (non-template) content in it. **`.claude/`'s hooks are not
  actually functional here**: `.claude/settings.json` registers them, but each hook command is
  a hardcoded Windows path (`C:/Users/izuuh/...`) left over from the original install, which
  doesn't resolve on this or any other non-original-author machine — "registered" is true,
  "wired" would overstate it. Fixing that path is out of scope for this slice (see the
  cognition-substrate plan's explicit exclusions).

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
