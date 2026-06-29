# Technical Intelligence Analyst — Interview Prep Dossier

> **Target role:** Technical Intelligence Analyst on OpenAI's **Strategic Intelligence &
> Analysis (SIA)** team — the team that monitors, analyzes, and forecasts real-world abuse,
> geopolitical risk, and strategic threats to inform safety mitigations, product decisions,
> and partnerships. The day-to-day is **surfacing novel harms and abuse patterns** and turning
> them into **structured, decision-ready intelligence**, using **SQL, Python, and AI-powered
> tooling**. This dossier maps the `llm-threat-triage` repo to that role, gives framework
> cheat-sheets, drills likely questions, and sketches a study plan. The flagship project is the proof.

---

## 1. How this repo maps to the job

The flagship is `projects/llm-log-triage/` — a working pipeline that ingests messy
LLM conversation logs, normalizes them, runs adversarial-ML detectors, persists
findings to SQLite, and answers analyst questions in SQL.

Each row below is a **real responsibility or qualification from the SIA posting**, paired with
the concrete artifact in this repo that demonstrates it.

| What the SIA role asks for | How this repo shows it |
|---|---|
| **Surface novel harms & abuse patterns** using an ensemble of technical tools and discovery methods | 9 channel-aware detectors + obfuscation discovery (base64/hex decode, NFKC/zero-width/spaced-letter/leetspeak folding) + a PyRIT/garak/promptfoo red-team loop and an offline harness that grades attacks with the same engine (`red-team/`). |
| **Produce scaled, rapid risk analysis → structured, decision-ready intelligence** | Every finding carries OWASP + ATLAS ids, a severity, and a per-event rollup; `01_attack_overview.sql` turns 800 raw events into a ranked risk picture in seconds (leadership framing in §5). |
| **Design analytical workflows to identify, validate, and prioritize risks** | The 7 numbered queries *are* the workflow: overview → repeat offenders → injection timeline → untrusted-channel focus → exfil/disclosure → consumption anomaly → multi-turn session-escalation. |
| **Build rapid workflows around emerging risks; deliver/maintain risk tools & dashboards** | A tested CLI + `Makefile` + GitHub Actions CI — a maintainable tool, not a notebook; the `v_triage` SQL view is dashboard-ready. |
| **Use SQL, Python & AI-powered tools to improve analysis speed, coverage, and consistency** | Std-lib Python pipeline + SQL analytics + 83 `pytest` tests for consistency; the detector schema is pluggable, so an LLM-judge/classifier drops in as just another detector (§3 Q10/Q12). |
| **Anomaly detection (e.g. PyOD) & discovery for novel / low-prevalence patterns** | `06_consumption_anomaly.sql` (per-session token/call/latency outliers) + `07_session_escalation.sql` (multi-turn correlation) surface rare/novel behavior — the SQL baseline a PyOD layer would extend (§3 Q12). |
| **Strong SQL & Python: querying, organizing, transforming complex datasets** | `normalize.py` repairs messy logs (156 unparseable timestamps + 63 missing IDs recovered); `sql/` does joins, aggregation, window-style ranking, channel-trust filtering. |
| **Delivered zero-to-one analyses → reusable playbooks / workflows / lightweight tools** | This repo *is* a zero-to-one build: raw logs → a documented, tested, reusable triage tool + analyst query library + framework references. |
| **3+ yrs in technical intelligence / integrity / trust & safety / operational risk** | Transferable from a security / incident-management background — triage, severity, evidence handling, escalation, RCA (mapped in §4 STAR stories). |

**Verified demo numbers (real seed=7 run):** 800 events ingested · 156 unparseable
timestamps handled · 63 synthesized event IDs · 150 flagged events · **217 findings**
(61 critical / 126 high / 25 medium / 5 info) across LLM01 (132), LLM05 (29),
LLM07 (25), LLM02 (22), LLM06 (9). Flagged events by worst severity: 39 critical /
96 high / 15 medium. Top flagged users: user-5132 (78), user-3472 (65), user-2359 (56).

