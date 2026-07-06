"""Scaffold validator for the CC Master Learning Center (PR-1 gate).

Stdlib-only, fail-closed. Validates the PR-1 scaffold: JSON well-formedness,
objective-matrix integrity, source-registry joins, bank manifest consistency,
correction-dictionary schema, empty facts/goldset, schema headers, markdown
link resolution, and the no-raw-transcript rule. Also names the reserved
future guards so later PRs align with the roadmap.

Run from the spine directory: ``python3 -m cc_spine.scaffold_validate``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PROJECT_ROOT.parent

DOMAINS = ("D1", "D2", "D3", "D4", "D5")
EXPECTED_WEIGHTS = {"D1": 0.26, "D2": 0.10, "D3": 0.22, "D4": 0.24, "D5": 0.18}
CLAIM_TYPES = {"definition", "concept", "comparison", "procedure", "numeric_fact", "exam_trap", "mnemonic"}
BANKS = {"definition_recall", "concept_discrimination", "scenario_application", "exam_strategy"}
COVERAGE_STATUSES = {"empty", "seeded", "covered", "validated", "deprecated"}
VERIFICATION_STATUSES = {"needs_official_source_review", "official_source_reviewed"}
CONFIDENCE_LEVELS = {"low", "medium", "high", "official-current"}
VOLATILITY_LEVELS = {"stable", "transitioning", "emerging"}
CORRECTION_CONFIDENCE = {"high", "medium", "low", "never_auto"}
CORRECTION_STATUSES = {"seed", "verified", "retired"}
CONTENT_STATUS_KEYS = {"notes", "facts", "definition_cards", "scenario_items", "holdout_items"}
# Raw transcript/presentation formats must never be committed anywhere in the repo.
# PDFs are also prohibited within the cc-master-learning-center project but are
# allowed elsewhere in the repository (e.g. docs/ reference material).
FORBIDDEN_UPLOAD_SUFFIXES = {".docx", ".doc", ".pdf", ".pptx"}
_FORBIDDEN_REPO_SUFFIXES = {".docx", ".doc", ".pptx"}  # repo-root scan (P0-3)

# Guard activation status. Guards move from "reserved" to "active" as the PR
# roadmap delivers them. PR-2 activated the freshness and IP-boundary guards;
# PR-3 activated the unsupported-claim guard (factstore validate_item).
GUARD_STATUS = {
    "source_freshness_guard": "active",       # PR-2: cc_spine.sources
    "ip_boundary_guard": "active",            # PR-2: cc_spine.ipboundary
    "no_verbatim_bulk_reproduction": "active",   # PR-5: cc_spine.ipboundary.scan_verbatim
    # PR-8c: holdout items live in a physically separate lane (spine/gold/holdout.json);
    # the scaffold enforces the structural half (holdout:true, no answer-bearing field),
    # cc_spine.cli quiz validate-holdout enforces the grounding + no-leak-into-practice half.
    "holdout_leakage_guard": "active",
    # PR-8a: the quiz engine isolates answer keys into a separate grader store. The
    # scaffold enforces the structural half here (no answer-bearing field in a learner
    # item file); cc_spine.cli quiz validate enforces the grounding + hash + near-dup half.
    "answer_key_isolation_guard": "active",
    "unsupported_claim_guard": "active",      # PR-3: cc_spine.factstore validate_item
    # PR-9: learner state is personal/mutable runtime data. The scaffold fails if a real
    # state file is committed and if the learner schemas carry a PII field; the engine
    # (cc_spine.learner_state) rejects holdout attempts at runtime.
    "learner_state_isolation_guard": "active",
    # PR-10.4b: api-generated variant DRAFTS are local runtime data (.local/variant-drafts/),
    # never committed and never practice-eligible until adversarially reviewed. The scaffold
    # fails on any committed json carrying the api_generated_local marker or a draft variant
    # body; cc_spine.variant_intake enforces the intake gates + gitignored-out-dir at runtime.
    "api_draft_isolation_guard": "active",
}

# Retained for callers that only need the still-reserved set.
RESERVED_GUARDS = tuple(name for name, status in GUARD_STATUS.items() if status == "reserved")

MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def _load_json(path: Path, failures: list[str]):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        failures.append(f"{path.relative_to(PROJECT_ROOT)}: JSON parse failed: {exc}")
        return None


def _collect_source_ids(node) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "source_id" and isinstance(value, str):
                found.add(value)
            else:
                found |= _collect_source_ids(value)
    elif isinstance(node, list):
        for value in node:
            found |= _collect_source_ids(value)
    return found


def _check_json_wellformed(failures: list[str]) -> dict[Path, object]:
    parsed: dict[Path, object] = {}
    for path in sorted(PROJECT_ROOT.rglob("*.json")):
        data = _load_json(path, failures)
        if data is not None:
            parsed[path] = data
    return parsed


def _check_matrix(matrix, registry_ids: set[str], failures: list[str]) -> None:
    if matrix is None:
        failures.append("objective-matrix.json missing or unparseable")
        return

    raw = (PROJECT_ROOT / "reference" / "objective-matrix.json").read_text(encoding="utf-8")
    if "seeded-verify" in raw:
        failures.append("objective-matrix.json: forbidden combined status token 'seeded-verify' present")

    outline = matrix.get("outlines", {}).get("2025-10")
    if not outline:
        failures.append("objective-matrix.json: missing current outline '2025-10'")
        return

    domains = outline.get("domains", [])
    domain_ids = [d.get("domain_id") for d in domains]
    if domain_ids != list(DOMAINS):
        failures.append(f"objective-matrix.json: domain ids {domain_ids} != {list(DOMAINS)}")

    total = 0.0
    for domain in domains:
        did = domain.get("domain_id")
        weight = domain.get("weight")
        total += weight or 0.0
        expected = EXPECTED_WEIGHTS.get(did)
        if expected is not None and abs((weight or 0.0) - expected) > 1e-9:
            failures.append(f"objective-matrix.json: {did} weight {weight} != {expected}")
    if abs(total - 1.0) > 1e-9:
        failures.append(f"objective-matrix.json: 2025-10 weights sum {total} != 1.0")

    seen_objectives: set[str] = set()
    for domain in domains:
        for obj in domain.get("objectives", []):
            oid = obj.get("objective_id", "<missing>")
            label = f"objective-matrix.json objective {oid}"
            if oid in seen_objectives:
                failures.append(f"{label}: duplicate objective_id")
            seen_objectives.add(oid)
            for field in ("objective_title", "official_outline", "source_id", "source_ref"):
                if not obj.get(field):
                    failures.append(f"{label}: missing {field}")
            if obj.get("coverage_status") not in COVERAGE_STATUSES:
                failures.append(f"{label}: bad coverage_status {obj.get('coverage_status')!r}")
            if obj.get("verification_status") not in VERIFICATION_STATUSES:
                failures.append(f"{label}: bad verification_status {obj.get('verification_status')!r}")
            if obj.get("confidence") not in CONFIDENCE_LEVELS:
                failures.append(f"{label}: bad confidence {obj.get('confidence')!r}")
            if obj.get("volatility") not in VOLATILITY_LEVELS:
                failures.append(f"{label}: bad volatility {obj.get('volatility')!r}")
            if not isinstance(obj.get("ai_security_extension"), bool):
                failures.append(f"{label}: ai_security_extension must be boolean")
            content = obj.get("content_status")
            if not isinstance(content, dict) or set(content) != CONTENT_STATUS_KEYS:
                failures.append(f"{label}: content_status keys must be exactly {sorted(CONTENT_STATUS_KEYS)}")
            elif not all(isinstance(v, bool) for v in content.values()):
                failures.append(f"{label}: content_status values must be boolean")
            if not isinstance(obj.get("crosswalk_2026"), list):
                failures.append(f"{label}: crosswalk_2026 must be a list")

    upcoming = matrix.get("outlines", {}).get("2026-09")
    if not upcoming:
        failures.append("objective-matrix.json: missing 2026-09 outline")
    else:
        up_domains = upcoming.get("domains", [])
        up_ids = [d.get("domain_id") for d in up_domains]
        if up_ids != list(DOMAINS):
            failures.append(f"objective-matrix.json: 2026-09 domain ids {up_ids} != {list(DOMAINS)}")
        for d in up_domains:
            if not d.get("domain_title"):
                failures.append(f"objective-matrix.json: 2026-09 {d.get('domain_id')} missing domain_title")
        approx_total = sum(d.get("weight_approx", 0.0) for d in up_domains)
        if abs(approx_total - 1.0) > 0.02:
            failures.append(f"objective-matrix.json: 2026-09 approx weights sum {approx_total} outside 1.0 +/- 0.02")
        if not upcoming.get("weights_confidence"):
            failures.append("objective-matrix.json: 2026-09 outline must declare weights_confidence")
        # PR-4.1b: the official 19-objective 2026 set (verified from the ISC2 PDF via
        # reviewer attestation). Ids unique, titles present, count == 19.
        up_objectives = []
        for d in up_domains:
            for obj in d.get("objectives", []):
                oid = obj.get("objective_id")
                up_objectives.append(oid)
                if not obj.get("objective_title"):
                    failures.append(f"objective-matrix.json: 2026-09 objective {oid} missing title")
                if oid and not oid.startswith(d.get("domain_id", "")[1:] + "."):
                    failures.append(f"objective-matrix.json: 2026-09 objective {oid} prefix != domain {d.get('domain_id')}")
        if len(up_objectives) != len(set(up_objectives)):
            failures.append("objective-matrix.json: 2026-09 has duplicate objective ids")
        if up_objectives and len(up_objectives) != 19:
            failures.append(f"objective-matrix.json: 2026-09 objective count {len(up_objectives)} != 19 (official set)")
        crosswalk = upcoming.get("crosswalk_map")
        if not isinstance(crosswalk, dict):
            failures.append("objective-matrix.json: 2026-09 crosswalk_map must be an object")
        else:
            # PR-4 completeness: every current objective maps to >=1 valid 2026 domain,
            # per-objective crosswalk_2026 mirrors the map, and no orphan keys exist.
            up_id_set = set(up_ids)
            if set(crosswalk) != seen_objectives:
                missing = sorted(seen_objectives - set(crosswalk))
                orphans = sorted(set(crosswalk) - seen_objectives)
                failures.append(
                    "objective-matrix.json: crosswalk_map keys must be exactly the 2025-10 "
                    f"objective ids (missing: {missing}; orphans: {orphans})")
            for oid, targets in crosswalk.items():
                if not (isinstance(targets, list) and targets):
                    failures.append(f"objective-matrix.json: crosswalk_map[{oid!r}] must be a non-empty list")
                    continue
                for t in targets:
                    if t not in up_id_set:
                        failures.append(f"objective-matrix.json: crosswalk_map[{oid!r}] target {t!r} is not a 2026-09 domain")
            for domain in domains:
                for obj in domain.get("objectives", []):
                    oid = obj.get("objective_id")
                    if oid in crosswalk and obj.get("crosswalk_2026") != crosswalk[oid]:
                        failures.append(
                            f"objective-matrix.json objective {oid}: crosswalk_2026 "
                            f"{obj.get('crosswalk_2026')} != crosswalk_map entry {crosswalk[oid]}")

    extensions = {e.get("id"): e for e in matrix.get("extensions", [])}
    ai_ext = extensions.get("global.ai-security")
    if not ai_ext:
        failures.append("objective-matrix.json: missing global.ai-security extension")
    elif ai_ext.get("applies_to") != list(DOMAINS):
        failures.append("objective-matrix.json: global.ai-security applies_to must be D1..D5")

    for source_id in sorted(_collect_source_ids(matrix)):
        if source_id not in registry_ids:
            failures.append(f"objective-matrix.json: source_id {source_id!r} not in source-registry.json")


def _check_registry(registry, failures: list[str]) -> set[str]:
    if registry is None:
        failures.append("source-registry.json missing or unparseable")
        return set()
    ids: set[str] = set()
    for entry in registry.get("sources", []):
        sid = entry.get("id", "<missing>")
        label = f"source-registry.json entry {sid}"
        if sid in ids:
            failures.append(f"{label}: duplicate id")
        ids.add(sid)
        if not isinstance(entry.get("tier"), int) or not 0 <= entry["tier"] <= 4:
            failures.append(f"{label}: tier must be an integer 0-4")
        for field in ("type", "status"):
            if not entry.get(field):
                failures.append(f"{label}: missing {field}")
    return ids


def _check_facts(parsed: dict[Path, object], failures: list[str]) -> None:
    facts_dir = PROJECT_ROOT / "spine" / "facts"
    expected = {f"{d}.json" for d in DOMAINS} | {"_global.json"}
    actual = {p.name for p in facts_dir.glob("*.json")}
    if actual != expected:
        failures.append(f"spine/facts: files {sorted(actual)} != {sorted(expected)}")
    for path in facts_dir.glob("*.json"):
        data = parsed.get(path)
        if not isinstance(data, list):
            failures.append(f"{path.relative_to(PROJECT_ROOT)}: must be a JSON array")


def _check_banks(banks, failures: list[str]) -> None:
    if banks is None:
        failures.append("banks.json missing or unparseable")
        return
    bank_defs = banks.get("banks", {})
    if set(bank_defs) != BANKS:
        failures.append(f"banks.json: banks {sorted(bank_defs)} != {sorted(BANKS)}")
    for name, bank in bank_defs.items():
        label = f"banks.json bank {name}"
        for claim_type in bank.get("eligible_claim_types", []):
            if claim_type not in CLAIM_TYPES:
                failures.append(f"{label}: unknown claim_type {claim_type!r}")
        fraction = bank.get("holdout_fraction")
        if not isinstance(fraction, (int, float)) or not 0.0 <= fraction <= 1.0:
            failures.append(f"{label}: holdout_fraction {fraction!r} outside [0, 1]")
        if not isinstance(bank.get("excluded_from_readiness"), bool):
            failures.append(f"{label}: excluded_from_readiness must be boolean")
        for scope, target in bank.get("targets", {}).items():
            if scope not in DOMAINS and scope != "global":
                failures.append(f"{label}: target scope {scope!r} not a domain or 'global'")
            floor, cap = target.get("floor"), target.get("cap")
            if not (isinstance(floor, int) and isinstance(cap, int) and 0 <= floor <= cap):
                failures.append(f"{label}: target {scope} floor/cap invalid ({floor!r}, {cap!r})")

    eligibility = banks.get("claim_type_eligibility", {})
    if set(eligibility) != CLAIM_TYPES:
        failures.append(f"banks.json: claim_type_eligibility keys {sorted(eligibility)} != {sorted(CLAIM_TYPES)}")
    for claim_type, allowed in eligibility.items():
        for bank in allowed:
            if bank not in BANKS:
                failures.append(f"banks.json: eligibility {claim_type} -> unknown bank {bank!r}")

    stratify = set(banks.get("holdout_policy", {}).get("stratify_by", []))
    expected_dims = {"domain", "objective", "topic", "difficulty", "question_type", "source_tier"}
    if stratify != expected_dims:
        failures.append(f"banks.json: holdout stratify_by {sorted(stratify)} != {sorted(expected_dims)}")

    formula = banks.get("readiness", {}).get("domain_formula", {})
    total = sum(formula.values())
    if abs(total - 1.0) > 1e-9:
        failures.append(f"banks.json: readiness domain_formula weights sum {total} != 1.0")
    global_weighting = banks.get("readiness", {}).get("global_weighting", {})
    for did, expected in EXPECTED_WEIGHTS.items():
        if abs(global_weighting.get(did, 0.0) - expected) > 1e-9:
            failures.append(f"banks.json: readiness global_weighting[{did}] != outline weight {expected}")
    mock_weights = banks.get("mock_exam", {}).get("domain_weights", {})
    for did, expected in EXPECTED_WEIGHTS.items():
        if abs(mock_weights.get(did, 0.0) - expected) > 1e-9:
            failures.append(f"banks.json: mock_exam domain_weights[{did}] != outline weight {expected}")


def _check_correction_dictionary(dictionary, failures: list[str]) -> None:
    if dictionary is None:
        failures.append("correction-dictionary.json missing or unparseable")
        return
    policy = dictionary.get("policy", {})
    if policy.get("default_mode") != "suggest_only":
        failures.append("correction-dictionary.json: policy.default_mode must be 'suggest_only'")
    if policy.get("auto_requires_guard") is not True:
        failures.append("correction-dictionary.json: policy.auto_requires_guard must be true")
    seen: set[str] = set()
    for entry in dictionary.get("entries", []):
        wrong = entry.get("wrong", "<missing>")
        label = f"correction-dictionary.json entry {wrong!r}"
        key = wrong.casefold()
        if key in seen:
            failures.append(f"{label}: duplicate key")
        seen.add(key)
        for field in ("wrong", "right", "match", "case_sensitive", "confidence", "mode", "status", "added"):
            if field not in entry:
                failures.append(f"{label}: missing {field}")
        if entry.get("confidence") not in CORRECTION_CONFIDENCE:
            failures.append(f"{label}: bad confidence {entry.get('confidence')!r}")
        if entry.get("mode") != "suggest_only":
            failures.append(f"{label}: mode must be 'suggest_only' in PR-1")
        if entry.get("status") not in CORRECTION_STATUSES:
            failures.append(f"{label}: bad status {entry.get('status')!r}")


# answer_key_isolation_guard (structural half): a learner-facing item file must never
# carry any field that reveals the correct answer. Kept in sync with
# cc_spine.quiz.FORBIDDEN_LEARNER_KEYS; inlined here so scaffold stays import-free of the
# quiz engine (and thus of the factstore).
_GOLDSET_FORBIDDEN_KEYS = (
    "correct_index", "correct", "answer", "rationale_refs", "rationales",
    "distractor_misconceptions", "answer_key_hash",
)


def _check_goldset(goldset, failures: list[str]) -> None:
    if goldset is None:
        failures.append("goldset.json missing or unparseable")
        return
    items = goldset.get("items")
    if not isinstance(items, list):
        failures.append("goldset.json: items must be a JSON array")
        return
    for item in items:
        if not isinstance(item, dict):
            failures.append("goldset.json: each item must be an object")
            continue
        iid = item.get("id", "<no-id>")
        for bad in _GOLDSET_FORBIDDEN_KEYS:
            if bad in item:
                failures.append(
                    f"goldset.json: item {iid} carries answer-bearing field {bad!r} "
                    "(answer_key_isolation_guard)")


def _check_holdout(holdout, failures: list[str]) -> None:
    """PR-8c holdout_leakage_guard (structural half): the holdout item file must exist,
    every item must set holdout:true, and — like the practice lane — carry no answer-bearing
    field. The grounding + no-leak-into-practice half runs in cli quiz validate-holdout."""
    if holdout is None:
        failures.append("holdout.json missing or unparseable")
        return
    items = holdout.get("items")
    if not isinstance(items, list):
        failures.append("holdout.json: items must be a JSON array")
        return
    for item in items:
        if not isinstance(item, dict):
            failures.append("holdout.json: each item must be an object")
            continue
        iid = item.get("id", "<no-id>")
        if item.get("holdout") is not True:
            failures.append(f"holdout.json: item {iid} must set holdout:true (lane label)")
        for bad in _GOLDSET_FORBIDDEN_KEYS:
            if bad in item:
                failures.append(
                    f"holdout.json: item {iid} carries answer-bearing field {bad!r} "
                    "(holdout_leakage_guard)")


# learner_state_isolation_guard (PR-9). Real learner state is never committed; only synthetic
# fixtures under tests/fixtures/ may carry learner-state-shaped data. And the learner schemas
# must stay anonymous — no PII field names anywhere in them.
_LEARNER_STATE_NAMES = {"learner_state.json"}
_LEARNER_STATE_DIRS = {"learner-state", ".local"}
_PII_FIELD_NAMES = {
    "name", "email", "phone", "ip", "address", "user", "username", "account",
    "device_id", "session_id", "cookie", "token", "location",
}


def _check_no_learner_state(failures: list[str]) -> None:
    fixtures = PROJECT_ROOT / "spine" / "tests" / "fixtures"
    # PR-10.4b: .local/variant-drafts/ is the SANCTIONED local runtime home for api-variant
    # drafts (gitignored). This check walks the WORKING TREE, so without the exemption a
    # legitimate local draft would turn every local `make ci` red — training the operator to
    # ignore the gate. The name-based rules still apply inside it; committed variant data
    # anywhere else is policed by _check_no_api_variant_data.
    draft_dir = PROJECT_ROOT / ".local" / "variant-drafts"
    for path in sorted(PROJECT_ROOT.rglob("*")):
        if not path.is_file() or path.is_relative_to(fixtures):
            continue
        name = path.name.lower()
        # Forbid learner-state DATA files only — documentation (.md) in learner-state/ is fine.
        in_state_dir = (any(part in _LEARNER_STATE_DIRS for part in path.parts)
                        and not path.is_relative_to(draft_dir))
        is_state = (name in _LEARNER_STATE_NAMES or name.endswith(".learner-state.json")
                    or (path.suffix.lower() == ".json" and in_state_dir))
        if is_state:
            failures.append(
                f"{path.relative_to(PROJECT_ROOT)}: learner state must not be committed "
                "(local/gitignored runtime only; synthetic fixtures go under tests/fixtures)")


def _check_no_api_variant_data(failures: list[str], root: Path = None) -> None:
    """The api_draft_isolation_guard (PR-10.4b): api-generated variant data is LOCAL runtime
    only. Fail on any project .json — outside tests/fixtures/ and the gitignored .local/ —
    that carries the api_generated_local marker, sits under a variant-drafts path, or is a
    draft/validated variant body (a stem_variant with an unreviewed status)."""
    root = root or PROJECT_ROOT
    fixtures = root / "spine" / "tests" / "fixtures"
    local = root / ".local"
    for path in sorted(root.rglob("*.json")):
        if not path.is_file() or path.is_relative_to(fixtures) or path.is_relative_to(local):
            continue
        rel = path.relative_to(root)
        if "variant-drafts" in path.parts:
            failures.append(f"{rel}: variant drafts must live under .local/ (gitignored), "
                            "never in a committable location")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        # the DATA marker is the source field set to api_generated_local — a schema enum or
        # documentation mention is not data and must not trip the guard.
        if re.search(r'"source"\s*:\s*"api_generated_local"', text):
            failures.append(f"{rel}: carries source=api_generated_local — api-generated "
                            "variants are local runtime data and must never be committed")
            continue
        if '"stem_variant"' in text:
            try:
                data = json.loads(text)
            except (json.JSONDecodeError, ValueError):
                # fail closed: an unparseable json that mentions stem_variant is suspicious,
                # not ignorable (review F4).
                failures.append(f"{rel}: unparseable json containing 'stem_variant' — inspect "
                                "before committing")
                continue
            objs = data if isinstance(data, list) else [data]
            # also look one level into dict values so the write_draft wrapper shape
            # ({draw_key, variant: {...}}) cannot evade the body check (review F4).
            nested = [v for o in objs if isinstance(o, dict) for v in o.values()
                      if isinstance(v, dict)]
            for obj in objs + nested:
                if (isinstance(obj, dict) and "stem_variant" in obj
                        and obj.get("status") in ("draft", "validated")):
                    failures.append(f"{rel}: unreviewed variant body (status "
                                    f"{obj.get('status')!r}) must not be committed")


def _pii_field_names(obj) -> set:
    found = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in _PII_FIELD_NAMES:
                found.add(k.lower())
            found |= _pii_field_names(v)
    elif isinstance(obj, list):
        for v in obj:
            found |= _pii_field_names(v)
    return found


def _check_learner_schemas_anonymous(failures: list[str]) -> None:
    schema_dir = PROJECT_ROOT / "spine" / "schemas"
    for name in ("learner-attempt.schema.json", "learner-state.schema.json"):
        path = schema_dir / name
        if not path.exists():
            failures.append(f"spine/schemas/{name}: missing (PR-9)")
            continue
        schema = json.loads(path.read_text(encoding="utf-8"))
        # Only inspect declared property NAMES, not descriptions/enums.
        pii = _pii_field_names(_schema_property_names(schema))
        if pii:
            failures.append(f"spine/schemas/{name}: carries PII-like field name(s) {sorted(pii)}")


def _schema_property_names(schema) -> dict:
    """Collect the {propertyName: subschema} maps so the PII scan only sees field names."""
    out = {}
    if isinstance(schema, dict):
        props = schema.get("properties")
        if isinstance(props, dict):
            for k, v in props.items():
                out[k] = _schema_property_names(v)
        for v in schema.values():
            child = _schema_property_names(v)
            if child:
                out.setdefault("_nested", []).append(child)
    elif isinstance(schema, list):
        acc = [_schema_property_names(v) for v in schema]
        if any(acc):
            out["_nested"] = acc
    return out


def _check_schema_headers(parsed: dict[Path, object], failures: list[str]) -> None:
    schema_dir = PROJECT_ROOT / "spine" / "schemas"
    schema_files = sorted(schema_dir.glob("*.schema.json"))
    if len(schema_files) != 10:
        failures.append(f"spine/schemas: expected 10 schema files, found {len(schema_files)}")
    for path in schema_files:
        data = parsed.get(path)
        if not isinstance(data, dict):
            continue
        for field in ("schema_version", "migration_policy"):
            if not data.get(field):
                failures.append(f"{path.relative_to(PROJECT_ROOT)}: missing {field}")


def _check_markdown_links(failures: list[str]) -> None:
    for md_path in sorted(PROJECT_ROOT.rglob("*.md")):
        # Skip dot-directories (installed tooling such as .claude/ and .cognition/): the scaffold
        # validates the governed learning-center content, not third-party toolkit templates, whose
        # docs legitimately carry placeholder links (e.g. 'path/to/file.py').
        if any(part.startswith(".") for part in md_path.relative_to(PROJECT_ROOT).parts[:-1]):
            continue
        in_fence = False
        for line_number, line in enumerate(md_path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for match in MD_LINK_RE.finditer(line):
                target = match.group(1).split("#", 1)[0]
                if not target or target.startswith(("http://", "https://", "mailto:")):
                    continue
                if target.startswith("cc-master-learning-center/"):
                    resolved = REPO_ROOT / target
                else:
                    resolved = md_path.parent / target
                if not resolved.exists():
                    failures.append(
                        f"{md_path.relative_to(PROJECT_ROOT)}:{line_number}: broken relative link {target!r}"
                    )


def _check_evidence(evidence, registry, failures: list[str]) -> None:
    """PR-4.1: the two-lane verification ledger is well-formed, and every
    operator-unreachable official source has a matching dated attestation."""
    if evidence is None:
        failures.append("reference/verification-evidence.json missing or unparseable")
        return
    attempts = evidence.get("operator_fetch_attempts")
    attestations = evidence.get("reviewer_attestations")
    if not isinstance(attempts, list) or not attempts:
        failures.append("verification-evidence.json: operator_fetch_attempts must be a non-empty list")
    else:
        for i, a in enumerate(attempts):
            if not a.get("url") or not a.get("result"):
                failures.append(f"verification-evidence.json: fetch attempt {i} missing url/result")
    att_urls: set[str] = set()
    if not isinstance(attestations, list) or not attestations:
        failures.append("verification-evidence.json: reviewer_attestations must be a non-empty list")
    else:
        for i, a in enumerate(attestations):
            if not a.get("url") or not a.get("date") or not a.get("confirms"):
                failures.append(f"verification-evidence.json: attestation {i} missing url/date/confirms")
            else:
                att_urls.add(a["url"])
    # Every operator-blocked official source names attestation_urls that exist here.
    for entry in (registry or {}).get("sources", []):
        if entry.get("operator_fetch_status") == "blocked_403" \
                and str(entry.get("confidence", "")).startswith("official"):
            for url in entry.get("attestation_urls") or ["<none>"]:
                if url not in att_urls:
                    failures.append(
                        f"verification-evidence.json: source {entry.get('id')} needs an "
                        f"attestation for {url}, none present")


def _check_manifest(manifest, failures: list[str]) -> None:
    """PR-5: the ingestion source manifest never commits raw transcripts."""
    if manifest is None:
        return  # manifest is optional until PR-5 ships one
    if manifest.get("ip_policy") != "distillation_only":
        failures.append("source-manifest.json: ip_policy must be 'distillation_only'")
    if not manifest.get("authorization", {}).get("authorized_by"):
        failures.append("source-manifest.json: missing authorization.authorized_by")
    for entry in manifest.get("sources", []):
        sid = entry.get("source_doc_id", "<missing>")
        if entry.get("raw_committed") is not False:
            failures.append(f"source-manifest.json {sid}: raw_committed must be false")
        if not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("sha256", ""))):
            failures.append(f"source-manifest.json {sid}: sha256 must be a 64-hex digest")
        name = entry.get("original_filename")
        if name and (PROJECT_ROOT / name).exists():
            failures.append(f"source-manifest.json {sid}: raw file {name!r} must not be in the repo")


def _check_no_raw_transcripts(failures: list[str]) -> None:
    # Two-tier scan (P0-3 hardening):
    # 1. Repo-root scope: DOCX/DOC/PPTX only — transcript formats that must never
    #    be committed anywhere. PDFs are legitimate docs/ reference material outside
    #    this project and are excluded from the repo-wide check.
    # 2. Project scope: full FORBIDDEN_UPLOAD_SUFFIXES (adds PDF) — no binary blobs
    #    are expected inside cc-master-learning-center at all.
    for path in sorted(REPO_ROOT.rglob("*")):
        suffix = path.suffix.lower()
        in_project = path.is_relative_to(PROJECT_ROOT)
        if (in_project and suffix in FORBIDDEN_UPLOAD_SUFFIXES) or \
                (not in_project and suffix in _FORBIDDEN_REPO_SUFFIXES):
            failures.append(
                f"{path.relative_to(REPO_ROOT)}: raw transcript/document files are not authorized in this repo"
            )


def run_checks() -> list[str]:
    failures: list[str] = []
    parsed = _check_json_wellformed(failures)

    registry = parsed.get(PROJECT_ROOT / "reference" / "source-registry.json")
    registry_ids = _check_registry(registry, failures)

    matrix = parsed.get(PROJECT_ROOT / "reference" / "objective-matrix.json")
    _check_matrix(matrix, registry_ids, failures)

    _check_facts(parsed, failures)
    _check_banks(parsed.get(PROJECT_ROOT / "spine" / "banks" / "banks.json"), failures)
    _check_correction_dictionary(
        parsed.get(PROJECT_ROOT / "spine" / "ingest" / "correction-dictionary.json"), failures
    )
    _check_goldset(parsed.get(PROJECT_ROOT / "spine" / "gold" / "goldset.json"), failures)
    _check_holdout(parsed.get(PROJECT_ROOT / "spine" / "gold" / "holdout.json"), failures)
    _check_no_learner_state(failures)
    _check_no_api_variant_data(failures)
    _check_learner_schemas_anonymous(failures)
    _check_evidence(
        parsed.get(PROJECT_ROOT / "reference" / "verification-evidence.json"), registry, failures)
    _check_manifest(
        parsed.get(PROJECT_ROOT / "spine" / "ingest" / "source-manifest.json"), failures)
    _check_schema_headers(parsed, failures)
    _check_markdown_links(failures)
    _check_no_raw_transcripts(failures)
    for problem in _verbatim_module().scan_verbatim(
            [PROJECT_ROOT / "notes", PROJECT_ROOT / "reference"]):
        failures.append(problem)
    return failures


def _verbatim_module():
    from . import ipboundary
    return ipboundary


def main() -> int:
    failures = run_checks()
    print(f"cc_spine scaffold validate — project root: {PROJECT_ROOT}")
    if failures:
        print(f"FAIL ({len(failures)} problem(s)):")
        for failure in failures:
            print(f"  - {failure}")
    else:
        print("OK: JSON well-formed; matrix, registry joins, banks, correction dictionary,")
        print("    facts/goldset/holdout arrays, answer-key + holdout isolation, schema headers, markdown links, no-transcript rule all pass.")
    print("Guard status (active guards run via cc_spine.cli; reserved activate in later PRs):")
    for guard, status in GUARD_STATUS.items():
        print(f"  {guard}: {status}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
