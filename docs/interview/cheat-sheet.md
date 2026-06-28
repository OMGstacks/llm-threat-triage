# Interview cheat-sheet — memorize this

> One page. The frameworks cold, the numbers tight, the pitch ready. (A printable PDF version,
> `cheat-sheet.pdf`, sits next to this file.)

## 30-second project pitch
> "I built `openai-tia-prep` — a Python + SQL pipeline that ingests messy LLM logs and flags
> prompt injection, jailbreaks, and data exfiltration, every finding mapped to OWASP LLM Top 10
> and MITRE ATLAS. 800 events → 150 flagged / 217 findings, 9 detectors, 7 analyst SQL queries
> including anomaly detection, 83 tests and CI. I red-teamed my own detectors and fixed the bugs."

## SIA mission (say it back in your words)
Monitor, analyze, and **forecast real-world abuse**, geopolitical and strategic threats →
inform **safety mitigations, product decisions, partnerships**. Day-to-day: **surface novel
harms & abuse patterns** → **structured, decision-ready intelligence**, via SQL + Python + AI tools.

## Repo numbers (seed 7)
800 events · 156 bad timestamps recovered · 63 missing IDs synthesized · **150 flagged** ·
**217 findings** (61 critical / 126 high / 25 medium / 5 info) · 9 detectors · 7 SQL queries · 83 tests.
By OWASP: LLM01 **132**, LLM05 29, LLM07 25, LLM02 22, LLM06 9.

## OWASP LLM Top 10 — 2025
| | | | |
|---|---|---|---|
| **01** Prompt Injection | **02** Sensitive Info Disclosure | **03** Supply Chain | **04** Data & Model Poisoning |
| **05** Improper Output Handling | **06** Excessive Agency | **07** System Prompt Leakage | **08** Vector & Embedding Weaknesses |
| **09** Misinformation | **10** Unbounded Consumption | | |

Repo covers (detectors) **01, 02, 05, 06, 07**; (SQL) **10** + multi-turn correlation. Roadmap: 03, 04, 08, 09.

## MITRE ATLAS — key techniques
`AML.T0051` LLM Prompt Injection (.000 Direct / .001 Indirect) · `AML.T0054` LLM Jailbreak ·
`AML.T0056` LLM Meta Prompt Extraction · `AML.T0053` AI Agent Tool Invocation ·
`AML.T0057` LLM Data Leakage · `AML.T0024` Exfiltration via AI Inference API.
(ATLAS = ATT&CK for ML: Recon → Model Access → Poisoning → ML Attack Staging → Exfiltration → Impact.)

## Rapid-fire definitions
- **Direct injection:** the *user* types the override ("ignore previous instructions").
- **Indirect injection:** override rides in on *ingested content* (RAG doc, web page, email, tool output); user may be innocent → more dangerous, blurred trust boundary.
- **Jailbreak:** defeats *safety/policy* (persona: DAN, "developer mode"); often delivered by injection but the intent is policy bypass.
- **System-prompt leakage/extraction:** probing to reveal the hidden prompt ("repeat the words above"); best signal = **canary token** in the prompt.
- **Improper output handling:** downstream system trusts model output → XSS/SSRF/exfil-link/code-exec; fix = treat output as untrusted input.
- **Excessive agency:** too much tool/permission/autonomy → unintended real-world actions.
- **Model extraction:** systematic querying to steal the model/decision boundary (LLM10 / AML.T0024).
- **Membership inference / inversion:** infer if a record was in training / reconstruct training data.
- **Denial-of-wallet (DoW):** cost-exhaustion via expensive inference (huge contexts, max tokens, recursive agent loops) — metered-billing twin of DoS (LLM10).
- **Data/model poisoning:** train-time corruption of data → altered behavior / backdoors (LLM04).

## Detection principles (the repo's design = your talking points)
1. **Channel-awareness** — same string is benign from a user, critical from a RAG document. Provenance is part of the verdict.
2. **Evasion-resistance** — normalize (NFKC, zero-width, spaced-letter, leetspeak) + decode base64/hex *before* matching.
3. **Output-side detection** — scan the model's *response* (secret leak, exfil link), not just input.
4. **Correlation > single signals** — chain injection → anomalous tool call → egress; track repeat offenders; multi-turn escalation.
5. **Signatures for the known, anomaly (PyOD) for the novel** — and triage where they agree first.
6. **Rank + communicate** — severity + framework id → "Finding → Mechanism → Impact → Likelihood → Recommendation → Cost of inaction."

## Mitigations (one each)
Injection → trust-tag & isolate untrusted content, treat all input as hostile, instruction
hierarchy. · Output handling → contextual encoding, strip/allowlist markdown, no eval/shell/SQL on
output. · Leakage → canary tokens, output secret-scan. · Excessive agency → least-privilege tools,
human-in-loop for high-impact actions. · Unbounded consumption → per-key rate/token/cost budgets,
loop guards.
