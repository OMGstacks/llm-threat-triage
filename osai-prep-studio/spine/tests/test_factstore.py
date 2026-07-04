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
    assert "L20" in scopes, "L20 (blue-team capstone) must be represented"


def test_capacity_targets_reachable():
    cov = factstore.coverage_report(FactStore())
    cap = cov["estimated_item_capacity"]
    # architecture_reasoning clears its target at the conservative 1-item/card floor;
    # lab_grounded reaches its target above the floor (<=2x phrasings). Both reachable.
    assert cap["architecture_reasoning"]["meets_floor_target"], cap["architecture_reasoning"]
    assert cap["lab_grounded"]["reachable_target"], cap["lab_grounded"]


def test_expanded_store_has_no_sensitive_or_draft_cards():
    cov = factstore.coverage_report(FactStore())
    assert cov["sensitive"] == 0
    assert cov["by_status"] == {"active": cov["cards_total"]}


def test_all_fact_grounded_items_validate():
    fs = FactStore()
    items = load_goldset()["items"]
    fg = [i for i in items if factstore.is_fact_grounded(i)]
    assert len(fg) >= 80, f"expected the grown fact-grounded set, got {len(fg)}"
    rep = factstore.validate_items(fs, items)
    assert rep["ok"], rep["errors"]


def test_no_near_duplicate_prompts_in_grounded_banks():
    """The fact-store target banks (lab_grounded, architecture_reasoning) stay fully
    near-dup clean, and NO fact-grounded item (in any bank, incl. re-routed framework_recall
    ones) is a near-dup of another item in its bank. Legacy tutor-grounded framework_recall
    items are out of scope here (rewording them would destabilise TF-IDF retrieval)."""
    import re
    stop = set("a an the of to in on for and or is are was be by with at as it its which "
               "what does do how where when who lab must fire this".split())
    def toks(s):
        return {w for w in re.findall(r"[a-z0-9:]+", s.lower()) if w not in stop}
    def jac(a, b):
        return len(a & b) / len(a | b) if (a | b) else 0.0
    items = load_goldset()["items"]
    # (1) the two fact-store target banks are fully clean
    for bank in ("lab_grounded", "architecture_reasoning"):
        ps = [(i["id"], toks(i["prompt"])) for i in items if i["bank"] == bank]
        dups = [(ps[x][0], ps[y][0]) for x in range(len(ps)) for y in range(x + 1, len(ps))
                if jac(ps[x][1], ps[y][1]) >= 0.7]
        assert not dups, f"near-duplicate prompts in {bank}: {dups[:5]}"
    # (2) every fact-grounded item is distinct from the rest of its bank
    for bank in {i["bank"] for i in items if factstore.is_fact_grounded(i)}:
        bi = [(i["id"], toks(i["prompt"]), factstore.is_fact_grounded(i))
              for i in items if i["bank"] == bank]
        dups = [(a[0], b[0]) for a in bi if a[2] for b in bi
                if a[0] != b[0] and jac(a[1], b[1]) >= 0.7]
        assert not dups, f"fact-grounded near-duplicate in {bank}: {dups[:5]}"


def test_scope_claim_type_is_wired_and_valid():
    from osai_spine.factstore import BANK_ELIGIBILITY, CLAIM_TYPES
    assert "scope" in CLAIM_TYPES
    assert BANK_ELIGIBILITY["scope"] == {"lab_grounded", "architecture_reasoning"}
    fs = FactStore()
    scope_cards = [c for c in fs.cards.values() if c["claim_type"] == "scope"]
    assert len(scope_cards) >= 10, f"expected authorized_scope cards, got {len(scope_cards)}"
    assert "L13.scope" not in fs.cards, "L13 must stay excluded"
    for c in scope_cards:
        assert validate_card(c, REG) == [], c["fact_id"]
        assert set(c["allowed_banks"]) <= BANK_ELIGIBILITY["scope"]


def test_framework_concept_cards_present_and_valid():
    fs = FactStore()
    ids = set(fs.cards)
    assert all(f"owasp.LLM{n:02d}" in ids for n in range(1, 11)), "OWASP LLM01-10 concept cards"
    assert all(f"agentic.T{n}" in ids for n in range(1, 16)), "OWASP Agentic T1-T15 concept cards"
    concept = [c for c in fs.cards.values() if c["claim_type"] == "concept"]
    assert len(concept) >= 25
    for c in concept:
        assert validate_card(c, REG) == [], c["fact_id"]


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
