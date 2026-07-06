"""cc_spine.dashboard — the readiness dashboard DATA MODEL (PR-11a).

Data-first, not the visual layer (that is PR-11b). This module projects a learner state (from
``learner_state.replay``) and an optional graded mock (from ``mock_exam.grade_mock``) into a single
content-free dashboard object: the numbers a readiness view renders. It adds no READINESS policy —
the verdict/score/blockers are carried verbatim from ``learner_state.readiness_report`` (the
banks.json formula) — composed with the spaced-repetition queue, the wrong-answer journal summary,
the misconception ranking, and the mock signals, so PR-11b can render pixels without recomputing
anything. The one judgment this module makes of its own is the DISPLAY-ONLY ``content_scale``
classification (proof-scale vs exam-scale, the P1-3 caveat) — advisory, never touching the verdict
or score.

Isolation & determinism:
- Content-free: only ids, counts, accuracies, verdicts — never a stem, a correct answer, an answer
  key, or a PII field. Item ids and misconception ids are already learner-visible (learner_view /
  the journal). Safe to log, ship, and commit as a synthetic sample.
- Deterministic: a pure function of (state, mock_result, leakage_ok, now). ``now`` is the injected
  day counter used everywhere in this codebase — no wall clock, no randomness.

Stdlib only. Imports ``learner_state``, ``mock_exam``, ``quiz``; imported by none of them.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import learner_state, quiz

DASHBOARD_SCHEMA_VERSION = "1.0.0"
_MAX_LIST = 10           # cap every id list so the dashboard stays a summary, not a dump
_SCENARIO_BANK = "scenario_application"
_BANKS_PATH = Path(__file__).resolve().parents[1] / "banks" / "banks.json"


def _content_scale() -> dict:
    """The P1-3 caveat: today's content is proof-scale, not exam-length. A learner must not read a
    ~15-item mock as exam readiness. Counts are derived from the committed stores; the target is the
    banks.json mock policy."""
    practice = len(quiz.load_goldset())
    holdout_scenarios = len([h for h in quiz.load_holdout() if h.get("bank") == _SCENARIO_BANK])
    banks = json.loads(_BANKS_PATH.read_text(encoding="utf-8"))["mock_exam"]
    lo, hi = banks["item_count_min"], banks["item_count_max"]
    exam_scale = practice + holdout_scenarios >= lo
    return {
        "practice_items": practice,
        "holdout_scenarios": holdout_scenarios,
        "mock_target_min": lo,
        "mock_target_max": hi,
        "status": "exam_scale" if exam_scale else "proof_scale",
        "caveat": (None if exam_scale else
                   f"content is proof-scale: {practice} practice + {holdout_scenarios} holdout "
                   f"scenario(s) support a short mock, well under the {lo}-{hi} item exam target — "
                   "a passing mock here is an engine proof, not exam readiness"),
    }


def build_dashboard(state: dict, mock_result: dict = None, leakage_ok: bool = True,
                    now: int = 0) -> dict:
    """Assemble the content-free readiness dashboard. Pure function of its inputs."""
    if not isinstance(mock_result, dict):
        mock_result = None      # a non-dict mock is treated as 'no mock' (defensive; review F1)
    readiness = learner_state.readiness_report(state, mock_result=mock_result, leakage_ok=leakage_ok)
    r = state.get("readiness", {})
    due = learner_state.review_queue(state, now)
    open_j = learner_state.open_journal(state)
    items = state.get("items", {})

    top_misconceptions = sorted(
        ({"misconception_id": mid, "missed": m["missed"], "closed": m["closed"]}
         for mid, m in state.get("misconceptions", {}).items() if m["missed"] > 0),
        key=lambda e: (-e["missed"], e["misconception_id"]))

    mock = None
    if mock_result is not None:
        mock = {
            "fresh_scenario_accuracy": mock_result.get("fresh_scenario_accuracy"),
            "fresh_scenario_count": mock_result.get("fresh_scenario_count", 0),
            "overall_accuracy": mock_result.get("overall_accuracy"),
            "burned_holdout_count": len(mock_result.get("burned_holdout_ids", [])),
        }

    return {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        "generated_at_day": now,
        "readiness": {
            "verdict": readiness["verdict"],
            "score": readiness["score"],
            "complete": readiness["complete"],
            "weighted_over": readiness["weighted_over"],
            "hard_blockers": readiness["hard_blockers"],
            "note": readiness["note"],
        },
        "domain_accuracy": {d: {"accuracy": round(s["accuracy"], 4), "attempts": s["attempts"]}
                            for d, s in sorted(r.get("per_domain", {}).items())},
        "bank_accuracy": {b: {"accuracy": round(s["accuracy"], 4), "total": s["total"]}
                          for b, s in sorted(r.get("per_bank", {}).items())},
        "spaced_repetition": {
            "total_items": len(items),
            "due_now": len(due),
            "mature_items": sum(1 for s in items.values()
                                if s.get("box", 1) >= learner_state.MATURE_BOX),
            "next_review_items": due[:_MAX_LIST],
        },
        "wrong_answers": {
            "open_count": len(open_j),
            "closure_rate": round(r.get("wrong_answer_closure_rate", 1.0), 4),
            "open_misconceptions": sorted({j.get("misconception_id") for j in open_j
                                           if j.get("misconception_id")})[:_MAX_LIST],
        },
        "top_misconceptions": top_misconceptions[:_MAX_LIST],
        "mock": mock,
        "content_scale": _content_scale(),
        "next_recommended_review": due[:_MAX_LIST],
    }
