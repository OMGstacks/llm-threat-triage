"""cc_spine.learner_state — the wrong-answer journal + spaced-repetition engine (PR-9).

Turns a stream of quiz attempts into a learner's study state: per-item Leitner mastery, a
wrong-answer journal keyed to the misconception registry, and a *partial* readiness readout.

Boundaries (the PR-9 isolation story):
- **No learner data is committed.** This module is the engine; actual state is a local,
  gitignored runtime artifact. The scaffold fails if a state file is committed.
- **Deterministic.** ``now`` and every ``submitted_at`` are injected as integer time units;
  the engine never reads the wall clock or a random source. Same attempts + same ``now`` →
  byte-identical state.
- **Fail closed on holdout.** An attempt whose item_id is not in the practice lane (a holdout
  item, or unknown) is rejected with ``LearnerStateError`` — it can never enter the journal,
  the schedule, or readiness.
- **Compact + non-leaky.** State stores ``selected_index`` and ``misconception_id`` — never a
  stem, full choice text, or answer key. The teaching text (correction / one-sentence rule)
  comes from the committed misconception registry.

Stdlib only. Imports ``quiz`` (practice loaders + grading) — never the reverse.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import quiz

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_BANKS_PATH = _PROJECT_ROOT / "spine" / "banks" / "banks.json"

# Leitner: box -> time units until the item is due again after a review in that box.
BOX_INTERVAL = {1: 0, 2: 1, 3: 3, 4: 7, 5: 16}
MAX_BOX = 5
CLOSED_AFTER_CORRECT_STREAK = 2   # a misconception is "closed" after 2 later correct answers
LOW_CONFIDENCE = 2                 # correct-but-unsure (<=) is not fully promoted
HIGH_CONFIDENCE = 4               # wrong-but-sure (>=) is a priority misconception
MATURE_BOX = 3                    # a flashcard is "mature" once it reaches this Leitner box
TIME_BUDGET_SECONDS = 90         # per-item time budget for the time-management signal

STATE_SCHEMA_VERSION = "1.0.0"


class LearnerStateError(Exception):
    """Raised on an attempt that must be rejected (e.g., a holdout item_id)."""


# --- lane resolution -------------------------------------------------------- #

def _practice_index(practice=None, keys=None):
    practice = practice if practice is not None else quiz.load_goldset()
    keys = keys if keys is not None else quiz.load_answer_keys()
    key_by_id = {k["item_id"]: k for k in keys}
    return {it["id"]: (it, key_by_id.get(it["id"])) for it in practice}


def _item_misconceptions(key) -> list:
    """The distinct misconceptions an item's distractors target, in choice order."""
    seen, out = set(), []
    for entry in (key.get("distractor_misconceptions") or {}).values():
        mid = entry.get("misconception_id")
        if mid and mid not in seen:
            seen.add(mid)
            out.append(mid)
    return out


def _attempt_sort_key(a: dict):
    """A TOTAL ordering key over an attempt's content, so replay output is a pure function of
    the attempt SET (not the input-list order) even when two attempts share item + time."""
    return (
        a.get("submitted_at", 0),
        a.get("item_id", ""),
        a.get("selected_index", -1),
        a.get("confidence_before_submit", -1),
        1 if a.get("marked_uncertain") else 0,
        a.get("time_seconds", -1),
    )


def _one_sentence_rule(correction: str) -> str:
    """The crisp rule = the first sentence of the registry correction."""
    first = correction.split(". ")[0].strip().rstrip(".")
    return (first + ".") if first else correction


# --- replay ----------------------------------------------------------------- #

