# Red-team tooling

The offensive half of the toolkit: generate adversarial traffic against LLMs, then
prove the [`llm-log-triage`](../projects/llm-log-triage/) detectors catch it. An
AI offensive-security analyst lives on both sides of that loop — finding novel
harms *and* building the detection that flags them at scale.

## ⭐ Full application security assessment

[`vulnerable-app/`](./vulnerable-app/vulnerable_app.py) + [`assessment/`](./assessment/) are a
self-contained **intentionally-vulnerable LLM agent** and an **end-to-end assessment** that
attacks it and grades every result with the *same* flagship detection engine — the complete
offensive→defensive loop, with detection on **both sides** of the model:

```
attack → vulnerable agent → response → detect(input + output) → OWASP/ATLAS + severity → mitigation → retest(hardened)
```

```bash
python red-team/assessment/run_assessment.py   # regenerates EVIDENCE.md + results.json; std-lib only, zero keys
```

Latest run — **9/9 attacks exploited the vulnerable target · 9/9 detected · 9/9 blocked after
hardening · 0 false positives** on the benign control. Full evidence table (attack → request →
response → exploit → OWASP → ATLAS → severity → mitigation → retest):
[`assessment/EVIDENCE.md`](./assessment/EVIDENCE.md). The target is a deterministic mock (no live
model), so exploit success is **ground truth** and the run is reproducible; the script exits
non-zero if any invariant fails, so it doubles as a self-test.

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
