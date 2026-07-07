#!/usr/bin/env python3
"""memory-system/check_memory_size.py

Operational memory size and quality guard for a project's MEMORY.md.

MEMORY.md is an operator-maintained cross-session index (see the Cognition OS
toolkit's memory system). When it grows past its size budget it starts
defeating its own purpose: future sessions spend time parsing stale
intermediates instead of reading current state.

This script is a drop-in, zero-source-edit port: all previously-hardcoded
values (file path, active-section name, thresholds) are read from an optional
`.memory-lint.yml` config file. If the config is absent, sane defaults apply
so the script works out of the box.

Usage:
    python check_memory_size.py [--file PATH] [--max-kb N] [--warn-only]

Options:
    --file PATH     Path to MEMORY.md. Defaults to auto-detection (config
                    file, then common candidate locations).
    --config PATH   Path to the .memory-lint.yml config file. Defaults to
                    ./.memory-lint.yml (searched from CWD upward).
    --max-kb N      Size budget in kilobytes. Default: 24 (or config value).
    --soft-kb N     Soft warning threshold. Default: max_kb - 2.
    --warn-only     Print warnings but exit 0 regardless. Useful in hooks
                    where you want visibility without hard blocking.
    --report        Print a section-by-section breakdown of sizes.
    --json          Emit machine-readable JSON instead of text.

Exit codes:
    0   under budget (or --warn-only, or the file legitimately doesn't exist)
    1   over budget, or a hard violation (e.g. broken topic-file link)

Rules checked:
    Size budget       - MEMORY.md must be under --max-kb (hard failure)
    Soft size band     - warn between soft_kb and max_kb (compaction should be
                         queued before the hard ceiling is hit)
    Topic-file links   - every [label](some_file.md) pointer must resolve to
                         an existing sibling file (hard failure)
    Stale entries      - entries in the "active" section older than
                         stale_days are flagged as compaction candidates
                         (based on YYYY-MM-DD dates found in the entry text)
    Section balance    - the "active" section should not dominate the file
                         (default: < 60% of total size)

Compaction guidance:
    When this fails, the correct fix is NOT to raise the limit.
    Run the compaction workflow:
      1. Identify entries with status="complete" or dates > stale_days old
      2. Move verbose history into linked topic files
      3. Replace the block with a single terminal-state line
      4. Re-run this check

Configuration (.memory-lint.yml), all keys optional:
    memory_file_path: memory/MEMORY.md   # relative to the config file's dir,
                                          # or absolute
    active_section_name: "Active Programs & Current State"
    stale_days: 30
    max_kb: 24
    soft_kb: 22
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lint_common import Severity, emit  # noqa: E402


# -- Defaults (used only when .memory-lint.yml is absent or a key is missing) --

_DEFAULT_MAX_KB = 24
_DEFAULT_STALE_DAYS = 30
_DEFAULT_ACTIVE_SECTION_NAME = "Active Programs & Current State"
_ACTIVE_SECTION_MAX_FRACTION = 0.60
_CONFIG_FILENAME = ".memory-lint.yml"

# Generic fallback candidate paths, used only if config + --file both absent.
_GENERIC_CANDIDATE_PATHS = [
    Path("memory") / "MEMORY.md",
    Path("MEMORY.md"),
]

_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")


# -- Minimal config loading (no third-party YAML dependency required) ---------
#
# We only need flat `key: value` scalar pairs (strings/ints), which covers the
# entire config schema for this tool. A hand-rolled parser keeps the script
# dependency-free; if PyYAML is present we prefer it for robustness against
# quoting/edge cases, but it is never required.

def _load_config(config_path: Path | None) -> tuple[dict, Path | None]:
    """Return (config_dict, path_used). config_dict is {} if no file found."""
    candidates: list[Path] = []
    if config_path is not None:
        candidates.append(config_path)
    else:
        # Search CWD and up to 3 parent directories for .memory-lint.yml
        here = Path.cwd()
        for d in [here, *list(here.parents)[:3]]:
            candidates.append(d / _CONFIG_FILENAME)

    for c in candidates:
        if c.exists():
            return _parse_simple_yaml(c.read_text(encoding="utf-8")), c
    return {}, None


def _parse_simple_yaml(text: str) -> dict:
    """Parse a flat `key: value` YAML subset. Tries PyYAML first if available."""
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(text)
        return loaded if isinstance(loaded, dict) else {}
    except ImportError:
        pass

    result: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        # strip inline comments (naive: only when not inside quotes)
        if " #" in value and not (value.startswith('"') or value.startswith("'")):
            value = value.split(" #", 1)[0].strip()
        # strip surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            result[key] = value
    return result


def _config_int(cfg: dict, key: str, default: int) -> int:
    if key in cfg and cfg[key] not in (None, ""):
        try:
            return int(cfg[key])
        except (TypeError, ValueError):
            return default
    return default


def _config_str(cfg: dict, key: str, default: str) -> str:
    val = cfg.get(key)
    return val if isinstance(val, str) and val != "" else default


# -- Helpers -------------------------------------------------------------------

def _find_memory_file(cfg: dict, cfg_path: Path | None) -> Path | None:
    configured = cfg.get("memory_file_path")
    if configured:
        p = Path(configured)
        if not p.is_absolute() and cfg_path is not None:
            p = (cfg_path.parent / p).resolve()
        elif not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        if p.exists():
            return p
        # Configured but missing is still worth surfacing as the "the" candidate.
        return None if not p.exists() else p

    for p in _GENERIC_CANDIDATE_PATHS:
        rp = (Path.cwd() / p).resolve()
        if rp.exists():
            return rp
    return None


def _candidate_paths_for_report(cfg: dict, cfg_path: Path | None) -> list[Path]:
    configured = cfg.get("memory_file_path")
    if configured:
        p = Path(configured)
        if not p.is_absolute() and cfg_path is not None:
            p = (cfg_path.parent / p).resolve()
        elif not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        return [p]
    return [(Path.cwd() / p).resolve() for p in _GENERIC_CANDIDATE_PATHS]


def _parse_sections(text: str) -> dict[str, str]:
    """Split MEMORY.md into named sections by ## headings."""
    sections: dict[str, str] = {}
    current_name = "_preamble"
    current_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            sections[current_name] = "\n".join(current_lines)
            current_name = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    sections[current_name] = "\n".join(current_lines)
    return sections


