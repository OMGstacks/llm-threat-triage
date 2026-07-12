"""Readiness-dashboard data-model tests — the PR-11a acceptance gates.

Proves the dashboard is a deterministic, content-free projection of a learner state (+ optional
graded mock): it composes the readiness verdict, per-domain/per-bank accuracy, the spaced-repetition
queue, the wrong-answer + misconception summaries, the mock signals, and the proof-scale content
caveat — carrying only ids/counts/accuracies/verdicts, never a stem, answer, key, or PII. The
committed sample is exactly what the code produces from the synthetic fixture (regenerable, no drift).
"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cc_spine import cli, dashboard, learner_state as ls, mock_exam as mx, quiz

FIXTURES = Path(__file__).resolve().parent / "fixtures"
STREAM = json.loads((FIXTURES / "synthetic_attempt_stream.json").read_text(encoding="utf-8"))
SAMPLE = json.loads((Path(__file__).resolve().parents[2] / "reports"
                     / "readiness-dashboard-sample.json").read_text(encoding="utf-8"))
# fields that would betray an answer or PII if they ever leaked into the dashboard
FORBIDDEN = ("stem", "choices", "correct_index", "correct", "answer", "answer_key_ref",
             "rationale_refs", "correction", "one_sentence_rule", "trap", "selected_index",
             "name", "email", "user", "username")


def _state(now=5):
    return ls.replay(STREAM, now=now)


class DeterminismTest(unittest.TestCase):
    def test_dashboard_is_deterministic(self):
        self.assertEqual(dashboard.build_dashboard(_state(), now=5),
                         dashboard.build_dashboard(_state(), now=5))

    def test_generated_at_day_is_the_injected_now_not_a_clock(self):
        self.assertEqual(dashboard.build_dashboard(_state(3), now=3)["generated_at_day"], 3)


class SampleTest(unittest.TestCase):
    def test_committed_sample_matches_regenerated(self):
        self.assertEqual(dashboard.build_dashboard(_state(5), now=5), SAMPLE)


class ContentFreeTest(unittest.TestCase):
    def test_dashboard_carries_no_answer_or_pii_field(self):
        blob = json.dumps(dashboard.build_dashboard(_state(), now=5))
        for forbidden in FORBIDDEN:
            self.assertNotIn(f'"{forbidden}"', blob)

    def test_no_stem_or_choice_text_leaks_as_a_value(self):
        # not just field NAMES (above) — no practice OR holdout stem/choice text may appear as a
        # value under any key (review claim 2: make the value-leak guarantee test-enforced).
        blob = json.dumps(dashboard.build_dashboard(_state(), now=5))
        for item in list(quiz.load_goldset()) + list(quiz.load_holdout()):
            self.assertNotIn(item["stem"], blob)
            for choice in item["choices"]:
                self.assertNotIn(choice, blob)

    def test_no_journal_teaching_text_leaks_as_a_value(self):
        # the wrong-answer journal carries correction / one_sentence_rule / trap text; the dashboard
        # must project only misconception_ids, never that free text (review claim 2).
        state = _state()
        blob = json.dumps(dashboard.build_dashboard(state, now=5))
        for j in state["journal"]:
            for field in ("correction", "one_sentence_rule", "trap"):
                if j.get(field):
                    self.assertNotIn(j[field], blob, field)


class CompositionTest(unittest.TestCase):
    def test_readiness_verdict_and_blockers_are_carried_from_readiness_report(self):
        d = dashboard.build_dashboard(_state(), now=5)
        rr = ls.readiness_report(_state())
        self.assertEqual(d["readiness"]["verdict"], rr["verdict"])
        self.assertEqual(d["readiness"]["hard_blockers"], rr["hard_blockers"])
        self.assertEqual(d["readiness"]["score"], rr["score"])

    def test_domain_and_bank_accuracy_match_state(self):
        d = dashboard.build_dashboard(_state(), now=5)
        r = _state()["readiness"]
        for dom, s in r["per_domain"].items():
            self.assertEqual(d["domain_accuracy"][dom]["attempts"], s["attempts"])
        for bank, s in r["per_bank"].items():
            self.assertEqual(d["bank_accuracy"][bank]["total"], s["total"])

    def test_spaced_repetition_counts_match_the_queue(self):
        d = dashboard.build_dashboard(_state(), now=5)
        self.assertEqual(d["spaced_repetition"]["due_now"], len(ls.review_queue(_state(), 5)))
        self.assertEqual(d["next_recommended_review"], ls.review_queue(_state(), 5)[:10])

    def test_top_misconceptions_ranked_by_miss_count(self):
        d = dashboard.build_dashboard(_state(), now=5)
        misses = [m["missed"] for m in d["top_misconceptions"]]
        self.assertEqual(misses, sorted(misses, reverse=True))

    def test_open_misconceptions_are_only_unclosed(self):
        d = dashboard.build_dashboard(_state(), now=5)
        state = _state()
        for mid in d["wrong_answers"]["open_misconceptions"]:
            self.assertFalse(state["misconceptions"][mid]["closed"], mid)


class MockCompletionTest(unittest.TestCase):
    def test_no_mock_is_incomplete_and_null(self):
        d = dashboard.build_dashboard(_state(), now=5)
        self.assertIsNone(d["mock"])
        self.assertFalse(d["readiness"]["complete"])

    def test_a_graded_mock_completes_readiness_and_populates_mock(self):
        mock = mx.assemble("dash", count=15)
        prac_keys = {k["item_id"]: k for k in quiz.load_answer_keys()}
        hold_keys = {k["item_id"]: k for k in quiz.load_holdout_keys()}
        subs = {}
        for e in mock["items"]:
            src = hold_keys if e["lane"] == "holdout" else prac_keys
            subs[e["item_id"]] = src[e["item_id"]]["correct_index"]
        graded = mx.grade_mock(mock, subs)
        d = dashboard.build_dashboard(_state(), mock_result=graded, now=5)
        self.assertIsNotNone(d["mock"])
        self.assertEqual(d["mock"]["burned_holdout_count"], len(graded["burned_holdout_ids"]))
        self.assertTrue(d["readiness"]["complete"])
        self.assertIn("fresh_scenario_accuracy", d["readiness"]["weighted_over"])


class RobustnessTest(unittest.TestCase):
    def test_non_dict_mock_is_treated_as_no_mock(self):          # review F1 (engine)
        d = dashboard.build_dashboard(_state(), mock_result=["not", "a", "dict"], now=5)
        self.assertIsNone(d["mock"])
        self.assertFalse(d["readiness"]["complete"])

    def test_cli_rejects_non_dict_mock_cleanly(self):            # review F1 (CLI)
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "mock.json"
            bad.write_text("[1, 2, 3]", encoding="utf-8")
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                rc = cli.main(["dashboard", "--attempts", str(FIXTURES / "synthetic_attempt_stream.json"),
                               "--now", "5", "--mock", str(bad)])
            self.assertEqual(rc, 1)
            self.assertIn("--mock must be", err.getvalue())


class ContentScaleTest(unittest.TestCase):
    def test_content_scale_flags_proof_scale_with_caveat(self):
        cs = dashboard.build_dashboard(_state(), now=5)["content_scale"]
        self.assertEqual(cs["status"], "proof_scale")
        self.assertIsNotNone(cs["caveat"])
        self.assertEqual(cs["practice_items"], len(quiz.load_goldset()))
        # PR-12: definition_recall growth pushed total items to/over the mock floor, yet the content
        # stays proof-scale because the fresh (holdout) scenario pool is below the scenario-draw
        # floor. Growing a single recall bank must NOT hide the caveat (false-confidence guard); the
        # caveat names the scenario shortfall.
        self.assertGreaterEqual(cs["practice_items"] + cs["holdout_scenarios"], cs["mock_target_min"])
        self.assertIn("scenario", cs["caveat"])


if __name__ == "__main__":
    unittest.main()
