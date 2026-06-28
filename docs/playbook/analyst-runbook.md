# Analyst runbook — day-to-day LLM threat intelligence

A practical operating manual for the role: the loop you run, how you triage, how you
investigate each attack class, when you escalate, and how you communicate. It's written
against the concepts this repo already implements, so the queries/detectors referenced are
real — but the discipline transfers to any production stack (a real SIEM, a data warehouse,
internal tooling).

> **The analyst loop:** `ingest → normalize → detect → triage → investigate → prioritize →
> communicate → harden`. Everything below is a station on that loop.

---

## Daily workflow

1. **Health-check the pipeline.** Did ingestion run? Any normalization spike (a jump in
   unparseable rows often means a producer changed format — a signal in itself)?
2. **Work the triage queue, severity-first.** Pull the day's findings ranked critical → high
   (repo parallel: `01_attack_overview.sql`). Critical = confirmed harm or high-confidence
   attack with blast radius. Don't touch mediums until criticals are cleared or parked.
3. **For each critical/high:** run the **triage SOP** (below) → confirmed, suspected, or false
   positive. Confirmed → escalate. Suspected → investigate or watchlist. FP → tune the detector.
4. **Scan repeat offenders & chains.** `02_repeat_offenders.sql` (who), `07_session_escalation.sql`
   (sessions pairing injection with exfil — the staged attacks single rows miss).
5. **Close out.** Update each finding's status; capture anything that should become a detector or
   a brief. Leave the queue in a state the next analyst can read.

## Weekly workflow (the forecasting half)

- **Trend, don't just count.** Watch each TTP's *slope* (`03_injection_timeline.sql`): a rising
  indirect-injection rate in the RAG channel predicts a poisoned-source campaign before it peaks.
- **Hunt for the novel.** Run anomaly passes (`06_consumption_anomaly.sql`; PyOD on per-principal
  features) and review new prompt clusters. Low-prevalence ≠ low-importance.
- **Tie to external context.** A jailbreak going viral, a new model capability, a geopolitical
  event shifting targeting — fold it into the outlook.
- **Ship one improvement.** A new detector, a tightened rule, a new query, or a retired FP source.
- **Write the weekly brief.** Top 3 risks, what's rising, what you shipped, what you recommend.

---

## Triage SOP (per finding)

1. **Read the evidence span**, not just the rule name. Does the matched text actually represent
   the attack, or is it a benign collision? (This is why every finding carries a snippet + rationale.)
2. **Establish provenance.** Which channel/role? Indirect injection on a `rag`/`tool`/`document`
   channel is a different (worse) animal than the same string from a user.
3. **Confirmed vs suspected.** *Confirmed* = harm demonstrably occurred (a live secret in output, an
   exfil URL that resolved, an unintended tool call). *Suspected* = a probing pattern with no proven
   payoff. Calibrate urgency and language to which one it is — never blur them.
4. **Scope the blast radius.** One user, or many? One session, or a campaign? Cross-tenant? Did it
   reach a connected tool / external system?
5. **Decide:** escalate (confirmed, or suspected-but-high-impact) · watchlist (suspected, low
   impact) · tune (false positive) · build (a recurring gap with no detector).

### Severity rubric
| Severity | Use when |
|---|---|
| **Critical** | Confirmed harm OR high-confidence attack with real blast radius (indirect injection that reached a tool, live secret in output, cross-tenant leak). |
| **High** | High-confidence attack, contained/no proven payoff yet (direct injection, jailbreak, excessive-agency probe). |
| **Medium** | Probing / reconnaissance (system-prompt extraction attempts, suspicious encoded blobs). |
| **Low / Info** | Weak signal, likely benign, or context-only (a lone email address in output). |

### Escalation criteria — escalate now if any are true
- A **confirmed** leak/exfil/unauthorized action (not a probe).
- **Cross-tenant** data exposure, or anything touching a connected/external system.
- A **campaign**: one principal or pattern across many sessions, or a sharp trend break.
- Anything you can't disposition with confidence and that has plausible high impact — escalate the
  *uncertainty*, clearly labelled, rather than sitting on it.

---

## Per-class investigation playbooks

