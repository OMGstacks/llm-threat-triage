# PR-11a Readiness Dashboard — Data Model

**Slice:** PR-11a — the **data-first** readiness dashboard (`cc_spine/dashboard.py`). The numbers a
readiness view renders, as one content-free object — **not** the visual layer (that is PR-11b). It
lands first so the visual layer consumes a stable, tested model rather than recomputing anything.

---

## 1. What it is

`build_dashboard(state, mock_result=None, leakage_ok=True, now=0)` — a **deterministic, content-free**
projection of a learner state (from `learner_state.replay`) plus an optional graded mock (from
`mock_exam.grade_mock`). It adds **no readiness policy** — the verdict/score/blockers are carried
verbatim from `learner_state.readiness_report` (the banks.json weighted formula) — composed with the
pieces a dashboard shows. The one judgment it makes of its own is the **display-only** `content_scale`
classification (§3), which never touches the verdict or score.

| Section | Source | Content |
|---|---|---|
| `readiness` | `readiness_report` | verdict, score, complete, weighted_over, hard_blockers, note |
| `domain_accuracy` / `bank_accuracy` | `state.readiness.per_domain/per_bank` | accuracy + attempt counts |
| `spaced_repetition` | `review_queue` + item boxes | total/due/mature counts, next-review ids |
| `wrong_answers` | `open_journal` + closure rate | open count, closure rate, open misconception ids |
| `top_misconceptions` | `state.misconceptions` | ever-missed, ranked by miss count (ids only) |
| `mock` | `grade_mock` | fresh-scenario accuracy + count, overall accuracy, burned-holdout count (`null` with no mock) |
| `content_scale` | goldset/holdout counts vs banks.json | **P1-3 caveat**: proof-scale vs exam-scale |
| `next_recommended_review` | `review_queue` | due item ids to study next |

## 2. Isolation & determinism

- **Content-free:** only ids, counts, accuracies, and verdicts — never a stem, correct answer, answer
  key, journal correction text, or PII field. Item ids and misconception ids are already
  learner-visible (`learner_view` / the journal). Two tests assert no answer/PII field name and no
  holdout stem/choice text appears; a `dashboard-check` CI gate scans the CLI output.
- **Deterministic:** a pure function of `(state, mock_result, leakage_ok, now)`. `now` is the injected
  day counter used throughout this codebase — no wall clock, no randomness. `generated_at_day` is
  that counter, not a timestamp. The `dashboard-check` gate builds twice and `cmp`s.

## 3. The P1-3 content-scale caveat

The reviewer's P1-3 concern — *a learner should not confuse a ~15-item mock with exam-length
readiness* — is now surfaced structurally. `content_scale` reports today's counts (45 practice + 5
holdout scenarios) against the banks.json mock target (100–125), flags `status: proof_scale`, and
carries a plain-language caveat: **a passing mock here is an engine proof, not exam readiness.** It
flips to `exam_scale` (caveat `null`) automatically once content grows past the target.

## 4. The committed sample

`reports/readiness-dashboard-sample.json` is **exactly what the code produces** from the synthetic
attempt fixture (`tests/fixtures/synthetic_attempt_stream.json`) at `now=5` — not hand-authored. A
test (`test_committed_sample_matches_regenerated`) asserts `build_dashboard(...) == the sample`, so
the sample can never drift from the model. It is the practice-only case (`mock: null`,
`complete: false`), the honest default before a mock is graded; the with-mock completion is proven by
a separate test.

## 5. Demonstration

```
python3 -m cc_spine.cli dashboard --attempts tests/fixtures/synthetic_attempt_stream.json --now 5
python3 -m cc_spine.cli dashboard --attempts stream.json --now 5 --mock graded_mock.json   # completes readiness
make dashboard-check
```

## 6. Review before commit (§16.0)

Independent review — **completed before commit** (PR-9 lesson). Verdict **accept-with-fixes** (1
minor + 2 nit, no majors); the reviewer confirmed content-freedom, determinism, faithful
readiness-report composition, a by-hand schema/sample match, and sample regenerability. All applied:

| # | Sev | Finding | Fix |
|---|---|---|---|
| F1 | minor | a non-dict `--mock` (e.g. `[1,2]`) crashed with a traceback (truthy non-dict reaches `.get`) | CLI rejects it cleanly (rc 1); `build_dashboard` coerces a non-dict mock to `None`; two tests |
| F2 | nit | `next_review_items` and `next_recommended_review` are identical | documented in the schema (both are the due-queue head; the second is reserved for a future weakness-ranked recommender) |
| F3 | nit | id lists capped at 10 with no truncation signal | schema notes the full totals (`due_now`/`open_count`) alongside the capped lists, so truncation is derivable |

Two overstated-claim flags corrected: "adds no policy" → "adds no **readiness** policy" (the
display-only `content_scale` classification is this module's one judgment); and the content-free
value-leak guarantee is now **test-enforced** for practice stems and journal correction/rule/trap
text, not just holdout stems and field names. Full record in
`pr11a-readiness-dashboard-review.json`.

## 7. Next → PR-11b

The **visual dashboard** (an Artifact) rendering this exact model — no recompute, just layout. Then
cram sheets / weak-area review packets.
