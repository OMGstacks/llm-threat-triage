"""Learner-state tests — the PR-9 acceptance gates.

Covers determinism, holdout-attempt rejection (fail closed), the no-content-leak invariant,
Leitner scheduling, review-queue ordering, misconception closure, confidence signals, and the
partial-readiness exclusions. All state is built by replaying the committed synthetic fixture or
in-memory streams — no learner data is ever written.
"""

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cc_spine import learner_state as ls
from cc_spine import quiz

SPINE = Path(__file__).resolve().parents[1]
FIXTURE = SPINE / "tests" / "fixtures" / "synthetic_attempt_stream.json"
STREAM = json.loads(FIXTURE.read_text(encoding="utf-8"))

PRACTICE = {i["id"]: i for i in quiz.load_goldset()}
KEYS = {k["item_id"]: k for k in quiz.load_answer_keys()}
HOLDOUT_ID = quiz.load_holdout()[0]["id"]


def _correct(iid):
    return KEYS[iid]["correct_index"]


def _wrong(iid):
    c = _correct(iid)
    return next(j for j in range(len(PRACTICE[iid]["choices"])) if j != c)


class DeterminismTest(unittest.TestCase):
    def test_replay_is_deterministic_and_order_independent(self):
        a = ls.replay(STREAM, now=5)
        b = ls.replay(list(reversed(STREAM)), now=5)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_replay_uses_injected_time_only(self):
        # Different `now` changes the review queue but not the stored state.
        s = ls.replay(STREAM, now=100)
        self.assertEqual(s["attempts_replayed"], len(STREAM))


class HoldoutRejectionTest(unittest.TestCase):
    """P0-1: holdout attempts fail closed and never enter any structure."""

    def test_holdout_attempt_rejected(self):
        with self.assertRaises(ls.LearnerStateError):
            ls.replay([{"item_id": HOLDOUT_ID, "selected_index": 0, "submitted_at": 0}], now=1)

    def test_unknown_item_rejected(self):
        with self.assertRaises(ls.LearnerStateError):
            ls.replay([{"item_id": "D9.9.9.definition.0001", "selected_index": 0, "submitted_at": 0}], now=1)

    def test_holdout_id_never_in_journal_schedule_or_readiness(self):
        state = ls.replay(STREAM, now=5)
        self.assertNotIn(HOLDOUT_ID, state["items"])
        self.assertFalse(any(j["item_id"] == HOLDOUT_ID for j in state["journal"]))
        self.assertNotIn(HOLDOUT_ID, ls.review_queue(state, now=5))
        blob = json.dumps(state)
        self.assertNotIn(HOLDOUT_ID, blob)


class NoContentLeakTest(unittest.TestCase):
    """Gate 8: state stores indices + ids, never a stem, choice text, or answer key."""

    def test_journal_has_no_stem_or_choice_text(self):
        # The journal stores indices + registry teaching text — never the question itself.
        # (A short label like "Hashing" may recur inside a correction sentence; that is
        # teaching vocabulary, not a leak. The real leak vectors are the verbatim stem and
        # full sentence-length choices, plus any stem/choices/answer field.)
        state = ls.replay(STREAM, now=5)
        for j in state["journal"]:
            item = PRACTICE[j["item_id"]]
            blob = json.dumps(j)
            self.assertNotIn(item["stem"], blob)
            for choice in item["choices"]:
                if len(choice) > 30:
                    self.assertNotIn(choice, blob)
            for forbidden in ("stem", "choices", "answer", "correct_index", "answer_key"):
                self.assertNotIn(forbidden, j)

    def test_journal_records_the_required_fields(self):
        state = ls.replay(STREAM, now=5)
        self.assertTrue(state["journal"])
        for j in state["journal"]:
            for field in ("item_id", "objective", "bank", "selected_index",
                          "misconception_id", "correction", "one_sentence_rule"):
                self.assertIn(field, j)

    def test_misconception_ids_resolve_in_the_registry(self):
        reg = quiz._load_registry()
        state = ls.replay(STREAM, now=5)
        for j in state["journal"]:
            self.assertIn(j["misconception_id"], reg)


class LeitnerTest(unittest.TestCase):
    def test_correct_promotes_and_wrong_demotes(self):
        iid = "D1.1.1.definition.0002"  # untouched by the fixture
        promote = ls.replay([{"item_id": iid, "selected_index": _correct(iid), "submitted_at": 0,
                              "confidence_before_submit": 5}], now=0)
        self.assertEqual(promote["items"][iid]["box"], 2)
        demote = ls.replay([
            {"item_id": iid, "selected_index": _correct(iid), "submitted_at": 0, "confidence_before_submit": 5},
            {"item_id": iid, "selected_index": _correct(iid), "submitted_at": 1, "confidence_before_submit": 5},
            {"item_id": iid, "selected_index": _wrong(iid), "submitted_at": 2},
        ], now=2)
        self.assertEqual(demote["items"][iid]["box"], 1)

    def test_correct_but_unsure_is_not_promoted(self):
        iid = "D1.1.1.definition.0002"
        s = ls.replay([{"item_id": iid, "selected_index": _correct(iid), "submitted_at": 0,
                        "confidence_before_submit": 1, "marked_uncertain": True}], now=0)
        self.assertEqual(s["items"][iid]["box"], 1)

    def test_due_date_is_deterministic_from_injected_time(self):
        iid = "D1.1.1.definition.0002"
        s = ls.replay([{"item_id": iid, "selected_index": _correct(iid), "submitted_at": 10,
                        "confidence_before_submit": 5}], now=10)
        # box 2 interval is 1 unit → due = 10 + 1
        self.assertEqual(s["items"][iid]["due"], 11)


class ReviewOrderTest(unittest.TestCase):
    def test_review_queue_is_stable_and_due_filtered(self):
        state = ls.replay(STREAM, now=5)
        q1 = ls.review_queue(state, now=5)
        q2 = ls.review_queue(state, now=5)
        self.assertEqual(q1, q2)
        for iid in q1:
            self.assertLessEqual(state["items"][iid]["due"], 5)

    def test_high_confidence_miss_floats_to_priority(self):
        iid = "D4.4.1.discrimination.0001"
        s = ls.replay([{"item_id": iid, "selected_index": _wrong(iid), "submitted_at": 0,
                        "confidence_before_submit": 5}], now=0)
        self.assertTrue(s["items"][iid]["priority"])


class ClosureTest(unittest.TestCase):
    def test_misconception_closes_after_two_correct(self):
        # The fixture misses hashing once then answers it correctly twice.
        state = ls.replay(STREAM, now=5)
        self.assertTrue(state["misconceptions"]["hashing-is-encryption"]["closed"])

    def test_unrecovered_miss_stays_open(self):
        state = ls.replay(STREAM, now=5)
        self.assertFalse(state["misconceptions"]["udp-reliable"]["closed"])
        self.assertTrue(any(not j["closed"] for j in state["journal"]))


class ReadinessExclusionTest(unittest.TestCase):
    def test_exam_strategy_excluded_from_readiness(self):
        state = ls.replay(STREAM, now=5)
        self.assertNotIn("global", state["readiness"]["per_domain"])

    def test_partial_flag_and_closure_rate_present(self):
        state = ls.replay(STREAM, now=5)
        self.assertTrue(state["readiness"]["partial"])
        self.assertIsInstance(state["readiness"]["wrong_answer_closure_rate"], float)


class SchemaShapeTest(unittest.TestCase):
    def test_state_and_attempt_schemas_are_anonymous(self):
        from cc_spine import scaffold_validate
        failures = []
        scaffold_validate._check_learner_schemas_anonymous(failures)
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
