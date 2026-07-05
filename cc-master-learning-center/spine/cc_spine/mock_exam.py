"""cc_spine.mock_exam — the mock-exam assembler (PR-10).

Draws a mock exam per the ``mock_exam`` policy in banks.json: domain-weighted, drawing
non-scenario items from the PRACTICE lane and scenario items from the HOLDOUT lane
(``scenario_draw: holdout_only``). The mock is the one place holdout items legitimately
surface to a learner — their single unseen exposure that feeds fresh-scenario accuracy.

Isolation:
- Determinism, not randomness: the draw is seeded by ``draw_key`` (a caller-supplied
  string), ranked by a stable hash — no ``random``/wall clock. Same key + same ``seen`` set
  → identical mock, which makes the draw auditable and the holdout "burn" reproducible.
- Single-use ("burn"): a holdout id passed in ``seen`` is excluded from the draw. Burn state
  is LEARNER state (gitignored) — this module only reads a ``seen`` set, never writes it.
- The learner view of a mock never carries answers (reuses ``quiz.learner_view``).

Stdlib only. Imports ``quiz`` (loaders + grading) and reads the banks.json policy.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import quiz

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_BANKS_PATH = _PROJECT_ROOT / "spine" / "banks" / "banks.json"

_SCENARIO_BANK = "scenario_application"


def _policy() -> dict:
    return json.loads(_BANKS_PATH.read_text(encoding="utf-8"))["mock_exam"]


def _rank(draw_key: str, item_id: str) -> str:
    """Deterministic per-item rank — a stable hash of the seed and the id (no randomness)."""
    return hashlib.sha256(f"{draw_key}\x1f{item_id}".encode("utf-8")).hexdigest()


def _domain_allocation(weights: dict, count: int) -> dict:
    """Split ``count`` across domains by weight, deterministically, summing to exactly count."""
    raw = {d: w * count for d, w in weights.items()}
    base = {d: int(v) for d, v in raw.items()}
    remainder = count - sum(base.values())
    # hand out the remaining slots to the largest fractional parts (ties by domain id).
    frac = sorted(weights, key=lambda d: (-(raw[d] - base[d]), d))
    for d in frac[:remainder]:
        base[d] += 1
    return base


def assemble(draw_key: str, count: int = 15, seen=frozenset()) -> dict:
    """Assemble a deterministic mock: domain-weighted, non-scenario from practice, scenario
    from holdout (excluding ``seen`` holdout ids). Returns a mock descriptor whose items carry
    their lane so the grader knows which key store to use."""
    policy = _policy()
    weights = policy["domain_weights"]
    draw_from = set(policy["draw_from"])

    practice = quiz.load_goldset()
    holdout = quiz.load_holdout()
    seen = set(seen)

    # candidate pools per domain
    prac_nonscenario = {}
    hold_scenario = {}
    for it in practice:
        if it["bank"] in draw_from and it["bank"] != _SCENARIO_BANK:
            prac_nonscenario.setdefault(it["domain"], []).append(it)
    for it in holdout:
        if it["bank"] == _SCENARIO_BANK and it["id"] not in seen:
            hold_scenario.setdefault(it["domain"], []).append(it)

    alloc = _domain_allocation(weights, count)
    picked, notes = [], []
    for dom in sorted(alloc):
        need = alloc[dom]
        if need <= 0:
            continue
        dom_items = []
        # one scenario per domain from holdout, if available
        scen = sorted(hold_scenario.get(dom, []), key=lambda it: _rank(draw_key, it["id"]))
        if scen:
            dom_items.append((scen[0], "holdout"))
        else:
            notes.append(f"{dom}: no unseen holdout scenario available")
        # fill the rest from practice non-scenario, ranked deterministically
        pool = sorted(prac_nonscenario.get(dom, []), key=lambda it: _rank(draw_key, it["id"]))
        for it in pool:
            if len(dom_items) >= need:
                break
            dom_items.append((it, "practice"))
        if len(dom_items) < need:
            notes.append(f"{dom}: only {len(dom_items)}/{need} items available (content-limited)")
        for it, lane in dom_items[:need]:
            picked.append({"item_id": it["id"], "lane": lane, "bank": it["bank"],
                           "domain": it["domain"], "objective": it["objective"]})

    return {"draw_key": draw_key, "requested": count, "assembled": len(picked),
            "items": picked, "notes": notes}


def exposed_holdout_ids(mock: dict) -> list:
    """Every holdout id assembled into this mock — 'seen' the moment the mock is built, because
    ``mock_learner_view`` reveals all of them. This is the authoritative burn set: pass it into a
    future ``assemble(seen=…)`` regardless of what the learner actually submitted, so an exposed
    scenario is never re-drawn and re-counted as 'fresh' (PR-10 review F2)."""
    return sorted({e["item_id"] for e in mock["items"] if e["lane"] == "holdout"})


def mock_learner_view(mock: dict) -> list:
    """The learner-facing mock — each item projected through quiz.learner_view (no answers).
    Practice and holdout items are shown uniformly; the learner cannot tell the lanes apart."""
    prac = {i["id"]: i for i in quiz.load_goldset()}
    hold = {i["id"]: i for i in quiz.load_holdout()}
    views = []
    for entry in mock["items"]:
        src = hold if entry["lane"] == "holdout" else prac
        item = src.get(entry["item_id"])
        if item is not None:
            views.append(quiz.learner_view(item))
    return views


def grade_mock(mock: dict, submissions: dict) -> dict:
    """Grade a mock in evaluator context. ``submissions`` maps item_id → selected_index.
    Resolves each item's key from its own lane (practice or holdout). Returns the overall and
    per-bank results plus the fresh-scenario (holdout) accuracy and the burned holdout ids —
    the holdout items' CONTENT never leaves this function."""
    prac_items = {i["id"]: i for i in quiz.load_goldset()}
    hold_items = {i["id"]: i for i in quiz.load_holdout()}
    prac_keys = quiz.load_answer_keys()
    hold_keys = quiz.load_holdout_keys()

    from collections import Counter
    correct = Counter()
    total = Counter()
    fresh_correct = fresh_total = 0

    # Burn on EXPOSURE, not submission: every holdout scenario ASSEMBLED into this mock was shown
    # to the learner (mock_learner_view reveals all of them) and is now 'seen' whether or not they
    # answered it — otherwise a skipped item could be re-drawn and re-counted 'fresh' (review F2).
    # exposed_holdout_ids is the single source of truth so the burn set can't drift from grading.
    burned = exposed_holdout_ids(mock)

    for entry in mock["items"]:
        iid = entry["item_id"]
        holdout = entry["lane"] == "holdout"
        item = (hold_items if holdout else prac_items).get(iid)
        keys = hold_keys if holdout else prac_keys
        if item is None or iid not in submissions:
            continue
        res = quiz.grade(item, keys, submissions[iid])
        ok = bool(res.get("correct"))
        total[entry["bank"]] += 1
        if ok:
            correct[entry["bank"]] += 1
        if holdout and entry["bank"] == _SCENARIO_BANK:
            fresh_total += 1   # accuracy counts only SUBMITTED holdout scenarios
            fresh_correct += int(ok)

    graded = sum(total.values())
    return {
        "graded": graded,
        "overall_accuracy": (sum(correct.values()) / graded) if graded else 0.0,
        "per_bank": {b: {"correct": correct[b], "total": total[b],
                         "accuracy": (correct[b] / total[b] if total[b] else 0.0)}
                     for b in total},
        "fresh_scenario_accuracy": (fresh_correct / fresh_total) if fresh_total else None,
        "fresh_scenario_count": fresh_total,
        "burned_holdout_ids": burned,
    }


def validate_mock(mock: dict) -> list:
    """Policy conformance: no duplicate items, scenarios are holdout-only, non-scenarios are
    practice, banks are within draw_from, and every referenced item resolves in its lane."""
    problems = []
    policy = _policy()
    draw_from = set(policy["draw_from"])
    prac = {i["id"] for i in quiz.load_goldset()}
    hold = {i["id"] for i in quiz.load_holdout()}

    seen = set()
    for entry in mock["items"]:
        iid = entry["item_id"]
        if iid in seen:
            problems.append(f"{iid}: appears more than once in the mock")
        seen.add(iid)
        if entry["bank"] not in draw_from:
            problems.append(f"{iid}: bank {entry['bank']!r} is not in the mock draw_from")
        if entry["bank"] == _SCENARIO_BANK and entry["lane"] != "holdout":
            problems.append(f"{iid}: scenario item must be drawn from the holdout lane (holdout_only)")
        if entry["bank"] != _SCENARIO_BANK and entry["lane"] != "practice":
            problems.append(f"{iid}: non-scenario item must be drawn from the practice lane")
        pool = hold if entry["lane"] == "holdout" else prac
        if iid not in pool:
            problems.append(f"{iid}: does not resolve in the {entry['lane']} lane")
    return problems
