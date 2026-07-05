# Memory Index

> Index only — one line per entry, detail in linked topic files. Keep this file under its
> size budget (see `.memory-lint.yml` / `check_memory_size.py`; default 24 KB, soft warning
> at 22 KB). **Authoring rule:** repo-file references use backtick code paths
> (`` `path/to/file.py` ``), NOT Markdown link syntax (`[label](path/to/file.py)`) — the
> link-integrity checker only resolves Markdown links for `.md` topic-file pointers, and a
> code-path wrapped in Markdown-link syntax will be misparsed as a broken topic-file link.

<!--
  HOW TO USE THIS TEMPLATE
  ========================
  1. Copy this file to memory/MEMORY.md (or wherever your project's memory
     lives — record that path in .memory-lint.yml as `memory_file_path`).
  2. Delete every block marked "DELETE THIS EXAMPLE" below.
  3. Keep entries to ONE LINE each. If an entry needs more than a line of
     detail, put the detail in a linked topic file (project_*.md,
     feedback_*.md, reference_*.md — see memory_types_guide.md for the
     naming/typing convention) and link it with `[short label](topic_file.md)`.
  4. Run `python check_memory_size.py` before ending a session that touched
     this file. Run `python check_memory_decay.py --file MEMORY.md
     --repo-root .` periodically (or in CI) to catch references that have
     gone stale.
-->

## Current State

<!-- DELETE THIS EXAMPLE — illustrates the expected one-line, dated entry style -->
- **Example: auth-refactor migration COMPLETE (2026-01-15).** Moved session
  handling to `src/auth/session_store.py`. Follow-up work tracked in
  [project_auth_refactor.md](project_auth_refactor.md).
<!-- END DELETE THIS EXAMPLE -->

## Reference

<!-- DELETE THIS EXAMPLE -->
- [Deploy runbook](reference_deploy_runbook.md) — canonical deploy steps; read before any release.
<!-- END DELETE THIS EXAMPLE -->

## Lessons & Standing Rules

<!-- One-line lessons that generalize across sessions. Prefer linking to a
     feedback_*.md topic file for anything with more than a sentence of
     detail or a specific failure story behind it. -->

## Closed / Historical

<!-- Entries that are resolved but worth a one-line record (not deleted
     outright — deleting institutional memory is itself a decay risk).
     Compact aggressively here first when the file approaches its size
     budget. -->
