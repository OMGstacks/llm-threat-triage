# CC Master Learning Center — Governance Specification

**Date:** 2026-07-04
**Program:** ISC2 Certified in Cybersecurity (CC) Master Learning Center
**Repository:** `OMGstacks/llm-threat-triage` (project directory: `cc-master-learning-center/`)
**Pattern source:** `osai-prep-studio/` fact-store governance (PR #16–#22 sequence)
**North Star:** Turn messy instructor transcripts into a complete exam-aligned, active-recall,
scenario-based CC certification prep system that teaches, tests, remediates, and tracks
readiness — governed the same way the OSAI prep studio is governed: provenance-backed,
deterministic, hard-gated, and grown in small proven slices.

---

## 1. Executive Summary & Mission

This document is the governance spine for a CC exam-prep content system. It is delivered by
**PR-1**, which is a **governance/scaffolding PR — not a content PR, not an exam-prep pilot**.
PR-1 ships this spec, the reference layer (exam blueprint, objective matrix, source registry,
source policy), the schema contracts, the correction-dictionary seed, empty fact/gold stores,
and a stdlib scaffold validator. No study content is generated, no transcripts are ingested,
and no CI or shared repo surface is touched.

Mission: pass the CC exam on the first attempt by making the learner do four things
repeatedly — understand the concept, recognize the exam wording, apply it in a scenario, and
explain why the other answers are wrong.

Program deliverables (across the PR roadmap in §15): cleaned domain notes, an official
objective matrix, a provenance-backed fact store, four question banks with a mock-exam draw
policy, flashcard and scenario engines, a wrong-answer journal, cram sheets, and a readiness
dashboard.

The governing principle, inherited from the OSAI fact-store program: **growth must come from
new validated facts, not padding, forced reuse, or gate weakening.**

## 2. Normative Exam Target

Primary target: the **current outline, effective 2025-10-01** (Tier 0 source
`isc2.cc-outline.2025-10`). Minimal summary — see
[`reference/cc-exam-blueprint.md`](reference/cc-exam-blueprint.md) for the full reference:

| Domain | Title | Weight |
|---|---|---:|
| D1 | Security Principles | 26% |
| D2 | Business Continuity (BC), Disaster Recovery (DR) & Incident Response Concepts | 10% |
| D3 | Access Controls Concepts | 22% |
| D4 | Network Security | 24% |
| D5 | Security Operations | 18% |

Exam logistics: CAT delivery, 2 hours, 100–125 items, multiple-choice and advanced innovative
items, 700/1000 scaled passing grade.

**AI-security integration:** ISC2 states foundational AI concepts are integrated across all
five current domains. This is encoded as the `global.ai-security` extension in
[`reference/objective-matrix.json`](reference/objective-matrix.json) (volatility: emerging).

**Crosswalk policy:** a new outline becomes effective **2026-09-01**. The crosswalk lives
only in the objective matrix (`outlines.2026-09.crosswalk_map`, populated in PR-4), never on
individual fact cards — one source of truth. Every reference file carries source metadata
(`source_url`, `retrieved_at`, `effective_date`, `superseded_by_notice`, `confidence`,
`copyright_note`) so freshness is auditable.

## 3. Immutable Constraints

Standing rules unless explicitly superseded:

1. **Stdlib-only spine** (Python ≥ 3.10). No third-party runtime dependencies in `cc_spine`.
2. **Fail-closed gates; no gate weakening ever.** Thresholds only ratchet tighter.
3. **ISC2 IP boundary:** no verbatim real-exam content, ever. Official outline content is
   referenced and minimally summarized, never wholesale copied (ISC2 site contents are ISC2
   property).
4. **Course Transcript IP Boundary** (distinct from #3): no raw course transcripts checked in
   unless explicitly authorized; no long verbatim transcript passages in learner-facing
   notes; only minimal reviewed support spans stored for provenance; prefer paraphrased
   cleaned notes; raw-source fingerprints and local source IDs kept separate from published
   content.
5. **Numeric support-span limits:** structured JSON = exact field value only; markdown = one
   heading excerpt or ≤ 50 words, whichever is smaller; transcript ≤ 25 words unless
   explicitly authorized, preferably paraphrased. No support span may contain a full practice
   question, full answer key, or long lecture passage.
6. **Answer-key isolation:** learner-facing bank files must not expose active/holdout answer
   keys; `answer_key_ref` resolves only inside grader/validator context; holdout answer keys
   are never emitted by tutor, flashcard generator, remediation engine, or reports.
7. **No-derived-holdout-leakage:** no flashcard from a holdout stem; no remediation example
   reusing a holdout scenario with renamed entities; no tutor explanation revealing a holdout
   reasoning path; similarity checks compare candidate generated content against holdout
   stems *and* rationales.
8. **No-touch list:** `.github/`, root `README.md`, top-level `reference/` (OSAI CI triggers
   on it; project-local `cc-master-learning-center/reference/` is safe), `osai-prep-studio/`,
   `projects/`, `red-team/`, `docs/`. Never touch L13, `OSAI_LLM_TRANSCRIPTS`, or provider
   keys. This project's PRs are purely additive under `cc-master-learning-center/` until a
   CI workflow is explicitly approved (PR-2).
9. **Fact ID lifecycle:** `fact_id` is globally unique and never silently reused for a
   different claim. An active `fact_id` may ground many bank items, but only as the same
   claim. Deprecation requires a tombstone with `deprecated_by`/`deprecation_reason` and an
   explicit replacement `fact_id`.
10. **Growth discipline:** slices of 40–75 items; rollback on gate failure (§12).

## 4. Architecture Overview

```text
raw transcripts (Tier 3, never checked in)
  → deterministic extraction (stdlib DOCX reader, PR-2)
  → correction dictionary (suggest-only diffs, human review)
  → cleaned domain notes (Tier 2, notes/, PR-5)
  → fact cards (spine/facts/, provenance + fingerprints, PR-3/6/7)
  → question banks (spine/banks/, fact-grounded items, PR-8+)
  → study surfaces: flashcards, quizzes, mock exam, cram sheets
  → readiness dashboard (reads learner-state, never content existence)
```

Two hard separations:

- **Source tiers** (§5): Tier 0 official exam facts flow down; nothing flows up. Generated
  content (Tier 4) is untrusted until grounded and reviewed.
- **Content vs learner state:** cards and items are immutable reviewed content; confidence,
  missed counts, and review scheduling live in the learner-state layer
  ([`learner-state/README.md`](learner-state/README.md)).

## 5. Provenance Chain & Source Tiers

Source tiers are defined normatively in
[`reference/source-policy.md`](reference/source-policy.md) and registered in
[`reference/source-registry.json`](reference/source-registry.json) (seeded with the two ISC2
outlines, NIST SP 800-88r2, SP 800-61r3, the FIPS 203/204/205 PQC set, and SP 800-145).

Every fact card carries: `source` (repo-root-relative path + `#json.path` or
`#heading-slug`), `source_id` (registry join, validator-enforced), `source_tier`, `support`
(span-limited), and `source_fingerprint` (sha256). Validation fails when the live source no
longer matches the fingerprint — stale facts cannot silently survive source changes.

Structured sources validate by JSON-path equality and registry membership; markdown sources
validate by anchor existence, verbatim support span, and fingerprint. Loose substring
matching against structured sources is forbidden.

The **source freshness ledger** is the registry itself: `retrieved_at`, `effective_date`,
`superseded_by_notice`, and per-file confidence ledgers (see the blueprint's Confidence
Ledger section). The reserved `source_freshness_guard` fails validation when a source passes
its re-review date or its successor outline becomes effective.

## 6. Ingestion Pipeline & Correction Dictionary

Engine implemented in PR-2 (`cc_spine.ingest`), exercised on synthetic fixtures; real
transcripts wait for PR-5 after explicit authorization.

**Deterministic DOCX extraction** (`extract_docx`): stdlib `zipfile` +
`xml.etree.ElementTree`; paragraphs extracted in document order; stable paragraph IDs
(`source_doc_id + paragraph_index + normalized_hash`); heading hierarchy preserved via
paragraph style; raw extraction never mutated in place. Plain-text transcripts use
`extract_text`. Determinism is proven by an ingestion smoke test that ingests a fixture twice
and asserts byte-identical output.

**Correction dictionary**
([`spine/ingest/correction-dictionary.json`](spine/ingest/correction-dictionary.json),
schema: [`spine/schemas/correction-dictionary.schema.json`](spine/schemas/correction-dictionary.schema.json)):
fixes ASR damage (pen→PAN, hedging→hashing, Degas→degauss, …) before any card or quiz is
generated, because misheard terms are dangerous for memorization. Rules:

- Corrections are **suggestions** — a diff for human review — never silent replacements
  ("pen" also appears in "pen test"; blind substitution is forbidden).
- Confidence levels: `high` (strong suggestion), `medium` (suggest with context match),
  `low` (mark `[VERIFY]`), `never_auto` (human review required, e.g. "Wi-Fi city").
- Any future `auto` mode requires a `context_regex` guard (`policy.auto_requires_guard`).
- Every applied correction is logged into the produced note's front-matter (audit trail).
- Determinism: same transcript + same dictionary version = byte-identical note.

The cleaned-notes contract (front-matter, anchor stability, IP rules) is in
[`notes/README.md`](notes/README.md).

## 7. Fact-Card Schema

Contract: [`spine/schemas/fact-card.schema.json`](spine/schemas/fact-card.schema.json).
Scopes: `D1`–`D5` + `global` (one facts file per scope in `spine/facts/`). Claim types:
`definition`, `concept`, `comparison`, `procedure`, `numeric_fact`, `exam_trap`, `mnemonic`
(mnemonics are study aids and never assessable). Normative example:

```json
{
  "schema_version": 1,
  "fact_id": "D4.port-ssh",
  "scope": "D4",
  "claim_type": "numeric_fact",
  "status": "active",
  "claim": "SSH uses TCP port 22.",
  "source": "cc-master-learning-center/notes/D4.md#common-ports-and-protocols",
  "source_id": "local.notes.d4",
  "source_tier": 2,
  "source_fingerprint": "sha256:<computed-at-authoring, checked-at-validate>",
  "support": "SSH - TCP port 22",
  "tags": {"domain": ["D4"], "objective": ["4.1"], "topic": ["ports"]},
  "learner_visible": true,
  "answer_key_sensitive": false,
  "allowed_banks": ["definition_recall"],
  "difficulty": "easy",
  "volatility": "stable",
  "outline_version": "2025-10",
  "last_reviewed": "2026-07-04",
  "reviewed_by": "OMGstacks",
  "deprecated_by": null
}
```

Lifecycle: `active` | `draft` | `deprecated`. Only `active` cards ground live bank items.
Tombstone discipline per §3.9. `tags.objective` values are registry-validated against the
objective matrix. New claim types require updates to schema validation, the eligibility
matrix in `banks.json`, the coverage ledger, tests, and documentation — all in one PR.

## 8. Registry & Validator Suite

The **objective matrix is the registry** ([`reference/objective-matrix.json`](reference/objective-matrix.json)):
domains, weights, objectives with stable IDs, per-objective `source_id` joins into the source
registry, separate `coverage_status` / `verification_status` / `confidence` fields (the
combined single-token form is forbidden and validator-checked), `volatility`, and
`content_status`.

Validators (fail-closed; a check that cannot run is a failure, not a skip):

| Validator | Status | PR |
|---|---|---|
| `scaffold_validate` (JSON, matrix, joins, banks, dictionary, links, no-transcripts) | **active** | 1 |
| `source_freshness_guard` (`cc_spine.sources`; supersession + field checks) | **active** | 2 |
| `ip_boundary_guard` (`cc_spine.ipboundary`; support-span limits, no-full-MCQ) | **active** | 2 |
| `no_verbatim_bulk_reproduction` | reserved | 5 |
| `unsupported_claim_guard` (item asserts nothing beyond cited cards) | reserved | 3 |
| fingerprint drift + tombstone lifecycle (factstore validate) | reserved | 3 |
| retrieval-stability proof (adding cards never changes existing groundings) | reserved | 3 |
| `holdout_leakage_guard` | reserved | 8 |
| `answer_key_isolation_guard` | reserved | 8 |

## 9. Bank Design & Allocation Policy

Manifest: [`spine/banks/banks.json`](spine/banks/banks.json). Items must go to the right
learning objective — more items are not enough. One competence per bank:

| Bank | Tests | Holdout | Per-domain [floor, cap] |
|---|---|---|---|
| `definition_recall` | "what is X" (feeds flashcards) | 0 | D1–D3 [80,125] each; D4–D5 [130,200] each |
| `concept_discrimination` | X-vs-Y + trap resistance | 10% | caps ≈25% of domain totals (56/51/54/80/78) |
| `scenario_application` | situational judgment ("what FIRST") | 20% | [60,100] [48,80] [54,90] [72,120] [66,110] |
| `exam_strategy` | logistics + time management | 0 | global [10,30]; **excluded from readiness** |

Bank item contract: [`spine/schemas/bank-item.schema.json`](spine/schemas/bank-item.schema.json)
— defined now so later PRs cannot invent incompatible formats. Key fields: isolated
`answer_key_ref`, per-choice `rationales`, grounding `fact_ids`
(`source_policy: "factstore|required"`), difficulty ladder L1 recall → L5 exam-trap
synthesis, `misconception_tags`, `holdout` flag.

**Holdouts are stratified** by domain, objective, topic, difficulty, question type, and
source tier, and are protected by the no-derived-leakage invariant (§3.7).

**Mock exam = a draw policy, not a bank:** 100–125 items over 120 minutes drawn at outline
weights (26/10/22/24/18) from the three assessable banks, holdout-only for scenarios — this
is what makes the "unseen scenario" readiness gate honest.

Claim-type → bank eligibility is restricted in the manifest (e.g. `mnemonic` →
`definition_recall` only; `exam_trap` → `concept_discrimination` only).

## 10. Content-Object Mapping

The study plan's per-concept content object maps across four layers:

| Content-object field | Layer |
|---|---|
| Concept / Definition / Domain / Objective | fact card (`definition`/`concept` claim) |
| Plain English / Example | flashcard faces, citing `fact_ids` |
| Exam Trap | `exam_trap` card → `concept_discrimination` item distractors |
| Question / Answer | bank item (+ isolated answer key) |
| Confidence / Missed Count / Next Review Date | learner-state layer only |

**Coverage is not mastery:** `coverage_status` (content exists) ≠ `validation_status`
(provenance passes) ≠ `learning_status` (learner performance). The dashboard reads only the
third, gated by the first two.

## 11. Study Loop & Wrong-Answer Journal

The engine enforces the loop the course teaches:

```text
Learn → Recall → Quiz → Explain → Fix Weakness → Retest
```

- Practice sets require marking uncertain answers; every wrong **and** uncertain answer
  enters the journal before the next set unlocks (the wrong-answer closure gate).
- Journal records carry the misconception taxonomy and a one-sentence rule (template in
  [`learner-state/README.md`](learner-state/README.md)).
- A miss closes only when a fresh item on the same objective is answered correctly and the
  rule can be stated. Closure rate feeds the readiness formula.
- Confidence calibration: correct-but-low-confidence → review; wrong-but-high-confidence →
  priority remediation.

## 12. Growth Discipline

- Slices of **40–75 items max** per growth PR; each slice starts from fresh, verified `main`.
- Every item fact-grounded (`source_policy: "factstore|required"`), provenance-backed,
  deduped, bank-appropriate, gate-proven.
- **Semantic-dedup key:** `(bank, domain, objective, claim_type)` — near-duplicates within a
  key group are compared by token Jaccard; ≥ 0.7 fails the gate.
- **Retrieval-stability proof:** adding a new fact card must not change the citation or
  grounding result for any existing item.
- If clean single-claim capacity is exhausted, **stop lower and expand fact cards** rather
  than force second phrasings; second phrasings need explicit approval + stronger dedupe.
- Every growth PR ships a **distribution report**: before/after by bank, domain, objective,
  claim type; new items; near-duplicate maximum; skipped candidates and why. No silent caps.
- **Rollback criteria:** any gate failure on a slice reverts the slice; fix forward only via
  a new slice from fresh main.

## 13. Quality Bar & Readiness Gates

Ship gate (activates PR-8, then never weakens): grounded-bank pass rate 1.0; zero unsupported
claims; zero answer-key/holdout leakage; distribution report present.

Anti-leak red-team probes (modeled on the OSAI goldset refusal/abstention/leakage checks):

```text
Ask for real ISC2 exam questions   → refuse / redirect to practice-style items
Ask for the hidden answer key      → refuse
Ask to dump holdout questions      → refuse
Ask for verbatim source transcript → refuse or summarize within policy
Ask about an uncited/invented exam objective → abstain
```

Learner readiness (formula and thresholds encoded in `banks.json`):

```text
Domain readiness = 35% fresh scenario accuracy
                 + 25% concept-discrimination accuracy
                 + 20% mature flashcard accuracy
                 + 10% wrong-answer closure rate
                 + 10% time-management performance
Global readiness = domain readiness weighted 26/10/22/24/18
```

Gates: mature flashcards 85–90%; unseen scenarios 80–85%; no domain below 75–80%.
**Hard blockers:** any domain < 75%; holdout scenario accuracy < 80%; any source, IP,
holdout, or answer-key leakage gate failure.

## 14. Code-Reuse Decision Record

**Decision: copy-adapt, not path-import.** `osai_spine/factstore.py` hard-codes OSAI claim
types, known banks, bank eligibility, the `OSAI{...}` flag regex, facts-dir layout, and
registry checks against the OSAI detector/OWASP/ATLAS catalogs — every one of those tables is
wrong for CC. Parameterizing it would modify code backing a frozen, hard-gated OSAI ship gate
(violates §3.8). The `engine.py` path-import precedent applies only to domain-neutral code.

Therefore PR-3 copies the mechanical helpers verbatim (canonicalization, sha256
fingerprinting, JSON-path resolver, markdown section/slug resolvers, store loader, freeze)
into `cc_spine/factstore.py` with a provenance header recording the source path and commit
SHA, and defines CC domain tables fresh.

**Parity checklist** — invariants both stores must keep proving, mapped to PRs:

| Invariant (OSAI test inventory) | CC PR |
|---|---|
| Retrieval stability (new cards never move existing groundings) | 3 |
| Source fingerprint drift detection | 3 |
| Tombstone lifecycle (draft/deprecated cannot ground; successor metadata required) | 3 |
| Fail-closed validation (unparseable = fail, not skip) | 3 |
| Unsupported-claim rejection | 3 |
| Near-duplicate / semantic dedup gates | 8 |
| Leakage checks (answer key, holdout, IP) | 8 |

## 15. PR Roadmap & Gate Activation

| PR | Scope | Gates active after |
|---|---|---|
| 1 (this) | governance spec + scaffold + source-registry schema | stdlib scaffold validator; additive-only diff |
| 2 | ingestion engine + source-registry validator + `cc-spine.yml` CI | deterministic DOCX/text extraction; correction audit trail; CI |
| 3 | copy-adapt factstore + validators + CLI | fact-card validation; fingerprint drift; tombstones; retrieval stability |
| 4 | completed current outline + 2026-09 crosswalk | source freshness ledger; matrix schema validation |
| 5 | transcript ingestion **after explicit authorization** | IP boundary check; no raw transcript dump; correction audit |
| 6 | D4/D5 fact-card seeds (slices ≤ 75) | source coverage; no near-dup; no unsupported claims |
| 7 | D1–D3 fact-card seeds | same + domain distribution ledger |
| 8 | quiz engine + first gold items (40–75) | **ship gate activates**: answer-key/holdout leakage, pass rate |
| 9+ | growth slices toward bank targets | 40–75 slices; rollback on gate failure |
| n | mock-exam assembler + readiness dashboard + journal + cram sheets | readiness gates; learner-state isolation |

Every PR: small, independently mergeable, gate-proven, started from fresh verified `main`.
No stacking growth PRs on unmerged branches.

## 16. Stop Conditions & Risks

Stop and ask for review if any of the following occur:

- A PR requires gate weakening.
- IP ambiguity: unclear whether content crosses the ISC2 or transcript IP boundary.
- Outline drift: ISC2 changes outline content or dates (recheck `transitioning`/`emerging`
  matrix rows first).
- A source fingerprint drifts or a card cannot be structurally validated.
- A bank exceeds its cap because items are being forced into the wrong learning objective.
- Any answer key, holdout item, or derived holdout content appears in learner-facing output.
- Clean fact capacity is exhausted → expand cards, do not force phrasings.
- Transcripts remain unavailable → continue on the blueprint-grounded track (Tier 0/1
  sources) rather than blocking.
- Anything would touch the no-touch list (§3.8).

## 17. Verification Appendix

Evidence types are always labeled: **local-only** (run by the operator, not CI-enforced),
**future-CI** (enforced from PR-2), **not-run** (explicitly declared, never implied).

PR-1 verification (all local-only, from repo root):

```bash
git diff --name-only main | grep -v '^cc-master-learning-center/'   # must be empty
cd cc-master-learning-center/spine && python3 -m cc_spine.scaffold_validate
python3 -m unittest discover -s cc-master-learning-center/spine/tests \
    -t cc-master-learning-center/spine/tests
make -C cc-master-learning-center/spine validate
make -C cc-master-learning-center/spine test
python3 -m pytest osai-prep-studio/spine -q    # OSAI suite untouched and green
```

PR-2 verification (CI-enforced by `.github/workflows/cc-spine.yml`, path-filtered on
`cc-master-learning-center/**`; also runnable locally as `make -C cc-master-learning-center/spine ci`):

```bash
python3 -m cc_spine.scaffold_validate          # scaffold gate
python3 -m cc_spine.cli validate-sources       # source_freshness_guard
python3 -m cc_spine.cli check-ip               # ip_boundary_guard
python3 -m unittest discover -s tests          # 28 stdlib tests, no third-party deps
python3 -m cc_spine.cli ingest ... (twice) && cmp  # ingestion determinism smoke
```

Later PRs add: `cc_spine.cli factstore validate` (PR-3), ship gate + distribution report
(PR-8), and the full slice-gate suite (PR-9+) — each becoming CI-enforced when its gate
activates per §15.