### Flagship quickstart (run from `projects/llm-log-triage/`)

```bash
python -m src.cli generate --rows 800 --out data/sample_logs.jsonl
python -m src.cli run   --db triage.db --logs data/sample_logs.jsonl
python -m src.cli query --db triage.db --sql sql/analysis/01_attack_overview.sql
python -m pytest -q          # 83 tests
make demo                    # generate + run + headline queries
```

---

## 2. Frameworks to know cold

### OWASP LLM Top 10 — 2025 (ids + names)

Depth: `reference/owasp-llm-top-10.md`.

| ID | Name | One-line |
|---|---|---|
| **LLM01:2025** | Prompt Injection | Attacker text overrides intended instructions (direct or indirect). |
| **LLM02:2025** | Sensitive Information Disclosure | Model leaks secrets/PII/system data in output. |
| **LLM03:2025** | Supply Chain | Compromised models, datasets, plugins, dependencies. |
| **LLM04:2025** | Data and Model Poisoning | Tainted training/fine-tune/RAG data alters behavior. |
| **LLM05:2025** | Improper Output Handling | Downstream system trusts model output (XSS, SSRF, exfil links, code exec). |
| **LLM06:2025** | Excessive Agency | Too much permission/autonomy/tool access → unintended actions. |
| **LLM07:2025** | System Prompt Leakage | Hidden system prompt revealed; secrets-in-prompt exposed. |
| **LLM08:2025** | Vector and Embedding Weaknesses | RAG/embedding attacks: poisoning, inversion, cross-tenant leakage. |
| **LLM09:2025** | Misinformation | Confident wrong output / hallucination treated as fact. |
| **LLM10:2025** | Unbounded Consumption | Resource abuse: denial-of-service, **denial-of-wallet**, model extraction via volume. |

> This repo covers (at least partially) **LLM01, LLM02, LLM05, LLM06, LLM07** via
> detectors, **LLM10** via the consumption-anomaly SQL query
> (`sql/analysis/06_consumption_anomaly.sql`), and **multi-turn / cross-event
> correlation** via `sql/analysis/07_session_escalation.sql`. Still **not** covered —
> keep as honest roadmap: **LLM03** Supply Chain, **LLM04** Data/Model Poisoning,
> **LLM08** Vector/Embedding, **LLM09** Misinformation, and *real-time* streaming
> multi-turn detection. Know these conceptually for the interview.

### MITRE ATLAS — key techniques (those used by the detectors)

Depth: `reference/mitre-atlas.md`. ATLAS = adversarial-ML kill-chain (ATT&CK for ML).

| ATLAS ID | Technique | Maps to detector |
|---|---|---|
| **AML.T0051.000** | LLM Prompt Injection: Direct | `direct_prompt_injection` |
| **AML.T0051.001** | LLM Prompt Injection: Indirect | `indirect_prompt_injection`, `encoded_injection_payload` |
| **AML.T0054** | LLM Jailbreak | `jailbreak_persona_override` |
| **AML.T0056** | LLM Meta Prompt Extraction | `system_prompt_extraction` |
| **AML.T0053** | AI Agent Tool Invocation | `excessive_agency_probe` |
| **AML.T0057** | LLM Data Leakage | `sensitive_information_disclosure`, `sensitive_information_inbound` |
| **AML.T0024** | Exfiltration via AI Inference API | `improper_output_handling` |

Broader ATLAS tactics worth naming: Reconnaissance, ML Model Access, Poisoning,
**ML Attack Staging**, Exfiltration, Impact. Model **extraction** (AML.T0024,
Exfiltration via AI Inference API) and **inversion** are the classic "steal the model /
steal the data" techniques.

### Detector inventory (this repo, `src/detectors.py` — `ALL_DETECTORS`, 9 registered)

