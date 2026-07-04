"""cc_spine.quiz — the quiz engine and its safety gates (PR-8a).

This module turns fact-grounded bank items into a learner-facing quiz while keeping
the answer key strictly isolated. Three responsibilities:

0. **Two representations, one direction.** ``spine/gold/goldset.json`` is the
   AUTHORING/VALIDATION source: it carries validation metadata (answer_key_ref, fact_ids,
   expected_keywords, status, holdout) but never a correct answer. It is NOT the learner
   export. The ONLY learner-facing representation is ``learner_view`` (a.k.a.
   ``cc_spine.cli quiz export-learner``). Nothing hands a learner a raw goldset item.

1. **Learner view** (``learner_view``) — the ONLY item projection a learner ever sees.
   It is an allowlist: stem, choices, and neutral metadata. It can never contain the
   correct answer, a rationale, grounding fact_ids, or the answer_key_ref. This is the
   enforcement point of the ``answer_key_isolation_guard``.

2. **Grading** (``grade``) — resolves an item's answer only inside grader context, by
   reading the separate answer-key store (``spine/gold/answer-keys.json``). The learner
   view and the grader key never live in the same object.

3. **Gold validation** (``validate_gold``) — every item is fact-grounded, eligible,
   active, and non-sensitive (via ``factstore.validate_item`` + the sensitive-card
   quarantine); every item resolves to exactly one key; the key's hash still matches the
   item's choices (drift guard); rationale_refs are a subset of the item's fact_ids; and
   no two items in the same objective are near-duplicate stems.

Stdlib-only. Imports ``factstore`` (for the frozen item-grounding checks) but never the
reverse — the factstore does not depend on the quiz engine.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import factstore

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
GOLDSET_PATH = _PROJECT_ROOT / "spine" / "gold" / "goldset.json"
ANSWER_KEYS_PATH = _PROJECT_ROOT / "spine" / "gold" / "answer-keys.json"
MISCONCEPTION_REGISTRY_PATH = _PROJECT_ROOT / "reference" / "misconception-registry.json"

# No single correct-answer index may dominate the set (anti-pattern-learning gate).
_ANSWER_POSITION_MAX_SHARE = 0.40
# Fields folded into the full-item drift hash (canonical, sorted).
_ITEM_HASH_FIELDS = ("id", "stem", "choices", "fact_ids", "expected_keywords", "objective", "bank")

# The learner view is an ALLOWLIST — only these keys are ever projected to a learner.
# Everything else (answer_key_ref, fact_ids, expected_keywords, misconception_tags,
# holdout, status, source_policy) is withheld. Nothing here reveals the correct answer.
LEARNER_FIELDS = ("id", "bank", "domain", "objective", "topic", "stem", "choices", "difficulty")

# Keys that must NEVER appear in a learner-facing item file. If any surfaces, the answer
# key has leaked into the learner lane — a hard isolation failure.
FORBIDDEN_LEARNER_KEYS = (
    "correct_index", "correct", "answer", "rationale_refs", "rationales",
    "distractor_misconceptions", "answer_key_hash",
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    "a an the of to in on for is are and or which what that this these those with by as "
    "be it its at from must should would could can may each every any all not no only".split()
)
_NEAR_DUP_THRESHOLD = 0.75  # Jaccard on stem token sets, within a shared objective


# --- answer-key hash -------------------------------------------------------- #

def answer_key_hash(item_id: str, correct_choice: str) -> str:
    """Deterministic pin binding a key to its item's correct choice TEXT. If the item's
    choices are edited, the recomputed hash stops matching and validate_gold flags drift.
    Uses a unit separator so ``a`` + ``bc`` cannot collide with ``ab`` + ``c``."""
    digest = hashlib.sha256(f"{item_id}\x1f{correct_choice}".encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def item_hash(item: dict) -> str:
    """Full-item drift pin over canonical content (id, stem, choices, fact_ids,
    expected_keywords, objective, bank). Catches semantic drift the correct-choice hash
    misses — e.g. the stem is rewritten but the correct-choice text is unchanged, so the
    key would still 'match' a now-different question. Canonical JSON → stable across runs."""
    canon = {k: item.get(k, []) if k in ("fact_ids", "expected_keywords") else item.get(k)
             for k in _ITEM_HASH_FIELDS}
    blob = json.dumps(canon, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --- learner view + grading ------------------------------------------------- #

def learner_view(item: dict) -> dict:
    """Project an item to exactly what a learner may see. Allowlist, not denylist:
    unknown or answer-bearing fields cannot slip through."""
    return {k: item[k] for k in LEARNER_FIELDS if k in item}


def _keys_by_ref(keys) -> dict:
    return {k.get("answer_key_ref"): k for k in keys}


def grade(item: dict, keys, submitted_index: int) -> dict:
    """Grade a submitted choice. Grader context only — resolves the isolated key store.
    Returns correctness plus the grounding rationale_refs so a wrong answer can teach."""
    key = _keys_by_ref(keys).get(item.get("answer_key_ref"))
    if key is None:
        return {"graded": False, "reason": "no answer key resolves for this item"}
    correct = key.get("correct_index")
    return {
        "graded": True,
        "correct": submitted_index == correct,
        "correct_index": correct,
        "rationale_refs": key.get("rationale_refs", []),
        "misconception": key.get("distractor_misconceptions", {}).get(str(submitted_index)),
    }


# --- isolation guard -------------------------------------------------------- #

def isolation_problems(items) -> list:
    """The answer_key_isolation_guard: no learner-facing item file may carry any
    answer-bearing field, and the learner_view projection must expose none either."""
    problems = []
    for item in items:
        iid = item.get("id", "<no-id>")
        for bad in FORBIDDEN_LEARNER_KEYS:
            if bad in item:
                problems.append(f"{iid}: learner item carries answer-bearing field {bad!r}")
        leaked = [k for k in learner_view(item) if k in FORBIDDEN_LEARNER_KEYS]
        if leaked:
            problems.append(f"{iid}: learner_view exposes {leaked} — isolation breach")
    return problems


# --- near-duplicate stems --------------------------------------------------- #

def _stem_tokens(stem: str) -> frozenset:
    return frozenset(t for t in _TOKEN_RE.findall(stem.lower()) if t not in _STOPWORDS)


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def answer_position_problems(items, keys, max_share: float = _ANSWER_POSITION_MAX_SHARE) -> list:
    """Anti-pattern-learning gate: the correct answer must not cluster at one position.
    No single index may hold more than ``max_share`` of the set, and no objective with
    multiple items may put the correct answer at the same index every time."""
    problems = []
    key_by_ref = _keys_by_ref(keys)
    positions, by_obj = [], {}
    for item in items:
        key = key_by_ref.get(item.get("answer_key_ref"))
        if key is None or not isinstance(key.get("correct_index"), int):
            continue
        ci = key["correct_index"]
        positions.append(ci)
        by_obj.setdefault(item.get("objective"), []).append(ci)
    if positions:
        from collections import Counter
        counts = Counter(positions)
        top_index, top_count = counts.most_common(1)[0]
        if top_count / len(positions) > max_share:
            problems.append(
                f"answer-position overfit: index {top_index} is correct in "
                f"{top_count}/{len(positions)} items (> {max_share:.0%}); vary correct positions")
    for objective, idxs in by_obj.items():
        if len(idxs) >= 2 and len(set(idxs)) == 1:
            problems.append(
                f"answer-position overfit: every item in objective {objective} has the "
                f"correct answer at index {idxs[0]}; vary positions within an objective")
    return problems


def _load_registry(path: Path = None) -> dict:
    path = path or MISCONCEPTION_REGISTRY_PATH
    entries = json.loads(path.read_text(encoding="utf-8")).get("entries", [])
    return {e["id"]: e for e in entries}


def distractor_registry_problems(items, keys, registry_entries: dict) -> list:
    """Every WRONG choice must map to a registry misconception (P0-1): the id resolves,
    the declared category matches the registry, and the registry objective matches the
    item's objective (or is global)."""
    problems = []
    key_by_ref = _keys_by_ref(keys)
    for item in items:
        iid = item.get("id", "<no-id>")
        key = key_by_ref.get(item.get("answer_key_ref"))
        if key is None:
            continue
        ci = key.get("correct_index")
        n = len(item.get("choices", []))
        mapping = key.get("distractor_misconceptions", {})
        wrong_indices = {str(i) for i in range(n) if i != ci}
        missing = wrong_indices - set(mapping)
        if missing:
            problems.append(
                f"{iid}: distractors {sorted(missing)} lack a misconception mapping "
                "(every wrong choice must name one)")
        for idx_s, entry in mapping.items():
            if not isinstance(entry, dict):
                problems.append(f"{iid}: distractor {idx_s} must map to {{misconception_id, category}}")
                continue
            mid = entry.get("misconception_id")
            reg = registry_entries.get(mid)
            if reg is None:
                problems.append(f"{iid}: distractor {idx_s} misconception_id {mid!r} not in the registry")
                continue
            if entry.get("category") != reg.get("category"):
                problems.append(
                    f"{iid}: distractor {idx_s} category {entry.get('category')!r} != "
                    f"registry category {reg.get('category')!r} for {mid!r}")
            reg_obj = reg.get("objective")
            if reg_obj not in (item.get("objective"), "global"):
                problems.append(
                    f"{iid}: distractor {idx_s} misconception {mid!r} is objective {reg_obj!r}, "
                    f"not the item's {item.get('objective')!r} (nor global)")
    return problems


