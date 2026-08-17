# Web / API security — lab progress & trajectory

*Public trajectory log for the conventional web/API half of an AI-offensive-security skill set. The
AI-specific layer is evidenced by the three runnable ranges in [`red-team/`](../red-team/) and the
[engagement report](./pentest-engagement-report.md); this file tracks the deliberate, in-progress
build-out of hands-on web/API exploitation depth (PortSwigger, Burp, BSCP) so "in progress" is
concrete and checkable rather than a vague claim.*

> **How to read this:** the honest framing is "AI/agent security is where I can already show
> executed work; conventional web/API pentest is my deliberate growth edge, aimed at where it
> compounds — because a tool-calling agent with an SSRF-able fetch is both an LLM06 problem and a
> classic SSRF problem." This log is the receipt for that trajectory. **Update the status columns as
> you go — do not pre-fill counts you haven't earned.**

---

## Why this exists (the strategy)

Not competing with a generalist who has five years of Burp — going where the two skills multiply.
Modern LLM apps and agents *are* web/API applications: their attack surface is REST/GraphQL
endpoints, auth/session handling, SSRF-able tool calls, IDOR on conversation objects, XSS from
model-rendered output, and injection into downstream systems. The practitioner who tests **both the
AI-specific layer and the conventional web/API layer underneath it** is rarer and more valuable than
either specialist alone — and it's a credible story from an AI-enablement starting point.

This repo already evidences the AI half (see the [engagement report](./pentest-engagement-report.md)
— 18 findings, CVSS, retest). The intersection is already in the ranges: **W1 SSRF is also
excessive agency (LLM06); W4 XSS is also improper output handling (LLM05); W2 IDOR is transcript
disclosure (LLM02).** This log tracks turning that mapped intersection into *hands-on tool depth*.

---

## PortSwigger Web Security Academy

Free, unlimited labs — and they double as **BSCP exam prep**. Ordered by highest value for AI-app
work first (server-side topics before client-side).

| # | Topic | Why it matters for AI apps | Labs done | Status |
|---|-------|----------------------------|:---------:|:------:|
| 1 | **SSRF** | Tool-calling agents fetch URLs — *the* overlap vuln (maps to range W1 / LLM06) | 0 / ~7 | ☐ not started |
| 2 | **Access control / IDOR** | Conversation & document objects (range W2 / LLM02) | 0 / ~13 | ☐ not started |
| 3 | **Authentication** | Session/token handling under the app (range W3) | 0 / ~14 | ☐ not started |
| 4 | **SQL injection** | Downstream data stores (range W5) | 0 / ~18 | ☐ not started |
| 5 | **OS command injection** | Tool/plugin execution surfaces | 0 / ~5 | ☐ not started |
| 6 | **XSS** | Model output rendered in a UI (range W4 / LLM05) | 0 / ~30 | ☐ not started |
| 7 | **XXE / deserialization** | File/format-handling tool inputs | 0 / ~13 | ☐ not started |
| 8 | **API / GraphQL** | The primary AI-app surface | 0 / ~10 | ☐ not started |

**Target for interview-readiness:** ~60–80 labs, logged one line each (what the bug was, how I found
it, how I'd fix it — that log is interview fuel). Running total: **0**.

## Burp Suite — reps against a target I own

The repo ships an OpenAI-compatible target that already speaks HTTP:
[`red-team/vulnerable-app/serve.py`](../red-team/vulnerable-app/serve.py). Proxy it through Burp,
intercept `/v1/chat/completions`, tamper and replay — a genuine "yes, I've used Burp against a
target I own and understand" data point.

| Rep | Status |
|-----|:------:|
| Proxy the local target through Burp; intercept + replay a request | ☐ |
| Tamper an injection payload in an intercepted request and observe the `x_acme` ground-truth block | ☐ |
| Run Burp's scanner against the local target; read what it asserts vs. the known ground truth | ☐ |
| Repeat against the web/API range endpoints (SSRF/IDOR/auth/XSS/SQLi) | ☐ |

## nuclei / nmap — coverage fluency

Enough to speak fluently about coverage vs. false positives, not to claim expertise.

| Rep | Status |
|-----|:------:|
| `nuclei` against the local target; read which templates fire and why | ☐ |
| `nmap` service/version scan of the local target | ☐ |
| Note template coverage vs. the ground-truth findings (what it catches / misses) | ☐ |

---

## Certification track

**Recommendation: BSCP** — cheapest, most directly relevant to "can you actually exploit a web app
with Burp," and the PortSwigger Academy labs above *are* the preparation. Mark it *"in progress"* on
the résumé the moment prep starts — in-progress certs are legitimate and show trajectory.

| Cert | Fit | Status |
|------|-----|:------:|
| **BSCP** (Burp Suite Certified Practitioner) | Recommended — practical Burp exploitation; Academy labs are the prep | ☐ not started |
| **OSWA** (OffSec WEB-200) | Strong alternative — broader practical web assessment | ☐ not started |
| **OSAI / AI-300** (OffSec) | The AI-red-team credential; pairs with the AI half already evidenced here | ☐ (see `osai-prep-studio`) |

*If only one this year: do the web one — AI security is the half already evidenced.*

---

## Public proof of reps

Link these from the résumé as public, checkable evidence (add handles as they fill in):

- **PortSwigger Academy** progress — _add profile/badge link_
- **HackTheBox / TryHackMe** profile — _add link_
- Optional: 1–2 sanitized write-ups of *own-lab* findings (report-writing is itself a
  high-signal skill for security roles) — link from here as they're published.

> Bug bounty **only** where scope is explicit and authorized. A couple of low-severity valid reports
> is a strong signal; don't force it.

---

## Change log

| Date | Update |
|------|--------|
| _(add dated rows as you make progress — this column is the visible trajectory)_ | |
