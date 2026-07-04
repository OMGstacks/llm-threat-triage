"""Note review-state lifecycle tests (cc_spine.notes_lifecycle — R&D-4)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cc_spine import notes_lifecycle


def _note(status_line: str = "status: draft") -> str:
    return f"---\nsource_doc_id: x\n{status_line}\nreviewed_by: r\n---\n\nBody.\n"


class TransitionTest(unittest.TestCase):
    def test_legal_transitions_pass(self):
        for old, new in (
            ("draft", "reviewed"), ("draft", "rejected"),
            ("reviewed", "promoted"), ("reviewed", "deprecated"), ("reviewed", "draft"),
            ("promoted", "deprecated"),
        ):
            with self.subTest(f"{old}->{new}"):
                self.assertEqual(notes_lifecycle.validate_transition(old, new), [])

    def test_illegal_transitions_fail(self):
        for old, new in (
            ("draft", "promoted"),        # cannot skip review
            ("rejected", "reviewed"),     # terminal
            ("deprecated", "reviewed"),   # terminal
            ("promoted", "reviewed"),     # no demotion except deprecation
        ):
            with self.subTest(f"{old}->{new}"):
                self.assertTrue(notes_lifecycle.validate_transition(old, new))

    def test_unknown_status_fails(self):
        self.assertTrue(notes_lifecycle.validate_transition("mystery", "reviewed"))
        self.assertTrue(notes_lifecycle.validate_transition("draft", "mystery"))


class GroundingRuleTest(unittest.TestCase):
    def test_grounding_allowed_only_for_reviewed_and_promoted(self):
        self.assertTrue(notes_lifecycle.grounding_allowed("reviewed"))
        self.assertTrue(notes_lifecycle.grounding_allowed("promoted"))
        for status in ("draft", "rejected", "deprecated", None, "mystery"):
            with self.subTest(status=status):
                self.assertFalse(notes_lifecycle.grounding_allowed(status))

    def test_note_status_parsed_from_frontmatter(self):
        self.assertEqual(notes_lifecycle.note_status(_note("status: reviewed")), "reviewed")

    def test_status_outside_frontmatter_does_not_count(self):
        # A 'status:' line in the body must not satisfy the fail-closed parse.
        text = "---\nsource_doc_id: x\n---\n\nstatus: reviewed\n"
        self.assertIsNone(notes_lifecycle.note_status(text))

    def test_missing_status_fails_closed(self):
        text = "---\nsource_doc_id: x\n---\n\nBody.\n"
        problems = notes_lifecycle.validate_note_status(text)
        self.assertTrue(any("no front-matter status" in p for p in problems))

    def test_unknown_status_fails_closed(self):
        problems = notes_lifecycle.validate_note_status(_note("status: mystery"))
        self.assertTrue(any("unknown status" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
