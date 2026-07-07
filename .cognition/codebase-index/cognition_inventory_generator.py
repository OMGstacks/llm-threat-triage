"""cognition_inventory_generator.py — indexes this project's own Cognition OS
toolkit: which of its five subsystems (memory, friction, ci-governance,
codebase-index, active-work) are template-only vs actually instantiated.

Why this is worth generating instead of hand-maintaining: before this
generator existed, "which cognition subsystems are actually wired up" was
narrative prose that had to be manually kept in sync with reality (or, more
likely, wasn't). Each subsystem has one unambiguous instantiation marker --
a specific file whose presence means "this stopped being a template and
became real content." `extract()` just checks those markers exist; this has
genuine drift-catching value the moment someone adds (or deletes) one of
those marker files without updating this generator, because `--check` will
then fail on the next CI run instead of the inventory silently going stale.

Each project in this repo that has the Cognition OS toolkit installed gets its
own copy of this file, scoped to that project's own `.cognition/` directory
via the `source_root` passed in by that project's `cli.py` -- there is
exactly one shared, generic `framework.py`, but this generator (like
`claims_cli.py`) is intentionally duplicated per project rather than
imported cross-project, so each copy's marker paths stay simple, relative,
project-local strings instead of needing to know about sibling projects.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from framework import generated_header, generated_json_marker

_GENERATOR_NAME = "cognition_inventory"
_REGENERATE_CMD = "python cli.py --write --only cognition_inventory"
_CHECK_CMD = "python cli.py --check --only cognition_inventory"

# One instantiation marker per subsystem: the file whose existence means
# "this subsystem has real content, not just the template/example it ships
# with." Order here is the order subsystems render in.
_SUBSYSTEMS: list[dict[str, str]] = [
    {
        "name": "memory",
        "marker": "memory/MEMORY.md",
        "template_note": "memory/MEMORY.template.md",
    },
    {
        "name": "friction",
        "marker": "friction/friction_log.jsonl",
        "template_note": "friction/friction_log.example.jsonl",
    },
    {
        "name": "ci-governance",
        "marker": "ci-governance/gates.yml",
        "template_note": "ci-governance/gates.example.yml",
    },
    {
        "name": "codebase-index",
        "marker": "codebase-index/cognition_inventory_generator.py",
        "template_note": "codebase-index/example_generator.py",
    },
    {
        "name": "active-work",
        "marker": "active-work/claims_cli.py",
        "template_note": None,
    },
]


class CognitionInventoryGenerator:
    """Implements the `IndexGenerator` protocol from `framework.py`.

    source_root should be the project's `.cognition/` directory (not the
    project root, not the repo root) -- every marker path above is relative
    to it.
    """

    def __init__(self, source_root: Path, output_dir: Path):
        self.source_root = source_root
        self.output_dir = output_dir

    @property
    def name(self) -> str:
        return _GENERATOR_NAME

    def _documented_paths(self) -> list[str]:
        """Every marker/template path this generator inspects, for the
        generated-header's documentation -- NOT the same as `inputs()`.
        Unlike a typical generator, none of these paths are required to
        exist: a missing marker is the TEMPLATE-ONLY signal being reported,
        not an error. Keeping this separate from `inputs()` lets the header
        stay informative without making `run_cli`'s pre-flight
        missing-input check (which hard-fails on anything `inputs()` lists
        that isn't present) misfire on a project where some subsystems are,
        correctly, still template-only.

        Returned as strings relative to the project root (source_root's
        parent), NOT absolute paths -- an absolute path bakes in whatever
        checkout location happened to generate the file, which differs
        between a local sandbox and a CI runner and would make `--check`
        report permanent false-positive drift the moment this runs anywhere
        but the machine that last ran `--write`."""
        paths = []
        for s in _SUBSYSTEMS:
            paths.append(f".cognition/{s['marker']}")
            if s["template_note"]:
                paths.append(f".cognition/{s['template_note']}")
        return paths

    def inputs(self) -> list[Path]:
        """No path this generator reads is required to exist -- see
        `_documented_paths()`'s docstring. Returning [] here (rather than
        the marker paths) is deliberate: it's what tells `run_cli` there is
        no required-input precondition to enforce before running."""
        return []

    def extract(self) -> list[dict[str, Any]]:
        """Pure function: for each subsystem, check whether its marker file
        exists. Returns one record per subsystem, sorted by declared order
        (not filesystem order -- deterministic regardless of platform)."""
        data = []
        for s in _SUBSYSTEMS:
            marker_path = self.source_root / s["marker"]
            instantiated = marker_path.exists()
            template_path = self.source_root / s["template_note"] if s["template_note"] else None
            data.append(
                {
                    "subsystem": s["name"],
                    "status": "INSTANTIATED" if instantiated else "TEMPLATE-ONLY",
                    "marker": s["marker"],
                    "marker_exists": instantiated,
                    "template_reference": s["template_note"],
                }
            )
        return data

    def render_md(self, data: list[dict[str, Any]]) -> str:
        header = generated_header(
            generator_name=_GENERATOR_NAME,
            input_paths=[str(p) for p in self._documented_paths()],
            regenerate_cmd=_REGENERATE_CMD,
            check_cmd=_CHECK_CMD,
        )
        instantiated_count = sum(1 for d in data if d["marker_exists"])
        lines: list[str] = [
            header,
            "# Cognition OS Toolkit Inventory",
            "",
            f"{instantiated_count}/{len(data)} subsystems instantiated (marker file present) "
            "vs. still template-only, for this project's `.cognition/` toolkit.",
            "",
            "| Subsystem | Status | Marker |",
            "|---|---|---|",
        ]
        for d in data:
            lines.append(f"| {d['subsystem']} | {d['status']} | `{d['marker']}` |")
        lines.append("")
        lines.append(
            "A subsystem is INSTANTIATED when its marker file exists -- a real content "
            "file, not the template/example the toolkit ships with. See each subsystem's "
            "own README.md for what \"instantiated\" means in more depth."
        )
        lines.append("")
        return "\n".join(lines)

    def render_json(self, data: list[dict[str, Any]]) -> str:
        payload = {
            **generated_json_marker(
                generator_name=_GENERATOR_NAME,
                input_paths=[str(p) for p in self._documented_paths()],
                regenerate_cmd=_REGENERATE_CMD,
                check_cmd=_CHECK_CMD,
            ),
            "subsystems": data,
        }
        return json.dumps(payload, indent=2, sort_keys=True) + "\n"

    def output_paths(self) -> dict[str, Path]:
        return {
            "md": self.output_dir / "cognition_inventory.md",
            "json": self.output_dir / "cognition_inventory.json",
        }
