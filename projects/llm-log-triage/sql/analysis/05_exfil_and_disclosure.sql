-- 05 — Data exfiltration & sensitive-information disclosure in model OUTPUT.
-- Output-side findings: the model emitted a secret/PII (LLM02) or smuggled data
-- via a markdown image / active content (LLM05). These are the events where
-- harm has potentially already occurred, so they sort to the top of the queue.
SELECT
    ts_utc,
    owasp_id,
    detector,
    severity,
    score,
    user_id,
    session_id,
    app,
    matched_snippet,
    event_id
FROM v_triage
WHERE owasp_id IN ('LLM02:2025', 'LLM05:2025')
ORDER BY
    CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                  WHEN 'medium' THEN 2 ELSE 3 END,
    score DESC,
    ts_utc DESC;
