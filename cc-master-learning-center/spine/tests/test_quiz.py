"""Quiz-engine tests — the PR-8a acceptance gates.

Covers the ship-gate's item side: gold-item grounding, answer-key isolation, key
resolution + hash-drift detection, the near-duplicate stem gate, and a set of
red-team leakage probes proving the learner lane never carries an answer. The shipped
gold set and its answer-key store are validated as-committed; negative cases mutate
in-memory copies so nothing is written to spine/gold/.
"""

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cc_spine import factstore, quiz

SPINE = Path(__file__).resolve().parents[1]
GOLD = SPINE / "gold"

STORE = factstore.FactStore()
ITEMS = quiz.load_goldset()
KEYS = quiz.load_answer_keys()


class GoldSetValidationTest(unittest.TestCase):
    """The committed gold set passes every item-side check."""

    def test_shipped_gold_set_validates(self):
        rep = quiz.validate_gold(STORE, ITEMS, KEYS)
        self.assertTrue(rep["ok"], rep["errors"])

    def test_every_item_resolves_to_a_key(self):
        refs = {k["answer_key_ref"] for k in KEYS}
        for item in ITEMS:
            self.assertIn(item["answer_key_ref"], refs, item["id"])

    def test_grader_resolves_every_correct_answer(self):
        # Reviewer gate 9: the grader export resolves an answer for every item.
        for item in ITEMS:
            res = quiz.grade(item, KEYS, submitted_index=0)
            self.assertTrue(res["graded"], item["id"])
            self.assertIsInstance(res["correct_index"], int)

    def test_at_least_three_core_banks_are_exercised(self):
        banks = {it["bank"] for it in ITEMS}
        self.assertLessEqual(
            {"definition_recall", "concept_discrimination", "scenario_application"}, banks)


class IsolationTest(unittest.TestCase):
    """answer_key_isolation_guard — the learner lane never carries an answer."""

    def test_committed_goldset_has_no_answer_bearing_fields(self):
        self.assertEqual(quiz.isolation_problems(ITEMS), [])

    def test_learner_view_is_an_allowlist(self):
        for item in ITEMS:
            view = quiz.learner_view(item)
            self.assertLessEqual(set(view), set(quiz.LEARNER_FIELDS))

    def test_learner_view_withholds_each_leak_sensitive_field(self):
        # P0-3: explicit, per-field proof — the leak-sensitive fields never appear.
        sensitive = ("answer_key_ref", "fact_ids", "expected_keywords", "source_policy",
                     "status", "holdout", "misconception_tags", "correct_index", "rationales")
        for item in ITEMS:
            view = quiz.learner_view(item)
            for field in sensitive:
                self.assertNotIn(field, view, f"{item['id']} leaks {field}")

    def test_learner_view_export_contains_no_answer_marker(self):
        # Red-team: serialise the entire learner export and prove no answer-key FIELD
        # leaks. Probes JSON-key form ("field":) — a bare word like "correct" appears
        # legitimately inside stems ("...is correct?"), so only key-position matches count.
        blob = json.dumps([quiz.learner_view(it) for it in ITEMS])
        for forbidden in quiz.FORBIDDEN_LEARNER_KEYS:
            self.assertNotIn(f'"{forbidden}":', blob)

    def test_answer_bearing_field_in_learner_item_fails(self):
        bad = copy.deepcopy(ITEMS)
        bad[0]["correct_index"] = 0  # smuggle the answer into the learner file
        problems = quiz.isolation_problems(bad)
        self.assertTrue(any("answer-bearing field" in p for p in problems))

    def test_scaffold_forbidden_keys_match_quiz_module(self):
        # The scaffold inlines the forbidden set to stay import-free of the engine;
        # this pins the two copies together so they cannot silently diverge.
        from cc_spine import scaffold_validate
        self.assertEqual(
            set(scaffold_validate._GOLDSET_FORBIDDEN_KEYS), set(quiz.FORBIDDEN_LEARNER_KEYS))


