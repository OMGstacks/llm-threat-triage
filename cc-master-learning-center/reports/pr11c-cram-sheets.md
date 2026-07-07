# PR-11c Cram Sheets — Weak-Area Review Packets

**Slice:** PR-11c — the second half of the deferred "dashboard + cram sheets" slice (first named in
`pr10-mock-assembler.md`'s §7). Completes PR-11 with `cram_sheet.py` (data model) +
`cram_sheet_view.py` (visual layer), following the same data-first-then-visual split as PR-11a/11b.

---

## 1. The inversion: content-bearing by design

The readiness dashboard (PR-11a/11b) is deliberately **content-free** — a live status panel of ids,
counts, accuracies. A cram sheet inverts that on purpose: its entire job is to surface the **teaching
content** behind the learner's own past misses, so they can actually study the weak spot. This is not
a leak — every fact shown came from an item the learner already attempted and got wrong; the
trap/correction/one_sentence_rule text is the misconception registry's committed, vetted explanation,
exactly what `learner_state.replay` already writes into the open journal for this purpose.

**What is still withheld, even here:** the item's `choices` (a conceptual review, not an answer-key
list), the isolated-key fields (`correct_index` / `answer_key_ref` / `rationale_refs` /
`distractor_misconceptions` / hashes — never belong in a learner-facing surface, full stop), the
learner's own `selected_index` (not useful for review), and `fact_ids`/`expected_keywords` (grounding
metadata, not teaching content). **Holdout content cannot reach it structurally**: `learner_state.replay`
rejects holdout attempts fail-closed, so no holdout item id ever enters the journal this module reads —
inherited, not re-implemented.

## 2. The data model (`cram_sheet.build_cram_sheet(state, now)`)

Pure, deterministic (no clock/random — only the injected `now` and the already-replayed state).

| Ordering | Rule |
|---|---|
| Domains | weakest-**scored**-accuracy-first. Domains with NO accuracy signal (`exam_strategy` items all carry domain `"global"`, which `learner_state.readiness_report` deliberately excludes from `per_domain`; also the `"unknown"` fallback below) sort **last** — an unscored domain is not the same as a failing one, and must never permanently outrank a domain the learner is actually weak in (review F1, a real bug caught pre-commit: the original code defaulted missing-domain accuracy to 0.0, pinning `global` above every genuinely weak domain). |
| Entries within a domain | priority-miss-first (an overconfident wrong answer — the most dangerous kind), then most-recent-first, then item_id as a stable tie-breaker |
| Closed recap | deduplicated to the latest occurrence per misconception_id, capped at 5, positive reinforcement for what's already been fixed |

An `item_id` absent from the goldset (e.g. a persisted attempt stream replayed against an updated
store) falls back to an explicit `"unknown"` domain — never a Python `None`, which would emit
schema-invalid JSON and crash `html.escape` in the render (review F2).

**Documented limitation (review F3):** `priority` reflects the *item's* current aggregate
confidence flag from `learner_state` (its most recent overconfident miss), not a per-misconception
attribution. Today's goldset never maps two distinct misconceptions to one item's distractors, so
this isn't yet observable — a future item authored that way would share one `priority` value across
its open entries. Documented rather than re-plumbed through the journal schema (a change to an
already-shipped, independently-reviewed module, out of scope for this slice).

## 3. The visual layer (`cram_sheet_view.render_html`)

A study-document treatment, not an instrument panel — read top to bottom, not scanned. Shares the
dashboard's color/type tokens (same product, same visual language: serif headings, mono for
ids/labels, sans for body) but is a self-contained template with no import from `dashboard_view`, so
this module carries zero regression risk to the already-shipped dashboard render. One "trap card" per
open misconception: a quoted stem for context, then three labeled rows — **The trap** (what you
believed) / **The fix** (what's actually true) / **One-line rule** (the distilled takeaway) — plus a
"confidently wrong" chip on priority misses.

## 4. Content-freedom of the answer-key surface (re-verified at this layer)

No forbidden field (choices, correct_index, answer_key_ref, rationale_refs,
distractor_misconceptions, hashes, selected_index, fact_ids, expected_keywords) appears in the data
model or the render; no holdout item id or stem appears. HTML-special characters are escaped.

## 5. Demonstration

```
python3 -m cc_spine.cli cram-sheet --attempts tests/fixtures/synthetic_attempt_stream.json --now 5
python3 -m cc_spine.cli cram-sheet --attempts stream.json --now 5 --html --out sheet.html
make cram-sheet-check cram-sheet-html-check
```

## 6. Review before commit (§16.0)

Independent review — **completed before commit** (PR-9 lesson). Verdict **accept-with-fixes**: 1
major + 3 minor, all fixed before this commit.

| # | Sev | Finding | Fix |
|---|---|---|---|
| F1 | **major** | domain sort defaulted an unscored domain's accuracy to 0.0, so a missed `exam_strategy`/`global` item (excluded from `per_domain` by design) was treated as "the single weakest domain" and could outrank a domain the learner is genuinely failing | sort key now sends any domain absent from `per_domain` to the **end**, not the front; a regression test proves a 10%-accuracy scored domain (D3) still outranks the unscored `global` bucket |
| F2 | minor | an unresolved `item_id` (goldset lookup miss) produced a Python `None` domain — schema-invalid JSON, and a hard crash in the HTML render (`html.escape(None)`) | falls back to an explicit `"unknown"` sentinel (added to the schema enum); regression test proves both the JSON shape and that the render no longer crashes |
| F3 | minor | `priority` is the item's aggregate confidence flag, not per-misconception — latent with today's content (no item maps two misconceptions to one set of distractors), would surface if one ever did | documented explicitly in the module docstring and this report as an accepted limitation, rather than re-plumbing `learner_state`'s journal schema (an already-shipped, independently-reviewed module) for an unreachable case |
| F4 | minor | the HTML leakage gates (both dashboard's and cram-sheet's) checked a narrower field list than their JSON siblings — a future edit could leak `choices`/`fact_ids`/`expected_keywords`/hash fields into HTML undetected | widened both HTML gates (Makefile + CI workflow) to the same compound-identifier set as their JSON gates. **Caught during the fix**: a naive widen using bare English words (`answer`, `correct`, `stem`, `trap`) false-positived against the dashboard's own legitimate copy ("Wrong answers", "no answers, no PII") and even CSS (`-apple-system` contains "stem") — verified empirically against real rendered output before landing the narrower, safe, compound-identifier-only pattern |

Clean areas the reviewer confirmed: holdout rejection happens before any journal entry can be built
(verified by reading the exact code order in `learner_state.replay`); `cram_sheet.py` imports only
`quiz.load_goldset()` — never `answer-keys.json`/`holdout.json` — a structurally stronger isolation
guarantee than "the journal happens to be clean"; the priority/recency/id sort and the closed-recap
dedup are both correct; the test suite deliberately avoided the CSS-class-vs-rendered-element false
positive already caught twice in the sibling dashboard-view suite. Full record in
`pr11c-cram-sheets-review.json`.

## 7. Next

PR-11 (dashboard + cram sheets) is now complete. Candidates: wiring cram-sheet generation into
`cmd_learner`'s replay flow as a convenience, or moving to PR-12 (live API variant generation, per
the PR-10.4 roadmap) or a promotion pipeline for reviewed variants.
