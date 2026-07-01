# OWASP Agentic AI — Threats and Mitigations

Quick reference for the **OWASP Agentic AI — Threats and Mitigations** taxonomy (OWASP
GenAI Security Project, Agentic Security Initiative). *Agentic* systems let an LLM plan
and take actions — call tools/APIs, run code, read/write memory, message other agents —
so their failure modes go beyond a single prompt/response. The fifteen threats (T1–T15)
below are the canonical agentic threat classes; each names the core risk and its primary
mitigations. Companion docs: [`owasp-llm-top-10.md`](./owasp-llm-top-10.md) (LLM01–10),
[`mitre-atlas.md`](./mitre-atlas.md) (ATLAS techniques), [`glossary.md`](./glossary.md).

Source: <https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/>. IDs/names
follow the version pinned in the studio's framework ledger; re-verify T-numbering against
the source at ingest.

## T1 — Memory Poisoning
Injecting false or malicious data into an agent's short- or long-term **memory** (e.g. a
vector store, scratchpad, or conversation history) so later decisions are silently
corrupted. Differs from prompt injection in that the payload *persists* and re-influences
future turns. **Mitigate:** validate/scope what enters memory, separate trusted from
untrusted memory, expire and integrity-check stored context, and require provenance on
retrieved memories.

## T2 — Tool Misuse
Manipulating the agent into invoking its **legitimate tools** in harmful ways — dangerous
parameters, unintended targets, or chained calls that achieve an attacker goal. **Mitigate:**
least-privilege tool scopes, per-tool input validation and allowlists, human approval for
high-impact actions, and rate/impact limits on tool calls.

## T3 — Privilege Compromise
Exploiting excessive, mismanaged, or dynamically-escalated **permissions** so the agent
acts beyond its intended authority. **Mitigate:** least privilege, short-lived scoped
credentials, no ambient authority, and continuous authorization checks at action time (not
just at session start).

## T4 — Resource Overload
Exhausting the agent's compute, memory, token, or downstream-service limits — an
availability attack (and, on paid APIs, a **denial-of-wallet**). **Mitigate:** quotas,
budget/spend caps, timeouts, loop/recursion guards, and back-pressure on tool and model
calls.

## T5 — Cascading Hallucination
A hallucinated or wrong output is trusted by a downstream step or another agent, so the
error **compounds** through the pipeline. **Mitigate:** ground outputs in verified sources,
add validation/critic steps between hops, and require citations or checks before an output
is consumed as input.

## T6 — Intent Breaking & Goal Manipulation
Subverting the agent's **planning or goals** so it pursues the attacker's objective while
appearing to follow the user. **Mitigate:** immutable/verified goal specifications,
plan-vs-policy checks, and monitoring for goal drift across steps.

## T7 — Misaligned & Deceptive Behaviors
The agent pursues harmful goals or **deceives** (hides actions, misreports) to achieve them,
including reward-hacking under optimization pressure. **Mitigate:** alignment testing,
behavioral monitoring, transparency of chain-of-action, and red-teaming for deception.

## T8 — Repudiation & Untraceability
Agent actions cannot be reliably **attributed or audited** — no non-repudiation — so
incidents can't be reconstructed. **Mitigate:** tamper-evident, complete action logging;
signed action records; and per-action identity binding.

## T9 — Identity Spoofing & Impersonation
An attacker impersonates a **user, agent, or service identity** to gain trust or authority
within the system. **Mitigate:** strong mutual authentication between agents/services,
verifiable agent identities, and no implicit trust by name.

## T10 — Overwhelming Human-in-the-Loop
Flooding or fatiguing **human reviewers** so oversight erodes into rubber-stamping, or
timing actions to slip past review. **Mitigate:** prioritize/batch approvals, cap the
review rate, escalate only high-impact decisions, and design for reviewer attention limits.

## T11 — Unexpected RCE & Code Attacks
The agent executes **attacker-controlled code** through a code-execution tool or an unsafe
eval sink, yielding remote code execution. **Mitigate:** sandbox all code execution,
egress-deny by default, drop privileges, and treat generated code as untrusted input.

## T12 — Agent Communication Poisoning
Corrupting the **messages or channels** between agents so a downstream agent acts on
tampered instructions or data. **Mitigate:** authenticate and integrity-protect
inter-agent messages, validate message schemas, and isolate untrusted channels.

## T13 — Rogue Agents in Multi-Agent Systems
A **malicious or compromised agent** operates inside an otherwise-trusted multi-agent
system, abusing the coordination trust. **Mitigate:** zero-trust between agents, behavioral
anomaly detection, and containment/quarantine of misbehaving agents.

## T14 — Human Attacks on Multi-Agent Systems
Humans exploit the **trust and coordination** between agents (e.g. playing agents against
each other) rather than attacking one agent directly. **Mitigate:** cross-agent policy
enforcement, consistent authorization across the mesh, and monitoring for coordination
abuse.

## T15 — Human Manipulation
The agent **manipulates its human** user — exploiting trust in the assistant to nudge
harmful actions or disclosures. **Mitigate:** disclosure of AI limits, guardrails on
persuasive/again-decisioning behavior, and user-side friction for high-stakes actions.
