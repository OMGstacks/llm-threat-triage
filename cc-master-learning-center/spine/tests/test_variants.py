"""Semantic variant tests — the PR-10.4a acceptance gates.

Proves the validator ACCEPTS a well-formed, grounded, semantically-locked variant and REJECTS the
bad-variant cases the reviewer enumerated: changed objective, changed bank, changed correct concept,
missing expected keyword, unresolved misconception_id, holdout source, too-similar stem, and an
unsupported new claim — plus the independent-review regressions: a lock keyword landing on the WRONG
choice (F1), authoring text leaking into the learner render (F2), the misconception-drift check being
skipped without source targets (F3), and an unknown smuggle field (F6). Synthetic variants only.
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cc_spine import factstore, presentation, quiz, variants as V

STORE = factstore.FactStore()
REGISTRY = quiz._load_registry()
GOLD = {i["id"]: i for i in quiz.load_goldset()}
HOLDOUT = {i["id"]: i for i in quiz.load_holdout()}
KEYS = {k["item_id"]: k for k in quiz.load_answer_keys()}

SOURCE = GOLD["D1.1.4.scenario.0001"]          # objective 1.4, scenario_application
SOURCE_KEY = KEYS["D1.1.4.scenario.0001"]      # its isolated key (targets canon-priority-...)


def _valid_variant() -> dict:
    """A well-formed variant of SOURCE: reworded stem + choices; the keyed-correct choice (index 2)
    uniquely carries the grounded lock keyword 'takes precedence over'."""
    return {
        "variant_id": "D1.1.4.scenario.0001.v001",
        "source_item_id": "D1.1.4.scenario.0001",
        "objective": "1.4",
        "bank": "scenario_application",
        "fact_ids": ["D1.14-canon-priority"],
        "expected_keywords": ["takes precedence over"],
        "misconception_ids": ["canon-priority-principal-over-society"],
        "semantic_lock": {
            "must_test": "Canon 1 (protect society) outranks Canon 3 (serve principals) in a conflict.",
            "correct_concept": "protect society first",
            "must_include_keywords": ["takes precedence over"],
            "must_not_change": ["objective", "bank", "fact_ids", "misconception_ids"],
        },
        "stem_variant": ("A company orders an analyst to hide a safety-critical defect from its "
                         "customers. Under the ISC2 Code of Ethics, which response is required?"),
        "choices_variant": [
            "Obey the order, since duty to the employer outranks any other obligation.",
            "Do nothing, because the canons carry equal force and cannot break the tie.",
            "Report it and protect the public, because Canon 1 takes precedence over duty to the employer.",
            "Obey, because any lawful instruction from an employer automatically satisfies the Code.",
        ],
        "status": "validated",
        "source": "synthetic_test",
    }


def _valid_key() -> dict:
    return {"variant_id": "D1.1.4.scenario.0001.v001", "correct_index": 2,
            "rationale_refs": ["D1.14-canon-priority"]}


def _validate(v, key=None, source=SOURCE, source_key=SOURCE_KEY):
    return V.validate_variant(v, key or _valid_key(), source, source_key, STORE, REGISTRY)


class ValidVariantTest(unittest.TestCase):
    def test_wellformed_variant_passes_all_gates(self):
        self.assertEqual(_validate(_valid_variant()), [])


class DriftRejectionTest(unittest.TestCase):
    def test_changed_objective_fails_with_drift_message(self):     # gate 3 (F7: specific message)
        v = _valid_variant(); v["objective"] = "1.1"
        self.assertTrue(any("objective" in p and "drifts from source" in p for p in _validate(v)))

    def test_changed_bank_fails_with_drift_message(self):
        v = _valid_variant(); v["bank"] = "definition_recall"
        self.assertTrue(any("bank" in p and "drifts from source" in p for p in _validate(v)))

    def test_fact_ids_not_subset_of_source_fails(self):            # gate 4
        v = _valid_variant(); v["fact_ids"] = ["D1.14-canon-priority", "D9.99-not-a-source-fact"]
        self.assertTrue(any("introduce a claim not in the source" in p for p in _validate(v)))

    def test_misconception_target_drift_fails(self):               # gate 13
        v = _valid_variant(); v["misconception_ids"] = ["cia-property-confusion"]
        self.assertTrue(any("misconception target drifts" in p for p in _validate(v)))


class SemanticRejectionTest(unittest.TestCase):
    def test_keyword_on_wrong_choice_is_rejected(self):            # review F1 (soundness)
        # the key marks choice 2 correct, but the lock keyword is moved to choice 0 only.
        v = _valid_variant()
        v["choices_variant"][2] = "Report it and protect the public, as Canon 1 outranks the employer."
        v["choices_variant"][0] = "Obey; the employer directive takes precedence over public safety."
        problems = _validate(v)
        self.assertTrue(any("keyed-correct choice does not contain" in p for p in problems))

    def test_second_choice_satisfying_lock_is_rejected(self):      # review F1 (no second answer)
        v = _valid_variant()
        v["choices_variant"][0] = "Obey; the employer directive takes precedence over public safety."
        # now BOTH choice 0 and choice 2 contain the lock keyword
        self.assertTrue(any("also satisfy the lock" in p for p in _validate(v)))

    def test_correct_concept_bare_letter_is_rejected(self):        # review F5
        v = _valid_variant(); v["semantic_lock"]["correct_concept"] = "C"
        self.assertTrue(any("bare letter/index" in p for p in _validate(v)))

    def test_correct_concept_bare_letter_E_is_rejected(self):      # review N4 (5-6 choice items)
        v = _valid_variant(); v["semantic_lock"]["correct_concept"] = "E"
        self.assertTrue(any("bare letter/index" in p for p in _validate(v)))

    def test_key_rationale_refs_must_be_subset_of_fact_ids(self):  # review N2
        key = _valid_key(); key["rationale_refs"] = ["D9.99-unrelated-card"]
        self.assertTrue(any("rationale_refs must be a subset" in p for p in _validate(_valid_variant(), key=key)))

    def test_missing_expected_keyword_support_fails(self):         # gate 5
        v = _valid_variant()
        v["expected_keywords"] = ["takes precedence over", "quantum uncertainty principle"]
        self.assertTrue(any("not supported by any cited fact card" in p for p in _validate(v)))

    def test_unsupported_new_claim_fails(self):
        v = _valid_variant()
        v["expected_keywords"] = ["encryption at rest is mandatory"]
        v["semantic_lock"]["must_include_keywords"] = ["encryption at rest is mandatory"]
        v["choices_variant"][2] = "Choose the option that says encryption at rest is mandatory here."
        self.assertTrue(any("not supported" in p for p in _validate(v)))

    def test_must_include_not_subset_of_expected_fails(self):
        v = _valid_variant()
        v["semantic_lock"]["must_include_keywords"] = ["Canon 1"]
        v["choices_variant"][2] = "Report it because Canon 1 protects the public above the employer."
        self.assertTrue(any("subset of expected_keywords" in p for p in _validate(v)))


class RegistryRejectionTest(unittest.TestCase):
    def test_unresolved_misconception_id_fails(self):              # gate 6
        v = _valid_variant(); v["misconception_ids"] = ["totally-made-up-misconception"]
        self.assertTrue(any("not in the registry" in p for p in _validate(v)))

    def test_misconception_wrong_objective_fails(self):
        wrong = next((mid for mid, e in REGISTRY.items()
                      if e.get("objective") not in ("1.4", "global", None)), None)
        self.assertIsNotNone(wrong)
        v = _valid_variant(); v["misconception_ids"] = [wrong]
        self.assertTrue(any("targets objective" in p for p in _validate(v)))


class SourceRejectionTest(unittest.TestCase):
    def test_unresolved_source_item_fails(self):                   # gate 1
        self.assertTrue(any("does not resolve" in p for p in _validate(_valid_variant(), source=None)))

    def test_holdout_source_is_rejected(self):                     # gate 2
        holdout_item = next(iter(HOLDOUT.values()))
        v = _valid_variant(); v["source_item_id"] = holdout_item["id"]
        problems = V.validate_variant(v, _valid_key(), holdout_item, SOURCE_KEY, STORE, REGISTRY)
        self.assertTrue(any("HOLDOUT" in p for p in problems))

    def test_missing_source_key_fails_closed_on_drift(self):       # review F3
        problems = V.validate_variant(_valid_variant(), _valid_key(), SOURCE, None, STORE, REGISTRY)
        self.assertTrue(any("cannot verify misconception drift" in p for p in problems))


class SimilarityTest(unittest.TestCase):
    def test_too_similar_stem_fails(self):                         # gate 12
        v = _valid_variant(); v["stem_variant"] = SOURCE["stem"]
        self.assertTrue(any("near-duplicate" in p for p in _validate(v)))

    def test_reworded_stem_passes_similarity(self):
        self.assertEqual(V.similarity_problems(_valid_variant(), SOURCE), [])


class ClosedObjectTest(unittest.TestCase):
    def test_variant_storing_correct_index_fails(self):            # gate 11
        v = _valid_variant(); v["correct_index"] = 2
        self.assertTrue(any("disallowed field 'correct_index'" in p for p in _validate(v)))

    def test_unknown_smuggle_field_is_rejected(self):              # review F6 (allowlist, not denylist)
        v = _valid_variant(); v["solution"] = "the answer is TCP"
        self.assertTrue(any("disallowed field 'solution'" in p for p in _validate(v)))

    def test_unknown_lock_field_is_rejected(self):
        v = _valid_variant(); v["semantic_lock"]["answer"] = "protect society"
        self.assertTrue(any("disallowed field 'answer' in semantic_lock" in p for p in _validate(v)))


class EligibilityTest(unittest.TestCase):
    def test_draft_variant_is_not_practice_eligible(self):         # gate 8
        v = _valid_variant(); v["status"] = "draft"
        self.assertFalse(V.is_practice_eligible(v))

    def test_bare_validated_is_not_practice_eligible(self):        # review F4
        v = _valid_variant(); v["status"] = "validated"
        self.assertFalse(V.is_practice_eligible(v))

    def test_reviewed_without_metadata_is_not_eligible(self):      # gate 9
        v = _valid_variant(); v["status"] = "reviewed"
        self.assertFalse(V.is_practice_eligible(v))
        self.assertTrue(any("reviewed_by" in p for p in _validate(v)))

    def test_reviewed_with_metadata_is_eligible(self):
        v = _valid_variant()
        v["status"] = "reviewed"; v["reviewed_by"] = "reviewer-a"; v["last_reviewed"] = "2026-07-05"
        self.assertTrue(V.is_practice_eligible(v))
        self.assertEqual(_validate(v), [])

    def test_readiness_weight_must_be_zero(self):
        v = _valid_variant(); v["readiness_weight"] = 1
        self.assertTrue(any("readiness_weight" in p for p in _validate(v)))


class PresentationTest(unittest.TestCase):
    def test_variant_renders_through_presentation_layer_no_field_leak(self):   # gate 10
        r = V.render_variant(_valid_variant(), SOURCE, "attempt-1")
        self.assertIn("presentation_id", r)
        self.assertEqual(sorted(r["choices"]), sorted(_valid_variant()["choices_variant"]))
        blob = json.dumps(r)
        for forbidden in ("correct_index", "answer", "correct", "rationale_refs", "choice_order"):
            self.assertNotIn(f'"{forbidden}"', blob)

    def test_render_does_not_leak_must_test_or_correct_concept(self):          # review F2
        v = _valid_variant()
        r = V.render_variant(v, SOURCE, "attempt-1")
        blob = json.dumps(r)
        self.assertNotIn(v["semantic_lock"]["must_test"], blob)
        self.assertNotIn(v["semantic_lock"]["correct_concept"], blob)
        # the neutral SOURCE topic is what surfaces
        self.assertEqual(r["topic"], SOURCE["topic"])

    def test_variant_grading_maps_display_to_canonical(self):                  # carry-forward 3
        v, key = _valid_variant(), _valid_key()
        seed, n = "attempt-grade", len(v["choices_variant"])
        canon = key["correct_index"]
        disp = presentation.presentation_order(v["variant_id"], seed, n).index(canon)
        self.assertTrue(V.grade_variant(v, key, SOURCE, seed, disp)["correct"])
        wrong = next(d for d in range(n) if d != disp)
        self.assertFalse(V.grade_variant(v, key, SOURCE, seed, wrong)["correct"])

    def test_variant_grading_uses_the_key_not_the_keyword(self):               # review F1 (grading)
        # move the keyword onto a distractor; grading must still key off variant_key.correct_index,
        # not the keyword — so the keyed choice grades correct regardless of where the keyword sits.
        v, key = _valid_variant(), _valid_key()
        v["choices_variant"][0] = "Obey; the directive takes precedence over public safety."
        seed, n = "s", len(v["choices_variant"])
        disp_keyed = presentation.presentation_order(v["variant_id"], seed, n).index(key["correct_index"])
        self.assertTrue(V.grade_variant(v, key, SOURCE, seed, disp_keyed)["correct"])

    def test_variant_grading_rejects_presentation_id_mismatch(self):
        v, key = _valid_variant(), _valid_key()
        pid = presentation.presentation_id(v["variant_id"], "render-seed")
        res = V.grade_variant(v, key, SOURCE, "other-seed", 0, expected_presentation_id=pid)
        self.assertFalse(res["graded"])


class LineageTest(unittest.TestCase):
    def test_lineage_is_traceable_and_content_free(self):
        lin = V.variant_lineage(_valid_variant())
        self.assertEqual(lin["source_item_id"], "D1.1.4.scenario.0001")
        self.assertEqual(lin["readiness_weight"], 0)
        self.assertTrue(lin["semantic_lock_hash"].startswith("sha256:"))
        blob = json.dumps(lin)
        for forbidden in ("stem", "choices", "correct"):
            self.assertNotIn(forbidden, blob)

    def test_semantic_lock_hash_changes_on_drift(self):
        base = V.semantic_lock_hash(_valid_variant())
        v = _valid_variant(); v["objective"] = "1.1"
        self.assertNotEqual(base, V.semantic_lock_hash(v))


if __name__ == "__main__":
    unittest.main()
