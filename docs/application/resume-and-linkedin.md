# Résumé + LinkedIn — Technical Intelligence Analyst (SIA, OpenAI)

> Personalized for Izu Uhiara (current employer anonymized for the public repo). The **project**
> bullets are factual (verifiable in this repo); the **experience** bullets are your real roles —
> add hard metrics where you have them.

---

## Résumé — Summary line (top of CV)

> Security incident management leader (AVP) and AI-enablement driver — ~20 years across operations,
> major-incident response, and security operations, now focused on **AI threat intelligence**. Strong
> **Python + SQL**; fluent in the **OWASP LLM Top 10 (2025)** and **MITRE ATLAS**. Built and shipped a
> tested LLM-log threat-detection pipeline (prompt injection, exfiltration, anomaly detection).
> Investigative core: triage, severity, evidence, escalation, root-cause analysis.

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

## Résumé — Experience (real roles — add metrics where you have them)

- **AVP, Security Incident Management** — global bank, CISO organization (2025–present). Lead
  security incident management and drive AI enablement: modernizing incident-management workflows,
  governing global AI use cases, and pairing security-operations rigor with practical AI execution
  to improve consistency and scale.
- **Sr. Major Incident Management Analyst** — T-Mobile (2016–2024). Owned major-incident response
  for a national telecom — triaged high-severity incidents under ambiguity, ran bridge calls,
  assigned severity, and drove SLA adherence, executive escalation, and root-cause analysis to
  prevent recurrence.
- **Lead Application Support Analyst** — T-Mobile (2014–2016). Led application support and incident
  response; turned recurring failures into process and reliability improvements.
- **Senior Network Support Analyst** — Verizon Wireless (2007–2012). Diagnosed and resolved complex
  network incidents; root-cause analysis on recurring fault classes.

> Drop in real numbers wherever you have them — incident volume, MTTR/MTTA reduction, SLA %, number
> of teams or analysts supported. Metrics turn each line from a duty into an achievement.

## Résumé — Education & certifications

- **Computer Engineering** — The University of Texas at Arlington
- **Electrical & Electronics Engineering** — Kettering University
- **Google Cloud: Core Infrastructure** (Google, 2024) · **Introduction to IT & AWS Cloud** (AWS) ·
  **Certified ScrumMaster (CSM)**

> Add degree level (B.S./M.S.) and any of your other certifications (your LinkedIn lists 12) here.

## Résumé — Skills (ATS keywords)

`Python` · `SQL` · `SQLite` · `threat intelligence` · `anomaly detection` · `PyOD` ·
`OWASP LLM Top 10` · `MITRE ATLAS` · `prompt injection` · `jailbreak` · `data exfiltration` ·
`LLM security` · `adversarial ML` · `red teaming` · `PyRIT` · `garak` · `promptfoo` ·
`incident response` · `triage` · `root-cause analysis` · `detection engineering` · `pytest` · `CI/CD`

---

## LinkedIn — Headline (pick one)

1. Security Incident Management leader (AVP) building **AI threat intelligence** | Python · SQL · OWASP LLM Top 10 · MITRE ATLAS | I build LLM-abuse detection
2. Technical Intelligence Analyst (LLM safety) | detecting prompt injection, jailbreaks & exfiltration with Python + SQL
3. Turning messy LLM logs into decision-ready intelligence | adversarial-ML detection · anomaly detection · red teaming

## LinkedIn — About

> I investigate how AI systems break. After nearly two decades in operations and incident
> management — now AVP, Security Incident Management, where I also lead AI enablement across a CISO
> organization — I'm focused on the frontier version of that work: surfacing novel harms and abuse
> patterns in LLM systems and turning them into intelligence that changes how products ship.
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

> **Draft (make it yours):** I've spent my career in incident management, and lately — inside a CISO
> organization — governing how AI actually gets used. That gave me a front-row view of how fast AI
> risk emerges and how little prior art exists to lean on. SIA's charter (monitor, analyze, and
> forecast real-world abuse at the frontier) is the same investigative loop I run today, but where
> the harms are novel and the analysis directly shapes how powerful systems deploy — and I'd
> specifically want to work on turning weak, early abuse signals into detection that scales.

**Why this role, given your background?** The job is investigative analysis with Python + SQL
applied to how models break. My security incident management background is exactly that
investigative core — triage, severity, evidence, escalation, RCA — and I closed the
domain/technical gap deliberately by building openai-tia-prep. I'm not pivoting blind; I've
already done the work the role describes.

**What's your biggest gap and how are you closing it?** Direct production LLM-abuse experience at
scale. I'm closing it with the project (real detection + anomaly work), the frameworks (OWASP
LLM / ATLAS, cold), hands-on red teaming (PyRIT/garak/promptfoo, Lakera Gandalf), and
anomaly-detection tooling (PyOD) — and I learn fastest by building, which the repo demonstrates.
