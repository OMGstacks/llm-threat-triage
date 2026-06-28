# Cover-letter variants — adjacent OpenAI roles

The same project maps to several roles in OpenAI's Intelligence / Investigations / Safety org.
Below are tailored short letters (≈160 words each) for the closest adjacent roles, plus notes on
what to emphasize and which gap to address honestly. Personalized for Izu Uhiara; the current
employer is anonymized for the public repo (swap in the real name for versions you submit directly).

> Apply to the role whose JD verbs match your strengths. The flagship (`openai-tia-prep`) is
> evidence for **all** of these — what changes is which of its facets you lead with.

---

## A. Technical Abuse Investigator — *Intelligence & Investigations*
*Detect, investigate, and disrupt malicious use of the platform; build lightweight SQL/Python
tooling, investigation templates, and dashboards; communicate via briefs and escalation summaries.*
([JD](https://openai.com/careers/technical-abuse-investigator-san-francisco/))

**Fit:** near-perfect on the technical-tooling + investigation axis. **Gap to address:** "5+ years
tracking threat actors in abuse domains" — lean on transferable security/incident-management years + the project.

> Dear Hiring Manager,
>
> I'm applying for the Technical Abuse Investigator role on Intelligence & Investigations. The core
> of the job — turning one-off insights into lightweight SQL/Python tooling that scales coverage and
> reduces manual investigation — is exactly what I build. `openai-tia-prep`
> (github.com/OMGstacks/openai-tia-prep) is a tested Python + SQL pipeline that ingests messy LLM
> logs, surfaces abuse signals (prompt injection, jailbreaks, data exfiltration) mapped to OWASP LLM
> Top 10 + MITRE ATLAS, ranks them by severity, and ships investigation-ready output — every finding
> with a matched snippet, rationale, and an escalation-ready brief template. It's 9 detectors, 7
> analyst SQL queries incl. anomaly detection, 83 tests and CI — and I red-teamed my own detectors
> and fixed the bugs. That's the "scale a one-off into a reusable tool" pattern the role asks for.
> Paired with nearly two decades in incident management — currently AVP, Security Incident
> Management in a CISO org — triage, severity, escalation, and root-cause analysis — I'd bring both
> the investigative instinct and the engineering to scale it.
>
> Izu Uhiara

---

## B. Technical Threat Investigator — *Threat Intel Engineering*
*Protect OpenAI and the ecosystem from sophisticated adversaries (incl. model misuse for cyber
ops); build tooling/automations that scale investigative throughput; prototype in ambiguous,
emerging spaces; produce high-signal written outputs for technical + executive stakeholders.*
([JD](https://openai.com/careers/technical-threat-investigator-threat-intel-engineering-san-francisco/))

**Fit:** strong on tooling-to-scale-investigations + ambiguity + comms. **Gap:** "investigating
sophisticated threat actors / adversary tradecraft" — frame your incident-management background + the
project's novel-coverage work.

> Dear Hiring Manager,
>
> I'm applying for the Technical Threat Investigator role in Threat Intel Engineering. The part that
> resonates is building tooling that scales investigative throughput in ambiguous, emerging spaces —
> novel attacker behaviors where coverage doesn't exist yet. I built exactly that:
> `openai-tia-prep` (github.com/OMGstacks/openai-tia-prep), a tested Python + SQL pipeline that
> detects LLM-abuse TTPs — direct, indirect, and *obfuscated* prompt injection, jailbreaks,
> exfiltration — mapped to OWASP LLM Top 10 + MITRE ATLAS, with SQL anomaly queries for the
> low-prevalence patterns signatures miss. It deliberately handles the emerging/evasive edge:
> base64/leetspeak decoding, multi-turn attack correlation, and a red-team harness that grades
> attacks with the same engine. 9 detectors, 83 tests, CI; I adversarially reviewed my own detectors
> and fixed what broke. With nearly two decades in incident management and security operations —
> triage, evidence, escalation — I operate well in fast, ambiguous problem spaces and turn investigations
> into high-signal written briefs.
>
> Izu Uhiara

---

## C. Quantitative Intelligence Analyst
*Discover novel/emerging risks in human–AI systems before they're measurable; build analytic models
of how harms form and propagate; operationalize unmeasured problems into detection signals; Python +
SQL, statistical modeling, supervised learning, Monte Carlo / stress testing.*
([JD](https://openai.com/careers/quantitative-intelligence-analyst-san-francisco/))

**Fit:** strong on Python/SQL + operationalizing-patterns-into-signals. **Gap:** depth in statistical
modeling / supervised learning / Monte Carlo — be honest; show the on-ramp (anomaly detection, PyOD)
and your build-to-learn trajectory.

> Dear Hiring Manager,
>
> I'm applying for the Quantitative Intelligence Analyst role. What draws me is operationalizing the
> *unmeasured* — taking ambiguous patterns and turning them into signals that support detection and
> planning. `openai-tia-prep` (github.com/OMGstacks/openai-tia-prep) is my proof of that loop in
> Python and SQL: it ingests messy human–AI interaction logs and converts them into structured,
> measured signals — 217 findings across 800 events, mapped to OWASP LLM Top 10 + MITRE ATLAS, with
> SQL anomaly detection (per-principal consumption outliers, multi-turn correlation) aimed squarely
> at low-prevalence, not-yet-defined risks. I'm strongest in data wrangling, SQL, and turning
> one-off analyses into reusable detection; I'm actively deepening the statistical/ML side
> (anomaly detection with PyOD/Isolation Forest is the natural next layer on the same feature tables,
> and I learn fastest by building — which this repo demonstrates). Combined with nearly two decades
> in security operations and incident management, I'd bring rigor, data fluency, and a bias toward operationalizing insight.
>
> Izu Uhiara

---

## D. AI Emerging Risks Analyst
*Strategic perspective on evolving frontier-AI risks; spot early warning signs, turn weak signals
into prioritized risk calls; mixed quantitative + qualitative; analyze complex online harms and
convert all-source analysis into prioritized recommendations.*
([JD](https://openai.com/careers/ai-emerging-risks-analyst-san-francisco/))

**Fit:** strong on weak-signal → prioritized-call + harm analysis. **Note:** this role is more
strategic/qualitative than the others — lead with judgment and prioritization, position the technical
build as the rigor underneath your calls. **Gap:** strategic/all-source intelligence tenure.

> Dear Hiring Manager,
>
> I'm applying for the AI Emerging Risks Analyst role. The work — spotting early warning signs and
> turning weak signals into clear, prioritized risk calls — is the analytical instinct I've built a
> career on, now aimed at frontier-AI harms. To ground that judgment in technical rigor, I built
> `openai-tia-prep` (github.com/OMGstacks/openai-tia-prep): a Python + SQL pipeline that turns messy
> LLM logs into prioritized, severity-ranked intelligence mapped to OWASP LLM Top 10 + MITRE ATLAS,
> with anomaly detection for the low-prevalence patterns that are early warning signs of emerging
> harms. It pairs quantitative signal (trends, outliers, severity) with qualitative framing (every
> finding carries a plain-English rationale and a decision-ready brief). From nearly two decades in
> incident management and security operations, I'm practiced at all-source triage under ambiguity and converting it into
> recommendations leadership can act on — exactly the weak-signal-to-prioritized-call loop this role
> runs at strategic scale.
>
> Izu Uhiara

---

## Quick chooser
| If you have… | Lean toward |
|---|---|
| Deep abuse/threat-actor tracking + tooling | **A** (Technical Abuse Investigator) |
| Security / IR / offensive background + ambiguity tolerance | **B** (Technical Threat Investigator) |
| Strong data/stats + Python/SQL + modeling appetite | **C** (Quantitative Intelligence Analyst) |
| Strategic judgment, harm analysis, all-source synthesis | **D** (AI Emerging Risks Analyst) or the **SIA TIA** role (primary) |

> Sources: [Technical Abuse Investigator](https://openai.com/careers/technical-abuse-investigator-san-francisco/) ·
> [Technical Threat Investigator](https://openai.com/careers/technical-threat-investigator-threat-intel-engineering-san-francisco/) ·
> [Quantitative Intelligence Analyst](https://openai.com/careers/quantitative-intelligence-analyst-san-francisco/) ·
> [AI Emerging Risks Analyst](https://openai.com/careers/ai-emerging-risks-analyst-san-francisco/) ·
> [Technical Intelligence Analyst (primary)](https://openai.com/careers/technical-intelligence-analyst-san-francisco/)
