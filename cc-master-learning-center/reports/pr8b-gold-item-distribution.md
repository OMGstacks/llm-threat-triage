# PR-8b Gold-Item Distribution Report

**Slice:** PR-8b — first full gold set (40 non-holdout items), three core banks.
**As of:** the PR-8b commit · **derived from** `spine/gold/goldset.json` + `spine/gold/answer-keys.json`.

Reviewer-approved scope: exactly 40 items, bank split **18 definition_recall / 14
concept_discrimination / 8 scenario_application**, 8 per domain, no `exam_strategy` (deferred to
PR-8d), no holdout (deferred to PR-8c). Numbers below are derived from the committed files.

---

## 1. Headline

| Metric | Value |
|---|---|
| Gold items | **40** |
| Isolated answer keys | 40 (1:1) |
| Banks used | 3 core (definition_recall, concept_discrimination, scenario_application) |
| Distinct misconceptions targeted | 36 (registry now 37 entries) |
| Avg grounding fact_ids / item | 1.23 |
| Gate status | quiz validate ✅ · export-scan ✅ · factstore 149 cards ✅ · OSAI 217✅/6⏭ |

## 2. By domain (target 8 each)

| Domain | Items | scenario items |
|---|---:|---:|
| D1 | 8 | 1 |
| D2 | 8 | 1 |
| D3 | 8 | 2 |
| D4 | 8 | 2 |
| D5 | 8 | 2 |
| **Total** | **40** | **8** |

## 3. By bank (target 18 / 14 / 8)

| Bank | Items | Target |
|---|---:|---:|
| definition_recall | 18 | 18 |
| concept_discrimination | 14 | 14 |
| scenario_application | 8 | 8 |

## 4. By objective

| Obj | Items | Obj | Items | Obj | Items |
|---|---:|---|---:|---|---:|
| 1.1 | 3 | 2.2 | 2 | 3.2 | 5 |
| 1.2 | 2 | 2.3 | 3 | 4.1 | 4 |
| 1.3 | 2 | 3.1 | 3 | 4.3 | 4 |
| 1.4 | 1 | 5.1 | 8 |  |  |
| 2.1 | 3 |  |  |  |  |

**Objectives with no gold items yet:** 1.5, 4.2, 5.2, 5.3, 5.4 — these carry no seeded fact cards
(they were out of scope for the PR-6/7 fact seed), so no grounded item can be authored for them
until their cards land. Not a gap in this slice; a pointer for future fact-seed work.

## 5. By difficulty (L1 recall → L5 synthesis)

| L1 | L2 | L3 | L4 | L5 |
|---:|---:|---:|---:|---:|
| 5 | 15 | 18 | 2 | 0 |

Weighted toward L2/L3 (comprehension/discrimination), which suits a first grounded set; L4 scenario
depth is light and L5 (exam-trap synthesis) is absent — a target for later slices.

## 6. Anti-gaming metrics

| Metric | Value | Gate |
|---|---|---|
| Correct-answer index distribution | {0:10, 1:10, 2:11, 3:9} | ✅ no index > 40% (max 27.5%) |
| Same correct index across an objective | none | ✅ per-objective gate |
| Near-duplicate stems (within objective) | none | ✅ Jaccard gate |
| **Answer-length bias** (correct is the single longest choice) | **21/40 (52%)** | ⚠️ advisory, not yet gated |
| Conspicuous length tell (correct > 1.5× every distractor) | **0/40** | fixed in review |

**Length-bias note.** Three items where the correct answer carried a "because …" justification tail
the distractors lacked (up to 2.26× longer) were flagged by the adversarial review and trimmed;
after fixes, no item has a conspicuous (>1.5×) tell. The residual 52%-longest figure reflects that a
fully-correct answer is often naturally more complete than a terse distractor; it is above the 25%
chance line and is recorded here as a tracked metric. **Target for PR-8b-onward authoring: < 40%,
by giving distractors parallel length/detail.** A formal length-bias gate is proposed for a future
hardening slice (analogous to the answer-position gate) once distractor-balancing patterns are
established.

## 7. Grounding & misconception coverage

- Every item cites 1–2 active fact cards (avg 1.23); all are bank-eligible; every `expected_keyword`
  resolves in a cited card (unsupported_claim_guard).
- 36 distinct misconceptions are targeted across the 40 items; the misconception registry grew from
  8 → 37 entries, each distractor set naming a specific, resolvable registry id.

## 8. Reproducing this report

```
cd cc-master-learning-center/spine
python3 -m cc_spine.cli quiz validate        # 40 items / 40 keys, OK
python3 -m cc_spine.cli quiz export-learner   # the learner projection (no answers)
```
