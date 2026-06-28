# MITRE ATLAS — Reference for LLM Log Triage

> **What this is.** A working reference for the ATLAS techniques this repo's detectors map
> to, plus the verified-current technique ids. Verified against the public ATLAS knowledge
> base and the MISP ATLAS galaxy mirror (June 2026). Where the official site
> ([atlas.mitre.org](https://atlas.mitre.org)) blocks automated fetch, names are
> cross-checked across the MISP galaxy JSON and multiple secondary trackers — items still
> worth a manual confirm against atlas.mitre.org are flagged inline.

## What ATLAS is

**MITRE ATLAS** (Adversarial Threat Landscape for Artificial-Intelligence Systems) is a
living knowledge base of adversary **tactics** (the *why* — the attacker's goal at a step)
and **techniques** (the *how* — the method used), specific to AI/ML-enabled systems. It is
modeled on MITRE ATT&CK and backed by real-world case studies.

### ATLAS vs ATT&CK — and why a TIA uses both

| | MITRE ATT&CK | MITRE ATLAS |
|---|---|---|
| Target | Enterprise IT: hosts, networks, identities | AI/ML systems: models, training data, prompts, inference APIs, agent tools |
| Tactics | 14 enterprise tactics | Reuses most ATT&CK tactics **+** two AI-specific ones: **ML Model Access** and **ML Attack Staging** |
| Technique ids | `T####` | `AML.T####` (with `.###` sub-techniques) |
| Example | Phishing (`T1566`) | LLM Prompt Injection (`AML.T0051`) |

ATLAS **complements** ATT&CK rather than replacing it: a real attack on an LLM-backed
product often chains both — e.g. ATT&CK Initial Access to reach the app, then ATLAS
`AML.T0051` to subvert the model. As a Technical Intelligence Analyst, ATLAS gives a shared
vocabulary to (1) classify an observed LLM abuse, (2) crosswalk it to OWASP LLM Top 10 for
the product-risk view, and (3) communicate it to a SOC that already speaks ATT&CK.

> **Versioning caveat (load-bearing).** ATLAS technique **names** change between releases
> even when the **id is stable**. The 2025 generative-AI expansion renamed several techniques
> (notably the broad `ML → AI` rename, plus `AML.T0053` and `AML.T0056`). Always treat the
> **id** as the join key and re-verify the **name** against the current matrix. This repo's
> detectors hardcode ids; this doc records the verified-current name for each.

## ATLAS tactics (matrix columns)

The tactics below are the lifecycle stages an AI-system adversary moves through. The two
**AI-specific** tactics are marked.

| Tactic | One-line description |
|---|---|
| Reconnaissance | Gather information on the target AI system, its data, architecture, and weaknesses. |
| Resource Development | Acquire/build capabilities — datasets, models, infrastructure, accounts — to stage an attack. |
| Initial Access | Gain a foothold in the AI system or its surrounding environment. |
| **ML Model Access** *(AI-specific)* | Obtain access to the model itself — via inference API, physical access, or the artifact. |
| Execution | Run adversary-controlled code or instructions (incl. via prompts / agent tools). |
| Persistence | Maintain access across restarts/retraining (e.g. poisoned data, backdoors). |
| Privilege Escalation | Gain higher permissions within the AI environment (e.g. via a compromised agent tool). |
| Defense Evasion | Avoid detection by AI defenses, filters, or guardrails. |
| Credential Access | Steal credentials/secrets reachable through the AI system. |
| Discovery | Explore the environment the model/agent can reach. |
| Collection | Gather data of interest (model outputs, artifacts, connected data). |
| **ML Attack Staging** *(AI-specific)* | Prepare model-targeting attacks — proxy/shadow models, crafted adversarial data, verification. |
| Exfiltration | Steal AI artifacts or information (training data, model, secrets) out of the system. |
| Impact | Degrade, manipulate, or destroy AI system availability/integrity, or achieve the end goal. |

> Tactic **count** varies by source (commonly cited as 14, sometimes 16 depending on release
> and whether sub-groupings are counted). Treat the list above as the stable backbone and
> confirm the exact current set at atlas.mitre.org.

## Key techniques for LLM abuse

Ids verified current (June 2026). **Name (current)** is what the live matrix shows; where it
differs from the label hardcoded in `detectors.py`, the old label is noted.

| Technique id | Name (current) | Tactic(s) | How it shows up in logs |
|---|---|---|---|
| `AML.T0051` | LLM Prompt Injection | Defense Evasion / Initial Access / Execution | User or upstream content that overrides the system prompt or injects new instructions. |
| `AML.T0051.000` | LLM Prompt Injection: **Direct** | (as parent) | The end user types the override directly into the chat ("ignore previous instructions"). |
| `AML.T0051.001` | LLM Prompt Injection: **Indirect** | (as parent) | Injection arrives via an untrusted channel the model ingests (RAG doc, tool output, email, web page). |
| `AML.T0054` | LLM Jailbreak | Defense Evasion / Privilege Escalation | Persona/roleplay or "no-restrictions" framing (DAN, "developer mode") to bypass guardrails. |
| `AML.T0056` | **LLM Meta Prompt Extraction** *(was "Extract LLM System Prompt")* | Discovery / Exfiltration | User probing to reveal the hidden system/meta prompt ("repeat the words above", "what are your instructions"). |
| `AML.T0053` | **AI Agent Tool Invocation** *(was "LLM Plugin Compromise")* | Execution / Privilege Escalation | Coercing connected tools/plugins/agents into destructive or unintended actions. |
| `AML.T0057` | LLM Data Leakage | Exfiltration | Model output containing secrets/PII the user should not receive (training data, other users' data, injected secrets). |
| `AML.T0024` | **Exfiltration via AI Inference API** *(was "...via ML Inference API")* | Exfiltration | Abuse of the inference interface to extract data/model info; in app logs, also covers output-channel exfil (markdown-image beacons, active content). |
| `AML.T0024.000` | Exfiltration via AI Inference API: Infer Training Data Membership | Exfiltration | Repeated probing queries designed to test whether a record was in the training set. |
| `AML.T0024.001` | Exfiltration via AI Inference API: Invert ML Model | Exfiltration | Query patterns reconstructing training inputs from outputs. |
| `AML.T0024.002` | Exfiltration via AI Inference API: Extract ML Model | Exfiltration | Systematic querying to clone model behavior. |

## Detector → ATLAS crosswalk

For each detector in [`projects/llm-log-triage/src/detectors.py`](../projects/llm-log-triage/src/detectors.py):
the OWASP LLM Top 10 mapping, the ATLAS id, and the **status** of the id/name currently
hardcoded in the source.

| Detector | OWASP LLM (2025) | ATLAS id (hardcoded) | ATLAS name (current) | Status |
|---|---|---|---|---|
| `direct_prompt_injection` | LLM01 Prompt Injection | `AML.T0051.000` | LLM Prompt Injection: Direct | ✅ id + name current |
| `indirect_prompt_injection` | LLM01 Prompt Injection | `AML.T0051.001` | LLM Prompt Injection: Indirect | ✅ id + name current |
| `jailbreak_persona_override` | LLM01 Prompt Injection | `AML.T0054` | LLM Jailbreak | ✅ id + name current |
| `system_prompt_extraction` | LLM07 System Prompt Leakage | `AML.T0056` | LLM Meta Prompt Extraction | ✅ id + name current (code updated from "Extract LLM System Prompt") |
| `excessive_agency_probe` | LLM06 Excessive Agency | `AML.T0053` | AI Agent Tool Invocation | ✅ id + name current (code updated from "LLM Plugin Compromise") |
| `sensitive_information_disclosure` | LLM02 Sensitive Information Disclosure | `AML.T0057` | LLM Data Leakage | ✅ id + name current |
| `sensitive_information_inbound` | LLM02 Sensitive Information Disclosure | `AML.T0057` | LLM Data Leakage | ✅ id + name current (untrusted-inbound twin of the disclosure detector) |
| `encoded_injection_payload` | LLM01 Prompt Injection | `AML.T0051.001` | LLM Prompt Injection: Indirect | ✅ id + name current (decoded base64/hex tripping an injection signature) |
| `suspicious_encoded_blob` | LLM01 Prompt Injection | `AML.T0051.001` | LLM Prompt Injection: Indirect | ✅ id + name current (high-entropy blob in untrusted content; emitted by the encoded-payload detector) |
| `improper_output_handling` | LLM05 Improper Output Handling | `AML.T0024` | Exfiltration via AI Inference API | ✅ id + name current (code updated from `AML.T0024.000` parent-promoted; ML→AI rename) |

### Notes on the previously-flagged rows (now resolved)

The code has been updated; these notes record *why* each name/id is what it is.

- **`system_prompt_extraction` → `AML.T0056`**: id is correct and current. The technique was
  **renamed** from *"Extract LLM System Prompt"* to *"LLM Meta Prompt Extraction"*. The display
  string in `detectors.py` now matches the current name; the id was already correct.
- **`excessive_agency_probe` → `AML.T0053`**: id is correct and current. The technique was
  **renamed** from *"LLM Plugin Compromise"* to *"AI Agent Tool Invocation"* in the 2025
  generative-AI/agent expansion. The display string now matches; id unchanged.
- **`improper_output_handling` → `AML.T0024`**: the hardcoded id was promoted from the
  `AML.T0024.000` sub-technique to the **parent** `AML.T0024` *Exfiltration via AI Inference API*.
  Rationale: `AML.T0024.000` is specifically *Infer Training Data Membership* (a membership-inference
  attack), which does **not** describe markdown-image/link exfil URLs or active content
  (`<script>`, `onerror=`, `javascript:`) in model output. Those are an **output-channel
  exfiltration** behavior. Improper output handling is also fundamentally a **downstream-consumer**
  vulnerability (OWASP LLM05's actual framing: the app renders model output unsafely), and ATLAS
  has no exact 1:1 for "the host app fails to sanitize model output," so the honest mapping is the
  parent `AML.T0024` (with the ML→AI rename applied), not the `.000` sub-technique.

## Summary of code-correction actions (applied)

```text
detectors.py — ATLAS field updates (applied; ids stable unless noted):
  system_prompt_extraction : name  "Extract LLM System Prompt" -> "LLM Meta Prompt Extraction"   (AML.T0056)  ✓ done
  excessive_agency_probe   : name  "LLM Plugin Compromise"     -> "AI Agent Tool Invocation"      (AML.T0053)  ✓ done
  improper_output_handling : id    "AML.T0024.000"             -> "AML.T0024"                                   ✓ done
                             name  "Exfiltration via ML Inference API" -> "Exfiltration via AI Inference API"  ✓ done
  (the broad ML->AI rename on the AML.T0024 parent name is reflected everywhere it is displayed)
All detector ids/names now match the verified-current ATLAS matrix.
```

## Sources

- [MITRE ATLAS (official)](https://atlas.mitre.org) — authoritative; verify names here on update.
- [MISP ATLAS attack-pattern galaxy](https://misp-galaxy.org/mitre-atlas-attack-pattern/) — machine-readable mirror used for id↔name verification.
- [MITRE ATLAS topic overview — Vectra AI](https://www.vectra.ai/topics/mitre-atlas)
- [AI Agent Tool Invocation (AML.T0053) — startupdefense.io](https://www.startupdefense.io/mitre-atlas-techniques/aml-t0053-ai-agent-tool-invocation-40f9c)
- [Exfiltration via AI Inference API (AML.T0024) — startupdefense.io](https://www.startupdefense.io/mitre-atlas-techniques/aml-t0024-exfiltration-via-ai-inference-api-a964f)
- [atlas-data CHANGELOG (release/rename history)](https://github.com/mitre-atlas/atlas-data/blob/main/CHANGELOG.md)
