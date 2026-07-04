"""IP-boundary guard tests (cc_spine.ipboundary)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cc_spine import ipboundary

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SPINE = PROJECT_ROOT / "spine"


class SupportSpanLimitTest(unittest.TestCase):
    def test_structured_exact_field_passes(self):
        self.assertEqual(ipboundary.check_support_span("SSH - TCP port 22", 0), [])

    def test_structured_rejects_multiline(self):
        problems = ipboundary.check_support_span("line one\nline two", 1)
        self.assertTrue(any("single-line" in p for p in problems))

    def test_markdown_within_fifty_words_passes(self):
        span = " ".join(["word"] * 50)
        self.assertEqual(ipboundary.check_support_span(span, 2), [])

    def test_markdown_over_fifty_words_fails(self):
        span = " ".join(["word"] * 51)
        problems = ipboundary.check_support_span(span, 2)
        self.assertTrue(any("51 words" in p for p in problems))

    def test_transcript_over_twenty_five_words_fails(self):
        span = " ".join(["word"] * 26)
        problems = ipboundary.check_support_span(span, 3)
        self.assertTrue(any("tier 3 limit is 25" in p for p in problems))

    def test_full_mcq_is_rejected(self):
        mcq = "Which port? A) 22 B) 80 C) 443 D) 3389"
        problems = ipboundary.check_support_span(mcq, 2)
        self.assertTrue(any("multiple-choice" in p for p in problems))


class StoreScanTest(unittest.TestCase):
    def test_empty_fact_store_passes(self):
        self.assertEqual(ipboundary.scan_facts(SPINE / "facts"), [])

    def test_notes_dir_passes_with_only_readme(self):
        self.assertEqual(ipboundary.scan_notes(PROJECT_ROOT / "notes"), [])


if __name__ == "__main__":
    unittest.main()
