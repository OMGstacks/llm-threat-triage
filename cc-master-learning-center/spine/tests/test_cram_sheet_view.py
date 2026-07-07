"""Cram-sheet render tests — the PR-11c acceptance gates.

Proves ``cram_sheet_view.render_html`` is a pure, deterministic formatter: standalone vs fragment
shape, HTML-special-character escaping, the empty state, priority chips, the closed recap, and —
despite deliberately showing teaching content — no forbidden field or holdout text ever appears.

NOTE on assertion style: several assertions below check the RENDERED element's class attribute
(e.g. ``class="chip chip-warn"``) rather than a bare class-name substring, because the stylesheet
always defines every ``.chip-*``/``.dot-*`` rule regardless of what's rendered — a bare substring
check would pass even if the wrong element (or no element) were rendered. This mirrors a false-
positive pattern already caught twice in the sibling dashboard-view test suite.
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cc_spine import cram_sheet, cram_sheet_view as cv, learner_state as ls, quiz

FIXTURES = Path(__file__).resolve().parent / "fixtures"
STREAM = json.loads((FIXTURES / "synthetic_attempt_stream.json").read_text(encoding="utf-8"))
FORBIDDEN = ("correct_index", "answer_key_ref", "rationale_refs", "distractor_misconceptions",
            "answer_key_hash", "item_hash", "selected_index")


def _sheet(now=5):
    return cram_sheet.build_cram_sheet(ls.replay(STREAM, now=now), now=now)


def _minimal_sheet(**overrides) -> dict:
    base = {
        "schema_version": "1.0.0", "generated_at_day": 5,
        "open_count": 0, "closed_count": 0, "priority_count": 0,
        "domains": [], "closed_recap": [],
    }
    base.update(overrides)
    return base


class DeterminismTest(unittest.TestCase):
    def test_render_is_deterministic(self):
        c = _sheet()
        self.assertEqual(cv.render_html(c), cv.render_html(c))
        self.assertEqual(cv.render_html(c, standalone=False), cv.render_html(c, standalone=False))


class DocumentShapeTest(unittest.TestCase):
    def test_standalone_is_a_complete_document(self):
        html = cv.render_html(_sheet(), standalone=True)
        for tag in ("<!DOCTYPE html>", "<html", "<head>", "<body>", "</html>"):
            self.assertIn(tag, html)

    def test_fragment_has_no_document_wrapper(self):
        html = cv.render_html(_sheet(), standalone=False)
        for tag in ("<!DOCTYPE", "<html", "<head>", "<body>"):
            self.assertNotIn(tag, html)
        self.assertIn("<title>", html)

    def test_tags_are_balanced(self):
        import html.parser

        _VOID = {"meta", "link", "br", "hr", "img", "input"}

        class _Tracker(html.parser.HTMLParser):
            def __init__(self, owner):
                super().__init__()
                self.stack = []
                self.owner = owner

            def handle_starttag(self, tag, attrs):
                if tag not in _VOID:
                    self.stack.append(tag)

            def handle_endtag(self, tag):
                self.owner.assertTrue(self.stack, f"unmatched closing </{tag}>")
                self.owner.assertEqual(self.stack.pop(), tag, f"mismatched closing </{tag}>")

        tracker = _Tracker(self)
        tracker.feed(cv.render_html(_sheet(), standalone=True))
        self.assertEqual(tracker.stack, [])


class ContentFreeTest(unittest.TestCase):
    def test_render_carries_no_isolated_key_field(self):
        html = cv.render_html(_sheet())
        for forbidden in FORBIDDEN:
            self.assertNotIn(forbidden, html)

    def test_no_holdout_stem_leaks(self):
        # NOTE: we do NOT check for absence of arbitrary choice-text substrings here — the cram
        # sheet's correction/trap/rule prose deliberately discusses domain concepts (e.g. "TCP"),
        # and short answer-choice strings elsewhere in the 45-item corpus legitimately share that
        # vocabulary. A bare substring match would false-positive on expected word overlap, not a
        # real leak. Choices are structurally absent from the data model (proven in
        # test_cram_sheet.py); holdout stems are long, specific sentences with negligible collision
        # risk, so that remains a meaningful check.
        html = cv.render_html(_sheet())
        for h in quiz.load_holdout():
            self.assertNotIn(h["stem"], html)

    def test_escapes_html_special_characters(self):
        c = _minimal_sheet(open_count=1, domains=[{
            "domain": "D1", "accuracy": 0.5, "attempts": 2,
            "entries": [{
                "item_id": "x", "objective": "1.1", "bank": "definition_recall",
                "misconception_id": "m1",
                "trap": '<script>alert(1)</script>', "correction": "fine & good",
                "one_sentence_rule": "the rule", "recorded_at_day": 1, "priority": False,
                "stem": None,
            }],
        }])
        html = cv.render_html(c)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&amp;", html)


class EmptyStateTest(unittest.TestCase):
    def test_no_domains_shows_positive_empty_state(self):
        html = cv.render_html(_minimal_sheet())
        self.assertIn("Nothing open right now", html)


class TrapCardTest(unittest.TestCase):
    def _one_entry_sheet(self, priority):
        return _minimal_sheet(open_count=1, domains=[{
            "domain": "D4", "accuracy": 0.0, "attempts": 1,
            "entries": [{
                "item_id": "D4.4.1.scenario.0001", "objective": "4.1", "bank": "scenario_application",
                "misconception_id": "udp-reliable", "trap": "UDP is reliable.",
                "correction": "UDP is best-effort.", "one_sentence_rule": "TCP is reliable; UDP is not.",
                "recorded_at_day": 2, "priority": priority, "stem": "Which protocol...?",
            }],
        }])

    def test_priority_entry_shows_confidently_wrong_chip(self):
        html = cv.render_html(self._one_entry_sheet(priority=True))
        # check the RENDERED class attribute, not a bare substring (the CSS always defines .chip-warn).
        self.assertIn('class="chip chip-warn"', html)
        self.assertIn("confidently wrong", html)

    def test_non_priority_entry_shows_no_chip(self):
        html = cv.render_html(self._one_entry_sheet(priority=False))
        self.assertNotIn('class="chip chip-warn"', html)

    def test_trap_correction_and_rule_all_render(self):
        html = cv.render_html(self._one_entry_sheet(priority=False))
        self.assertIn("UDP is reliable.", html)
        self.assertIn("UDP is best-effort.", html)
        self.assertIn("TCP is reliable; UDP is not.", html)

    def test_stem_renders_as_quote_context(self):
        html = cv.render_html(self._one_entry_sheet(priority=False))
        self.assertIn("Which protocol...?", html)

    def test_missing_stem_renders_no_quote_block(self):
        # check the RENDERED element, not a bare class-name substring (the CSS always defines
        # .stem-quote regardless of whether the element is present — the same false-positive
        # pattern already caught twice in the sibling dashboard-view test suite).
        c = self._one_entry_sheet(priority=False)
        c["domains"][0]["entries"][0]["stem"] = None
        html = cv.render_html(c)
        self.assertNotIn('<blockquote class="stem-quote"', html)


class RecapTest(unittest.TestCase):
    def test_recap_renders_when_present(self):
        c = _minimal_sheet(closed_count=1,
                          closed_recap=[{"misconception_id": "hashing-is-encryption",
                                        "one_sentence_rule": "Hashing is one-way."}])
        html = cv.render_html(c)
        self.assertIn("Recently closed", html)
        self.assertIn("Hashing is one-way.", html)

    def test_no_recap_section_when_empty(self):
        html = cv.render_html(_minimal_sheet())
        self.assertNotIn("Recently closed", html)


if __name__ == "__main__":
    unittest.main()
