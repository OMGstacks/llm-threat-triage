# PR-10.2 Mock Exposure-Receipt Hardening

**Slice:** PR-10.2 — make burn-on-exposure *operational* before any dashboard renders a mock. No
content growth; engine hardening only, on top of the PR-10 F2 fix (`cc7586b`).

---

## 1. Why (the residual hazard the reviewer named)

PR-10's F2 fix made `grade_mock` burn every *exposed* holdout scenario — but only inside the grading
path. The reviewer flagged the integration hazard beyond grading:

> `mock_learner_view(mock)` reveals holdout items but returns only the learner-facing items, not an
> exposure receipt. If a future UI/dashboard renders a mock and the learner abandons it before
> grading, the caller must still persist the burn set — and nothing forces it to.

So the rule *"any code path that renders a mock must also persist the exposure receipt"* was true in
principle but not surfaced in code. PR-10.2 makes the **sanctioned public render path** carry it.

> **Honesty note (independent review F1).** The first cut of this PR claimed `render_mock` made the
> obligation "inseparable / enforced for any render path." The reviewer correctly rejected that:
> Python can't hard-enforce it, and the raw projection was still public. This slice was re-scoped to
> what the code actually delivers — see §2 and §6.

## 2. What ships

| Piece | Contract |
|---|---|
| `mock_exam.mock_exposure_receipt(mock)` | Content-free record: `draw_key`, `item_count`, `exposed_holdout_ids`, `holdout_exposure_count`, `burn_required`. **No stems / choices / rationales / answers** — safe to log, store, ship in a receipt trail. |
| `mock_exam.render_mock(mock)` | The **sole public** learner render — bundles `{"items": learner views, "exposure_receipt": receipt}`. The raw receipt-less projection is now **private** (`_mock_learner_view`), so the default public path a UI reaches for carries the burn obligation. (Not absolute — a caller can still reach the private helper — but the public render surface always carries the receipt.) |
| CLI `mock render` | Prints the receipt (stdout, content-free) and, when `burn_required`, the burn obligation to **stderr**. Operational proof that this render path surfaces the burn set rather than hiding it. |
| `make mock-render` + CI step | Runs `mock render` and **scans its output** for any content/answer-bearing field (mirrors `quiz-export-scan`), so a CLI regression that leaked stems would fail CI. The receipt is content-free, so it is safe in CI logs. |

`exposed_holdout_ids(mock)` (added in the PR-10 F2 fix) remains the single source of truth; the
receipt and `grade_mock`'s `burned_holdout_ids` both derive from it, so the three can never disagree.
It counts **assembled** exposure — conservative, so burn can over-count but never under-count (never
leaks; review F5).

## 3. Isolation preserved

- The **receipt** carries only ids + counts. Tested: no holdout stem or choice string, and no
  answer-bearing key (`correct_index`, `answer_key_ref`, `rationale_refs`, `item_hash`, `stem`,
  `choices`), appears in the serialized receipt.
- The **CLI `render`** prints the receipt to stdout (content-free) and the warning to stderr; it does
  **not** dump learner stems to the terminal, so holdout content never reaches CI logs. A real UI
  renders `render_mock(...)["items"]` (answer-free learner views) and persists the receipt.
- **Item ids are the intended minimal exposure**: an id like `D1.1.2.scenario.9001` is exactly the
  burn key that must be persisted; the descriptive topic text is not in the id (review, clean).
- Determinism unchanged: the receipt is a pure function of the (deterministic) mock (`sorted({…})`).

## 4. Tests (all stdlib unittest, in `test_mock_exam.py::ExposureReceiptTest`)

```
test_render_mock_bundles_items_and_receipt                 # the sole public render always bundles both
test_raw_projection_is_private_no_public_unguarded_render  # the receipt-less render is NOT public (F1/F2)
test_mock_render_items_match_exposure_receipt              # exposed ids ⊆ rendered; oracle from mock items
test_receipt_burn_set_equals_exposed_holdout_ids          # receipt == grade_mock burn == independent oracle (F3)
test_receipt_contains_no_holdout_stems_or_answers         # receipt is content-free
test_cli_mock_assemble_or_export_prints_receipt_or_warns  # CLI render prints receipt + warns; no leak
```

## 5. Demonstration

```
python3 -m cc_spine.cli mock render --draw-key 2026-07-05 --count 15
# stdout: {"draw_key": ..., "exposed_holdout_ids": [...5 ids...], "burn_required": true}
# stderr: WARNING burn-on-exposure: this mock exposes 5 holdout scenario(s) [...]; persist as burned.
```

## 6. Review before commit (§16.0)

Independent code review of the receipt/render coupling — enforcement strength, content-freedom of
the receipt, no CLI leak, determinism, test quality — **completed before commit** (PR-9 lesson).
Verdict **accept-with-fixes**; all five findings applied before this commit:

| # | Sev | Finding | Fix |
|---|---|---|---|
| F1 | major | "enforced / no code path / inseparable" overstated — `mock_learner_view` was a public bypass | raw projection made private (`_mock_learner_view`); `render_mock` is the sole public render; all "enforces/inseparable" language softened to "sanctioned public surface" |
| F2 | minor | no test proved the bypass was closed; "inseparable" comment claimed more than tested | added `test_raw_projection_is_private_no_public_unguarded_render`; removed the overstated comment |
| F3 | minor | burn-set agreement test was near-tautological (all three values = same function call) | assertion now uses an independent oracle recomputed from `mock["items"]` |
| F4 | minor | `mock-render` gate only checked exit 0, not content-freeness | gate now scans output for content/answer-bearing fields (mirrors `quiz-export-scan`), in both Makefile and CI |
| F5 | nit | receipt counts assembled, not rendered, exposure | documented as intentional conservative (over-burn, never under-burn) counting |

Clean areas the reviewer confirmed: receipt content-freedom (all 12 holdout items), item-id as
intended minimal exposure, three-way burn-set agreement by shared-function construction,
determinism, no CLI leak. Full record in `pr10-2-exposure-receipt-review.json`.

## 7. Deferred (reviewer P1, → PR-11a data model)

- **P1-1** mock attempt IDs (caller-supplied nonce, no wall clock in the engine).
- **P1-2** `schemas/mock-attempt.schema.json` for local-only mock attempt state (gitignored, like
  learner state).
- **P1-3** content-limited-mock caveat surfaced in the readiness output (`incomplete_content_scale`)
  — folds naturally into the PR-11a readiness dashboard data model.
