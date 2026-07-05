#!/usr/bin/env python3
"""
friction_render.py — render the JSONL friction log into a human-readable
Markdown view.

The JSONL log (friction_log.jsonl by default) is the SOURCE OF TRUTH.
This script's output is a GENERATED ARTIFACT — never hand-edit it; re-run
this script instead. See the header comment this script writes into its
own output for the same note, mirroring the "don't hand-edit generated
docs" convention used by codebase-index-style generated docs.

Usage:
    python friction_render.py [--log friction_log.jsonl] [--config threshold_config.yml] [--out FRICTION_DIARY.md]

If --config points at a missing file, the rollup's "review agrees?" column
degrades gracefully to "n/a (no config)" rather than failing the whole
render — rendering the diary should not hard-depend on a threshold config
being present, since read-and-skim is a more common operation than review.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Force UTF-8 stdout/stderr — see friction_cli.py for rationale (Windows
# console codepage safety).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

# Reuse the exact same read + threshold logic the CLI uses, so the rendered
# "review agrees?" column can never drift from what `friction_cli.py review`
# would itself report.
from friction_cli import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_LOG_PATH,
    ThresholdConfig,
    compute_build_eligible,
    load_threshold_config,
    read_log,
)

GENERATED_HEADER = """<!--
  GENERATED FILE — DO NOT HAND-EDIT.

  This file is rendered from {log_path} by friction_render.py.
  The JSONL log is the source of truth; this Markdown view is derived from
  it and will be silently overwritten the next time this script runs.

  To change diary content: edit entries via friction_cli.py (log / bump /
  promote), or edit {log_path} directly, then regenerate with:

      python friction_render.py --log {log_path} --out {out_path}

  Generated at: {generated_at}
-->

