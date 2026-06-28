-- 06 — Unbounded Consumption (OWASP LLM10:2025) signal, computed in pure SQL.
-- There is no per-event regex for this class — it only shows up in AGGREGATE:
-- a session burning far more tokens / making far more calls / running far hotter
-- than the population norm is the fingerprint of denial-of-wallet, a runaway
-- agent loop, or systematic model-extraction probing. This is the "anomaly
-- detection with SQL" the JD calls for.
WITH per_session AS (
    SELECT
        session_id,
        user_id,
        COUNT(*)                                                        AS events,
        SUM(COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0))     AS total_tokens,
        ROUND(AVG(COALESCE(latency_ms, 0)), 0)                          AS avg_latency_ms,
        MAX(COALESCE(latency_ms, 0))                                    AS max_latency_ms
    FROM events
    WHERE session_id IS NOT NULL
    GROUP BY session_id, user_id
),
pop AS (
    SELECT
        AVG(total_tokens) AS mean_tokens,
        AVG(events)       AS mean_events
    FROM per_session
)
SELECT
    p.session_id,
    p.user_id,
    p.events,
    p.total_tokens,
    p.avg_latency_ms,
    p.max_latency_ms,
    ROUND(p.total_tokens * 1.0 / NULLIF((SELECT mean_tokens FROM pop), 0), 1) AS tokens_vs_mean,
    ROUND(p.events       * 1.0 / NULLIF((SELECT mean_events FROM pop), 0), 1) AS calls_vs_mean
FROM per_session p
WHERE p.total_tokens > 2.0 * (SELECT mean_tokens FROM pop)
   OR p.events       > 3.0 * (SELECT mean_events FROM pop)
ORDER BY p.total_tokens DESC
LIMIT 20;
