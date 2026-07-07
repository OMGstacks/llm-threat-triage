"""Cram-sheet data-model tests — the PR-11c acceptance gates.

Proves ``build_cram_sheet`` is a deterministic, teaching-content projection of a learner state:
domains ordered weakest-accuracy-first, entries ordered priority-then-recency, the closed recap is
deduplicated and capped, and — despite deliberately carrying trap/correction/rule text — it never
carries an item's choices, an isolated-key field, the learner's own selected_index, or any holdout
content (which cannot reach the journal in the first place, since ``learner_state.replay`` rejects
holdout attempts fail-closed).
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cc_spine import cram_sheet, learner_state as ls, quiz

FIXTURES = Path(__file__).resolve().parent / "fixtures"
STREAM = json.loads((FIXTURES / "synthetic_attempt_stream.json").read_text(encoding="utf-8"))
HOLDOUT = quiz.load_holdout()
FORBIDDEN_KEYS = ("choices", "correct_index", "answer_key_ref", "rationale_refs",
                 "distractor_misconceptions", "answer_key_hash", "item_hash", "selected_index",
                 "fact_ids", "expected_keywords")


def _state(now=5):
    return ls.replay(STREAM, now=now)


class DeterminismTest(unittest.TestCase):
    def test_build_is_deterministic(self):
        self.assertEqual(cram_sheet.build_cram_sheet(_state(), now=5),
                         cram_sheet.build_cram_sheet(_state(), now=5))

    def test_generated_at_day_is_the_injected_now(self):
        self.assertEqual(cram_sheet.build_cram_sheet(_state(3), now=3)["generated_at_day"], 3)


class ContentTest(unittest.TestCase):
    def test_carries_no_forbidden_field(self):
        blob = json.dumps(cram_sheet.build_cram_sheet(_state(), now=5))
        for forbidden in FORBIDDEN_KEYS:
            self.assertNotIn(f'"{forbidden}"', blob)

    def test_no_holdout_item_id_or_stem_appears(self):
        c = cram_sheet.build_cram_sheet(_state(), now=5)
        blob = json.dumps(c)
        for h in HOLDOUT:
            self.assertNotIn(h["id"], blob)
            self.assertNotIn(h["stem"], blob)

    def test_counts_match_the_journal(self):
        state = _state()
        c = cram_sheet.build_cram_sheet(state, now=5)
        self.assertEqual(c["open_count"], sum(1 for j in state["journal"] if not j["closed"]))
        self.assertEqual(c["closed_count"], sum(1 for j in state["journal"] if j["closed"]))

    def test_entries_only_come_from_open_journal_rows(self):
        state = _state()
        c = cram_sheet.build_cram_sheet(state, now=5)
        open_ids = {j["misconception_id"] for j in state["journal"] if not j["closed"]}
        seen_ids = {e["misconception_id"] for d in c["domains"] for e in d["entries"]}
        self.assertEqual(seen_ids, open_ids)


class OrderingTest(unittest.TestCase):
    def test_domains_ordered_weakest_accuracy_first(self):
        c = cram_sheet.build_cram_sheet(_state(), now=5)
        accs = [d["accuracy"] for d in c["domains"]]
        self.assertEqual(accs, sorted(accs))

    def test_unscored_domain_sorts_last_not_as_worst(self):
        # review F1: exam_strategy items all carry domain "global", which learner_state's
        # per_domain EXCLUDES (readiness accuracy excludes the exam_strategy bank). A missed
        # exam_strategy item must not be treated as "0% accuracy" and float above a genuinely
        # weak SCORED domain (D3 at 10% here, far worse than D1's 50%).
        state = {
            "readiness": {"per_domain": {"D1": {"accuracy": 0.5, "attempts": 2},
                                         "D3": {"accuracy": 0.1, "attempts": 10}}},
            "items": {}, "journal": [
                {"item_id": "D1.1.1.definition.0001", "objective": "1.1", "bank": "definition_recall",
                 "misconception_id": "cia-property-confusion", "trap": "t", "correction": "c",
                 "one_sentence_rule": "r", "recorded_at": 1, "closed": False},
                {"item_id": "D3.3.1.definition.0001", "objective": "3.1", "bank": "definition_recall",
                 "misconception_id": "physical-control-name-confusion", "trap": "t", "correction": "c",
                 "one_sentence_rule": "r", "recorded_at": 1, "closed": False},
                {"item_id": "global.0.0.strategy.0001", "objective": "0.0", "bank": "exam_strategy",
                 "misconception_id": "exam-logistics-confusion", "trap": "t", "correction": "c",
                 "one_sentence_rule": "r", "recorded_at": 1, "closed": False},
            ],
        }
        c = cram_sheet.build_cram_sheet(state, now=5)
        doms = [d["domain"] for d in c["domains"]]
        # the unscored "global" domain must sort LAST — never floated above D3 (10%, the actual
        # worst scored domain) or D1 (50%) by a fabricated 0.0.
        self.assertEqual(doms, ["D3", "D1", "global"])
        self.assertIsNone(next(d for d in c["domains"] if d["domain"] == "global")["accuracy"])

    def test_entries_ordered_priority_then_recency_then_id(self):
        # synthetic state dict exercising the sort directly (no replay dependency).
        state = {
            "readiness": {"per_domain": {"D1": {"accuracy": 0.5, "attempts": 2}}},
            "items": {
                "a": {"priority": False}, "b": {"priority": True}, "c": {"priority": False},
            },
            "journal": [
                {"item_id": "a", "objective": "1.1", "bank": "definition_recall",
                 "misconception_id": "m1", "trap": "t", "correction": "c", "one_sentence_rule": "r",
                 "recorded_at": 3, "closed": False},
                {"item_id": "b", "objective": "1.1", "bank": "definition_recall",
                 "misconception_id": "m2", "trap": "t", "correction": "c", "one_sentence_rule": "r",
                 "recorded_at": 1, "closed": False},
                {"item_id": "c", "objective": "1.1", "bank": "definition_recall",
                 "misconception_id": "m3", "trap": "t", "correction": "c", "one_sentence_rule": "r",
                 "recorded_at": 5, "closed": False},
            ],
        }
        c = cram_sheet.build_cram_sheet(state, now=5)
        ids = [e["item_id"] for e in c["domains"][0]["entries"]]
        # b is priority (floats first); then c (recorded_at=5) before a (recorded_at=3).
        self.assertEqual(ids, ["b", "c", "a"])


class UnresolvedItemTest(unittest.TestCase):
    def test_unresolved_item_id_falls_back_to_unknown_domain_not_none(self):
        # review F2: an item_id absent from quiz.load_goldset() (e.g. a persisted attempt stream
        # replayed against an updated store) must not surface a Python None as "domain" — that
        # would emit schema-invalid JSON and crash the HTML render's html.escape(None).
        state = {
            "readiness": {"per_domain": {}}, "items": {},
            "journal": [{"item_id": "no-such-item.9999", "objective": "9.9", "bank": "definition_recall",
                        "misconception_id": "m1", "trap": "t", "correction": "c",
                        "one_sentence_rule": "r", "recorded_at": 1, "closed": False}],
        }
        c = cram_sheet.build_cram_sheet(state, now=5)
        self.assertEqual(c["domains"][0]["domain"], "unknown")
        self.assertIsInstance(c["domains"][0]["domain"], str)
        # and it must be renderable without crashing (html.escape(None) would raise).
        from cc_spine import cram_sheet_view
        cram_sheet_view.render_html(c)  # must not raise


class RecapTest(unittest.TestCase):
    def test_closed_recap_is_deduplicated_by_misconception(self):
        state = {
            "readiness": {"per_domain": {}}, "items": {},
            "journal": [
                {"item_id": "a", "objective": "1.1", "bank": "definition_recall",
                 "misconception_id": "m1", "trap": "t", "correction": "c1", "one_sentence_rule": "old",
                 "recorded_at": 1, "closed": True},
                {"item_id": "b", "objective": "1.1", "bank": "definition_recall",
                 "misconception_id": "m1", "trap": "t", "correction": "c1", "one_sentence_rule": "new",
                 "recorded_at": 4, "closed": True},
            ],
        }
        c = cram_sheet.build_cram_sheet(state, now=5)
        self.assertEqual(len(c["closed_recap"]), 1)
        self.assertEqual(c["closed_recap"][0]["one_sentence_rule"], "new")

    def test_closed_recap_capped_at_five(self):
        state = {
            "readiness": {"per_domain": {}}, "items": {},
            "journal": [
                {"item_id": f"i{i}", "objective": "1.1", "bank": "definition_recall",
                 "misconception_id": f"m{i}", "trap": "t", "correction": "c", "one_sentence_rule": f"r{i}",
                 "recorded_at": i, "closed": True}
                for i in range(8)
            ],
        }
        c = cram_sheet.build_cram_sheet(state, now=5)
        self.assertEqual(len(c["closed_recap"]), 5)


class EmptyStateTest(unittest.TestCase):
    def test_no_open_entries_gives_empty_domains_list(self):
        state = {"readiness": {"per_domain": {}}, "items": {}, "journal": []}
        c = cram_sheet.build_cram_sheet(state, now=0)
        self.assertEqual(c["domains"], [])
        self.assertEqual(c["open_count"], 0)


if __name__ == "__main__":
    unittest.main()
