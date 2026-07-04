"""PR-1 scaffold gate: the unittest wrapper around cc_spine.scaffold_validate.

Runnable with stock Python from the spine directory
(``python3 -m unittest discover -s tests``) or from the repo root
(``python3 -m unittest discover -s cc-master-learning-center/spine/tests
-t cc-master-learning-center/spine/tests`` — the explicit top-level dir is
required because the project path is not an importable package name).
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cc_spine import scaffold_validate


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
        }
        self.assertEqual(set(scaffold_validate.GUARD_STATUS), expected)

    def test_pr2_activated_freshness_and_ip_guards(self):
        self.assertEqual(scaffold_validate.GUARD_STATUS["source_freshness_guard"], "active")
        self.assertEqual(scaffold_validate.GUARD_STATUS["ip_boundary_guard"], "active")

    def test_pr3_activated_unsupported_claim_guard(self):
        self.assertEqual(scaffold_validate.GUARD_STATUS["unsupported_claim_guard"], "active")
        # The remaining three are not delivered until later PRs (answer-key
        # isolation names bank-output/holdout enforcement — PR-8; card-level
        # quarantine already ships in the PR-3 factstore).
        self.assertEqual(
            set(scaffold_validate.RESERVED_GUARDS),
            {
                "no_verbatim_bulk_reproduction",
                "holdout_leakage_guard",
                "answer_key_isolation_guard",
            },
        )


if __name__ == "__main__":
    unittest.main()
