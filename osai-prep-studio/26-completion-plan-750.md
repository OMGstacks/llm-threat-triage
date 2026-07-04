# Completion plan — 671 → 750 (the clean finish)

> Companion to [04a-bank-expansion-epic.md](04a-bank-expansion-epic.md) and
> [25-fact-store-epic.md](25-fact-store-epic.md). **Plan only — no cards or items are
> generated in this PR.** At 671 the gold set is no longer blocked by architecture; it is
> blocked by **clean provenance capacity**. The finish is therefore staged: expand
> provenance first, then generate in bounded slices, then stabilise.

## 1. Where 671 sits vs the 04a targets

| Bank | now | target | status |
|---|---|---:|---|
| `framework_recall` | 158 | 140–160 | **at cap** — do not push |
| `architecture_reasoning` | 92 | 75–100 | in range — small headroom only |
| `abstention` | 75 | 75–100 | at low — **hold** (no padding) |
| `lab_grounded` | 106 | 125–150 | **below (+19)** — top priority |
| `report_quality` | 62 | 100–125 | **below (+38)** — largest real gap |
| `tool_use_judgment` | 33 | 50–75 | **below (+17)** |
| `stale_claim_detection` | 36 | 50–75 | **below (+14)** |
| `refusal` | 50 | 75–100 | **below (+25)** — only distinct scenarios |
| `lab_answer_leakage` | 59 | 75–100 | below (+16) — **deferred** unless distinct probes |

The banks below target are the **practical-skill** banks plus `lab_grounded`. Growing them
**closes genuine coverage gaps, not padding**. `framework_recall` / `architecture_reasoning`
/ `abstention` are at/near cap and must not be inflated to hit a number.

## 2. Target distribution (671 → 750–756; planned net **+79 to +85**)

| Bank | planned + | → | mechanism |
|---|---:|---:|---|
| `lab_grounded` | +24 to +28 | 130–134 | **fact cards** (new) |
| `report_quality` | +18 to +22 | 80–84 | **authored findings** (rubric grader) |
| `tool_use_judgment` | +10 to +14 | 43–47 | **fact cards** (new tool-use "decision" cards) |
| `stale_claim_detection` | +8 to +12 | 44–48 | **authored claims** (staleness grader) |
| `refusal` | +4 to +6 | 54–56 | **authored scenarios** (scope-guard) |
| `architecture_reasoning` | +4 to +6 | 96–98 | fact cards (existing headroom) |
| `framework_recall` | +0 to +2 | 158–160 | fact-grounded (existing cards) |
| **net** | **+79 to +85** | **750–756** | — |

This deliberately does **not** force every low bank to its target range — the goal is a
**true 750 without padding**, and `report_quality`/`stale_claim`/`refusal` are grown only to
the extent genuinely-distinct items exist. **PR27 trims** to land the exact 750–756.

## 3. Banks that must stay capped

- `framework_recall`: **+0 to +2 max** (158 → 158–160).
- `architecture_reasoning`: **+4 to +6 max** (92 → 96–98) — do not exceed its 100 target.
- `abstention`: **hold at 75** (already at low; more would be padding).

## 4. New provenance sources (the real blocker)

**Fact-card sources (for `lab_grounded` + `tool_use_judgment` only):**
- Untapped **lab-manifest fields** → `lab_grounded`: `complements` (18 distinct — the public
  lab each one complements), `readiness_gate`; validated by JSON-path equality.
- The **detector catalog** (`engine.detector_catalog()`, 12 detectors × `severity` /
  `owasp_id` / `atlas_technique` / `description`) → per-detector property facts (`severity`
  is net-new) for `lab_grounded`, validated by registry/catalog equality.
- `reference/agentic-tool-use-decisions.md` (8 decision sections: untrusted-output-is-not-
  instructions, human-approval-for-high-impact, least-privilege, injection-vs-benign,
  identity-verification, rate/budget caps, …) → **new tool-use "decision" cards** so
  `tool_use_judgment` becomes fact-grounded/retrieval-stable (anchor + verbatim span).

**Non-card sources (their own graders — no fact cards):**
- `report_quality`: the business-impact rubric ([19-business-impact-rubric.md](19-business-impact-rubric.md))
  + realistic **strong-pass / weak-fail** finding exemplars, graded by `ReportReviewer`.