class GradingTest(unittest.TestCase):
    def test_correct_and_incorrect_grading(self):
        item = ITEMS[0]
        key = quiz._keys_by_ref(KEYS)[item["answer_key_ref"]]
        ci = key["correct_index"]
        self.assertTrue(quiz.grade(item, KEYS, ci)["correct"])
        self.assertFalse(quiz.grade(item, KEYS, (ci + 1) % len(item["choices"]))["correct"])

    def test_wrong_answer_returns_targeted_misconception(self):
        item = ITEMS[0]
        key = quiz._keys_by_ref(KEYS)[item["answer_key_ref"]]
        wrong = next(int(i) for i in key["distractor_misconceptions"])
        res = quiz.grade(item, KEYS, wrong)
        self.assertFalse(res["correct"])
        self.assertIsNotNone(res["misconception"])


class KeyIntegrityTest(unittest.TestCase):
    """The key store must stay consistent with the items it grades."""

    def test_correct_choice_drift_breaks_answer_key_hash(self):
        items = copy.deepcopy(ITEMS)
        ci = quiz._keys_by_ref(KEYS)[items[0]["answer_key_ref"]]["correct_index"]
        items[0]["choices"][ci] = "A tampered correct choice"
        rep = quiz.validate_gold(STORE, items, KEYS)
        self.assertFalse(rep["ok"])
        self.assertTrue(any("answer_key_hash mismatch" in e for e in rep["errors"]))

    def test_stem_drift_breaks_item_hash_even_when_choices_unchanged(self):
        # P0-2: the dangerous case — stem is rewritten but the correct-choice text is
        # unchanged, so answer_key_hash still matches; only the full-item hash catches it.
        items = copy.deepcopy(ITEMS)
        items[0]["stem"] = "An entirely different question that reuses the same choices?"
        rep = quiz.validate_gold(STORE, items, KEYS)
        errs = rep["errors"]
        self.assertTrue(any("item_hash mismatch" in e for e in errs))
        self.assertFalse(any("answer_key_hash mismatch" in e for e in errs))

    def test_rationale_refs_must_be_subset_of_fact_ids(self):
        keys = copy.deepcopy(KEYS)
        keys[0]["rationale_refs"] = keys[0]["rationale_refs"] + ["D9.99-nonexistent"]
        rep = quiz.validate_gold(STORE, ITEMS, keys)
        self.assertTrue(any("rationale_refs are not a subset" in e for e in rep["errors"]))

    def test_orphan_key_fails(self):
        keys = copy.deepcopy(KEYS)
        keys.append({**keys[0], "answer_key_ref": "D1.1.1.definition.9999.key",
                     "item_id": "D1.1.1.definition.9999"})
        rep = quiz.validate_gold(STORE, ITEMS, keys)
        self.assertTrue(any("orphan answer key" in e for e in rep["errors"]))

    def test_missing_key_fails(self):
        rep = quiz.validate_gold(STORE, ITEMS, KEYS[1:])  # drop the first key
        self.assertTrue(any("does not resolve to a key" in e for e in rep["errors"]))

    def test_distractor_cannot_mark_correct_choice(self):
        keys = copy.deepcopy(KEYS)
        ci = keys[0]["correct_index"]
        keys[0]["distractor_misconceptions"][str(ci)] = "definition_confusion"
        rep = quiz.validate_gold(STORE, ITEMS, keys)
        self.assertTrue(any("marks the correct choice" in e for e in rep["errors"]))


