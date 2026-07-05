# PR-8d Exam-Strategy Bank Report

**Slice:** PR-8d — fill the `exam_strategy` bank (the last empty learner-facing bank).
**Derived from** `spine/facts/_global.json` + the `exam_strategy` items in `spine/gold/goldset.json`.

Before PR-8d, `exam_strategy` had **zero** eligible cards — no fact card carried it in
`allowed_banks` — so the bank could hold no items. PR-8d seeds the global exam-logistics cards and
the first exam_strategy items, grounded on the official ISC2 exam facts.

---

## 1. What was added

| Artifact | Count | Notes |
|---|---|---|
| Global fact cards (`_global.json`) | **7** | scope `global`, grounded on `cc-exam-blueprint.md#exam-facts` (tier 0) |
| exam_strategy practice items | **5** | in `goldset.json`, `holdout:false` |
| Matrix extension | 1 | `global.exam-strategy` (so the cards' objective validates in the registry) |

**Cards** (all `numeric_fact` or `concept`, `allowed_banks: [definition_recall, exam_strategy]`):
`global.exam-duration`, `global.exam-item-count`, `global.exam-passing-score`,
`global.exam-delivery`, `global.exam-item-formats`, `global.outline-current`, `global.outline-next`.

**Items** cover: exam duration (2h/120min), passing score (700/1000 scaled), item count (100–125),
delivery (CAT), and item formats (multiple-choice + advanced innovative items).

## 2. How the global lane fits the model

- `scope: "global"`; `fact_id` prefixed `global.`; `tags.domain: []`; `tags.objective:
  ["global.exam-strategy"]`.
- The `global.exam-strategy` matrix extension makes the objective resolve in the registry (mirroring
  the existing `global.ai-security` extension), grounded on the blueprint `#exam-facts` anchor,
  source `isc2.cc-outline.2025-10`.
- The `exam_strategy` bank is `excluded_from_readiness` (banks.json): it helps the learner with
  logistics but must not inflate cybersecurity mastery. Its items are `holdout_fraction: 0.0` — they
  never enter the holdout/mock-exam scenario draw.

## 3. Full gold set after PR-8d

| Bank | Items | Target split |
|---|---:|---|
| definition_recall | 18 | (PR-8b) |
| concept_discrimination | 14 | (PR-8b) |
| scenario_application | 8 | (PR-8b) |
| **exam_strategy** | **5** | **new (PR-8d)** |
| **Total** | **45** | |

The `exam_strategy` bank floor is 10 (global); 5 items is a first slice, not the floor — the bank now
*works end-to-end* and can grow. Anti-gaming metrics still hold on the full 45-item set: correct-index
distribution stays under the 40% position gate, and the answer-length-bias advisory is **29% (13/45)**,
under the 40% target.

## 4. Adversarial review (before commit, §16.0)

An independent reviewer verified the 7 cards and 5 items against the official CC exam facts — factual
accuracy of each logistic value, single-best-answer, and distractor plausibility. Result recorded in
`pr8d-exam-strategy-review.json`.

## 5. Reproducing

```
cd cc-master-learning-center/spine
python3 -m cc_spine.cli factstore validate     # 156 cards incl. 7 global exam_strategy
python3 -m cc_spine.cli factstore coverage      # exam_strategy bank capacity now non-zero
python3 -m cc_spine.cli quiz validate           # 45 items, all four banks
```
