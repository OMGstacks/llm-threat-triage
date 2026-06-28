# garak — LLM vulnerability scanner

[garak](https://github.com/NVIDIA/garak) (Generative AI Red-teaming &
Assessment Kit, from NVIDIA) is an open-source **LLM vulnerability scanner** —
think `nmap` for language models. You point it at a model, it fires a large
library of known attacks (150+ probes, thousands of prompts), and it tells you
which ones landed. Instead of hand-typing jailbreaks one at a time, garak runs
the whole battery, judges every response automatically, and emits a structured
report you can diff between model versions.

## Why this matters for a Technical Intelligence Analyst

A TIA investigates *how LLMs break* — not networks. The flagship project in this
repo (`projects/llm-log-triage`) is the **detection / forensics** half of that
loop: it ingests messy model logs and flags attacks that already happened, mapped
to OWASP LLM Top-10 categories. garak is one of the **offensive / generation**
halves: it produces a known, labelled stream of adversarial traffic — under
authorization — so you can measure a guardrail's true bypass rate and benchmark
one model against another before an attacker does.

```
   garak (this dir)                         llm-log-triage (flagship)
   ----------------                         -------------------------
   fire 150+ known probes        --->       detect & triage them in logs
   auto-judge each response                 classify by OWASP LLM0x
   emit JSONL pass/fail report   --->       feed labelled corpus to detectors
```

It sits alongside the `pyrit/` scaffold: PyRIT is a *framework* for composing
your own attacks turn-by-turn; garak is a *batteries-included scanner* you run as
one command for broad, repeatable coverage. A TIA wants both — bespoke and broad.

## Install

```bash
python -m pip install -U garak        # Python 3.10+; a venv is strongly advised
```

Bleeding-edge (tracks the probe library closely):

```bash
python -m pip install -U "git+https://github.com/NVIDIA/garak.git@main"
```

Provide credentials only for an endpoint you own or are authorized to test:

```bash
export OPENAI_API_KEY="sk-..."        # for the openai target type
```

## Mental model — four plugin types

garak is plugin-based. Four families do the work, plus two that orchestrate:

- **Generators** — the model adapters. They take a prompt and return a response.
  One per backend: `openai`, `huggingface`, `ollama`, `ggml`, `rest`, `test`
  (a no-cost mock), and more. This is the *target* under test.
- **Probes** — the attacks. Each probe assembles and sends adversarial prompts
  (e.g. `promptinject`, `dan`, `encoding`, `leakreplay`). A probe is "one family
  of attack."
- **Detectors** — the judges. After a probe sends prompts, detectors score each
  response: did the attack succeed? (e.g. did the model emit the toxic string,
  comply with the jailbreak, leak the replayed text?) garak auto-selects sensible
  detectors per probe unless you override.
- **Buffs** — prompt mutators applied in-flight: paraphrase, lowercase, encode,
  translate. A buff multiplies a probe's prompts into variants to test robustness.

Two more glue pieces, worth knowing by name:

- **Harness** — orchestrates the probe → generator → detector loop.
- **Evaluator** — aggregates detector scores into pass/fail per probe against
  `eval_threshold`, and writes the report.

The one-liner: **a probe attacks, a generator answers, a detector judges, a buff
mutates, the harness runs the loop, the evaluator scores it.**

## Quickstart

```bash
# 1. See what attacks exist (also: --list_detectors, --list_generators, --list_buffs)
python -m garak --list_probes

# 2. Run a single probe family against a cheap model
python -m garak --target_type openai --target_name gpt-4o-mini --probes encoding

# 3. Run a curated set, name the report, cap cost
python -m garak --target_type openai --target_name gpt-4o-mini \
  --probes promptinject,dan,encoding,leakreplay \
  --generations 3 --report_prefix tia_baseline_2026q2

# 4. Reproduce a full run from a config file (see garak_config.yaml)
python -m garak --config garak_config.yaml
```