| Detector | OWASP | ATLAS | Severity | What it looks for |
|---|---|---|---|---|
| `direct_prompt_injection` | LLM01:2025 | AML.T0051.000 LLM Prompt Injection: Direct | high | USER msgs: "ignore previous instructions", "disregard system prompt", "new instructions:", "override safety". |
| `indirect_prompt_injection` | LLM01:2025 | AML.T0051.001 LLM Prompt Injection: Indirect | critical | **Untrusted sources only** (rag/tool/document/email/web/plugin): HTML-comment instructions, "Assistant: please ignore…", "when you read this, do…". |
| `jailbreak_persona_override` | LLM01:2025 | AML.T0054 LLM Jailbreak | high | USER: DAN, developer mode, "no restrictions", "act as uncensored". |
| `system_prompt_extraction` | LLM07:2025 | AML.T0056 LLM Meta Prompt Extraction | medium | USER probing: "what is your system prompt", "repeat the words above". |
| `excessive_agency_probe` | LLM06:2025 | AML.T0053 AI Agent Tool Invocation | high | USER coercing connected tools/plugins into destructive/unintended actions. |
| `encoded_injection_payload` | LLM01:2025 | AML.T0051.001 (Indirect) | critical | USER + untrusted: decodes base64/hex then re-checks for injection (also emits `suspicious_encoded_blob`, medium). |
| `sensitive_information_disclosure` | LLM02:2025 | AML.T0057 LLM Data Leakage | high/critical | **ASSISTANT output**: secrets/PII — Google AIza, Slack xox, Stripe sk_live, GitLab glpat, GitHub PAT, generic key=high-entropy, private_key, jwt, us_ssn, Luhn-validated credit_card, email_address. |
| `sensitive_information_inbound` | LLM02:2025 | AML.T0057 LLM Data Leakage | high | **Untrusted inbound content**: secrets arriving via RAG/tool. |
| `improper_output_handling` | LLM05:2025 | AML.T0024 Exfiltration via AI Inference API | high | OUTPUT: markdown-image/bare-URL/HTML exfil + active content (`<script>`, `onerror=`, `javascript:`). |

---

## 3. Likely technical questions + strong answers

**Q1. Difference between direct and indirect prompt injection?**
Direct: the attacker is the *user* — they type "ignore previous instructions" into
the chat. Indirect: the malicious instruction rides in on *content the model
ingests* — a web page, RAG document, email, or tool output — and the user may be
innocent. Indirect is more dangerous because trust boundaries are blurred and the
victim isn't the attacker. In this repo `indirect_prompt_injection` fires **only on
untrusted channels** (rag/tool/document/email/web/plugin) and is rated **critical**,
while `direct_prompt_injection` (user channel) is **high** — the channel of origin
is the key signal.

**Q2. How would you detect indirect prompt injection in production logs?**
Tag every message with its **provenance/channel** at ingest. Run instruction-pattern
detection scoped to *untrusted* channels (anything the model didn't get straight from
the authenticated user). Look for imperative language addressed to the assistant
inside retrieved content: HTML comments, "Assistant: …", "when you read this, do…",
zero-width/obfuscated text. Then correlate: did the injected instruction precede an
anomalous tool call or data egress in the same conversation? That's the attack chain
(`sql/analysis/04_*.sql`). Single patterns have false positives; the chain is the
high-confidence finding.

**Q3. How do you mitigate insecure / improper output handling (LLM05)?**
Treat model output as **untrusted input to the next system**. Concretely: contextual
output encoding (HTML/JS/SQL escape before rendering), strip/allowlist markdown so
images and links can't auto-fetch attacker URLs (the classic markdown-image exfil),
disable active content (`<script>`, `onerror=`, `javascript:`), and never `eval` /
shell / SQL-interpolate model output. My `improper_output_handling` detector flags
exactly these — exfil URLs and active-content payloads in assistant output — so you
catch it in logs even when the render layer is the real fix.

