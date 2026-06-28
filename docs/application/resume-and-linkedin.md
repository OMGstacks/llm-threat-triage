# Résumé + LinkedIn — Technical Intelligence Analyst (SIA, OpenAI)

> `[brackets]` = your specifics. The **project** bullets are factual (verifiable in this repo);
> the **experience** bullets are templates — keep the verbs and structure, drop in your real
> situations and numbers.

---

## Résumé — Summary line (top of CV)

> Security / incident-management professional moving into **AI threat intelligence**. Strong
> **Python + SQL**; fluent in the **OWASP LLM Top 10 (2025)** and **MITRE ATLAS**. Built and
> shipped a tested LLM-log threat-detection pipeline (prompt injection, exfiltration, anomaly
> detection). Investigative mindset: triage, severity, evidence, escalation, root-cause analysis.

## Résumé — Selected project (lead with this)

**LLM Log Triage — `openai-tia-prep`** · Python, SQL/SQLite, pytest, GitHub Actions · github.com/OMGstacks/openai-tia-prep

- Built an end-to-end LLM-log threat-detection pipeline (ingest → normalize → detect → SQL
  triage) that flags **150 of 800** sample events / **217 findings**, every finding mapped to the
  **OWASP LLM Top 10 (2025)** and **MITRE ATLAS**.
- Wrote **9 channel-aware, evasion-resistant detectors** (direct/indirect/encoded prompt
  injection, jailbreak, system-prompt extraction, excessive agency, sensitive-data disclosure,
  output exfil) defeating unicode/spaced-letter/leetspeak and base64/hex obfuscation.
- Authored **7 analyst SQL queries** including an **unbounded-consumption anomaly** detector and
  **multi-turn cross-event correlation** for low-prevalence / staged attacks.
- **Red-teamed my own detectors**, finding and fixing real bugs (silent timestamp corruption,
  role-scoping false positives, evasion bypasses); locked behind **83 passing tests** + CI.
- Built a normalizer that recovers **156 unparseable timestamps** and **63 missing IDs** from
  deliberately messy logs — turning unqueryable data into a triage-ready dataset.

## Résumé — Experience bullets (templates — make them yours)

- Triaged [volume] [security incidents / alerts] under ambiguity; built a severity rubric that
  [cut mean time-to-triage by X% / reduced false escalations by Y%].
- Led root-cause analysis on [recurring incident class]; shipped a [process/detection] fix that
  [dropped recurrence by Z%].
- Built [a tool / runbook / dashboard] that let [the team / N people] [do X] consistently —
  replacing one-off manual work (a zero-to-one → reusable-tool pattern).

## Résumé — Skills (ATS keywords)

`Python` · `SQL` · `SQLite` · `threat intelligence` · `anomaly detection` · `PyOD` ·
`OWASP LLM Top 10` · `MITRE ATLAS` · `prompt injection` · `jailbreak` · `data exfiltration` ·
`LLM security` · `adversarial ML` · `red teaming` · `PyRIT` · `garak` · `promptfoo` ·
`incident response` · `triage` · `root-cause analysis` · `detection engineering` · `pytest` · `CI/CD`

---

## LinkedIn — Headline (pick one)

1. Security & incident response → **AI threat intelligence** | Python · SQL · OWASP LLM Top 10 · MITRE ATLAS | I build LLM-abuse detection
2. Technical Intelligence Analyst (LLM safety) | detecting prompt injection, jailbreaks & exfiltration with Python + SQL
3. Turning messy LLM logs into decision-ready intelligence | adversarial-ML detection · anomaly detection · red teaming

## LinkedIn — About

> I investigate how AI systems break. After [N years] in [security / incident management] —
> triage, severity, evidence, escalation, root-cause analysis — I'm focused on the frontier
> version of that work: surfacing novel harms and abuse patterns in LLM systems and turning them
> into intelligence that changes how products ship.
>
> To prove it rather than claim it, I built **openai-tia-prep**: a tested Python + SQL pipeline
> that ingests messy LLM interaction logs and flags prompt injection (direct, indirect, and
> obfuscated), jailbreaks, system-prompt extraction, and data exfiltration — every finding mapped
> to the **OWASP LLM Top 10 (2025)** and **MITRE ATLAS**, with SQL anomaly detection for the
> low-prevalence patterns signatures miss. 9 detectors, 7 analyst queries, 83 tests, CI — and I
> red-teamed my own detectors and fixed what broke.
>
> Fluent in: Python, SQL, the LLM-threat frameworks, and the red-team stack (PyRIT, garak,
> promptfoo). Looking for technical intelligence / trust & safety / AI-security roles.
> Repo: github.com/OMGstacks/openai-tia-prep

---

## Application Q&A (have these ready)

**Why OpenAI / why SIA?** *(write 2–3 genuine sentences — what about the frontier-safety mission
and SIA's "monitor, analyze, forecast real-world abuse" charter is real for you. Avoid generic
praise; name something specific you'd want to work on.)*

**Why this role, given your background?** The job is investigative analysis with Python + SQL
applied to how models break. My [security / incident-management] background is exactly that
investigative core — triage, severity, evidence, escalation, RCA — and I closed the
domain/technical gap deliberately by building openai-tia-prep. I'm not pivoting blind; I've
already done the work the role describes.

**What's your biggest gap and how are you closing it?** Direct production LLM-abuse experience at
scale. I'm closing it with the project (real detection + anomaly work), the frameworks (OWASP
LLM / ATLAS, cold), hands-on red teaming (PyRIT/garak/promptfoo, Lakera Gandalf), and
anomaly-detection tooling (PyOD) — and I learn fastest by building, which the repo demonstrates.
