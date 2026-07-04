# PR-7 Fact-Card Distribution Report

**Slice:** PR-6 + PR-7 combined fact-card seed (D1–D5).
**As of commit:** `2784802` (PR-7 fixup) · **outline:** 2025-10 · **generated from:** the live
card files under [`../spine/facts/`](../spine/facts/) and the bank contract in
[`../spine/banks/banks.json`](../spine/banks/banks.json).

This report is the persisted evidence for the PR-7 growth slice: what was produced, how it is
distributed, the slice-size exception, and whether the deck can support the PR-8 gold-item set.
Numbers are derived from the committed cards, not hand-entered.

---

## 1. Headline

| Metric | Value |
|---|---|
| Total validated cards | **149** |
| Domains with seed coverage | **5 / 5** |
| Objectives with cards | **12** (of 19 in the 2025-10 set) |
| Tier-0 (ISC2 blueprint) cards | 136 |
| Tier-1 (NIST) cards | 13 |
| `allowed_banks` ↔ eligibility mismatches | **0** |
| Sensitive / answer-key cards | 0 |
| Gate status | factstore validate ✅ · no-verbatim ✅ · IP-span ✅ · OSAI 217✅/6⏭ |

## 2. Distribution by domain

| Domain | Cards | Objectives seeded |
|---|---:|---|
| D1 — Security Principles | 41 | 1.1, 1.2, 1.3, 1.4 |
| D2 — BC / DR / IR | 26 | 2.1, 2.2, 2.3 |
| D3 — Access Controls | 23 | 3.1, 3.2 |
| D4 — Network Security | 37 | 4.1, 4.3 |
| D5 — Security Operations | 22 | 5.1 |
| **Total** | **149** | 12 objectives |

## 3. Distribution by objective

| Obj | Title | Cards |
|---|---|---:|
| 1.1 | Information assurance (CIA, AAA, non-repudiation, privacy) | 12 |
| 1.2 | Risk management process | 11 |
| 1.3 | Security controls | 11 |
| 1.4 | ISC2 Code of Ethics | 7 |
| 2.1 | Business continuity | 10 |
| 2.2 | Disaster recovery | 8 |
| 2.3 | Incident response | 8 |
| 3.1 | Physical access controls | 11 |
| 3.2 | Logical access controls | 12 |
| 4.1 | Computer networking | 20 |
| 4.3 | Network security infrastructure | 17 |
| 5.1 | Data security | 22 |

## 4. Distribution by claim type

| Domain | definition | concept | comparison | numeric_fact | procedure | exam_trap | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| D1 | 27 | 6 | 4 | 0 | 0 | 4 | 41 |
| D2 | 18 | 1 | 5 | 0 | 0 | 2 | 26 |
| D3 | 15 | 1 | 4 | 0 | 1 | 2 | 23 |
| D4 | 14 | 7 | 7 | 5 | 1 | 3 | 37 |
| D5 | 12 | 4 | 2 | 1 | 1 | 2 | 22 |
| **Total** | **86** | **19** | **22** | **6** | **3** | **13** | **149** |

No `mnemonic` cards were authored (per PR-6/7 scope). The deck is definition-weighted (58%),
which is expected for a foundational seed; the 22 comparison + 13 exam_trap cards are the primary
fuel for `concept_discrimination` items in PR-8.

## 5. Provenance by source tier

| Tier | Source | Cards | Grounds |
|---|---|---:|---|
| 0 | `isc2.cc-outline.2025-10` (local blueprint) | 136 | all objectives |
| 1 | `nist.sp800-145` | 5 | cloud (4.3) |
| 1 | `nist.sp800-88r2` | 5 | sanitization (5.1) |
| 1 | `nist.pqc.fips-203-204-205` | 3 | post-quantum crypto (5.1) |

Every card resolves to a local `.md`/`.json` anchor; the tier-1 NIST cards ground on dedicated
blueprint anchor sections, and the registry tier equals each card's `source_tier` (enforced by
`validate_card`). No card grounds on a raw transcript or on a concept-inventory `source_id`.

## 6. Bank-eligibility coverage (PR-8 readiness)

Cards eligible for each learner-facing bank, by domain (derived from `claim_type_eligibility` in
`banks.json`). This is the supply available to PR-8 gold-item authoring — an item can only cite
cards eligible for its bank.

| Bank | D1 | D2 | D3 | D4 | D5 | Total |
|---|---:|---:|---:|---:|---:|---:|
| `definition_recall` | 33 | 19 | 17 | 27 | 18 | 114 |
| `concept_discrimination` | 35 | 25 | 21 | 24 | 16 | 121 |
| `scenario_application` | 37 | 24 | 21 | 29 | 19 | 130 |
| `exam_strategy` | 6 | 1 | 1 | 12 | 5 | 25 |

**Readiness verdict:** every domain carries ≥16 cards eligible for each of the three core banks —
ample supply for the proposed PR-8 first gold set of 40 items (8 per domain). `exam_strategy` is
thin in D2/D3 (1 eligible card each), which is acceptable: that bank has a single global target
(floor 10 / cap 30) and PR-8 proposes only 2 exam-strategy items. No bank floor is reachable yet —
all floors remain 0-satisfied because no gold items exist. This report measures *card supply*, not
*bank fill*; bank fill begins in PR-8.

## 7. Slice-size exception (P0 governance note)

The program's growth-slice discipline is **40–75 items per slice** (governance spec §15). PR-7's
final slice was **90 cards** (92 authored, 2 near-duplicates removed), which exceeds that ceiling.

**Exception accepted, not rolled back**, on the following basis:

1. All deterministic gates passed (schema, eligibility, drift, IP-span, no-verbatim, freshness).
2. A full adversarial content review completed and its confirmed defects were fixed (see
   [`pr7-adversarial-review.md`](pr7-adversarial-review.md)).
3. PR-7 closes fact coverage across the three previously-unseeded domains (D1–D3) in one pass,
   which was the slice's stated purpose; splitting it would have fragmented a single coherent
   milestone with no correctness benefit.

**Forward rule (now recorded in governance spec §16):** future content-growth slices return to
**40–75 items** unless a larger slice is explicitly approved *before* implementation.

## 8. Reproducing this report

```
cd cc-master-learning-center/spine
python3 -m cc_spine.cli factstore validate     # 149 cards, 0 sensitive, OK
python3 -m cc_spine.cli factstore coverage      # machine-readable bank coverage
```

The counts above are a snapshot; re-derive from `spine/facts/*.json` after any card change.
