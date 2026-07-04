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
| `claim_type` | `detector` \| `framework_mapping` \| `evidence_path` \| `architecture` \| `defense` \| `module` \| `concept` \| `scope` \| `reference` \| `detector_property` \| `decision` |
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
| **catalog** (`catalog:detectors#{name}.{property}`, PR24) | resolve the property off `engine.detector_catalog()` by detector name; assert `support == value` (equality) exactly like a structured source; a non-empty string for `detector_property`; the `claim` must literally contain the asserted value. An unknown detector name resolves to a provenance failure. |

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

## 6b. PR3 — first controlled growth slice (530 → 602)

The first growth slice adds **72 fact-grounded gold items** (37 `lab_grounded`, 35
`architecture_reasoning`), every one `grounding:factstore` + `fact_ids` — no TF-IDF. Two
guardrails keep it padding-free:

- **Semantic dedup.** A candidate is skipped if its `(bank, lab, fact_type)` is already
  tested by any existing item. This is why the slice concentrates on the fact types the
  corpus set never covered — **ATLAS techniques (10), AI-300 modules (12), per-lab
  kill-chain stages (12), per-lab evidence paths (9)** — plus the uncovered labs' detector
  (10) / owasp (5) / agentic (3) / defense (11). Every item cites a **distinct** card
  (max `fact_id` reuse = 1).
- **Near-duplicate filter.** No same-bank prompt pair may reach Jaccard ≥ 0.7 (prompts
  carry the lab title + rotated phrasings). After the slice, the whole bank's max pairwise
  Jaccard is 0.60 (`lab_grounded`) / 0.56 (`architecture_reasoning`); a regression test
  (`test_no_near_duplicate_prompts_in_grounded_banks`) enforces it. Five PR1-era pilot
  prompts that were near-duplicates were reworded (deterministic grading is unaffected).

Result: gold set **530 → 602**; `lab_grounded` 39 → 76, `architecture_reasoning` 36 → 71;
**85 fact-grounded items** total. Ship gate **PASS** (both banks 1.0), `factstore validate`
OK, retrieval-stability test still green.

**Slice #2 (602 → 635).** +33 net-new fact-grounded items (18 `architecture_reasoning`,
15 `lab_grounded`), targeting the coverage gaps the slice-#1 distribution surfaced:
per-lab `architecture_reasoning` (kill-chain/module/defense) for **L15–L19** and the **L20**
capstone (bespoke role/focus prompts on its PR2 cards), plus `lab_grounded` atlas/evidence/
detector for the thin labs. Every lab L01–L19 now has an even 3 per-lab `architecture_reasoning`
items; L20 has 2. Each item cites a **distinct** card (max `fact_id` reuse = 1), 0 near-dups.
**118 fact-grounded items** total; `lab_grounded` 91, `architecture_reasoning` 89.

**Honest ceiling.** 635 (not the 660–675 target) is where the slice stops **on purpose**:
it is the clean maximum at `fact_id` reuse = 1 with the current 137 cards (agentic and most
owasp/detector facts are already tested). Reaching ~675 would require either a second
distinct phrasing per card (reuse = 2) or a further **fact-card expansion** (more
provenance-backed facts) — preferring "stop lower over forced reuse," this slice stops at
635. The next lever for clean growth is more cards, not more phrasings.

## 6c. PR21 — fact-card expansion (cards only, 137 → 183)

Slice #2 stopped at 635 because net-new facts were exhausted at `fact_id` reuse = 1. PR21
lifts that ceiling by adding **46 provenance-backed fact cards — no gold items**:

- **29 framework concept cards** — OWASP **LLM01–10** and OWASP Agentic **T1–T15**
  definitions, plus MITRE ATLAS and NIST AI RMF concepts, each an **anchor + verbatim span**
  from the reference corpus (`owasp-llm-top-10.md`, `owasp-agentic-threats.md`,
  `mitre-atlas.md`, `nist-ai-rmf.md`).
- **15 `authorized_scope` cards** — a new **`scope` claim_type** wired through schema
  validation, the bank-eligibility matrix, the coverage ledger, tests, and this doc — one per
  lab whose authorized scope is meaningfully distinct (L01/L04/L07 skipped as generic;
  **L13 excluded**), JSON-path-validated against the manifest.
- **2 architecture cards** — the previously-uncarded `data-handling choke point` and
  `lab range overview` sections.

Store **137 → 183 cards** (0 sensitive, all active; 0 duplicate ids). Refreshed capacity:
`lab_grounded` **125 cards → now clears its 125–150 target at the 1-item/card floor**;
`architecture_reasoning` **168 cards** (far above 75–100). Ship gate unchanged at **635**;
`factstore validate` OK; full suite green. This unlocks PR22 growth toward ~675–700 without
forced reuse.

## 6d. PR22 — growth slice #3 (635 → 671)

