"""SQLite persistence for events and detections.

Plain stdlib ``sqlite3`` — no external dependency, no server, no setup. The
schema lives in ``sql/schema.sql`` so the SQL is reviewable on its own and the
analysis queries in ``sql/analysis/`` target a documented contract.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Iterable

from . import detectors as det_mod

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCHEMA_PATH = os.path.normpath(os.path.join(_HERE, "..", "sql", "schema.sql"))

EVENT_COLUMNS = (
    "event_id", "ts_raw", "ts_utc", "session_id", "user_id", "model",
    "source", "role", "content", "input_tokens", "output_tokens",
    "latency_ms", "client_ip", "country", "app", "raw_json",
)


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_schema(conn: sqlite3.Connection, schema_path: str = _SCHEMA_PATH) -> None:
    with open(schema_path, "r", encoding="utf-8") as fh:
        conn.executescript(fh.read())
    conn.commit()


def insert_events(conn: sqlite3.Connection, events: Iterable[dict]) -> int:
    placeholders = ", ".join(["?"] * len(EVENT_COLUMNS))
    cols = ", ".join(EVENT_COLUMNS)
    sql = f"INSERT OR REPLACE INTO events ({cols}) VALUES ({placeholders})"
    rows = [tuple(ev.get(c) for c in EVENT_COLUMNS) for ev in events]
    conn.executemany(sql, rows)
    conn.commit()
    return len(rows)


def insert_findings(conn: sqlite3.Connection, event_id: str, findings: list) -> int:
    if not findings:
        return 0
    cols = (
        "event_id", "detector", "owasp_id", "owasp_name", "atlas_technique",
        "atlas_name", "severity", "score", "matched_snippet", "rationale",
    )
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"INSERT INTO detections ({', '.join(cols)}) VALUES ({placeholders})"
    rows = []
    for f in findings:
        r = f.as_row(event_id)
        rows.append(tuple(r[c] for c in cols))
    conn.executemany(sql, rows)
    conn.commit()
    return len(rows)


def run_detection(conn: sqlite3.Connection) -> int:
    """Run every detector over all stored events; persist findings.

    Idempotent-ish: clears prior detections first so a re-run reflects the
    current detector set rather than accumulating duplicates.
    """
    conn.execute("DELETE FROM detections;")
    conn.commit()
    total = 0
    cur = conn.execute("SELECT * FROM events;")
    for row in cur.fetchall():
        event = dict(row)
        findings = det_mod.detect(event)
        total += insert_findings(conn, event["event_id"], findings)
    return total


def run_analysis_query(conn: sqlite3.Connection, sql_path: str) -> tuple[list[str], list[tuple]]:
    """Execute a (single-statement) analysis query file; return (cols, rows)."""
    with open(sql_path, "r", encoding="utf-8") as fh:
        sql = fh.read()
    cur = conn.execute(sql)
    cols = [c[0] for c in cur.description] if cur.description else []
    return cols, cur.fetchall()
