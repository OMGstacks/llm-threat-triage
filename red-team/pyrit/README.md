# PyRIT — automated prompt-injection probing

[PyRIT](https://github.com/Azure/PyRIT) (Python Risk Identification Tool for
generative AI, from Microsoft) is an open-source framework for **automating the
red-teaming of LLM systems**. Instead of hand-typing jailbreaks one at a time,
you describe:

- a **target** (the model/endpoint under test),
- a set of **attack payloads** (seed prompts, jailbreak templates, mutations),
- a **scorer** (did the response leak/comply/refuse?),

and PyRIT runs the cross-product, records every turn, and tells you which attacks
landed. That turns "I tried a few prompts and one worked" into a repeatable,
measurable harness — the difference between an anecdote and a finding.

## Why this matters for a Technical Intelligence Analyst

A TIA investigates *how LLMs break* — not networks. The flagship project in this
repo (`projects/llm-log-triage`) is the **detection / forensics** half of that
loop: it ingests messy model logs and flags attacks that already happened, mapped
to OWASP LLM Top-10 categories. PyRIT is the **offensive / generation** half:
it produces the adversarial traffic in the first place, under authorization, so
you can measure a guardrail's true bypass rate before an attacker does.

```
   PyRIT (this dir)                         llm-log-triage (flagship)
   ----------------                         -------------------------
   generate injection payloads   --->       detect & triage them in logs
   score guardrail bypass rate              classify by OWASP LLM0x
   produce attack corpus         --->       feed labelled corpus to detectors
```

The two share a vocabulary on purpose. The payload themes in
`prompt_injection_probe.py` (ignore-previous-instructions, DAN, system-prompt
extraction, markdown exfiltration) are the **same attack themes** the flagship
detectors look for. Probe output here is exactly the kind of traffic the triage
pipeline is built to catch — so the offensive and defensive sides validate each
other.

## How this example maps to OWASP LLM01

OWASP **LLM01: Prompt Injection** covers inputs that manipulate an LLM into
ignoring its instructions, revealing its system prompt, or taking
attacker-chosen actions. `prompt_injection_probe.py` exercises four sub-classes
of LLM01:

| Payload theme               | What it attempts                                  | OWASP   |
|-----------------------------|---------------------------------------------------|---------|
| Ignore-previous-instructions| Direct instruction override                       | LLM01   |
| DAN / role-play jailbreak   | Persona-swap to escape the policy                 | LLM01   |
| System-prompt extraction    | Coax the model into printing its hidden prompt    | LLM01 / LLM06 (sensitive-info disclosure) |
| Markdown / link exfiltration| Smuggle data out via a rendered markdown image    | LLM01 / LLM02 (insecure output handling) |

This mirrors the LLM01 dominance in the flagship demo output (LLM01 = 132 of
217 findings) — prompt injection is the single largest attack class in the
sample corpus, which is why it gets the dedicated probe here.

## Install

The default run needs **nothing but the Python standard library** — the script
ships a local `MockTarget` so you can see the full harness work offline.

```bash
python red-team/pyrit/prompt_injection_probe.py
```

To use the real PyRIT framework against a target you are **authorized** to test:

```bash
pip install pyrit            # Python 3.10+ recommended; a venv is strongly advised
```

PyRIT pulls in a fairly large dependency tree (it wraps multiple model SDKs and a
local memory/DB layer), so install it into an isolated environment.

## Running against a real target

By design the script **never calls a real API unless you explicitly opt in.**
The real-target path is gated behind an environment variable and is inactive by
default:

```bash
# 1. Install PyRIT and the provider SDK you need.
pip install pyrit

# 2. Provide credentials for the endpoint you OWN or are AUTHORIZED to test.
export OPENAI_API_KEY="sk-..."
export OPENAI_CHAT_ENDPOINT="https://api.openai.com/v1/chat/completions"

# 3. Flip the explicit opt-in switch.
export PYRIT_PROBE_USE_REAL_TARGET=1

python red-team/pyrit/prompt_injection_probe.py
```

If `PYRIT_PROBE_USE_REAL_TARGET` is unset (the default), the script ignores all
credentials and runs entirely against the in-process mock.

## Authorization — read this first

> This is an **illustrative scaffold**, not a weaponized tool. The bundled
> payloads are deliberately well-known, low-novelty jailbreaks used to
> demonstrate the *measurement workflow*.
>
> Point the real-target path **only** at a model, endpoint, or application you
> own or have **written authorization** to test. Unauthorized probing of a
> third-party LLM service may violate that provider's terms of service and
> applicable law. Red-teaming is a permissioned activity; treat it like one.

## Files

| File                        | Purpose                                                        |
|-----------------------------|----------------------------------------------------------------|
| `prompt_injection_probe.py` | Runnable probe: mock target by default, real PyRIT path gated. |
| `README.md`                 | This file.                                                     |

## Further reading

- OWASP LLM Top-10 summary: [`../../reference/owasp-llm-top-10.md`](../../reference/owasp-llm-top-10.md)
- MITRE ATLAS techniques: [`../../reference/mitre-atlas.md`](../../reference/mitre-atlas.md)
- PyRIT docs: <https://azure.github.io/PyRIT/>