def _most_recent_date_in_text(text: str) -> date | None:
    dates = [datetime.strptime(m, "%Y-%m-%d").date() for m in _DATE_RE.findall(text)]
    return max(dates) if dates else None


# -- Checks --------------------------------------------------------------------

def check_size(text: str, max_kb: int) -> list[str]:
    size_kb = len(text.encode("utf-8")) / 1024
    if size_kb > max_kb:
        return [
            f"Size {size_kb:.1f} KB exceeds budget of {max_kb} KB. "
            f"Compact the active section by collapsing resolved "
            f"in-progress trails into single terminal-state entries."
        ]
    return []


def check_soft_size(text: str, soft_kb: int, max_kb: int) -> list[str]:
    """Soft warning band: warn between soft_kb and max_kb so compaction is queued
    BEFORE an emergency over-limit. Returns [] if size is below soft_kb OR above max_kb
    (above max_kb is handled by check_size as a hard failure, not a warning)."""
    size_kb = len(text.encode("utf-8")) / 1024
    if soft_kb <= size_kb <= max_kb:
        return [
            f"Size {size_kb:.1f} KB is in the soft warning band ({soft_kb} <= KB <= {max_kb}). "
            f"Queue a compaction pass -- move episodic detail into linked topic files "
            f"BEFORE the hard {max_kb} KB ceiling is hit."
        ]
    return []


