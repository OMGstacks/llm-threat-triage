---
name: feedback_grep_gate_bare_word_false_positive
description: Read before adding or widening a grep-based content-leakage gate (a CI check that
  greps generated output for forbidden terms) — a bare English word will false-positive against
  legitimate copy and unrelated substrings, and must be tested against real generated output
  before landing.
metadata:
  type: feedback
---

# Feedback: grep-gate bare-word false positive

## The mistake, generalized

A content-leakage gate greps generated output for terms that would indicate a sensitive value
leaked into a place it shouldn't be (e.g. an answer key leaking into learner-facing HTML). The
gate is widened by adding bare English words like `answer` or `stem` on the theory that "these
words shouldn't appear in this context." In practice both words appear constantly in legitimate,
non-leaking copy and even in unrelated substrings inside CSS or font-stack declarations (e.g.
`-apple-system` contains the substring `stem`).

## Why it keeps recurring

Widening a gate to "catch more" feels strictly safer than not widening it — the failure mode
(a false-positive gate blocking legitimate content) looks like an annoyance to fix later, not a
correctness bug, so it doesn't get the same scrutiny a false-negative would. The bare word is
also the first thing that comes to mind because it's the most literal description of the
sensitive concept, which makes it an easy default to reach for under time pressure.

## The rule

1. A grep content-gate must match compound, jargon-specific identifiers tied to the actual data
   shape being protected (e.g. a field name like `correct_index` or `distractor_misconceptions`),
   never a bare English word that could plausibly appear in ordinary prose or unrelated CSS/JS.
2. Any new or widened gate pattern must be run against real generated output (not reasoned about
   in the abstract) before it lands — grep the actual artifact the gate will run against and
   confirm zero false positives on legitimate content.
3. If a bare word is genuinely the only available signal, anchor it with surrounding context
   (a regex requiring adjacent structural markers, not just the word alone) rather than shipping
   an unanchored substring match.

## How this was learned

An attempted fix to an HTML-leakage gate during CC Master Learning Center's PR-11 development
series (on `claude/cc-cert-learning-plan-xqo5g7`, not yet merged to `main`) widened the gate with
bare words and immediately matched the dashboard's own legitimate copy ("Wrong answers," "no
answers, no PII") and its CSS font stack. Caught before landing by testing against real generated
output rather than shipping the reasoning untested.
