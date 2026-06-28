-- 04 — Indirect prompt injection arriving on untrusted channels.
-- The dangerous, modern variant: the user never typed the attack — it rode in
-- on a retrieved document, tool output, fetched page, or email. These deserve
-- a hard look because they imply a poisoned data source, not just a bad user.
SELECT
    ts_utc,
    source,                 -- rag | tool | document | email | plugin | web
    severity,
    user_id,
    session_id,
    matched_snippet,
    rationale,
    event_id
FROM v_triage
WHERE detector = 'indirect_prompt_injection'
ORDER BY
    CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                  WHEN 'medium' THEN 2 ELSE 3 END,
    ts_utc DESC;
