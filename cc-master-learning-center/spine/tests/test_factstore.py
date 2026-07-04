"""Fact-store tests — the PR-3 acceptance gates.

Zero checked-in fixture files: synthetic cards are in-memory dicts grounded on
real, stable anchors (the confirmed Exam Facts section of the blueprint and the
exam block of the objective matrix); negative cases use tmp dirs. Nothing is
ever written to spine/facts/ — the scaffold gate keeps the shipped store empty.

Fingerprints are computed at test setup via compute_fingerprint, never
hardcoded, so future edits to the reference files cannot strand this suite
(drift detection is proven by deliberate-mismatch tests instead).
"""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cc_spine import factstore, registry

SPINE = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SPINE.parent
REPO_ROOT = PROJECT_ROOT.parent
SCHEMA = json.loads((SPINE / "schemas" / "fact-card.schema.json").read_text(encoding="utf-8"))

REG = registry.Registry()


def _structured_card(**overrides) -> dict:
    """A valid active card grounded on a structured (tier-0) source."""
    card = {
        "schema_version": 1,
        "fact_id": "global.passing-score",
        "scope": "global",
        "claim_type": "numeric_fact",
        "status": "active",
        "claim": "The CC exam passing grade is 700 on a 1000-point scale.",
        "source": "cc-master-learning-center/reference/objective-matrix.json#exam.passing_score_scaled",
        "source_id": "isc2.cc-outline.2025-10",
        "source_tier": 0,
        "support": "700",
        "tags": {"domain": [], "objective": [], "topic": ["exam-logistics"]},
        "learner_visible": True,
        "answer_key_sensitive": False,
        "allowed_banks": ["exam_strategy"],
        "reviewed_by": "test-suite",
    }
    card.update(overrides)
    if "source_fingerprint" not in card:  # setdefault would compute eagerly
        card["source_fingerprint"] = factstore.compute_fingerprint(card, REPO_ROOT)
    return card


def _markdown_card(**overrides) -> dict:
    """A valid active card grounded on a markdown (tier-0) anchor."""
    card = {
        "schema_version": 1,
        "fact_id": "global.cat-delivery",
        "scope": "global",
        "claim_type": "concept",
        "status": "active",
        "claim": "The CC exam is delivered as CAT (computerized adaptive testing).",
        "source": "cc-master-learning-center/reference/cc-exam-blueprint.md#exam-facts",
        "source_id": "isc2.cc-outline.2025-10",
        "source_tier": 0,
        "support": "CAT (computerized adaptive testing)",
        "tags": {"domain": [], "objective": [], "topic": ["exam-logistics"]},
        "learner_visible": True,
        "answer_key_sensitive": False,
        "allowed_banks": ["exam_strategy"],
        "reviewed_by": "test-suite",
    }
    card.update(overrides)
    if "source_fingerprint" not in card:  # setdefault would compute eagerly
        card["source_fingerprint"] = factstore.compute_fingerprint(card, REPO_ROOT)
    return card


def _store_with(*cards) -> factstore.FactStore:
    """An in-memory store seeded with the given cards (empty facts dir on disk)."""
    fs = factstore.FactStore()
    for card in cards:
        fs.add(card)
    return fs


def _item(**overrides) -> dict:
    item = {
        "id": "global.exam.def.0001",
        "bank": "exam_strategy",
        "grounding": "factstore",
        "fact_ids": ["global.passing-score"],
        "expected_keywords": ["700"],
    }
    item.update(overrides)
    return item


class EmptyStoreTest(unittest.TestCase):
    """Gate 1: the empty shipped store and empty goldset validate."""

    def test_empty_shipped_store_validates(self):
        fs = factstore.FactStore()
        self.assertEqual(fs.cards, {})
        rep = factstore.validate_store(fs, REG)
        self.assertTrue(rep["ok"], rep["errors"])

    def test_empty_goldset_items_validate(self):
        goldset = json.loads((SPINE / "gold" / "goldset.json").read_text(encoding="utf-8"))
        rep = factstore.validate_items(factstore.FactStore(), goldset["items"])
        self.assertTrue(rep["ok"], rep["errors"])