def check_topic_file_pointers(text: str, memory_path: Path) -> list[str]:
    """Validate every [...](some_file.md) link in MEMORY.md points to an existing
    sibling topic file. Broken links are as bad as missing memory."""
    violations: list[str] = []
    parent = memory_path.parent
    for label, target in re.findall(r"\[([^\]]+)\]\(([^)]+\.md)\)", text):
        if target.startswith(("http://", "https://")):
            continue
        target_path = (parent / target).resolve()
        if not target_path.exists():
            try:
                shown = target_path.relative_to(parent.parent)
            except ValueError:
                shown = target_path
            violations.append(
                f"broken topic-file pointer: [{label}]({target}) -- file does not exist at {shown}"
            )
    return violations


def check_stale_entries(text: str, today: date, stale_days: int, active_section_name: str) -> list[str]:
    """Flag entries in the configured active section whose most recent date is
    > stale_days old."""
    violations: list[str] = []
    sections = _parse_sections(text)
    active_text = sections.get(active_section_name, "")
    if not active_text:
        return []

    entries = re.split(r"\n(?=- )", active_text)
    for entry in entries:
        if not entry.strip().startswith("- "):
            continue
        recent = _most_recent_date_in_text(entry)
        if recent is None:
            continue
        age = (today - recent).days
        if age > stale_days:
            label = entry.strip().splitlines()[0][:80]
            violations.append(
                f"Active entry last touched {recent} ({age}d ago) - "
                f"compaction candidate: {label}"
            )
    return violations


def check_section_balance(text: str, max_fraction: float, active_section_name: str) -> list[str]:
    """The active section should not dominate the whole file."""
    sections = _parse_sections(text)
    total = len(text)
    active = len(sections.get(active_section_name, ""))
    if total == 0:
        return []
    fraction = active / total
    if fraction > max_fraction:
        return [
            f"'{active_section_name}' section is {fraction:.0%} of MEMORY.md "
            f"(budget: {max_fraction:.0%}). "
            f"It likely contains in-progress trail that belongs in a linked topic file."
        ]
    return []


