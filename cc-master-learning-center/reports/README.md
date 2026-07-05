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
