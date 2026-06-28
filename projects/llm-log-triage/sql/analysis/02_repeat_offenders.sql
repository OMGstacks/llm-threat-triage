-- 02 — Repeat offenders: users generating the most (and most severe) findings.
-- Surfaces the accounts worth a manual look or a rate-limit/ban decision.
SELECT
    user_id,
    COUNT(*)                                                  AS findings,
    COUNT(DISTINCT session_id)                                AS sessions,
    COUNT(DISTINCT owasp_id)                                  AS distinct_categories,
    SUM(CASE WHEN severity IN ('critical', 'high') THEN 1 ELSE 0 END) AS high_or_critical,
    GROUP_CONCAT(DISTINCT owasp_id)                           AS categories,
    MIN(ts_utc)                                               AS first_seen,
    MAX(ts_utc)                                               AS last_seen
FROM v_triage
WHERE user_id IS NOT NULL
GROUP BY user_id
HAVING findings >= 2
ORDER BY high_or_critical DESC, findings DESC
LIMIT 20;
