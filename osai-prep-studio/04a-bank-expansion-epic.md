# Bank Expansion Epic — reaching ~750 the right way

> Companion to [04-evaluation-harness.md](04-evaluation-harness.md). This epic tracks the
> build-out of the gold set from the **v0.3 milestone (280 items, 4 banks)** to the
> **~750-item, 9-bank** target — through **new grader-backed bank types**, not padding.

## Context

The gold set reached 280 quality-vetted items across four banks (framework_recall,
abstention, refusal, lab_answer_leakage). Those four are **structurally capped**:
`framework_recall` is bounded by corpus coverage, and the other three degrade into
near-duplicates past their design size. Padding them to 750 would make the dashboard bigger
while making the ship gate **weaker** — a padded compliance artifact.

The remaining ~470 items must therefore come from the **five unbuilt doc-04 bank types**,
each of which tests a genuinely different capability and needs **its own grader**. The rule
for this epic: **graders first, items second**, and every item carries a `bank`, `source`,
grader, expected behaviour, and failure mode.

## Non-negotiable process (per bank)

1. **Define the rubric** — what the bank tests and the exact pass condition.
2. **Implement the grader** in `goldset.py` and add it to the `GATE` (its pass-rate is
   hard-gated, so any item the grader fails blocks CI).
3. **Add a small seed set** (10–20 items) via generate-and-filter against the real tutor +
   the new grader.
4. **Prove the grader fails bad answers** — a unit test where a wrong / abstained /
   invented / hallucinated answer is graded `False`.
5. **Generate in batches of 25–50**, running the ship gate and **deduping (by id AND
   prompt)** after every batch.

No bulk generation without dedupe; no target-count padding; no bank without a grader.

## Sequence (by dependency + grading complexity)

| Phase | Bank(s) | Grader idea | Status |
|---|---|---|---|
| **1** | `architecture_reasoning`, `lab_grounded` | Grounded + cited + **required fact present** + **no invention** (anti-fabrication), over a new `reference/osai-studio-architecture.md` corpus doc | **✅ landed** — graders + gate + 28 vetted seeds (15 + 13) + grader-teeth test |
| **2** | `tool_use_judgment` | Grade the **decision** — the correct call (block / require-approval / untrusted / …) must appear and the wrong call must not; grounded in a new `agentic-tool-use-decisions.md` corpus doc | **✅ landed** — reuses the grounded grader via `_GROUNDED_BANKS`; 13 seeds; grader-teeth test asserts a wrong decision fails |
| **3** | `stale_claim_detection` | A rule-based staleness detector (`staleness.py`) flags version-sensitive/outdated claims against current ground truth and names the fresher fact; grader checks the **verdict** | **✅ landed** — `tutor.ask(mode="stale")` + grader hard-gated at 1.0; 20 seeds (10 stale / 10 fresh); module + grader-teeth tests |
| **4** | `report_quality` | Reuse the existing `ReportReviewer` rubric — item = finding + expected rubric outcome; the runner routes it through `reviewer.review` and the grader asserts pass/total matches | **✅ landed** — hard-gated at 1.0; 14 seeds (6 strong-pass / 8 weak-fail); grader-teeth asserts a wrong outcome fails both directions |

## Growth pass (post–Phase 4) — controlled slices toward ~750

All 9 bank types exist and are gated; the remaining work is **growth**, run as controlled
slices under strict guardrails (approved):

- Small PRs, **~75–125 items each**; generate in **batches of 25–50**.
- **Ship gate + dedupe + near-duplicate check after every batch** (near-dup = Jaccard on
  normalized tokens vs. same-bank items; padding candidates are dropped).
- Per-bank **caps** = the target column below (caps, not obligations — stop a bank early
  when it ceilings / quality degrades; the win is clean distinct items, not exactly 750).
- No bank grows unless its grader passes at 1.0; no gate weakening, no test deletion, no
  new runtime dependency. **Stop immediately** on any leakage, hallucinated taxonomy id,
  unresolved CI failure, or near-duplicate/padding pattern.
- **Report milestones at ~450 / ~550 / ~650 / ~750**, each with: total, per-bank count &
  pass-rate, provenance coverage, near-duplicate rate, leakage failures, hallucinated ids,
  abstention/refusal status, and generated/dropped counts.

Per-bank caps for the growth pass: framework_recall 150 · abstention 90 · refusal 90 ·
lab_answer_leakage 90 · architecture_reasoning 90 · lab_grounded 135 · tool_use_judgment 65 ·
stale_claim_detection 65 · report_quality 90.

### Growth log

- **Slice 1 → 451 (~450 milestone).** +96 vetted items (report_quality +25, lab_grounded
  +16, architecture_reasoning +12, tool_use_judgment +11, stale_claim_detection +10,
  abstention +10, lab_answer_leakage +6, refusal +4, framework_recall +2). Near-duplicate
  guardrail dropped 22 templated candidates (10.7% of generated). Ship gate PASS; all 9
  banks at pass-rate 1.0; 0 hallucinated ids; 0 leakage. Provenance coverage 451/451.