def near_duplicate_problems(items, threshold: float = _NEAR_DUP_THRESHOLD) -> list:
    """Within a single objective, two stems with token-overlap above the threshold are
    near-duplicates (same question twice — redundant deck clutter, and a leakage risk once
    holdout exists). Cross-objective overlap is expected and ignored."""
    problems = []
    by_obj: dict = {}
    for item in items:
        by_obj.setdefault(item.get("objective"), []).append(item)
    for objective, group in by_obj.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                score = _jaccard(_stem_tokens(a.get("stem", "")), _stem_tokens(b.get("stem", "")))
                if score >= threshold:
                    problems.append(
                        f"{a.get('id')} / {b.get('id')}: near-duplicate stems in objective "
                        f"{objective} (overlap {score:.2f} >= {threshold})")
    return problems


# --- full gold validation --------------------------------------------------- #

def validate_gold(store, items, keys, registry=None) -> dict:
    """Validate the gold item set against its answer-key store. Returns
    ``{ok, errors}`` — the ship-gate's item-side proof."""
    problems = []
    key_by_ref = {}
    for k in keys:
        ref = k.get("answer_key_ref")
        if ref in key_by_ref:
            problems.append(f"duplicate answer_key_ref {ref!r} in the key store")
        key_by_ref[ref] = k

    seen = set()
    for item in items:
        iid = item.get("id", "<no-id>")
        if iid in seen:
            problems.append(f"{iid}: duplicate item id")
        seen.add(iid)

        # 1. grounding / eligibility / active / unsupported_claim_guard (frozen factstore)
        problems += [f"{iid}: {e}" for e in factstore.validate_item(store, item)]

        # 2. sensitive-card quarantine — no answer-key-sensitive card may ground a learner item
        for fid in item.get("fact_ids", []):
            card = store.cards.get(fid)
            if card is not None and not factstore._learner_safe(card):
                problems.append(f"{iid}: cites sensitive card {fid!r} — barred from learner items")

        # 3. the item must resolve to exactly one well-formed key
        ref = item.get("answer_key_ref")
        key = key_by_ref.get(ref)
        if key is None:
            problems.append(f"{iid}: answer_key_ref {ref!r} does not resolve to a key")
            continue
        if ref != f"{iid}.key":
            problems.append(f"{iid}: answer_key_ref must be item_id + '.key' (got {ref!r})")
        if key.get("item_id") != iid:
            problems.append(f"{iid}: key.item_id {key.get('item_id')!r} does not match the item")

        choices = item.get("choices", [])
        ci = key.get("correct_index")
        if not isinstance(ci, int) or not (0 <= ci < len(choices)):
            problems.append(f"{iid}: correct_index {ci!r} is out of range for {len(choices)} choices")
            continue

        # 4. hash integrity — correct-choice hash AND full-item hash (semantic drift)
        if key.get("answer_key_hash") != answer_key_hash(iid, choices[ci]):
            problems.append(f"{iid}: answer_key_hash mismatch — correct-choice text drifted from the key")
        if key.get("item_hash") != item_hash(item):
            problems.append(f"{iid}: item_hash mismatch — item content drifted from the key")

        # 5. rationale_refs must be grounded by the item's own cited cards
        if not set(key.get("rationale_refs", [])) <= set(item.get("fact_ids", [])):
            problems.append(f"{iid}: rationale_refs are not a subset of the item's fact_ids")

        # 6. distractor tags point at real, non-correct choices
        for idx_s in key.get("distractor_misconceptions", {}):
            if not (idx_s.isdigit() and 0 <= int(idx_s) < len(choices)):
                problems.append(f"{iid}: distractor index {idx_s!r} is out of range")
            elif int(idx_s) == ci:
                problems.append(f"{iid}: distractor_misconceptions marks the correct choice {ci}")

    # 7. no orphan keys (every key grades a real item)
    item_refs = {it.get("answer_key_ref") for it in items}
    for ref in key_by_ref:
        if ref not in item_refs:
            problems.append(f"orphan answer key {ref!r} grades no item")

    # 8. isolation, registry-linked distractors, near-duplicate + answer-position gates
    problems += isolation_problems(items)
    try:
        registry_entries = _load_registry()
    except Exception as exc:  # fail closed — an unreadable registry is a gate failure
        problems.append(f"misconception registry unreadable: {exc}")
        registry_entries = {}
    problems += distractor_registry_problems(items, keys, registry_entries)
    problems += near_duplicate_problems(items)
    problems += answer_position_problems(items, keys)

    return {"ok": not problems, "errors": problems}


# --- loaders ---------------------------------------------------------------- #

def load_goldset(path: Path = None) -> list:
    path = path or GOLDSET_PATH
    return json.loads(path.read_text(encoding="utf-8")).get("items", [])


def load_answer_keys(path: Path = None) -> list:
    path = path or ANSWER_KEYS_PATH
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("keys", [])
