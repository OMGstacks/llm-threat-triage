# PR-10.4b Locked API-Prompt Scaffold + Local Draft-Runtime Intake

**Slice:** PR-10.4b — the deterministic pipeline around the PR-10.4a validator: build the **locked
generation prompt** for a missed practice item, and validate **untrusted candidate JSON** into a
local, gitignored draft. **No live API provider** (that is PR-12) — pure stdlib, no network, no wall
clock, no randomness, so the pipeline proves it rejects bad candidates before any provider exists.

---

## 1. Trust model

| Artifact | Trust | Handling |
|---|---|---|
| **Prompt** | evaluator/generator context | Derived entirely from GOVERNED stores; contains NO source stem/choices (nothing quoted outward, nothing to near-duplicate); never shown to a learner (CLI prints the caveat to stderr) |
| **Candidate** | untrusted | Closed 5-key contract, fail-closed parse; strict `self_check` verified but **never trusted alone** (reviewer rule); full 13-gate PR-10.4a validation + intake gates I1–I10 |
| **Draft** | local runtime | `status=draft`, `source=api_generated_local`, `readiness_weight=0`; written only to gitignored/.local or outside-repo dirs; answer-bearing key **physically separate**; never practice-eligible; cannot touch readiness |

## 2. The locked prompt (`build_variant_request` + `build_variant_prompt`)

Everything the generator must preserve is derived from governed stores — never from the candidate:
`must_test` = the cited fact card's claim; **`correct_concept` = the misconception registry's
`correct` field** (concept-level, already learner-visible as journal corrections — never the keyed
choice text, which the API would echo verbatim into a recognizable answer); misconception targets =
the source key's distractor map; `must_include_keywords` = the source's grounded `expected_keywords`.
Holdout sources are refused fail-closed (flag + holdout-store cross-check).

> **Flagged deviation from the reviewer's template** (deliberate, called out here): the
> `{correct_concept}` slot **value** is enriched with
> `(the correct choice must contain the exact phrase(s): "…")`. Gate 7 requires the keyed choice to
> carry the exact `must_include_keywords`; a generator that is never told the phrases could only pass
> by luck. The template *text* is unchanged — only the slot value carries the extra clause.

The prompt is a pure function of the request — byte-identical across runs (CI `cmp`-gated).

## 3. Candidate intake — the gate stack

Parse (I1–I3): closed 5-key object; choices 2–6, non-empty, pairwise-distinct; `self_check` exactly
three keys, each strictly `is True`; `factstore.residual_secrets` clean.
Derive (I4): the correct index = the SINGLE in-range choice index absent from the candidate's
distractor map (canonical decimal keys, unique) — anything else fails closed. The intake **forces**
`status/source/readiness_weight`; the candidate cannot assert governance fields.
Then the **full PR-10.4a 13-gate validator**, then I5–I10: misconception ids ⊆ request targets
(categories from the registry, never candidate-asserted); `correct_choice_concept` must **echo** the
request's concept (a divergence signals a mislabeled correct choice); choice count == source count
(difficulty drift); **holdout contamination** (no holdout stem verbatim in the candidate blob; stem
near-dup ≥ 0.75 rejected); the PR-8b.1 length/parallelism tells; draft invariants re-asserted.

**Attack matrix outcome** (plan-time stress test, all test-proven):
map-the-right-choice-as-distractor → gate 7; right-choice-still-carries-keywords → gate 7
(second-match); index games (`"01"`, `"-1"`, out-of-range, all-mapped, two-unmapped) → I4;
2-choices-for-a-4-choice-source → I7; duplicate/empty choices → I1; concept mismatch → I6.

## 4. Known residual (N3 class — documented, not hidden)

A deliberate adversary that **echoes the correct concept AND plants the lock keywords on a
semantically wrong choice** defeats every text gate — automated gates cannot verify semantic
correctness (the PR-10.4a N3 finding, unchanged). Containment, test-proven: such a candidate lands
only in a **draft** that no learner-facing path consumes — `is_practice_eligible` is False (even for
a forged `status:"validated"`), `learner_state.replay` raises on a variant id, mock/holdout never
read drafts, `readiness_weight` is 0. **Human adversarial review is the promotion backstop.**

