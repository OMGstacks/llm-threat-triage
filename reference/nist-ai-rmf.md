# NIST AI Risk Management Framework (AI RMF 1.0) + GenAI Profile (AI 600-1)

Quick reference for the **NIST AI Risk Management Framework 1.0** and its **Generative AI
Profile (NIST AI 600-1)**. Where OWASP/ATLAS catalog *attacks*, the AI RMF is the
*governance* frame a red-team report maps risk and remediation onto. Companion docs:
[`owasp-llm-top-10.md`](./owasp-llm-top-10.md), [`mitre-atlas.md`](./mitre-atlas.md),
[`owasp-agentic-threats.md`](./owasp-agentic-threats.md), [`glossary.md`](./glossary.md).

Sources: AI RMF 1.0 <https://www.nist.gov/itl/ai-risk-management-framework> · GenAI Profile
<https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence>.

## AI RMF core functions
The framework organizes AI risk work into four core functions, applied iteratively across
the AI lifecycle:
- **GOVERN** — cultivate a culture of risk management: policies, accountability, roles,
  and oversight structures that make the other three functions actually happen.
- **MAP** — establish context and identify risks: intended use, actors, and the ways the
  system could cause harm, so risks are framed before they are measured.
- **MEASURE** — analyze, assess, benchmark, and monitor identified risks using quantitative
  and qualitative methods (including red-teaming and evaluations).
- **MANAGE** — prioritize and act on measured risks: allocate resources, apply treatments,
  and respond to and recover from incidents.

GOVERN is cross-cutting; MAP → MEASURE → MANAGE form the operational loop.

## Trustworthy AI characteristics
The RMF frames trustworthy AI as **valid and reliable** (the foundation), plus **safe**,
**secure and resilient**, **accountable and transparent**, **explainable and
interpretable**, **privacy-enhanced**, and **fair — with harmful bias managed**. Red-team
findings are often expressed as a failure of one or more of these characteristics.

## GenAI Profile (AI 600-1) — the twelve risks
The Generative AI Profile enumerates twelve risks that are novel to, or amplified by,
generative AI. A red-team report can tag findings to these categories:
1. **CBRN Information or Capabilities** — lowered barriers to chemical/biological/radiological/nuclear harm.
2. **Confabulation** — confidently stated false or fabricated content ("hallucination").
3. **Dangerous, Violent, or Hateful Content** — generation of content that enables or incites harm.
4. **Data Privacy** — leakage or inference of personal/sensitive data from training or context.
5. **Environmental Impacts** — energy/compute cost of training and inference.
6. **Harmful Bias or Homogenization** — biased outputs, or convergence that erases diversity.
7. **Human-AI Configuration** — over-reliance, automation bias, or misaligned human-system roles.
8. **Information Integrity** — mis/disinformation at scale, including synthetic media.
9. **Information Security** — expanded attack surface (prompt injection, model theft, insecure output handling).
10. **Intellectual Property** — training-data provenance, copyright, and generated-content ownership.
11. **Obscene, Degrading, and/or Abusive Content** — including non-consensual and CSAM-adjacent material.
12. **Value Chain and Component Integration** — third-party model/data/tool supply-chain risk.

## How it maps to the attack frameworks
NIST AI RMF is complementary, not a substitute: **Information Security** (risk 9) is where
most OWASP LLM Top 10 and MITRE ATLAS findings land; **Confabulation** aligns with OWASP
LLM09 misinformation; **Value Chain and Component Integration** aligns with OWASP LLM03
supply chain; **Data Privacy** with LLM02 sensitive-information disclosure. A good report
cites the specific attack (OWASP/ATLAS) *and* the governance risk (RMF) it realizes.