class SyntheticCardTest(unittest.TestCase):
    """Gate 2: valid synthetic cards pass; schema/policy tables are enforced."""

    def test_structured_card_with_valid_source_passes(self):
        self.assertEqual(factstore.validate_card(_structured_card(), REG), [])

    def test_markdown_card_with_valid_anchor_passes(self):
        self.assertEqual(factstore.validate_card(_markdown_card(), REG), [])

    def test_required_fields_match_schema(self):
        self.assertEqual(set(factstore.REQUIRED_FIELDS), set(SCHEMA["required"]))

    def test_fact_id_pattern_and_scope_prefix_enforced(self):
        bad_pattern = _structured_card(fact_id="global.Bad_ID")
        self.assertTrue(any("does not match" in e
                            for e in factstore.validate_card(bad_pattern, REG)))
        bad_prefix = _structured_card(fact_id="D4.passing-score")
        self.assertTrue(any("prefix does not match scope" in e
                            for e in factstore.validate_card(bad_prefix, REG)))

    def test_source_tier_required_and_valid(self):
        for bad_tier in (9, -1, "0"):
            with self.subTest(tier=bad_tier):
                card = _structured_card(source_tier=bad_tier,
                                        source_fingerprint="sha256:" + "0" * 64)
                self.assertTrue(any("source_tier must be an integer 0-4" in e
                                    for e in factstore.validate_card(card, REG)))

    def test_allowed_banks_must_exist_in_banks_json(self):
        card = _structured_card(allowed_banks=["no_such_bank"])
        self.assertTrue(any("not a known bank" in e
                            for e in factstore.validate_card(card, REG)))

    def test_claim_type_must_exist_in_claim_types(self):
        card = _structured_card(claim_type="detector")  # an OSAI type, not a CC one
        self.assertTrue(any("unknown claim_type" in e
                            for e in factstore.validate_card(card, REG)))

    def test_registry_rejects_bad_domain_objective_and_source_id(self):
        card = _structured_card(
            tags={"domain": ["D9"], "objective": ["9.9"], "topic": []})
        errs = factstore.validate_card(card, REG)
        self.assertTrue(any("not a known domain" in e for e in errs))
        self.assertTrue(any("not in the objective matrix" in e for e in errs))
        card = _structured_card(source_id="nope.unknown")
        self.assertTrue(any("not in source-registry.json" in e
                            for e in factstore.validate_card(card, REG)))

    def test_source_tier_must_match_registry_tier(self):
        card = _structured_card(source_tier=1)  # registry says the ISC2 outline is tier 0
        card["source_fingerprint"] = factstore.compute_fingerprint(card, REPO_ROOT)
        self.assertTrue(any("!= registry tier" in e
                            for e in factstore.validate_card(card, REG)))

    def test_valid_objective_and_extension_tags_pass(self):
        card = _structured_card(
            tags={"domain": [], "objective": ["1.1", "global.ai-security"], "topic": []})
        self.assertEqual(factstore.validate_card(card, REG), [])


