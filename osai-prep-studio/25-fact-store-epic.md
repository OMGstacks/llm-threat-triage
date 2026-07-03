# Structured Fact Store — retrieval-stable grounding toward a defensible "true 750"

> Companion to [04a-bank-expansion-epic.md](04a-bank-expansion-epic.md) (which deferred
> this work) and [04-evaluation-harness.md](04-evaluation-harness.md). **PR1 = design +
> a 2–3 lab pilot only** — no mass generation, no ship-gate change, feature-flag-free.
> The gold set stays hard-gated at pass-rate 1.0 on every bank.

## 1. The problem this removes

Two grounded banks — `architecture_reasoning` and `lab_grounded` — were **corpus-bound**.
They could only be graded as *grounded + cited* by making the extractive tutor retrieve a
supporting chunk from a single free-text doc (`reference/osai-studio-architecture.md`) via
**global TF-IDF**. Growth and stability were in direct tension:

- adding content to that doc shifts TF-IDF term weights, so an existing item's top-
  retrieved chunk can change and its required fact drops out of the answer → it fails;
- Slice 2 of the bank-expansion epic lost 4 `lab_grounded` items exactly this way and was
  reverted. The honest ceiling without a rework was ~650–700, not 750.

The fix is not "write more prose." It is to **stop grounding these banks on a competitive
retrieval** and ground them on **addressable, provenance-backed facts** instead.

## 2. The unlock — deterministic, `fact_id`-keyed grounding

A gold item opts into the new path with `"grounding": "factstore"` and a list of
`fact_ids`. At grade time the runner resolves those ids by **exact keyed lookup** in the
`FactStore` and builds the answer + citations from the cited cards — never TF-IDF.

Because lookup is keyed, it is **additive**: adding card *N+1* cannot change the citation
of any item grounded on cards *1..N*. That property is not asserted, it is **proved** by a
regression test (`test_adding_a_card_does_not_change_existing_citations`) — the direct
antidote to the Slice-2 regression. This is what makes growth toward 750 *defensible*:
volume that is provenance-backed and retrieval-stable, not padding.

```
gold item  ──cites──▶  fact_ids  ──keyed lookup──▶  fact cards  ──validated against──▶  authoritative source
(grounding: factstore)                              (claim+provenance)                  (lab manifest / registry / ref-doc)
```

The extractive tutor's TF-IDF was always just a stand-in for "grounded + cited." The fact
store is a stronger, deterministic grounding source; when the generative tutor is enabled
later, the cited card claims are handed to it as its SOURCES and the same gate runs against
its output, so the anti-hallucination guarantee holds either way.

## 3. Fact-card schema (`osai-prep-studio/spine/facts/*.json`)

One JSON file per lab (`L03.json`, …) plus `_global.json`; each is a list of cards.

| Field | Meaning |
|---|---|
| `schema_version` | card schema version (currently `1`) |
| `fact_id` | stable, globally-unique, human-readable id (`L03.detector`, `global.two-signal-definition`) |
| `scope` | `L{nn}` or `"global"` |
| `claim_type` | `detector` \| `framework_mapping` \| `evidence_path` \| `architecture` \| `defense` \| `module` \| `concept` |
| `tags` | `{owasp, atlas, agentic, topic}` — validated framework ids |
| `claim` | the human-readable fact (what the learner answer asserts) |
| `source` | **repo-root-relative** provenance path: `…/labs/L03.json#two_signal_grading.detector_required` (structured) or `reference/…md#anchor` (markdown) |
| `support` | the exact reviewed provenance span — the structured value (string/list) or a verbatim markdown quote |
| `source_fingerprint` | `sha256:…` over the canonical `support`, recomputed from the live source at validate time for **drift detection** |
| `learner_visible` | may the claim appear in a learner-facing answer? |
| `answer_key_sensitive` | is this grading-key / secret material? |
| `allowed_banks` | banks this card is authorised to ground |
| `difficulty`, `exam_relevance` | authoring metadata / AI-300 module |
| `status` | `active` \| `deprecated` \| `draft` (only `active` may ground a live item) |
| `last_reviewed`, `reviewed_by` | review provenance |
| `deprecated_by` | successor `fact_id` — **required** when `status=deprecated` (no silent rename) |
| `sensitive_override` | explicit escape hatch to let a sensitive card serve a learner bank |

