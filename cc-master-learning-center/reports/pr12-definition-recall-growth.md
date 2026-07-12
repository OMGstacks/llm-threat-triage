# PR-12 — definition_recall growth slice (+51 items)

**Slice type:** content growth (governance §16.0 / §12 fresh-main growth discipline).
**Bank:** `definition_recall` only. **Net add:** 45 → 96 practice goldset items (+51).
**Grounding:** every new item cites exactly one existing, active fact card already eligible for
`definition_recall` — **no new facts, no registry mutation, no holdout change.**
**Adversarial review:** completed *before* this commit — see
[`pr12-definition-recall-review.json`](pr12-definition-recall-review.json) (51/51 accepted).
**Gate status:** `make ci` green (scaffold, sources, IP, factstore, `quiz validate` 96/96,
holdout, mock, dashboard no-leak, cram, 393 unittests, deterministic ingestion).

---

## 1. What landed

| File | Change |
|---|---|
| `spine/gold/goldset.json` | +51 `definition_recall` items (existing 45 preserved byte-for-byte; additive append + stable id sort) |
| `spine/gold/answer-keys.json` | +51 isolated keys (exact `answer_key_hash` / `item_hash` via the shipped `quiz.py`) |
| `spine/cc_spine/dashboard.py` | `_content_scale()` made scenario-aware — a **fail-closed correction** the growth necessitated (§4 below) |
| `spine/tests/test_dashboard.py` | `test_content_scale_flags_proof_scale_with_caveat` updated to the corrected invariant |
| `reports/readiness-dashboard-sample.json` | regenerated (drift-checked committed sample; `practice_items` 45→96, caveat text refreshed) |

Items were authored by a per-domain author→review→revise pipeline, then assembled by a
**deterministic** assembler that imports `quiz.py`/`factstore.py` for exact hashing, preserves every
existing item, appends new items, round-robins correct-answer positions per objective, and runs
`validate_gold` as the write gate. Authoring (fallible, semantic) is fully separated from assembly
(exact, mechanical).

## 2. Distribution

### By domain (new items)
| Domain | New | def_recall total after |
|---|---|---|
| D1 | 12 | 30 (across its objectives) |
| D2 | 10 | — |
| D3 | 9 | — |
| D4 | 12 | — |
| D5 | 8 | — |
| **Total** | **51** | **69 def_recall / 96 goldset** |

Goldset composition after slice: **69** `definition_recall` · **14** `concept_discrimination` ·
**8** `scenario_application` · **5** `exam_strategy` = 96.

### By objective (new items / def_recall items now / eligible cards)
| Obj | New | def_recall now | eligible cards | headroom |
|---|---|---|---|---|
| 1.1 | 4 | 6 | 10 | 4 |
| 1.2 | 4 | 5 | 8 | 3 |
| 1.3 | 4 | 5 | 9 | 4 |
| 2.1 | 4 | 5 | 6 | 1 |
| 2.2 | 4 | 5 | 6 | 1 |
| 2.3 | 2 | 4 | 7 | 3 |
| 3.1 | 5 | 7 | 9 | 2 |
| 3.2 | 4 | 6 | 8 | 2 |
| 4.1 | 6 | 7 | 14 | 7 |
| 4.3 | 6 | 8 | 13 | 5 |
| 5.1 | 8 | 11 | 18 | 7 |

Every allocation stayed within available single-claim card capacity (one card grounds at most one
item — the single-competence rule; `headroom` = eligible cards not yet consumed).

### By difficulty (new items)
| Level | Count | |
|---|---|---|
| L1 (recall) | 37 | |
| L2 (comprehension) | 14 | |

No L3+ — discrimination / scenario-application / exam-trap difficulty belongs to the
`concept_discrimination` and `scenario_application` banks, not `definition_recall`.

### Correct-answer position (anti-pattern guard)
- **New 51:** index 0→12, 1→14, 2→14, 3→11 (max share 27% < the 40% cap; no all-same within any objective).
- **Full 96:** 0→24, 1→25, 2→26, 3→21.
- **answer_length_bias ratio:** 0.208 (warn threshold 0.40) — correct answers are not systematically longer.

### Misconception coverage (distractors)
- **153** distractor slots (51 items × 3), mapping to **35 distinct** misconception-registry entries.
- Category spread: `definition_confusion` 94 · `network_device_confusion` 22 ·
  `control_category_confusion` 19 · `crypto_property_confusion` 12 · `process_order_confusion` 6.
- Most-used: `osi-tcpip-confusion` (14), `control-category-function-confusion` (10),
  `physical-control-name-confusion` (10), `data-handling-term-confusion` (10),
  `risk-terminology-confusion` (9), `incremental-vs-differential-confusion` (9).
- Every distractor maps to a registry entry whose `objective ∈ {item.objective, global}` and whose
  `category` matches the recorded tag — enforced by the `distractor_registry` gate.

