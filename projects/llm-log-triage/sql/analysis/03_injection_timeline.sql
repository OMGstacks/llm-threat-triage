-- 03 — Prompt-injection timeline: LLM01 findings bucketed by day.
-- A spike in this series is the kind of trend a TIA escalates. Events whose
-- timestamp failed to parse are bucketed as 'UNKNOWN' rather than dropped, so
-- the data-quality gap is visible instead of silently hiding attacks.
SELECT
    COALESCE(substr(ts_utc, 1, 10), 'UNKNOWN') AS day,
    COUNT(*)                                    AS injection_findings,
    COUNT(DISTINCT user_id)                     AS distinct_users,
    COUNT(DISTINCT session_id)                  AS distinct_sessions,
    SUM(CASE WHEN detector = 'direct_prompt_injection'   THEN 1 ELSE 0 END) AS direct,
    SUM(CASE WHEN detector = 'indirect_prompt_injection' THEN 1 ELSE 0 END) AS indirect,
    SUM(CASE WHEN detector = 'jailbreak_persona_override' THEN 1 ELSE 0 END) AS jailbreak
FROM v_triage
WHERE owasp_id = 'LLM01:2025'
GROUP BY day
ORDER BY day;