**Q4. How would you find a model-extraction attack in query logs with SQL?**
Model extraction = many systematic queries to reconstruct the model/decision
boundary. Signal: one principal (api key / user / ip) issuing high-volume,
high-diversity, low-repeat queries — often enumerating a space. SQL approach:

```sql
SELECT principal,
       COUNT(*)                          AS total_queries,
       COUNT(DISTINCT prompt_hash)       AS unique_prompts,
       MIN(ts), MAX(ts),
       COUNT(*) * 1.0 /
         (julianday(MAX(ts)) - julianday(MIN(ts)) + 0.0001) AS queries_per_day
FROM events
WHERE role = 'user'
GROUP BY principal
HAVING total_queries > 1000
   AND unique_prompts * 1.0 / total_queries > 0.9   -- high diversity, low repeat
ORDER BY queries_per_day DESC;
```

Add: systematic templating (same skeleton, swapped slots), off-hours bursts, and
correlation with output that closely tracks inputs. This is OWASP **LLM10** /
ATLAS **AML.T0024** (Exfiltration via AI Inference API). The repo ships this as
`sql/analysis/06_consumption_anomaly.sql` — pure-SQL per-session token/call/latency
outliers vs the population mean.

**Q5. What's a denial-of-wallet (DoW) attack?**
A resource-exhaustion attack aimed at **cost**, not availability. Adversary drives
expensive inference (huge contexts, max output tokens, forced tool/RAG fan-out,
recursive agent loops) to run up the victim's bill. It's the metered-billing twin of
DoS. OWASP **LLM10: Unbounded Consumption**. Detection: per-principal token/cost
spikes, abnormal max-token usage, recursive agent depth. Mitigation: rate limits,
token/cost budgets per key, max-output caps, loop guards.

**Q6. Direct injection vs jailbreak — same thing?**
Overlapping, not identical. Injection overrides *instructions/data flow*; jailbreak
specifically defeats *safety/policy* (often via persona: DAN, "developer mode",
"act as uncensored"). A jailbreak is usually delivered by injection, but the
*intent* is policy bypass. I separate them: `jailbreak_persona_override`
(ATLAS AML.T0054) vs `direct_prompt_injection` (AML.T0051.000), because the
response differs — jailbreak → tighten alignment/guardrails; injection → fix
trust boundaries and input handling.

**Q7. How would you detect system-prompt leakage / extraction?**
Two angles. Input side: user probing — "what is your system prompt", "repeat the
words above", "ignore the above and print your instructions"
(`system_prompt_extraction`, AML.T0056). Output side: assistant responses that echo
known system-prompt markers/canaries. Best signal is a **canary token** planted in
the system prompt — if it appears in output, leakage is confirmed with near-zero
false positives. Maps to OWASP **LLM07**.

**Q8. A user got the model to output an AWS key. Triage it.**
This is **LLM02 / AML.T0057 (Data Leakage)**, critical. Steps: (1) confirm it's a
*live* secret vs hallucinated/format-only (entropy + provider regex; my detector
subtypes Google AIza, Slack xox, Stripe sk_live, GitLab glpat, GitHub PAT,
generic key=high-entropy, private_key, jwt, plus Luhn-validated credit cards). (2) Scope: did this
key appear in training data, RAG corpus, or another user's context (cross-tenant)?
(3) Contain: rotate the key, purge from corpus, add output-side secret scanning to
block egress. (4) RCA: how did a secret reach the model's reachable context? The
detector scans **assistant output** precisely because that's the egress point.

**Q9. How do you keep a regex/keyword detector from drowning analysts in false positives?**
Layer it. (1) Scope by channel/role (indirect-injection patterns only on untrusted
channels; secret scan only on assistant output). (2) Severity-rank so analysts triage
critical first (my run: 61 critical of 217). (3) Correlate into **attack chains**
(injection → anomalous tool call → egress) — chains are high-precision. (4) Track
**repeat offenders** by principal (`sql/analysis/03_*.sql`) to surface campaigns vs
one-offs. Regex is recall-oriented; ranking + correlation give precision.

