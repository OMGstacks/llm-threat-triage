"""framework.py — generic "generated documentation stays in sync with source" framework.

This module contains ZERO project-specific knowledge. It defines:

  - `IndexGenerator`: the protocol every generator must implement (5 members).
  - `generated_header()` / `generated_json_marker()`: the generated-file header
    convention, shared across all generators so every generated file is
    self-describing (what produced it, what it read, how to regenerate/check it).
  - `run_cli()`: the CLI runner — `--check` / `--write` / `--list` / `--only NAME`
    — plus the unregistered-generated-looking-file scan.

A target project does NOT edit this file. It writes its own `IndexGenerator`
subclasses (see `example_generator.py` for a complete worked example) and wires
them into a small project-local `cli.py` (see that file for the ~20-line pattern).

The extract / render / check pattern
-------------------------------------
Each generator's job is a strict pipeline:

    extract()  -> structured data   (pure function; reads source files, no writes)
    render_md(data)   -> Markdown string
    render_json(data) -> JSON string

`--write` calls extract() once, then both renderers, then writes the results to
`output_paths()`. `--check` does exactly the same computation *in memory* and
diffs the result against what is already on disk — byte-exact string comparison,
no normalization, no "close enough." Any mismatch (including a missing file) is a
hard failure (non-zero exit), because it means the committed generated file no
longer reflects the source it claims to be generated from.

Why render_json is (usually) a light transform of the same data
-----------------------------------------------------------------
`render_json()` is not a second, independently-derived view — it should serialize
the SAME structured object `extract()` produced (optionally wrapped with the
`_generated_by` marker block). Two independent code paths computing "the same"
data from source are how a Markdown/JSON pair quietly drifts from each other.
Keep exactly one extraction step; both renderers are pure presentations of it.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


# --------------------------------------------------------------------------
# The generator protocol
# --------------------------------------------------------------------------


@runtime_checkable
class IndexGenerator(Protocol):
    """Protocol every registered generator must implement.

    Five members, in pipeline order:

      name           -- unique identifier (used for --only, --list, warnings)
      inputs()       -- source files this generator reads
      extract()      -- pure function: source files -> structured data
      render_md()    -- structured data -> Markdown string
      render_json()  -- structured data -> JSON string
      output_paths() -- {"md": Path, "json": Path, ...}

    Implement this as a plain class (inheriting from `IndexGenerator` is
    optional — the Protocol is structural/duck-typed via `runtime_checkable`,
    but subclassing documents intent and gets you a not-implemented error for
    free on missing members if you use `BaseIndexGenerator` instead).
    """

    @property
    def name(self) -> str:
        """Unique identifier for this generator, e.g. 'env_var_index'."""
        ...

    def inputs(self) -> list[Path]:
        """Source files this generator reads.

        Used for (a) error messages when a source is missing, and (b) any
        future staleness/mtime-based reasoning a caller wants to layer on top
        (the framework itself does not do mtime comparisons — `--check` always
        does a full re-extract, since that is the only fully correct check).
        """
        ...

    def extract(self) -> Any:
        """Pure function: read `inputs()`, return structured data.

        Must have no side effects (no writes, no mutation of shared state).
        Return a list of dicts or a dict — whatever shape is natural for this
        generator's domain. Both renderers below must be pure functions of
        this same returned value.
        """
        ...

    def render_md(self, data: Any) -> str:
        """Render `data` (as returned by `extract()`) to a Markdown string.

        Should prepend `generated_header(...)` (see helper below) so the
        output file is self-describing.
        """
        ...

    def render_json(self, data: Any) -> str:
        """Render `data` (as returned by `extract()`) to a JSON string.

        Convention: this should be `json.dumps` of the SAME structured object
        `extract()` returned (typically wrapped in an envelope dict that adds
        a `_generated_by` marker — see `generated_json_marker()`), sorted and
        indented for stable diffs. If a generator needs a "light transform"
        (e.g. renaming a key, dropping an internal-only field) that is fine —
        just don't re-derive the data from source a second time.
        """
        ...

    def output_paths(self) -> dict[str, Path]:
        """Mapping of format name -> output file Path, e.g. {"md": ..., "json": ...}.

        Keys are conventionally "md" and "json" but a generator may register
        additional formats; `run_cli` treats every value in this dict as a
        file that must exist and match on `--check` and gets written on
        `--write`. The corresponding render must exist as an attribute lookup:
        `render_<key>` (e.g. key "md" -> method `render_md`). Stick to "md"
        and "json" unless you also add a matching `render_<key>` method.
        """
        ...


class BaseIndexGenerator:
    """Optional convenience base class.

    Subclassing this (instead of just duck-typing `IndexGenerator`) gets you
    a clearer `TypeError` if you forget to implement a member, and a default
    `inputs()`/`name` wiring pattern. Purely a convenience — the framework only
    depends on the structural protocol above, not on this base class.
    """

    @property
    def name(self) -> str:  # pragma: no cover - must be overridden
        raise NotImplementedError

    def inputs(self) -> list[Path]:  # pragma: no cover - must be overridden
        raise NotImplementedError

    def extract(self) -> Any:  # pragma: no cover - must be overridden
        raise NotImplementedError

    def render_md(self, data: Any) -> str:  # pragma: no cover - must be overridden
        raise NotImplementedError

    def render_json(self, data: Any) -> str:  # pragma: no cover - must be overridden
        raise NotImplementedError

    def output_paths(self) -> dict[str, Path]:  # pragma: no cover - must be overridden
        raise NotImplementedError


# --------------------------------------------------------------------------
# Generated-file header convention
# --------------------------------------------------------------------------


def generated_header(
    generator_name: str,
    input_paths: list[Path] | list[str],
    regenerate_cmd: str,
    check_cmd: str,
) -> str:
    """Build the standard HTML-comment header block for generated Markdown.

    Every generated Markdown file should start with this block (via
    `f"{generated_header(...)}\\n{rest_of_markdown}"`) so a reader (human or
    tool) who opens the file cold can immediately see: this is generated, here
    is what generated it, here is what it read, and here is how to regenerate
    or verify it.

    JSON files can't hold a comment, so use `generated_json_marker()` instead
    to get an equivalent top-level `"_generated_by"` key for the JSON output.
    """
    input_lines = "\n".join(f"  - {p}" for p in input_paths)
    return (
        "<!--\n"
        "GENERATED FILE — DO NOT EDIT BY HAND\n"
        f"Generator: {generator_name}\n"
        "Inputs:\n"
        f"{input_lines}\n"
        "Regenerate:\n"
        f"  {regenerate_cmd}\n"
        "Check (CI gate):\n"
        f"  {check_cmd}\n"
        "-->\n"
    )


def generated_json_marker(
    generator_name: str,
    input_paths: list[Path] | list[str],
    regenerate_cmd: str,
    check_cmd: str,
) -> dict[str, Any]:
    """JSON-comment-equivalent convention: a `_generated_by` envelope block.

    JSON has no comment syntax, so the generated-file convention for JSON
    output is a reserved top-level key, `_generated_by`, carrying the same
    four facts as `generated_header()`. A generator's `render_json()` should
    merge this dict's single key into its output envelope, e.g.:

        payload = {
            "_generated_by": generated_json_marker(self.name, self.inputs(), ...),
            "items": data,
        }
        return json.dumps(payload, indent=2, sort_keys=True) + "\\n"
    """
    return {
        "_generated_by": {
            "generator": generator_name,
            "inputs": [str(p) for p in input_paths],
            "regenerate": regenerate_cmd,
            "check": check_cmd,
            "notice": "GENERATED FILE — DO NOT EDIT BY HAND",
        }
    }


# --------------------------------------------------------------------------
# CLI runner
# --------------------------------------------------------------------------


def _render(generator: IndexGenerator, fmt: str, data: Any) -> str:
    method = getattr(generator, f"render_{fmt}")
    return method(data)


def _diff(expected: str, actual: str, path: Path) -> str:
    return "".join(
        difflib.unified_diff(
            actual.splitlines(keepends=True),
            expected.splitlines(keepends=True),
            fromfile=f"{path} (on disk)",
            tofile=f"{path} (regenerated)",
        )
    )


def _select_generators(
    generators: list[IndexGenerator], only: str | None
) -> list[IndexGenerator]:
    if only is None:
        return generators
    selected = [g for g in generators if g.name == only]
    if not selected:
        names = ", ".join(g.name for g in generators)
        raise SystemExit(
            f"ERROR: no registered generator named '{only}'. Registered: {names}"
        )
    return selected


def _scan_unregistered_files(generators: list[IndexGenerator]) -> list[Path]:
    """Warn (never fail) about files sitting in a generator's output directory
    that are not claimed by ANY registered generator's `output_paths()`.

    This catches a generated-docs directory silently accumulating a
    hand-maintained file nobody remembers to register — often legitimate
    (e.g. a README living alongside generated indexes), so this is a WARNING,
    not a failure.
    """
    claimed: set[Path] = set()
    directories: set[Path] = set()
    for g in generators:
        for p in g.output_paths().values():
            claimed.add(p.resolve())
            directories.add(p.resolve().parent)

    unregistered: list[Path] = []
    for d in sorted(directories):
        if not d.exists():
            continue
        for f in sorted(d.iterdir()):
            if not f.is_file():
                continue
            if f.resolve() not in claimed:
                unregistered.append(f)
    return unregistered


def run_cli(generators: list[IndexGenerator], argv: list[str]) -> int:
    """Run the shared CLI over a list of registered generator instances.

    Modes (mutually exclusive except --only, which restricts --check/--write):
      --check        regenerate all in-memory, diff against disk, non-zero on ANY mismatch
      --write         regenerate all, write to disk
      --list          print registered generator names + output paths; do nothing else
      --only NAME    restrict --check/--write to a single generator by name

    Returns an exit code (0 = success), never calls sys.exit() itself so it is
    testable in-process.
    """
    parser = argparse.ArgumentParser(
        prog="codebase-index",
        description="Keep generated documentation in sync with its source.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="Regenerate in-memory and diff against files on disk. Exit non-zero on mismatch.",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="Regenerate and write all registered outputs to disk.",
    )
    mode.add_argument(
        "--list",
        action="store_true",
        help="List registered generator names and their output paths. Does not run anything.",
    )
    parser.add_argument(
        "--only",
        metavar="NAME",
        default=None,
        help="Restrict --check/--write to the single generator named NAME.",
    )
    args = parser.parse_args(argv)

    if not generators:
        print("ERROR: no generators registered.", file=sys.stderr)
        return 1

    if args.list:
        for g in generators:
            paths = ", ".join(f"{k}={v}" for k, v in g.output_paths().items())
            print(f"{g.name}: {paths}")
        return 0

    try:
        selected = _select_generators(generators, args.only)
    except SystemExit as e:
        print(str(e), file=sys.stderr)
        return 1

    if args.write:
        for g in selected:
            missing_inputs = [p for p in g.inputs() if not Path(p).exists()]
            if missing_inputs:
                print(
                    f"ERROR [{g.name}]: missing input file(s): "
                    f"{', '.join(str(p) for p in missing_inputs)}",
                    file=sys.stderr,
                )
                return 1
            data = g.extract()
            for fmt, path in g.output_paths().items():
                content = _render(g, fmt, data)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                print(f"  -> [{g.name}] {path} ({len(content)} chars)")
        print("Done.")
        return 0

    # --check
    drifted: list[tuple[Path, str, str]] = []
    missing: list[Path] = []
    for g in selected:
        missing_inputs = [p for p in g.inputs() if not Path(p).exists()]
        if missing_inputs:
            print(
                f"ERROR [{g.name}]: missing input file(s): "
                f"{', '.join(str(p) for p in missing_inputs)}",
                file=sys.stderr,
            )
            return 1
        data = g.extract()
        for fmt, path in g.output_paths().items():
            expected = _render(g, fmt, data)
            if not path.exists():
                missing.append(path)
                continue
            actual = path.read_text(encoding="utf-8")
            if actual != expected:
                drifted.append((path, expected, actual))

    if missing or drifted:
        print("DRIFT detected:", file=sys.stderr)
        for p in missing:
            print(f"  MISSING: {p}", file=sys.stderr)
        for path, expected, actual in drifted:
            print(f"  STALE:   {path}", file=sys.stderr)
            print(_diff(expected, actual, path), file=sys.stderr)
        print(
            "Run with --write to regenerate, then commit the result.",
            file=sys.stderr,
        )
        return 1

    # Non-blocking: scan for unregistered generated-looking files.
    unregistered = _scan_unregistered_files(selected)
    for f in unregistered:
        print(
            f"WARNING: unregistered file in generated-output directory: {f} "
            "(not claimed by any registered generator's output_paths() — "
            "if this is hand-maintained content, ignore; if it looks generated, "
            "register a generator for it)",
            file=sys.stderr,
        )

    print(f"OK: {sum(len(g.output_paths()) for g in selected)} output file(s) match source")
    return 0
