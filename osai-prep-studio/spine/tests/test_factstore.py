"""Structured fact store — the PR1 acceptance teeth (25-fact-store-epic.md).

Proves, offline: the shipped store validates against its authoritative sources; every
fact-grounded pilot item cites approved fact_ids and grades 1.0; unsupported claims,
leaked secrets, sensitive misuse, draft/deprecated grounding, source drift, duplicate
ids, and silent renames all FAIL; and — the epic's whole justification — adding a fact
card does NOT change an existing item's citation (retrieval stability).
"""

import copy
import json

import pytest

from osai_spine import factstore
from osai_spine.factstore import (
    FactStore, validate_card, validate_item, validate_items, validate_store,
)
from osai_spine.goldset import GoldSetRunner, load_goldset
from osai_spine.taxonomy import TaxonomyRegistry

REG = TaxonomyRegistry()


def _fg_items():
    return [i for i in load_goldset()["items"] if factstore.is_fact_grounded(i)]


# --- shipped store + items validate (the CI gate) ------------------------- #

def test_shipped_store_validates_against_sources():
    rep = validate_store(FactStore(), REG)
    assert rep["ok"], rep["errors"]


def test_shipped_fact_grounded_items_validate():
    fs = FactStore()
    rep = validate_items(fs, load_goldset()["items"])
    assert rep["ok"], rep["errors"]


def test_pilot_items_grade_pass_1_0():
    report = GoldSetRunner().run()
    failed = {f["id"] for f in report["failures"]}
    ids = [i["id"] for i in _fg_items()]
    assert ids, "expected fact-grounded pilot items"
    assert not (set(ids) & failed), f"fact-grounded items failing: {set(ids) & failed}"
    # and the two target banks are still hard-gated at 1.0
    assert report["gate"]["lab_grounded_pass_rate"]
    assert report["gate"]["architecture_reasoning_pass_rate"]


# --- retrieval stability: the epic's justification ------------------------ #

def test_adding_a_card_does_not_change_existing_citations():
    fs = FactStore()
    items = _fg_items()
    before = {i["id"]: factstore.ground(fs, i)["citations"] for i in items}
    # inject a brand-new, unrelated (but valid) card
    newcard = copy.deepcopy(fs.get("L03.detector"))
    newcard["fact_id"] = "L03.detector.NEW"
    fs.add(newcard)
    after = {i["id"]: factstore.ground(fs, i)["citations"] for i in items}
    assert before == after
    assert json.dumps(before, sort_keys=True) == json.dumps(after, sort_keys=True)


# --- unsupported claims fail --------------------------------------------- #

def test_unsupported_expected_keyword_fails_item():
    fs = FactStore()
    item = {"id": "X", "bank": "lab_grounded", "grounding": "factstore",
            "fact_ids": ["L03.detector"], "expected_keywords": ["vector_store_probe"]}
    errs = validate_item(fs, item)
    assert any("not supported by any cited fact card" in e for e in errs), errs


def test_fact_grounded_item_without_fact_ids_fails():
    fs = FactStore()
    item = {"id": "X", "bank": "lab_grounded", "grounding": "factstore",
            "fact_ids": [], "expected_keywords": []}
    assert any("no fact_ids" in e for e in validate_item(fs, item))


def test_cited_fact_id_not_allowed_for_bank_fails():
    fs = FactStore()   # L03.evidence-log is allowed only for lab_grounded
    item = {"id": "X", "bank": "architecture_reasoning", "grounding": "factstore",
            "fact_ids": ["L03.evidence-log"], "expected_keywords": []}
    assert any("not allowed for bank" in e for e in validate_item(fs, item))


def test_unknown_fact_id_fails():
    fs = FactStore()
    item = {"id": "X", "bank": "lab_grounded", "grounding": "factstore",
            "fact_ids": ["NOPE.x"], "expected_keywords": []}
    assert any("unknown fact_id" in e for e in validate_item(fs, item))


# --- lifecycle: draft/deprecated cannot ground a live item --------------- #

@pytest.mark.parametrize("status", ["draft", "deprecated"])
def test_draft_or_deprecated_card_cannot_ground_live_item(status):
    fs = FactStore()
    card = copy.deepcopy(fs.get("L03.detector"))
    card["fact_id"] = f"L03.{status}"
    card["status"] = status
    fs.add(card)
    item = {"id": "X", "bank": "lab_grounded", "grounding": "factstore",
            "fact_ids": [f"L03.{status}"], "expected_keywords": ["encoded_injection_payload"]}
    assert any(status in e for e in validate_item(fs, item))


def test_deprecated_card_needs_tombstone_no_silent_rename():
    fs = FactStore()
    card = copy.deepcopy(fs.get("L03.module"))
    card["fact_id"] = "L03.module.old"
    card["status"] = "deprecated"          # no deprecated_by -> silent rename
    fs.add(card)
    rep = validate_store(fs, REG)
    assert any("deprecated_by" in e for e in rep["errors"])


def test_deprecated_by_must_resolve():
    fs = FactStore()
    card = copy.deepcopy(fs.get("L03.module"))
    card["fact_id"] = "L03.module.old"
    card["status"] = "deprecated"
    card["deprecated_by"] = "does.not.exist"
    fs.add(card)
    rep = validate_store(fs, REG)
    assert any("does not resolve" in e for e in rep["errors"])


