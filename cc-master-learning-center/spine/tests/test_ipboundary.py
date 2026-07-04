"""IP-boundary guard tests (cc_spine.ipboundary)."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cc_spine import ipboundary

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SPINE = PROJECT_ROOT / "spine"


def _note(status: str, paragraph: str) -> str:
    return (f"---\nsource_doc_id: x\nstatus: {status}\nreviewed_by: r\n---\n\n"
            f"{paragraph}\n")


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


class NotesScanTest(unittest.TestCase):
    """R&D-1a: published (reviewed/promoted) notes must respect the 25-word span
    limit — must-fail proofs, via tmp notes dirs."""

    def _scan(self, status: str, words: int):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        (Path(tmp.name) / "D4.md").write_text(
            _note(status, " ".join(["word"] * words)), encoding="utf-8")
        return ipboundary.scan_notes(Path(tmp.name))

    def test_reviewed_note_paragraph_over_25_words_fails(self):
        failures = self._scan("reviewed", 26)
        self.assertTrue(any("exceeds transcript span limit" in f for f in failures))

    def test_promoted_note_paragraph_over_25_words_fails(self):
        # The lifecycle's 'promoted' state must not bypass the published-span gate.
        failures = self._scan("promoted", 26)
        self.assertTrue(any("exceeds transcript span limit" in f for f in failures))

    def test_draft_note_is_not_subject_to_published_gate(self):
        self.assertEqual(self._scan("draft", 26), [])

    def test_reviewed_note_within_limit_passes(self):
        self.assertEqual(self._scan("reviewed", 25), [])


class NoVerbatimGuardTest(unittest.TestCase):
    """PR-5 no_verbatim_bulk_reproduction: committed markdown must be distilled,
    not transcript-shaped bulk prose."""

    def _dir_with(self, text: str):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        (Path(tmp.name) / "note.md").write_text(text, encoding="utf-8")
        return Path(tmp.name)

    def test_long_prose_paragraph_fails(self):
        dump = " ".join(["word"] * 200)
        failures = ipboundary.scan_verbatim([self._dir_with(f"# H\n\n{dump}\n")])
        self.assertTrue(any("exceeds the no-verbatim cap" in f for f in failures))

    def test_structured_content_passes(self):
        md = ("# Heading\n\n| Concept | Gloss |\n|---|---|\n"
              "| " + " ".join(["x"] * 200) + " | short |\n\n- " + " ".join(["y"] * 200) + "\n")
        self.assertEqual(ipboundary.scan_verbatim([self._dir_with(md)]), [])

    def test_short_prose_passes(self):
        self.assertEqual(ipboundary.scan_verbatim([self._dir_with("# H\n\nA short intro line.\n")]), [])

    def test_committed_concept_inventories_pass(self):
        # The real distilled inventories must clear the guard.
        self.assertEqual(ipboundary.scan_verbatim([PROJECT_ROOT / "notes"]), [])


if __name__ == "__main__":
    unittest.main()
