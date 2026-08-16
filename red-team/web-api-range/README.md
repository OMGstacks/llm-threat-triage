# Web / API Range — the conventional layer under the AI app

Where [`../assessment/`](../assessment/) and [`../agent-range/`](../agent-range/) attack the
**AI-specific** layer (prompt injection, excessive agency, cross-step taint), this range attacks the
**conventional web/API layer the AI app is built on**. A modern LLM application *is* a web
application: its attack surface is REST endpoints, auth/session handling, SSRF-able tool calls, IDOR
on conversation objects, XSS from model-rendered output, and injection into downstream stores. Those
classic flaws don't disappear because there's a model in the loop — and they're exactly what an
application pentester (Burp / nuclei / manual) looks for.

```
attack case → vulnerable AcmeChat app → response
  ├─ ground-truth exploit check   (did the app actually get compromised?)
  ├─ map to OWASP API/Web Top 10 + CWE   (the conventional taxonomy, NOT the LLM Top 10)
  └─ mitigation → retest on the HARDENED app   (does the textbook fix hold?)
```

## Attack the intersection, not the gap
The point of this range is the **overlap**: the vulnerabilities here are simultaneously classic
web/API bugs *and* AI-application problems. An agent tool that fetches a user-supplied URL is both
**SSRF (CWE-918)** and **excessive agency (LLM06)**. Model output rendered unescaped is both
**reflected XSS (CWE-79)** and **improper output handling (LLM05)**. This range assesses the target
the way a web pentester would and maps each finding to the **OWASP API/Web Top 10 + CWE**, so the
portfolio demonstrates conventional application-security testing — not only prompt injection.

## Cases (see [`run_web_assessment.py`](./run_web_assessment.py))
| ID | Vulnerability | OWASP | CWE | Also an AI issue |
|----|---------------|-------|-----|------------------|
| W1 | **SSRF** — agent URL-fetch tool reaches cloud metadata | API7:2023 / A10:2021 | CWE-918 | excessive agency (LLM06) |
| W2 | **IDOR / BOLA** — read another user's conversation | API1:2023 / A01:2021 | CWE-639 | transcript disclosure (LLM02) |
| W3 | **Broken auth** — admin config with no valid token | API2:2023 / A07:2021 | CWE-306 | system-prompt & key exposure (LLM07) |
| W4 | **Reflected XSS** — search echoes active content unescaped | A03:2021 | CWE-79 | improper output handling (LLM05) |
| W5 | **SQL injection** — `' OR '1'='1` dumps all users' history | A03:2021 / API8:2023 | CWE-89 | — |
| W6 | Benign control — normal search + own conversation | — | — | false-positive control |

## Components
| File | Role |
|------|------|
| [`webapp.py`](./webapp.py) | The target: an intentionally web-vulnerable `AcmeChat` API. `mode="vulnerable"` (no guardrails) vs `mode="hardened"` (the textbook fix for each flaw — egress allowlist, ownership check, constant-time token check, HTML-escaping, parameterized query). Each response carries **ground-truth exploit flags**. |
| [`run_web_assessment.py`](./run_web_assessment.py) | Drives every case through both targets, maps to OWASP/CWE, writes the evidence, and asserts the invariants. |
| [`EVIDENCE.md`](./EVIDENCE.md) · [`results.json`](./results.json) | Generated evidence (committed): human-readable report + machine-readable results. |

## Run it
```bash
python3 red-team/web-api-range/run_web_assessment.py
```
Std-lib only, no network, no API keys. It regenerates `EVIDENCE.md` + `results.json` and **exits
non-zero if any invariant fails**, so it doubles as a regression self-test — the same contract as
the LLM-side ranges, and it runs in the `security-regression` CI gate:

- every attack case is actually exploitable on the vulnerable target (the range works),
- every attack case is blocked/prevented on the hardened target (the mitigation holds on retest),
- the benign control is neither flagged nor blocked (no false positive).

Latest run — **5/5 attacks exploited the vulnerable app, 5/5 blocked after hardening, 0 false
positives** on the control. Full per-case detail: [`EVIDENCE.md`](./EVIDENCE.md).

## Honest scope
- The target is a **deterministic mock**, not a live web stack — so exploit success is ground truth
  and the run reproduces anywhere with zero setup. The "SQL" is an in-memory row filter modelling the
  tautology, the "SSRF" reaches a mocked internal-metadata string (no real egress), and planted
  secrets are fake fixtures (the AWS-docs example key, a not-real DSN). This exercises the
  *assessment and remediation workflow* — find → map → fix → retest — not a novel 0-day.
- The hardened mode implements the **textbook** fix for each class; it's the durable control under
  test, retested in the same run. Against a real target these same classes are what a Burp/nuclei
  engagement would confirm dynamically — this range is the reproducible, self-testing stand-in that
  lives in the repo and fails CI if a fix ever regresses.
- This is the in-repo artifact for the "conventional web/API" half of the portfolio; the sequencing
  and cert plan behind it (PortSwigger Academy → BSCP, real Burp reps against your own target) is
  tracked separately.
