# Red-team tooling

The offensive half of the toolkit: generate adversarial traffic against LLMs, then
prove the [`llm-log-triage`](../projects/llm-log-triage/) detectors catch it. A
Technical Intelligence Analyst lives on both sides of that loop — finding novel
harms *and* building the detection that flags them at scale.

| Tool | What it is | Runs offline? | Maps to |
|------|------------|---------------|---------|
| [**PyRIT**](./pyrit/) | Microsoft's automation framework for red-teaming generative AI | ✅ Yes — `prompt_injection_probe.py` ships a std-lib `MockTarget` (swap in a real `PromptTarget` via env var) | OWASP LLM01 |
| [**NVIDIA garak**](./garak/) | LLM vulnerability *scanner* (probes → detectors → generators) | ⚠️ Needs `pip install garak` + a target; config + commands included | LLM01/02/05/07 |
| [**promptfoo**](./promptfoo/) | LLM eval + red-team harness, CI-friendly | ⚠️ Needs Node + provider API keys; `redteam` config included | LLM01/02/06 |
| [**local_redteam_harness.py**](./local_redteam_harness.py) | Closes the loop — runs an attack battery through a mock model and grades it with **our own detectors** | ✅ Yes — std-lib only, zero keys | OWASP LLM01/02/05/07 |

## Quickstart (fully offline, no keys)

```bash
# 1. PyRIT-style automated injection probe against a mock guardrailed model
python red-team/pyrit/prompt_injection_probe.py

# 2. Loop closure — red-team attacks graded by the flagship detection engine
python red-team/local_redteam_harness.py
```

## Running the real tools (need install / keys / an authorized target)

```bash
# garak — scan an OpenAI model for prompt-injection & jailbreak probes
pip install garak
garak --model_type openai --model_name gpt-4o-mini \
      --probes promptinject,dan,encoding,leakreplay --report_prefix acme

# promptfoo — generate & run a red-team suite, then view results
npx promptfoo@latest redteam run -c red-team/promptfoo/promptfooconfig.yaml
npx promptfoo@latest view
```

> **Authorization.** These tools send adversarial prompts to a model and can incur
> cost. Only point them at systems you are explicitly authorized to test
> (a pentest engagement, a CTF, your own deployment, or a research sandbox).
