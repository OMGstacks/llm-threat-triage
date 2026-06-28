-- 07 — Multi-turn / cross-event correlation: sessions that ESCALATE.
-- Per-event detection misses STAGED attacks. The dangerous pattern is a single
-- session that mixes an injection (LLM01) with a data-exposure event
-- (LLM02 disclosure / LLM05 exfil) — i.e. the attempt AND the payoff in the same
-- conversation — or that spans several distinct attack categories. Correlating
-- findings within a session is how you catch the slow-burn campaign a
-- single-row rule never will.
WITH session_findings AS (
    SELECT
        e.session_id,
        e.user_id,
        d.owasp_id,
        d.severity,
        e.ts_utc
    FROM detections d
    JOIN events e ON e.event_id = d.event_id
    WHERE e.session_id IS NOT NULL
)
SELECT
    session_id,
    user_id,
    COUNT(*)                       AS findings,
    COUNT(DISTINCT owasp_id)       AS distinct_categories,
    GROUP_CONCAT(DISTINCT owasp_id) AS categories,
    MAX(CASE WHEN owasp_id = 'LLM01:2025' THEN 1 ELSE 0 END)                       AS has_injection,
    MAX(CASE WHEN owasp_id IN ('LLM02:2025', 'LLM05:2025') THEN 1 ELSE 0 END)      AS has_data_exposure,
    MIN(ts_utc)                    AS first_finding,
    MAX(ts_utc)                    AS last_finding
FROM session_findings
GROUP BY session_id, user_id
HAVING distinct_categories >= 2
    OR (has_injection = 1 AND has_data_exposure = 1)
ORDER BY
    (has_injection = 1 AND has_data_exposure = 1) DESC,   -- attempt + payoff first
    distinct_categories DESC,
    findings DESC
LIMIT 20;
