# PR-10.1 Holdout Scenario Content Slice

**Slice:** PR-10.1 — grow the holdout scenario supply so mock exams (PR-10) can measure real
unseen-scenario accuracy. Small content slice; no engine changes.

## Why

`mock_exam.scenario_draw` is `holdout_only`, but the holdout lane carried **1** scenario item —
too thin for a mock to draw a scenario per domain. This slice adds **4** holdout scenario items
(D1–D4), bringing the holdout scenario supply to **5 — one per domain**.

| Domain | New holdout scenario | Concept |
|---|---|---|
| D1 | `D1.1.2.scenario.9001` | risk treatment — Transfer/Share (insurance) |
| D2 | `D2.2.1.scenario.9001` | BC vs DR (restore = DR) |
| D3 | `D3.3.1.scenario.9001` | layered physical defense in depth |
| D4 | `D4.4.3.scenario.9001` | DMZ vs VLAN (perimeter isolation) |
| D5 | `D5.5.1.scenario.9001` | (existing) sanitization Destroy |

## Gates

All holdout gates hold: same item gates (`validate_gold`), lane partition, no-leak-into-practice,
structural isolation. Registry grew by 4 entries. **Adversarial review before commit (§16.0):
independent reviewer, author ≠ reviewer — 0 findings** (this time the review was awaited before
the commit). Holdout lane: 8 → 12 items.
