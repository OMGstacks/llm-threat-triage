# Cover letter — Technical Intelligence Analyst, Strategic Intelligence & Analysis (OpenAI)

> Fill the `[brackets]` with your specifics. The project paragraph is factual — it
> describes this repo, which the reader can open and run. Keep the full letter to one page.

---

## Full letter

Dear Hiring Manager,

I'm applying for the Technical Intelligence Analyst role on the Strategic Intelligence &
Analysis team. The part of the mission that pulls me in is the forward-looking one —
surfacing novel harms and abuse patterns and turning them into intelligence that actually
changes safety mitigations and product decisions. That's the work I've been teaching myself
to do, and rather than just describe it, I built it.

`openai-tia-prep` (github.com/OMGstacks/openai-tia-prep) is a working LLM-threat-detection
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

That instinct comes from my background in [security / incident management]. For [N years] I've
[triaged high-severity incidents / assigned severity under ambiguity / driven root-cause analysis
and escalation] — [add one concrete, quantified win, e.g. "cut mean time-to-triage by X%"]. The
domain is shifting from how networks break to how models break, but the core is identical:
ingest noisy signals, separate confirmed from suspected, prioritize by impact, and hand
leadership a decision, not a payload.

What draws me specifically to OpenAI and SIA is [one or two genuine sentences — e.g. the chance
to do this at the frontier, where the harms are novel and the stakes are real, and where
intelligence directly informs how powerful systems are deployed]. I'd bring an investigative
mindset, real SQL and Python, fluency in the LLM-threat frameworks, and a demonstrated habit of
turning a zero-to-one analysis into a reusable tool.

Thank you for your consideration — I'd welcome the chance to walk through the project live.

[Your name]
[email] · [phone] · github.com/OMGstacks

---

## Short version (application form / "why you?" box, ~120 words)

I build the thing instead of just claiming it. `openai-tia-prep`
(github.com/OMGstacks/openai-tia-prep) is a working Python + SQL pipeline that ingests messy LLM
logs and flags prompt injection, jailbreaks, and data exfiltration — nine detectors, every
finding mapped to OWASP LLM Top 10 (2025) + MITRE ATLAS, plus SQL anomaly queries for novel /
low-prevalence patterns. 800 events → 150 flagged / 217 findings, 83 tests, CI; I red-teamed my
own detectors and fixed the bugs. It's exactly the SIA loop — surface novel harms, turn them
into structured, decision-ready intelligence. I pair it with [N years] in [security / incident
management]: triage, severity, evidence, escalation, RCA — the same instincts, applied to how
models break instead of networks.

---

## Referral / cold-email blurb (3 sentences)

I'm targeting the Technical Intelligence Analyst role on OpenAI's Strategic Intelligence &
Analysis team. To show I can do the day-to-day, I built `openai-tia-prep` — a tested Python + SQL
pipeline that triages messy LLM logs for prompt injection, jailbreaks, and exfiltration, mapped
to OWASP LLM Top 10 + MITRE ATLAS, with SQL anomaly detection for novel patterns
(github.com/OMGstacks/openai-tia-prep). Combined with [N years] in [security / incident
management], it's the investigative-mindset-plus-Python/SQL profile the role asks for — could you
point me to the right person or refer me in?
