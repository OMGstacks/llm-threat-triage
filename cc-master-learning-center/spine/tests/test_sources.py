"""Source-registry freshness guard tests (cc_spine.sources)."""

import datetime
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cc_spine import sources

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = PROJECT_ROOT / "reference" / "source-registry.json"
REGISTRY = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


class SourceFreshnessTest(unittest.TestCase):
    def test_registry_is_fresh_today(self):
        # 2026-07-04 is before the 2026-09-01 outline transition.
        failures = sources.validate_registry(REGISTRY, today=datetime.date(2026, 7, 4))
        self.assertEqual(failures, [], "\n".join(failures))

    def test_transition_date_fires_the_guard(self):
        # On/after 2026-09-01 the current outline is superseded and the
        # upcoming outline has become effective — both must be flagged.
        failures = sources.validate_registry(REGISTRY, today=datetime.date(2026, 9, 2))
        joined = "\n".join(failures)
        self.assertIn("isc2.cc-outline.2026-09", joined)
        self.assertIn("isc2.cc-outline.2025-10", joined)

    def test_bad_tier_is_rejected(self):
        bad = {"sources": [{
            "id": "x", "tier": 9, "type": "reference", "status": "current",
            "topic": "t", "source_url": "u", "retrieved_at": "2026-07-04",
        }]}
        failures = sources.validate_registry(bad, today=datetime.date(2026, 7, 4))
        self.assertTrue(any("tier must be an integer 0-4" in f for f in failures))

    def test_future_retrieved_at_is_rejected(self):
        bad = {"sources": [{
            "id": "x", "tier": 1, "type": "reference", "status": "current",
            "topic": "t", "source_url": "u", "retrieved_at": "2030-01-01",
        }]}
        failures = sources.validate_registry(bad, today=datetime.date(2026, 7, 4))
        self.assertTrue(any("future" in f for f in failures))

    def test_missing_source_url_fails(self):
        bad = {"sources": [{
            "id": "x", "tier": 1, "type": "reference", "status": "current",
            "topic": "t", "retrieved_at": "2026-07-04",
        }]}
        failures = sources.validate_registry(bad, today=datetime.date(2026, 7, 4))
        self.assertTrue(any("missing source_url" in f for f in failures))

    def test_duplicate_id_is_rejected(self):
        entry = {
            "id": "dup", "tier": 1, "type": "reference", "status": "current",
            "topic": "t", "source_url": "u", "retrieved_at": "2026-07-04",
        }
        failures = sources.validate_registry(
            {"sources": [entry, dict(entry)]}, today=datetime.date(2026, 7, 4)
        )
        self.assertTrue(any("duplicate id" in f for f in failures))


if __name__ == "__main__":
    unittest.main()
