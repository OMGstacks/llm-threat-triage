# Résumé + LinkedIn — Technical Intelligence Analyst (SIA, OpenAI)

> Personalized for Izu Uhiara (current employer anonymized for the public repo). The **project**
> bullets are factual (verifiable in this repo); the **experience** bullets are your real roles —
> add hard metrics where you have them.

---

## Résumé — Summary line (top of CV)

> Security operations & technical-intelligence leader (AVP) — **20 years** across major-incident
> command, security incident management, application/network operations, and **governed AI-assisted
> workflows**, now focused on **AI threat intelligence**. Strong **Python + SQL**; CompTIA **Security+**;
> fluent in the **OWASP LLM Top 10 (2025)** and **MITRE ATLAS**. Built and shipped a tested LLM-log
> threat-detection pipeline (prompt injection, exfiltration, anomaly detection). Investigative core:
> triage, severity, evidence, escalation, root-cause analysis.

## Résumé — Selected project (lead with this)

**LLM Log Triage — `llm-threat-triage`** · Python, SQL/SQLite, pytest, GitHub Actions · github.com/OMGstacks/llm-threat-triage

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

## Résumé — Experience

> Current employer anonymized for the public repo (a global bank); named in versions you submit
> directly. Add hard numbers wherever you have them — they turn a duty into an achievement.

**Assistant Vice President, Security Incident Management** — global bank, CISO organization · 2025–present
- Lead security incident management workstreams — post-containment coordination, governance alignment,
  operational analysis, and process improvement across complex enterprise incident workflows.
- Framed and advanced **governed AI-assisted workflows** for security incident analysis, reducing manual
  data-handling steps while preserving analyst review, access controls, and control discipline.
- Built proof-of-concept AI-enabled incident-analysis workflows end to end: requirements, non-production
  test-data boundaries, access-control considerations, and structured output validation.
- Converted recurring security-operations analysis needs into reusable workflow patterns for triage
  support, structured summary drafting, and decision-support output.
- Produced incident-trend analysis that surfaced containment-definition gaps and long-tail remediation
  patterns, strengthening incident-response metrics ownership; established recurring AI-adoption forums
  and reusable knowledge assets for responsible use across security operations.

**Sr. Major Incident Management Analyst** — T-Mobile · 2016–2024
- Led enterprise **major-incident command** for high-impact (P1/P2) service disruptions — aligning
  technical, operational, and business stakeholders to accelerate restoration and reduce business impact.
- Drove escalation discipline, communications cadence, and structured decision-making on live bridges;
  acted as liaison between internal teams and external partners during critical events.
- Owned post-incident root-cause analysis, identified recurring issues, and implemented permanent fixes
  that reduced MTTR and fed continuous improvement; built and facilitated incident-response training.

**Lead Application Support Analyst** — T-Mobile · 2014–2016
- Led application-support triage and production-issue coordination across dev, infrastructure, and
  support teams; maintained production stability through proactive resolution and 24/7 on-call.

**Senior Network Support Analyst** — Verizon Wireless · 2007–2012
- Network incident analysis, technical troubleshooting, escalation coordination, and recurring-issue
  tracking in a high-pressure telecommunications environment.

**Production / Maintenance Operations Group Leader** — General Motors · 2001–2005
- Led frontline production and maintenance operations — uptime, safety, quality, and team execution
  in a high-volume manufacturing environment.

## Résumé — Education

- **Computer Engineering** — The University of Texas at Arlington (2005–2007)
- **Electrical & Electronics Engineering** — Kettering University (2001–2005) — GM Assembly co-op

## Résumé — Certifications

Certified ScrumMaster (CSM) · ITIL v3 Foundation · ITIL Practitioner · ITIL v4 Foundation ·
**CompTIA Security+** · Artificial Intelligence on Microsoft Azure · Python Programming ·
Ethical Hacking Foundations · Digital Forensic Investigation · AWS Cloud Practitioner (in progress)

## Résumé — Skills (ATS keywords)

`Python` · `SQL` · `SQLite` · `PostgreSQL` · `Splunk` · `Elasticsearch` · `Kibana` · `Grafana` ·
`Power BI` · `Tableau` · `ServiceNow` · `Jira` · `Wireshark` · `AWS` · `Azure` · `Linux` ·
`threat intelligence` · `anomaly detection` · `OWASP LLM Top 10` · `MITRE ATLAS` · `prompt injection` ·
`jailbreak` · `data exfiltration` · `LLM security` · `adversarial ML` · `red teaming` · `PyRIT` ·
`garak` · `promptfoo` · `incident management` · `major incident command` · `triage` ·
`root-cause analysis` · `detection engineering` · `governed AI workflows` · `pytest` · `CI/CD`

---

## LinkedIn — Headline (pick one)

1. Security Incident Management leader (AVP) building **AI threat intelligence** | Python · SQL · OWASP LLM Top 10 · MITRE ATLAS | I build LLM-abuse detection
2. Technical Intelligence Analyst (LLM safety) | detecting prompt injection, jailbreaks & exfiltration with Python + SQL
3. Turning messy LLM logs into decision-ready intelligence | adversarial-ML detection · anomaly detection · red teaming

## LinkedIn — About

> I investigate how AI systems break. After 20 years in major-incident command and security incident
> management — now an AVP designing governed, AI-assisted incident-analysis workflows in a global
> bank's CISO organization — I'm focused on the frontier version of that work: surfacing novel harms
> and abuse patterns in LLM systems and turning them into intelligence that changes how products ship.
>
> To prove it rather than claim it, I built **llm-threat-triage**: a tested Python + SQL pipeline
> that ingests messy LLM interaction logs and flags prompt injection (direct, indirect, and
> obfuscated), jailbreaks, system-prompt extraction, and data exfiltration — every finding mapped
> to the **OWASP LLM Top 10 (2025)** and **MITRE ATLAS**, with SQL anomaly detection for the
> low-prevalence patterns signatures miss. 9 detectors, 7 analyst queries, 83 tests, CI — and I
> red-teamed my own detectors and fixed what broke.
>
> Fluent in: Python, SQL, the LLM-threat frameworks, and the red-team stack (PyRIT, garak,
> promptfoo). Looking for technical intelligence / trust & safety / AI-security roles.
> Repo: github.com/OMGstacks/llm-threat-triage

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
domain/technical gap deliberately by building llm-threat-triage. I'm not pivoting blind; I've
already done the work the role describes.

**What's your biggest gap and how are you closing it?** Direct production LLM-abuse experience at
scale. I'm closing it with the project (real detection + anomaly work), the frameworks (OWASP
LLM / ATLAS, cold), hands-on red teaming (PyRIT/garak/promptfoo, Lakera Gandalf), and
anomaly-detection tooling (PyOD) — and I learn fastest by building, which the repo demonstrates.
