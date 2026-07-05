# PR-9 Learner State + Wrong-Answer Journal

**Slice:** PR-9 — the personalization layer: a wrong-answer journal + spaced-repetition engine.
**Engine:** `spine/cc_spine/learner_state.py` · **schemas:** `learner-attempt`, `learner-state`.

Fulfils the reserved contract in `learner-state/README.md` (written at PR-1): confidence
calibration, the misconception-tagged journal, and the closure→readiness loop. This slice ships
the **engine and schemas only** — never a person's study history.

---

## 1. The isolation story (why this is safe)

| Concern | How PR-9 handles it |
|---|---|
| Personal data in the repo | **Never committed.** `.gitignore` + `learner_state_isolation_guard` scaffold scan fail the build on any committed state `.json`. Only synthetic fixtures under `tests/fixtures/` may hold attempt-shaped data. |
| PII | Schemas are `additionalProperties:false` at every fixed object; a scaffold scan rejects any PII-like field name (name/email/ip/user/token/…). Anonymous by construction. |
| Holdout leakage | The engine **rejects (fail closed)** any attempt whose item_id is a holdout or unknown item — it can never enter the journal, schedule, or readiness. |
| Content leak | State stores `selected_index` + `misconception_id`; the teaching text comes from the committed misconception registry. No stem, full choice text, or answer key is stored. |
| Determinism | `now` and every `submitted_at` are injected integer time units; the engine reads no wall clock and no random source. Same attempts → byte-identical state. |

## 2. What the engine computes

- **Leitner mastery** (5 boxes): a confident-correct answer promotes; a miss demotes to box 1;
  a correct-but-*unsure* answer is **not** promoted (stays due sooner). Due date =
  `submitted_at + interval[box]`.
- **Wrong-answer journal**: every miss records `{item_id, objective, bank, selected_index,
  misconception_id, trap, correction, one_sentence_rule, recorded_at, closed}` — the trap and
  correction resolved from the registry (42 entries).
- **Misconception closure**: a misconception is *closed* after **2** correct answers following a
  miss (`closed_after_correct_streak: 2`); the journal reconciles to final closure status.
- **Confidence signals**: correct + low confidence (≤2 or `marked_uncertain`) → not promoted;
  wrong + high confidence (≥4) → `priority`, floated to the top of the review queue.
- **Partial readiness**: per-domain practice accuracy + wrong-answer-closure rate, **excluding**
  the `exam_strategy` bank (`excluded_from_readiness`) and holdout. Flagged `partial: true` — the
  fresh-scenario and mock components arrive with the mock assembler (PR-10).

## 3. Review-queue ordering (gate 10)

`review_queue(state, now)` returns items due at `now`, ordered: priority first, then lower
Leitner box, then older `last_seen`, then `item_id` (deterministic tie-break).

## 4. Demonstration

```
python3 -m cc_spine.cli learner replay --attempts tests/fixtures/synthetic_attempt_stream.json --now 5
```

The committed synthetic stream misses the *hashing-is-encryption* trap once (high confidence),
recovers it with two correct answers (→ closed), logs an open *udp-reliable* miss, tracks a
correct-but-unsure item without promoting it, and excludes an exam-strategy attempt from readiness.

## 5. Adversarial review

An independent agent reviewer (author ≠ reviewer) audited the engine end-to-end. **Process note:**
that review completed *after* the initial PR-9 commit — a repeat of the PR-7 commit-before-review
gap. It found **4 minor defects** (no blockers): a non-total sort key (determinism), an unchecked
`graded` flag (should fail closed), first-vs-selected misconception attribution, and holdout
rejection that relied only on `holdout.json` membership. **All four were fixed in PR-9.1** with
regression tests. Full record in `pr9-learner-state-review.json`. The lesson from PR-7 stands
reinforced: wait for the independent review before committing.

## 6. Deferred (keeps PR-9 small)

- Mock-exam assembler + fresh-scenario/holdout readiness components → **PR-10**.
- Visual readiness dashboard / cram sheets → **PR-11** (an Artifact, like the practice quiz).

## 7. Guard status

`learner_state_isolation_guard` is now active — the **7th and final** guard. All are active.
