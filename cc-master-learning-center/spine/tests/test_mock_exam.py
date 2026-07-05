"""Mock-exam assembler tests — the PR-10 acceptance gates.

Proves the assembler is deterministic and policy-conformant, that scenarios are holdout-only,
that a burned holdout id is excluded, that the learner view carries no answers, and that a
graded mock produces fresh-scenario accuracy without leaking holdout content into practice.
"""

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cc_spine import cli
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
        views = mx.render_mock(mx.assemble("k", count=15))["items"]
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


class ExposureReceiptTest(unittest.TestCase):
    """PR-10.2: the SANCTIONED public render path emits a content-free exposure receipt so
    burn-on-exposure is surfaced, not silently skipped, by a future UI/dashboard."""

    def test_render_mock_bundles_items_and_receipt(self):
        bundle = mx.render_mock(mx.assemble("k", count=15))
        # render_mock is the sanctioned public render: it always returns items AND their receipt.
        self.assertEqual(set(bundle), {"items", "exposure_receipt"})
        self.assertTrue(bundle["items"])
        self.assertEqual(bundle["exposure_receipt"]["burn_required"], True)

    def test_raw_projection_is_private_no_public_unguarded_render(self):
        # review F1/F2: the only public way to render mock items must carry the receipt. The raw
        # projection that renders items WITHOUT a receipt is private (underscore), so a caller
        # reaching for the module's public surface cannot get items without the burn obligation.
        self.assertFalse(hasattr(mx, "mock_learner_view"),
                          "the receipt-less render must not be a public entry point")
        self.assertTrue(hasattr(mx, "render_mock"))
        # every public path that yields items carries a receipt.
        self.assertIn("exposure_receipt", mx.render_mock(mx.assemble("k", count=15)))

    def test_mock_render_items_match_exposure_receipt(self):
        mock = mx.assemble("k", count=15)
        bundle = mx.render_mock(mock)
        receipt = bundle["exposure_receipt"]
        rendered_ids = {v["id"] for v in bundle["items"]}
        # every exposed holdout id in the receipt is actually rendered to the learner...
        self.assertTrue(set(receipt["exposed_holdout_ids"]) <= rendered_ids)
        # ...and the exposed set is exactly the mock's holdout-lane ids (independent oracle).
        holdout_ids = sorted(e["item_id"] for e in mock["items"] if e["lane"] == "holdout")
        self.assertEqual(receipt["exposed_holdout_ids"], holdout_ids)
        self.assertEqual(receipt["holdout_exposure_count"], len(holdout_ids))
        self.assertEqual(receipt["item_count"], len(mock["items"]))
        self.assertEqual(receipt["draw_key"], "k")

    def test_receipt_burn_set_equals_exposed_holdout_ids(self):
        mock = mx.assemble("k", count=15)
        # independent oracle: recompute the expected burn set straight from the mock items,
        # NOT by calling exposed_holdout_ids again (review F3 — avoid a tautological assertion).
        expected = sorted(e["item_id"] for e in mock["items"] if e["lane"] == "holdout")
        receipt = mx.mock_exposure_receipt(mock)
        self.assertEqual(receipt["exposed_holdout_ids"], expected)
        self.assertEqual(mx.exposed_holdout_ids(mock), expected)
        # and the burn set grade_mock records, regardless of submissions, is the same oracle.
        g = mx.grade_mock(mock, submissions={})
        self.assertEqual(g["burned_holdout_ids"], expected)
        self.assertEqual(receipt["burn_required"], bool(expected))

    def test_receipt_contains_no_holdout_stems_or_answers(self):
        mock = mx.assemble("k", count=15)
        blob = json.dumps(mx.mock_exposure_receipt(mock))
        for hid, item in HOLDOUT.items():
            self.assertNotIn(item["stem"], blob, hid)
            for choice in item["choices"]:
                self.assertNotIn(choice, blob, hid)
        for forbidden in ("correct_index", "answer_key_ref", "rationale_refs",
                          "item_hash", "stem", "choices"):
            self.assertNotIn(f'"{forbidden}"', blob)

    def test_cli_mock_assemble_or_export_prints_receipt_or_warns(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cli.main(["mock", "render", "--draw-key", "k", "--count", "15"])
        self.assertEqual(rc, 0)
        receipt = json.loads(out.getvalue())          # stdout is the content-free receipt
        self.assertIn("exposed_holdout_ids", receipt)
        self.assertTrue(receipt["burn_required"])
        self.assertIn("burn-on-exposure", err.getvalue())   # stderr carries the burn obligation
        # the CLI receipt itself must leak no holdout content
        for item in HOLDOUT.values():
            self.assertNotIn(item["stem"], out.getvalue())


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
