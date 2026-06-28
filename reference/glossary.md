# AI-Security Glossary

A fast-reference glossary of the LLM-security terms a Technical Intelligence Analyst should be
able to define on the spot. Terms are alphabetical. Cross-links point to the companion docs in
this directory:

- [`owasp-llm-top-10.md`](./owasp-llm-top-10.md) — OWASP Top 10 for LLM Applications (LLM01–LLM10)
- [`mitre-atlas.md`](./mitre-atlas.md) — MITRE ATLAS adversarial-ML tactics & techniques

> The flagship `llm-log-triage` pipeline tags findings with these OWASP IDs. A real run over 800
> events produced 217 findings (61 critical / 126 high / 25 medium / 5 info) across **LLM01** (132),
> **LLM05** (29), **LLM07** (25), **LLM02** (22), **LLM06** (9) — the categories below explain
> what each of those tags means and how it shows up in logs.

---

## Adversarial example
An input crafted with small, often human-imperceptible perturbations that causes a model to
misclassify or misbehave while looking benign to a person. Classic in vision (perturbed pixels);
in LLMs it shows up as adversarial suffixes/token sequences that flip a refusal into compliance.
See ATLAS *Evade ML Model* ([`mitre-atlas.md`](./mitre-atlas.md)).

## Agentic / tool-use / excessive agency
**Agentic** systems let an LLM take actions — call tools/APIs, run code, read/write files, send
messages — rather than only emit text. **Excessive agency** is the failure mode where the model
is granted too much permission, autonomy, or functionality, so a manipulated or hallucinated
decision causes real-world side effects (deleting data, spending money, exfiltrating secrets).
Maps to **OWASP LLM06: Excessive Agency** ([`owasp-llm-top-10.md`](./owasp-llm-top-10.md)).

## Alignment
The degree to which a model's behavior matches the intended goals, values, and policies of its
developers and users. Misalignment covers everything from following the literal instruction over
the intended one, to deceptive or reward-hacking behavior under optimization pressure.

