"""cc_spine.variants — the semantic variant model + validators (PR-10.4a).

A *variant* re-tests a MISSED practice item without reusing its exact stem: same concept, different
surface wording. The governance problem is that free rewording can silently change WHAT is tested, so
a variant is only trustworthy if it provably preserves the source item's testable core. This module
is the validator that proves it — synthetic variants only; NO live API here (that is PR-10.4b).

Answer-key isolation (carried from the quiz engine): the variant OBJECT stores no correct answer —
no correct index, display letter, or choice order (gate 11). The correct choice lives in a SEPARATE,
evaluator-context ``variant_key`` (``{variant_id, correct_index, rationale_refs}``), exactly like
``answer-keys.json`` for gold items. The ``semantic_lock`` does NOT define correctness on its own
(that was unsound — a misleading keyword can land on a distractor); it CORROBORATES the key: the
keyed-correct choice must contain every ``must_include_keyword`` and no other choice may, so the lock
keywords are a real discriminator and there is no second choice that satisfies the lock.

The ``semantic_lock_guard`` is the consolidated drift check: objective, bank, fact_ids, and the
misconception target (derived from the SOURCE item's isolated key) must not move off the source.

Variants render + grade through the PR-10.3 presentation layer, so they shuffle per attempt exactly
like items and the render carries neither answers nor answer-adjacent authoring text.

Stdlib only. Imports ``factstore`` (grounding), ``quiz`` (tokeniser/registry/grade), and
``presentation`` (render/grade). Never imported by any of them.
"""

from __future__ import annotations

import hashlib
import json

from . import factstore, presentation, quiz

# The variant object's allowed shape (an ALLOWLIST, mirroring the schema's additionalProperties:false
# and closing the "arbitrarily-named smuggle field" gap a denylist leaves open — review F6). Any key
# outside these fails validation, so no answer-bearing field of any name can ride along.
_ALLOWED_TOP_KEYS = frozenset({
    "variant_id", "source_item_id", "objective", "bank", "fact_ids", "expected_keywords",
    "misconception_ids", "semantic_lock", "stem_variant", "choices_variant", "status", "source",
    "reviewed_by", "last_reviewed", "readiness_weight",
})
_ALLOWED_LOCK_KEYS = frozenset({"must_test", "correct_concept", "must_include_keywords", "must_not_change"})

# too-similar bound on the reworded stem. Reconciled to the goldset's own near-duplicate standard
# (quiz._NEAR_DUP_THRESHOLD, 0.75) — a variant may not be closer to its source than two goldset stems
# are allowed to be to each other (review F9).
_TOO_SIMILAR_JACCARD = quiz._NEAR_DUP_THRESHOLD
_MIN_STEM_TOKENS = 3
# correct_concept must be a concept, not a bare display letter/index. A single character (any
# letter A-F for up to 6 choices, or a digit) is rejected regardless of which (review F5, N4).


def _kw_in(text: str, keywords) -> bool:
    low = text.lower()
    return all(kw.lower() in low for kw in keywords)


def keyed_correct_index(variant_key: dict, n: int):
    """The correct index is the SOURCE OF TRUTH from the isolated key, range-checked. Returns None on
    a malformed/out-of-range key so callers fail closed."""
    if not isinstance(variant_key, dict):
        return None
    ci = variant_key.get("correct_index")
    return ci if isinstance(ci, int) and not isinstance(ci, bool) and 0 <= ci < n else None