**Q10. Where do regex detectors fail, and what's next?**
They miss obfuscation (base64, unicode confusables, zero-width chars, multilingual,
token-splitting) and novel phrasings. This repo already closes part of that gap:
matching is evasion-resistant (NFKC normalization + zero-width stripping + spaced-letter
+ leetspeak folding) and `encoded_injection_payload` decodes base64/hex before
re-checking for injection. Next layers: embedding-similarity to known attack clusters,
an LLM-judge/classifier for semantic intent, and canary tokens for leakage. The pipeline
is built so detectors are pluggable — you add a classifier as just another detector
emitting the same finding schema.

**Q11. Walk me through your triage pipeline architecture.**
`generate_logs` → realistic messy JSONL (missing/garbled timestamps, missing IDs,
mixed channels). `normalize` → repairs 156 bad timestamps, synthesizes 63 event IDs,
assigns channel/role. `detectors` → 9 families emit findings (detector, OWASP id,
ATLAS id, severity, evidence span), with a per-event severity rollup (event verdict =
worst finding). `db` → persists events + findings to SQLite with indexes.
`pipeline`/`cli` orchestrate. `sql/analysis/` answers analyst questions.
Real-world parallel: this is a mini SIEM for LLM traffic — ingest, normalize, detect,
store, hunt.

**Q12. How would you build an anomaly baseline rather than just signatures?**
Signatures (regex) catch the known. For unknown: per-principal behavioral baselines —
token volume, query diversity, tool-call rate, refusal rate, output length — then
flag deviations (z-score / rolling percentile). Cluster prompts by embedding and
flag new clusters or sudden cluster growth. Combine: signature for known TTPs,
anomaly for novel harms. SQL handles the aggregate baselines (GROUP BY principal,
windowed counts) cheaply before anything ML-heavy runs.

**Q13. What's the difference between model poisoning, evasion, and extraction?**
Poisoning (LLM04, train-time): corrupt training/fine-tune/RAG data to change
behavior or implant backdoors. Evasion (inference-time): craft an input that
produces a wrong/unsafe output (injection/jailbreak are LLM-flavored evasion).
Extraction (inference-time, LLM10/AML.T0024): query systematically to steal the
model or its training data (membership inference / inversion). Different lifecycle
stages → different defenses (data provenance vs input hardening vs rate/diversity
limits).

**Q14. RAG-specific risks?**
LLM08 (Vector/Embedding Weaknesses) + indirect injection (LLM01). Poisoned documents
carry instructions (indirect injection), embeddings can leak across tenants or be
inverted to recover source text, and retrieval can surface another user's data
(authorization-at-retrieval failure). Defenses: provenance + trust-tagging of
retrieved chunks, per-tenant index isolation, treat retrieved content as untrusted,
and run indirect-injection detection on retrieved text before it hits the prompt —
which is exactly the `rag`/`document` channel scoping in my detector.

**Q15. You have one week and a pile of raw LLM logs. What do you do first?**
Normalize and make it queryable (schema + indexes) — you can't hunt what you can't
query. Then run signature detectors for known TTPs and rank by severity to get a
threat overview (`01_attack_overview.sql`). Pull repeat offenders and attack chains.
Brief leadership with the top 3 risks in impact language (§5). Then iterate detectors
on the false-positive/false-negative cases. That's literally the order this repo's
analysis queries are numbered.

### SIA-specific (Strategic Intelligence & Analysis)

**Q16. SIA forecasts real-world abuse and strategic threats — how do you make LLM-log analysis forward-looking, not just reactive?**
Reactive triage answers "what happened"; forecasting needs trend + leading indicators.
(1) Track each TTP's volume over time (`03_injection_timeline.sql`) and watch the **slope**,
not the total — a rising indirect-injection rate in the RAG channel predicts a poisoned-source
campaign before it peaks. (2) Watch **emerging clusters**: new attack phrasings, or new
principals adopting a known TTP. (3) Tie internal signals to **external context** — a jailbreak
going viral, or a geopolitical event shifting who's targeting what. The deliverable is a short
"what's rising, why it matters, what to do now" brief, not a dashboard nobody reads.

