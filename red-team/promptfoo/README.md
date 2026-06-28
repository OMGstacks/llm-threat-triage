# promptfoo — declarative LLM eval + red-team harness

[promptfoo](https://github.com/promptfoo/promptfoo) is an open-source,
config-driven harness for **evaluating and red-teaming LLM applications**. You
describe your system once in a YAML file:

- the **prompt(s)** under test,
- the **provider(s)** (the model/endpoint being evaluated),
- a **`redteam`** block (what to attack, and how to deliver the attack),
- explicit **`tests`** with **`assert`** blocks (the pass/fail oracle),

and promptfoo runs the matrix, scores every case, and gives you a reproducible
report plus a non-zero exit code on failure — which is what makes it usable as a
CI gate. Where PyRIT (the sibling dir) is a Python framework you script, promptfoo
is the **declarative, CI-native** member of this repo's red-team set: the same
attack themes, expressed as config you can diff and review.

## Why this matters for a Technical Intelligence Analyst

A TIA investigates *how LLMs break*. The flagship project in this repo
(`projects/llm-log-triage`) is the **detection / forensics** half of that loop —
it ingests model logs and flags attacks that already happened, mapped to OWASP
LLM Top-10 categories. promptfoo is part of the **offensive / generation** half:
it manufactures the adversarial traffic, under authorization, so you can measure a
guardrail's bypass rate *before* an attacker does — and produce a labelled attack
corpus the triage detectors can be validated against.

```
   promptfoo (this dir)                     llm-log-triage (flagship)
   --------------------                     -------------------------
   generate adversarial cases    --->       detect & triage them in logs
   assert refusal / bypass rate             classify by OWASP LLM0x
   emit JSON report + exit code  --->       feed labelled corpus to detectors
```

The `redteam` plugins and strategies here exercise the **same OWASP categories**
(LLM01/02/06/07) the flagship detectors look for — so the offensive and defensive
sides share a vocabulary and validate each other.

## What promptfoo is (one line)

A declarative LLM eval + red-team harness: YAML config → CLI/CI run → scored,
reproducible report. It does two related jobs — **eval** (does my prompt meet my
assertions?) and **red-team** (does my system resist adversarial input?).

## Install

promptfoo is a Node tool. No install is required for a one-off run:

```bash
npx promptfoo@latest --help          # run the latest without installing
```

For repeated use, install it globally:

```bash
npm install -g promptfoo             # then: promptfoo --help
```

> **Provider API keys are required to hit a real model.** promptfoo calls the
> provider you name in `providers:` / `targets:`, so export the matching key
> first — e.g. `export OPENAI_API_KEY="sk-..."` or
> `export ANTHROPIC_API_KEY="sk-ant-..."`. Without a key, generation and eval
> against that provider will fail. Point it **only** at a model or application you
> own or are **authorized** to test.

## How `promptfoo redteam` generates adversarial cases

The red-team workflow separates **what to attack** from **how to deliver it**:

- **plugins** = the *vulnerability classes* to probe (e.g. `pii:direct`,
  `prompt-extraction`, `excessive-agency`, the `owasp:llm` collection). Each
  plugin generates seed adversarial prompts targeting that class.
- **strategies** = the *delivery technique* layered on top of the seeds (e.g.
  `prompt-injection`, `jailbreak`, `jailbreak:composite`, `crescendo` for
  multi-turn). A strategy mutates/wraps each seed to evade defenses.

The flow is **generate → eval**:

```bash
promptfoo redteam generate    # plugins x strategies -> a corpus of attack cases
promptfoo redteam eval        # run that corpus against the target, score results
promptfoo redteam run         # convenience: generate + eval in one step
```

`promptfoo redteam init` scaffolds a starter `promptfooconfig.yaml` interactively;
`promptfoo view` opens the local results UI.

## Quickstart commands

```bash
# 1. Scaffold a red-team config interactively.
npx promptfoo@latest redteam init

# 2. Generate + run the red-team suite from a config (this dir's config).
npx promptfoo@latest redteam run -c promptfooconfig.yaml

# 3. Run the plain-eval tests (the hand-written `tests:` with assert blocks).
npx promptfoo@latest eval -c promptfooconfig.yaml

# 4. Browse results in the local web UI.
npx promptfoo@latest view

# 5. CI one-liner: run red-team, write JSON, fail the job on any failing case.
npx promptfoo@latest redteam run -c promptfooconfig.yaml -o results.json
```

## Red-team plugins / strategies → OWASP LLM Top-10

promptfoo distinguishes **plugins** (vulnerability classes) from **strategies**
(delivery techniques) — a common write-up error is calling the jailbreak/injection
deliverers "plugins". The table maps both honestly, and ties each row to the OWASP
category the flagship `llm-log-triage` detectors classify.

| promptfoo id | Kind | What it probes | OWASP LLM id |
|---|---|---|---|
| `prompt-injection` | strategy | Wraps a seed to override system instructions | LLM01 Prompt Injection |
| `jailbreak`, `jailbreak:composite` | strategy | Persona / multi-step escape of the policy | LLM01 Prompt Injection |
| `owasp:llm:01` | plugin collection | Bundled injection-class probes | LLM01 Prompt Injection |
| `pii`, `pii:direct`, `pii:session`, `harmful:privacy` | plugin(s) | Coax disclosure of personal/private data | LLM02 Sensitive Information Disclosure |
| `owasp:llm:02` | plugin collection | Bundled sensitive-info-disclosure probes | LLM02 Sensitive Information Disclosure |
| `excessive-agency`, `rbac`, `hijacking` | plugin(s) | Unauthorized actions / privilege / goal hijack | LLM06 Excessive Agency |
| `owasp:llm:06` | plugin collection | Bundled excessive-agency probes | LLM06 Excessive Agency |
| `prompt-extraction` | plugin | Extract the hidden system prompt | LLM07 System Prompt Leakage |
| `harmful` (e.g. `{id: harmful}`) | plugin | Solicit disallowed / unsafe content | LLM09-class safety / misinformation |
| `owasp:llm` | plugin collection | Run the whole OWASP LLM Top-10 set | LLM01–LLM10 |

> The strings "prompt-injection" and "jailbreak" are **strategies**, not plugins,
> in current promptfoo. The OWASP `owasp:llm:NN` collections are the canonical way
> to pull a whole category's plugin set in one id. See
> [`../../reference/owasp-llm-top-10.md`](../../reference/owasp-llm-top-10.md) for
> the full category definitions.

## CI integration

promptfoo is built to run as a gate. The official GitHub Action:

```yaml
# .github/workflows/redteam.yml
name: LLM red-team
on: [pull_request]
jobs:
  redteam:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: promptfoo/promptfoo-action@v1
        with:
          config: red-team/promptfoo/promptfooconfig.yaml
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

Or a plain step with the CLI — `redteam run` exits **non-zero on any failing
case**, so the job fails the PR automatically:

```yaml
      - run: npx promptfoo@latest redteam run -c red-team/promptfoo/promptfooconfig.yaml -o results.json
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

Add `--tag ci=${{ github.sha }}` to attach CI context to the run for later
correlation. Store the provider key as a repo/org **secret**, never in the config.

## Authorization — read this first

> This is an **illustrative scaffold**, not a weaponized tool. The bundled
> red-team plugins and the explicit `tests` use deliberately well-known,
> low-novelty attack themes to demonstrate the *measurement workflow*.
>
> Point the providers/targets **only** at a model, endpoint, or application you
> own or have **written authorization** to test. Unauthorized probing of a
> third-party LLM service may violate that provider's terms of service and
> applicable law. Red-teaming is a permissioned activity; treat it like one.

## Files

| File | Purpose |
|---|---|
| `promptfooconfig.yaml` | Commented, schema-accurate eval + red-team config. |
| `README.md` | This file. |

## Further reading

- OWASP LLM Top-10 summary: [`../../reference/owasp-llm-top-10.md`](../../reference/owasp-llm-top-10.md)
- MITRE ATLAS techniques: [`../../reference/mitre-atlas.md`](../../reference/mitre-atlas.md)
- Sibling offensive harness (Python): [`../pyrit/README.md`](../pyrit/README.md)
- promptfoo docs: <https://www.promptfoo.dev/docs/red-team/>

---
*Verified against promptfoo.dev / GitHub source docs (`promptfoo/promptfoo`), June 2026.*