> Flag note: modern garak uses `--target_type` / `--target_name`. The older
> `--model_type` / `--model_name` aliases are still accepted; you will see both
> in docs and blog posts. (Verify exact flags against
> <https://github.com/NVIDIA/garak> for your installed version.)

## Concrete CLI examples

```bash
# A. Prompt-injection battery against a local Hugging Face model (no API cost)
python -m garak --target_type huggingface --target_name gpt2 \
  --probes promptinject

# B. Jailbreak / "Do Anything Now" persona attacks, OpenAI target
python -m garak --target_type openai --target_name gpt-4o-mini \
  --probes dan --report_prefix dan_run

# C. Encoding / obfuscation evasion (base64, ROT13, etc. smuggled instructions)
python -m garak --target_type openai --target_name gpt-4o-mini \
  --probes encoding

# D. Training-data / memorization leakage (replays known text, checks for echo)
python -m garak --target_type openai --target_name gpt-4o-mini \
  --probes leakreplay

# E. Zero-cost dry run to learn the tool — the built-in mock generator
python -m garak --target_type test --target_name Blank --probes dan

# F. Scope a run by tag instead of naming probes (e.g. only OWASP-tagged probes)
python -m garak --target_type openai --target_name gpt-4o-mini \
  --probe_tags owasp:llm01
```

## Reading the report

Every run writes (default dir `garak_runs/`, overridable via `report_dir`):

- `garak.log` — human-readable run log,
- `<prefix>.report.jsonl` — one JSON object per attempt (the machine-readable
  source of truth),
- `<prefix>.report.html` — a rendered summary.

The exact filenames are printed at the start and end of the run. The JSONL is the
artifact a TIA actually queries — each line records the probe, prompt, model
output, detector verdict, and score. Count failures by probe with `jq`:

```bash
# Failed attempts (detector tripped) grouped by probe, most-failing first
jq -r 'select(.entry_type=="attempt" and .status==2) | .probe_classname' \
  garak_runs/tia_baseline_2026q2.report.jsonl | sort | uniq -c | sort -rn

# Or pretty-print a few records to learn the schema
python -m json.tool < garak_runs/tia_baseline_2026q2.report.jsonl | head -n 60
```

> The JSONL schema (field names, `status`/`entry_type` codes) varies across garak
> versions — inspect a few records with `python -m json.tool` first, then adjust
> the `jq` filter. Treat the field names above as illustrative, not pinned.

## garak probe families → OWASP LLM Top-10

Indicative mapping only. garak organizes by attack technique, not by the OWASP
taxonomy, and it ships its own MITRE-ATLAS-style tags rather than an OWASP column;
one probe can touch several OWASP categories. IDs below follow OWASP **2025**
(see [`../../reference/owasp-llm-top-10.md`](../../reference/owasp-llm-top-10.md)).

| garak probe family | What it attacks | OWASP LLM (2025) |
|---|---|---|
| `promptinject`, `latentinjection` | Direct & indirect instruction override | **LLM01** Prompt Injection |
| `dan`, `grandma`, jailbreak personas | Persona-swap / policy escape | **LLM01** (jailbreak variant) |
| `encoding`, `glitch` | Obfuscated / evasive injection (base64, ROT13, glitch tokens) | **LLM01** (evasion of input filters) |
| `leakreplay`, `replay` | Training-data memorization / verbatim echo | **LLM02** Sensitive Information Disclosure |
| `xss`, `latentinjection` (markdown exfil) | Output rendered/executed downstream unsafely | **LLM05** Improper Output Handling |
| `malwaregen`, `packagehallucination` | Generated malware / hallucinated install targets | **LLM03** Supply Chain / **LLM05** |
| `realtoxicityprompts`, `lmrc`, `continuation` | Toxic / harmful content elicitation | **LLM09** Misinformation & harms-adjacent |
| `donotanswer`, `misleading` | Confident-but-wrong / unsafe answers | **LLM09** Misinformation |

The honest framing for a TIA: this table is a *bridge* for reporting, not a
ground truth garak emits. State the mapping is indicative and cite the probe's own
tags when you file a finding.

## Authorization & cost — read this first

> garak makes **real model calls.** Two consequences:
>
> - **Cost.** A full probe battery is thousands of generations. Against a paid API
>   that is real money. Develop against the `test` generator (free mock) or a
>   local Hugging Face / Ollama model; scope to a few probes and a low
>   `--generations` value before pointing at a paid endpoint; use a cheap model
>   (e.g. `gpt-4o-mini`) for baselines.
> - **Authorization.** Scan **only** a model, endpoint, or application you own or
>   have **written authorization** to test. Unauthorized probing of a third-party
>   LLM service may violate that provider's terms of service and applicable law.
>   Red-teaming is a permissioned activity; treat it like one.

## Files

| File | Purpose |
|---|---|
| `garak_config.yaml` | Commented example run config (placeholders + probe list). |
| `README.md` | This file. |

## Further reading

- OWASP LLM Top-10 summary: [`../../reference/owasp-llm-top-10.md`](../../reference/owasp-llm-top-10.md)
- MITRE ATLAS techniques: [`../../reference/mitre-atlas.md`](../../reference/mitre-atlas.md)
- Sibling scaffold (framework-style red-teaming): [`../pyrit/`](../pyrit/)
- garak source & docs: <https://github.com/NVIDIA/garak> · <https://reference.garak.ai/>
