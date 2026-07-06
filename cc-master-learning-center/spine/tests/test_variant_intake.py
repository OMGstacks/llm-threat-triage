"""Variant-intake tests — the PR-10.4b acceptance gates.

Proves the locked prompt builder is deterministic and leak-free, that untrusted candidate JSON is
validated fail-closed through the full attack matrix (parse gates I1-I3, derivation gate I4, intake
gates I5-I10, plus the PR-10.4a 13-gate validator), that drafts are written only to gitignored
locations with the answer-bearing key PHYSICALLY separate, and that a draft can never touch
readiness. No live API anywhere — candidates come from fixtures.
"""

import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cc_spine import cli, factstore, learner_state, quiz, variants
from cc_spine import variant_intake as vi

STORE = factstore.FactStore()
REGISTRY = quiz._load_registry()
GOLD = {i["id"]: i for i in quiz.load_goldset()}
KEYS = {k["item_id"]: k for k in quiz.load_answer_keys()}
HOLDOUT = quiz.load_holdout()

SOURCE = GOLD["D1.1.4.scenario.0001"]
SOURCE_KEY = KEYS["D1.1.4.scenario.0001"]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOOD = json.loads((FIXTURES / "variant_candidate_good.json").read_text(encoding="utf-8"))
BAD_KEYED_WRONG = json.loads(
    (FIXTURES / "variant_candidate_keyed_wrong_choice.json").read_text(encoding="utf-8"))


def _request(draw_key="demo"):
    return vi.build_variant_request(SOURCE, SOURCE_KEY, STORE, REGISTRY, draw_key)


def _validate(candidate, draw_key="demo", source=SOURCE, source_key=SOURCE_KEY):
    return vi.validate_candidate(candidate, source, source_key, STORE, REGISTRY, draw_key)


class RequestBuildTest(unittest.TestCase):
    def test_request_is_deterministic(self):
        self.assertEqual(_request(), _request())

    def test_request_refuses_holdout_source_fail_closed(self):
        holdout_item = HOLDOUT[0]
        with self.assertRaises(vi.VariantIntakeError):
            vi.build_variant_request(holdout_item, SOURCE_KEY, STORE, REGISTRY, "demo")
        # a practice-shaped item whose id is in the holdout set is also refused
        fake = dict(SOURCE, id=holdout_item["id"])
        with self.assertRaises(vi.VariantIntakeError):
            vi.build_variant_request(fake, SOURCE_KEY, STORE, REGISTRY, "demo")

    def test_request_fails_closed_on_missing_registry_correct(self):
        broken = {mid: dict(e, correct="") for mid, e in REGISTRY.items()}
        with self.assertRaises(vi.VariantIntakeError):
            vi.build_variant_request(SOURCE, SOURCE_KEY, STORE, broken, "demo")

    def test_variant_id_matches_schema_pattern_and_is_deterministic(self):
        vid = vi.variant_id_for("D1.1.4.scenario.0001", "demo")
        self.assertRegex(vid, r"^D1\.1\.4\.scenario\.0001\.v[0-9]{3}$")
        self.assertEqual(vid, vi.variant_id_for("D1.1.4.scenario.0001", "demo"))
        self.assertNotEqual(vid, vi.variant_id_for("D1.1.4.scenario.0001", "other-key"))

    def test_must_test_from_cited_card_claim(self):
        card = STORE.cards["D1.14-canon-priority"]
        self.assertEqual(_request()["must_test"], card["claim"])

    def test_correct_concept_from_registry_correct_field(self):
        expected = REGISTRY["canon-priority-principal-over-society"]["correct"]
        self.assertEqual(_request()["correct_concept"], expected)


class PromptTest(unittest.TestCase):
    def test_prompt_contains_locked_template_lines_verbatim(self):
        prompt = vi.build_variant_prompt(_request())
        for line in ("Generate a new practice-question variant.", "You must preserve:",
                     "You may change:", "You must not:",
                     "- Use real certification exam questions", "- Quote transcript text",
                     "- Use holdout content", "- Reveal answer-key metadata", "Return JSON only:"):
            self.assertIn(line, prompt)

    def test_prompt_is_byte_deterministic(self):
        self.assertEqual(vi.build_variant_prompt(_request()).encode(),
                         vi.build_variant_prompt(_request()).encode())

    def test_prompt_excludes_source_stem_and_choices(self):
        prompt = vi.build_variant_prompt(_request())
        self.assertNotIn(SOURCE["stem"], prompt)
        for choice in SOURCE["choices"]:
            self.assertNotIn(choice, prompt)

    def test_prompt_correct_concept_slot_carries_keyword_requirement(self):
        prompt = vi.build_variant_prompt(_request())
        self.assertIn('the correct choice must contain the exact phrase(s): "takes precedence over"',
                      prompt)


