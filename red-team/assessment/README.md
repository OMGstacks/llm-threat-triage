# AI Application Security Assessment

An **end-to-end offensive-security assessment** of an intentionally-vulnerable LLM agent, graded
with the same detection engine the rest of this repo defends with. It demonstrates the full loop
a real AI-security engagement runs — not just attack generation, and not just defensive detection:

```
attack case → vulnerable agent → response
  ├─ detect on INPUT   (was the attack visible arriving?)
  ├─ detect on OUTPUT  (did the response leak / exfiltrate?)
  ├─ ground-truth exploit check (did the app actually get compromised?)
  └─ mitigation → retest on the HARDENED agent (does the fix hold?)
→ every finding mapped to OWASP LLM Top 10 (2025) + MITRE ATLAS + a severity + a remediation
```

## Why detection on *both* sides
Filtering the input is not the security boundary. The real question isn't "did a malicious prompt
arrive?" — it's "did the system produce an unsafe *outcome*?" So the harness scans the model's
**output** for disclosure/exfil as well as the **input** for injection, and the hardened agent
enforces guards on both. That's why A09 (an output-side exfil pixel) is caught even though its
input also trips a guard: defense in depth, instrumented.

## Why provenance matters
The same sentence is a different security event depending on where it came from. "Ignore previous
instructions…" typed by a user is a *direct* injection (`AML.T0051.000`); the identical text
arriving inside a retrieved document, tool result, or email is an *indirect* injection
(`AML.T0051.001`) against a channel the model implicitly trusts. The corpus sends the same class of
payload down `chat_ui` vs `document`/`tool`/`rag`/`email` so the channel-aware detectors classify
each correctly.

## Components
| File | Role |
|------|------|
| [`../vulnerable-app/vulnerable_app.py`](../vulnerable-app/vulnerable_app.py) | The target: a deterministic mock agent with a planted-secret system prompt and weakly-authorized tools. `mode="vulnerable"` (no guardrails) vs `mode="hardened"` (the detectors wrapped as an input+output guard). |
| [`attack_corpus.py`](./attack_corpus.py) | The attack cases — one per class/channel, each with its expected OWASP/ATLAS mapping and a ground-truth success criterion. |
| [`run_assessment.py`](./run_assessment.py) | Drives the corpus through both targets, grades with the flagship detectors, writes the evidence, and asserts the invariants. |
| [`EVIDENCE.md`](./EVIDENCE.md) · [`results.json`](./results.json) | Generated evidence (committed): human-readable report + machine-readable results. |

## Run it
```bash
python3 red-team/assessment/run_assessment.py
```
Std-lib only, no network, no API keys. It regenerates `EVIDENCE.md` + `results.json` and **exits
non-zero if any invariant fails**, so it's also a self-test:

- every offensive case is actually exploitable on the vulnerable target (the range works),
- every offensive case is detected on input and/or output (no silent misses),
- every offensive case is blocked on the hardened target (the mitigation holds on retest),
- the benign control is neither flagged nor blocked (no false positive).

## Honest scope
- The target is a **mock**, not a live model — deliberately, so exploit success is ground truth and
  the assessment reproduces anywhere with zero setup. It exercises the *detection and remediation*
  workflow, which is where AI findings actually bottleneck at scale (triage → verify → remediate →
  retest), not a novel model jailbreak.
- The hardened guard reuses the same heuristic detectors — good for first-line triage, but the same
  limitations apply (see the root `README.md` "Limitations & scope"): it needs model-based
  classifiers and behavioral baselines to hold up against novel phrasings at production scale.
- The real PyRIT / Garak / Promptfoo CLIs can attack this same target: [`../vulnerable-app/serve.py`](../vulnerable-app/serve.py)
  exposes it as an OpenAI-compatible endpoint (no keys) — see the red-team [README](../README.md#point-the-real-tools-at-the-local-vulnerable-app-no-keys).
  The offense→detect→classify loop and taxonomy are already in place for their transcripts to plug into.