## 4. Provenance model — extracted, not free-authored

Every card is **derived from an authoritative record already in the repo** and validated
**structurally** against it (never "a keyword happens to appear somewhere"):

| Source kind | Validation |
|---|---|
| **structured** (`labs/L{nn}.json#json.path`) | resolve the JSON path; assert `support == value` (equality); registry membership for `detector` (∈ `detector_catalog()`) and `framework_mapping` (valid OWASP/ATLAS/Agentic id); the `claim` must literally contain the asserted value |
| **markdown** (`reference/…md#anchor`) | the anchor section must exist; the `support` quote must be a substring of the current section; fingerprint over the normalised span |

On top of that, a **`source_fingerprint`** is recomputed from the live source at validate
time; if the underlying manifest field or reference section changes, the fingerprint no
longer matches and the card **fails until a human re-reviews it**. Provenance paths without
drift detection would let a card keep looking valid after its source moved — so both are
required.

## 5. Validator suite (fail-closed; stdlib; offline)

**Card** (`validate_card`): schema completeness + known enums; `allowed_banks` ⊆ known
banks **and** ⊆ the claim_type's eligibility set (`BANK_ELIGIBILITY`, defence-in-depth);
structural provenance + registry membership (§4); **fingerprint drift**; the claim mentions
the asserted value; **secret scan** (`llm.residual_secrets` + a flag-token check — no
`OSAI{…}`, key, PEM, PAN, or email may live in a card, whatever its labels); **sensitivity
quarantine** — a `answer_key_sensitive`/`learner_visible:false` card may not serve a
learner-facing bank unless it carries an explicit `sensitive_override`.

**Store** (`validate_store`): every card valid; **no duplicate `fact_id`** across files; a
`deprecated` card must tombstone to an existing successor (`deprecated_by`) — a fact_id is
retired, never silently renamed.

**Gold item** (`validate_item`): a `grounding:factstore` item must carry non-empty
`fact_ids`; every id exists, is `active`, and lists the item's bank in its `allowed_banks`;
every `expected_keyword` is **supported** by the union of the cited cards (an unsupported
claim fails). Wired into CI as `osai_spine.cli factstore validate` and asserted by
`tests/test_factstore.py`.

## 6. Pilot (this PR) — L03, L08, L11

17 fact cards (L03 ×4, L08 ×5, L11 ×6, global ×2) across all seven claim types, and **13
fact-grounded gold items** (8 `lab_grounded`, 5 `architecture_reasoning`) that ground
**only** via `fact_ids` — demonstrating in miniature that new items in these banks no
longer touch the free-text architecture doc. Gold set 517 → **530**; both target banks
still hard-gated at 1.0.

`factstore validate` also prints a **coverage ledger** (cards per lab / claim_type / bank /
framework tag, sensitive count, by-status) — the seed for PR2's capacity report, so we can
see whether the store can actually support 750 *before* generating items.

## 6a. PR2 — full-lab expansion + capacity ledger (cards only)

PR2 expands the store to **every lab except L13** — **cards only, no gold-set generation, no
ship-gate change**. Cards are **deterministically extracted** from each manifest (every
`support` is the exact value at its provenance path, so structural validation is correct by
construction), plus 4 new global architecture/concept cards (6 global total) and the L20
blue-team capstone. The three PR1 pilot labs (L03/L08/L11) are **backfilled to the same
template** so per-lab coverage is uniform. Result: **17 → 137 cards**; ship gate unchanged
(**530**, all banks 1.0); `factstore validate` OK; full suite green.

