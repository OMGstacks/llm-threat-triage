---
name: feedback_overstated_enforcement_claims
description: Read before writing any docstring, commit message, or report claim about what
  code "enforces," "prevents," "cannot leak," or "guarantees" — verify the claim against the
  actual code path in the same review pass that writes it.
metadata:
  type: feedback
---

# Feedback: overstated enforcement claims

## The mistake, generalized

A docstring, commit message, or report asserts what a piece of code *enforces* — "adds no
policy," "cannot leak PII," "grouped weakest-domain-first," "is idempotent" — based on the
author's intent for the code, not on tracing the actual code path that would have to make the
claim true. The claim reads as a verified fact to the next reader (including a future session
relying on it as memory), but nothing checked it.

## Why it keeps recurring

Writing the claim and writing the code that satisfies the claim feel like the same act while
you're doing it — the author believes they're describing what they just built. The gap only
shows up when someone traces the claim against the code independently, which is exactly what
review is for. Left unverified, an enforcement claim silently becomes load-bearing: later code
gets written *assuming* the claim holds, compounding the risk.

## The rule

Before a claim of the form "this code enforces / prevents / cannot / guarantees X" ships in a
docstring, commit message, or report:

1. Name the specific code path (function, check, gate) that makes the claim true.
2. Trace it — mentally or by reading — from the input that would violate the claim through to
   the point where it's actually blocked. "I intended for this to be blocked" is not tracing.
3. If no such path exists yet, downgrade the claim's tense/certainty: "intends to," "is designed
   to," "should," not "does" / "cannot" / "always."
4. Do this in the *same review pass* that writes the claim — not as a follow-up, since the claim
   ships and gets relied upon the moment it's written, not the moment it's re-checked.

## How this was learned

Observed repeatedly (multiple independent instances) during CC Master Learning Center's PR-10
and PR-11 development series — a docstring or report asserted an enforcement property (a
semantic-lock's soundness, "adds no policy," a domain-ranking guarantee, an ordering guarantee)
that independent review then traced and found the code did not actually back, in each case.
That work happened on the `claude/cc-cert-learning-plan-xqo5g7` branch (not yet merged to
`main` as of this note) — this file records the generalized rule, not the original code
references, since those aren't present on this branch's history.