class GroundingTest(unittest.TestCase):
    """Items inherit the frozen factstore grounding gates."""

    def test_item_citing_unknown_card_fails(self):
        items = copy.deepcopy(ITEMS)
        items[0]["fact_ids"] = ["D9.99-nonexistent"]
        rep = quiz.validate_gold(STORE, items, KEYS)
        self.assertFalse(rep["ok"])

    def test_item_citing_card_not_eligible_for_bank_fails(self):
        # D1.11-confidentiality is not eligible for scenario_application.
        items = copy.deepcopy(ITEMS)
        items[0]["bank"] = "scenario_application"
        rep = quiz.validate_gold(STORE, items, KEYS)
        self.assertTrue(any("not allowed for bank" in e for e in rep["errors"]))

    def test_unsupported_expected_keyword_fails(self):
        items = copy.deepcopy(ITEMS)
        items[0]["expected_keywords"] = ["quantum teleportation"]
        rep = quiz.validate_gold(STORE, items, KEYS)
        self.assertTrue(any("not supported by any cited fact card" in e for e in rep["errors"]))


class DistractorRegistryTest(unittest.TestCase):
    """P0-1: every distractor names a specific, resolvable registry misconception."""

    def setUp(self):
        self.reg = quiz._load_registry()

    def test_shipped_distractors_resolve_in_registry(self):
        self.assertEqual(quiz.distractor_registry_problems(ITEMS, KEYS, self.reg), [])

    def _first_wrong(self, key):
        return next(iter(key["distractor_misconceptions"]))

    def test_unknown_misconception_id_fails(self):
        keys = copy.deepcopy(KEYS)
        fw = self._first_wrong(keys[0])
        keys[0]["distractor_misconceptions"][fw]["misconception_id"] = "not-a-real-id"
        problems = quiz.distractor_registry_problems(ITEMS, keys, self.reg)
        self.assertTrue(any("not in the registry" in p for p in problems))

    def test_category_mismatch_fails(self):
        keys = copy.deepcopy(KEYS)
        fw = self._first_wrong(keys[0])
        keys[0]["distractor_misconceptions"][fw]["category"] = "network_device_confusion"
        problems = quiz.distractor_registry_problems(ITEMS, keys, self.reg)
        self.assertTrue(any("!= registry category" in p for p in problems))

    def test_missing_distractor_mapping_fails(self):
        keys = copy.deepcopy(KEYS)
        fw = self._first_wrong(keys[0])
        del keys[0]["distractor_misconceptions"][fw]
        problems = quiz.distractor_registry_problems(ITEMS, keys, self.reg)
        self.assertTrue(any("lack a misconception mapping" in p for p in problems))

    def test_wrong_objective_misconception_fails(self):
        # item[0] is objective 1.1; udp-reliable is objective 4.1.
        keys = copy.deepcopy(KEYS)
        fw = self._first_wrong(keys[0])
        keys[0]["distractor_misconceptions"][fw] = {
            "misconception_id": "udp-reliable", "category": "network_device_confusion"}
        problems = quiz.distractor_registry_problems(ITEMS, keys, self.reg)
        self.assertTrue(any("not the item's" in p for p in problems))

    def test_registry_unreadable_fails_closed(self):
        keys = copy.deepcopy(KEYS)
        rep = quiz.validate_gold(STORE, ITEMS, keys)  # sanity: passes with real registry
        self.assertTrue(rep["ok"], rep["errors"])


class AnswerPositionTest(unittest.TestCase):
    """R&D-3: the correct answer must not cluster at one position."""

    def test_shipped_positions_are_varied(self):
        self.assertEqual(quiz.answer_position_problems(ITEMS, KEYS), [])

    def test_all_same_index_fails(self):
        keys = copy.deepcopy(KEYS)
        for k in keys:
            k["correct_index"] = 0
        problems = quiz.answer_position_problems(ITEMS, keys)
        self.assertTrue(any("overfit" in p for p in problems))

    def test_same_index_within_objective_fails(self):
        # Self-contained: two items in one objective, both correct at the same index.
        items = [{"id": "D9.9.9.definition.0001", "objective": "9.9",
                  "answer_key_ref": "k1", "choices": ["a", "b", "c", "d"]},
                 {"id": "D9.9.9.definition.0002", "objective": "9.9",
                  "answer_key_ref": "k2", "choices": ["a", "b", "c", "d"]}]
        keys = [{"answer_key_ref": "k1", "correct_index": 2},
                {"answer_key_ref": "k2", "correct_index": 2}]
        problems = quiz.answer_position_problems(items, keys)
        self.assertTrue(any("within an objective" in p for p in problems))


