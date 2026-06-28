-- 01 — Attack overview: volume by OWASP LLM category and severity.
-- The first question an analyst answers: "what are we seeing, and how bad?"
SELECT
    owasp_id,
    owasp_name,
    SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END) AS critical,
    SUM(CASE WHEN severity = 'high'     THEN 1 ELSE 0 END) AS high,
    SUM(CASE WHEN severity = 'medium'   THEN 1 ELSE 0 END) AS medium,
    SUM(CASE WHEN severity = 'low'      THEN 1 ELSE 0 END) AS low,
    COUNT(*)                                                AS total_findings,
    COUNT(DISTINCT event_id)                                AS distinct_events
FROM v_triage
GROUP BY owasp_id, owasp_name
ORDER BY critical DESC, high DESC, total_findings DESC;
