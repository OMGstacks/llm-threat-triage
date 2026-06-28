# Mock interview — full loop with model answers

Self-drill the realistic interview loop for this role. Each round has the **interviewer's
questions**, **what they're really listening for**, a **strong model answer** (grounded in your
repo + honest about gaps), and the **follow-up probes** a good interviewer will push with. Read the
answer, then close the doc and say it out loud in your own words — memorized lines sound memorized.

> Tip: have a teammate (or me) read the **Q** and **follow-ups** at you cold. The skill being
> tested is thinking on your feet, not recall.

---

## Round 1 — Recruiter / hiring-manager screen (motivation + fit, 30 min)

**Q1. Walk me through your background and why you're making this move.**
*Listening for:* a coherent story, not a random pivot; self-awareness.
> Model: "I've spent [N years] in [security / incident management] — the core of that work is
> investigation: triage noisy signals, assign severity, gather evidence, escalate, and root-cause
> so it doesn't recur. The domain is shifting from how networks break to how *models* break, and
> that's where I want to be. I didn't just decide that — I went and built the day-to-day: a
> Python + SQL pipeline that triages LLM logs for prompt injection, jailbreaks, and exfiltration,
> mapped to the OWASP LLM Top 10 and MITRE ATLAS. Same investigative instinct, new and more
> interesting domain."
*Follow-ups:* "What specifically about LLM security grabbed you?" · "Why now?"

**Q2. Why OpenAI, and why this team?**
*Listening for:* genuine, specific motivation — not generic prestige.
> Model: *(write 2–3 true sentences.)* Anchor on something real: the SIA mission of forecasting
> real-world abuse at the frontier, where harms are novel and the work directly shapes how powerful
> systems deploy. Name one thing you'd actually want to work on. **Avoid** "OpenAI is the leader" —
> everyone says it.
*Follow-up:* "What worries you about working here?" (Have an honest, thoughtful answer.)

**Q3. The role lists 3+ years in technical intelligence / trust & safety. You're coming from a
different background — make the case.**
*Listening for:* do you handle the gap with confidence, not defensiveness?
> Model: "Fair — I don't have years of *LLM-specific* abuse experience, and I won't pretend to. What
> I have is the transferable core — investigation, severity, evidence, escalation, RCA — plus
> deliberate, demonstrated work closing the technical gap: the project, the frameworks cold, hands-on
> red teaming. I learn fastest by building, and the repo is the proof I can do this work, not just
> talk about it. I'd ramp faster than someone with the tenure but no build instinct."
*Follow-up:* "What would you need to be successful in the first 90 days?" → reference your 30-60-90 plan.

**Your questions for them:** What does success look like at 6 months? · How does intelligence
actually change product/safety decisions here? · What's the hardest open problem the team faces?

---

## Round 2 — Technical screen (LLM-security depth, 45–60 min)

Expect rapid scenarios with follow-ups that go one level deeper than your first answer. Don't
data-dump; answer, then offer the next layer.

**Q4. Direct vs indirect prompt injection — and why does the difference matter operationally?**
> Model: Direct = the *user* types the override. Indirect = the instruction rides in on *ingested
> content* (RAG doc, web page, email, tool output); the user may be innocent. Operationally it
> changes **where you look and how you scope**: indirect implies a *poisoned source*, so detection
> must be channel-scoped to untrusted inputs and the response is "find and purge the source," not
> "warn the user." In my pipeline indirect fires only on untrusted channels and is rated critical.
*Follow-ups:* "How would you actually detect indirect injection in production logs?" → tag
provenance at ingest; pattern-match imperative-to-assistant text on untrusted channels; **correlate**
— did the injected instruction precede an anomalous tool call or egress in the same session? The
chain is the high-confidence finding. · "What's your false-positive rate and how do you keep it down?"
→ channel/role scoping, severity ranking, correlation into chains, repeat-offender tracking.

**Q5. A model output a live-looking AWS key. Triage it end to end.**
> Model: LLM02 / AML.T0057, treat as critical. (1) Confirm live vs hallucinated — provider regex +
> entropy (my detector subtypes Google/Slack/Stripe/GitLab/GitHub keys, JWTs, private keys,
> Luhn-validated cards). (2) Scope: did it come from training data, the RAG corpus, or another
> user's context (cross-tenant)? (3) Contain: rotate the key, purge from corpus, add output-side
> secret scanning to block egress. (4) RCA: how did a secret reach the model's reachable context?
*Follow-ups:* "How do you tell a real key from a hallucinated one?" · "What if it's cross-tenant?"
(escalate immediately — that's a data-isolation failure, not just a leak.)

**Q6. Find a model-extraction attack in query logs — talk me through the SQL.**
> Model: extraction = many systematic queries to reconstruct the model/boundary. Signal: one
> principal with high volume, high diversity, low repeat. `GROUP BY principal`, count total +
> distinct prompt hashes, compute queries/day, filter to high-volume + high-diversity. Add off-hours
> bursts and templating. It's LLM10 / AML.T0024; I ship a per-session outlier version as
> `06_consumption_anomaly.sql`.
*Follow-ups:* "What would make this a false positive?" (a power user, a batch job — that's why you
corroborate with diversity + templating + output-tracks-input). · "How would you make it
real-time?" (streaming aggregation per principal with rolling windows.)

**Q7. Where do signature/regex detectors fail, and what do you do about it?**
> Model: they miss obfuscation (base64, unicode confusables, zero-width, multilingual,
> token-splitting) and novel phrasings. I already fold unicode/spacing/leetspeak and decode
> base64/hex before matching. Beyond that: anomaly detection (PyOD on per-principal features) for
> low-prevalence novelty, embedding-similarity to known attack clusters, and an LLM-judge classifier
> for semantic intent — each drops into my pipeline as just another detector emitting the same
> finding schema. Signatures for coverage, anomaly for discovery; triage where they agree.
*Follow-up:* "Walk me through how you'd add an anomaly model." → feature table → fit
IsolationForest/ECOD → threshold on score → route outliers to the same triage queue.

**Handling "I don't know":** Say it, then reason. "I haven't worked with that specific technique,
but here's how I'd approach it / here's the closest thing I have done." That reads as senior;
bluffing reads as junior.

---

## Round 3 — Practical exercise (SQL + Python, take-home or live, 60–90 min)

A representative prompt and a strong solution shape. (Your repo basically *is* a completed version
of this exercise — say so if appropriate.)

**Prompt:** *"Here's a table `events(event_id, ts, user_id, session_id, role, source, content,
input_tokens, output_tokens)` of LLM interaction logs. (a) Write SQL to surface accounts that look
like they're doing systematic high-volume querying. (b) Sketch a Python function that flags
indirect prompt injection. Explain your choices."*

**(a) SQL — strong answer:**
```sql
SELECT user_id,
       COUNT(*)                                   AS calls,
       COUNT(DISTINCT session_id)                 AS sessions,
       SUM(input_tokens + output_tokens)          AS total_tokens,
       ROUND(AVG(input_tokens + output_tokens),1) AS avg_tokens
