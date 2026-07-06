"""PR-1 scaffold gate: the unittest wrapper around cc_spine.scaffold_validate.

Runnable with stock Python from the spine directory
(``python3 -m unittest discover -s tests``) or from the repo root
(``python3 -m unittest discover -s cc-master-learning-center/spine/tests
-t cc-master-learning-center/spine/tests`` — the explicit top-level dir is
required because the project path is not an importable package name).
"""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cc_spine import scaffold_validate

MATRIX = json.loads(
    (Path(__file__).resolve().parents[2] / "reference" / "objective-matrix.json")
    .read_text(encoding="utf-8"))


class ScaffoldValidationTest(unittest.TestCase):
    def test_scaffold_passes_all_checks(self):
        failures = scaffold_validate.run_checks()
        self.assertEqual(failures, [], "scaffold validation failed:\n" + "\n".join(failures))

    def test_all_guards_are_tracked(self):
        expected = {
            "source_freshness_guard",
            "ip_boundary_guard",
            "no_verbatim_bulk_reproduction",
            "holdout_leakage_guard",
            "answer_key_isolation_guard",
            "unsupported_claim_guard",
            "learner_state_isolation_guard",
            "api_draft_isolation_guard",
        }
        self.assertEqual(set(scaffold_validate.GUARD_STATUS), expected)

    def test_pr10_4b_activated_api_draft_isolation_guard(self):
        self.assertEqual(scaffold_validate.GUARD_STATUS["api_draft_isolation_guard"], "active")

    def test_api_variant_scan_flags_committed_draft(self):
        import tempfile
        failures = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "spine").mkdir()
            # a draft variant body parked in a committable location must fail...
            (root / "spine" / "sneaky.json").write_text(json.dumps(
                {"stem_variant": "x?", "status": "draft"}), encoding="utf-8")
            # ...as must the api_generated_local source marker...
            (root / "spine" / "marker.json").write_text(
                '{"source": "api_generated_local"}', encoding="utf-8")
            # ...and any variant-drafts path outside .local/...
            (root / "variant-drafts").mkdir()
            (root / "variant-drafts" / "d.json").write_text("{}", encoding="utf-8")
            # ...and the write_draft WRAPPER shape with the source marker stripped (review F4)...
            (root / "spine" / "wrapper.json").write_text(json.dumps(
                {"draw_key": "k", "variant": {"stem_variant": "x?", "status": "draft"}}),
                encoding="utf-8")
            # ...and unparseable json that mentions stem_variant (review F4).
            (root / "spine" / "broken.json").write_text('{"stem_variant": ', encoding="utf-8")
            scaffold_validate._check_no_api_variant_data(failures, root=root)
        self.assertEqual(len(failures), 5, failures)

    def test_local_variant_drafts_dir_does_not_fail_scaffold(self):
        import tempfile
        failures = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            drafts = root / ".local" / "variant-drafts"
            drafts.mkdir(parents=True)
            (drafts / "D1.1.4.scenario.0001.v115.draft.json").write_text(
                json.dumps({"draw_key": "demo",
                            "variant": {"stem_variant": "x?", "status": "draft",
                                        "source": "api_generated_local"}}), encoding="utf-8")
            scaffold_validate._check_no_api_variant_data(failures, root=root)
        self.assertEqual(failures, [])

    def test_learner_state_check_exempts_local_variant_drafts(self):
        # A legitimate local draft in the sanctioned gitignored dir must NOT turn the
        # working-tree learner-state scan red (PR-10.4b; plan-time bug fix).
        drafts = scaffold_validate.PROJECT_ROOT / ".local" / "variant-drafts"
        drafts.mkdir(parents=True, exist_ok=True)
        probe = drafts / "zz-test-probe.draft.json"
        probe.write_text("{}", encoding="utf-8")
        try:
            failures = []
            scaffold_validate._check_no_learner_state(failures)
            self.assertEqual([f for f in failures if "zz-test-probe" in f], [])
        finally:
            probe.unlink()

    def test_pr2_activated_freshness_and_ip_guards(self):
        self.assertEqual(scaffold_validate.GUARD_STATUS["source_freshness_guard"], "active")
        self.assertEqual(scaffold_validate.GUARD_STATUS["ip_boundary_guard"], "active")

    def _matrix_failures(self, matrix):
        registry_ids = {s["id"] for s in json.loads(
            (Path(__file__).resolve().parents[2] / "reference" / "source-registry.json")
            .read_text(encoding="utf-8"))["sources"]}
        failures = []
        scaffold_validate._check_matrix(matrix, registry_ids, failures)
        return failures

    def test_completed_crosswalk_validates(self):
        # PR-4: the real matrix carries a complete, consistent crosswalk.
        self.assertEqual(self._matrix_failures(MATRIX), [])

    def test_crosswalk_missing_objective_fails(self):
        broken = copy.deepcopy(MATRIX)
        del broken["outlines"]["2026-09"]["crosswalk_map"]["4.2"]
        failures = self._matrix_failures(broken)
        self.assertTrue(any("crosswalk_map keys must be exactly" in f for f in failures))

    def test_crosswalk_bad_target_domain_fails(self):
        broken = copy.deepcopy(MATRIX)
        broken["outlines"]["2026-09"]["crosswalk_map"]["1.1"] = ["D9"]
        failures = self._matrix_failures(broken)
        self.assertTrue(any("is not a 2026-09 domain" in f for f in failures))

    def test_crosswalk_objective_inconsistency_fails(self):
        # A per-objective crosswalk_2026 that disagrees with the map must fail.
        broken = copy.deepcopy(MATRIX)
        broken["outlines"]["2026-09"]["crosswalk_map"]["2.3"] = ["D2"]  # matrix objective says D5
        failures = self._matrix_failures(broken)
        self.assertTrue(any("!= crosswalk_map entry" in f for f in failures))

    def test_crosswalk_empty_target_list_fails(self):
        broken = copy.deepcopy(MATRIX)
        broken["outlines"]["2026-09"]["crosswalk_map"]["5.1"] = []
        failures = self._matrix_failures(broken)
        self.assertTrue(any("non-empty list" in f for f in failures))

    def test_pr3_activated_unsupported_claim_guard(self):
        self.assertEqual(scaffold_validate.GUARD_STATUS["unsupported_claim_guard"], "active")

    def test_manifest_rejects_raw_committed_true(self):
        failures = []
        scaffold_validate._check_manifest(
            {"ip_policy": "distillation_only", "authorization": {"authorized_by": "x"},
             "sources": [{"source_doc_id": "d", "raw_committed": True, "sha256": "a" * 64}]},
            failures)
        self.assertTrue(any("raw_committed must be false" in f for f in failures))

    def test_manifest_rejects_bad_hash(self):
        failures = []
        scaffold_validate._check_manifest(
            {"ip_policy": "distillation_only", "authorization": {"authorized_by": "x"},
             "sources": [{"source_doc_id": "d", "raw_committed": False, "sha256": "nope"}]},
            failures)
        self.assertTrue(any("64-hex digest" in f for f in failures))

    def test_pr5_activated_no_verbatim_guard(self):
        self.assertEqual(scaffold_validate.GUARD_STATUS["no_verbatim_bulk_reproduction"], "active")

    def test_pr8_activated_answer_key_isolation_guard(self):
        self.assertEqual(scaffold_validate.GUARD_STATUS["answer_key_isolation_guard"], "active")

    def test_pr8c_activated_holdout_leakage_guard(self):
        self.assertEqual(scaffold_validate.GUARD_STATUS["holdout_leakage_guard"], "active")

    def test_pr9_activated_learner_state_isolation_guard(self):
        self.assertEqual(scaffold_validate.GUARD_STATUS["learner_state_isolation_guard"], "active")
        # All tracked guards are active — none reserved.
        self.assertEqual(set(scaffold_validate.RESERVED_GUARDS), set())

    def test_raw_docx_anywhere_in_repo_scope_fails(self):
        # P0-3: raw file scan covers the full repo root, not just the project dir.
        # Simulate a .docx outside the cc-master-learning-center tree by patching
        # REPO_ROOT to a tmp directory with a stray .docx in a sibling folder.
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        sibling = Path(tmp.name) / "other-project"
        sibling.mkdir()
        (sibling / "transcript.docx").write_bytes(b"")
        orig = scaffold_validate.REPO_ROOT
        try:
            scaffold_validate.REPO_ROOT = Path(tmp.name)
            failures: list[str] = []
            scaffold_validate._check_no_raw_transcripts(failures)
        finally:
            scaffold_validate.REPO_ROOT = orig
        self.assertTrue(any(".docx" in f for f in failures))


if __name__ == "__main__":
    unittest.main()
