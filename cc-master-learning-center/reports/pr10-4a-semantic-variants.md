# PR-10.4a Semantic Variant Model + `semantic_lock_guard`

**Slice:** PR-10.4a — the data model and validators for **semantically-equivalent variants** of
missed items. Synthetic variants only; **no live API, no provider integration** (that is PR-10.4b).
The validator exists — and proves it rejects bad variants — *before* any API output is allowed near
the system.

---

## 1. The idea, and the governance problem

A learner who misses an item should later see the *same concept* reworded, not the identical stem.
The hazard: free rewording can silently change **what** is tested. A variant is only trustworthy if
it provably preserves the source item's testable core, so PR-10.4a is the validator that proves it.

## 2. The model (`item-variant.schema.json` + `variants.py`)

Correctness lives in a **separate, evaluator-context variant key** (`{variant_id, correct_index,
rationale_refs}`) — exactly the answer-key isolation the quiz engine uses. The variant OBJECT stores
no correct index, display letter, or choice order and is a **closed object** (an allowlist check, so
no field of any name can smuggle an answer — gate 11).

The `semantic_lock` **corroborates** the key, it does not define correctness:

> The keyed-correct choice must contain every `must_include_keyword`, and **no other** choice may — so
> the lock keywords uniquely discriminate the correct choice and there is no second defensible answer.

Grading keys off the isolated `correct_index` (never the keyword), and renders through the PR-10.3
presentation layer, so variants shuffle per attempt exactly like items.

| Function | Role |
|---|---|
| `validate_variant(variant, variant_key, source_item, source_key, store, registry, holdout_ids?)` | the full gate set → `[]` iff valid |
| `semantic_lock_guard(variant, source_item, source_misconception_ids)` | consolidated no-drift check (objective, bank, fact_ids, misconception target — targets derived from the SOURCE key, never a silent skip) |
| `lock_consistency_problems(variant, variant_key)` | gate 7: the lock corroborates the isolated key; single best answer |
| `similarity_problems` | too-similar (Jaccard > the goldset near-dup bound, 0.75) |
| `is_practice_eligible` | **reviewed + metadata only**; draft and bare `validated` are never eligible |
| `render_variant` / `grade_variant` | delegate to `presentation` (shuffle + `presentation_id` integrity); render uses the SOURCE's neutral topic |
| `variant_lineage` | content-free traceable record incl. `semantic_lock_hash`, `readiness_weight: 0` |

## 3. Gate → proof (`test_variants.py`, 33 tests)

```
 1 source_item_id resolves to a practice item     test_unresolved_source_item_fails
 2 holdout item cannot seed a variant             test_holdout_source_is_rejected (flag + holdout-store cross-check)
 3 objective & bank match the source              test_changed_objective_fails_with_drift_message / _bank_
 4 fact_ids ⊆ source fact_ids                     test_fact_ids_not_subset_of_source_fails
 5 expected_keywords stay grounded                test_missing_expected_keyword_support_fails / _unsupported_new_claim
 6 misconception_ids resolve in the registry      test_unresolved_misconception_id_fails / _wrong_objective
 7 one correct concept, no second answer          test_keyword_on_wrong_choice_is_rejected / _second_choice_satisfying_lock
 8 draft/bare-validated never eligible            test_draft_... / test_bare_validated_is_not_practice_eligible
 9 reviewed needs review metadata                 test_reviewed_without_metadata_is_not_eligible / _with_metadata
10 variants render through presentation.py        test_variant_renders_..._no_field_leak / _does_not_leak_must_test
11 closed object: no smuggled field               test_variant_storing_correct_index_fails / _unknown_smuggle_field
12 not-too-similar (Jaccard ≤ 0.75)               test_too_similar_stem_fails
13 semantic_lock_guard fails on drift             test_misconception_target_drift_fails / _missing_source_key_fails_closed
```