class ProvenanceFailureTest(unittest.TestCase):
    """Gate 3: missing/bad source paths fail closed."""

    def test_missing_source_file_fails(self):
        card = _structured_card(
            source="cc-master-learning-center/reference/does-not-exist.json#a.b",
            source_fingerprint="sha256:" + "0" * 64)
        self.assertTrue(any("provenance source unresolved" in e
                            for e in factstore.validate_card(card, REG)))

    def test_bad_json_path_fails(self):
        card = _structured_card(
            source="cc-master-learning-center/reference/objective-matrix.json#exam.no_such_field",
            source_fingerprint="sha256:" + "0" * 64)
        self.assertTrue(any("provenance source unresolved" in e
                            for e in factstore.validate_card(card, REG)))

    def test_missing_markdown_anchor_fails(self):
        card = _markdown_card(
            source="cc-master-learning-center/reference/cc-exam-blueprint.md#no-such-anchor",
            source_fingerprint="sha256:" + "0" * 64)
        self.assertTrue(any("anchor not found" in e
                            for e in factstore.validate_card(card, REG)))

    def test_markdown_support_span_absent_fails(self):
        card = _markdown_card(support="this span does not appear in the section")
        card["source_fingerprint"] = factstore.compute_fingerprint(card, REPO_ROOT)
        self.assertTrue(any("support span is not present" in e
                            for e in factstore.validate_card(card, REG)))

    def test_duplicate_markdown_anchor_fails_closed(self):
        # Anchors must be unique after slug normalization — a citation must never
        # silently pick between two sections (reviewer P0).
        md = "## Dup\n\nfirst section body\n\n## Dup\n\nsecond section body\n"
        with self.assertRaises(ValueError):
            factstore._section_text(md, "dup")
        # And through the full card path: a card citing a duplicated anchor fails.
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        ref = root / "cc-master-learning-center" / "reference"
        ref.mkdir(parents=True)
        (ref / "dup.md").write_text(md, encoding="utf-8")
        card = _markdown_card(
            source="cc-master-learning-center/reference/dup.md#dup",
            support="first section body",
            source_fingerprint="sha256:" + "0" * 64)
        errs = factstore.validate_card(card, REG, root=root)
        self.assertTrue(any("duplicate markdown anchor" in e for e in errs), errs)

    def test_unique_anchor_still_resolves(self):
        md = "## Only\n\nbody text\n\n## Other\n\nmore\n"
        self.assertEqual(factstore._section_text(md, "only"), "body text")

    def test_source_path_cannot_escape_repo_root(self):
        card = _structured_card(
            source="../outside.json#a",
            source_fingerprint="sha256:" + "0" * 64)
        errs = factstore.validate_card(card, REG)
        self.assertTrue(any("provenance source unresolved" in e for e in errs), errs)

    def test_source_path_cannot_reference_absolute_path(self):
        card = _structured_card(
            source="/etc/passwd#a",
            source_fingerprint="sha256:" + "0" * 64)
        errs = factstore.validate_card(card, REG)
        self.assertTrue(any("provenance source unresolved" in e for e in errs), errs)

    def test_source_extension_not_allowed_fails(self):
        # The Makefile exists, but only .json/.md sources are allowed.
        card = _structured_card(
            source="cc-master-learning-center/spine/Makefile#a",
            source_fingerprint="sha256:" + "0" * 64)
        errs = factstore.validate_card(card, REG)
        self.assertTrue(any("unsupported source kind" in e for e in errs), errs)


class DriftTest(unittest.TestCase):
    """Gate 4: fingerprint drift fails; canonical equality is exact, not fuzzy."""

    def test_changed_fingerprint_fails(self):
        card = _structured_card(source_fingerprint="sha256:" + "a" * 64)
        self.assertTrue(any("source_fingerprint mismatch" in e
                            for e in factstore.validate_card(card, REG)))

    def test_structured_support_canonical_whitespace_passes(self):
        # Benign whitespace normalization: "  700 " canonicalizes to "700".
        card = _structured_card(support="  700 ")
        card["source_fingerprint"] = factstore.compute_fingerprint(card, REPO_ROOT)
        self.assertEqual(factstore.validate_card(card, REG), [])

    def test_structured_support_wrong_value_fails(self):
        card = _structured_card(
            support="710",
            claim="The CC exam passing grade is 710 on a 1000-point scale.")
        card["source_fingerprint"] = factstore.compute_fingerprint(card, REPO_ROOT)
        self.assertTrue(any("drift/mismatch" in e
                            for e in factstore.validate_card(card, REG)))

    def test_source_edit_detected_as_drift(self):
        # Copy the real matrix into a tmp root, then edit the grounded value.
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        ref = root / "cc-master-learning-center" / "reference"
        ref.mkdir(parents=True)
        matrix = json.loads(
            (PROJECT_ROOT / "reference" / "objective-matrix.json").read_text(encoding="utf-8"))
        card = _structured_card()  # fingerprint computed against the REAL source
        matrix["exam"]["passing_score_scaled"] = 710  # the source drifts
        (ref / "objective-matrix.json").write_text(json.dumps(matrix), encoding="utf-8")
        errs = factstore.validate_card(card, REG, root=root)
        self.assertTrue(any("drift/mismatch" in e for e in errs), errs)
        self.assertTrue(any("source_fingerprint mismatch" in e for e in errs), errs)


