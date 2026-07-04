"""Ingestion engine tests: extraction, suggest-only corrections, determinism.

The DOCX fixture is built in-memory so no .docx file is committed (the scaffold
validator forbids raw document files in the repo). The .txt fixture is
synthetic test data with planted ASR errors.
"""

import io
import json
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cc_spine import ingest

SPINE = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample_transcript.txt"
DICTIONARY = json.loads(
    (SPINE / "ingest" / "correction-dictionary.json").read_text(encoding="utf-8")
)

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    "</Types>"
)
_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
    "</Relationships>"
)


def make_docx(paragraphs) -> bytes:
    """Build a minimal .docx in memory. Each item is (text, style-or-None)."""
    body = []
    for text, style in paragraphs:
        ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
        body.append(f'<w:p>{ppr}<w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>')
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{W}"><w:body>{"".join(body)}</w:body></w:document>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _RELS)
        zf.writestr("word/document.xml", document)
    return buf.getvalue()


class DocxExtractionTest(unittest.TestCase):
    def test_extracts_in_order_with_headings(self):
        docx = make_docx([
            ("Network Security", "Heading1"),
            ("SSH uses TCP port 22.", None),
            ("Ports and Protocols", "Heading2"),
            ("HTTPS uses TCP port 443.", None),
            ("   ", None),  # empty paragraph is dropped
        ])
        paras = ingest.extract_docx(docx, "unit-doc")
        self.assertEqual([p.text for p in paras], [
            "Network Security", "SSH uses TCP port 22.",
            "Ports and Protocols", "HTTPS uses TCP port 443.",
        ])
        self.assertEqual([p.heading_level for p in paras], [1, None, 2, None])
        self.assertEqual([p.index for p in paras], [0, 1, 2, 3])

    def test_extraction_is_deterministic(self):
        docx = make_docx([("Heading", "Heading1"), ("Body text here.", None)])
        first = ingest.extract_docx(docx, "unit-doc")
        second = ingest.extract_docx(docx, "unit-doc")
        self.assertEqual([p.paragraph_id for p in first], [p.paragraph_id for p in second])

    def test_paragraph_id_is_stable_and_content_addressed(self):
        pid = ingest.paragraph_id("doc", 3, "The  QUICK   brown fox")
        # Whitespace/case-normalized before hashing → same id for equivalent text.
        self.assertEqual(pid, ingest.paragraph_id("doc", 3, "the quick brown fox"))
        self.assertTrue(pid.startswith("doc#0003#"))


class CorrectionSuggestionTest(unittest.TestCase):
    def setUp(self):
        self.paras = ingest.extract_text(FIXTURE.read_bytes(), "sample-transcript")
        self.suggestions = ingest.suggest_corrections(self.paras, DICTIONARY)

    def _pairs(self):
        return {(s.wrong.lower(), s.right, s.verify) for s in self.suggestions}

    def test_high_and_medium_corrections_are_suggested(self):
        pairs = self._pairs()
        self.assertIn(("art", "ARP", False), pairs)
        self.assertIn(("mag address", "MAC address", False), pairs)
        self.assertIn(("hedging", "hashing", False), pairs)
        self.assertIn(("pen", "PAN", False), pairs)

    def test_never_before_guard_suppresses_pen_test(self):
        # "pen test" must never be corrected to PAN.
        pen_paras = {s.paragraph_index for s in self.suggestions
                     if s.wrong.lower() == "pen"}
        # The "pen test" paragraph (index 4) must NOT yield a pen suggestion.
        self.assertNotIn(4, pen_paras)
        # ...but the legitimate "pen connects wearables" paragraph (index 3) must.
        self.assertIn(3, pen_paras)

    def test_never_auto_term_is_flagged_not_applied(self):
        flagged = [s for s in self.suggestions if s.wrong.lower() == "wi-fi city"]
        self.assertEqual(len(flagged), 1)
        self.assertTrue(flagged[0].verify)

    def test_engine_never_mutates_source_text(self):
        # Suggest-only: the original misheard terms remain in the paragraphs.
        joined = " ".join(p.text for p in self.paras)
        self.assertIn("art protocol", joined)
        self.assertIn("hedging function", joined)


class NoteBuildingTest(unittest.TestCase):
    def test_note_is_byte_identical_across_runs(self):
        note_a = ingest.ingest(FIXTURE, "sample-transcript", DICTIONARY)
        note_b = ingest.ingest(FIXTURE, "sample-transcript", DICTIONARY)
        self.assertEqual(note_a, note_b)

    def test_note_has_valid_frontmatter(self):
        note = ingest.ingest(FIXTURE, "sample-transcript", DICTIONARY)
        self.assertEqual(ingest.validate_note_frontmatter(note), [])

    def test_frontmatter_records_applied_and_flagged(self):
        note = ingest.ingest(FIXTURE, "sample-transcript", DICTIONARY)
        self.assertIn('right: "ARP"', note)
        self.assertIn('right: "hashing"', note)
        self.assertIn("corrections_flagged:", note)
        self.assertIn('wrong: "Wi-Fi city"', note)

    def test_body_preserves_original_text(self):
        note = ingest.ingest(FIXTURE, "sample-transcript", DICTIONARY)
        body = note.split("---", 2)[-1]
        self.assertIn("The art protocol maps", body)  # original preserved
        self.assertIn('> suggestion: "art" -> "ARP"', body)  # correction annotated, not applied

    def test_missing_frontmatter_is_reported(self):
        problems = ingest.validate_note_frontmatter("no front matter here")
        self.assertTrue(problems)


if __name__ == "__main__":
    unittest.main()
