"""Command-line interface for the LLM Log Triage toolkit.

    python -m src.cli generate  --rows 800 --out data/sample_logs.jsonl
    python -m src.cli ingest    --db triage.db --logs data/sample_logs.jsonl
    python -m src.cli detect    --db triage.db
    python -m src.cli report    --db triage.db
    python -m src.cli run       --db triage.db --logs data/sample_logs.jsonl   # all of the above
    python -m src.cli query     --db triage.db --sql sql/analysis/01_attack_overview.sql

`run` is the one-shot demo: it regenerates nothing, just ingests an existing
log file, runs detection, and prints the triage report.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import db as db_mod
from . import generate_logs
from . import pipeline


def _print_table(cols: list[str], rows: list) -> None:
    if not cols:
        print("(no result set)")
        return
    str_rows = [[("" if v is None else str(v)) for v in r] for r in rows]
    widths = [len(c) for c in cols]
    for r in str_rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], min(len(cell), 60))
    header = " | ".join(c.ljust(widths[i]) for i, c in enumerate(cols))
    print(header)
    print("-+-".join("-" * w for w in widths))
    for r in str_rows:
        print(" | ".join(cell[:60].ljust(widths[i]) for i, cell in enumerate(r)))
    print(f"\n({len(rows)} row{'s' if len(rows) != 1 else ''})")


def cmd_generate(args) -> int:
    recs = generate_logs.generate(rows=args.rows, seed=args.seed)
    generate_logs.write_jsonl(recs, args.out)
    print(f"Generated {len(recs)} messy records -> {args.out}")
    return 0


def cmd_ingest(args) -> int:
    stats = pipeline.ingest(args.db, args.logs)
    print(json.dumps(stats, indent=2))
    return 0


def cmd_detect(args) -> int:
    summary = pipeline.analyze(args.db)
    print(pipeline.format_report({"analysis": summary}))
    return 0


def cmd_report(args) -> int:
    conn = db_mod.connect(args.db)
    try:
        summary = pipeline.summarize(conn)
    finally:
        conn.close()
    print(pipeline.format_report({"analysis": summary}))
    return 0


def cmd_run(args) -> int:
    report = pipeline.run_full(args.db, args.logs)
    print(pipeline.format_report(report))
    return 0


def cmd_query(args) -> int:
    conn = db_mod.connect(args.db)
    try:
        cols, rows = db_mod.run_analysis_query(conn, args.sql)
    finally:
        conn.close()
    _print_table(cols, rows)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="llm-log-triage", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="generate messy synthetic logs")
    g.add_argument("--rows", type=int, default=800)
    g.add_argument("--out", default="data/sample_logs.jsonl")
    g.add_argument("--seed", type=int, default=7)
    g.set_defaults(func=cmd_generate)

    i = sub.add_parser("ingest", help="load + normalize logs into the DB")
    i.add_argument("--db", default="triage.db")
    i.add_argument("--logs", default="data/sample_logs.jsonl")
    i.set_defaults(func=cmd_ingest)

    d = sub.add_parser("detect", help="run detectors over stored events")
    d.add_argument("--db", default="triage.db")
    d.set_defaults(func=cmd_detect)

    r = sub.add_parser("report", help="print triage summary from the DB")
    r.add_argument("--db", default="triage.db")
    r.set_defaults(func=cmd_report)

    run = sub.add_parser("run", help="ingest + detect + report in one shot")
    run.add_argument("--db", default="triage.db")
    run.add_argument("--logs", default="data/sample_logs.jsonl")
    run.set_defaults(func=cmd_run)

    q = sub.add_parser("query", help="run a .sql analysis file and print results")
    q.add_argument("--db", default="triage.db")
    q.add_argument("--sql", required=True)
    q.set_defaults(func=cmd_query)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