Puts PR21's new cards to work: **+36 fact-grounded items** (21 `architecture_reasoning`,
15 `lab_grounded`), every one `grounding:factstore` + a **distinct** `fact_id` (max reuse 1),
0 near-dups (bank max 0.60 / 0.64).

**Bank allocation is by learning objective** (decided at review): framework ID/category
recognition belongs in `framework_recall`, not `architecture_reasoning`.

- **15 `authorized_scope` items** → `lab_grounded` (91 → 106) — per-lab scope-discipline facts.
- **18 framework-APPLIED items** → **`framework_recall`** (140 → 158): OWASP LLM01–10 (10) and
  OWASP Agentic T1–T15 (8) as **scenario→category** questions (e.g. *"A web UI renders raw
  model output as HTML with no sanitization, yielding stored XSS — which OWASP category?"*),
  grounded on the PR21 concept cards (answer = the category id). The concept cards'
  `allowed_banks` were extended to include `framework_recall` to home them correctly.
- **3 genuine architecture/causal items** → `architecture_reasoning` (89 → 92): L14 Signal-C,
  lab-range, transcript choke-point.
- **PR20 bug fixed:** the existing `AR-fs-L14-killchain` asked the kill-chain question but was
  mis-grounded on the causal-chain card (expecting `tool_call`); repointed to the matching
  `L14.killchain` card (answer "impact"), and the freed causal-chain card now grounds its own
  `AR-fs-L14-causal` item.

Result: gold set **635 → 671** — `framework_recall` 140→**158**, `lab_grounded` 91→**106**,
`architecture_reasoning` 89→**92** (stays within its 75–100 target). Ship gate **PASS** (all
gated banks 1.0, `framework_id_validation` 1.0, 0 hallucinated ids); `factstore validate` OK;
retrieval-stability green; suite 251. Every new item cites a **distinct** `fact_id` (reuse 1);
the fact-grounded items are near-dup clean in every bank. (Four *pre-existing*, tutor-grounded
`framework_recall` near-dup pairs are a legacy artifact left untouched — rewording them would
destabilise TF-IDF retrieval.)

## 6e. PR24 — final card expansion for the 750 path (cards only, 183 → 220)

The last card-expansion PR before the 671 → 750 growth slices (26-completion-plan-750.md).
**+37 provenance-backed fact cards, 0 gold items**, targeting the two banks the completion
plan grows next — `lab_grounded` and `tool_use_judgment`:

- **18 `complements` cards** (new **`reference`** claim_type) → `lab_grounded` — one per lab
  that names the public resource it complements (`#complements`, JSON-path equality;
  **L13 excluded**; L20 declares no complement, so it has none).
- **12 detector-severity cards** (new **`detector_property`** claim_type, new **`catalog`**
  source kind) → `lab_grounded` — each asserts a detector's `severity` resolved live off
  `engine.detector_catalog()` (`catalog:detectors#{name}.severity`), validated by equality
  exactly like a structured source. This makes the reused detector taxonomy's severities
  first-class, drift-checked fact cards.
- **7 tool-use decision cards** (new **`decision`** claim_type) → `tool_use_judgment` — the
  seven allow/block/require-approval rules in `reference/agentic-tool-use-decisions.md`
  (untrusted tool output, human approval for irreversible actions, least privilege,
  injection-vs-benign, direct-vs-indirect, identity verification, rate/budget caps), each an
  **anchor + verbatim span**. This is the first time `tool_use_judgment` gets fact-grounded,
  retrieval-stable cards (its 33 existing items are authored/keyword-graded).

**New wiring (all four extensions carried through the whole stack):** `reference`,
`detector_property`, `decision` added to `CLAIM_TYPES` and `BANK_ELIGIBILITY`
(`decision → {tool_use_judgment, architecture_reasoning}`; the other two → `{lab_grounded,
architecture_reasoning}`); the `catalog` source kind added to `_source_kind`,
`_read_source_value` (resolves off `engine.detector_catalog()`), the equality/claim-mention
checks, and a `detector_property` registry check; the coverage ledger now reports
`tool_use_judgment`; **7 new tests** cover the claim-type/eligibility wiring, complements
cards, catalog-source validity + equality-drift + unknown-detector failure, decision-card
grounding, and the honest capacity verdict.

**Two honest reconciliations with the plan's estimates:**
- **`readiness_gate` deferred (deliberate).** Doc 26 listed it as *one of three* candidate
  `lab_grounded` sources to reach "~25–30 cards"; `complements` (18) + detector-severity (12)
  already hit **30**, and `lab_grounded` has ample unused headroom (below), so carding a
  low-distinctiveness uniform field (only `R3`/`R4`/`R5` across 19 labs, marginal exam
  relevance) — against the standing "skip uniform fields" guidance — would add a new
  claim_type for no needed capacity. Left for a later PR only if a distinct question shape
  emerges.
- **7 decision sections, not 8.** The plan estimated "8 sections → 10–12 decision cards";
  the reference doc has exactly **7** sections, all carded (no padding). So
  `tool_use_judgment` fact-grounded headroom is **+7 at reuse = 1** (not +10–14). PR25's
  `tool_use_judgment` growth is therefore capped at **+7** from fact cards; the rest of its
  climb toward the 50–75 bank target comes from **authored** items — consistent with how that
  bank already works. The coverage ledger reports this honestly (`tool_use_judgment`:
  7 cards → 7–14 items, **short** of the 50–75 target even at 2×).

**Capacity ledger — PR25 headroom (the gate).** Store **183 → 220 cards** (0 sensitive,
all active, 0 duplicate ids). Unused groundable cards at reuse = 1: **`lab_grounded` 44**
(155 eligible − 111 consumed) **+ `tool_use_judgment` 7** = **51 distinct cards**, comfortably
covering the plan's PR25 target of **+35 to +42** fact-grounded items (`lab_grounded` +24–28 &
`tool_use_judgment` +7). Ship gate **PASS**, gold set **unchanged at 671**; `factstore validate`
OK; retrieval-stability green; suite **258**. No L13 / transcript / provider / auth / Ollama
changes.

