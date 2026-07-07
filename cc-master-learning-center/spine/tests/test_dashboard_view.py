"""Visual-dashboard render tests — the PR-11b acceptance gates.

Proves ``dashboard_view.render_html`` is a pure, deterministic formatter over the PR-11a data model:
standalone mode is a complete document, fragment mode is head-less (for host embedding), every
verdict/blocker/mock/content-scale branch renders the right state, HTML-special characters are
escaped, and — most importantly — the render can never carry an answer-bearing or PII field, because
it never receives one (traced against the same fixture used for the dashboard tests).
"""

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cc_spine import dashboard, dashboard_view as dv, learner_state as ls, mock_exam as mx, quiz

FIXTURES = Path(__file__).resolve().parent / "fixtures"
STREAM = json.loads((FIXTURES / "synthetic_attempt_stream.json").read_text(encoding="utf-8"))
FORBIDDEN = ("correct_index", "answer_key_ref", "rationale_refs", "distractor_misconceptions",
            "answer_key_hash", "item_hash", "selected_index")


def _dashboard(now=5, mock_result=None):
    return dashboard.build_dashboard(ls.replay(STREAM, now=now), mock_result=mock_result, now=now)


class DeterminismTest(unittest.TestCase):
    def test_render_is_deterministic(self):
        d = _dashboard()
        self.assertEqual(dv.render_html(d), dv.render_html(d))
        self.assertEqual(dv.render_html(d, standalone=False), dv.render_html(d, standalone=False))


class DocumentShapeTest(unittest.TestCase):
    def test_standalone_is_a_complete_document(self):
        html = dv.render_html(_dashboard(), standalone=True)
        for tag in ("<!DOCTYPE html>", "<html", "<head>", "<body>", "</html>"):
            self.assertIn(tag, html)
        self.assertIn("<title>", html)

    def test_fragment_has_no_document_wrapper(self):
        html = dv.render_html(_dashboard(), standalone=False)
        for tag in ("<!DOCTYPE", "<html", "<head>", "<body>"):
            self.assertNotIn(tag, html)
        self.assertIn("<title>", html)   # still present, per Artifact-embedding convention

    def test_tags_are_balanced(self):
        # review F2: html.parser.HTMLParser has no strict/validating mode — overriding error()
        # never fires, so that was a near-tautological check. Track start/end tags for real balance.
        import html.parser

        _VOID = {"meta", "link", "br", "hr", "img", "input"}

        class _TagTracker(html.parser.HTMLParser):
            def __init__(self):
                super().__init__()
                self.stack = []

            def handle_starttag(self, tag, attrs):
                if tag not in _VOID:
                    self.stack.append(tag)

            def handle_endtag(self, tag):
                self.assertion_target.assertTrue(self.stack, f"unmatched closing </{tag}>")
                self.assertion_target.assertEqual(self.stack.pop(), tag,
                                                  f"mismatched closing </{tag}>")

        tracker = _TagTracker()
        tracker.assertion_target = self
        tracker.feed(dv.render_html(_dashboard(), standalone=True))
        self.assertEqual(tracker.stack, [], f"unclosed tag(s): {tracker.stack}")


class ContentFreeTest(unittest.TestCase):
    def test_render_carries_no_answer_bearing_field(self):
        html = dv.render_html(_dashboard())
        for forbidden in FORBIDDEN:
            self.assertNotIn(forbidden, html)

    def test_no_practice_or_holdout_stem_or_choice_leaks(self):
        html = dv.render_html(_dashboard())
        for item in list(quiz.load_goldset()) + list(quiz.load_holdout()):
            self.assertNotIn(item["stem"], html)
            for choice in item["choices"]:
                self.assertNotIn(choice, html)

    def test_escapes_html_special_characters_in_data(self):
        # a synthetic dashboard with a hostile-looking string in a data field must not inject markup.
        d = _dashboard()
        d = json.loads(json.dumps(d))
        d["readiness"]["hard_blockers"] = ['<script>alert(1)</script> & "quoted"']
        html = dv.render_html(d)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&amp;", html)