"""


def _try_load_config(config_path: Path) -> Optional[ThresholdConfig]:
    if not config_path.exists():
        return None
    try:
        return load_threshold_config(config_path)
    except SystemExit:
        return None


def _review_agreement(entry: dict[str, Any], config: Optional[ThresholdConfig]) -> str:
    if entry["status"] not in ("CANDIDATE", "QUALIFYING"):
        return "n/a"
    if config is None:
        return "n/a (no config)"
    recomputed_eligible = compute_build_eligible(entry, config)
    recomputed_status = "BUILD_ELIGIBLE" if recomputed_eligible else entry["status"]
    return "agrees" if recomputed_status == entry["status"] else f"DRIFT (formula says {recomputed_status})"


def render_rollup_table(entries: list[dict[str, Any]], config: Optional[ThresholdConfig]) -> str:
    active = [e for e in entries if e["status"] not in ("BUILT", "DISQUALIFIED")]
    if not active:
        return "_(no active — non-BUILT/non-DISQUALIFIED — entries)_\n"

    lines = [
        "| ID | Title | Status | Recurrence | Severity | Days span | Review agrees? |",
        "|---|---|---|---|---|---|---|",
    ]
    for e in active:
        try:
            days_span = (
                datetime.strptime(e["last_seen_date"], "%Y-%m-%d").date()
                - datetime.strptime(e["created_date"], "%Y-%m-%d").date()
            ).days
        except Exception:
            days_span = "?"
        lines.append(
            f"| {e['id']} | {e['title']} | {e['status']} | {e['recurrence_count']} | "
            f"{e['severity_signal']} | {days_span} | {_review_agreement(e, config)} |"
        )
    return "\n".join(lines) + "\n"


def render_entry_block(entry: dict[str, Any]) -> str:
    lines = []
    lines.append(f"### {entry['id']} — {entry['title']}")
    lines.append("")
    lines.append(f"- **Status:** {entry['status']}")
    lines.append(f"- **Created:** {entry['created_date']}  |  **Last seen:** {entry['last_seen_date']}")
    lines.append(f"- **Affected component:** {entry['affected_component']}")
    domain_ext = entry.get("domain_extensions") or {}
    if domain_ext:
        ext_str = ", ".join(f"`{k}={v}`" for k, v in domain_ext.items())
        lines.append(f"- **Domain extensions:** {ext_str}")
    lines.append(f"- **Recurrence count:** {entry['recurrence_count']}  "
                 f"(**recurrence signal:** {entry['recurrence_signal']})")
    lines.append(f"- **Severity signal:** {entry['severity_signal']}")
    lines.append(f"- **Golden-rule answer** (\"would this recur next week if nothing changed?\"): "
                 f"{entry['golden_rule_answer']}")
    lines.append("")
    lines.append(f"**Manual procedure today:** {entry['manual_procedure']}")
    lines.append("")
    lines.append(f"**Proposed fix:** {entry['proposed_fix']}")
    lines.append("")
    lines.append(f"**Falsifiability gate:** {entry['falsifiability_gate']}")
    lines.append("")

    evidence = entry.get("evidence_log") or []
    if evidence:
        lines.append("**Evidence log:**")
        for ev in evidence:
            lines.append(f"- {ev['date']}: {ev['note']}")
        lines.append("")

    if entry["status"] == "BUILT":
        lines.append(f"**Built as:** {entry.get('built_as') or '_(missing)_'}  "
                     f"|  **Built PR:** {entry.get('built_pr') or '_(missing)_'}")
        pbc = entry.get("post_build_check")
        if pbc is None:
            lines.append("")
            lines.append(
                "> ⚠️ **No post_build_check recorded.** A BUILT entry without a "
                "post_build_check is a schema smell — BUILT should not be a "
                "permanent unverified end-state. Add one via a follow-up edit."
            )
        else:
            result = pbc.get("result")
            result_str = result if result is not None else "_(pending)_"
            lines.append("")
            lines.append(
                f"**Post-build check:** due {pbc.get('due_date')} — {pbc.get('procedure')} "
                f"— result: {result_str}"
            )
        lines.append("")

    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def render_markdown(
    entries: list[dict[str, Any]],
    log_path: Path,
    out_path: Path,
    config: Optional[ThresholdConfig],
    generated_at: str,
) -> str:
    parts = []
    parts.append(
        GENERATED_HEADER.format(
            log_path=log_path.name, out_path=out_path.name, generated_at=generated_at
        )
    )
    parts.append("# Operational Friction Diary\n")
    parts.append(
        f"Source of truth: `{log_path.name}` ({len(entries)} total entries). "
        "This view is regenerated, not hand-maintained.\n"
    )

    parts.append("\n## Rollup — active entries (non-BUILT, non-DISQUALIFIED)\n")
    parts.append(render_rollup_table(entries, config))

    status_counts: dict[str, int] = {}
    for e in entries:
        status_counts[e["status"]] = status_counts.get(e["status"], 0) + 1
    counts_str = ", ".join(f"{k}={v}" for k, v in sorted(status_counts.items()))
    parts.append(f"\n_Status counts: {counts_str}_\n")

    parts.append("\n## All entries\n")
    for entry in entries:
        parts.append(render_entry_block(entry))

    return "\n".join(parts)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render the JSONL friction log to Markdown.")
    parser.add_argument("--log", default=DEFAULT_LOG_PATH, help=f"path to JSONL log (default: {DEFAULT_LOG_PATH})")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help=f"path to threshold config (default: {DEFAULT_CONFIG_PATH})")
    parser.add_argument("--out", default="FRICTION_DIARY.md", help="output Markdown path (default: FRICTION_DIARY.md)")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    log_path = Path(args.log)
    config_path = Path(args.config)
    out_path = Path(args.out)

    entries = read_log(log_path)
    config = _try_load_config(config_path)

    generated_at = datetime.now().isoformat(timespec="seconds")
    md = render_markdown(entries, log_path, out_path, config, generated_at)

    out_path.write_text(md, encoding="utf-8", newline="\n")
    print(f"Rendered {len(entries)} entries from {log_path} -> {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
