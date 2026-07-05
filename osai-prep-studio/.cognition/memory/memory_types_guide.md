# Memory types guide

A concise authoring guide for Claude Code's cross-session, file-based memory: when to save
something, which of the four memory types it belongs to, the frontmatter shape each type
expects, and — just as important — what should **never** be saved.

This guide is standalone: it applies to any project using this memory system, not to any
one codebase in particular.

## The four types

| Type | Purpose | Lives in | Typical filename prefix |
|---|---|---|---|
| **user** | Standing facts about the human operator: preferences, environment, recurring constraints that hold across every project they work on. | A user-level memory location (not project-scoped). | (no prefix convention needed — user memory is usually a single small file or a few) |
| **feedback** | A lesson learned from a specific mistake, near-miss, or correction — "this went wrong once, here's the rule that prevents recurrence." | Project memory directory | `feedback_*.md` |
| **project** | Durable knowledge about a specific ongoing initiative, program, or subsystem: its design, current status, decisions made, and why. | Project memory directory | `project_*.md` |
| **reference** | A stable fact, credential location, protocol, or lookup table you'll need to re-consult but that isn't tied to one initiative's narrative (e.g. "how do I SSH into X", "here is the API's rate limit"). | Project memory directory | `reference_*.md` |

### When to save one

Save a memory entry when the information:

1. **Will be needed again** in a future session (not just useful right now), AND
2. **Is not already discoverable** by reading the current codebase, CLAUDE.md, or recent
   git history in under a minute, AND
3. **Would cost real time or cause a real mistake to re-derive** if forgotten.

If all three are true, write a one-line index entry in `MEMORY.md` and, if the detail is
more than a sentence, a linked topic file with the full story.

### Required frontmatter shape

Every topic file (the `project_*.md` / `feedback_*.md` / `reference_*.md` files linked from
the index) should open with frontmatter that makes its type and purpose machine-readable:

```markdown
---
name: <short_snake_case_identifier>
description: <one-sentence summary of what this file records and when to read it>
metadata:
  type: project | feedback | reference | user
---

# Human-readable title

...body...
```

- `name` should match the filename (minus extension) so cross-references stay unambiguous.
- `description` is what a future session skims to decide whether to open the file — write it
  as "read this when you need to know X," not a vague label.
- `metadata.type` must be exactly one of the four values above. This is what lets tooling
  (including future lint/consolidation tools in this toolkit) reason about the memory corpus
  by type without re-parsing prose.

### The index entry itself (in `MEMORY.md`)

One line, present tense or dated-past-tense, with a link to the topic file for detail:

```markdown
- **Short label of the current state (YYYY-MM-DD).** One clause of why it matters.
  [topic label](project_whatever.md)
```

Use a backtick code path — not a Markdown link — when the reference is to a **source file**,
not a memory topic file: `` `src/auth/session_store.py` ``, never
`[session_store.py](src/auth/session_store.py)`. The link-integrity checker in this toolkit
(`check_memory_size.py`) only resolves `.md` Markdown-link targets as topic-file pointers; a
source-code path wrapped in Markdown-link syntax will be misparsed as a broken topic-file
link and fail the linter for the wrong reason.

## What NOT to save

Memory is expensive to maintain and cheap to let rot. Do not save:

- **Code patterns derivable from reading the repo.** If a future session can learn it by
  opening the file, it doesn't belong in memory — memory is for things that AREN'T visible
  from the current state of the code (history, rationale, prior failed approaches).
- **Anything git history already answers.** `git log`, `git blame`, and PR history are a more
  reliable and more detailed record than a paraphrase in a memory file. Link to a PR/commit
  instead of restating its contents.
- **Debugging solutions for one-off bugs.** A fixed bug's root cause and fix are best recorded
  in the commit message or an incident doc, not in cross-session memory — unless the *lesson*
  generalizes ("we keep making this class of mistake"), in which case save the lesson (as
  `feedback_*.md`), not the bug.
- **Anything already stated in the project's CLAUDE.md** (or equivalent auto-loaded
  instructions file). Duplicating it in memory creates two sources of truth that can silently
  diverge. If it's a standing rule the project should always load, it belongs in CLAUDE.md,
  not memory.
- **Ephemeral in-progress task state.** "I am currently in the middle of X, step 3 of 7" is
  session-scratch, not memory — it will be stale and misleading the moment the session ends
  or another session picks up the thread differently. Record the *outcome* once the task
  reaches a stable state, not the blow-by-blow.
- **Anything you are not confident will still be true** the next time someone reads it. A
  memory file that confidently asserts something false is worse than no memory at all,
  because it actively misdirects instead of leaving an honest gap. (See
  `check_memory_decay.py` in this toolkit — it exists precisely to catch this class of
  problem: a reference that sounded right when written but has since gone stale.)

## Keeping memory honest over time

- Run the size linter (`check_memory_size.py`) regularly — a memory file that has grown past
  its budget is a sign it has accumulated in-progress trail that should have been compacted
  into topic files or deleted.
- Run the decay linter (`check_memory_decay.py`) periodically — it catches references to
  files, paths, and functions that no longer exist or have changed shape since the memory
  entry was written.
- When compacting, prefer **moving detail to a topic file and shrinking the index entry**
  over deleting the fact outright. The exception is anything that has become actively false
  (per the decay checker) — false memory should be corrected or removed immediately, not
  preserved for continuity's sake.
