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
PR-10 follow-up applies the independent review's F2 (major): the holdout "burn" now tracks
EXPOSURE, not submission. A holdout scenario assembled into a mock is revealed by the learner
view whether or not it is answered, so a new ``mock_exam.exposed_holdout_ids`` returns every
assembled holdout id and is the single source of truth for ``grade_mock``'s burned set — an
exposed-but-unsubmitted scenario can no longer be re-drawn and re-counted as "fresh". Fresh-
scenario accuracy still counts only submitted scenarios. F1 (minor) was confirmed already fixed.
PR-10.2 surfaces burn-on-exposure before any dashboard renders a mock: a new
``mock_exam.mock_exposure_receipt`` returns a content-free record (draw_key, item_count,
``exposed_holdout_ids``, ``burn_required``), and ``mock_exam.render_mock`` — the SOLE public render
path — bundles the learner items WITH that receipt. The raw receipt-less projection is made private
(``_mock_learner_view``), so the default public path a UI/dashboard reaches for carries the burn
obligation (Python can't hard-enforce it — a caller can still reach the private helper — so the
guarantee is "the sanctioned public render surface always carries the receipt," not absolute). The
receipt carries no stems/choices/answers. CLI ``mock render`` prints the receipt and warns on stderr
when burn is required; a ``mock-render`` CI gate scans its output for content and answer-bearing
fields. Independent review (accept-with-fixes) drove this scoping down from an overstated
"enforced/no code path" claim (review F1) plus test/gate strengthening (F2-F5).
PR-10.3 adds render-time answer-choice shuffling (``presentation``) so a repeated item isn't
memorisable by letter — provided the caller supplies a fresh per-attempt seed (the contract is
load-bearing; ``quiz render`` requires ``--attempt-seed``, no default). The canonical goldset/holdout
never change; presentation order is a pure function of ``(attempt_seed, item_id)`` via SHA-256 rank
(no random, no clock), so the grader RECOMPUTES the order to map a displayed choice back to its
canonical index — no choice-order secret is stored or shown. ``render_item``/``render_quiz`` reuse the
learner-view allowlist (choices only reordered, ``presentation_id`` + ``choice_count`` added, no
answer field); ``grade_presented`` maps displayed→canonical, rejects a non-int/bool/out-of-range
index, and fails closed on an ``expected_presentation_id`` mismatch (a render/grade seed mix-up);
``item_hash``/``answer_key_hash`` still pin the canonical item. A ``quiz-render-scan`` CI gate scans
the shuffled render for answer/order fields; holdout items use the same machinery. Independent review
(accept-with-fixes) hardened the bool guard, the required seed, the anti-memorization gate, and the
presentation_id integrity check before commit (F1-F5).
PR-10.4a adds the semantic variant model + validators (``variants`` + ``item-variant.schema.json``)
so a MISSED item can later be re-tested with reworded-but-equivalent variants. Synthetic variants
only; NO live API (that is PR-10.4b). Correctness lives in a SEPARATE evaluator-context variant key
(answer-key isolation, carried from the quiz engine); the variant OBJECT stores no correct index /
display letter / choice order and is a CLOSED object (allowlist, so no field of any name smuggles an
answer — gate 11). The ``semantic_lock`` CORROBORATES the key rather than defining correctness: the
keyed-correct choice must carry every ``must_include_keyword`` and no other choice may (gate 7).
``validate_variant`` enforces the gate set: source resolves and is NOT holdout (cross-checked against
the holdout store, not just a caller flag); objective/bank/fact_ids/misconception target (derived
from the SOURCE key — never a silent skip) may not drift (``semantic_lock_guard``); expected_keywords
stay grounded (reuses ``factstore.validate_item``); misconception_ids resolve; the stem is reworded
but not a synonym swap (Jaccard ≤ the goldset near-dup bound). Only ADVERSARIALLY-REVIEWED variants
(reviewed + metadata) are practice-eligible; ``readiness_weight`` is pinned to 0. Variants render +
grade through the PR-10.3 presentation layer, using the SOURCE's neutral topic so no answer-adjacent
authoring text leaks. Independent review (needs-work → fixed) drove the isolated-key model, the render
leak fix, the fail-closed drift check, and the closed-object allowlist before commit (F1-F9). 8th
schema; scaffold count gate updated.
PR-10.4b adds the locked API-prompt scaffold + local draft-runtime intake (``variant_intake``) —
still with NO live API provider (that is PR-12); the pipeline is pure, deterministic stdlib. The
prompt builder derives everything the generator must preserve from GOVERNED stores (must_test from
the cited fact card; the correct-answer CONCEPT from the misconception registry's ``correct`` field —
never the keyed choice text) and contains no source stem/choices; one flagged deviation enriches the
correct-concept slot VALUE with the exact must_include phrase(s) so gate 7 is satisfiable. Untrusted
candidate JSON passes a closed 5-key parse (strict self_check, never trusted alone), the correct
index is DERIVED as the single choice absent from the candidate's distractor map, and the result
runs the full PR-10.4a 13-gate validator plus intake gates I1-I10 (target-subset, concept echo,
choice-count parity, holdout contamination, length/parallelism tells). Accepted drafts are
``status=draft``/``source=api_generated_local``/``readiness_weight=0``, written only to gitignored
locations with the explicit answer FIELDS (incl. the distractor map — its absent index IS the
answer) in a separate ``*.draft.key.json`` (field-level separation; the draft body stays
answer-deducible via its lock, inherent to the gate-7 design — review F2). Drafts are never
practice-eligible and cannot touch readiness (``replay`` raises on variant ids). The 8th guard (``api_draft_isolation_guard``,
superseding PR-9's "7th and final" wording) fails the build on any committed variant data. Known
residual (N3 class, documented): text gates cannot verify SEMANTIC correctness of the keyed choice;
human adversarial review is the promotion backstop. CLI ``variant prompt|ingest|requests|validate``;
a ``variant-check`` CI gate proves determinism + attack rejection. 9th schema (variant-candidate).
"""

__version__ = "0.8.5"