## 5. Draft storage

`.local/variant-drafts/<vid>.draft.json` = `{draw_key, variant}` and `<vid>.draft.key.json` =
`{variant_id, correct_index, rationale_refs, distractor_misconceptions}` — the explicit answer
**fields** live in the separate key file, keeping the "no single file holds question + answer"
invariant at the field level. The candidate's distractor map is answer-bearing (its absent index IS
the answer), so it lives in the **key** file. **Honest scoping (review F2):** the separation is
field-level, not information-level — the draft body remains answer-*deducible* via its semantic_lock
(gate 7 guarantees exactly one choice carries the keywords), which is inherent to the
lock-corroboration design and acceptable for an evaluator-context local file never rendered to a
learner.
`write_draft` refuses committable out-dirs and same-id drafts recorded under a different draw_key
(deterministic `variant_id = sha256(source_id, draw_key) % 1000` → `.vNNN`).

The **8th guard** — `api_draft_isolation_guard` (superseding PR-9's "7th and final" wording) — fails
the build on any committed json carrying `source=api_generated_local`, an unreviewed variant body, or
a `variant-drafts` path outside `.local/`. The learner-state working-tree scan now exempts the
sanctioned `.local/variant-drafts/` dir (a plan-time bug fix: a legitimate local draft must not turn
local `make ci` red).

## 6. Demonstration

```
python3 -m cc_spine.cli variant prompt   --item-id D1.1.4.scenario.0001 --draw-key demo
python3 -m cc_spine.cli variant ingest   --item-id D1.1.4.scenario.0001 --draw-key demo \
        --candidate tests/fixtures/variant_candidate_good.json          # → 2 files, DRAFT notice
python3 -m cc_spine.cli variant requests --attempts tests/fixtures/synthetic_attempt_stream.json --now 5
make variant-check                                                       # the CI gate
```

## 7. Review before commit (§16.0)

Independent adversarial review — **completed before commit** (PR-9 lesson). Verdict
**accept-with-fixes** (4 minor + 4 nit, no majors); the reviewer confirmed determinism/purity, the
leak-free prompt, sound correct-index derivation, symlink-safe draft-dir guarding, and a clean
real-tree scaffold scan. All eight findings applied before this commit:

| # | Sev | Finding | Fix |
|---|---|---|---|
| F1 | minor | distractor-map VALUES weren't type-checked — arbitrary nested JSON rode through into the key file | values must be non-empty strings (matches the schema); dict branch in I5 removed; regression test |
| F2 | minor | "physically separate key" overstated — the draft body is answer-*deducible* via its lock | wording scoped to field-level separation everywhere; deducibility documented as inherent to gate-7 design |
| F3 | minor | missing per-action CLI args crashed with a raw traceback | fail-closed usage errors (rc 2) for all four actions; test |
| F4 | minor | the scaffold body-check missed the nested `{draw_key, variant:{…}}` wrapper and skipped unparseable JSON | recurses one level into dict values; unparseable JSON mentioning `stem_variant` now flagged; tests |
| F5 | nit | I6's one-directional containment reads stronger than it is | documented as ADVISORY against accidental mislabeling; correctness rests on gate 7 + the derived index |
| F6 | nit | unreachable duplicate-index branch | removed, with the why-it-can't-fire comment |
| F7 | nit | a corrupted existing draft crashed the collision check | fail-closed refuse-to-overwrite with a clean error |
| F8 | nit | holdout store loaded up to 3× per candidate | loaded once; one consistent snapshot feeds all gates |

Full record in `pr10-4b-variant-intake-review.json`.

## 8. Next

**PR-11a** — the data-first readiness dashboard (per the accepted roadmap). PR-12 later connects a
live provider to this scaffold: the provider becomes a `prompt → candidate JSON` adapter; everything
it returns already has to survive this intake.
