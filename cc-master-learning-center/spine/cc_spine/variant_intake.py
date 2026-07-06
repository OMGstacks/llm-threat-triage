"""cc_spine.variant_intake — locked API-prompt scaffold + local draft-runtime intake (PR-10.4b).

PR-10.4a shipped the variant VALIDATOR (``variants.validate_variant``). This module is the pipeline
around it: it BUILDS the locked generation prompt for a missed practice item, and it VALIDATES
untrusted candidate output (the reviewer's JSON contract) into a local, gitignored draft. There is
deliberately **no live API provider here** (that is PR-12): the pipeline is pure, deterministic
stdlib — no network, no wall clock, no randomness — so it can prove it rejects bad candidates before
any provider is ever wired in.

Trust model:
- The PROMPT is evaluator/generator context. It names the tested concept, the misconception target,
  and the correct-answer CONCEPT (from the misconception registry's ``correct`` field — never the
  keyed correct-choice text, which the API would echo verbatim). It contains NO source stem/choices
  (nothing to near-duplicate, nothing quoted outward) and must never be shown to a learner.
- The CANDIDATE is untrusted input. ``parse_candidate`` enforces a closed 5-key contract fail-closed;
  ``assemble_draft`` derives the correct index as the SINGLE choice index absent from the candidate's
  distractor map; the result then passes the FULL PR-10.4a gate set plus the intake gates I1-I10
  (self-check is verified but never trusted alone — the reviewer's rule).
- The DRAFT is local runtime data: ``status=draft``, ``source=api_generated_local``,
  ``readiness_weight=0``, written only under a gitignored dir (default ``.local/variant-drafts/``)
  with the explicit answer FIELDS in a separate ``*.draft.key.json`` file (the candidate's
  distractor map is answer-bearing — the absent index IS the answer — so it lives in the key file).
  The separation is FIELD-level, not information-level (review F2): the draft body remains
  answer-DEDUCIBLE via its semantic_lock — gate 7 guarantees exactly one choice carries the
  must_include keywords — which is inherent to the lock-corroboration design and acceptable for an
  evaluator-context local file that is never rendered to a learner. Drafts are never
  practice-eligible (``variants.is_practice_eligible`` demands reviewed+metadata), never enter
  holdout or a mock draw, and cannot touch readiness (``learner_state.replay`` raises on a
  variant id).

Residual risk (documented, not hidden — the PR-10.4a N3 class): a deliberate adversary that echoes
the correct concept AND plants the lock keywords on a semantically wrong choice defeats every text
gate. Automated gates cannot verify semantic correctness; such a candidate still lands only in a
DRAFT no learner-facing path consumes, and the mandatory human adversarial review is the promotion
backstop.

Stdlib only. Imports ``factstore``, ``quiz``, ``learner_state``, ``variants``; imported by none.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import factstore, learner_state, quiz, variants

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[3]
DRAFT_DIR = _PROJECT_ROOT / ".local" / "variant-drafts"

_CANDIDATE_KEYS = frozenset({"stem_variant", "choices_variant", "correct_choice_concept",
                             "distractor_misconceptions", "self_check"})
_SELF_CHECK_KEYS = frozenset({"same_tested_concept", "single_best_answer", "no_new_facts"})
_INDEX_RE = re.compile(r"^(0|[1-9][0-9]*)$")

# The reviewer's locked prompt template (PR-10.4b spec). Slot VALUES are filled per request; the
# template TEXT is fixed. One flagged deviation (see build_variant_prompt): the correct-concept slot
# value also names the exact must_include phrase(s), because gate 7 requires the keyed choice to
# carry them — a generator that is never told cannot pass except by luck.
PROMPT_TEMPLATE = """Generate a new practice-question variant.

You must preserve:
- Objective: {objective}
- Bank: {bank}
- Fact IDs: {fact_ids}
- Tested concept: {must_test}
- Misconception targeted: {misconception_ids}
- Correct answer concept: {correct_concept}

You may change:
- Surface scenario
- Names
- Wording
- Choice phrasing

You must not:
- Add new facts
- Change the correct concept
- Use real certification exam questions
- Quote transcript text
- Use holdout content
- Reveal answer-key metadata