def _minimal_dashboard() -> dict:
    """A minimal synthetic dashboard for exercising a single branch in isolation."""
    return {
        "schema_version": "1.0.0", "generated_at_day": 5,
        "readiness": {"verdict": "ready", "score": 0.9, "complete": True, "weighted_over": ["a"],
                     "hard_blockers": [], "note": None},
        "domain_accuracy": {}, "bank_accuracy": {},
        "spaced_repetition": {"total_items": 0, "due_now": 0, "mature_items": 0, "next_review_items": []},
        "wrong_answers": {"open_count": 0, "closure_rate": 1.0, "open_misconceptions": []},
        "top_misconceptions": [], "mock": None,
        "content_scale": {"practice_items": 45, "holdout_scenarios": 5, "mock_target_min": 100,
                          "mock_target_max": 125, "status": "exam_scale", "caveat": None},
        "next_recommended_review": [],
    }


class VerdictStateTest(unittest.TestCase):
    def _base(self):
        return _minimal_dashboard()

    def test_ready_shows_good_chip_and_no_attention_card(self):
        html = dv.render_html(self._base())
        self.assertIn('chip-good">READY', html)
        # the .attn-card CSS rule is always in the stylesheet; check the ELEMENT isn't rendered.
        self.assertNotIn('class="card attn-card"', html)

    def test_incomplete_shows_warn_chip_and_note(self):
        d = self._base()
        d["readiness"].update(verdict="not-ready", complete=False,
                              note="incomplete: needs a graded mock for fresh_scenario_accuracy")
        html = dv.render_html(d)
        self.assertIn("INCOMPLETE", html)
        self.assertIn("needs a graded mock", html)

    def test_blockers_show_bad_chip_and_attention_rows(self):
        d = self._base()
        d["readiness"].update(verdict="not-ready", score=0.5,
                              hard_blockers=["domain D4 accuracy 0% < 75%"])
        html = dv.render_html(d)
        self.assertIn('chip-bad">NOT READY', html)
        self.assertIn("domain D4 accuracy 0%", html)
        self.assertIn('class="card attn-card"', html)

    def test_complete_no_blockers_below_target_shows_score_note(self):
        d = self._base()
        d["readiness"].update(verdict="not-ready", score=0.72, complete=True, hard_blockers=[])
        html = dv.render_html(d)
        self.assertIn("below the 80% readiness target", html)


class DomainGaugeTest(unittest.TestCase):
    """review F1/F3: the domain gauge color must never contradict the real hard-blocker gate
    (accuracy < 0.75). No intermediate 'near miss' tier may render an active blocker as anything
    but gauge-bad — the earlier three-tier version let a 70%-accuracy domain, an ACTIVE blocker,
    render amber ('warn') while the same domain listed red in the Attention card."""

    def _with_domains(self, domains: dict, hard_blockers=()):
        d = _minimal_dashboard()
        d["domain_accuracy"] = {dom: {"accuracy": acc, "attempts": 5} for dom, acc in domains.items()}
        d["readiness"]["hard_blockers"] = list(hard_blockers)
        d["readiness"]["verdict"] = "not-ready" if hard_blockers else d["readiness"]["verdict"]
        return d

    def test_every_hard_blocker_domain_renders_gauge_bad_never_warn(self):
        # check the RENDERED class attribute ("gauge-fill gauge-bad"), not a bare substring — the CSS
        # stylesheet always defines .gauge-bad/.gauge-warn rules regardless of what's rendered, so a
        # bare substring check would pass even if the element used the wrong class (the exact bug
        # that let the original miscalibration ship undetected).
        for acc in (0.0, 0.40, 0.60, 0.70, 0.749):    # the whole failing range, incl. the old warn band
            d = self._with_domains({"D4": acc}, hard_blockers=[f"domain D4 accuracy {acc:.0%} < 75%"])
            html = dv.render_html(d)
            self.assertIn("gauge-fill gauge-bad", html, f"accuracy {acc} must render gauge-bad")
            self.assertNotIn("gauge-fill gauge-warn", html,
                            f"accuracy {acc} must not render a warn/near-miss tier")

    def test_passing_domain_renders_gauge_good(self):
        for acc in (0.75, 0.90, 1.0):
            html = dv.render_html(self._with_domains({"D1": acc}))
            self.assertIn("gauge-fill gauge-good", html)
            self.assertNotIn("gauge-fill gauge-bad", html)

    def test_no_gauge_warn_class_exists_for_domains_at_all(self):
        # belt-and-braces: the CSS itself must not define a domain warn tier a future edit could reach for.
        self.assertNotIn(".gauge-warn", dv._STYLE)

    def test_empty_domain_accuracy_shows_empty_state(self):
        html = dv.render_html(_minimal_dashboard())   # domain_accuracy == {}
        self.assertIn("No domain attempts recorded yet.", html)