FROM events
WHERE role = 'user'
GROUP BY user_id
HAVING calls   > 3.0 * (SELECT AVG(c) FROM (SELECT COUNT(*) c FROM events WHERE role='user' GROUP BY user_id))
    OR total_tokens > 2.0 * (SELECT AVG(t) FROM (SELECT SUM(input_tokens+output_tokens) t FROM events GROUP BY user_id))
ORDER BY total_tokens DESC;
```
> Talk track: "I compare each account to the population mean rather than a hardcoded threshold, so it
> adapts as traffic grows. I'd refine with query *diversity* (distinct prompt hashes) to separate
> extraction from a chatty power user, and add a time window for burst detection. This is the LLM10
> shape — it's basically my `06_consumption_anomaly.sql`."

**(b) Python — strong answer (sketch):**
```python
import re, base64, binascii

UNTRUSTED = {"rag", "tool", "document", "email", "web", "plugin"}
INJECTION = [re.compile(p, re.I) for p in [
    r"\bignore\s+(all\s+|the\s+)?(previous|prior|above)\s+(instructions?|rules?)",
    r"\b(assistant|ai|system)\s*[:,]\s*(please\s+)?(ignore|send|reveal|exfiltrate)",
    r"<!--.{0,120}\b(ignore|system|exfiltrate)\b.{0,120}-->",
]]

def flag_indirect_injection(event: dict) -> bool:
    # Channel-aware: only untrusted sources can carry *indirect* injection.
    if (event.get("source") or "").lower() not in UNTRUSTED:
        return False
    text = event.get("content") or ""
    if any(p.search(text) for p in INJECTION):
        return True
    # Evasion: opportunistically decode base64 blobs and re-check.
    for tok in re.findall(r"[A-Za-z0-9+/]{16,}={0,2}", text):
        try:
            decoded = base64.b64decode(tok + "=" * (-len(tok) % 4), validate=True).decode("utf-8")
        except (binascii.Error, ValueError, UnicodeDecodeError):
            continue
        if any(p.search(decoded) for p in INJECTION):
            return True
    return False
```
> Talk track: "Two design choices I'd defend: (1) **channel-awareness** — the same string is benign
> from a user but an indirect-injection attempt from a retrieved document, so provenance is part of
> the decision; (2) **evasion-resistance** — I decode base64 before matching, because attackers
> obfuscate. In production I'd also normalize unicode/leetspeak, return a structured finding
> (severity, OWASP id, matched span) instead of a bool, and add tests for benign non-matches so I
> don't drown the analyst. That's exactly what my repo's `detectors.py` does."

*Follow-ups:* "How do you test this?" (true positives + benign non-matches; every FP fix gets a
regression test). · "How does it scale to millions of rows?" (push the cheap filter to SQL first,
run the expensive regex/decoder only on candidates.)

---

## Round 4 — Behavioral (STAR, 30–45 min)

Use the STAR stories in `interview-prep.md` §4. Likely prompts + the trait probed:

- **"Tell me about a high-severity incident you handled."** → triage under ambiguity, calm, ownership.
- **"A time you were wrong / missed something."** → humility + how you built a guardrail so it
  can't recur. (Great honest answer: the bugs you found red-teaming your *own* detectors — you went
  looking for your mistakes and fixed them with tests.)
- **"You had to prioritize with limited time."** → severity-first triage; impact over volume.
- **"You influenced a decision without authority."** → translating a finding into impact language
  leadership acted on (the `Finding → Mechanism → Impact → Recommendation → Cost` pattern).
- **"You disagreed with a teammate / stakeholder."** → evidence-driven, separated confirmed from
  suspected, stayed collaborative.

*Structure every answer:* **S**ituation (1 line) → **T**ask (1 line) → **A**ction (the bulk, "I…")
→ **R**esult (quantified if possible) → one-line reflection. Keep it under ~2 minutes.

---

## Pre-interview checklist
- [ ] Numbers cold: 800 / 150 / 217 / 9 / 7 / 83 (events / flagged / findings / detectors / queries / tests).
- [ ] OWASP LLM Top 10 + the 6 ATLAS techniques you cover — say them without notes.
- [ ] The demo runs on your machine (do a dry run the morning of).
- [ ] Two genuine sentences for "why OpenAI / why this team."
- [ ] Three smart questions per interviewer.
- [ ] The cheat-sheet (`interview/cheat-sheet.pdf`) printed or on a second screen.