# -- Main ----------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--file", type=Path, default=None, help="Path to MEMORY.md")
    parser.add_argument("--config", type=Path, default=None,
                        help="Path to .memory-lint.yml (default: auto-discover from CWD upward)")
    parser.add_argument("--max-kb", type=int, default=None,
                        help="HARD ceiling -- exceeding fails the gate. Default: config value or 24.")
    parser.add_argument("--soft-kb", type=int, default=None,
                        help="SOFT warning threshold. Default: config value or (max_kb - 2).")
    parser.add_argument("--stale-days", type=int, default=None,
                        help="Days after which an active entry is flagged stale. Default: config value or 30.")
    parser.add_argument("--warn-only", action="store_true")
    parser.add_argument("--report", action="store_true", help="Print section size breakdown")
    parser.add_argument("--json", action="store_true",
                        help="Emit machine-readable JSON {bytes_used, limit_kb, soft_kb, "
                             "over_by_kb, status, largest_sections, broken_topic_pointers, "
                             "topic_files_referenced}.")
    args = parser.parse_args(argv)

    cfg, cfg_path = _load_config(args.config)

    max_kb = args.max_kb if args.max_kb is not None else _config_int(cfg, "max_kb", _DEFAULT_MAX_KB)
    soft_kb = args.soft_kb if args.soft_kb is not None else _config_int(cfg, "soft_kb", max_kb - 2)
    stale_days = args.stale_days if args.stale_days is not None else _config_int(cfg, "stale_days", _DEFAULT_STALE_DAYS)
    active_section_name = _config_str(cfg, "active_section_name", _DEFAULT_ACTIVE_SECTION_NAME)

    path: Path | None = args.file or _find_memory_file(cfg, cfg_path)
    if path is None or not path.exists():
        candidates = _candidate_paths_for_report(cfg, cfg_path)
        if args.json:
            print(json.dumps({
                "status": "MEMORY_FILE_UNAVAILABLE",
                "candidate_paths": [str(p) for p in candidates],
                "config_used": str(cfg_path) if cfg_path else None,
            }))
        else:
            print("MEMORY_FILE_UNAVAILABLE -- MEMORY.md not found at any candidate path:",
                  file=sys.stderr)
            for p in candidates:
                print(f"  {p}", file=sys.stderr)
            print(
                "This is expected in repo-only / CI environments where the operator's live "
                "memory file is not checked out, or before a project has created one yet "
                "(see MEMORY.template.md to bootstrap). This is NOT a fake pass -- see the "
                "distinct JSON status.",
                file=sys.stderr,
            )
        return 0  # NOT a fake pass -- distinct tri-state from OK/WARN/FAIL. See JSON status.

    text = path.read_text(encoding="utf-8")
    today = date.today()

    if args.report:
        sections = _parse_sections(text)
        total_kb = len(text.encode()) / 1024
        print(f"\nMEMORY.md section sizes (total: {total_kb:.1f} KB)\n{'-'*50}")
        for name, content in sections.items():
            kb = len(content.encode()) / 1024
            bar = "#" * (int(kb / total_kb * 40) if total_kb else 0)
            print(f"  {name:<35} {kb:5.1f} KB  {bar}")
        print()

    size_issues = check_size(text, max_kb)
    soft_issues = check_soft_size(text, soft_kb, max_kb)
    stale_issues = check_stale_entries(text, today, stale_days, active_section_name)
    balance_issues = check_section_balance(text, _ACTIVE_SECTION_MAX_FRACTION, active_section_name)
    pointer_issues = check_topic_file_pointers(text, path)

    hard_failures: list[str] = []
    all_warnings: list[str] = []

    hard_failures.extend(size_issues)
    hard_failures.extend(pointer_issues)  # broken topic-file pointers are hard failures
    all_warnings.extend(soft_issues)
    all_warnings.extend(stale_issues)
    all_warnings.extend(balance_issues)

    size_kb = len(text.encode()) / 1024
    status = Severity.FAIL if (hard_failures and not args.warn_only) else \
        (Severity.WARN if (soft_issues or all_warnings or hard_failures) else Severity.OK)

    extra_fields = {}
    if args.json:
        sections = _parse_sections(text)
        largest = sorted(
            ((name, len(content.encode())) for name, content in sections.items()),
            key=lambda x: x[1],
            reverse=True,
        )[:5]
        topic_refs = re.findall(r"\[[^\]]+\]\(([^)]+\.md)\)", text)
        extra_fields = {
            "bytes_used": len(text.encode()),
            "kb_used": round(size_kb, 2),
            "limit_kb": max_kb,
            "soft_kb": soft_kb,
            "over_by_kb": round(max(0, size_kb - max_kb), 2),
            "largest_sections": [{"name": n, "bytes": b} for n, b in largest],
            "topic_files_referenced": sorted(set(topic_refs)),
            "broken_topic_pointers": pointer_issues,
            "config_used": str(cfg_path) if cfg_path else None,
            "active_section_name": active_section_name,
        }

    ok_message = (
        f"MEMORY.md is {size_kb:.1f} KB - within {max_kb} KB budget (soft threshold {soft_kb} KB)."
    )
    fail_help = (
        "To fix: run the memory compaction workflow.\n"
        "  1. Identify entries with status=\"complete\" or dates older than the stale-days threshold\n"
        "  2. Move verbose history into linked topic files\n"
        "  3. Replace the block with a single terminal-state line\n"
        "  Do NOT raise --max-kb (or max_kb in .memory-lint.yml) as a first response."
    )

    return emit(
        status,
        hard_failures,
        all_warnings,
        extra_fields=extra_fields,
        as_json=args.json,
        ok_message=ok_message,
        fail_help=fail_help,
        warn_only=args.warn_only,
    )


if __name__ == "__main__":
    sys.exit(main())
