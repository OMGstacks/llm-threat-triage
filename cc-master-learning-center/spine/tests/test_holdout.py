"""Holdout-lane tests — the PR-8c acceptance gates.

Proves the physical separation invariant: the practice path never opens the holdout
files, the holdout lane passes the same item gates as the practice set, and no holdout
question leaks into the learner practice export (verbatim or as a near-duplicate stem).
"""

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cc_spine import factstore, quiz

STORE = factstore.FactStore()
PRACTICE = quiz.load_goldset()
HOLDOUT = quiz.load_holdout()
HOLDOUT_KEYS = quiz.load_holdout_keys()
LEARNER_EXPORT = [quiz.learner_view(it) for it in PRACTICE]


class HoldoutLaneValidationTest(unittest.TestCase):
    def test_holdout_lane_is_non_empty(self):
        self.assertTrue(HOLDOUT, "expected a shipped holdout lane")
        self.assertEqual(len(HOLDOUT), len(HOLDOUT_KEYS))

    def test_holdout_passes_the_same_item_gates(self):
        rep = quiz.validate_gold(STORE, HOLDOUT, HOLDOUT_KEYS)
        self.assertTrue(rep["ok"], rep["errors"])

    def test_every_holdout_item_is_flagged_holdout(self):
        for it in HOLDOUT:
            self.assertIs(it.get("holdout"), True, it.get("id"))

    def test_partition_is_clean(self):
        self.assertEqual(quiz.holdout_partition_problems(PRACTICE, HOLDOUT), [])


class PhysicalSeparationTest(unittest.TestCase):
    def test_practice_loader_never_returns_holdout_items(self):
        hold_ids = {it["id"] for it in HOLDOUT}
        practice_ids = {it["id"] for it in PRACTICE}
        self.assertEqual(hold_ids & practice_ids, set())

    def test_learner_export_contains_no_holdout_item(self):
        hold_ids = {it["id"] for it in HOLDOUT}
        self.assertEqual([e["id"] for e in LEARNER_EXPORT if e["id"] in hold_ids], [])

    def test_practice_and_holdout_are_distinct_files(self):
        self.assertNotEqual(quiz.GOLDSET_PATH, quiz.HOLDOUT_PATH)
        self.assertNotEqual(quiz.ANSWER_KEYS_PATH, quiz.HOLDOUT_KEYS_PATH)


class HoldoutLeakageTest(unittest.TestCase):
    def test_shipped_set_has_no_leakage(self):
        self.assertEqual(
            quiz.holdout_leakage_problems(LEARNER_EXPORT, HOLDOUT, HOLDOUT_KEYS), [])

    def test_holdout_stem_copied_into_practice_is_caught(self):
        # Simulate a leak: a practice item that reuses a holdout stem verbatim.
        leaked_export = copy.deepcopy(LEARNER_EXPORT)
        leaked_export[0]["stem"] = HOLDOUT[0]["stem"]
        problems = quiz.holdout_leakage_problems(leaked_export, HOLDOUT, HOLDOUT_KEYS)
        self.assertTrue(any("appears verbatim" in p or "near-duplicate" in p for p in problems))

    def test_near_duplicate_holdout_stem_is_caught(self):
        # A practice stem that paraphrases a holdout stem (high token overlap) must flag.
        leaked_export = copy.deepcopy(LEARNER_EXPORT)
        leaked_export[0]["stem"] = HOLDOUT[0]["stem"] + " Please choose one."
        problems = quiz.holdout_leakage_problems(leaked_export, HOLDOUT, HOLDOUT_KEYS)
        self.assertTrue(any("near-duplicate" in p or "appears verbatim" in p for p in problems))

    def test_holdout_answer_keys_are_isolated_from_the_item_file(self):
        # No holdout item file entry may carry an answer-bearing field.
        for it in HOLDOUT:
            for bad in quiz.FORBIDDEN_LEARNER_KEYS:
                self.assertNotIn(bad, it, f"{it['id']} leaks {bad}")


if __name__ == "__main__":
    unittest.main()
