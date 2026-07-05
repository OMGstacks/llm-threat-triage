"""cc_spine.presentation — render-time answer-choice shuffling (PR-10.3).

Canonical items in ``goldset.json`` / ``holdout.json`` NEVER change. Presentation order is computed
per ATTEMPT at render time, so a learner who repeats an item does not see the same choice letters —
*provided the caller supplies a fresh, distinct ``attempt_seed`` per attempt*. That seed-freshness
contract is load-bearing: the order is a PURE function of ``(attempt_seed, item_id)``, so reusing a
seed reproduces the identical order (which is exactly what makes grading recomputable — see below).
Callers that want the "letters move every attempt" anti-memorization property must vary the seed
(an attempt counter, a uuid); reusing one is fully memorisable by design.

Deterministic recomputation (the reviewer's preferred model): ``(attempt_seed, item_id)`` seeds a
stable permutation via SHA-256 rank — no ``random`` module, no wall clock. Because the order is a
pure function of the seed and the id, the GRADER recomputes the exact same order to map a displayed
choice back to its canonical index. Nothing has to store or transmit a choice-order mapping, so no
"order secret" ever reaches the learner lane.

Isolation preserved:
- ``render_item`` reuses ``quiz.learner_view`` (the allowlist) and only REORDERS the choices — it
  adds no answer-bearing field. ``presentation_id`` is a content-free hash of ``(attempt_seed,
  item_id)`` and reveals nothing about the correct answer.
- ``item_hash`` / ``answer_key_hash`` still pin the CANONICAL item; shuffling touches neither the
  goldset nor the key store.
- The grader never assumes displayed index == canonical index.

Stdlib only. Imports ``quiz`` (learner_view + grade); never the reverse.
"""

from __future__ import annotations

import hashlib

from . import quiz


def _rank(attempt_seed: str, item_id: str, index: int) -> str:
    """Stable per-choice rank — a SHA-256 of the seed, the id, and the canonical index (no
    randomness, no clock). Unit separators so fields cannot run together and collide."""
    return hashlib.sha256(f"{attempt_seed}\x1f{item_id}\x1f{index}".encode("utf-8")).hexdigest()


def presentation_order(item_id: str, attempt_seed: str, n: int) -> list:
    """Deterministic permutation of ``range(n)``: element ``d`` is the CANONICAL choice index shown
    in display position ``d``. Ranked by ``_rank``; a stable sort keeps it a valid permutation even
    in the astronomically unlikely event of a rank tie. Same inputs → identical order; a different
    ``attempt_seed`` → (almost always) a different order."""
    return sorted(range(n), key=lambda i: _rank(attempt_seed, item_id, i))


def presentation_id(item_id: str, attempt_seed: str) -> str:
    """A content-free token for one (item, attempt) render — a hash of ``(attempt_seed, item_id)``.
    Carries no answer information and does not encode the order; safe in a learner render. Passing it
    back to ``grade_presented`` as ``expected_presentation_id`` turns it into a real integrity check
    that the submission is being graded under the SAME attempt it was rendered for."""
    digest = hashlib.sha256(f"{attempt_seed}\x1f{item_id}".encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def render_item(item: dict, attempt_seed: str) -> dict:
    """A learner-safe render of ONE item with its choices shuffled for this attempt. Built on
    ``quiz.learner_view`` (the allowlist), so it carries no correct index / rationale / answer-key
    field — only the choices are reordered. Adds ``presentation_id`` and ``choice_count``."""
    view = quiz.learner_view(item)
    choices = view.get("choices", [])
    order = presentation_order(item["id"], attempt_seed, len(choices))
    view["choices"] = [choices[i] for i in order]
    view["presentation_id"] = presentation_id(item["id"], attempt_seed)
    view["choice_count"] = len(choices)
    return view


def render_quiz(items: list, attempt_seed: str) -> list:
    """Render a whole attempt — every item shuffled under the same ``attempt_seed``. Each item's
    order is still independent (the id is part of the rank), so items don't share a permutation."""
    return [render_item(it, attempt_seed) for it in items]


def displayed_to_canonical(item_id: str, attempt_seed: str, displayed_index: int, n: int) -> int:
    """Map a learner's displayed choice index back to the canonical index by RECOMPUTING the same
    order the render used — no stored mapping required. ``order[displayed] == canonical``.
    PRECONDITION: ``displayed_index`` must already be a validated ``int`` in ``[0, n)`` — this
    primitive does not range-check (``grade_presented`` is the guarded public entry point); an
    out-of-range value raises IndexError and a negative value wraps."""
    return presentation_order(item_id, attempt_seed, n)[displayed_index]


def _is_index(x) -> bool:
    """A real choice index — an int but NOT a bool (``bool`` is an ``int`` subclass, and True/False
    must not be silently coerced to indices 1/0 on a governed grader)."""
    return isinstance(x, int) and not isinstance(x, bool)


def grade_presented(item: dict, keys, attempt_seed: str, displayed_index: int,
                    expected_presentation_id: str = None) -> dict:
    """Grade a submission made against the SHUFFLED presentation. Recomputes the order, maps the
    displayed index to its canonical index, then grades canonically (reuses ``quiz.grade``). Grader
    context only — the returned canonical/correct indices never travel in a learner render.

    Fail-closed on a malformed submission (non-int / bool / out-of-range displayed index). If
    ``expected_presentation_id`` is supplied, it must match the id recomputed from ``attempt_seed``
    and the item — otherwise the submission is being graded under a DIFFERENT attempt than it was
    rendered for (a seed mix-up) and is rejected rather than silently mapped through the wrong
    permutation."""
    n = len(item.get("choices", []))
    if not _is_index(displayed_index) or not (0 <= displayed_index < n):
        return {"graded": False, "reason": "displayed_index out of range for this presentation"}
    pid = presentation_id(item["id"], attempt_seed)
    if expected_presentation_id is not None and expected_presentation_id != pid:
        return {"graded": False, "reason": "presentation_id mismatch: submission was rendered "
                "under a different attempt seed than it is being graded under"}
    canonical = displayed_to_canonical(item["id"], attempt_seed, displayed_index, n)
    result = quiz.grade(item, keys, canonical)
    result["displayed_index"] = displayed_index
    result["canonical_index"] = canonical
    result["presentation_id"] = pid
    return result