class ParseCandidateTest(unittest.TestCase):
    def test_good_candidate_parses(self):
        candidate, problems = vi.parse_candidate(copy.deepcopy(GOOD))
        self.assertEqual(problems, [])
        self.assertIsNotNone(candidate)

    def test_candidate_smuggle_field_rejected(self):
        for field in ("status", "source", "correct_index", "fact_ids", "solution"):
            raw = copy.deepcopy(GOOD); raw[field] = "smuggled"
            candidate, problems = vi.parse_candidate(raw)
            self.assertIsNone(candidate, field)
            self.assertTrue(any("disallowed field" in p for p in problems), field)

    def test_self_check_false_rejected(self):
        raw = copy.deepcopy(GOOD); raw["self_check"]["no_new_facts"] = False
        candidate, problems = vi.parse_candidate(raw)
        self.assertIsNone(candidate)
        self.assertTrue(any("not strictly true" in p for p in problems))

    def test_self_check_stringly_true_rejected(self):
        raw = copy.deepcopy(GOOD); raw["self_check"]["no_new_facts"] = "true"
        candidate, problems = vi.parse_candidate(raw)
        self.assertIsNone(candidate)
        self.assertTrue(any("not strictly true" in p for p in problems))

    def test_self_check_missing_key_rejected(self):
        raw = copy.deepcopy(GOOD); del raw["self_check"]["single_best_answer"]
        candidate, problems = vi.parse_candidate(raw)
        self.assertIsNone(candidate)
        self.assertTrue(any("self_check must carry exactly" in p for p in problems))

    def test_secret_in_candidate_rejected(self):
        raw = copy.deepcopy(GOOD)
        raw["stem_variant"] += " Contact admin AKIAIOSFODNN7EXAMPLE for help."
        candidate, problems = vi.parse_candidate(raw)
        self.assertIsNone(candidate)
        self.assertTrue(any("residual secret" in p for p in problems))

    def test_empty_or_duplicate_choice_rejected(self):
        raw = copy.deepcopy(GOOD); raw["choices_variant"][2] = "   "
        self.assertTrue(any("non-empty" in p for p in vi.parse_candidate(raw)[1]))
        raw = copy.deepcopy(GOOD); raw["choices_variant"][2] = raw["choices_variant"][0].upper()
        self.assertTrue(any("duplicate" in p for p in vi.parse_candidate(raw)[1]))

    def test_malformed_json_text_rejected(self):
        candidate, problems = vi.parse_candidate("{not json")
        self.assertIsNone(candidate)
        self.assertTrue(any("not valid JSON" in p for p in problems))

    def test_dict_valued_distractor_map_entry_rejected(self):        # review F1
        raw = copy.deepcopy(GOOD)
        raw["distractor_misconceptions"]["0"] = {
            "misconception_id": "canon-priority-principal-over-society",
            "smuggled_answer_note": "correct is index 1"}
        candidate, problems = vi.parse_candidate(raw)
        self.assertIsNone(candidate)
        self.assertTrue(any("non-empty string" in p and "nested" in p for p in problems))


class AssembleDraftTest(unittest.TestCase):
    def test_correct_index_is_single_absent_index(self):
        variant, key, problems = vi.assemble_draft(_request(), copy.deepcopy(GOOD))
        self.assertEqual(problems, [])
        self.assertEqual(key["correct_index"], 1)     # the one unmapped choice

    def test_all_indices_mapped_rejected(self):
        raw = copy.deepcopy(GOOD)
        raw["distractor_misconceptions"]["1"] = "canon-priority-principal-over-society"
        variant, key, problems = vi.assemble_draft(_request(), raw)
        self.assertIsNone(variant)
        self.assertTrue(any("exactly ONE unmapped" in p for p in problems))

    def test_two_absent_indices_rejected(self):
        raw = copy.deepcopy(GOOD); del raw["distractor_misconceptions"]["2"]
        variant, key, problems = vi.assemble_draft(_request(), raw)
        self.assertIsNone(variant)
        self.assertTrue(any("exactly ONE unmapped" in p for p in problems))

    def test_noncanonical_distractor_keys_rejected(self):
        for bad_key in ("01", "1.0", "-1", "9"):
            raw = copy.deepcopy(GOOD)
            raw["distractor_misconceptions"][bad_key] = "canon-priority-principal-over-society"
            variant, key, problems = vi.assemble_draft(_request(), raw)
            self.assertIsNone(variant, bad_key)

    def test_intake_forces_draft_status_source_and_zero_weight(self):
        variant, key, _ = vi.assemble_draft(_request(), copy.deepcopy(GOOD))
        self.assertEqual(variant["status"], "draft")
        self.assertEqual(variant["source"], "api_generated_local")
        self.assertEqual(variant["readiness_weight"], 0)


