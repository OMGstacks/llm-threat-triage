# codebase-index

A small, pluggable framework for **generated documentation that stays in sync
with its source**: extract structured data from source files, render it to
Markdown and JSON, and fail CI the moment either rendered file drifts from
what's actually on disk.

This directory has no domain-specific knowledge baked in. `framework.py` is
generic; you write your own "generator" classes for whatever generated-from-source
docs your project needs, register them in a tiny `cli.py`, and get `--check` /
`--write` / `--list` for free.

## The extract / render / check pattern

Every generator is a strict 3-stage pipeline:

```
extract()        source files -> structured data     (pure function, no I/O writes)
render_md(data)  structured data -> Markdown string
render_json(data) structured data -> JSON string
```

`extract()` is the single source of truth. Both renderers are pure functions
of its return value — never two independently-derived views of the source,
which is exactly how a Markdown/JSON pair quietly drifts apart from each other
over time.

Two CLI modes drive the pipeline:

- **`--write`**: run `extract()` once, run both renderers, write the results
  to each generator's `output_paths()`. This is what you run locally after
  changing something the generator reads, then commit the diff.
- **`--check`**: run the exact same computation **in memory** and diff it,
  byte-exact, against whatever is currently committed on disk. Any mismatch
  (including a file that doesn't exist yet) is a hard failure — non-zero exit.
  This is what CI runs. It proves the committed generated file is still an
  accurate rendering of current source, not a snapshot from three commits ago.

`--list` prints registered generator names and their output paths without
running anything (fast sanity check / discovery). `--only NAME` restricts
`--check` or `--write` to a single generator, useful when a project registers
several and you're iterating on just one.

## Registering a new generator

1. Copy `cli.py` into your project's repo root (or wherever you want the
   entrypoint to live).
2. Write a class implementing the 5-member `IndexGenerator` protocol from
   `framework.py`:
   - `name` (property) — a unique string identifier, used by `--only` and in
     warning/error messages.
   - `inputs()` — the list of source file `Path`s this generator reads. Used
     for missing-file error messages and available for any staleness/mtime
     reasoning a caller wants to layer on top (the framework itself always
     does a full re-extract on `--check` — that's the only fully correct
     check).
   - `extract()` — pure function, reads `inputs()`, returns structured data
     (a list of dicts or a dict — whatever shape is natural).
   - `render_md(data)` — structured data -> Markdown string. Should call
     `generated_header(...)` and prepend its output.
   - `render_json(data)` — structured data -> JSON string. Convention: this
     is `json.dumps` of the **same** data `extract()` returned (typically
     wrapped in an envelope with `generated_json_marker(...)`'s
     `_generated_by` key), sorted and indented for stable diffs. A light
     transform (renaming a key, dropping an internal-only field) is fine;
     re-deriving the data from source a second time is not.
   - `output_paths()` — `{"md": Path(...), "json": Path(...)}` (or additional
     format keys, each requiring a matching `render_<key>` method).

   See `example_generator.py` for a complete, working implementation (an
   "every `os.environ.get(...)` / `os.getenv(...)` reference in the codebase"
   index — genuinely useful standalone, and a template for your own).

3. In your copy of `cli.py`, import your class, instantiate it (pointing at
   your project's actual paths), add it to the `GENERATORS` list, and delete
   the example generator import/instance if you don't want it too.
4. Wire `--check` into CI (it's just a script invocation with a non-zero exit
   code on drift) and, optionally, `--write` into a pre-commit hook or a
   documented "run this after you touch X" step.

`framework.py` itself should not need edits — if you find yourself wanting to
change it for a specific generator's needs, that's usually a sign the logic
belongs in the generator's `extract()`/`render_*()` methods instead.

## The generated-header convention

Every generated Markdown file should start with the block `generated_header()`
produces:

```
<!--
GENERATED FILE — DO NOT EDIT BY HAND
Generator: <name>
Inputs:
  - <path>
  - <path>
Regenerate:
  <command>
Check (CI gate):
  <command>
-->
```

This means anyone who opens the file cold — no context, no memory of why it
exists — immediately knows it's generated, what generated it, what it's a
rendering of, and the exact commands to regenerate or verify it. Since JSON
has no comment syntax, the equivalent for JSON output is a reserved top-level
`_generated_by` key with the same four facts, produced by
`generated_json_marker()`.

## The unregistered-file warning

`--check` also scans every registered generator's output **directory** (not
just its exact registered files) and looks for files that aren't claimed by
any registered generator's `output_paths()`. If it finds one, it prints a
**warning** — but does not fail the check.

This is deliberately non-blocking: a generated-docs directory legitimately
often holds hand-maintained content alongside the generated files (a README,
a hand-written overview doc, notes-in-progress). Failing on an unrecognized
file would punish that legitimate pattern. But the warning matters because
the *other* case — a file that used to be generated, or was meant to be
generated, and nobody ever wired a generator for it — silently accumulates
drift nobody is checking. The warning surfaces that file so a human can
decide: "yes, that's hand-maintained, leave it" or "huh, that should have a
generator — let me register one."

Mismatch (a registered output that doesn't match its source) is always a hard
failure. An unregistered file merely sitting in the directory is always a
soft warning. Those are different failure classes and the framework keeps
them that way on purpose.

---

## What's registered for this project

`cli.py` registers two generators:

- **`cognition_inventory`** (`cognition_inventory_generator.py`) — this project's
  real, gated generator. Indexes the toolkit's own five subsystems (memory,
  friction, ci-governance, codebase-index, active-work), reporting
  INSTANTIATED vs. TEMPLATE-ONLY per a marker-file check — see that file's
  module docstring for the full rationale. Output:
  `cc-master-learning-center/docs/codebase_index/cognition_inventory.{md,json}`.
  Gated in CI via `--check --only cognition_inventory`.
- **`env_var_index`** (`example_generator.py`) — the toolkit's shipped
  worked example, kept registered as a reference/demo (`--list`,
  `--only env_var_index` still work) but **not** committed or gated in CI:
  its generated header bakes in an absolute filesystem path derived from
  this project's root, which will never byte-match between two different
  checkout locations (a known limitation of the example generator itself,
  not something specific to this project — see `cli.py`'s NOTE comment).

---

_This framework was extracted from patterns proven in a production
trading-system's migration-table and cron-schedule index generators, where
the extract/render/check shape closed a real class of "the docs say X, the
code does Y" drift._
