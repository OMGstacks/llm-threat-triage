"""CC Master Learning Center spine.

Standard-library-only package (Python >= 3.10) for the governed CC exam-prep
content system. The fact-store machinery is copy-adapted from
``osai-prep-studio/spine/osai_spine`` rather than path-imported: the OSAI
factstore hard-codes OSAI claim types, banks, eligibility, flag regexes, and
registry checks that back a frozen ship gate, so this package defines its own
domain tables while keeping the mechanical helpers (fingerprinting, JSON-path
and markdown-anchor resolvers, loader, freeze) verbatim. See
``00-governance-spec.md`` section 14 for the decision record and parity
checklist.

PR-1 ships only the scaffold validator. PR-2 adds the deterministic ingestion
engine (``ingest``), the source-registry freshness guard (``sources``), the
IP-boundary support-span guard (``ipboundary``), and the CLI (``cli``). PR-3
adds the copy-adapted fact store (``factstore``), the CC registry over the
objective matrix and source registry (``registry``), and the note review-state
lifecycle (``notes_lifecycle``). PR-4 completes the 2026-09 outline + crosswalk
in the objective matrix and adds the source-freshness ledger (``next_review``).
PR-4.1 adds the two-lane verification evidence ledger, the official 19-objective
2026 set, and the attestation guard (``sources`` + scaffold evidence check).
PR-5 ingests the transcripts by semantic distillation: a source manifest
(raw_committed:false), an IP-safe correction audit, objective coverage/gap maps,
compact original concept inventories, and the no_verbatim_bulk_reproduction
guard (``ipboundary.scan_verbatim``).
PR-5.1 hardens the no-verbatim guard against table-cell bypass (per-cell/row word
caps), expands the raw-file scan to repo root, anonymises the manifest's
``authorized_by`` field, adds ``grading_policy`` to the coverage map, documents
concept inventories as authoring aids, and tracks flagged-but-unresolved
corrections.
PR-6 seeds the first real fact cards: 59 cards across D4 objectives 4.1/4.3 and D5
objective 5.1, grounded on tier-0 blueprint anchors (isc2.cc-outline.2025-10) and
tier-1 NIST anchors (nist.sp800-145, nist.sp800-88r2, nist.pqc.fips-203-204-205).
No bank items, no holdout, no mnemonic cards. Scaffold validator updated to allow
non-empty fact arrays.
PR-7 completes fact-card seeding across the remaining domains: 90 cards over D1
(1.1-1.4), D2 (2.1-2.3), and D3 (3.1-3.2), grounded on new tier-0 blueprint anchors
(the incident-response lifecycle is taught as the ISC2 CC four-phase model, with
NIST SP 800-61r3's CSF-2.0 reframing kept as a tier-1 note). An adversarial content
review flagged a six-vs-four phase error and two near-duplicate cards, both fixed.
Fact store now holds 149 validated cards; all five domains have seed coverage.
PR-7.1 persists the slice acceptance evidence under ``reports/`` (a data-derived
distribution report + the adversarial-review record) and records two content-slice
rules in the governance spec: 40-75 items per growth slice, and no content commit
until its adversarial review completes. No cards changed.
PR-8a lands the quiz engine (``quiz``) and activates the ``answer_key_isolation_guard``:
learner-facing gold items live in ``spine/gold/goldset.json`` with NO correct answer,
while the grader answer keys live in a separate ``spine/gold/answer-keys.json`` store
(new ``answer-key.schema.json``). The engine's learner view is an allowlist projection;
``validate_gold`` enforces grounding + key resolution + hash-drift + near-duplicate stem
gates; a red-team test suite proves no answer leaks into the learner lane. Ships 6 first
gold items across the three core banks and a misconception registry seeded from the PR-7
review. No holdout items yet (that guard stays reserved).
PR-8a.1 hardens the quiz isolation before scale-up: distractors now name a specific
misconception-registry id (validated for existence, category, and objective match), not
just a taxonomy category; answer keys gain a full-item ``item_hash`` that catches semantic
drift the correct-choice hash misses; correct-answer positions are varied and gated against
overfit; ``cc_spine.cli quiz export-learner`` emits the sole learner projection and CI
scans it for any answer-bearing field; and goldset.json is documented as the authoring
source, not the learner export.
PR-8b scales the gold set to 40 non-holdout items (three core banks 18/14/8, 8 per
domain) grounded on the fact store, each distractor naming a specific registry
misconception. Items were authored by per-domain agents, mechanically grounding-checked,
then run through a five-reviewer adversarial pass BEFORE commit (governance spec §16.0):
0 factual errors, 3 minor stem-quality fixes plus an answer-length-bias trim. The
misconception registry grew 8 -> 37 entries. Evidence in reports/pr8b-*. Still no
exam_strategy items (PR-8d) and no holdout lane (PR-8c).
PR-8b.1 hardens item quality before the holdout lane: ``quiz validate`` now fails on a
conspicuous length tell (correct > 1.5x every distractor), a causal-tail-only correct
answer, or mixed choice structure (short labels beside long sentences); it also reports an
advisory answer-length-bias metric (40% warn). Eight near-tie items had a weak distractor
strengthened to parallel length, bringing longest-correct 52% -> 32% without changing any
keyed answer. Adds an all-choices grading smoke test over all 40 items and a machine-readable
review artifact (reports/pr8b-adversarial-item-review.json).
PR-8c adds the holdout lane in a PHYSICALLY separate store (spine/gold/holdout.json +
holdout-keys.json) that the learner practice path never opens; only the explicit
``quiz validate-holdout`` evaluator command reads it. It flips the ``holdout_leakage_guard``
active: the scaffold enforces holdout:true + answer isolation structurally, and the CLI
enforces the same item gates plus lane partition and a no-leak-into-practice check (no
holdout stem, verbatim or near-duplicate, reaches the learner export). Ships 8 unseen
holdout items on concepts distinct from the 40 practice items; all tracked guards are now
active. Evidence in reports/pr8c-*.
PR-8d fills the last empty learner-facing bank (exam_strategy): 7 global exam-logistics
fact cards in _global.json (scope global, grounded on the blueprint #exam-facts anchor via
a new global.exam-strategy matrix extension) and 5 exam_strategy practice items. The gold
set is now 45 items across all four banks; the fact store holds 156 cards. Independent
review before commit: 0 findings. Evidence in reports/pr8d-*.
PR-9 adds the learner-state layer (``learner_state``): a Leitner spaced-repetition engine
and a misconception-tagged wrong-answer journal that replays an attempt stream into a study
state. It fulfils the PR-1 reserved contract in learner-state/README.md. The engine ships;
learner data never does — the new ``learner_state_isolation_guard`` (7th and final guard)
fails the build on any committed state file and rejects PII field names in the two new
schemas (learner-attempt, learner-state), and the engine rejects holdout attempts fail-closed.
Deterministic (injected time, no wall clock). CLI ``learner replay`` demos it. Evidence in
reports/pr9-*.
PR-9.1 applies the independent engine review's four minor fixes: a total attempt sort key
(determinism for same-item/same-time attempts), fail-closed on an ungradable attempt, the
journal records the SELECTED distractor's misconception (not the first), and holdout rejection
also checks the resolved item's holdout flag. Four regression tests added. The review had
completed after the initial commit — the PR-7 commit-before-review lesson reinforced.
PR-10.1 grows the holdout scenario supply from 1 to 5 items (one per domain) so PR-10 mock
exams can draw a scenario per domain (mock_exam.scenario_draw is holdout_only). Same holdout
gates; independent review awaited before commit — 0 findings. Holdout lane now 12 items.
PR-10 adds the mock-exam assembler (``mock_exam``) and completes the readiness formula.
``assemble`` draws a deterministic mock per the banks.json policy (domain-weighted,
non-scenario from practice, scenario from the holdout lane only), excluding burned holdout
ids; ``grade_mock`` yields fresh-scenario accuracy without leaking holdout content; and
``learner_state.readiness_report`` computes the full weighted formula plus the hard blockers
(domain < 75%, holdout-scenario < 80%, leakage gate). Engine proof at ~15-item scale (real
exam length is content-blocked). CLI ``mock assemble|validate``. Evidence reports/pr10-*.
"""

__version__ = "0.8.0"
