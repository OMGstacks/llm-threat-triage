# Reports — persisted acceptance evidence

This directory holds the **evidence trail** for content-growth slices. A slice is not accepted on
the strength of a chat transcript; it is accepted on the strength of a report committed here that
anyone can re-derive from the source files.

## Contract

Every content-growth slice (PR-6, PR-7, PR-9+) lands a persisted acceptance report before the next
slice starts. At minimum:

1. **Distribution report** — final card counts by domain / objective / claim_type / source_tier,
   bank-eligibility coverage, and a PR-readiness verdict. Numbers are derived from the committed
   card files, not hand-entered.
2. **Adversarial review report** — the semantic-review method, confirmed defects and fixes, the
   areas that came back clean, and any process findings.

## Rules recorded here (see governance spec §16.0)

- **Slice size:** 40–75 items per growth slice; a larger slice needs approval *before*
  implementation and a documented exception in the distribution report.
- **Review order:** no content-growth commit until its adversarial review completes.

## Index

| Report | Slice | Summary |
|---|---|---|
| [`pr7-fact-card-distribution.md`](pr7-fact-card-distribution.md) | PR-6 + PR-7 | 149 cards across 5 domains; 90-card slice-size exception documented |
| [`pr7-adversarial-review.md`](pr7-adversarial-review.md) | PR-7 | 2 defects + 2 near-duplicates fixed; misconception-registry seeds for PR-8 |
| [`pr8b-gold-item-distribution.md`](pr8b-gold-item-distribution.md) | PR-8b | 40 gold items, banks 18/14/8, 8/domain; anti-gaming metrics |
| [`pr8b-adversarial-item-review.md`](pr8b-adversarial-item-review.md) | PR-8b | 5 per-domain reviewers; 3 minor stem-quality fixes; 0 factual errors |
| [`pr8b-adversarial-item-review.json`](pr8b-adversarial-item-review.json) | PR-8b | machine-readable per-item review outcome (companion to the .md) |
| [`pr8c-holdout-lane.md`](pr8c-holdout-lane.md) | PR-8c | 8 holdout items in a physically separate lane; holdout_leakage_guard active |
| [`pr8c-holdout-adversarial-review.json`](pr8c-holdout-adversarial-review.json) | PR-8c | holdout review outcome — 0 findings |
| [`pr8d-exam-strategy.md`](pr8d-exam-strategy.md) | PR-8d | fills the exam_strategy bank: 7 global cards + 5 items; all 4 banks live |
| [`pr8d-exam-strategy-review.json`](pr8d-exam-strategy-review.json) | PR-8d | exam-strategy review outcome — 0 findings |
| [`pr9-learner-state.md`](pr9-learner-state.md) | PR-9 | wrong-answer journal + Leitner engine; learner_state_isolation_guard active |
| [`pr9-learner-state-review.json`](pr9-learner-state-review.json) | PR-9 / 9.1 | independent engine review — 4 minors, all fixed in PR-9.1 |
| [`pr10-1-holdout-scenarios.md`](pr10-1-holdout-scenarios.md) | PR-10.1 | +4 holdout scenarios (5 total, one per domain); mock scenario supply |
| [`pr10-1-holdout-scenarios-review.json`](pr10-1-holdout-scenarios-review.json) | PR-10.1 | holdout scenario review — 0 findings |
| [`pr10-mock-assembler.md`](pr10-mock-assembler.md) | PR-10 | mock-exam assembler + full readiness formula (engine, proof-scale) |
| [`pr10-mock-assembler-review.json`](pr10-mock-assembler-review.json) | PR-10 | engine review — self-audit (1 fix) + independent review (F1 confirmed, F2 major burn-on-exposure fixed in follow-up) |
| [`pr10-2-exposure-receipt.md`](pr10-2-exposure-receipt.md) | PR-10.2 | mock exposure receipt + `render_mock` coupling; burn-on-exposure made operational before the dashboard |
| [`pr10-2-exposure-receipt-review.json`](pr10-2-exposure-receipt-review.json) | PR-10.2 | independent review accept-with-fixes; F1 (major, overstated enforcement) + F2–F5 all fixed before commit |
| [`pr10-3-presentation-randomization.md`](pr10-3-presentation-randomization.md) | PR-10.3 | render-time choice shuffling (deterministic recomputation); canonical items stable; grader maps displayed→canonical |
| [`pr10-3-presentation-randomization-review.json`](pr10-3-presentation-randomization-review.json) | PR-10.3 | independent review accept-with-fixes; F1–F5 (bool guard, required seed, stronger anti-memo gate, precondition, pid integrity check) all fixed before commit |
| [`pr10-4a-semantic-variants.md`](pr10-4a-semantic-variants.md) | PR-10.4a | semantic variant model + `semantic_lock_guard` (synthetic-only, no live API); 13 gates + carry-forward |
| [`pr10-4a-semantic-variants-review.json`](pr10-4a-semantic-variants-review.json) | PR-10.4a | independent review needs-work → all fixed: 3 major (wrong-choice-graded-correct, render leak, drift bypass) + F4–F9, redesigned around an isolated variant key |
| [`pr10-4b-variant-intake.md`](pr10-4b-variant-intake.md) | PR-10.4b | locked API-prompt scaffold + draft intake (no live API); gates I1–I10 + 8th guard; N3 residual documented |
| [`pr10-4b-variant-intake-review.json`](pr10-4b-variant-intake-review.json) | PR-10.4b | independent review accept-with-fixes; F1–F8 (map-value typing, field-vs-information separation honesty, CLI guards, wrapper-shape scan, …) all fixed before commit |
| [`pr11a-readiness-dashboard.md`](pr11a-readiness-dashboard.md) | PR-11a | readiness dashboard DATA MODEL (content-free, deterministic); composes readiness_report; P1-3 content-scale caveat |
| [`pr11a-readiness-dashboard-review.json`](pr11a-readiness-dashboard-review.json) | PR-11a | independent review accept-with-fixes; F1 (non-dict mock crash) + F2/F3 nits fixed; value-leak guarantee made test-enforced |
| [`readiness-dashboard-sample.json`](readiness-dashboard-sample.json) | PR-11a | the dashboard produced from the synthetic fixture (regenerable; drift-checked by a test) |
| [`pr11b-visual-dashboard.md`](pr11b-visual-dashboard.md) | PR-11b | the visual layer (`dashboard_view.render_html`) — pure formatter over the PR-11a model; instrument-panel design |
| [`pr11b-visual-dashboard-review.json`](pr11b-visual-dashboard-review.json) | PR-11b | independent review needs-work → all fixed: 1 major (domain-gauge miscalibration vs the real hard-blocker gate) + 4 minor/nit |
| [`pr11c-cram-sheets.md`](pr11c-cram-sheets.md) | PR-11c | weak-area review packets — deliberately content-bearing (trap/correction/rule), never choices/isolated-key fields |
| [`pr11c-cram-sheets-review.json`](pr11c-cram-sheets-review.json) | PR-11c | independent review accept-with-fixes; F1 (major, domain-sort mis-ranking) + F2-F4 all fixed/documented before commit |
| [`pr12-definition-recall-growth.md`](pr12-definition-recall-growth.md) | PR-12 | +51 definition_recall items (45→96 goldset), grounded on existing cards; distribution + zero-card gaps + a fail-closed content_scale correction (single-bank growth must not hide the proof-scale caveat) |
| [`pr12-definition-recall-review.json`](pr12-definition-recall-review.json) | PR-12 | per-domain adversarial review — 51/51 accepted; 2 quality tells fixed pre-commit; misconception-tag looseness documented as a registry-coverage follow-up |
