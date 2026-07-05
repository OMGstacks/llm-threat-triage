"""Presentation-randomization tests — the PR-10.3 acceptance gates.

Proves render-time choice shuffling is deterministic in the attempt seed, that the canonical
goldset is never mutated, that the learner render carries no answer/choice-order secret, that the
grader maps a displayed index back to the canonical index correctly, and that the correct answer is
not consistently pinned to one letter across attempts. Holdout items use the same machinery.
"""

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cc_spine import cli
from cc_spine import presentation as pz
from cc_spine import quiz

PRACTICE = quiz.load_goldset()
HOLDOUT = quiz.load_holdout()
PKEYS = quiz.load_answer_keys()
HKEYS = quiz.load_holdout_keys()
FORBIDDEN = ("correct_index", "correct", "answer", "rationale_refs", "rationales",
             "distractor_misconceptions", "answer_key_hash", "answer_key_ref",
             "fact_ids", "expected_keywords", "choice_order", "misconception_tags")

# a multi-choice practice item and a holdout item to drive the gates
ITEM = next(it for it in PRACTICE if len(it["choices"]) >= 3)
HITEM = next(it for it in HOLDOUT if len(it["choices"]) >= 3)


def _correct_index(item, keys):
    key = quiz._keys_by_ref(keys).get(item["answer_key_ref"])
    return key["correct_index"]


class DeterminismTest(unittest.TestCase):
    def test_same_item_same_seed_gives_identical_order(self):        # gate 1
        a = pz.presentation_order(ITEM["id"], "seed-A", len(ITEM["choices"]))
        b = pz.presentation_order(ITEM["id"], "seed-A", len(ITEM["choices"]))
        self.assertEqual(a, b)
        # a full render is identical too
        self.assertEqual(pz.render_item(ITEM, "seed-A"), pz.render_item(ITEM, "seed-A"))

    def test_order_is_a_valid_permutation(self):
        n = len(ITEM["choices"])
        self.assertEqual(sorted(pz.presentation_order(ITEM["id"], "s", n)), list(range(n)))

    def test_different_seed_varies_order_when_possible(self):        # gate 2
        n = len(ITEM["choices"])
        orders = {tuple(pz.presentation_order(ITEM["id"], f"seed-{i}", n)) for i in range(24)}
        self.assertGreater(len(orders), 1, "distinct seeds should yield more than one order")


class CanonicalStabilityTest(unittest.TestCase):
    def test_render_does_not_mutate_canonical_goldset(self):         # gate 8 (part)
        before = json.dumps(ITEM, sort_keys=True)
        pz.render_item(ITEM, "seed-A")
        pz.render_quiz(PRACTICE, "seed-A")
        self.assertEqual(json.dumps(ITEM, sort_keys=True), before)

    def test_item_hash_pins_canonical_not_presentation(self):        # gate 8
        # the shuffled render's choices differ from canonical for at least one seed, yet item_hash
        # (computed over canonical content) is unchanged — presentation never feeds the drift pin.
        h = quiz.item_hash(ITEM)
        self.assertEqual(h, quiz.item_hash(ITEM))          # stable
        rendered = pz.render_item(ITEM, "seed-A")["choices"]
        # find a seed whose order actually reorders, then confirm item_hash still matches canonical
        n = len(ITEM["choices"])
        seed = next(s for s in (f"s{i}" for i in range(50))
                    if pz.presentation_order(ITEM["id"], s, n) != list(range(n)))
        self.assertNotEqual(pz.render_item(ITEM, seed)["choices"], ITEM["choices"])
        self.assertEqual(quiz.item_hash(ITEM), h)


class LearnerLeakTest(unittest.TestCase):
    def test_render_carries_no_answer_or_order_secret(self):         # gates 3, 6
        blob = json.dumps(pz.render_quiz(PRACTICE, "seed-A"))
        for forbidden in FORBIDDEN:
            self.assertNotIn(f'"{forbidden}"', blob)

    def test_render_shape_is_learner_safe(self):
        r = pz.render_item(ITEM, "seed-A")
        self.assertIn("presentation_id", r)
        self.assertEqual(r["choice_count"], len(ITEM["choices"]))
        self.assertEqual(len(r["choices"]), len(ITEM["choices"]))
        # every rendered choice is one of the canonical choices (reorder, not rewrite)
        self.assertEqual(sorted(r["choices"]), sorted(ITEM["choices"]))


