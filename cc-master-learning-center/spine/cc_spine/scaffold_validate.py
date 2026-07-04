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
FORBIDDEN_UPLOAD_SUFFIXES = {".docx", ".doc", ".pdf", ".pptx"}

# Guard activation status. Guards move from "reserved" to "active" as the PR
# roadmap delivers them. PR-2 activated the freshness and IP-boundary guards.
GUARD_STATUS = {
    "source_freshness_guard": "active",       # PR-2: cc_spine.sources
    "ip_boundary_guard": "active",            # PR-2: cc_spine.ipboundary
    "no_verbatim_bulk_reproduction": "reserved",
    "holdout_leakage_guard": "reserved",
    "answer_key_isolation_guard": "reserved",
    "unsupported_claim_guard": "reserved",
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

    stub = matrix.get("outlines", {}).get("2026-09")
    if not stub:
        failures.append("objective-matrix.json: missing 2026-09 stub outline")
    else:
        approx_total = sum(d.get("weight_approx", 0.0) for d in stub.get("domains", []))
        if abs(approx_total - 1.0) > 0.02:
            failures.append(f"objective-matrix.json: 2026-09 approx weights sum {approx_total} outside 1.0 +/- 0.02")
        if not isinstance(stub.get("crosswalk_map"), dict):
            failures.append("objective-matrix.json: 2026-09 crosswalk_map must be an object")

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
        if data != []:
            failures.append(f"{path.relative_to(PROJECT_ROOT)}: must be an empty array in PR-1")


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


def _check_goldset(goldset, failures: list[str]) -> None:
    if goldset is None:
        failures.append("goldset.json missing or unparseable")
        return
    if goldset.get("items") != []:
        failures.append("goldset.json: items must be empty in PR-1")


def _check_schema_headers(parsed: dict[Path, object], failures: list[str]) -> None:
    schema_dir = PROJECT_ROOT / "spine" / "schemas"
    schema_files = sorted(schema_dir.glob("*.schema.json"))
    if len(schema_files) != 4:
        failures.append(f"spine/schemas: expected 4 schema files, found {len(schema_files)}")
    for path in schema_files:
        data = parsed.get(path)
        if not isinstance(data, dict):
            continue
        for field in ("schema_version", "migration_policy"):
            if not data.get(field):
                failures.append(f"{path.relative_to(PROJECT_ROOT)}: missing {field}")


def _check_markdown_links(failures: list[str]) -> None:
    for md_path in sorted(PROJECT_ROOT.rglob("*.md")):
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


def _check_no_raw_transcripts(failures: list[str]) -> None:
    for path in sorted(PROJECT_ROOT.rglob("*")):
        if path.suffix.lower() in FORBIDDEN_UPLOAD_SUFFIXES:
            failures.append(
                f"{path.relative_to(PROJECT_ROOT)}: raw transcript/document files are not authorized in this repo"
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
    _check_schema_headers(parsed, failures)
    _check_markdown_links(failures)
    _check_no_raw_transcripts(failures)
    return failures


def main() -> int:
    failures = run_checks()
    print(f"cc_spine scaffold validate — project root: {PROJECT_ROOT}")
    if failures:
        print(f"FAIL ({len(failures)} problem(s)):")
        for failure in failures:
            print(f"  - {failure}")
    else:
        print("OK: JSON well-formed; matrix, registry joins, banks, correction dictionary,")
        print("    facts/goldset emptiness, schema headers, markdown links, no-transcript rule all pass.")
    print("Guard status (active guards run via cc_spine.cli; reserved activate in later PRs):")
    for guard, status in GUARD_STATUS.items():
        print(f"  {guard}: {status}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