Carry-forward from PR-10.3 (reviewer's four invariants): variants render **through** `presentation.py`
(gate 10), use a fresh per-attempt seed, support `expected_presentation_id` on grading
(`test_variant_grading_rejects_presentation_id_mismatch`), and store no choice order / correct letter
(gate 11). Plus grading keys off the isolated key not the keyword
(`test_variant_grading_uses_the_key_not_the_keyword`), `variant_lineage` (R&D), and
`must_include_keywords ⊆ expected_keywords`.

## 4. What PR-10.4a deliberately does NOT do

- **No live API / no provider.** Only `source: synthetic_test|human_authored` are exercised;
  `api_generated_local` is defined in the schema but always `draft` and never practice-eligible.
- **No variant touches readiness, holdout, or a mock draw.** `is_practice_eligible` gates practice
  display; `readiness_weight` is pinned to 0; the holdout/mock pools are physically separate and
  never read variants.
- **No committed variant content.** Like the factstore fixtures, the valid/bad variants live in the
  test as in-memory synthetic objects grounded on a real source item.

## 5. Review before commit (§16.0)

Independent code review — **completed before commit** (PR-9 lesson). Verdict **needs-work**; the
reviewer found real soundness defects (not cosmetics) that were all fixed before this commit:

| # | Sev | Finding | Fix |
|---|---|---|---|
| F1 | major | "semantic_lock is the key" was unsound — a keyword landing on a distractor could validate + **grade the wrong choice correct** | correctness moved to an **isolated variant key**; the lock now only corroborates it (keyed choice must carry the keywords, no other may). Grading keys off `correct_index`. Regression tests added. |
| F2 | major | `must_test` (answer-adjacent) leaked into the learner render via the allowlisted `topic` field | render uses the **source's neutral topic**; `must_test` stays validation-only. Render test asserts no `must_test`/`correct_concept` in the blob. |
| F3 | major | the misconception-drift check was **skipped** when `source_misconception_ids` defaulted to `None` | targets are now derived from the **source item's isolated key**; a missing key fails closed. Negative test added. |
| F4 | minor | a bare self-asserted `status: "validated"` was treated as practice-eligible | `is_practice_eligible` now requires **reviewed + metadata** only. |
| F5 | minor | `correct_concept` was never validated; the lock hash was described as a drift signal | reject a bare-letter `correct_concept`; hash re-described as a lineage id, not a live gate. |
| F6 | minor | only a fixed denylist was checked; the schema's `additionalProperties:false` was never run | replaced with a **closed-object allowlist** in code (unknown field of any name → fail). Test added. |
| F7 | minor | several negatives asserted weak substrings that an unrelated problem could satisfy | assertions tightened to specific messages; F1/F2/F3 negatives added. |
| F8 | nit | gate 2 depended on the caller's `holdout` flag | `validate_variant` also cross-checks the id against the **holdout store**. |
| F9 | nit | the similarity bound (0.85) was looser than the goldset's own near-dup bound (0.75) | reconciled to `quiz._NEAR_DUP_THRESHOLD`. |

A second **focused re-review** of the redesign confirmed all nine fixed (it rebuilt the F1 attack and
verified it is now rejected) and returned **accept-with-fixes** with four small items — all applied:
N1 (fail-closed if the holdout store is unreadable, matching `validate_gold`), N2 (`variant_key`
rationale_refs must be a subset of the variant's fact_ids), N3 (documented that automated gates can't
verify *semantic* correctness — human review is the backstop), N4 (reject any single-character
`correct_concept`, incl. E/F for 5–6-choice items). Full record in
`pr10-4a-semantic-variants-review.json`.

## 6. Next → PR-10.4b

The locked API-prompt scaffold + `api_generated_local / draft_runtime / readiness_weight: 0` handling
— API output is a **draft candidate**, validated by *this* engine and adversarially reviewed before it
can become `reviewed`/practice-eligible. Then PR-11a dashboard data model.
