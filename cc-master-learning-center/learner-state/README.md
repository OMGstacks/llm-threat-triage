# Learner State — Intentionally Separate From Content

This directory documents the **learner-state layer**. It holds no committed data — ever. PR-1
reserved this contract; **PR-9 delivers the engine** (`../spine/cc_spine/learner_state.py`) plus
the formal schemas (`../spine/schemas/learner-attempt.schema.json`,
`../spine/schemas/learner-state.schema.json`). Real learner state is a local, gitignored runtime
artifact: the `learner_state_isolation_guard` fails the build if any state `.json` is committed
here, and only synthetic fixtures under `../spine/tests/fixtures/` may carry attempt-shaped data.
The sketches below are the original contract; the schemas are the authoritative form (e.g.
attempts store `selected_index`, and the engine re-grades rather than trusting a stored `correct`).

## Why learner state is excluded from fact cards

Fact cards and bank items are **immutable reviewed content**. Scheduling and performance
state — the Confidence / Missed-Count / Next-Review-Date fields from the study-plan
content-object schema — live here, in a learner database, never on cards. Mixing them would
make content PRs churn on every study session and would break card fingerprinting.

## Coverage is not mastery

Three separate signals, never conflated:

| Signal | Meaning | Lives in |
|---|---|---|
| `coverage_status` | Content exists for an objective | `reference/objective-matrix.json` |
| `validation_status` | Content passes factstore/provenance gates | validator reports |
| `learning_status` | The learner has demonstrated performance | this layer |

A readiness dashboard may only say "ready" based on `learning_status` (plus green gates) —
never because files exist.

## Reserved per-attempt record (confidence calibration)

```json
{
  "question_id": "D4.4.1.scenario.0001",
  "selected_answer": "B",
  "correct": true,
  "confidence_before_submit": 2,
  "time_seconds": 71,
  "marked_uncertain": true,
  "remediation_required": true
}
```

Calibration rules:

- **Correct but low-confidence** answers still enter review.
- **Wrong but high-confidence** answers become priority remediation.

This encodes the course's study method: mark uncertainty, review every miss and every
uncertain answer, and only move forward after you can explain the concept.

## Misconception taxonomy (controlled list)

The wrong-answer journal tags every miss with one or more of:

- `definition_confusion`
- `process_order_confusion`
- `best_vs_first_qualifier_miss`
- `control_category_confusion`
- `overly_technical_answer`
- `overly_expensive_answer`
- `ignored_business_or_data_owner`
- `current_vs_2026_outline_confusion`
- `crypto_property_confusion`
- `network_device_confusion`

Extending this list is a schema change (see the migration policy in
[`../spine/schemas/bank-item.schema.json`](../spine/schemas/bank-item.schema.json), which
mirrors the same taxonomy in `misconception_tags`).

## Wrong-answer journal record (reserved)

```text
Question missed:
Correct answer:
Why my answer was wrong:
Keyword I missed:
Misconception tag(s):
Concept to restudy (objective id):
One-sentence rule:
Next review date:
```

A missed question is **closed** only when the learner answers a fresh item on the same
objective correctly *and* can state the one-sentence rule. The closure rate feeds the
readiness formula in [`../spine/banks/banks.json`](../spine/banks/banks.json).