class IntakeGateTest(unittest.TestCase):
    def test_good_fixture_passes_all_13_gates_plus_intake(self):
        res = _validate(copy.deepcopy(GOOD))
        self.assertTrue(res["ok"], res["problems"])
        self.assertEqual(res["problems"], [])

    def test_keyed_wrong_choice_without_keywords_rejected(self):     # attack 1
        res = _validate(copy.deepcopy(BAD_KEYED_WRONG))
        self.assertFalse(res["ok"])
        self.assertTrue(any("keyed-correct choice does not contain" in p for p in res["problems"]))

    def test_second_choice_with_keywords_rejected(self):             # attack 2
        raw = copy.deepcopy(GOOD)
        raw["choices_variant"][0] = ("Follow the instruction, since the employer's order takes "
                                     "precedence over any duty to the public.")
        res = _validate(raw)
        self.assertFalse(res["ok"])
        self.assertTrue(any("also satisfy the lock" in p for p in res["problems"]))

    def test_concept_mismatch_on_keyed_wrong_choice_rejected(self):  # I6
        raw = copy.deepcopy(GOOD)
        raw["correct_choice_concept"] = "The employer's directive always wins."
        res = _validate(raw)
        self.assertFalse(res["ok"])
        self.assertTrue(any("does not carry the request's correct" in p for p in res["problems"]))

    def test_full_attack_variant_is_still_draft_and_never_practice_eligible(self):
        # The N3-class residual: echo the concept AND plant keywords on a wrong choice while
        # keying it 'correct'. Even if such a candidate defeated every text gate, the assembled
        # object is a DRAFT that no learner-facing path consumes.
        variant, key, _ = vi.assemble_draft(_request(), copy.deepcopy(GOOD))
        self.assertFalse(variants.is_practice_eligible(variant))
        self.assertEqual(variant["readiness_weight"], 0)
        forged = dict(variant, status="validated")   # even a smuggled 'validated' stays inert
        self.assertFalse(variants.is_practice_eligible(forged))

    def test_choice_count_drift_rejected(self):                      # I7
        raw = copy.deepcopy(GOOD)
        raw["choices_variant"] = raw["choices_variant"][:2]
        raw["distractor_misconceptions"] = {"0": "canon-priority-principal-over-society"}
        res = _validate(raw)
        self.assertFalse(res["ok"])
        self.assertTrue(any("difficulty drift" in p for p in res["problems"]))

    def test_distractor_id_outside_targets_rejected(self):           # I5
        raw = copy.deepcopy(GOOD)
        raw["distractor_misconceptions"]["0"] = "cia-property-confusion"
        res = _validate(raw)
        self.assertFalse(res["ok"])
        self.assertTrue(any("outside the request's" in p or "drifts" in p for p in res["problems"]))

    def test_holdout_paraphrase_stem_rejected(self):                 # I8 (stem near-dup)
        raw = copy.deepcopy(GOOD)
        raw["stem_variant"] = HOLDOUT[0]["stem"]
        res = _validate(raw)
        self.assertFalse(res["ok"])
        self.assertTrue(any("holdout" in p.lower() for p in res["problems"]))

    def test_holdout_stem_inside_choice_rejected(self):              # I8 (verbatim in a choice)
        raw = copy.deepcopy(GOOD)
        raw["choices_variant"][0] = HOLDOUT[0]["stem"]
        res = _validate(raw)
        self.assertFalse(res["ok"])
        self.assertTrue(any("verbatim" in p for p in res["problems"]))

    def test_length_tell_rejected(self):                             # I9
        raw = copy.deepcopy(GOOD)
        raw["choices_variant"][1] = ("Disclose and protect the public, since Canon 1 takes "
                                     "precedence over duty to the employer, whose interests are "
                                     "always secondary to the safety of society at large in every "
                                     "conflict the canons can describe, without exception or "
                                     "qualification of any kind whatsoever in practice.")
        res = _validate(raw)
        self.assertFalse(res["ok"])
        self.assertTrue(any("length tell" in p for p in res["problems"]))

    def test_parallelism_tell_rejected(self):                        # I9
        raw = copy.deepcopy(GOOD)
        raw["choices_variant"][0] = "Obey fully."
        res = _validate(raw)
        self.assertFalse(res["ok"])
        self.assertTrue(any("parallel" in p for p in res["problems"]))


class DraftStorageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "drafts"
        res = _validate(copy.deepcopy(GOOD))
        self.variant, self.key = res["variant"], res["variant_key"]

    def tearDown(self):
        self.tmp.cleanup()

    def test_key_file_physically_separate_correct_index_absent_from_draft(self):
        draft_path, key_path = vi.write_draft(self.variant, self.key, "demo", out_dir=self.out)
        self.assertNotEqual(draft_path, key_path)
        draft_text = draft_path.read_text(encoding="utf-8")
        self.assertNotIn('"correct_index"', draft_text)
        self.assertIn('"correct_index"', key_path.read_text(encoding="utf-8"))

    def test_distractor_map_lives_in_key_file_not_wrapper(self):
        draft_path, key_path = vi.write_draft(self.variant, self.key, "demo", out_dir=self.out)
        self.assertNotIn('"distractor_misconceptions"', draft_path.read_text(encoding="utf-8"))
        self.assertIn('"distractor_misconceptions"', key_path.read_text(encoding="utf-8"))

    def test_out_dir_inside_repo_rejected(self):
        committable = vi._PROJECT_ROOT / "spine" / "gold"
        with self.assertRaises(vi.VariantIntakeError):
            vi.write_draft(self.variant, self.key, "demo", out_dir=committable)

    def test_local_and_tmp_out_dirs_allowed(self):
        self.assertTrue(vi._out_dir_allowed(vi.DRAFT_DIR))
        self.assertTrue(vi._out_dir_allowed(self.out))
        self.assertFalse(vi._out_dir_allowed(vi._PROJECT_ROOT / "reports"))

    def test_collision_with_different_draw_key_refused(self):
        vi.write_draft(self.variant, self.key, "demo", out_dir=self.out)
        with self.assertRaises(vi.VariantIntakeError):
            vi.write_draft(self.variant, self.key, "other-key", out_dir=self.out)

    def test_same_draw_key_reingest_idempotent(self):
        a = vi.write_draft(self.variant, self.key, "demo", out_dir=self.out)
        b = vi.write_draft(self.variant, self.key, "demo", out_dir=self.out)
        self.assertEqual(a, b)


class IsolationTest(unittest.TestCase):
    def test_replay_rejects_variant_id_attempt_with_learner_state_error(self):
        # A graded draft can never enter learner state / readiness: replay fails closed on the id.
        attempt = {"attempt_id": "a1", "item_id": "D1.1.4.scenario.0001.v115",
                   "selected_index": 1, "at": 1}
        with self.assertRaises(learner_state.LearnerStateError):
            learner_state.replay([attempt], now=2)

    def test_open_journal_requests_projects_missed_items_only(self):
        stream = json.loads((FIXTURES / "synthetic_attempt_stream.json").read_text(encoding="utf-8"))
        reqs = vi.open_journal_requests(stream, now=5)
        self.assertTrue(all(set(r) == {"item_id", "objective", "bank", "misconception_id"}
                            for r in reqs))
        blob = json.dumps(reqs)
        self.assertNotIn("correct_index", blob)


class CliVariantTest(unittest.TestCase):
    def test_cli_prompt_is_deterministic_and_warns_on_stderr(self):
        outs = []
        for _ in range(2):
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = cli.main(["variant", "prompt", "--item-id", "D1.1.4.scenario.0001",
                               "--draw-key", "demo"])
            self.assertEqual(rc, 0)
            self.assertIn("evaluator context", err.getvalue())
            outs.append(out.getvalue())
        self.assertEqual(outs[0], outs[1])

    def test_cli_ingest_good_fixture_accepts_and_writes_two_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = cli.main(["variant", "ingest", "--item-id", "D1.1.4.scenario.0001",
                               "--draw-key", "demo",
                               "--candidate", str(FIXTURES / "variant_candidate_good.json"),
                               "--out", tmp])
            self.assertEqual(rc, 0)
            written = sorted(p.name for p in Path(tmp).iterdir())
            self.assertEqual(len(written), 2)
            self.assertTrue(any(n.endswith(".draft.json") for n in written))
            self.assertTrue(any(n.endswith(".draft.key.json") for n in written))
            self.assertIn("not practice-eligible", out.getvalue() + err.getvalue())

    def test_cli_missing_per_action_args_fail_cleanly(self):         # review F3
        for argv in (["variant", "requests"], ["variant", "validate"],
                     ["variant", "ingest", "--item-id", "D1.1.4.scenario.0001"]):
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = cli.main(argv)
            self.assertEqual(rc, 2, argv)
            self.assertIn("requires", err.getvalue())

    def test_cli_ingest_bad_fixture_rejects_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = cli.main(["variant", "ingest", "--item-id", "D1.1.4.scenario.0001",
                               "--draw-key", "demo",
                               "--candidate", str(FIXTURES / "variant_candidate_keyed_wrong_choice.json"),
                               "--out", tmp])
            self.assertNotEqual(rc, 0)
            self.assertEqual(list(Path(tmp).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
