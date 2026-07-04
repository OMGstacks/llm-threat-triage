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
EVIDENCE = json.loads(
    (PROJECT_ROOT / "reference" / "verification-evidence.json").read_text(encoding="utf-8"))


class SourceFreshnessTest(unittest.TestCase):
    def test_registry_is_fresh_today(self):
        # 2026-07-04 is before the 2026-09-01 outline transition; attestations back
        # the operator-unreachable ISC2 sources.
        failures = sources.validate_registry(
            REGISTRY, today=datetime.date(2026, 7, 4), evidence=EVIDENCE)
        self.assertEqual(failures, [], "\n".join(failures))

    def test_transition_date_fires_the_guard(self):
        # On/after 2026-09-01 the current outline is superseded and the
        # upcoming outline has become effective — both must be flagged.
        failures = sources.validate_registry(
            REGISTRY, today=datetime.date(2026, 9, 2), evidence=EVIDENCE)
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
            "topic": "t", "retrieved_at": "2026-07-04", "next_review": "2027-01-01",
        }]}
        failures = sources.validate_registry(bad, today=datetime.date(2026, 7, 4))
        self.assertTrue(any("missing source_url" in f for f in failures))

    def test_missing_next_review_fails(self):
        # Freshness ledger (PR-4): every source must carry a next_review date.
        bad = {"sources": [{
            "id": "x", "tier": 1, "type": "reference", "status": "current",
            "topic": "t", "source_url": "u", "retrieved_at": "2026-07-04",
        }]}
        failures = sources.validate_registry(bad, today=datetime.date(2026, 7, 4))
        self.assertTrue(any("missing next_review" in f for f in failures))

    def test_past_next_review_is_stale(self):
        bad = {"sources": [{
            "id": "x", "tier": 1, "type": "reference", "status": "current",
            "topic": "t", "source_url": "u", "retrieved_at": "2026-01-04",
            "next_review": "2026-06-01",
        }]}
        failures = sources.validate_registry(bad, today=datetime.date(2026, 7, 4))
        self.assertTrue(any("source review is due" in f for f in failures))

    def test_isc2_sources_go_stale_at_transition(self):
        # The registry's ISC2 entries carry next_review = 2026-09-01, so the
        # freshness ledger forces a human re-review at the outline transition.
        failures = sources.validate_registry(
            REGISTRY, today=datetime.date(2026, 9, 2), evidence=EVIDENCE)
        stale = [f for f in failures if "source review is due" in f]
        self.assertTrue(any("isc2.cc-outline.2025-10" in f for f in stale))
        self.assertTrue(any("isc2.cc-outline.2026-09" in f for f in stale))


class AttestationGuardTest(unittest.TestCase):
    """PR-4.1: operator-unreachable official sources require dated attestations."""

    def _blocked_source(self, **over):
        entry = {
            "id": "isc2.x", "tier": 0, "type": "exam_outline", "status": "current",
            "topic": "t", "source_url": "https://isc2.example/outline",
            "retrieved_at": "2026-07-04", "next_review": "2027-01-01",
            "confidence": "official-current", "operator_fetch_status": "blocked_403",
            "attestation_urls": ["https://isc2.example/outline"],
        }
        entry.update(over)
        return {"sources": [entry]}

    def _evidence(self, url="https://isc2.example/outline", date="2026-07-04"):
        return {"reviewer_attestations": [
            {"url": url, "date": date, "confirms": ["x"]}]}

    def test_blocked_official_source_with_attestation_passes(self):
        failures = sources.validate_registry(
            self._blocked_source(), today=datetime.date(2026, 7, 4), evidence=self._evidence())
        self.assertEqual(failures, [], "\n".join(failures))

    def test_blocked_official_source_without_evidence_fails(self):
        failures = sources.validate_registry(
            self._blocked_source(), today=datetime.date(2026, 7, 4), evidence=None)
        self.assertTrue(any("no verification evidence was loaded" in f for f in failures))

    def test_blocked_official_source_without_matching_attestation_fails(self):
        failures = sources.validate_registry(
            self._blocked_source(), today=datetime.date(2026, 7, 4),
            evidence=self._evidence(url="https://isc2.example/other"))
        self.assertTrue(any("no reviewer attestation" in f for f in failures))

    def test_attestation_predating_retrieval_fails(self):
        failures = sources.validate_registry(
            self._blocked_source(), today=datetime.date(2026, 7, 4),
            evidence=self._evidence(date="2026-06-01"))
        self.assertTrue(any("predates retrieved_at" in f for f in failures))

    def test_blocked_official_source_without_attestation_urls_fails(self):
        failures = sources.validate_registry(
            self._blocked_source(attestation_urls=[]),
            today=datetime.date(2026, 7, 4), evidence=self._evidence())
        self.assertTrue(any("lists no attestation_urls" in f for f in failures))

    def test_reachable_source_needs_no_attestation(self):
        # not_attempted sources (e.g. NIST) are not subject to the attestation guard.
        entry = self._blocked_source(operator_fetch_status="not_attempted", attestation_urls=[])
        failures = sources.validate_registry(
            entry, today=datetime.date(2026, 7, 4), evidence=None)
        self.assertEqual(failures, [], "\n".join(failures))

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
