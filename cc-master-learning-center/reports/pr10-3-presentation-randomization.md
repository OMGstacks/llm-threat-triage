# PR-10.3 Quiz Presentation Randomization + Attempt Receipts

**Slice:** PR-10.3 — render-time answer-choice shuffling so a repeated item can't be memorised by
letter ("it was C last time"). Engine only; no content growth. Lands **before** the dashboard
(PR-11a) so the dashboard consumes the same presentation/attempt model the learner actually uses.

---

## 1. The principle

> **Canonical item stays stable. Presentation order changes per attempt — when the caller supplies a
> fresh per-attempt seed.**

`goldset.json` / `holdout.json` are never mutated. Presentation order is computed at render time from
`(attempt_seed, item_id)` and is a **pure, deterministic** function — SHA-256 rank, no `random`, no
wall clock (same idiom as the mock assembler's draw). Because the order is recomputable, the
**grader recomputes it** to map a displayed choice back to its canonical index. Nothing stores or
transmits a choice-order mapping, so there is no "order secret" to leak — this is the reviewer's
preferred *deterministic recomputation* model, not a stored receipt.

The seed-freshness contract is **load-bearing** and honestly scoped (review F2): the anti-memorization
property holds only if the caller varies the seed per attempt. Reusing a seed reproduces the identical
order by design — so `quiz render` **requires** `--attempt-seed` (no fixed default that would silently
reproduce one order).

## 2. The module (`cc_spine/presentation.py`)

| Function | Contract |
|---|---|
| `presentation_order(item_id, attempt_seed, n)` | Deterministic permutation of `range(n)`: `order[display_pos] = canonical_index`. Stable sort → always a valid permutation. |
| `presentation_id(item_id, attempt_seed)` | Content-free hash correlating a render with its grading; reveals nothing about the answer. |
| `render_item(item, attempt_seed)` | Learner-safe render of one item: built on `quiz.learner_view` (allowlist), choices **reordered** (not rewritten), `presentation_id` + `choice_count` added, no answer field. |
| `render_quiz(items, attempt_seed)` | A whole attempt; each item shuffled independently (id is part of the rank). |
| `displayed_to_canonical(item_id, attempt_seed, d, n)` | Recomputes the order and returns `order[d]`. |
| `grade_presented(item, keys, attempt_seed, displayed_index)` | Maps displayed→canonical, then grades via `quiz.grade`. Grader context only; never assumes displayed == canonical. |

## 3. Isolation preserved

- The render reuses the `learner_view` allowlist — only `choices` are reordered; `presentation_id`
  (a hash) and `choice_count` (an int) are the only additions. No `correct_index`, rationale,
  `answer_key_ref`, or choice-order mapping.
- `item_hash` / `answer_key_hash` still pin the **canonical** item — shuffling touches neither the
  goldset nor the key store, so the drift guards keep working on authoring content.
- Grader context (`grade_presented`) returns canonical/correct indices, exactly like `quiz.grade`;
  those never travel in a learner render.

## 4. Gate → proof (`test_presentation.py`, 13 tests)

```
1 same item + same seed → identical order            test_same_item_same_seed_gives_identical_order
2 same item + different seed → varies when possible   test_different_seed_varies_order_when_possible
3 learner render shuffled, no correct index/secret    test_render_carries_no_answer_or_order_secret
4 grader maps displayed → canonical correctly         test_displayed_index_maps_back_to_canonical
5 answer-key isolation intact                         (grade uses isolated key store; render allowlist)
6 export/render scan finds no answer-bearing field    test_cli_render_...; quiz-render-scan CI gate
7 correct answer not pinned to one letter             test_correct_answer_not_pinned_to_one_letter
8 item_hash pins canonical, not the shuffle           test_item_hash_pins_canonical_not_presentation
9 holdout render uses same machinery, no leak         test_holdout_render_uses_same_machinery_...
```

Plus: valid-permutation, learner-safe shape, grader-doesn't-assume-display==canonical,
out-of-range display rejected, canonical goldset not mutated.

## 5. Demonstration

```
python3 -m cc_spine.cli quiz render --attempt-seed A --item-id D1.1.1.definition.0001
python3 -m cc_spine.cli quiz render --attempt-seed B --item-id D1.1.1.definition.0001   # different order
python3 -m cc_spine.cli quiz render --attempt-seed ci-attempt                            # whole shuffled quiz
```

## 6. Review before commit (§16.0)

Independent code review — **completed before commit** (PR-9 lesson). Verdict **accept-with-fixes**;
the core mechanics were confirmed clean (canonical immutability, permutation correctness for all n,
end-to-end displayed→canonical mapping, determinism, leak surface, hash pinning, holdout parity). All
five findings applied before this commit:

| # | Sev | Finding | Fix |
|---|---|---|---|
| F1 | minor | `grade_presented` accepted Python `bool` as an index (`bool` ⊂ `int`), silently grading `True`→1 / `False`→0 | added `_is_index` (int and not bool); test rejects bool/float/str/None |
| F2 | minor | anti-memorization depends on a fresh per-attempt seed, but the CLI default was a fixed `attempt-0` and the docstring overstated "letters move every attempt" | `--attempt-seed` is now required for `render` (no default); docstring/report scoped to the seed-freshness contract |
| F3 | minor | gate-7 test (`>1` distinct slot, one item) permitted heavy single-slot bias | strengthened: over 200 seeds × 6 items, every slot must be hit and no slot may exceed 60% |
| F4 | nit | `displayed_to_canonical` had no range check / documented precondition | documented the `[0,n)` precondition; `grade_presented` remains the guarded entry point |
| F5 | nit | `presentation_id` was described as correlating render↔grading but nothing checked it | `grade_presented` now takes an optional `expected_presentation_id` and fails closed on a seed mismatch; test proves it |

Full record in `pr10-3-presentation-randomization-review.json`.

## 7. Next → PR-10.4

The **semantic variant engine** for missed questions (variants preserve source_item_id / objective /
bank / fact_ids / expected_keywords / misconception_id / correct concept; API-generated variants are
draft/local until validated + reviewed; no holdout item seeds a variant; `semantic_lock_guard`). It
will reuse this presentation machinery. Then PR-11a dashboard.