class BankGaugeTest(unittest.TestCase):
    def test_bank_accuracy_renders_with_accent_not_semantic_color(self):
        d = _minimal_dashboard()
        d["bank_accuracy"] = {"scenario_application": {"accuracy": 0.40, "total": 5}}
        html = dv.render_html(d)
        # informational, not gated — must use the accent fill, never good/warn/bad on a bank bar.
        # Check the rendered class attribute, not a bare substring (the CSS always defines the rule).
        self.assertIn("gauge-fill gauge-accent", html)
        self.assertIn("scenario_application", html)

    def test_empty_bank_accuracy_shows_empty_state(self):
        html = dv.render_html(_minimal_dashboard())   # bank_accuracy == {}
        self.assertIn("No bank attempts recorded yet.", html)


class ContentScaleTest(unittest.TestCase):
    def test_proof_scale_shows_banner(self):
        html = dv.render_html(_dashboard())   # fixture content is proof-scale
        self.assertIn("Proof-scale content", html)

    def test_exam_scale_hides_banner(self):
        d = _dashboard()
        d["content_scale"]["status"] = "exam_scale"
        d["content_scale"]["caveat"] = None
        self.assertNotIn("Proof-scale content", dv.render_html(d))


class MockStateTest(unittest.TestCase):
    def test_no_mock_shows_empty_state(self):
        html = dv.render_html(_dashboard())
        self.assertIn("No mock graded yet", html)

    def test_graded_mock_shows_stats(self):
        mock = mx.assemble("dash-view", count=15)
        prac_keys = {k["item_id"]: k for k in quiz.load_answer_keys()}
        hold_keys = {k["item_id"]: k for k in quiz.load_holdout_keys()}
        subs = {e["item_id"]: (hold_keys if e["lane"] == "holdout" else prac_keys)[e["item_id"]]["correct_index"]
                for e in mock["items"]}
        graded = mx.grade_mock(mock, subs)
        html = dv.render_html(_dashboard(mock_result=graded))
        self.assertNotIn("No mock graded yet", html)
        self.assertIn("fresh-scenario accuracy", html)


class SpacedRepetitionTest(unittest.TestCase):
    def test_remainder_note_shown_when_due_exceeds_shown(self):
        d = dict(_dashboard())
        d["spaced_repetition"] = {"total_items": 20, "due_now": 15, "mature_items": 3,
                                  "next_review_items": [f"item-{i}" for i in range(10)]}
        self.assertIn("+5 more due", dv.render_html(d))

    def test_no_remainder_note_when_due_matches_shown(self):
        html = dv.render_html(_dashboard())   # fixture: due_now == len(next_review_items) == 4
        self.assertNotIn("more due", html)


if __name__ == "__main__":
    unittest.main()