def replay(attempts, now: int, practice=None, keys=None, registry=None, holdout_ids=None) -> dict:
    """Fold an attempt stream into a learner-state snapshot. ``now`` and every attempt's
    ``submitted_at`` are integer time units (injected — never read from the clock)."""
    index = _practice_index(practice, keys)
    holdout_ids = holdout_ids if holdout_ids is not None else {i["id"] for i in quiz.load_holdout()}
    registry = registry if registry is not None else quiz._load_registry()

    items: dict = {}
    journal: list = []
    misconceptions: dict = {}
    domain_stats: dict = {}   # domain -> [correct, total], excluding exam_strategy
    bank_stats: dict = {}     # bank -> [correct, total], excluding exam_strategy
    time_within = time_total = 0   # time-management: attempts answered within budget

    # Deterministic order: a TOTAL key over the attempt's content, so the output is a pure
    # function of the attempt SET — two attempts on the same item at the same time no longer
    # depend on input-list order (PR-9.1 fix).
    ordered = sorted(attempts, key=_attempt_sort_key)

    for a in ordered:
        iid = a.get("item_id")
        if iid in holdout_ids:
            raise LearnerStateError(
                f"attempt for {iid!r} is a holdout item — holdout attempts are rejected from learner state")
        if iid not in index:
            raise LearnerStateError(f"attempt for unknown item {iid!r} (not in the practice lane)")
        item, key = index[iid]
        if key is None:
            raise LearnerStateError(f"attempt for {iid!r} has no grader key")
        # Defense-in-depth: a holdout-flagged item that leaked into the practice lane is
        # rejected even if it is absent from holdout.json (PR-9.1 fix).
        if item.get("holdout"):
            raise LearnerStateError(f"attempt for {iid!r} is flagged holdout — rejected from learner state")

        sel = a.get("selected_index")
        graded = quiz.grade(item, [key], sel)
        # Fail closed on an ungradable attempt (e.g. answer_key_ref drift) rather than
        # silently recording it as a miss (PR-9.1 fix).
        if not graded.get("graded"):
            raise LearnerStateError(f"attempt for {iid!r} could not be graded (grader key unresolved)")
        correct = bool(graded.get("correct"))
        conf = a.get("confidence_before_submit")
        unsure = bool(a.get("marked_uncertain")) or (isinstance(conf, int) and conf <= LOW_CONFIDENCE)
        overconfident = isinstance(conf, int) and conf >= HIGH_CONFIDENCE
        t = a.get("submitted_at", 0)

        st = items.setdefault(iid, {"box": 1, "attempts": 0, "correct": 0, "correct_streak": 0,
                                    "last_seen": t, "due": t, "priority": False})
        st["attempts"] += 1
        st["last_seen"] = t
        if correct:
            st["correct"] += 1
            # correct-but-unsure is not promoted (stays due sooner); confident-correct promotes.
            if not unsure:
                st["box"] = min(st["box"] + 1, MAX_BOX)
            st["correct_streak"] += 1
            if st["correct_streak"] >= CLOSED_AFTER_CORRECT_STREAK:
                st["priority"] = False
        else:
            st["box"] = 1
            st["correct_streak"] = 0
            if overconfident:
                st["priority"] = True
        st["due"] = t + BOX_INTERVAL[st["box"]]

        def _mc(mid):
            return misconceptions.setdefault(mid, {"seen": 0, "missed": 0, "correct_streak": 0, "closed": False})

        def _close_check(mc):
            mc["closed"] = mc["missed"] > 0 and mc["correct_streak"] >= CLOSED_AFTER_CORRECT_STREAK

        if correct:
            # A correct answer avoids every trap the item's distractors set — progress each.
            for mid in _item_misconceptions(key):
                mc = _mc(mid)
                mc["seen"] += 1
                mc["correct_streak"] += 1
                _close_check(mc)
        else:
            # The learner demonstrated the misconception of the choice they ACTUALLY selected
            # (not merely the first distractor) (PR-9.1 fix).
            sel_entry = graded.get("misconception")
            missed_mid = (sel_entry or {}).get("misconception_id") if isinstance(sel_entry, dict) else None
            if missed_mid is None:
                item_mids = _item_misconceptions(key)
                missed_mid = item_mids[0] if item_mids else None
            if missed_mid:
                mc = _mc(missed_mid)
                mc["seen"] += 1
                mc["missed"] += 1
                mc["correct_streak"] = 0
                _close_check(mc)

        # readiness accuracy excludes the exam_strategy bank (excluded_from_readiness).
        if item.get("bank") != "exam_strategy":
            dom = item.get("domain", "?")
            ds = domain_stats.setdefault(dom, [0, 0])
            ds[1] += 1
            bs = bank_stats.setdefault(item.get("bank", "?"), [0, 0])
            bs[1] += 1
            if correct:
                ds[0] += 1
                bs[0] += 1
            ts = a.get("time_seconds")
            if isinstance(ts, (int, float)):
                time_total += 1
                if ts <= TIME_BUDGET_SECONDS:
                    time_within += 1

        # wrong answers become journal entries (with the registry correction, not the stem).
        if not correct and missed_mid:
            reg = registry.get(missed_mid, {})
            correction = reg.get("correct", "")
            journal.append({
                "item_id": iid, "objective": item.get("objective"), "bank": item.get("bank"),
                "selected_index": sel, "misconception_id": missed_mid,
                "trap": reg.get("misconception", ""), "correction": correction,
                "one_sentence_rule": _one_sentence_rule(correction),
                "recorded_at": t,
                "closed": bool(misconceptions.get(missed_mid, {}).get("closed")),
            })

    # Reconcile each journal entry's closed flag to the FINAL misconception status (a miss
    # logged early may have been closed by later correct answers).
    for j in journal:
        j["closed"] = bool(misconceptions.get(j["misconception_id"], {}).get("closed"))

    # closure rate: of misconceptions ever missed, how many are now closed.
    missed = [m for m in misconceptions.values() if m["missed"] > 0]
    closed = [m for m in missed if m["closed"]]
    closure_rate = (len(closed) / len(missed)) if missed else 1.0

    per_domain = {d: {"correct": c, "attempts": n, "accuracy": (c / n if n else 0.0)}
                  for d, (c, n) in sorted(domain_stats.items())}

    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "attempts_replayed": len(ordered),
        "items": items,
        "journal": journal,
        "misconceptions": misconceptions,
        "readiness": {
            "partial": True,
            "note": "practice-only: excludes exam_strategy and holdout; fresh-scenario needs a mock (readiness_report)",
            "per_domain": per_domain,
            "per_bank": {b: {"correct": c, "total": n, "accuracy": (c / n if n else 0.0)}
                         for b, (c, n) in sorted(bank_stats.items())},
            "time_management": {"within_budget": time_within, "total": time_total,
                                "performance": (time_within / time_total if time_total else 0.0)},
            "wrong_answer_closure_rate": closure_rate,
        },
    }