# --- answer-key / secret leakage fails ------------------------------------ #

def test_flag_in_a_card_is_rejected():
    fs = FactStore()
    card = copy.deepcopy(fs.get("L03.detector"))
    card["claim"] = card["claim"] + " flag OSAI{L03-leaked}"
    assert any("flag token" in e or "residual" in e for e in validate_card(card, REG))


def test_secret_in_a_card_is_rejected():
    fs = FactStore()
    card = copy.deepcopy(fs.get("L03.detector"))
    card["claim"] = card["claim"] + " contact victim.doe@acme.co"
    assert any("residual" in e for e in validate_card(card, REG))


def test_sensitive_card_quarantined_from_learner_bank_without_override():
    fs = FactStore()
    card = copy.deepcopy(fs.get("L03.detector"))
    card["answer_key_sensitive"] = True                # sensitive, no override
    errs = validate_card(card, REG)
    assert any("without sensitive_override" in e for e in errs)
    card["sensitive_override"] = True                  # explicit allow clears it
    assert not any("sensitive_override" in e for e in validate_card(card, REG))


# --- structural (not substring) provenance + drift detection -------------- #

def test_structural_equality_not_mere_substring():
    # a VALID-but-wrong detector (right catalog, wrong lab) must fail structurally
    fs = FactStore()
    card = copy.deepcopy(fs.get("L03.detector"))
    card["support"] = "vector_store_probe"   # a real detector, but not L03's
    errs = validate_card(card, REG)
    assert any("!= source value" in e or "does not mention" in e for e in errs)


def test_source_fingerprint_drift_is_detected():
    fs = FactStore()
    card = copy.deepcopy(fs.get("L03.detector"))
    card["source_fingerprint"] = "sha256:" + "0" * 64
    assert any("fingerprint mismatch" in e for e in validate_card(card, REG))


def test_missing_markdown_anchor_fails():
    fs = FactStore()
    card = copy.deepcopy(fs.get("global.grader-owns-grading"))
    card["source"] = "reference/osai-studio-architecture.md#no-such-anchor"
    assert any("anchor" in e or "unresolved" in e for e in validate_card(card, REG))


def test_markdown_support_span_must_be_present():
    fs = FactStore()
    card = copy.deepcopy(fs.get("global.grader-owns-grading"))
    card["support"] = "this exact sentence is not in the source section at all"
    assert any("support span is not present" in e for e in validate_card(card, REG))


def test_missing_source_file_fails():
    fs = FactStore()
    card = copy.deepcopy(fs.get("L03.detector"))
    card["source"] = "osai-prep-studio/spine/labs/NOPE.json#two_signal_grading.detector_required"
    assert any("unresolved" in e for e in validate_card(card, REG))


# --- store-level invariants ----------------------------------------------- #

def test_duplicate_fact_ids_across_files_fail(tmp_path):
    real = FactStore().get("L03.module")
    (tmp_path / "a.json").write_text(json.dumps([real]))
    (tmp_path / "b.json").write_text(json.dumps([real]))
    rep = validate_store(FactStore(facts_dir=tmp_path), REG)
    assert any("duplicate fact_id" in e for e in rep["errors"])


def test_bank_eligibility_by_claim_type_enforced():
    fs = FactStore()
    card = copy.deepcopy(fs.get("L03.evidence-log"))   # evidence_path
    card["allowed_banks"] = ["architecture_reasoning"]  # not eligible for evidence_path
    assert any("not eligible for bank" in e for e in validate_card(card, REG))


def test_all_labs_except_l13_have_fact_cards():
    import glob
    fs = FactStore()
    scopes = {c["scope"] for c in fs.cards.values()}
    labs = {f.split("/")[-1][:-5] for f in glob.glob("labs/*.json")}
    missing = {lid for lid in labs if lid != "L13" and lid not in scopes}
    assert not missing, f"labs without fact cards: {missing}"
    assert "L13" not in scopes, "L13 must be excluded per the standing constraint"


def test_capacity_supports_bank_targets():
    cov = factstore.coverage_report(FactStore())
    cap = cov["estimated_item_capacity"]
    assert cap["architecture_reasoning"]["supports_target"], cap["architecture_reasoning"]
    assert cap["lab_grounded"]["supports_target"], cap["lab_grounded"]


def test_expanded_store_has_no_sensitive_or_draft_cards():
    cov = factstore.coverage_report(FactStore())
    assert cov["sensitive"] == 0
    assert cov["by_status"] == {"active": cov["cards_total"]}


def test_ground_missing_fact_id_fails_cleanly_not_crash():
    fs = FactStore()
    item = {"id": "X", "bank": "lab_grounded", "grounding": "factstore",
            "fact_ids": ["does.not.exist"], "expected_keywords": ["encoded_injection_payload"]}
    res = factstore.ground(fs, item)          # must not raise
    assert res["citations"] == [] and res["answer"] == ""


def test_ground_is_deterministic_and_cited():
    fs = FactStore()
    item = {"id": "X", "bank": "lab_grounded", "grounding": "factstore",
            "fact_ids": ["L03.detector", "L03.owasp"], "expected_keywords": []}
    r1, r2 = factstore.ground(fs, item), factstore.ground(fs, item)
    assert r1 == r2 and r1["citations"] and not r1["refused"] and not r1["abstained"]
    assert all(c["tier"] == factstore.FACT_TIER for c in r1["citations"])
