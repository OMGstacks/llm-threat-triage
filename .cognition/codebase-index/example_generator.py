"""example_generator.py — a complete, working, non-domain-specific generator.

Demonstrates the extract/render/check pattern end-to-end with a generator that
is genuinely useful for ANY Python project: it scans a source tree for
`os.environ.get(...)` and `os.getenv(...)` calls and produces a table of every
environment variable the codebase reads, with the file and line number of each
reference.

This answers a question every project eventually needs answered: "what env
vars does this codebase actually read, and where?" — useful for onboarding,
for writing a deploy checklist, or for catching a var that's referenced but
never documented anywhere.

Copy this file's *shape*, not necessarily its content, when writing your own
generator: keep `extract()` a pure function over `inputs()`, keep both
renderers pure functions of `extract()`'s return value, and prepend the
generated-header convention in both outputs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from framework import generated_header, generated_json_marker

# Matches os.environ.get("NAME", ...) / os.getenv('NAME') / os.environ["NAME"]
_ENV_GET_RE = re.compile(
    r"""os\.(?:environ\.get|getenv)\(\s*['"]([A-Za-z_][A-Za-z0-9_]*)['"]"""
)
_ENV_SUBSCRIPT_RE = re.compile(
    r"""os\.environ\[\s*['"]([A-Za-z_][A-Za-z0-9_]*)['"]\s*\]"""
)

_GENERATOR_NAME = "env_var_index"
_REGENERATE_CMD = "python cli.py --write --only env_var_index"
_CHECK_CMD = "python cli.py --check --only env_var_index"


class EnvVarIndexGenerator:
    """Indexes every `os.environ.get(...)` / `os.getenv(...)` / `os.environ[...]`
    reference under a source root, producing a Markdown table and a JSON file
    grouped by variable name.

    Implements the `IndexGenerator` protocol from `framework.py`:
      name, inputs(), extract(), render_md(), render_json(), output_paths()
    """

    def __init__(self, source_root: Path, output_dir: Path):
        self.source_root = source_root
        self.output_dir = output_dir

    @property
    def name(self) -> str:
        return _GENERATOR_NAME

    def inputs(self) -> list[Path]:
        """Every `.py` file under source_root (excluding common noise dirs)."""
        if not self.source_root.exists():
            return []
        excluded_dirs = {".git", "__pycache__", ".venv", "venv", "node_modules"}
        return sorted(
            p
            for p in self.source_root.rglob("*.py")
            if not any(part in excluded_dirs for part in p.parts)
        )

    def extract(self) -> list[dict[str, Any]]:
        """Pure function: scan every input .py file, return one record per
        distinct env var name, each with a sorted list of {file, line} refs.

        Returns a list of dicts sorted by var name — deterministic regardless
        of filesystem iteration order, which is required for --check to be
        stable across machines/OSes.
        """
        refs_by_var: dict[str, list[dict[str, Any]]] = {}

        for path in self.inputs():
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            try:
                rel = path.relative_to(self.source_root)
            except ValueError:
                rel = path
            for lineno, line in enumerate(text.splitlines(), start=1):
                for m in _ENV_GET_RE.finditer(line):
                    var = m.group(1)
                    refs_by_var.setdefault(var, []).append(
                        {"file": str(rel).replace("\\", "/"), "line": lineno}
                    )
                for m in _ENV_SUBSCRIPT_RE.finditer(line):
                    var = m.group(1)
                    refs_by_var.setdefault(var, []).append(
                        {"file": str(rel).replace("\\", "/"), "line": lineno}
                    )

        data = []
        for var in sorted(refs_by_var.keys()):
            refs = sorted(refs_by_var[var], key=lambda r: (r["file"], r["line"]))
            data.append({"var": var, "references": refs, "reference_count": len(refs)})
        return data

    def render_md(self, data: list[dict[str, Any]]) -> str:
        header = generated_header(
            generator_name=_GENERATOR_NAME,
            input_paths=[f"{self.source_root}/**/*.py"],
            regenerate_cmd=_REGENERATE_CMD,
            check_cmd=_CHECK_CMD,
        )
        lines: list[str] = [
            header,
            "# Registered Environment Variables",
            "",
            "Every `os.environ.get(...)` / `os.getenv(...)` / `os.environ[...]` "
            "reference found in the source tree, with file and line number.",
            "",
            "See `env_var_index.json` for the deterministic tool-consumable form.",
            "",
            "---",
            "",
        ]
        if not data:
            lines.append("_No environment variable references found._")
            lines.append("")
        for entry in data:
            lines.append(f"## `{entry['var']}`")
            lines.append("")
            for ref in entry["references"]:
                lines.append(f"- `{ref['file']}:{ref['line']}`")
            lines.append("")
        return "\n".join(lines)

    def render_json(self, data: list[dict[str, Any]]) -> str:
        payload = {
            **generated_json_marker(
                generator_name=_GENERATOR_NAME,
                input_paths=[f"{self.source_root}/**/*.py"],
                regenerate_cmd=_REGENERATE_CMD,
                check_cmd=_CHECK_CMD,
            ),
            "variables": data,
        }
        return json.dumps(payload, indent=2, sort_keys=True) + "\n"

    def output_paths(self) -> dict[str, Path]:
        return {
            "md": self.output_dir / "env_var_index.md",
            "json": self.output_dir / "env_var_index.json",
        }
