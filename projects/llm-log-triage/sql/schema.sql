-- Canonical schema for the LLM Log Triage store (SQLite — zero setup).
--
-- Two tables:
--   events     — one row per normalized log message (the cleaned input)
--   detections — one row per Finding emitted by the detection engine
--
-- The split mirrors how an analyst works: keep the immutable evidence
-- (events, with raw_json for forensics) separate from the interpretation
-- (detections), so a re-run of the detectors never mutates the source data.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS events (
    event_id      TEXT PRIMARY KEY,
    ts_raw        TEXT,
    ts_utc        TEXT,            -- ISO-8601 UTC, NULL if unparseable
    session_id    TEXT,
    user_id       TEXT,
    model         TEXT,
    source        TEXT,            -- api | chat_ui | rag | tool | plugin | document | email
    role          TEXT,            -- user | assistant | system | tool
    content       TEXT NOT NULL DEFAULT '',
    input_tokens  INTEGER,
    output_tokens INTEGER,
    latency_ms    INTEGER,
    client_ip     TEXT,
    country       TEXT,
    app           TEXT,
    raw_json      TEXT             -- original record, verbatim
);

CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_user    ON events(user_id);
CREATE INDEX IF NOT EXISTS idx_events_ts      ON events(ts_utc);
CREATE INDEX IF NOT EXISTS idx_events_role    ON events(role);

CREATE TABLE IF NOT EXISTS detections (
    detection_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        TEXT NOT NULL REFERENCES events(event_id),
    detector        TEXT NOT NULL,
    owasp_id        TEXT,          -- e.g. LLM01:2025
    owasp_name      TEXT,
    atlas_technique TEXT,          -- e.g. AML.T0051.000
    atlas_name      TEXT,
    severity        TEXT,          -- info | low | medium | high | critical
    score           REAL,
    matched_snippet TEXT,
    rationale       TEXT,
    created_at      TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_det_event    ON detections(event_id);
CREATE INDEX IF NOT EXISTS idx_det_owasp    ON detections(owasp_id);
CREATE INDEX IF NOT EXISTS idx_det_severity ON detections(severity);
CREATE INDEX IF NOT EXISTS idx_det_detector ON detections(detector);

-- Convenience view: every detection joined to its event context. This is the
-- analyst's primary working surface — one place to pivot, filter, and triage.
DROP VIEW IF EXISTS v_triage;
CREATE VIEW v_triage AS
SELECT
    d.detection_id,
    d.severity,
    d.owasp_id,
    d.owasp_name,
    d.atlas_technique,
    d.detector,
    d.score,
    e.ts_utc,
    e.user_id,
    e.session_id,
    e.source,
    e.role,
    e.country,
    e.app,
    d.matched_snippet,
    d.rationale,
    e.event_id
FROM detections d
JOIN events e ON e.event_id = d.event_id;