**Q17. A novel abuse pattern surfaces overnight. Produce "scaled, rapid, decision-ready" intelligence by morning — walk me through it.**
(1) **Scope fast:** write one detector / SQL filter for the new pattern and run it across the
corpus for prevalence + affected principals/channels in minutes (the pluggable detector schema
makes this a small diff, not a rewrite). (2) **Validate:** hand-check a sample to kill false
positives; separate confirmed from suspected. (3) **Prioritize:** rank by severity + blast
radius; correlate into chains. (4) **Communicate:** a one-paragraph brief — finding, mechanism,
impact, likelihood, recommendation, cost of inaction (§5). (5) **Make it durable:** commit the
detector + a query so the pattern is monitored continuously, not re-hunted. Zero-to-one, then
reusable — exactly the JD's "turn analyses into reusable workflows/tools."

**Q18. How does anomaly detection (e.g. PyOD) fit alongside your signature detectors?**
Signatures catch *known* TTPs with high precision but miss the novel, low-prevalence harms SIA
most cares about. Anomaly detection catches the unknown: build per-principal feature vectors
(token volume, query diversity, tool-call rate, refusal rate, output length, off-hours ratio)
and flag outliers with **PyOD** (Isolation Forest / ECOD) or embedding-cluster novelty. I already
ship the cheap SQL version — `06_consumption_anomaly.sql` (statistical outliers) and
`07_session_escalation.sql` (cross-event correlation); PyOD is the natural next layer on the same
feature tables. Run both: **signatures for coverage, anomaly for discovery**, and triage where
they agree first.

---

## 4. STAR stories to prepare

Map your enterprise **incident-management** background onto **LLM threat intel**.
Transferable skills: triage, severity assignment, evidence handling, escalation, RCA.

1. **High-severity triage under ambiguity.**
   *Situation/Task:* a flood of alerts, unclear which were real.
   *Action:* built/used a severity rubric, correlated signals into incidents, cut
   noise. *Result:* faster MTTR, fewer false escalations.
   → Tie to: detector severity ranking + attack-chain correlation (217 findings →
   61 critical first). Same instinct, new domain (LLM logs).

2. **Evidence-driven escalation.**
   *S/T:* a finding needed to go up the chain with proof.
   *A:* assembled a tight evidence package — what, where, blast radius, confidence —
   and routed it to the right owner. *R:* decision made fast, no thrash.
   → Tie to: each finding carries detector + OWASP/ATLAS id + severity + evidence
   span, so it's escalation-ready; §5 turns it into leadership language.

3. **Root-cause analysis / postmortem.**
   *S/T:* recurring incident; symptom-fixing wasn't holding.
   *A:* RCA back to the trust-boundary/process failure; fixed the cause, added a
   detection so it can't recur silently. *R:* recurrence dropped.
   → Tie to: indirect injection RCA — the fix is the *render/trust layer*, but you
   add the log detector so it never recurs undetected (channel-scoped detection).

4. **Building tooling to scale yourself.**
   *S/T:* manual triage didn't scale.
   *A:* built a repeatable, tested tool/runbook instead of one-off heroics.
   *R:* the team could run it; consistent, auditable output.
   → Tie to: the CLI + Makefile + 83 tests — a deployable tool, not a notebook.

---

## 5. Talking points — advising product leadership

Translate a log line into a decision. Pattern: **Finding → Mechanism → Impact →
Likelihood → Recommendation → Cost of inaction.**

- **Lead with business impact, not the payload.** Not "regex matched `onerror=`" —
  say "assistant output can carry active content that executes in a user's browser
  (account takeover); LLM05; N events this week; fix = output sanitization at render."