## 6f. PR25 — fact-grounded growth slice #4 (671 → 706)

Puts PR24's new cards to work: **+35 fact-grounded items**, every one `grounding:factstore`
+ a **distinct** `fact_id` (max reuse **1**), 0 near-dups, retrieval-stable.

- **+28 `lab_grounded`** (106 → **134**, the top of its 130–134 target): **16 `complements`**
  (one per lab, topic-enriched prompts, two phrasings; L06/L07 dropped as duplicate-answer of
  L05/L04), **9 detector-severity** (spanning critical/high/medium tiers), **3 `detector`**
  (L01/L02/L17). `indirect_prompt_injection.severity` was intentionally left out — its prompt
  near-dups `direct_prompt_injection.severity` (shared `prompt`+`injection` name tokens); the
  detector itself is still covered via the `L02.detector` item.
- **+7 `tool_use_judgment`** (33 → **40**): the seven agentic decision cards, each a
  scenario → decision (block / require human approval / allow / throttled). First
  fact-grounded/retrieval-stable items in this bank.

**Why it lands at the +35 floor (706), not higher.** The completion plan's PR25 upper end
(+42 → 713) assumed `tool_use_judgment` +10–14; PR24 established the honest cap is **+7** (only
7 real decision sections). `lab_grounded` is at its plan ceiling (+28 → 134). The remaining
plan headroom is `architecture_reasoning` +4–6 — but its only unused genuine-reasoning cards
are 3 same-`(global, architecture)`-slot platform cards, and the other unused arch-eligible
cards are framework-*recognition* facts that belong in `framework_recall` (the PR22 lesson),
so growing arch here would be padding or a bank misassignment. Landing at **+35 → 706** is the
clean, honest maximum for this slice; PR26 (authored `report_quality`/`stale_claim`/`refusal`)
carries the rest toward 750–756.

| bank | before | after | Δ |
|---|---:|---:|---:|
| `lab_grounded` | 106 | 134 | **+28** |
| `tool_use_judgment` | 33 | 40 | **+7** |
| all others | — | — | 0 |
| **total** | **671** | **706** | **+35** |

**Adversarial pass** (2 finders → verify): 1 confirmed defect fixed — `LG-fs-L01-detector`'s
keyword `direct_prompt_injection` is a substring of the sibling detector
`indirect_prompt_injection` (the only such collision in the catalog), so a wrong "indirect"
answer would pass substring grading; added `indirect_prompt_injection` to that item's
`forbidden`. One low finding refuted (immaterial to the deterministic grader), but the
`TUJ-fs-verify-identity` prompt was reframed anyway to test the unambiguous principle
(verify identity → identity spoofing) rather than the card's co-equal block/approval branch.

Ship gate **PASS** (all gated banks 1.0, `framework_id_validation` 1.0, 0 hallucinated ids,
0 lab-answer-leakage); `factstore validate` OK; near-dup + semantic-dedup + retrieval-stability
green; reuse = 1 (0 reused); 0 answer-key/flag leakage; suite **258**. No authored
report/stale/refusal items (those are PR26). No L13 / transcript / provider / auth / Ollama
changes.

## 7. Answer-key safety

The public/sensitive boundary is the one the codebase already draws: per-lab
detector/OWASP/evidence-**path** mappings are **public educational content** (they live in
the committed lab manifests, which contain paths, never flag values); the per-learner
**flag value**, hidden **rubric** prose, and grading internals are **sensitive**. The
validator enforces this two ways — a structural secret scan on every card, and a
sensitivity quarantine that keeps `answer_key_sensitive` cards out of learner banks unless
explicitly overridden. All 183 shipped cards are public, non-sensitive; the sensitive path is
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
