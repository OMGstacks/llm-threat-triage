"""End-to-end triage pipeline: messy JSONL -> normalized DB -> detections -> report.

This is the spine the CLI drives. Each step is a plain function so it can be
unit-tested and reused (e.g. from a notebook) without the CLI.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Optional

from . import db as db_mod
from . import detectors as det_mod
from . import normalize as norm_mod


def load_jsonl(path: str) -> list[dict]:
    """Read JSONL, tolerating blank lines and the occasional corrupt row."""
    records: list[dict] = []
    bad = 0
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                bad += 1
                records.append({"content": line, "_parse_error": True})
    if bad:
        print(f"  warning: {bad} line(s) were not valid JSON (kept as raw content)")
    return records


def ingest(db_path: str, jsonl_path: str) -> dict:
    """Load -> normalize -> persist events. Returns data-quality stats."""
    raw = load_jsonl(jsonl_path)
    normalized = norm_mod.normalize_many(raw)
    conn = db_mod.connect(db_path)
    try:
        db_mod.init_schema(conn)
        n = db_mod.insert_events(conn, normalized)
    finally:
        conn.close()
    stats = norm_mod.normalization_stats(raw, normalized)
    stats["inserted"] = n
    return stats


def analyze(db_path: str) -> dict:
    """Run detectors over stored events; return a triage summary."""
    conn = db_mod.connect(db_path)
    try:
        total = db_mod.run_detection(conn)
        summary = summarize(conn)
    finally:
        conn.close()
    summary["total_findings"] = total
    return summary


def summarize(conn) -> dict:
    """Aggregate detections into the headline numbers an analyst reports."""
    def rows(sql, params=()):
        return conn.execute(sql, params).fetchall()

    by_severity = Counter()
    for r in rows("SELECT severity, COUNT(*) c FROM detections GROUP BY severity"):
        by_severity[r["severity"]] = r["c"]

    by_owasp = {}
    for r in rows(
        "SELECT owasp_id, owasp_name, COUNT(*) c FROM detections "
        "GROUP BY owasp_id, owasp_name ORDER BY c DESC"
    ):
        by_owasp[r["owasp_id"]] = {"name": r["owasp_name"], "count": r["c"]}

    top_users = [
        {"user_id": r["user_id"], "findings": r["c"]}
        for r in rows(
            "SELECT e.user_id, COUNT(*) c FROM detections d "
            "JOIN events e ON e.event_id = d.event_id "
            "WHERE e.user_id IS NOT NULL "
            "GROUP BY e.user_id ORDER BY c DESC LIMIT 5"
        )
    ]

    total_events = rows("SELECT COUNT(*) c FROM events")[0]["c"]
    flagged_events = rows(
        "SELECT COUNT(DISTINCT event_id) c FROM detections"
    )[0]["c"]

    # Per-event severity rollup: an event's verdict is the worst of its findings.
    per_event: dict = {}
    for r in rows("SELECT event_id, severity FROM detections"):
        per_event.setdefault(r["event_id"], []).append(r["severity"])
    events_by_severity = Counter(det_mod.max_severity(s) for s in per_event.values())

    return {
        "total_events": total_events,
        "flagged_events": flagged_events,
        "by_severity": dict(by_severity),
        "events_by_severity": dict(events_by_severity),
        "by_owasp": by_owasp,
        "top_users": top_users,
    }


def run_full(db_path: str, jsonl_path: str) -> dict:
    """ingest + analyze in one call. Returns a merged report."""
    ingest_stats = ingest(db_path, jsonl_path)
    analysis = analyze(db_path)
    return {"ingest": ingest_stats, "analysis": analysis}


def format_report(report: dict) -> str:
    """Render a human-readable triage report (what you'd paste into a ticket)."""
    ing = report.get("ingest", {})
    an = report.get("analysis", report)
    lines = []
    lines.append("=" * 64)
    lines.append("  LLM LOG TRIAGE REPORT")
    lines.append("=" * 64)
    if ing:
        lines.append("\nINGEST / DATA QUALITY")
        lines.append(f"  events ingested ........ {ing.get('inserted', '?')}")
        lines.append(f"  unparseable timestamps . {ing.get('unparseable_timestamps', 0)}")
        lines.append(f"  missing role ........... {ing.get('missing_role', 0)}")
        lines.append(f"  missing source ......... {ing.get('missing_source', 0)}")
        lines.append(f"  synthesized event ids .. {ing.get('synthesized_ids', 0)}")
    lines.append("\nDETECTION SUMMARY")
    lines.append(f"  total events ........... {an.get('total_events', '?')}")
    lines.append(f"  flagged events ......... {an.get('flagged_events', '?')}")
    lines.append(f"  total findings ......... {an.get('total_findings', '?')}")

    sev = an.get("by_severity", {})
    if sev:
        lines.append("\n  findings by severity:")
        for s in ("critical", "high", "medium", "low", "info"):
            if s in sev:
                lines.append(f"    {s:<9} {sev[s]}")

    ev_sev = an.get("events_by_severity", {})
    if ev_sev:
        lines.append("\n  flagged events by worst severity:")
        for s in ("critical", "high", "medium", "low", "info"):
            if s in ev_sev:
                lines.append(f"    {s:<9} {ev_sev[s]}")

    owasp = an.get("by_owasp", {})
    if owasp:
        lines.append("\n  by OWASP LLM category:")
        for oid, info in owasp.items():
            lines.append(f"    {oid:<12} {info['name']:<32} {info['count']}")

    top = an.get("top_users", [])
    if top:
        lines.append("\n  top flagged users:")
        for u in top:
            lines.append(f"    {str(u['user_id']):<14} {u['findings']} finding(s)")
    lines.append("=" * 64)
    return "\n".join(lines)
