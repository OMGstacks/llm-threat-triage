# PR-8c Holdout Lane Report

**Slice:** PR-8c — holdout lane proof (8 unseen items in a physically separate store).
**Derived from** `spine/gold/holdout.json` + `spine/gold/holdout-keys.json`.

Reviewer-approved scope: a small holdout lane that *proves the lane*, physically separate from
the practice set, with the `holdout_leakage_guard` activated. No large holdout set; no learner-lane
exposure.

---

## 1. The invariant this PR establishes

> No holdout stem, choice, answer, or misconception explanation appears in learner practice,
> remediation, tutor demos, or any non-holdout export.

Enforced by **physical separation** (the user's chosen design), not a flag inside the practice file:

| Lane | Item file | Key file | Who reads it |
|---|---|---|---|
| Practice | `spine/gold/goldset.json` | `spine/gold/answer-keys.json` | `quiz validate`, `quiz export-learner`, the practice quiz |
| Holdout | `spine/gold/holdout.json` | `spine/gold/holdout-keys.json` | `quiz validate-holdout` only (evaluator) |

`load_goldset()` / `learner_view()` / `export-learner` open **only** the practice files — the
holdout paths are never referenced on the learner path. Proven by test
(`PhysicalSeparationTest`, `test_practice_and_holdout_are_distinct_files`).

## 2. Holdout set

| Metric | Value |
|---|---|
| Holdout items | **8** |
| Concepts | risk, hot site, separation of duties, MAC vs RBAC, SSH port, OSI vs TCP/IP, data classification, hybrid encryption |
| Distinct from the 40 practice items | yes — different concepts and stems |
| Item ids | numbered `.9001`+ so they can never collide with practice ids |

**By domain:** D1 1 · D2 1 · D3 2 · D4 2 · D5 2.
**By bank:** definition_recall 5 · concept_discrimination 2 · scenario_application 1.
**Correct-index:** {0:3, 1:2, 2:1, 3:2} — varied (max 37.5%, under the 40% gate).

## 3. Gates the holdout lane passes

- **Same item gates as practice** (`quiz validate-holdout` runs `validate_gold`): grounding on
  active, bank-eligible cards; every `expected_keyword` resolves in a cited card; answer-key
  isolation; `answer_key_hash` + `item_hash`; registry-linked distractors; near-duplicate stem;
  answer-position; length/parallelism.
- **Lane partition** (`holdout_partition_problems`): every holdout item is `holdout:true`, every
  practice item is `holdout:false`, and no id appears in both lanes.
- **No leak into practice** (`holdout_leakage_problems`): no holdout stem appears verbatim in the
  learner export, and no practice stem near-duplicates a holdout stem (the derived-leakage vector).
- **Structural isolation** (scaffold `_check_holdout`): the holdout item file carries no
  answer-bearing field; keys live only in `holdout-keys.json`.

Shared short distractor *labels* (e.g. "Defense in depth") across lanes are domain vocabulary, not
leakage, and are intentionally not flagged — only the question and its answer matter.

## 4. Adversarial review (before commit, §16.0)

An independent reviewer (author ≠ reviewer) checked all 8 holdout items for factual accuracy,
single-best-answer, distractor plausibility, grounding fidelity, and stem quality. **0 findings.**
The reviewer stress-tested the hybrid-encryption scenario's strongest distractor (encrypt a large
file directly with the recipient's public key) and confirmed single-best-answer holds — RSA cannot
encrypt bulk data, so hybrid encryption remains the unique best answer.

## 5. Guard status after PR-8c

All tracked guards are now **active**: `source_freshness`, `ip_boundary`,
`no_verbatim_bulk_reproduction`, `unsupported_claim`, `answer_key_isolation`, and now
`holdout_leakage`. None remain reserved.

## 6. Reproducing

```
cd cc-master-learning-center/spine
python3 -m cc_spine.cli quiz validate-holdout    # holdout gates + partition + no-leak, OK
python3 -m cc_spine.cli quiz export-learner       # practice only — contains no holdout item
```
