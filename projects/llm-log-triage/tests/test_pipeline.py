"""End-to-end: generate -> ingest -> detect -> summarize against a temp DB."""

import os

from src import generate_logs, pipeline, db as db_mod


def _make_logs(tmp_path, rows=400, seed=7):
    recs = generate_logs.generate(rows=rows, seed=seed)
    p = tmp_path / "logs.jsonl"
    generate_logs.write_jsonl(recs, str(p))
    return str(p)


def test_full_pipeline_flags_attacks(tmp_path):
    logs = _make_logs(tmp_path)
    db = str(tmp_path / "triage.db")
    report = pipeline.run_full(db, logs)

    an = report["analysis"]
    assert an["total_events"] > 0
    assert an["flagged_events"] > 0
    assert an["total_findings"] > 0
    # The generator injects every attack class, so the headline OWASP
    # categories must all show up.
    cats = set(an["by_owasp"])
    for required in ("LLM01:2025", "LLM02:2025", "LLM05:2025", "LLM07:2025"):
        assert required in cats, f"missing {required} in {cats}"


def test_ingest_reports_data_quality(tmp_path):
    logs = _make_logs(tmp_path)
    db = str(tmp_path / "triage.db")
    stats = pipeline.ingest(db, logs)
    assert stats["inserted"] > 0
    # The messy generator guarantees some unparseable timestamps & synth ids.
    assert stats["unparseable_timestamps"] > 0
    assert stats["synthesized_ids"] > 0


def test_detection_is_idempotent(tmp_path):
    logs = _make_logs(tmp_path)
    db = str(tmp_path / "triage.db")
    pipeline.ingest(db, logs)
    first = pipeline.analyze(db)["total_findings"]
    second = pipeline.analyze(db)["total_findings"]
    assert first == second, "re-running detection must not accumulate duplicates"


def test_analysis_sql_files_execute(tmp_path):
    logs = _make_logs(tmp_path)
    db = str(tmp_path / "triage.db")
    pipeline.run_full(db, logs)

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    analysis_dir = os.path.join(here, "sql", "analysis")
    conn = db_mod.connect(db)
    try:
        sql_files = sorted(f for f in os.listdir(analysis_dir) if f.endswith(".sql"))
        assert sql_files, "no analysis queries found"
        for fname in sql_files:
            cols, rows = db_mod.run_analysis_query(conn, os.path.join(analysis_dir, fname))
            assert isinstance(cols, list)  # query ran without error
    finally:
        conn.close()


def test_load_jsonl_tolerates_bad_lines(tmp_path):
    p = tmp_path / "messy.jsonl"
    p.write_text('{"content": "ok", "role": "user"}\n\nnot json at all\n{"content": "ok2"}\n')
    recs = pipeline.load_jsonl(str(p))
    # blank line skipped; bad line preserved as raw content; 3 records total
    assert len(recs) == 3
    assert any(r.get("_parse_error") for r in recs)


def test_format_report_renders(tmp_path):
    logs = _make_logs(tmp_path)
    db = str(tmp_path / "triage.db")
    report = pipeline.run_full(db, logs)
    text = pipeline.format_report(report)
    assert "LLM LOG TRIAGE REPORT" in text
    assert "by OWASP LLM category" in text
