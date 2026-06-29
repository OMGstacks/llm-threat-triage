# Cover letter — Technical Intelligence Analyst, Strategic Intelligence & Analysis (OpenAI)

> Personalized for Izu Uhiara. The project paragraph is factual — it describes this repo,
> which the reader can open and run. The current employer is anonymized for the public repo;
> swap in the real name for versions you submit directly. Keep the full letter to one page.

---

## Full letter

Dear Hiring Manager,

I'm applying for the Technical Intelligence Analyst role on the Strategic Intelligence &
Analysis team. The part of the mission that pulls me in is the forward-looking one —
surfacing novel harms and abuse patterns and turning them into intelligence that actually
changes safety mitigations and product decisions. That's the work I've been teaching myself
to do, and rather than just describe it, I built it.

`llm-threat-triage` (github.com/OMGstacks/llm-threat-triage) is a working LLM-threat-detection
pipeline in Python and SQL. It ingests deliberately messy LLM interaction logs, normalizes
them, and flags adversarial activity — prompt injection (direct, indirect, and base64/leetspeak-
obfuscated), jailbreaks, system-prompt extraction, excessive agency, and data exfiltration —
with nine channel-aware detectors, every finding mapped to the OWASP LLM Top 10 (2025) and
MITRE ATLAS. On an 800-event sample it flags 150 events / 217 findings, ranks them by severity,
surfaces repeat offenders, and includes SQL anomaly queries for unbounded-consumption and
multi-turn attack patterns — the low-prevalence signals that signatures miss. It ships with 83
tests, CI, and red-team scaffolds (PyRIT, garak, promptfoo). I also ran an adversarial review
of my own detectors and fixed real bugs — a timestamp parser silently corrupting dates, rules
that fired on the wrong role, and evasions that bypassed every regex — because a detection tool
you haven't tried to break isn't one you can trust.

That instinct isn't new for me. For **20 years** I've worked in major-incident command and security
operations — most recently as **AVP, Security Incident Management** in a global bank's CISO
organization, and before that running enterprise major-incident command for a national telecom
(T-Mobile). My day-to-day is triaging high-severity incidents under ambiguity, assigning severity,
driving root-cause analysis, and owning executive escalation — and, increasingly, designing
governed, AI-assisted workflows for how those incidents get analyzed. The signals are shifting from
how networks break to how models break, but the core is identical: ingest noisy inputs, separate
confirmed from suspected, prioritize by impact, and hand leadership a decision, not a payload.

What draws me specifically to OpenAI and SIA is that it's the same investigative work I've done
for years — monitor, analyze, forecast abuse — but at the frontier, where the harms are novel and
the intelligence directly informs how powerful systems are deployed. Governing AI use cases inside
a CISO organization gave me a close-up view of how fast these risks emerge and how little prior art
exists to lean on; I want to do that work where it matters most. I'd bring an investigative
mindset, CompTIA Security+ and real SQL and Python, fluency in the LLM-threat frameworks, and a
demonstrated habit of turning a zero-to-one analysis into a reusable tool.

Thank you for your consideration — I'd welcome the chance to walk through the project live.

Izu Uhiara
izu.uhiara@gmail.com · github.com/OMGstacks · linkedin.com/in/izu-uhiara-177b1052

---

## Short version (application form / "why you?" box, ~120 words)

I build the thing instead of just claiming it. `llm-threat-triage`
(github.com/OMGstacks/llm-threat-triage) is a working Python + SQL pipeline that ingests messy LLM
logs and flags prompt injection, jailbreaks, and data exfiltration — nine detectors, every
finding mapped to OWASP LLM Top 10 (2025) + MITRE ATLAS, plus SQL anomaly queries for novel /
low-prevalence patterns. 800 events → 150 flagged / 217 findings, 83 tests, CI; I red-teamed my
own detectors and fixed the bugs. It's exactly the SIA loop — surface novel harms, turn them
into structured, decision-ready intelligence. I pair it with 20 years in operations and
incident management — now AVP, Security Incident Management in a global bank's CISO org, where I
also lead AI enablement: triage, severity, evidence, escalation, RCA — the same instincts, applied
to how models break instead of networks.

---

## Referral / cold-email blurb (3 sentences)

I'm targeting the Technical Intelligence Analyst role on OpenAI's Strategic Intelligence &
Analysis team. To show I can do the day-to-day, I built `llm-threat-triage` — a tested Python + SQL
pipeline that triages messy LLM logs for prompt injection, jailbreaks, and exfiltration, mapped
to OWASP LLM Top 10 + MITRE ATLAS, with SQL anomaly detection for novel patterns
(github.com/OMGstacks/llm-threat-triage). Combined with 20 years in incident management —
currently AVP, Security Incident Management, plus AI-enablement leadership in a CISO org — it's the
investigative-mindset-plus-Python/SQL profile the role asks for — could you point me to the right
person or refer me in?