**Lab coverage.** L01–L12 and L14–L19 are attack labs with a `two_signal_grading` manifest;
each gets detector, OWASP + ATLAS framework, module, kill-chain, and defense cards — plus an
Agentic-threat card where the manifest maps one (L11/L12/L14/L15/L16), an evidence-log card
where the manifest has a non-flag `/logs` or `/state` token (so L01/L04/L07, whose only token
is a flag, have none), and **L14's Signal-C causal-chain fact**. **L20** is the *blue-team
triage capstone* — it has no attack manifest, so it is represented by two architecture/concept
cards grounded in the `reference/osai-studio-architecture.md` L20 section. **L13 is deliberately
excluded** per the standing "do not touch L13" constraint. `test_all_labs_except_l13_have_fact_cards`
asserts every other lab (incl. L20) is covered and L13 is absent.

**Coverage / capacity ledger** (`factstore validate`):

| Metric | Value |
|---|---|
| cards | **137** active / 137 total · 0 sensitive · all `active` |
| per claim_type | detector 18 · framework_mapping 41 · module 18 · architecture 24 · defense 18 · evidence_path 15 · concept 3 |
| per lab | L01–L12, L14–L20 (6–9 cards each; L20 ×2) + 6 global |
| capacity `architecture_reasoning` | 122 cards → 122–244 items — **clears target 75–100 at the 1-item/card floor** |
| capacity `lab_grounded` | 110 cards → 110–220 items — **reaches target 125–150 above the floor (≤2 phrasings/card)** |

The ledger answers "can the store support 750 without padding?" honestly: `architecture_reasoning`
already exceeds its target at the conservative 1-item-per-card floor; `lab_grounded` (110
cards) sits just below its 125 floor and reaches 125–150 with ~1.2–1.4 items/card — reachable
without padding, but **not** at the floor. Either way PR3 growth is grounding-limited by real
facts, not raw-corpus retrieval.

## 7. Answer-key safety

The public/sensitive boundary is the one the codebase already draws: per-lab
detector/OWASP/evidence-**path** mappings are **public educational content** (they live in
the committed lab manifests, which contain paths, never flag values); the per-learner
**flag value**, hidden **rubric** prose, and grading internals are **sensitive**. The
validator enforces this two ways — a structural secret scan on every card, and a
sensitivity quarantine that keeps `answer_key_sensitive` cards out of learner banks unless
explicitly overridden. All 137 shipped cards are public, non-sensitive; the sensitive path is
exercised by tests, not shipped.

## 8. Epic sequence

| PR | Scope | Gate after |
|---|---|---|
| **PR1** (this) | FactStore + schema + validators + drift/lifecycle + pilot on L03/L08/L11 + `factstore validate` CLI + docs | CI green; ship gate unchanged/PASS; `factstore validate` OK |
| **PR2** | expand cards across all labs (extracted + validated); **coverage/capacity ledger** so we know whether 750 is reachable without padding | ledger + validate green |
| **PR3** | grow `architecture_reasoning` + `lab_grounded` in **50–75-item slices**, every item `fact_id`-grounded | ship gate + dedupe + retrieval-stability after each slice |
| **PR4+** | continue 650 → 750 with dedupe + gate per slice; milestone reports | same |

## 9. PR1 acceptance gate — result

- ✅ CI green; full spine suite **243 passed**; ship gate **PASS** at 530 (banks 1.0)
- ✅ `factstore validate` OK; **no duplicate `fact_id`**; every pilot card validates against its source
- ✅ every pilot item cites approved `fact_ids`; `architecture_reasoning` + `lab_grounded` pilot items pass **1.0**
- ✅ unsupported claims fail; leaked flags/secrets/rubric internals fail; **draft/deprecated cards cannot ground a live item**
- ✅ **source drift is detected** (fingerprint mismatch); structural (non-substring) validation enforced
- ✅ **retrieval-stability test** proves adding a new card does not change existing citations
- ✅ **no auth / OSAI_LLM_TRANSCRIPTS / provider-key / Ollama / L13 / ship-gate-threshold changes**