**Known limitation — misconception-tag precision.** Several distractors (concentrated in 4.1, the
2.x objectives, and 5.1) carry the *closest-available umbrella* misconception from the objective's
allowed list rather than an exact-fit entry — e.g. `osi-tcpip-confusion` on RFC-1918-range and
handshake-count lures; `data-handling-term-confusion` as the only `definition_confusion` umbrella in
5.1. Every such tag is still a valid, in-set, gate-passing entry; the looseness is a
**registry-coverage gap, not a correctness or fairness defect.** This slice deliberately did **not**
mutate `reference/misconception-registry.json` (scope kept to goldset + keys + reports + the
display-metric fix). Recommended follow-up: enrich the registry for 4.1 / 2.1 / 2.2 / 2.3 / 5.1 and
retag.

## 3. Structural gaps — zero-card objectives (documented, not filled)

Five current-outline (2025-10) objectives have **zero fact cards**
(`content_status.facts: false` in `reference/objective-matrix.json`), so **zero** `definition_recall`
items can be authored for them until upstream facts are ingested. These block on the *fact* layer,
not on this content-authoring layer:

| Obj | Title | Blocker |
|---|---|---|
| 1.5 | Understand governance processes | 0 facts |
| 4.2 | Understand network threats and attacks | 0 facts |
| 5.2 | Understand system hardening | 0 facts |
| 5.3 | Understand best practice security policies | 0 facts |
| 5.4 | Understand security awareness training | 0 facts |

**Deferred within this slice (not a structural gap):** objective **1.4** (ISC2 Code of Ethics) has
6 eligible cards but received 0 items this slice — skipped for thin misconception-registry coverage.
It is groundable in a later slice once the 1.4 misconception set is enriched. It is a *deferral*, not
a zero-fact structural gap.

Per the user's sequencing, the **next** slice unblocks the zero-card objectives (fact ingestion first),
and `scenario_application` growth follows only after the scenario fact base is stronger.

## 4. The `content_scale` fail-closed correction (learner-facing signal)

Growing `definition_recall` to 96 practice items pushed the dashboard's advisory
`content_scale` metric — `exam_scale = practice + holdout_scenarios >= mock_item_count_min` —
past its threshold (96 + 5 holdout scenarios = 101 ≥ 100), which **would have flipped the
learner-facing banner from `proof_scale` (with its "this is an engine proof, not exam readiness"
caveat) to `exam_scale` (caveat removed).**

That flip is **false confidence** and was corrected rather than accepted:

- The mock draws scenarios `holdout_only`, and the real CC exam is scenario-dominant. At 5 holdout
  scenarios, a "full-length" 100-item draw is ~95% recall — structurally unable to resemble the exam.
- The old proxy (`total items ≥ 100`) can be satisfied by **single-bank** growth, letting a
  definition_recall slice silently hide the caveat. That is exactly the normalized-false-confidence
  failure this project's discipline exists to prevent.

**Fix:** `exam_scale` now requires **both** enough total material **and** a holdout scenario pool that
reaches the scenario bank's own holdout floor — derived from `banks.json` as
`sum(per-domain scenario floors) × scenario.holdout_fraction` = `300 × 0.2` = **60**. With 5 holdout
scenarios (5 ≪ 60), the content stays **`proof_scale`**, and the caveat now names the real shortfall:

> content is proof-scale: only 5 of the 60 holdout scenarios a scenario-dominant exam draw needs
> exist — a passing mock here is an engine proof, not exam readiness

`content_scale` remains **display-only / advisory** — it never touches the readiness verdict or score
(the verdict already gates on scenario accuracy and still reads `not-ready`). This change only keeps
the *advisory banner* honest. No schema field was added; the `content_scale` dict keys are unchanged.

## 5. Rollback (§12)

This slice is additive and self-contained. To revert:
```
git revert <this commit>        # restores goldset/answer-keys to 45 items, dashboard.py, sample, tests
```
Nothing downstream depends on the new item ids; the pre-slice 45 items are untouched, so a revert
returns the stores and the `content_scale` metric to their prior state with no migration.

## 6. Provenance & guarantees (per item)

- **Grounded:** cites one active card eligible for `definition_recall`; `expected_keyword` is a
  verbatim case-insensitive substring of the card's claim+support (`unsupported_claim_guard`).
- **Single-claim:** no card grounds two items (single-competence rule).
- **Isolated:** no answer-bearing field leaks into learner-facing item; keys are separate with
  `answer_key_hash` + `item_hash`.
- **Distractor-registry backed:** every wrong choice maps to an in-objective (or global) registry
  misconception with matching category.
- **Anti-tell:** passes near-duplicate (Jaccard < 0.75 within objective), answer-position, answer-length,
  and choice-parallelism gates.