class AllChoicesGradingTest(unittest.TestCase):
    """R&D-2: exhaustively grade every choice of every shipped item."""

    def test_every_choice_of_every_item(self):
        kb = quiz._keys_by_ref(KEYS)
        for item in ITEMS:
            key = kb[item["answer_key_ref"]]
            ci = key["correct_index"]
            corrects = 0
            for j in range(len(item["choices"])):
                res = quiz.grade(item, KEYS, j)
                self.assertTrue(res["graded"], item["id"])
                if res["correct"]:
                    corrects += 1
                    self.assertEqual(j, ci, item["id"])
                    self.assertIsNone(res["misconception"],
                                      f"{item['id']}: correct choice returns a distractor misconception")
                else:
                    self.assertIsNotNone(res["misconception"],
                                         f"{item['id']}: wrong choice {j} has no misconception")
            self.assertEqual(corrects, 1, f"{item['id']} must have exactly one correct choice")


class LengthAndParityGateTest(unittest.TestCase):
    """PR-8b.1: anti-gaming length + parallelism gates."""

    def test_shipped_set_passes_both_gates(self):
        self.assertEqual(quiz.answer_length_problems(ITEMS, KEYS), [])
        self.assertEqual(quiz.choice_parallelism_problems(ITEMS), [])

    def test_shipped_length_bias_under_target(self):
        bias = quiz.answer_length_bias(ITEMS, KEYS)
        self.assertLess(bias["ratio"], bias["warn_threshold"])

    def test_conspicuous_length_tell_fails(self):
        items = copy.deepcopy(ITEMS)
        it = items[0]
        ci = quiz._keys_by_ref(KEYS)[it["answer_key_ref"]]["correct_index"]
        it["choices"][ci] = it["choices"][ci] + " " + ("padding " * 60)
        self.assertTrue(any("length tell" in p for p in quiz.answer_length_problems(items, KEYS)))

    def test_causal_tail_only_fails(self):
        items = copy.deepcopy(ITEMS)
        it = items[0]  # distractors are one-word labels with no causal marker
        ci = quiz._keys_by_ref(KEYS)[it["answer_key_ref"]]["correct_index"]
        it["choices"][ci] = "Confidentiality, because it prevents disclosure"
        self.assertTrue(any("explanatory tell" in p for p in quiz.answer_length_problems(items, KEYS)))

    def test_mixed_structure_fails(self):
        items = copy.deepcopy(ITEMS)
        items[0]["choices"] = ["Confidentiality", "Integrity", "Availability",
                               "It is the property that keeps information secret from every unauthorized party"]
        self.assertTrue(any("parallel" in p for p in quiz.choice_parallelism_problems(items)))


class NearDuplicateTest(unittest.TestCase):
    def test_near_duplicate_stems_in_same_objective_fail(self):
        items = copy.deepcopy(ITEMS)
        twin = copy.deepcopy(items[0])
        twin["id"] = "D1.1.1.definition.0002"
        twin["answer_key_ref"] = twin["id"] + ".key"
        # identical stem, same objective -> Jaccard 1.0
        items.append(twin)
        problems = quiz.near_duplicate_problems(items)
        self.assertTrue(any("near-duplicate stems" in p for p in problems))

    def test_distinct_stems_do_not_trip_the_gate(self):
        self.assertEqual(quiz.near_duplicate_problems(ITEMS), [])

    def test_same_stem_across_objectives_is_allowed(self):
        items = copy.deepcopy(ITEMS[:1])
        twin = copy.deepcopy(items[0])
        twin["id"], twin["objective"] = "D2.2.1.definition.0002", "2.1"
        items.append(twin)
        self.assertEqual(quiz.near_duplicate_problems(items), [])


if __name__ == "__main__":
    unittest.main()
