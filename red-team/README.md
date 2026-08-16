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

## ⭐ Multi-step agent range

[`agent-range/`](./agent-range/) takes it further: a **RAG + tool-using agent** where a poisoned
retrieved document chains through tool calls to exfiltration and destruction — credential access,
unsafe delegation, sandbox escape. Every step is instrumented, graded with the flagship detectors,
and the hardened agent's **kill point** is identified.

```bash
python red-team/agent-range/run_range.py       # regenerates EVIDENCE.md + results.json
```

Latest run — **3/3 attacks exploited · 3/3 detected · 3/3 broken on the hardened agent · 0 false
positives**. Evidence: [`agent-range/EVIDENCE.md`](./agent-range/EVIDENCE.md).

## ⭐ Web / API range — the conventional layer underneath

[`web-api-range/`](./web-api-range/) attacks the target the way an **application pentester** would.
A modern LLM app *is* a web/API app, so this range covers the classic flaws that live under the
model — **SSRF, IDOR/BOLA, broken auth, reflected XSS, SQLi** — each mapped to the **OWASP API/Web
Top 10 + CWE** (not the LLM Top 10), and each exploited on the vulnerable build then retested on the
hardened one. The point is the intersection: an agent's URL-fetch tool is both SSRF (CWE-918) *and*
excessive agency (LLM06); unescaped model output is both XSS (CWE-79) *and* improper output handling
(LLM05).

```bash
python red-team/web-api-range/run_web_assessment.py   # regenerates EVIDENCE.md + results.json
```

Latest run — **5/5 web/API flaws exploited · 5/5 blocked after hardening · 0 false positives**.
Evidence: [`web-api-range/EVIDENCE.md`](./web-api-range/EVIDENCE.md).

All three ranges run in the `security-regression` CI gate — each exits non-zero if an attack stops
exploiting the vulnerable target, a mitigation regresses, or the benign control false-positives, so
they are a live regression suite, not just documentation.

## Quickstart (fully offline, no keys)

```bash
# 1. PyRIT-style automated injection probe against a mock guardrailed model
python red-team/pyrit/prompt_injection_probe.py

# 2. Loop closure — red-team attacks graded by the flagship detection engine
python red-team/local_redteam_harness.py
```

## Point the real tools at the local vulnerable app (no keys)

[`vulnerable-app/serve.py`](./vulnerable-app/serve.py) exposes the vulnerable agent as an
**OpenAI-compatible** endpoint — so PyRIT / Garak / Promptfoo can attack it locally with no API
key and no cost, against an authorized target you own. It returns the normal completion plus a
non-standard `x_acme` block (`leaked_secret` / `obeyed_injection` / `tool_invoked` / `refused`), so
a harness can score each tool's transcripts with the same ground truth the offline assessment uses.

```bash
# 1. Start the target (VULN_APP_MODE=hardened to attack the defended build instead)
python red-team/vulnerable-app/serve.py                 # http://127.0.0.1:8000/v1

# 2a. PyRIT probe against the shim (uses the real-target path already in the probe)
PYRIT_PROBE_USE_REAL_TARGET=1 \
  OPENAI_CHAT_ENDPOINT=http://127.0.0.1:8000/v1/chat/completions OPENAI_API_KEY=dummy \
  python red-team/pyrit/prompt_injection_probe.py

# 2b. Garak — point its OpenAI generator at the shim
pip install garak
OPENAI_API_KEY=dummy OPENAI_BASE_URL=http://127.0.0.1:8000/v1 \
  garak --model_type openai --model_name acme-assistant \
        --probes promptinject,dan,encoding,leakreplay

# 2c. Promptfoo — an OpenAI provider with a local base URL
#   providers:
#     - id: openai:chat:acme-assistant
#       config: { apiBaseUrl: http://127.0.0.1:8000/v1, apiKey: dummy }
npx promptfoo@latest redteam run -c red-team/promptfoo/promptfooconfig.yaml
```

## Running the real tools against an external model (need install / keys / an authorized target)

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