Each: **signal → query/where to look → validate → escalate-if → mitigation (what you'd recommend).**

### LLM01 — Prompt Injection (direct / indirect / obfuscated)
- **Signal:** override language ("ignore previous instructions"), persona jailbreaks, or imperative
  text aimed at the assistant inside ingested content; obfuscated variants (base64/leetspeak).
- **Look:** `04_indirect_injection_via_rag.sql` (untrusted channels), direct/jailbreak detectors,
  `encoded_injection_payload`. Indirect is the priority — it implies a poisoned source.
- **Validate:** did the injected instruction *precede* an anomalous tool call or data egress in the
  same session (`07_session_escalation.sql`)? That chain is the high-confidence finding.
- **Escalate-if:** the chain completed (action/egress), or the source is a shared corpus (campaign).
- **Mitigate:** trust-tag & isolate untrusted content; run injection detection pre-prompt; instruction
  hierarchy; purge the poisoned document.

### LLM02 — Sensitive Information Disclosure
- **Signal:** secrets/PII in **assistant output** (API keys, tokens, private keys, SSNs, Luhn-valid
  cards) — or arriving in untrusted inbound content (`sensitive_information_inbound`).
- **Validate:** is the secret **live** (entropy + provider format) or hallucinated/format-only? Where
  did it enter the model's reachable context — training data, RAG corpus, another user's context?
- **Escalate-if:** the secret is live, or the exposure is cross-tenant. Treat as confirmed → critical.
- **Mitigate:** rotate the key, purge from corpus, add output-side secret-scanning to block egress;
  RCA how a secret reached reachable context.

### LLM05 — Improper Output Handling / exfil
- **Signal:** model output with exfil URLs (markdown image/link with encoded query), or active
  content (`<script>`, `onerror=`, `javascript:`).
- **Validate:** would a downstream renderer auto-fetch/execute it? Often the tail end of an indirect
  injection — check the session for the instruction that produced it.
- **Escalate-if:** the render layer would execute it, or data left via the URL.
- **Mitigate:** contextual output encoding, strip/allowlist markdown (kill image auto-fetch), disable
  active content; never eval/shell/SQL-interpolate model output.

### LLM06 — Excessive Agency
- **Signal:** user coercing connected tools/plugins into destructive/unintended actions.
- **Validate:** did the tool actually fire? What were its real permissions? Action vs mere request.
- **Escalate-if:** a high-impact action executed (delete/transfer/exfiltrate).
- **Mitigate:** least-privilege tools, human-in-the-loop for high-impact actions, scope tokens.

### LLM07 — System Prompt Leakage
- **Signal (input):** extraction probes ("repeat the words above", "what is your system prompt").
  **(output):** assistant echoing prompt markers/canaries.
- **Validate:** a **canary token** in the system prompt is the gold standard — if it appears in
  output, leakage is confirmed with near-zero FPs.
- **Escalate-if:** the prompt (esp. any secret-in-prompt) actually leaked.
- **Mitigate:** canaries, keep secrets out of prompts, output-side canary detection.

### LLM10 — Unbounded Consumption (incl. model extraction, DoW)
- **Signal:** per-principal token/call/latency outliers; high-volume, high-diversity, low-repeat
  querying (extraction); recursive agent loops / max-token abuse (denial-of-wallet).
- **Look:** `06_consumption_anomaly.sql` (statistical outliers) → extend with PyOD on richer features.
- **Escalate-if:** sustained extraction-shaped traffic, or cost/abuse impact.
- **Mitigate:** per-key rate/token/cost budgets, max-output caps, loop guards, query-diversity limits.

---

## Signature vs anomaly — which tool when
- **Signature (rule/regex/detector):** known TTP, need precision and an explainable artifact. Fast to
  ship; add it the moment a pattern recurs. *Recall-oriented; pair with ranking + correlation for precision.*
- **Anomaly (statistical / PyOD / clustering):** unknown or low-prevalence harms — the novel ones SIA
  most cares about. Build per-principal feature vectors (token volume, query diversity, tool-call rate,
  refusal rate, output length, off-hours ratio) and flag outliers. *Discovery-oriented.*
- **Run both. Triage where they agree first.** Signatures cover the known; anomaly surfaces the next
  thing to write a signature for. The cheap SQL baseline (`06`/`07`) is the on-ramp to PyOD.

## Novel-harm discovery loop
`anomaly/cluster surfaces something unfamiliar → hand-inspect a sample → name the pattern →
write a one-off detector/query → measure prevalence + blast radius → brief it → commit the detector
so it's monitored continuously (not re-hunted).` That last step is the JD's "turn analyses into
reusable workflows/tools."

---

## Templates

### Intel brief (the unit of output — paste-ready)
```
TITLE: <OWASP id + plain-English what>, <severity>
WHAT:        <one line — confirmed or suspected, and the finding>
MECHANISM:   <how it works / the attack chain>
IMPACT:      <business/safety impact in their language, not the payload>
SCOPE:       <# events, # principals, channels, trend vs last period, cross-tenant?>
LIKELIHOOD:  <confirmed / probable / possible — and why>
RECOMMENDATION: <concrete mitigation + rough cost (e.g. "~1 sprint")>
COST OF INACTION: <what happens if we don't>
EVIDENCE:    <links / event ids / query>
```
> Example one-liner: *"LLM01 indirect prompt injection via RAG: 110 critical findings this week,
> up 40%. Mechanism — poisoned docs carry instructions the model obeys; one preceded an unintended
> tool call. Impact — unauthorized actions on connected systems. Recommendation — trust-tag retrieved
> chunks + pre-prompt injection detection (~1 sprint). Cost of inaction — agentic exfil at scale."*

### Finding writeup (per investigated finding)
```
finding_id · detector · owasp_id · atlas_technique · severity
status: confirmed | suspected | false_positive | watchlist
provenance: channel / role / principal / session
evidence: matched snippet + rationale + event id(s)
chain: <preceding/following events, if part of an attack chain>
disposition: <escalated to … | tuned detector | watchlisted | closed>
```

### New-detector checklist (before you ship a signature)
- [ ] Maps to an OWASP LLM id **and** a MITRE ATLAS technique.
- [ ] Channel/role-scoped correctly (don't scan output rules on input, or user rules on RAG).
- [ ] Tests for **true positives AND benign non-matches** (every FP fix gets a regression test).
- [ ] Exercised by sample/synthetic data so the pipeline has signal.
- [ ] Severity + rationale set; emits the same finding schema as everything else.
- [ ] Considered evasion (does an obfuscated variant still trip it?).

---

## Communication principles (with leadership)
Lead with **business impact, not the payload**. Use a **shared severity vocabulary** tied to
OWASP/ATLAS. **Quantify exposure** (counts, principals, trend). **Always pair risk with a concrete
mitigation and its cost.** **Name the trust boundary that failed** — systemic causes get fixed
faster than symptoms. **Separate confirmed from suspected** — it's your credibility.