class StoreInvariantTest(unittest.TestCase):
    """Gates 5-6: duplicate fact_ids and tombstone lifecycle."""

    def test_duplicate_fact_id_across_files_fails(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        card = _structured_card()
        for name in ("a.json", "b.json"):
            (Path(tmp.name) / name).write_text(json.dumps([card]), encoding="utf-8")
        fs = factstore.FactStore(facts_dir=tmp.name)
        rep = factstore.validate_store(fs, REG)
        self.assertFalse(rep["ok"])
        self.assertTrue(any("duplicate fact_id" in e for e in rep["errors"]))

    def test_deprecated_without_deprecated_by_fails(self):
        dep = _structured_card(status="deprecated", deprecation_reason="superseded")
        rep = factstore.validate_store(_store_with(dep), REG)
        self.assertTrue(any("must set deprecated_by" in e for e in rep["errors"]))

    def test_deprecated_without_deprecation_reason_fails(self):
        succ = _markdown_card()
        dep = _structured_card(status="deprecated", deprecated_by=succ["fact_id"])
        rep = factstore.validate_store(_store_with(dep, succ), REG)
        self.assertTrue(any("non-empty deprecation_reason" in e for e in rep["errors"]))

    def test_deprecated_by_must_resolve(self):
        dep = _structured_card(status="deprecated", deprecated_by="global.ghost",
                               deprecation_reason="superseded")
        rep = factstore.validate_store(_store_with(dep), REG)
        self.assertTrue(any("does not resolve" in e for e in rep["errors"]))

    def test_valid_tombstone_passes(self):
        succ = _markdown_card()
        dep = _structured_card(status="deprecated", deprecated_by=succ["fact_id"],
                               deprecation_reason="superseded by the markdown card")
        rep = factstore.validate_store(_store_with(dep, succ), REG)
        self.assertTrue(rep["ok"], rep["errors"])


class GroundingLifecycleTest(unittest.TestCase):
    """Gate 7 + unsupported_claim_guard: item-level grounding rules."""

    def test_draft_card_cannot_ground_active_item(self):
        fs = _store_with(_structured_card(status="draft"))
        errs = factstore.validate_item(fs, _item())
        self.assertTrue(any("only active cards may ground" in e for e in errs))

    def test_deprecated_card_cannot_ground_active_item(self):
        fs = _store_with(_structured_card(status="deprecated",
                                          deprecated_by="global.cat-delivery",
                                          deprecation_reason="superseded"))
        errs = factstore.validate_item(fs, _item())
        self.assertTrue(any("only active cards may ground" in e for e in errs))

    def test_active_item_with_mixed_active_and_draft_cards_fails(self):
        fs = _store_with(_structured_card(), _markdown_card(status="draft"))
        item = _item(fact_ids=["global.passing-score", "global.cat-delivery"])
        errs = factstore.validate_item(fs, item)
        self.assertTrue(any("draft" in e for e in errs), errs)

    def test_item_with_no_fact_ids_fails(self):
        fs = _store_with(_structured_card())
        errs = factstore.validate_item(fs, _item(fact_ids=[]))
        self.assertTrue(any("no fact_ids" in e for e in errs))

    def test_unknown_fact_id_fails_item(self):
        fs = _store_with(_structured_card())
        errs = factstore.validate_item(fs, _item(fact_ids=["global.ghost"]))
        self.assertTrue(any("unknown fact_id" in e for e in errs))

    def test_unsupported_expected_keyword_fails_item(self):
        fs = _store_with(_structured_card())
        errs = factstore.validate_item(fs, _item(expected_keywords=["quantum"]))
        self.assertTrue(any("not supported by any cited fact card" in e for e in errs))


class EligibilityTest(unittest.TestCase):
    """Gate 8: claim_type -> bank eligibility, loaded from banks.json."""

    def test_mnemonic_card_cannot_be_authorised_for_scenario_application(self):
        card = _markdown_card(claim_type="mnemonic",
                              allowed_banks=["scenario_application"])
        self.assertTrue(any("not eligible for bank" in e
                            for e in factstore.validate_card(card, REG)))

    def test_item_citing_mnemonic_card_for_scenario_bank_fails(self):
        card = _markdown_card(claim_type="mnemonic", allowed_banks=["definition_recall"])
        fs = _store_with(card)
        item = _item(bank="scenario_application", fact_ids=[card["fact_id"]],
                     expected_keywords=[])
        errs = factstore.validate_item(fs, item)
        self.assertTrue(any("not allowed for bank" in e for e in errs))

    def test_bank_eligibility_matrix_loaded_from_banks_json(self):
        banks = json.loads((SPINE / "banks" / "banks.json").read_text(encoding="utf-8"))
        policy = factstore._bank_policy()
        self.assertEqual(policy["known_banks"], set(banks["banks"]))
        for ctype, allowed in banks["claim_type_eligibility"].items():
            self.assertEqual(policy["eligibility"][ctype], set(allowed))


class AnswerKeySafetyTest(unittest.TestCase):
    """Gates 9-11: quarantine, residual secrets, tightened sensitive_override."""

    def test_answer_key_sensitive_card_quarantined_from_learner_bank(self):
        card = _structured_card(answer_key_sensitive=True)
        self.assertTrue(any("without sensitive_override" in e
                            for e in factstore.validate_card(card, REG)))

    def test_learner_visible_false_card_quarantined(self):
        card = _structured_card(learner_visible=False)
        self.assertTrue(any("without sensitive_override" in e
                            for e in factstore.validate_card(card, REG)))

    def test_sensitive_override_requires_reason_reviewer_and_explicit_bank(self):
        # Grant path: override + reason + reviewer + date -> no quarantine errors.
        good = _structured_card(
            answer_key_sensitive=True, sensitive_override=True,
            override_reason="grader-side numeric key, reviewed for exam_strategy only",
            last_reviewed="2026-07-04")
        self.assertEqual(factstore.validate_card(good, REG), [])
        # Deny path: override without a reason (or date) is NOT clearance.
        for missing in ("override_reason", "last_reviewed"):
            with self.subTest(missing=missing):
                card = copy.deepcopy(good)
                del card[missing]
                errs = factstore.validate_card(card, REG)
                self.assertTrue(any(f"requires" in e and missing in e for e in errs), errs)

    def test_override_never_clears_residual_secrets(self):
        card = _markdown_card(
            claim="Ask admin@example.com about CAT (computerized adaptive testing).",
            answer_key_sensitive=True, sensitive_override=True,
            override_reason="attempted blanket clearance", last_reviewed="2026-07-04")
        errs = factstore.validate_card(card, REG)
        self.assertTrue(any("residual scan" in e for e in errs), errs)

    def test_residual_secret_in_claim_fails(self):
        card = _markdown_card(
            claim="Email admin@example.com — CAT (computerized adaptive testing).")
        errs = factstore.validate_card(card, REG)
        self.assertTrue(any("residual scan" in e for e in errs))

    def test_for_bank_excludes_sensitive_cards(self):
        safe = _structured_card()
        sensitive = _markdown_card(answer_key_sensitive=True)
        fs = _store_with(safe, sensitive)
        visible = {c["fact_id"] for c in fs.for_bank("exam_strategy")}
        self.assertIn(safe["fact_id"], visible)
        self.assertNotIn(sensitive["fact_id"], visible)
        # Grader-side access still possible, explicitly.
        graderside = {c["fact_id"] for c in fs.for_bank("exam_strategy", include_sensitive=True)}
        self.assertIn(sensitive["fact_id"], graderside)

    def test_ground_learner_output_excludes_answer_key_sensitive_support(self):
        safe = _structured_card()
        sensitive = _markdown_card(answer_key_sensitive=True)
        fs = _store_with(safe, sensitive)
        result = factstore.ground(fs, _item(
            fact_ids=[safe["fact_id"], sensitive["fact_id"]]))
        self.assertNotIn(sensitive["claim"], result["answer"])
        self.assertEqual([c["fact_id"] for c in result["citations"]], [safe["fact_id"]])

    def test_ground_learner_output_excludes_learner_visible_false_support(self):
        safe = _structured_card()
        hidden = _markdown_card(learner_visible=False)
        fs = _store_with(safe, hidden)
        result = factstore.ground(fs, _item(
            fact_ids=[safe["fact_id"], hidden["fact_id"]]))
        self.assertNotIn(hidden["claim"], result["answer"])
        self.assertEqual([c["fact_id"] for c in result["citations"]], [safe["fact_id"]])


class RetrievalStabilityTest(unittest.TestCase):
    """Gates 12-13: deterministic grounding; adding a card changes nothing."""

    def test_adding_card_does_not_change_existing_citations(self):
        fs = _store_with(_structured_card(), _markdown_card())
        items = [
            _item(),
            _item(id="global.exam.def.0002", fact_ids=["global.cat-delivery"],
                  expected_keywords=["CAT"]),
        ]
        before = [factstore.ground(fs, item) for item in items]
        newcard = copy.deepcopy(_structured_card())
        newcard["fact_id"] = "global.duration"
        fs.add(newcard)
        after = [factstore.ground(fs, item) for item in items]
        self.assertEqual(json.dumps(before, sort_keys=True),
                         json.dumps(after, sort_keys=True))

    def test_ground_is_deterministic_and_missing_id_fails_cleanly(self):
        fs = _store_with(_structured_card())
        a = factstore.ground(fs, _item())
        b = factstore.ground(fs, _item())
        self.assertEqual(a, b)
        self.assertEqual(a["citations"][0]["tier"], factstore.FACT_TIER)
        missing = factstore.ground(fs, _item(fact_ids=["global.ghost"]))
        self.assertEqual(missing["answer"], "")
        self.assertEqual(missing["citations"], [])

    def test_ground_preserves_requested_fact_id_order(self):
        fs = _store_with(_structured_card(), _markdown_card())
        result = factstore.ground(fs, _item(
            fact_ids=["global.cat-delivery", "global.passing-score"]))
        self.assertEqual([c["fact_id"] for c in result["citations"]],
                         ["global.cat-delivery", "global.passing-score"])


class IPBoundaryIntegrationTest(unittest.TestCase):
    """Net-new vs OSAI: support spans pass the PR-2 IP guard inside validate_card."""

    def test_overlong_support_span_fails_card(self):
        # Tier 0 allows 20 words max; 21 words must fail the card.
        card = _structured_card(support=" ".join(["word"] * 21),
                                source_fingerprint="sha256:" + "0" * 64)
        errs = factstore.validate_card(card, REG)
        self.assertTrue(any("limit is 20" in e for e in errs), errs)

    def test_full_mcq_support_fails_card(self):
        card = _markdown_card(support="Which port? A) 22 B) 80 C) 443 D) 3389",
                              source_fingerprint="sha256:" + "0" * 64)
        errs = factstore.validate_card(card, REG)
        self.assertTrue(any("multiple-choice" in e for e in errs), errs)


class NotesGroundingTest(unittest.TestCase):
    """Gate 15: only reviewed/promoted notes may ground fact cards."""

    def _note_root(self, status: str):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        notes = root / "cc-master-learning-center" / "notes"
        notes.mkdir(parents=True)
        (notes / "D4.md").write_text(
            "---\n"
            "source_doc_id: d4-transcript\n"
            "source_tier: 3\n"
            "dictionary_version: 1.0.0\n"
            "outline_version: 2025-10\n"
            "reviewed_by: OMGstacks\n"
            f"status: {status}\n"
            "corrections_applied: []\n"
            "corrections_flagged: []\n"
            "---\n\n"
            "## Common Ports\n\n"
            "SSH uses TCP port 22.\n",
            encoding="utf-8")
        # A tmp source registry carrying a tier-2 cleaned-notes source id.
        sources = {"schema_version": "1.0.0", "sources": [
            {"id": "notes.d4", "tier": 2, "type": "cleaned_notes", "status": "current",
             "topic": "domain-4", "source_url": "local", "retrieved_at": "2026-07-04"},
        ]}
        reg_path = root / "source-registry.json"
        reg_path.write_text(json.dumps(sources), encoding="utf-8")
        reg = registry.Registry(sources_path=reg_path)
        return root, reg

    def _note_card(self, root) -> dict:
        card = {
            "schema_version": 1,
            "fact_id": "D4.port-ssh",
            "scope": "D4",
            "claim_type": "definition",
            "status": "active",
            "claim": "SSH uses TCP port 22 for encrypted remote administration.",
            "source": "cc-master-learning-center/notes/D4.md#common-ports",
            "source_id": "notes.d4",
            "source_tier": 2,
            "support": "SSH uses TCP port 22.",
            "tags": {"domain": ["D4"], "objective": ["4.1"], "topic": ["ports"]},
            "learner_visible": True,
            "answer_key_sensitive": False,
            "allowed_banks": ["definition_recall"],
            "reviewed_by": "test-suite",
        }
        card["source_fingerprint"] = factstore.compute_fingerprint(card, root)
        return card

    def test_card_grounded_on_reviewed_note_passes(self):
        root, reg = self._note_root("reviewed")
        self.assertEqual(factstore.validate_card(self._note_card(root), reg, root=root), [])

    def test_card_grounded_on_promoted_note_passes(self):
        root, reg = self._note_root("promoted")
        self.assertEqual(factstore.validate_card(self._note_card(root), reg, root=root), [])

    def test_card_grounded_on_draft_note_fails(self):
        root, reg = self._note_root("draft")
        errs = factstore.validate_card(self._note_card(root), reg, root=root)
        self.assertTrue(any("only reviewed/promoted notes may ground" in e for e in errs), errs)

    def test_card_grounded_on_unknown_note_status_fails_closed(self):
        root, reg = self._note_root("mystery")
        errs = factstore.validate_card(self._note_card(root), reg, root=root)
        self.assertTrue(any("unknown status" in e for e in errs), errs)


class FreezeTest(unittest.TestCase):
    """Gate 16: freeze rewrites fingerprints only; refuses unresolved support."""

    def _tmp_facts(self, card) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        facts = Path(tmp.name)
        (facts / "cards.json").write_text(json.dumps([card]), encoding="utf-8")
        return facts

    def test_freeze_rewrites_fingerprints_in_tmp_dir(self):
        card = _structured_card(source_fingerprint="sha256:" + "0" * 64)
        facts = self._tmp_facts(card)
        n = factstore.freeze(facts_dir=facts, root=REPO_ROOT)
        self.assertEqual(n, 1)
        frozen = json.loads((facts / "cards.json").read_text(encoding="utf-8"))[0]
        self.assertEqual(frozen["source_fingerprint"],
                         factstore.compute_fingerprint(frozen, REPO_ROOT))

    def test_freeze_changes_only_source_fingerprint_fields(self):
        # Checksum-style proof: the whole card is identical except the fingerprint.
        card = _structured_card(source_fingerprint="sha256:" + "0" * 64)
        facts = self._tmp_facts(card)
        factstore.freeze(facts_dir=facts, root=REPO_ROOT)
        frozen = json.loads((facts / "cards.json").read_text(encoding="utf-8"))[0]
        before = {k: v for k, v in card.items() if k != "source_fingerprint"}
        after = {k: v for k, v in frozen.items() if k != "source_fingerprint"}
        self.assertEqual(json.dumps(before, sort_keys=True),
                         json.dumps(after, sort_keys=True))
        self.assertNotEqual(frozen["source_fingerprint"], card["source_fingerprint"])

    def test_freeze_refuses_when_support_no_longer_resolves(self):
        card = _structured_card(
            source="cc-master-learning-center/reference/does-not-exist.json#a",
            source_fingerprint="sha256:" + "0" * 64)
        facts = self._tmp_facts(card)
        with self.assertRaises(Exception):
            factstore.freeze(facts_dir=facts, root=REPO_ROOT)


if __name__ == "__main__":
    unittest.main()
