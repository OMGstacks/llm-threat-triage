"""cc_spine CLI — the spine's runnable surface.

    python -m cc_spine.cli validate            # PR-1 scaffold gate
    python -m cc_spine.cli validate-sources    # source-registry freshness guard
    python -m cc_spine.cli check-ip            # IP-boundary support-span guard
    python -m cc_spine.cli ingest --source t.txt --source-doc-id demo [--out note.md]

Stdlib-only; no third-party dependencies.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

from . import ingest as ingest_mod
from . import ipboundary, scaffold_validate, sources

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REFERENCE = PROJECT_ROOT / "reference"
SPINE = PROJECT_ROOT / "spine"
DEFAULT_DICTIONARY = SPINE / "ingest" / "correction-dictionary.json"


def _report(title: str, failures: list[str]) -> int:
    if failures:
        print(f"FAIL {title} ({len(failures)} problem(s)):")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"OK   {title}")
    return 0


def cmd_validate(args) -> int:
    return scaffold_validate.main()


def cmd_validate_sources(args) -> int:
    today = datetime.date.fromisoformat(args.today) if args.today else None
    failures = sources.validate_registry_file(REFERENCE / "source-registry.json", today=today)
    return _report("source-registry freshness (source_freshness_guard)", failures)


def cmd_check_ip(args) -> int:
    failures = ipboundary.scan_facts(SPINE / "facts") + ipboundary.scan_notes(PROJECT_ROOT / "notes")
    return _report("IP-boundary support spans (ip_boundary_guard)", failures)


def cmd_ingest(args) -> int:
    dictionary = json.loads(Path(args.dictionary).read_text(encoding="utf-8"))
    domains = set(args.domains.split(",")) if args.domains else None
    note = ingest_mod.ingest(
        Path(args.source), args.source_doc_id, dictionary,
        source_tier=args.source_tier, outline_version=args.outline_version,
        reviewed_by=args.reviewed_by, status=args.status, domains=domains,
    )
    fm_problems = ingest_mod.validate_note_frontmatter(note)
    if fm_problems:
        print("FAIL produced note failed front-matter validation:", file=sys.stderr)
        for problem in fm_problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    if args.out:
        Path(args.out).write_text(note, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(note)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cc_spine.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="run the PR-1 scaffold gate").set_defaults(func=cmd_validate)

    p_src = sub.add_parser("validate-sources", help="source-registry freshness guard")
    p_src.add_argument("--today", help="override reference date (ISO), for testing")
    p_src.set_defaults(func=cmd_validate_sources)

    sub.add_parser("check-ip", help="IP-boundary support-span guard").set_defaults(func=cmd_check_ip)

    p_ing = sub.add_parser("ingest", help="extract + suggest corrections + build a note")
    p_ing.add_argument("--source", required=True, help="path to a .docx or .txt source")
    p_ing.add_argument("--source-doc-id", required=True, help="stable local id for provenance")
    p_ing.add_argument("--dictionary", default=str(DEFAULT_DICTIONARY))
    p_ing.add_argument("--source-tier", type=int, default=3)
    p_ing.add_argument("--outline-version", default="2025-10")
    p_ing.add_argument("--reviewed-by", default=None)
    p_ing.add_argument("--status", default="draft")
    p_ing.add_argument("--domains", default=None, help="comma-separated domain filter (e.g. D4,D5)")
    p_ing.add_argument("--out", default=None, help="write note here instead of stdout")
    p_ing.set_defaults(func=cmd_ingest)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