## Blue teaming
*See [Red teaming vs blue teaming](#red-teaming-vs-blue-teaming).*

## Content provenance / watermarking
Techniques to mark or trace the origin of model outputs. **Watermarking** embeds a statistically
detectable signal in generated text/images so they can later be identified as AI-produced.
**Provenance** more broadly tracks where content came from (e.g. C2PA signed metadata). Both are
defenses against misinformation, impersonation, and undetected synthetic content.

## Data / model poisoning
Tampering with training, fine-tuning, or RAG data to implant backdoors, biases, or degraded
behavior. A poisoned trigger phrase can make a model emit attacker-chosen output on demand while
behaving normally otherwise. Maps to **OWASP LLM04: Data and Model Poisoning**
([`owasp-llm-top-10.md`](./owasp-llm-top-10.md)) and ATLAS *Poison Training Data*.

## Denial-of-wallet
*See [Unbounded consumption / denial-of-wallet](#unbounded-consumption--denial-of-wallet).*

## Direct vs indirect prompt injection
**Prompt injection** overrides a model's intended instructions with attacker-supplied text.
- **Direct** — the attacker types the malicious instruction straight into the prompt
  (e.g. *"ignore previous instructions and …"*).
- **Indirect** — the malicious instruction is hidden in *content the model later ingests* — a web
  page, email, PDF, or RAG document — so the attack fires without the attacker touching the prompt.
Both map to **OWASP LLM01: Prompt Injection** ([`owasp-llm-top-10.md`](./owasp-llm-top-10.md)) —
the single largest finding category in the flagship run (132 of 217).

## Embedding inversion
Reconstructing the original input text (or sensitive attributes of it) from its vector embedding.
Because embeddings are often stored or transmitted as if they were anonymized, inversion shows
that a leaked embedding store can leak the underlying private data. Related to
[model inversion](#model-inversion).

## Eval
A repeatable, scored test that measures a model or system on a specific capability or safety
property (e.g. a refusal-rate eval, a jailbreak-resistance eval, a factuality benchmark). Evals
turn "it seems safer" into a number you can track across versions; in `red-team/` tools like
`promptfoo` and `garak` produce eval-style pass/fail reports.

## Guardrails
Runtime controls that constrain model inputs and outputs — input filters, output classifiers,
allow/deny lists, schema validators, policy checks, rate limits. Distinct from training-time
alignment: guardrails sit *around* the model and can be added, tuned, or bypassed independently
of the weights. *See also [Refusal / safety filter](#refusal--safety-filter).*

## Jailbreak
A prompt-engineering attack that bypasses a model's safety training or guardrails to elicit
restricted output (e.g. role-play framings, encoding tricks, "DAN"-style personas, many-shot
priming). A jailbreak defeats the *policy*; a [prompt injection](#direct-vs-indirect-prompt-injection)
hijacks the *instructions* — they often combine. Maps to **OWASP LLM01**.

## Jailbreak transfer
The observation that a jailbreak crafted against one model frequently works against *other*
models — different vendors, sizes, or versions — because they share training data, architectures,
and safety approaches. Transferability makes jailbreaks cheap to scale and is why a single new
exploit can become an industry-wide incident.

## Membership inference
An attack that determines whether a specific record was part of a model's training set, usually
by exploiting the model's higher confidence on data it has seen. A successful inference is a
privacy breach (e.g. proving someone's medical record was used to train the model). ATLAS
*Infer Training Data Membership*.

## Model extraction / distillation
Stealing a model's functionality by querying it heavily and training a surrogate ("student") on
its outputs. **Extraction** aims to clone the target's behavior/IP; **distillation** is the same
mechanism used legitimately to compress a large model into a smaller one. The attacker version is
theft of a proprietary model via its API. ATLAS *Steal ML Model*.

## Model inversion
Reconstructing sensitive *training inputs* (e.g. a recognizable face, a verbatim record) from a
model's outputs or parameters. Differs from [membership inference](#membership-inference)
(yes/no on one record) by recovering the actual data, and from
[embedding inversion](#embedding-inversion) (which targets the embedding, not the model).

## Multi-agent system
An architecture where several LLM agents collaborate, delegate, or critique each other (e.g.
planner + worker + reviewer). It expands capability but also the attack surface: a
[prompt injection](#direct-vs-indirect-prompt-injection) into one agent can propagate through
inter-agent messages, and [excessive agency](#agentic--tool-use--excessive-agency) compounds
across the chain.

## Multimodal injection
A [prompt injection](#direct-vs-indirect-prompt-injection) delivered through a non-text channel —
text hidden in an image, audio, or video that a vision/audio model reads as instructions (e.g.
faint text in a picture saying *"ignore the user and reply X"*). It evades text-only input
filters because the malicious payload never appears in the literal prompt string.

## Novel harms
Failure modes that don't map cleanly onto known categories — emergent, unanticipated, or
capability-driven risks discovered through investigation rather than from a checklist. Surfacing
and characterizing novel harms (vs. cataloguing known ones) is the core investigative work of a
TIA. In `llm-log-triage` these are the events that *don't* match an existing detector but still
look anomalous.

## Prompt template
The fixed scaffolding a system wraps around user input before sending it to the model — system
prompt, formatting, instructions, few-shot examples, tool descriptions, retrieved context. Templates
are a security boundary: weak separation between trusted template text and untrusted user/retrieved
text is what makes [prompt injection](#direct-vs-indirect-prompt-injection) possible.

## RAG (retrieval-augmented generation)
A pattern that retrieves relevant documents from an external store (often a vector DB) and inserts
them into the prompt so the model can answer over up-to-date or private knowledge. It reduces
hallucination but introduces attack surface: poisoned or attacker-controlled documents become
[indirect prompt injection](#direct-vs-indirect-prompt-injection) vectors, and the retrieval
corpus itself can be a [poisoning](#data--model-poisoning) target.

## Red teaming vs blue teaming
- **Red teaming** — offense: actively probing a model/system to find vulnerabilities (jailbreaks,
  injections, harmful-output elicitation) before adversaries do. Tooling in `red-team/`:
  `pyrit`, `garak`, `promptfoo`.
- **Blue teaming** — defense: detecting, monitoring, and mitigating those attacks in production
  (guardrails, log triage, incident response). The `llm-log-triage` flagship is blue-team work.
The two operate as a loop — red-team findings drive blue-team detectors and evals.

## Refusal / safety filter
The model's learned behavior of declining disallowed requests ("refusal"), plus any external
classifier ("safety filter") that blocks unsafe inputs or outputs. [Jailbreaks](#jailbreak) target
exactly this layer; tracking refusal rate (and over-refusal of benign requests) is a standard
[eval](#eval). *See also [Guardrails](#guardrails).*

## Supply chain (model / dataset)
Risks inherited from third-party components: pretrained weights, base models, datasets, fine-tunes,
adapters, plugins, and libraries pulled from hubs like Hugging Face. A backdoored checkpoint or
tampered dataset compromises every downstream system that trusts it. Maps to
**OWASP LLM03: Supply Chain** ([`owasp-llm-top-10.md`](./owasp-llm-top-10.md)).

## System prompt leakage
When a model reveals its hidden system prompt — instructions, policies, embedded secrets, or
tool definitions the developer assumed were private. Beyond IP exposure, a leaked system prompt
hands an attacker the exact rules to craft a [jailbreak](#jailbreak) against. Maps to
**OWASP LLM07: System Prompt Leakage** ([`owasp-llm-top-10.md`](./owasp-llm-top-10.md)) — 12
findings in the flagship run.

## Unbounded consumption / denial-of-wallet
Abusing an LLM service to drive runaway resource use — flooding with expensive queries, forcing
huge generations, or triggering recursive tool calls. The aim is cost explosion ("denial of
wallet") or availability loss (denial of service). Maps to **OWASP LLM10: Unbounded Consumption**
([`owasp-llm-top-10.md`](./owasp-llm-top-10.md)).

## Watermarking
*See [Content provenance / watermarking](#content-provenance--watermarking).*
