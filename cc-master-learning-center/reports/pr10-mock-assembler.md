# PR-10 Mock-Exam Assembler + Readiness Completion

**Slice:** PR-10 — the mock-exam assembler (`cc_spine/mock_exam.py`) and the completion of the
`banks.json` readiness formula in `learner_state`. Engine proof, scaled to available content.

---

## 1. Content-scale note (read first)

The `mock_exam` policy targets **100–125 items**; the fact base supports **~15** today (45 practice
+ 12 holdout). PR-10 therefore builds and gates the *machinery* — deterministic draw, holdout-only
scenarios, burn tracking, full readiness — proven with a **15-item mock**, exactly as PR-8a proved
the quiz engine before PR-8b scaled it. PR-10.1 already raised holdout scenarios to 5 (one per
domain); reaching real exam length needs continued growth slices (more items per bank, more holdout
scenarios). The assembler scales automatically as content grows.

## 2. The assembler (`mock_exam.py`)

- **`assemble(draw_key, count, seen)`** — domain-weighted draw (banks.json `domain_weights`),
  non-scenario items from **practice**, scenario items from **holdout only** (`scenario_draw:
  holdout_only`), excluding already-`seen` (burned) holdout ids. **Deterministic**: ranked by a
  stable SHA-256 of `(draw_key, item_id)` — no `random`, no wall clock. Same key → identical mock.
- **`mock_learner_view`** — the learner-facing exam via `quiz.learner_view`; practice and holdout
  items are shown uniformly and carry no answers.
- **`grade_mock`** — scores in evaluator context, resolving each item's key from its own lane;
  returns per-bank accuracy, **fresh-scenario accuracy** (holdout scenarios), and the **burned**
  holdout ids. Holdout item *content* never leaves this function.
- **`validate_mock`** — policy conformance: scenarios holdout-only, non-scenarios practice, banks
  within `draw_from`, no duplicates, every item resolves in its lane.

## 3. Holdout-in-mock isolation (the delicate part)

| Invariant | How |
|---|---|
| Holdout surfaces only in a mock | `export-learner` and the practice quiz still exclude holdout (unchanged, tested) |
| No holdout-content remediation | `learner_state.replay` still **rejects** holdout attempts; mock holdout results feed `fresh_scenario_accuracy` as a *count only* — no holdout stem/misconception enters the journal |
| Single-use (burn) | `grade_mock` returns `burned_holdout_ids`; `assemble(seen=…)` excludes them. Burn state is **learner state → gitignored**, never committed |

## 4. Readiness completion

`learner_state.readiness_report(state, mock_result, leakage_ok)` computes the full weighted formula
from `banks.json`: `fresh_scenario_accuracy` (0.35, from the mock) · `concept_discrimination_accuracy`
(0.25) · `mature_flashcard_accuracy` (0.20, Leitner box ≥ 3) · `wrong_answer_closure_rate` (0.10) ·
`time_management_performance` (0.10). Weights renormalize over components that have data, so a
mock-less report is informative but flagged **incomplete**. **Hard blockers** fire on any domain
< 75%, holdout-scenario accuracy < 80%, or a failing leakage gate → `not-ready` with reasons.

## 5. Demonstration

```
python3 -m cc_spine.cli mock assemble --draw-key 2026-07-05 --count 15   # a reproducible mock
python3 -m cc_spine.cli mock validate --draw-key 2026-07-05 --count 15   # policy conformance
python3 -m cc_spine.cli learner replay --attempts tests/fixtures/synthetic_attempt_stream.json --now 5
```

## 6. Review before commit (§16.0)

An independent code reviewer audited the assembler + readiness for determinism, holdout isolation,
allocation correctness, and readiness math — **awaited before commit** (the PR-9 lesson applied). It
returned two findings: **F1** (minor) confirmed the operator's already-applied time-management fix;
**F2** (major) — a holdout scenario *exposed* in a mock but left unsubmitted was never burned, so it
could re-draw and re-count as "fresh". The follow-up fixes F2: burn now tracks **exposure**, not
submission (new `exposed_holdout_ids`, made the single source of truth for `grade_mock`'s burn set),
with three regression tests. Full record in `pr10-mock-assembler-review.json`.

## 7. Deferred → PR-11

The **readiness dashboard** (an Artifact) and **cram sheets** — the visual layer over these numbers.