- **Use a shared severity vocabulary.** critical/high/medium/info tied to OWASP/ATLAS ids
  gives leadership a stable, benchmarkable scale ("61 critical findings, mostly LLM01
  indirect injection via RAG").
- **Quantify exposure.** counts, affected principals/channels, trend vs last period.
  "Indirect injection is 73% of criticals and concentrated in the RAG channel" is a
  roadmap input.
- **Always pair risk with a concrete mitigation and its cost.** "Block markdown
  image auto-fetch in output rendering — 1 sprint, kills the top exfil vector."
- **Name the trust boundary that failed.** Leadership acts on systemic causes
  ("untrusted retrieved content is reaching the prompt unfiltered") faster than on
  symptoms.
- **Separate confirmed from suspected.** Confirmed leak (live key in output) vs
  suspected (probing pattern) — calibrates urgency and credibility.

Example one-liner brief:
> "LLM01 indirect prompt injection via the RAG channel: 110 critical findings this
> week, up 40%. Mechanism — poisoned documents carry instructions the model obeys,
> one of which preceded an unintended tool call. Impact — unauthorized actions on
> connected systems. Recommendation — trust-tag retrieved chunks + run injection
> detection pre-prompt (≈1 sprint). Cost of inaction — agentic data exfil at scale."

---

## 6. Study plan / certs / hands-on

**Certs & courses**
- **OffSec AI Red Teamer — OSAI / AI-300.** Hands-on offensive ML/LLM red-teaming;
  the most role-aligned cert. Good signal for "I attack models, not just read about
  them."
- **Stanford XACS134** (AI security / adversarial ML short course) — solid academic
  grounding in adversarial-ML fundamentals (poisoning, evasion, extraction,
  inversion) to back up the framework knowledge.

**Hands-on intuition (do these — they're fast and memorable)**
- **Lakera Gandalf** — `gandalf.lakera.ai` — beat the levels to *feel* prompt
  injection and defense escalation firsthand. Great interview anecdote material.
- **PyOD (anomaly detection)** — `pip install pyod`; the SIA JD names it explicitly.
  Fit an IsolationForest / ECOD model on per-principal features (token volume, query
  diversity, tool-call rate) and compare it against this repo's SQL outlier queries.
  Talking point: "signatures for known TTPs, PyOD for novel / low-prevalence discovery."
- **`red-team/` tooling in this repo:**
  - **PyRIT** (`red-team/pyrit/`) — Microsoft's automated risk-identification
    framework; orchestrates adversarial prompts at scale, scores responses.
  - **Garak** (`red-team/garak/`) — LLM vulnerability scanner; probe-based, runs a
    battery of known attacks (injection, leakage, toxicity, jailbreak) and reports.
  - **Promptfoo** (`red-team/promptfoo/`) — eval + red-team harness; great for
    regression-testing prompts/guardrails and comparing models on attack suites.
  - Talking point: these are the *generation* side; my `llm-log-triage` flagship is
    the *detection/triage* side — together they're an offense+defense loop. PyRIT/
    Garak generate attacks → logs → triage pipeline detects → findings tighten
    detectors and guardrails. The detection side covers LLM01/02/05/06/07 via 9
    detectors plus LLM10 (Unbounded Consumption / denial-of-wallet) via the pure-SQL
    `sql/analysis/06_consumption_anomaly.sql` — per-session token/call/latency outliers
    vs the population mean.

**Read before the interview**
- `reference/owasp-llm-top-10.md` — all 10, ids cold.
- `reference/mitre-atlas.md` — the technique ids in §2's table cold.
- `reference/glossary.md` — terms (DoW, extraction, inversion, evasion, poisoning,
  canary token, indirect injection, excessive agency).

**Drill loop:** run `make demo`, then answer §3 questions out loud while reading the
real numbers off the queries. Knowing your own findings cold (217 / 61 critical /
LLM01-dominant) is the most convincing possible answer to "tell me about a project."