- **Slice 2 → 517.** +66 vetted items (report_quality +23, abstention +10,
  tool_use_judgment +9, stale_claim_detection +6, lab_answer_leakage +6, architecture_reasoning
  +4, framework_recall +3, refusal +3, lab_grounded +2). A corpus enrichment attempt
  regressed 4 `lab_grounded` items (retrieval shift) and was **reverted** — no-regression
  held. Ship gate PASS; all 9 banks 1.0; 0 hallucinated ids; 0 leakage.
  **Ceiling reached (honestly flagged):** `architecture_reasoning` (~31) and `lab_grounded`
  (~31) are **corpus-bound** — they cannot reach their 90/135 caps because the studio-
  architecture corpus can only ground so many distinct questions, and expanding it
  destabilizes retrieval for existing items. Realistic clean total without a dedicated
  lab-grounding rework is **~650–700**, not exactly 750; the win is clean distinct
  grader-backed items, not the number. Growth continues on the banks with genuine headroom.

## Target distribution (~750; ranges, not exact equality)

| Bank | Target |
|---|---:|
| framework_recall | 140–160 |
| abstention | 75–100 |
| refusal | 75–100 |
| lab_answer_leakage | 75–100 |
| architecture_reasoning | 75–100 |
| lab_grounded | 125–150 |
| report_quality | 100–125 |
| stale_claim_detection | 50–75 |
| tool_use_judgment | 50–75 |
| **Total** | **~750** |

## Acceptance criteria for "750 achieved"

- Every bank has a **grader** and is **hard-gated** (no ungated bank).
- No item without **provenance** (`bank`, `source`) or **expected behaviour**.
- **0** hallucinated taxonomy ids; **0** lab-answer-leakage failures.
- No **near-duplicate padding** (dedupe by id + prompt enforced each batch).
- Old **abstention/refusal** behaviour still passes (no regression).
- All **CI and ship gates green**, and every bank passes **independently**.
- The gate report includes per-bank: `item_count`, `source_corpus`, `grader_name`,
  `pass_rate`, and failure examples.

## Phase 4 result — all 9 bank types now stood up

- `report_quality` reuses the existing `ReportReviewer` (`report.py`): the runner routes a
  finding through `reviewer.review(finding, transcript)` and the grader asserts the rubric
  **outcome** matches (`passed == expected_pass`, plus optional `min_total`/`max_total`).
  Hard-gated at 1.0 (`_RATE_GATED_BANKS`).
- 14 vetted seeds — 6 strong findings that pass, 8 weak findings (missing evidence /
  reproduction / impact, or an invalid OWASP id) that fail. Grader-teeth asserts a wrong
  outcome fails in **both** directions.

**Milestone:** the epic's structural goal is met — **all nine grader-backed bank types now
exist and are hard-gated** (gold set **355 items**, ship gate PASS, suite 165 green). What
remains for ~750 is **growth**: scaling each bank to its target size in vetted batches of
25–50 with gate + dedupe after each — deferred to a growth pass, not padding.

## Phase 3 result

- New `staleness.py` — a rule-based detector keyed to current ground truth (OWASP is the
  2025 list; Excessive Agency is LLM06 not LLM08; CI needs no live LLM; the gold set is no
  longer four banks; 750 is not reached by padding). `check_claim` returns
  `{stale, fresher, guidance}`.
- `tutor.ask(mode="stale")` routes to it; `goldset.py` grades the **verdict**
  (`stale == expected_stale`, and a stale flag must name a fresher fact), hard-gated at 1.0.
- 20 vetted seeds (10 stale / 10 fresh — no false positives). A module test and a
  grader-teeth test (missed-stale, no-fresher, false-positive all fail). Gold set now
  **341 items**, ship gate PASS, suite 165 green.

## Phase 2 result

- New corpus doc `reference/agentic-tool-use-decisions.md` (untrusted-output-not-instructions,
  human-approval for high-impact, least privilege, injection-vs-benign, identity
  verification, rate/budget caps), wired into `tutor.DEFAULT_SOURCES`.
- The grounded grader was generalized to a `_GROUNDED_BANKS` set so `tool_use_judgment`
  is graded (and hard-gated at 1.0) exactly like the Phase 1 banks, with the *decision*
  as the required keyword and the opposite decision as `forbidden`.
- 13 vetted scenario seeds; the grader-teeth test now also proves a **wrong decision fails**.
  A corpus-introduced abstention regression (one item collided with new content) was
  caught by the gate and fixed — abstention stays at pass-rate 1.0. Gold set now **321
  items**, ship gate PASS, suite 164 green.

## Phase 1 result (this epic's first delivery)

- New corpus doc `reference/osai-studio-architecture.md` (component ownership, trust
  boundaries, two-signal + Signal C grading, per-lab attack→detector→defense), wired into
  `tutor.DEFAULT_SOURCES`.
- `goldset.py` grades `architecture_reasoning` + `lab_grounded` as grounded-and-cited with
  a **required-keyword / anti-invention** check; both hard-gated at pass-rate 1.0.
- 28 vetted seeds; a unit test proves the grader **fails** missing-fact, abstained,
  uncited, invented, and hallucinated answers. Gold set now **308 items**, ship gate PASS.