class GradingTest(unittest.TestCase):
    def test_displayed_index_maps_back_to_canonical(self):           # gate 4
        seed = "seed-grade"
        n = len(ITEM["choices"])
        order = pz.presentation_order(ITEM["id"], seed, n)
        canon = _correct_index(ITEM, PKEYS)
        displayed_correct = order.index(canon)     # where the correct choice now sits
        good = pz.grade_presented(ITEM, PKEYS, seed, displayed_correct)
        self.assertTrue(good["correct"])
        self.assertEqual(good["canonical_index"], canon)
        # any other displayed position grades wrong
        wrong_display = next(d for d in range(n) if d != displayed_correct)
        bad = pz.grade_presented(ITEM, PKEYS, seed, wrong_display)
        self.assertFalse(bad["correct"])

    def test_grader_does_not_assume_display_equals_canonical(self):
        # pick a seed where the correct answer is NOT at its canonical position, then submitting
        # the canonical index (as if display==canonical) must grade WRONG.
        canon = _correct_index(ITEM, PKEYS)
        n = len(ITEM["choices"])
        seed = next(s for s in (f"g{i}" for i in range(100))
                    if pz.presentation_order(ITEM["id"], s, n).index(canon) != canon)
        res = pz.grade_presented(ITEM, PKEYS, seed, canon)
        # submitting the canonical index at that seed lands on a different canonical choice
        self.assertEqual(res["canonical_index"], pz.presentation_order(ITEM["id"], seed, n)[canon])
        self.assertNotEqual(res["canonical_index"], canon)

    def test_out_of_range_display_is_rejected(self):
        res = pz.grade_presented(ITEM, PKEYS, "s", len(ITEM["choices"]))
        self.assertFalse(res["graded"])
        self.assertFalse(pz.grade_presented(ITEM, PKEYS, "s", -1)["graded"])

    def test_bool_and_non_int_display_are_rejected(self):     # review F1
        # bool is an int subclass; True/False must NOT be coerced to indices 1/0 by a governed grader.
        for bad in (True, False, 1.0, "1", None):
            res = pz.grade_presented(ITEM, PKEYS, "s", bad)
            self.assertFalse(res["graded"], f"{bad!r} must be rejected")

    def test_presentation_id_mismatch_is_rejected(self):      # review F5
        seed = "render-seed"
        n = len(ITEM["choices"])
        canon = _correct_index(ITEM, PKEYS)
        disp = pz.presentation_order(ITEM["id"], seed, n).index(canon)
        rendered_pid = pz.presentation_id(ITEM["id"], seed)
        # grading under the SAME seed with the matching pid succeeds...
        ok = pz.grade_presented(ITEM, PKEYS, seed, disp, expected_presentation_id=rendered_pid)
        self.assertTrue(ok["correct"])
        # ...but grading under a DIFFERENT seed while claiming the rendered pid is rejected (a
        # seed mix-up must fail closed, not silently map through the wrong permutation).
        bad = pz.grade_presented(ITEM, PKEYS, "other-seed", disp, expected_presentation_id=rendered_pid)
        self.assertFalse(bad["graded"])
        self.assertIn("presentation_id mismatch", bad["reason"])


class AntiMemorizationTest(unittest.TestCase):
    def test_correct_answer_not_pinned_to_one_letter(self):          # gate 7 (strengthened, F3)
        # Over many seeds and across several items, the correct answer must land in EVERY display
        # slot and no single slot may dominate — a far stronger check than ">1 distinct slot".
        from collections import Counter
        trials = 200
        multi = [it for it in PRACTICE if len(it["choices"]) >= 3][:6]
        self.assertTrue(multi, "need multi-choice items to test")
        for it in multi:
            n = len(it["choices"])
            canon = _correct_index(it, PKEYS)
            slots = Counter(pz.presentation_order(it["id"], f"seed-{i}", n).index(canon)
                            for i in range(trials))
            self.assertEqual(set(slots), set(range(n)),
                             f"{it['id']}: correct answer never reached some slot")
            top_share = max(slots.values()) / trials
            self.assertLess(top_share, 0.6,
                            f"{it['id']}: correct answer concentrated in one slot ({top_share:.0%})")


class HoldoutTest(unittest.TestCase):
    def test_holdout_render_uses_same_machinery_without_leaking(self):   # gate 9
        r = pz.render_item(HITEM, "seed-H")
        self.assertEqual(sorted(r["choices"]), sorted(HITEM["choices"]))
        blob = json.dumps(r)
        for forbidden in FORBIDDEN:
            self.assertNotIn(f'"{forbidden}"', blob)
        # and grading a holdout presentation still maps correctly
        seed, n = "seed-H", len(HITEM["choices"])
        canon = _correct_index(HITEM, HKEYS)
        disp = pz.presentation_order(HITEM["id"], seed, n).index(canon)
        self.assertTrue(pz.grade_presented(HITEM, HKEYS, seed, disp)["correct"])


class CliRenderTest(unittest.TestCase):
    def test_cli_render_emits_shuffled_learner_quiz_without_answers(self):   # gates 3, 5, 6
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cli.main(["quiz", "render", "--attempt-seed", "cli-seed"])
        self.assertEqual(rc, 0)
        rendered = json.loads(out.getvalue())
        self.assertEqual(len(rendered), len(PRACTICE))
        for forbidden in FORBIDDEN:
            self.assertNotIn(f'"{forbidden}"', out.getvalue())

    def test_cli_render_requires_a_seed(self):      # review F2 — no fixed default seed
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            rc = cli.main(["quiz", "render"])
        self.assertEqual(rc, 2)
        self.assertIn("--attempt-seed", err.getvalue())


if __name__ == "__main__":
    unittest.main()