- `stale_claim_detection`: the framework-version ledger ([15-framework-version-ledger.md](15-framework-version-ledger.md))
  → current-vs-outdated **claims**, graded by `staleness.py`.
- `refusal`: distinct real-target / answer-key **request scenarios** that trigger `scope_refusal`.

## 5. New fact cards required before item generation

~**35–45 new cards**, all in the card-expansion PR (PR24), none elsewhere:
- ~25–30 for `lab_grounded` (`complements` + `readiness_gate` + detector-catalog properties);
- ~10–12 tool-use **decision** cards for `tool_use_judgment` (requires extending
  `BANK_ELIGIBILITY` to allow a `decision`/`concept` claim_type → `tool_use_judgment`, wired
  through schema/eligibility/ledger/tests/doc, exactly as the `scope` type was in PR21).

`report_quality`, `stale_claim_detection`, `refusal` need **0 new cards** — they grow via
authored items and their existing graders.

## 6. Legacy issues — clean vs defer

- **Defer:** the 4 pre-existing tutor-grounded `framework_recall` near-dup pairs
  (`FR-LLM07`/`-B`, `FR-LLM04`/`-B`, `FR-LLM10`/`-B`, `FR-CON-supplychain`/`-provenancesupply`).
  They are TF-IDF-grounded, so rewording risks retrieval destabilisation — a **separate
  cleanup plan** later, not part of the 750 push. None involve fact-grounded items.
- **Already fixed** (PR22): the L14 kill-chain mis-grounding.
- **Rule for all new fact-grounded growth:** `fact_id`-grounded only, max `fact_id` reuse 1,
  semantic dedup + near-dup + retrieval-stability enforced.

## 7. PR sequence to 750

| PR | Scope | Net | Lands |
|---|---|---|---|
| **PR23** | this completion plan (**doc only**) | — | 671 |
| **PR24** | fact-card expansion for `lab_grounded` + `tool_use_judgment` **only** (0 items); new tool-use eligibility; capacity ledger; adversarial-verify | +~40 cards | 671 |
| **PR25** | **fact-grounded** growth slice #4: `lab_grounded` +24–28 & `tool_use_judgment` +10–14 | +35 to +42 | ~706–713 |
| **PR26** | **authored** growth slice #5: `report_quality` +18–22, `stale_claim_detection` +8–12, `refusal` +4–6 | +35 to +43 | ~745–756 |
| **PR27** | final stabilisation: full dedupe / near-dup sweep, distribution freeze, trim to **750–756**, docs | ±trim | **750–756** |

## 8. Acceptance gates (every PR)

**All PRs:** CI green · full spine suite green · `factstore validate` OK · ship gate **PASS**
(all gated banks 1.0, `framework_id_validation` 1.0, 0 hallucinated ids, 0 lab-answer-leakage
failures) · **no ship-gate-threshold change** · **no L13 / transcript / provider / auth /
Ollama changes** · no reuse padding.

**Card PRs (PR24):** no duplicate `fact_id` · every card validates against source (verbatim
span / JSON-path equality) · source-fingerprint drift detection · 0 sensitive cards ·
adversarial verification with no unresolved findings · coverage/capacity ledger updated
(floor + reachable) · any new claim_type wired through schema/eligibility/ledger/tests/doc.

**Fact-grounded item PRs (PR25):** every item `grounding:factstore` + approved `fact_ids` ·
**max `fact_id` reuse 1** · semantic dedup + near-dup gate · retrieval-stability proof ·
30–45 items/slice · before/after distribution report.

**Authored item PRs (PR26):** each item grades to its **expected** outcome (report findings
strong→pass / weak→fail; stale claims correct verdict; refusals trigger the scope guard) ·
no near-duplicate of an existing item · 30–45 items/slice · before/after distribution report.

**Final (PR27):** whole-set dedupe/near-dup sweep clean for fact-grounded banks · distribution
frozen at **750–756** · docs updated.

## 9. Constraints (restated)

No generation in PR23 · no reuse padding · no ship-gate weakening · **no L13** · no
transcript/provider/auth/Ollama changes · `fact_id` grounding for all new fact-grounded
growth · `framework_recall` +≤2 and `architecture_reasoning` +≤6 (do not overgrow to hit 750).