Return JSON only:
{{
  "stem_variant": "...",
  "choices_variant": [{choice_slots}],
  "correct_choice_concept": "...",
  "distractor_misconceptions": {{"<wrong choice index>": "<misconception_id>"}},
  "self_check": {{
    "same_tested_concept": true,
    "single_best_answer": true,
    "no_new_facts": true
  }}
}}"""


class VariantIntakeError(Exception):
    """A request cannot be built (holdout source, unresolved key/registry, empty concept)."""


def variant_id_for(source_item_id: str, draw_key: str) -> str:
    """Deterministic variant id: sha256(source, draw_key) -> .vNNN in the schema's 3-digit space.
    Pure function of its inputs (no clock, no counter, reproducible across machines). Collisions in
    the 1000-space are handled at write time (write_draft refuses a same-id draft recorded under a
    DIFFERENT draw_key)."""
    digest = hashlib.sha256(f"{source_item_id}\x1f{draw_key}".encode("utf-8")).hexdigest()
    return f"{source_item_id}.v{int(digest, 16) % 1000:03d}"


def build_variant_request(source_item: dict, source_key: dict, store, registry: dict,
                          draw_key: str, holdout_ids=None) -> dict:
    """The locked generation request for one missed practice item. Everything the generator must
    preserve is derived HERE, from governed stores — never from the candidate. Fails closed
    (VariantIntakeError) on a holdout source, an unresolved source key, an unresolved registry
    entry, or an empty registry ``correct`` text."""
    sid = source_item.get("id", "<no-id>")
    if holdout_ids is None:
        try:
            holdout_ids = {h.get("id") for h in quiz.load_holdout()}
        except Exception as exc:  # noqa: BLE001 — unreadable governance store = fail closed
            raise VariantIntakeError(f"{sid}: holdout store unreadable — cannot verify source lane ({exc})")
    if source_item.get("holdout") is True or sid in holdout_ids:
        raise VariantIntakeError(f"{sid}: holdout items may never seed a variant")

    mapping = (source_key or {}).get("distractor_misconceptions")
    if not isinstance(mapping, dict) or not mapping:
        raise VariantIntakeError(f"{sid}: source item has no resolvable answer key / distractor map")
    misconception_ids = sorted({e.get("misconception_id") for e in mapping.values()
                                if isinstance(e, dict) and e.get("misconception_id")})
    if not misconception_ids:
        raise VariantIntakeError(f"{sid}: source key's distractor map names no misconception ids")

    # Correct answer CONCEPT = the registry's 'correct' texts for the targeted misconceptions —
    # concept-level and already learner-visible via journal corrections; never the keyed choice text.
    corrections = []
    for mid in misconception_ids:
        entry = registry.get(mid)
        if entry is None:
            raise VariantIntakeError(f"{sid}: misconception {mid!r} does not resolve in the registry")
        text = (entry.get("correct") or "").strip()
        if not text:
            raise VariantIntakeError(f"{sid}: registry entry {mid!r} has no 'correct' text")
        corrections.append(text)
    correct_concept = "; ".join(corrections)

    rationale_refs = sorted(source_key.get("rationale_refs", []) or source_item.get("fact_ids", []))
    if not rationale_refs:
        raise VariantIntakeError(f"{sid}: source has no rationale_refs/fact_ids to ground a variant")
    card = store.cards.get(rationale_refs[0])
    if card is None:
        raise VariantIntakeError(f"{sid}: grounding card {rationale_refs[0]!r} does not resolve")

    return {
        "variant_id": variant_id_for(sid, draw_key),
        "source_item_id": sid,
        "objective": source_item.get("objective"),
        "bank": source_item.get("bank"),
        "fact_ids": sorted(source_item.get("fact_ids", [])),
        "expected_keywords": sorted(source_item.get("expected_keywords", [])),
        "misconception_ids": misconception_ids,
        "must_test": card.get("claim"),
        "correct_concept": correct_concept,
        "must_include_keywords": sorted(source_item.get("expected_keywords", [])),
        "n_choices": len(source_item.get("choices", [])),
        "rationale_refs": rationale_refs,
        "draw_key": draw_key,
    }


def build_variant_prompt(request: dict) -> str:
    """Render the locked template — a pure, byte-deterministic function of the request. The prompt
    deliberately contains NO source stem or choices: nothing to quote outward, nothing for the API to
    near-duplicate. FLAGGED DEVIATION from the reviewer's template (report §): the correct-concept
    slot VALUE also names the exact must_include phrase(s), or no candidate could satisfy gate 7."""
    kws = ", ".join(f'"{k}"' for k in request["must_include_keywords"])
    concept = (f"{request['correct_concept']} "
               f"(the correct choice must contain the exact phrase(s): {kws})")
    return PROMPT_TEMPLATE.format(
        objective=request["objective"],
        bank=request["bank"],
        fact_ids=", ".join(request["fact_ids"]),
        must_test=request["must_test"],
        misconception_ids=", ".join(request["misconception_ids"]),
        correct_concept=concept,
        choice_slots=", ".join(['"..."'] * max(request["n_choices"], 2)),
    )


def _norm(text: str) -> str:
    return " ".join(str(text).lower().split())


def parse_candidate(raw) -> tuple:
    """Fail-closed shape validation of the raw candidate (gates I1-I3). ``raw`` may be a JSON string
    or an already-decoded dict. Returns (candidate|None, problems)."""
    problems = []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            return None, [f"candidate is not valid JSON ({exc})"]
    if not isinstance(raw, dict):
        return None, ["candidate must be a JSON object"]

    unknown = sorted(set(raw) - _CANDIDATE_KEYS)                              # I1: closed object
    missing = sorted(_CANDIDATE_KEYS - set(raw))
    if unknown:
        problems.append(f"candidate carries disallowed field(s) {unknown} (closed 5-key contract)")
    if missing:
        problems.append(f"candidate is missing required field(s) {missing}")

    stem = raw.get("stem_variant")
    if not isinstance(stem, str) or not stem.strip():
        problems.append("stem_variant must be a non-empty string")
    choices = raw.get("choices_variant")
    if (not isinstance(choices, list) or not (2 <= len(choices) <= 6)
            or not all(isinstance(c, str) and c.strip() for c in choices)):
        problems.append("choices_variant must be 2-6 non-empty strings")
    elif len({_norm(c) for c in choices}) != len(choices):
        problems.append("choices_variant contains duplicate choices (after normalization)")
    if not isinstance(raw.get("correct_choice_concept"), str) or not raw.get("correct_choice_concept", "").strip():
        problems.append("correct_choice_concept must be a non-empty string")
    mapping = raw.get("distractor_misconceptions")
    if not isinstance(mapping, dict):
        problems.append("distractor_misconceptions must be an object")
    else:
        # values must be plain non-empty strings (the schema's additionalProperties contract) —
        # a dict/list value is an open channel for arbitrary untrusted JSON (review F1).
        for k, v in mapping.items():
            if not isinstance(v, str) or not v.strip():
                problems.append(f"distractor_misconceptions[{k!r}] must be a non-empty string "
                                "misconception id (no nested objects)")

    sc = raw.get("self_check")                                                # I2: strict booleans
    if not isinstance(sc, dict) or set(sc) != set(_SELF_CHECK_KEYS):
        problems.append(f"self_check must carry exactly {sorted(_SELF_CHECK_KEYS)}")
    else:
        for k in sorted(_SELF_CHECK_KEYS):
            if sc.get(k) is not True:
                problems.append(f"self_check.{k} is not strictly true — candidate rejected "
                                "(and the self-check is never trusted alone)")

    secrets = factstore.residual_secrets(raw)                                 # I3
    if secrets:
        problems.append(f"candidate contains residual secret pattern(s): {secrets}")

    return (raw if not problems else None), problems


def assemble_draft(request: dict, candidate: dict) -> tuple:
    """Assemble (variant, variant_key, problems) from a parsed candidate. Gate I4: the correct index
    is the SINGLE choice index in 0..n-1 absent from the candidate's distractor map (canonical
    decimal keys, in range, unique) — anything else fails closed. The intake FORCES status=draft,
    source=api_generated_local, readiness_weight=0; the candidate can never assert them."""
    problems = []
    choices = candidate.get("choices_variant", [])
    n = len(choices)
    mapping = candidate.get("distractor_misconceptions", {})

    mapped = set()
    for key in mapping:                                                       # I4
        if not isinstance(key, str) or not _INDEX_RE.match(key):
            problems.append(f"distractor index {key!r} is not a canonical decimal string")
            continue
        idx = int(key)
        if not (0 <= idx < n):
            problems.append(f"distractor index {key} out of range for {n} choices")
            continue
        # duplicate indices cannot occur: JSON object keys are unique post-parse and the
        # canonical-decimal regex forbids alternate spellings of the same integer (review F6).
        mapped.add(idx)
    unmapped = [i for i in range(n) if i not in mapped]
    if problems or len(unmapped) != 1:
        if len(unmapped) != 1:
            problems.append(f"distractor map must leave exactly ONE unmapped choice (the correct "
                            f"one); found {len(unmapped)} unmapped of {n}")
        return None, None, problems
    correct_index = unmapped[0]

    variant = {
        "variant_id": request["variant_id"],
        "source_item_id": request["source_item_id"],
        "objective": request["objective"],
        "bank": request["bank"],
        "fact_ids": list(request["fact_ids"]),
        "expected_keywords": list(request["expected_keywords"]),
        "misconception_ids": list(request["misconception_ids"]),
        "semantic_lock": {
            "must_test": request["must_test"],
            "correct_concept": request["correct_concept"],
            "must_include_keywords": list(request["must_include_keywords"]),
            "must_not_change": ["objective", "bank", "fact_ids", "misconception_ids"],
        },
        "stem_variant": candidate["stem_variant"],
        "choices_variant": list(choices),
        "status": "draft",                       # forced — never candidate-asserted (I10)
        "source": "api_generated_local",
        "readiness_weight": 0,
    }
    variant_key = {
        "variant_id": request["variant_id"],
        "correct_index": correct_index,
        "rationale_refs": list(request["rationale_refs"]),
        # answer-bearing: the map's ABSENT index is the answer — key file only, never the draft.
        "distractor_misconceptions": dict(mapping),
    }
    return variant, variant_key, []


def intake_problems(request: dict, candidate: dict, variant: dict, variant_key: dict,
                    source_item: dict, holdout_items) -> list:
    """The intake-specific gates I5-I10 (on top of variants.validate_variant's 13)."""
    vid = variant["variant_id"]
    problems = []

    for key, mid in candidate.get("distractor_misconceptions", {}).items():   # I5
        # values are guaranteed plain strings by parse_candidate (review F1); no dict shape here.
        if mid not in request["misconception_ids"]:
            problems.append(f"{vid}: distractor {key} names {mid!r}, outside the request's "
                            f"targets {request['misconception_ids']}")

    # I6 — ADVISORY against accidental mislabeling only (review F5): one-directional token
    # containment catches the realistic bug (a generator that mislabeled the correct choice
    # returns a diverging concept) but a deliberate adversary can satisfy it by concatenation.
    # Correctness rests on gate 7 + the derived index; semantics on human review (N3 residual).
    concept_tokens = quiz._stem_tokens(request["correct_concept"])
    returned = candidate.get("correct_choice_concept", "")
    if len(returned.strip()) <= 1:
        problems.append(f"{vid}: correct_choice_concept is a bare letter/index, not a concept")
    elif concept_tokens and not concept_tokens <= quiz._stem_tokens(returned):
        problems.append(f"{vid}: correct_choice_concept does not carry the request's correct "
                        "concept — the generator may have mislabeled which choice is correct")

    if len(variant["choices_variant"]) != request["n_choices"]:               # I7
        problems.append(f"{vid}: choice count {len(variant['choices_variant'])} != source's "
                        f"{request['n_choices']} (difficulty drift)")

    blob = _norm(variant["stem_variant"] + " " + " ".join(variant["choices_variant"]))  # I8
    stem_tokens = quiz._stem_tokens(variant["stem_variant"])
    for h in holdout_items:
        h_stem = h.get("stem", "")
        if _norm(h_stem) and _norm(h_stem) in blob:
            problems.append(f"{vid}: holdout stem {h.get('id')} appears verbatim in the candidate")
        elif quiz._jaccard(stem_tokens, quiz._stem_tokens(h_stem)) >= quiz._NEAR_DUP_THRESHOLD:
            problems.append(f"{vid}: candidate stem is a near-duplicate of holdout {h.get('id')} "
                            "(holdout contamination)")

    item = variants._synthetic_item(variant, source_item)                     # I9
    qkey = {"answer_key_ref": item["answer_key_ref"],
            "correct_index": variant_key["correct_index"]}
    problems += quiz.answer_length_problems([item], [qkey])
    problems += quiz.choice_parallelism_problems([item])

    for field, want in (("status", "draft"), ("source", "api_generated_local"),  # I10
                        ("readiness_weight", 0)):
        if variant.get(field) != want:
            problems.append(f"{vid}: draft invariant violated — {field} must be {want!r}")
    return problems


def validate_candidate(raw, source_item: dict, source_key: dict, store, registry: dict,
                       draw_key: str, holdout_items=None, holdout_ids=None) -> dict:
    """The full intake: parse -> request -> assemble -> the PR-10.4a 13-gate validator -> the intake
    gates. Returns {ok, variant, variant_key, problems}; fail-closed at every stage."""
    candidate, problems = parse_candidate(raw)
    if candidate is None:
        return {"ok": False, "variant": None, "variant_key": None, "problems": problems}
    # Load the holdout store ONCE and derive the id set from it (review F8) — one consistent
    # snapshot feeds the request check, the 13-gate validator, and the contamination gate.
    if holdout_items is None:
        try:
            holdout_items = quiz.load_holdout()
        except Exception as exc:  # noqa: BLE001 — fail closed on an unreadable governance store
            return {"ok": False, "variant": None, "variant_key": None,
                    "problems": [f"holdout store unreadable — cannot run intake gates ({exc})"]}
    if holdout_ids is None:
        holdout_ids = {h.get("id") for h in holdout_items}
    try:
        request = build_variant_request(source_item, source_key, store, registry, draw_key,
                                        holdout_ids=holdout_ids)
    except VariantIntakeError as exc:
        return {"ok": False, "variant": None, "variant_key": None, "problems": [str(exc)]}
    variant, variant_key, asm_problems = assemble_draft(request, candidate)
    if variant is None:
        return {"ok": False, "variant": None, "variant_key": None, "problems": asm_problems}
    problems = variants.validate_variant(variant, variant_key, source_item, source_key,
                                         store, registry, holdout_ids=holdout_ids)
    problems += intake_problems(request, candidate, variant, variant_key, source_item, holdout_items)
    return {"ok": not problems, "variant": variant, "variant_key": variant_key, "problems": problems}


def _out_dir_allowed(out_dir: Path) -> bool:
    """Drafts may be written only OUTSIDE the repo (e.g. /tmp, $RUNNER_TEMP) or under the project's
    gitignored ``.local/`` — never into a committable location."""
    out = out_dir.resolve()
    if out.is_relative_to(_PROJECT_ROOT / ".local"):
        return True
    return not out.is_relative_to(_REPO_ROOT)


def write_draft(variant: dict, variant_key: dict, draw_key: str, out_dir: Path = DRAFT_DIR) -> tuple:
    """Persist a validated draft: ``<vid>.draft.json`` = {draw_key, variant} and the answer-bearing
    ``<vid>.draft.key.json`` PHYSICALLY separate. Refuses a committable out dir; refuses an existing
    draft recorded under a DIFFERENT draw_key (id collision); same draw_key overwrites idempotently."""
    out_dir = Path(out_dir)
    if not _out_dir_allowed(out_dir):
        raise VariantIntakeError(f"refusing to write drafts into a committable location: {out_dir} "
                                 "(use .local/variant-drafts or a directory outside the repo)")
    out_dir.mkdir(parents=True, exist_ok=True)
    vid = variant["variant_id"]
    draft_path = out_dir / f"{vid}.draft.json"
    key_path = out_dir / f"{vid}.draft.key.json"
    if draft_path.exists():
        try:
            recorded = json.loads(draft_path.read_text(encoding="utf-8")).get("draw_key")
        except (OSError, json.JSONDecodeError, ValueError) as exc:   # review F7: fail closed
            raise VariantIntakeError(f"{vid}: existing draft is unreadable ({exc}) — refusing to "
                                     "overwrite; inspect or remove it manually")
        if recorded != draw_key:
            raise VariantIntakeError(f"{vid}: draft already exists under draw_key {recorded!r} — "
                                     "variant-id collision; choose a new draw key")
    draft_path.write_text(json.dumps({"draw_key": draw_key, "variant": variant},
                                     indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    key_path.write_text(json.dumps(variant_key, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    return draft_path, key_path


def open_journal_requests(attempts, now: int) -> list:
    """Which missed items are eligible for variant generation: replay the attempt stream (the engine
    rejects holdout/unknown ids fail-closed) and project the OPEN wrong-answer journal entries —
    ids and misconception targets only, no answer content."""
    state = learner_state.replay(attempts, now=now)
    return [{"item_id": j.get("item_id"), "objective": j.get("objective"), "bank": j.get("bank"),
             "misconception_id": j.get("misconception_id")}
            for j in learner_state.open_journal(state)]