def semantic_lock_hash(variant: dict) -> str:
    """A lineage id over the invariant core (source_item_id, objective, bank, sorted fact_ids +
    misconception_ids, correct_concept, sorted must_include_keywords). Its value CHANGES if any of
    those change, so two lineage records for the 'same' variant that disagree are tamper-evident.
    It is a lineage/traceability id, not a live drift gate (validate_variant enforces drift directly)."""
    lock = variant.get("semantic_lock", {})
    canon = {
        "source_item_id": variant.get("source_item_id"),
        "objective": variant.get("objective"),
        "bank": variant.get("bank"),
        "fact_ids": sorted(variant.get("fact_ids", [])),
        "misconception_ids": sorted(variant.get("misconception_ids", [])),
        "correct_concept": lock.get("correct_concept"),
        "must_include_keywords": sorted(lock.get("must_include_keywords", [])),
    }
    blob = json.dumps(canon, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def unknown_field_problems(variant: dict) -> list:
    """Gate 11 + review F6: the variant is a CLOSED object — any top-level key or semantic_lock key
    outside the allowlist fails (so no answer/display-order field of any name can be smuggled in)."""
    vid = variant.get("variant_id", "<no-id>")
    problems = [f"{vid}: disallowed field {k!r} on the variant (closed object)"
                for k in variant if k not in _ALLOWED_TOP_KEYS]
    lock = variant.get("semantic_lock")
    if isinstance(lock, dict):
        problems += [f"{vid}: disallowed field {k!r} in semantic_lock" for k in lock
                     if k not in _ALLOWED_LOCK_KEYS]
    return problems


def lock_consistency_problems(variant: dict, variant_key: dict) -> list:
    """Gate 7 (review F1): the semantic_lock must corroborate the isolated key, not replace it. The
    keyed-correct choice must contain every ``must_include_keyword``; NO other choice may contain them
    all (else there is a second choice that satisfies the lock — an ambiguous/defensible second
    answer). ``correct_concept`` must be a non-empty concept, not a bare display letter/index.

    NOTE (review N3): this proves the keyed choice UNIQUELY carries the grounded keyword text — it
    does NOT prove that choice is semantically correct (an author can still key a wrong index, exactly
    as with answer-keys.json). Automated gates cannot verify semantic correctness; human review is the
    backstop — ``is_practice_eligible`` requires ``status == 'reviewed'`` + metadata before use."""
    vid = variant.get("variant_id", "<no-id>")
    problems = []
    lock = variant.get("semantic_lock", {})
    kws = lock.get("must_include_keywords", [])
    choices = variant.get("choices_variant", [])
    ci = keyed_correct_index(variant_key, len(choices))
    if ci is None:
        return [f"{vid}: variant_key has no valid correct_index for this variant"]
    if not kws:
        problems.append(f"{vid}: semantic_lock has no must_include_keywords to corroborate the key")
    elif not _kw_in(choices[ci], kws):
        problems.append(f"{vid}: the keyed-correct choice does not contain all must_include_keywords "
                        "(the lock must identify the SAME choice the key marks correct)")
    others = [i for i in range(len(choices)) if i != ci and kws and _kw_in(choices[i], kws)]
    if others:
        problems.append(f"{vid}: distractor(s) {others} also satisfy the lock keywords — no single "
                        "best answer (a second choice is defensibly correct)")
    cc = (lock.get("correct_concept") or "").strip()
    if not cc:
        problems.append(f"{vid}: semantic_lock.correct_concept is empty")
    elif len(cc) == 1:
        problems.append(f"{vid}: semantic_lock.correct_concept {cc!r} is a bare letter/index, not a concept")
    return problems


def semantic_lock_guard(variant: dict, source_item: dict, source_misconception_ids) -> list:
    """The consolidated no-drift check (gate 13): the variant may not move objective, bank, fact_ids,
    or the misconception target off the source item. ``source_misconception_ids`` is the source item's
    target set (from its isolated key). It is REQUIRED — a caller that cannot supply it gets an
    explicit failure, never a silent skip (review F3)."""
    vid = variant.get("variant_id", "<no-id>")
    problems = []
    if variant.get("objective") != source_item.get("objective"):
        problems.append(f"{vid}: objective {variant.get('objective')!r} drifts from source "
                        f"{source_item.get('objective')!r}")
    if variant.get("bank") != source_item.get("bank"):
        problems.append(f"{vid}: bank {variant.get('bank')!r} drifts from source {source_item.get('bank')!r}")
    src_facts = set(source_item.get("fact_ids", []))
    if not set(variant.get("fact_ids", [])) <= src_facts:
        problems.append(f"{vid}: fact_ids introduce a claim not in the source item's fact_ids (drift)")
    if source_misconception_ids is None:
        problems.append(f"{vid}: cannot verify misconception drift — no source misconception targets "
                        "supplied (source item's isolated key is required)")
    elif not set(variant.get("misconception_ids", [])) <= set(source_misconception_ids):
        problems.append(f"{vid}: misconception target drifts from the source item's targets")
    return problems


def similarity_problems(variant: dict, source_item: dict) -> list:
    """Gate 12 + R&D: a good variant is semantically equivalent but not text-identical. Too similar
    (stem Jaccard > threshold vs the source) is a synonym swap, not a real rewrite."""
    vid = variant.get("variant_id", "<no-id>")
    problems = []
    v_tokens = quiz._stem_tokens(variant.get("stem_variant", ""))
    s_tokens = quiz._stem_tokens(source_item.get("stem", ""))
    if len(v_tokens) < _MIN_STEM_TOKENS:
        problems.append(f"{vid}: stem_variant too short to be a meaningful variant")
    elif quiz._jaccard(v_tokens, s_tokens) > _TOO_SIMILAR_JACCARD:
        problems.append(f"{vid}: stem_variant is a near-duplicate of the source stem "
                        f"(Jaccard > {_TOO_SIMILAR_JACCARD}) — reword, don't synonym-swap")
    return problems


def _source_misconception_ids(source_key: dict):
    """The source item's misconception target set, from its isolated key's distractor map. Returns
    None if the key is missing/malformed so the drift check fails closed (review F3)."""
    if not isinstance(source_key, dict):
        return None
    mapping = source_key.get("distractor_misconceptions")
    if not isinstance(mapping, dict):
        return None
    ids = {e.get("misconception_id") for e in mapping.values() if isinstance(e, dict)}
    ids.discard(None)
    return ids


def _synthetic_item(variant: dict, source_item: dict) -> dict:
    """An item-shaped dict from a variant so the frozen item validators and the presentation layer
    apply unchanged. The learner-facing ``topic`` uses the SOURCE item's NEUTRAL topic — never
    ``must_test`` (which is answer-adjacent authoring text and would leak through the allowlisted
    topic field, review F2). ``must_test`` stays internal to validation."""
    return {
        "id": variant["variant_id"],
        "bank": variant["bank"],
        "domain": source_item.get("domain"),
        "objective": variant["objective"],
        "topic": source_item.get("topic"),
        "stem": variant["stem_variant"],
        "choices": variant["choices_variant"],
        "difficulty": source_item.get("difficulty"),
        "fact_ids": variant["fact_ids"],
        "expected_keywords": variant["expected_keywords"],
        "source_policy": "factstore|required",
        "answer_key_ref": variant["variant_id"] + ".key",
    }


def validate_variant(variant: dict, variant_key: dict, source_item, source_key,
                     store, registry: dict, holdout_ids=None) -> list:
    """Full gate set for one variant ([] == valid).

    ``variant_key`` is the ISOLATED correct-answer record (evaluator context). ``source_item`` /
    ``source_key`` are the resolved source practice item and its isolated key (None → unresolved).
    ``holdout_ids`` (optional) is the set of holdout ids; when omitted it is loaded so gate 2 does
    not depend on the caller (review F8)."""
    vid = variant.get("variant_id", "<no-id>")
    problems = list(unknown_field_problems(variant))            # gate 11 / F6

    if source_item is None:                                     # gate 1
        return problems + [f"{vid}: source_item_id {variant.get('source_item_id')!r} does not resolve "
                           "to a practice item"]
    if holdout_ids is None:
        # Load the holdout ids ourselves so gate 2 does not depend on the caller — but fail CLOSED
        # (a clean gate error), not loud, if the governance file is unreadable (matches validate_gold;
        # review N1).
        try:
            holdout_ids = {h.get("id") for h in quiz.load_holdout()}
        except Exception as exc:  # noqa: BLE001 — any load/parse failure is a fail-closed gate error
            return problems + [f"{vid}: holdout store unreadable — cannot verify gate 2 ({exc})"]
    if source_item.get("holdout") is True or variant.get("source_item_id") in holdout_ids:  # gate 2
        problems.append(f"{vid}: source is a HOLDOUT item — holdout may never seed a variant")
    if variant.get("source_item_id") != source_item.get("id"):
        problems.append(f"{vid}: source_item_id does not match the provided source item")

    if keyed_correct_index(variant_key, len(variant.get("choices_variant", []))) is None:
        problems.append(f"{vid}: isolated variant_key is missing or has an out-of-range correct_index")
    elif variant_key.get("variant_id") not in (None, vid):
        problems.append(f"{vid}: variant_key.variant_id {variant_key.get('variant_id')!r} != variant_id")
    # the key's rationale_refs must stay within the variant's grounding, like the gold trust model
    # (validate_gold enforces the same subset rule; review N2).
    if isinstance(variant_key, dict) and not set(variant_key.get("rationale_refs", [])) <= set(variant.get("fact_ids", [])):
        problems.append(f"{vid}: variant_key.rationale_refs must be a subset of the variant's fact_ids")

    problems += semantic_lock_guard(variant, source_item, _source_misconception_ids(source_key))  # 3,4,13

    # gate 5: grounding — every expected_keyword supported by cited (active, bank-eligible) cards.
    # The synthetic item's id IS the variant_id, so factstore errors already reference it.
    problems += factstore.validate_item(store, _synthetic_item(variant, source_item))

    lock = variant.get("semantic_lock", {})
    if not set(lock.get("must_include_keywords", [])) <= set(variant.get("expected_keywords", [])):
        problems.append(f"{vid}: must_include_keywords must be a subset of expected_keywords (so the "
                        "identifying keywords are grounded)")

    for mid in variant.get("misconception_ids", []):            # gate 6
        reg = registry.get(mid)
        if reg is None:
            problems.append(f"{vid}: misconception_id {mid!r} not in the registry")
            continue
        reg_obj = reg.get("objective")
        if reg_obj not in (variant.get("objective"), "global", None):
            problems.append(f"{vid}: misconception_id {mid!r} targets objective {reg_obj!r}, "
                            f"not the variant's {variant.get('objective')!r}")

    problems += lock_consistency_problems(variant, variant_key)  # gate 7 / F1
    problems += similarity_problems(variant, source_item)        # gate 12

    if variant.get("status") == "reviewed" and not (variant.get("reviewed_by") and variant.get("last_reviewed")):
        problems.append(f"{vid}: status 'reviewed' requires reviewed_by + last_reviewed")     # gate 9

    if "readiness_weight" in variant and variant["readiness_weight"] != 0:
        problems.append(f"{vid}: readiness_weight must be 0 — variants never contribute to readiness")

    return problems


def is_practice_eligible(variant: dict) -> bool:
    """Gates 8+9: ONLY an adversarially-reviewed variant with review metadata is practice-eligible.
    'validated' (passed the automated validator) and 'draft' (incl. every api_generated_local) are
    NOT eligible on their own — the status string is self-asserted, so eligibility requires the
    reviewed+metadata evidence, not a bare 'validated' flag (review F4). No variant of any status
    enters holdout or a mock draw (those pools are physically separate and never read variants)."""
    return (variant.get("status") == "reviewed"
            and bool(variant.get("reviewed_by") and variant.get("last_reviewed")))


def render_variant(variant: dict, source_item: dict, attempt_seed: str) -> dict:
    """Gate 10 + carry-forward: render a variant through the PR-10.3 presentation layer, so its
    choices shuffle per (attempt_seed, variant_id) exactly like a canonical item. The render is the
    learner_view allowlist over the synthetic item, whose topic is the SOURCE's neutral topic — so no
    answer/order field AND no answer-adjacent authoring text (must_test) reaches the learner."""
    return presentation.render_item(_synthetic_item(variant, source_item), attempt_seed)


def grade_variant(variant: dict, variant_key: dict, source_item: dict, attempt_seed: str,
                  displayed_index: int, expected_presentation_id: str = None) -> dict:
    """Carry-forward 3: grade a variant submission through the presentation layer. The correct index
    is the ISOLATED key's correct_index (not keyword-derived); fails closed if the key is malformed."""
    item = _synthetic_item(variant, source_item)
    ci = keyed_correct_index(variant_key, len(item["choices"]))
    if ci is None:
        return {"graded": False, "reason": "variant_key has no valid correct_index"}
    key = {"answer_key_ref": item["answer_key_ref"], "correct_index": ci,
           "rationale_refs": variant_key.get("rationale_refs", variant.get("fact_ids", []))}
    return presentation.grade_presented(item, [key], attempt_seed, displayed_index,
                                        expected_presentation_id=expected_presentation_id)


def variant_lineage(variant: dict) -> dict:
    """R&D: a traceable lineage record for a variant — no stems/choices/answers, so it is safe to log
    and to accumulate as api-generated remediation grows. readiness_weight is pinned to 0."""
    return {
        "variant_id": variant.get("variant_id"),
        "source_item_id": variant.get("source_item_id"),
        "source_fact_ids": sorted(variant.get("fact_ids", [])),
        "misconception_ids": sorted(variant.get("misconception_ids", [])),
        "semantic_lock_hash": semantic_lock_hash(variant),
        "review_status": variant.get("status"),
        "readiness_weight": 0,
    }