# --- review queue (gate 10 ordering) ---------------------------------------- #

def review_queue(state: dict, now: int) -> list:
    """Item ids due at ``now``, ordered: lower Leitner box first, then older last_seen, then
    item_id as a deterministic tie-breaker. Priority (high-confidence miss) floats to the top."""
    due = [(iid, s) for iid, s in state.get("items", {}).items() if s["due"] <= now]
    due.sort(key=lambda kv: (not kv[1].get("priority"), kv[1]["box"], kv[1]["last_seen"], kv[0]))
    return [iid for iid, _ in due]


def open_journal(state: dict) -> list:
    """Journal entries for misconceptions not yet closed — the active study list."""
    return [j for j in state.get("journal", []) if not j.get("closed")]


# --- full readiness (PR-10: completes the banks.json formula with a graded mock) ---------- #

def _readiness_policy() -> dict:
    return json.loads(_BANKS_PATH.read_text(encoding="utf-8"))["readiness"]


def _mature_accuracy(state: dict):
    c = t = 0
    for st in state.get("items", {}).values():
        if st.get("box", 1) >= MATURE_BOX:
            c += st.get("correct", 0)
            t += st.get("attempts", 0)
    return (c / t) if t else None


def readiness_report(state: dict, mock_result: dict = None, leakage_ok: bool = True) -> dict:
    """Compute the full banks.json readiness formula. Practice attempts supply concept-
    discrimination, mature-flashcard, closure, and time components; a graded mock supplies
    ``fresh_scenario_accuracy`` (holdout scenarios). Applies the hard blockers (any domain
    < 75%; holdout-scenario accuracy < 80%; any leakage gate red). Weights over the
    components that have data, so a mock-less report is still informative but flagged
    incomplete."""
    weights = _readiness_policy()["domain_formula"]
    r = state.get("readiness", {})
    per_bank = r.get("per_bank", {})
    fresh = (mock_result or {}).get("fresh_scenario_accuracy")

    tm = r.get("time_management", {})
    components = {
        "fresh_scenario_accuracy": fresh,
        "concept_discrimination_accuracy": per_bank.get("concept_discrimination", {}).get("accuracy"),
        "mature_flashcard_accuracy": _mature_accuracy(state),
        "wrong_answer_closure_rate": r.get("wrong_answer_closure_rate"),
        # No timing data → excluded (None), not a 0% penalty.
        "time_management_performance": tm.get("performance") if tm.get("total") else None,
    }
    avail = {k: v for k, v in components.items() if v is not None}
    wsum = sum(weights[k] for k in avail) or 1.0
    score = sum(weights[k] * avail[k] for k in avail) / wsum

    blockers = []
    for dom, s in r.get("per_domain", {}).items():
        if s.get("attempts") and s["accuracy"] < 0.75:
            blockers.append(f"domain {dom} accuracy {s['accuracy']:.0%} < 75%")
    if fresh is not None and fresh < 0.80:
        blockers.append(f"holdout scenario accuracy {fresh:.0%} < 80%")
    if not leakage_ok:
        blockers.append("a leakage/isolation gate is failing")

    complete = fresh is not None
    ready = complete and not blockers and score >= 0.80
    return {
        "score": round(score, 4),
        "components": components,
        "weighted_over": sorted(avail),
        "hard_blockers": blockers,
        "complete": complete,
        "verdict": "ready" if ready else "not-ready",
        "note": None if complete else "incomplete: needs a graded mock for fresh_scenario_accuracy",
    }
