# PR-8b Adversarial Item Review

**Scope:** all 40 gold items (the first full non-holdout set).
**When:** before commit, per governance spec §16.0 (no content-growth commit until its adversarial
review completes).
**Method:** five independent per-domain adversarial reviewers (D1–D5), each given the items *with the
correct answer marked* plus the grounding card claims, and told to try to break each item —
find a factually-wrong key, a second defensible answer, an implausible or secretly-correct
distractor, a grounding gap, or a stem-quality tell. The authoring pass and this review pass were
run by separate agents (author ≠ reviewer).

**Outcome:** 0 factual errors, 0 multiple-correct blockers, 0 grounding gaps. **3 minor
stem-quality findings, all fixed before commit.**

---

## 1. Mechanical pre-checks (all pass, before human-style review)

Every item was first validated by `quiz validate`:
- grounding: each item cites active, bank-eligible fact cards; every `expected_keyword` resolves in a
  cited card (unsupported_claim_guard).
- answer-key isolation: no answer-bearing field in the learner lane; `export-learner` scan clean.
- key integrity: `answer_key_hash` (correct-choice) and `item_hash` (full item) match every key.
- distractors: every wrong choice names a resolvable registry misconception (correct category +
  objective).
- anti-gaming: answer-position gate (no index > 40%, none uniform within an objective) and
  near-duplicate stem gate pass.

## 2. Confirmed findings (all minor, all fixed)

| Item | Finding | Fix |
|---|---|---|
| `D1.1.1.discrimination.0001` (authn vs authz) | Correct option was conspicuously the longest, with parenthetical elaboration the distractors lacked — a length/specificity tell. | Rewrote all four options to parallel length/structure. |
| `D1.1.3.discrimination.0001` (preventive vs detective) | Correct option was the only one carrying concrete examples ("firewall", "IDS alert") and markedly longer. | Gave every option a parallel example so length/detail is balanced; correct is no longer the longest. |
| `D5.5.1.definition.0002` (asymmetric encryption) | All three distractors were equivalent restatements of "symmetric encryption" — a test-wise candidate could pick the odd-one-out structurally. | Diversified distractors to three distinct misconceptions (symmetric-key, hashing/one-way, key-roles-don't-matter). |

## 3. Operator-added hardening (beyond the reviewers' findings)

A mechanical scan for the **answer-length tell** (correct answer the single longest choice) found it
in 57% of items, with 3 items where the correct answer was > 1.5× longer than every distractor (up to
2.26×). Those 3 (all D5 scenario/discrimination with "because …" justification tails) were trimmed to
length parity; one marginal label case (`D3.3.1.definition.0002`, "Security guards (human personnel)")
was shortened. **After fixes: 0 items with a conspicuous (> 1.5×) tell; 52% residual longest-correct**,
recorded as a tracked metric with a < 40% authoring target (see the distribution report §6).

## 4. Clean areas (recorded, not assumed)

- **D2, D3, D4 (24 items):** zero findings across all five review dimensions. Includes the
  exam-critical IR four-phase items — reviewers confirmed the four-phase model and that the six-phase
  and five-phase options are correctly keyed as distractors.
- **Factual accuracy:** no keyed answer was wrong; no distractor was secretly correct (checked
  explicitly for the Purge-level sanitization item, where a wrongly-keyed distractor would be a
  blocker).

## 5. Process compliance

This review ran and its findings were resolved **before** the PR-8b commit, satisfying the §16.0
review-order rule adopted after PR-7. The authoring agents and reviewing agents were distinct.

## 6. Summary

| | |
|---|---|
| Items reviewed | 40 (D1–D5, 8 each) |
| Factual errors | 0 |
| Multiple-correct blockers | 0 |
| Grounding gaps | 0 |
| Minor stem-quality findings | 3 — all fixed |
| Operator length-bias fixes | 4 items trimmed |
| Final | 40 items, all gates green |
