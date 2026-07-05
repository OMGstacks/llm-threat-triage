"""Mock-exam assembler tests — the PR-10 acceptance gates.

Proves the assembler is deterministic and policy-conformant, that scenarios are holdout-only,
that a burned holdout id is excluded, that the learner view carries no answers, and that a
graded mock produces fresh-scenario accuracy without leaking holdout content into practice.
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cc_spine import mock_exam as mx
from cc_spine import quiz
from cc_spine import learner_state as ls

PRACTICE = {i["id"]: i for i in quiz.load_goldset()}
HOLDOUT = {i["id"]: i for i in quiz.load_holdout()}
PKEYS = {k["item_id"]: k for k in quiz.load_answer_keys()}
HKEYS = {k["item_id"]: k for k in quiz.load_holdout_keys()}


def _all_correct_submissions(mock):
    subs = {}
    for e in mock["items"]:
        keys = HKEYS if e["lane"] == "holdout" else PKEYS
        subs[e["item_id"]] = keys[e["item_id"]]["correct_index"]
    return subs


class AssemblyTest(unittest.TestCase):
    def test_deterministic_in_draw_key(self):
        a = mx.assemble("key-A", count=15)
        b = mx.assemble("key-A", count=15)
        self.assertEqual(a["items"], b["items"])

    def test_different_key_gives_a_different_draw(self):
        a = mx.assemble("key-A", count=15)
        b = mx.assemble("key-B", count=15)
        self.assertNotEqual(a["items"], b["items"])

    def test_conforms_to_policy(self):
        self.assertEqual(mx.validate_mock(mx.assemble("k", count=15)), [])

    def test_scenarios_are_holdout_only(self):
        for e in mx.assemble("k", count=15)["items"]:
            if e["bank"] == "scenario_application":
                self.assertEqual(e["lane"], "holdout", e["item_id"])
            else:
                self.assertEqual(e["lane"], "practice", e["item_id"])

    def test_no_duplicate_items(self):
        items = mx.assemble("k", count=15)["items"]
        ids = [e["item_id"] for e in items]
        self.assertEqual(len(ids), len(set(ids)))


class BurnTest(unittest.TestCase):
    def test_seen_holdout_is_excluded(self):
        mock = mx.assemble("k", count=15)
        burned = next(e["item_id"] for e in mock["items"] if e["lane"] == "holdout")
        again = mx.assemble("k", count=15, seen={burned})
        self.assertNotIn(burned, [e["item_id"] for e in again["items"]])

    def test_exposed_holdout_ids_are_all_assembled_holdout(self):
        mock = mx.assemble("k", count=15)
        expected = sorted(e["item_id"] for e in mock["items"] if e["lane"] == "holdout")
        self.assertEqual(mx.exposed_holdout_ids(mock), expected)

    def test_unsubmitted_holdout_scenario_is_still_burned(self):
        # PR-10 review F2: a holdout scenario assembled (and thus revealed by the learner view)
        # but never answered must STILL burn — otherwise it re-draws and re-counts as 'fresh'.
        mock = mx.assemble("k", count=15)
        holdout_ids = [e["item_id"] for e in mock["items"] if e["lane"] == "holdout"]
        self.assertTrue(holdout_ids, "fixture should assemble at least one holdout scenario")
        # Submit NOTHING — the learner opened the exam but answered no holdout item.
        g = mx.grade_mock(mock, submissions={})
        self.assertEqual(g["burned_holdout_ids"], sorted(holdout_ids))
        self.assertEqual(g["fresh_scenario_count"], 0)      # none submitted → no fresh accuracy
        self.assertIsNone(g["fresh_scenario_accuracy"])
        # The burned ids must feed a follow-up draw and exclude every exposed scenario.
        again = mx.assemble("k", count=15, seen=set(g["burned_holdout_ids"]))
        self.assertEqual(set(e["item_id"] for e in again["items"]) & set(holdout_ids), set())

    def test_burn_set_equals_exposure_even_on_partial_submission(self):
        mock = mx.assemble("k", count=15)
        holdout_ids = sorted(e["item_id"] for e in mock["items"] if e["lane"] == "holdout")
        # Answer only the FIRST holdout item; the rest stay unsubmitted but exposed.
        first = holdout_ids[0]
        subs = {first: HKEYS[first]["correct_index"]}
        g = mx.grade_mock(mock, subs)
        self.assertEqual(g["burned_holdout_ids"], holdout_ids)   # all exposed, not just answered
        self.assertEqual(g["fresh_scenario_count"], 1)


class IsolationTest(unittest.TestCase):
    def test_learner_view_carries_no_answer(self):
        views = mx.mock_learner_view(mx.assemble("k", count=15))
        blob = json.dumps(views)
        for forbidden in ("correct_index", "answer_key_ref", "rationale_refs", "item_hash"):
            self.assertNotIn(f'"{forbidden}":', blob)

    def test_export_learner_still_excludes_holdout(self):
        # PR-10 must not change the practice learner export.
        export_ids = {i["id"] for i in quiz.load_goldset()}
        self.assertEqual(export_ids & set(HOLDOUT), set())


class GradingTest(unittest.TestCase):
    def test_all_correct_yields_fresh_scenario_accuracy_one(self):
        mock = mx.assemble("k", count=15)
        g = mx.grade_mock(mock, _all_correct_submissions(mock))
        self.assertEqual(g["overall_accuracy"], 1.0)
        self.assertEqual(g["fresh_scenario_accuracy"], 1.0)
        self.assertTrue(g["burned_holdout_ids"])

    def test_grade_result_carries_no_holdout_content(self):
        mock = mx.assemble("k", count=15)
        g = mx.grade_mock(mock, _all_correct_submissions(mock))
        blob = json.dumps(g)
        for hid, item in HOLDOUT.items():
            self.assertNotIn(item["stem"], blob)


class ReadinessTest(unittest.TestCase):
    def setUp(self):
        stream = json.loads((Path(__file__).resolve().parents[1] /
                             "tests" / "fixtures" / "synthetic_attempt_stream.json").read_text())
        self.state = ls.replay(stream, now=5)

    def test_partial_readiness_is_incomplete_without_a_mock(self):
        rp = ls.readiness_report(self.state)
        self.assertFalse(rp["complete"])
        self.assertNotIn("fresh_scenario_accuracy", rp["weighted_over"])

    def test_mock_completes_the_formula(self):
        mock = mx.assemble("k", count=15)
        g = mx.grade_mock(mock, _all_correct_submissions(mock))
        rp = ls.readiness_report(self.state, mock_result=g)
        self.assertTrue(rp["complete"])
        self.assertIn("fresh_scenario_accuracy", rp["weighted_over"])

    def test_low_domain_accuracy_is_a_hard_blocker(self):
        # The fixture intentionally misses a D4 item → D4 accuracy 0% → not ready.
        rp = ls.readiness_report(self.state)
        self.assertEqual(rp["verdict"], "not-ready")
        self.assertTrue(any("domain D4" in b for b in rp["hard_blockers"]))

    def test_leakage_gate_failure_blocks_readiness(self):
        rp = ls.readiness_report(self.state, leakage_ok=False)
        self.assertTrue(any("leakage" in b for b in rp["hard_blockers"]))


if __name__ == "__main__":
    unittest.main()
