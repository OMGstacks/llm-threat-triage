"""cc_spine CLI — the spine's runnable surface.

    python -m cc_spine.cli validate            # PR-1 scaffold gate
    python -m cc_spine.cli validate-sources    # source-registry freshness guard
    python -m cc_spine.cli check-ip            # IP-boundary support-span guard
    python -m cc_spine.cli ingest --source t.txt --source-doc-id demo [--out note.md]
    python -m cc_spine.cli factstore [validate|coverage|freeze]   # PR-3 fact store
    python -m cc_spine.cli quiz [validate|export-learner|validate-holdout|render]  # PR-8/10.3 quiz
    python -m cc_spine.cli learner replay --attempts stream.json --now 5    # PR-9 learner state
    python -m cc_spine.cli mock [assemble|validate|render] --draw-key K      # PR-10 mock assembler

Stdlib-only; no third-party dependencies.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

from . import factstore as factstore_mod
from . import ingest as ingest_mod
from . import ipboundary, learner_state, mock_exam, presentation, quiz, registry, scaffold_validate, sources

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REFERENCE = PROJECT_ROOT / "reference"
SPINE = PROJECT_ROOT / "spine"
DEFAULT_DICTIONARY = SPINE / "ingest" / "correction-dictionary.json"


def _report(title: str, failures: list[str]) -> int:
    if failures:
        print(f"FAIL {title} ({len(failures)} problem(s)):")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"OK   {title}")
    return 0


def cmd_validate(args) -> int:
    return scaffold_validate.main()


def cmd_validate_sources(args) -> int:
    today = datetime.date.fromisoformat(args.today) if args.today else None
    failures = sources.validate_registry_file(REFERENCE / "source-registry.json", today=today)
    return _report("source-registry freshness (source_freshness_guard)", failures)


def cmd_check_ip(args) -> int:
    failures = ipboundary.scan_facts(SPINE / "facts") + ipboundary.scan_notes(PROJECT_ROOT / "notes")
    verbatim = ipboundary.scan_verbatim([PROJECT_ROOT / "notes", PROJECT_ROOT / "reference"])
    ip_ok = _report("IP-boundary support spans (ip_boundary_guard)", failures)
    verbatim_ok = _report("no verbatim bulk reproduction (no_verbatim_bulk_reproduction)", verbatim)
    return 0 if ip_ok == 0 and verbatim_ok == 0 else 1


def cmd_factstore(args) -> int:
    fs = factstore_mod.FactStore()
    if args.action == "coverage":
        print(json.dumps(factstore_mod.coverage_report(fs), indent=2))
        return 0
    if args.action == "freeze":
        n = factstore_mod.freeze()
        print(f"froze {n} card fingerprint(s)")
        return 0
    # validate (default): every card + cross-card invariants + grounded items
    try:
        reg = registry.Registry()
    except Exception as exc:
        print(f"FAIL fact store: registry unavailable ({exc})")
        return 1
    store_rep = factstore_mod.validate_store(fs, reg)
    goldset_path = Path(args.goldset) if args.goldset else SPINE / "gold" / "goldset.json"
    items = json.loads(goldset_path.read_text(encoding="utf-8")).get("items", [])
    item_rep = factstore_mod.validate_items(fs, items)
    ok = store_rep["ok"] and item_rep["ok"]
    if args.json:
        print(json.dumps({"store": store_rep, "items": item_rep, "ok": ok}, indent=2))
    else:
        report = factstore_mod.coverage_report(fs)
        print(f"fact store: {report['cards_total']} card(s), "
              f"{report['cards_active']} active, {report['sensitive']} sensitive; "
              f"{len(items)} goldset item(s)")
        for err in store_rep["errors"]:
            print(f"  STORE ERR {err}")
        for iid, errs in item_rep["errors"].items():
            for err in errs:
                print(f"  ITEM ERR {err}")
        print(f"{'OK  ' if ok else 'FAIL'} fact store validate "
              "(drift, tombstones, eligibility, answer-key quarantine, unsupported_claim_guard)")
    return 0 if ok else 1


def cmd_quiz(args) -> int:
    """PR-8a quiz-engine gate: validate the gold item set against its isolated
    answer-key store. Proves grounding, key resolution + hash integrity, answer-key
    isolation, and the near-duplicate stem gate in one pass."""
    fs = factstore_mod.FactStore()
    goldset_path = Path(args.goldset) if args.goldset else quiz.GOLDSET_PATH
    keys_path = Path(args.answer_keys) if args.answer_keys else quiz.ANSWER_KEYS_PATH
    items = json.loads(goldset_path.read_text(encoding="utf-8")).get("items", [])
    keys = quiz.load_answer_keys(keys_path)

    if args.action == "export-learner":
        # The ONLY learner-facing representation. Reads the PRACTICE goldset only —
        # never the holdout lane. CI scans this output for answer-bearing fields.
        print(json.dumps([quiz.learner_view(it) for it in items], indent=2))
        return 0

    if args.action == "render":
        # PR-10.3: a per-ATTEMPT presented quiz — choices shuffled by (attempt_seed, item_id),
        # canonical goldset untouched. Learner-safe (no answers); CI scans this output too.
        # The seed is REQUIRED and must be fresh per attempt (review F2): a fixed default would
        # reproduce the same order every attempt and defeat the anti-memorization intent.
        if not args.attempt_seed:
            print("FAIL quiz render requires --attempt-seed (a fresh per-attempt value); "
                  "reusing a seed reproduces the same choice order", file=sys.stderr)
            return 2
        subset = [it for it in items if it["id"] == args.item_id] if args.item_id else items
        print(json.dumps(presentation.render_quiz(subset, args.attempt_seed), indent=2))
        return 0

    if args.action == "validate-holdout":
        # Explicit evaluator command — the only path that opens the holdout lane.
        hold = quiz.load_holdout()
        hkeys = quiz.load_holdout_keys()
        rep = quiz.validate_gold(fs, hold, hkeys)
        part = quiz.holdout_partition_problems(items, hold)
        leak = quiz.holdout_leakage_problems([quiz.learner_view(it) for it in items], hold, hkeys)
        print(f"holdout lane: {len(hold)} item(s), {len(hkeys)} isolated key(s)")
        return _report(
            "holdout validate (same item gates + lane partition + no-leak into practice)",
            rep["errors"] + part + leak,
        )

    rep = quiz.validate_gold(fs, items, keys)
    bias = quiz.answer_length_bias(items, keys)
    if args.json:
        print(json.dumps({**rep, "answer_length_bias": bias}, indent=2))
        return 0 if rep["ok"] else 1
    print(f"gold set: {len(items)} item(s), {len(keys)} isolated key(s)")
    # advisory (non-failing) anti-gaming metric
    if bias["ratio"] > bias["warn_threshold"]:
        print(f"  WARN answer-length bias: correct is the longest choice in "
              f"{bias['longest_correct']}/{bias['total']} items ({bias['ratio']:.0%} > "
              f"{bias['warn_threshold']:.0%} target)")
    return _report(
        "gold items validate (grounding, isolation, hash drift, near-dup, length/parity tells)",
        rep["errors"],
    )


def cmd_learner(args) -> int:
    """PR-9 learner-state demo: replay a synthetic attempt stream and print the wrong-answer
    journal, the spaced-repetition review queue, and the partial readiness readout. Operates
    only on committed practice content + the injected stream — it writes no learner data."""
    attempts = json.loads(Path(args.attempts).read_text(encoding="utf-8"))
    try:
        state = learner_state.replay(attempts, now=args.now)
    except learner_state.LearnerStateError as exc:
        print(f"FAIL learner replay rejected an attempt: {exc}")
        return 1
    queue = learner_state.review_queue(state, now=args.now)
    readiness = learner_state.readiness_report(state)
    if args.json:
        print(json.dumps({"state": state, "review_next": queue, "readiness": readiness}, indent=2))
        return 0
    r = state["readiness"]
    print(f"learner replay: {state['attempts_replayed']} attempt(s) → "
          f"{len(state['journal'])} journal entry(ies), {len(state['items'])} item(s) tracked")
    print(f"  wrong-answer closure rate: {r['wrong_answer_closure_rate']:.0%}")
    print(f"  readiness: {readiness['verdict']} (score {readiness['score']:.0%}"
          f"{'' if readiness['complete'] else ', incomplete — no mock yet'})")
    for b in readiness["hard_blockers"]:
        print(f"    BLOCKER {b}")
    for j in learner_state.open_journal(state):
        print(f"  OPEN  {j['item_id']} [{j['objective']}] trap={j['misconception_id']} — {j['one_sentence_rule']}")
    print(f"  review next ({len(queue)}): {', '.join(queue[:8])}{' …' if len(queue) > 8 else ''}")
    return 0


def cmd_mock(args) -> int:
    """PR-10 mock-exam assembler: draw a mock per the banks.json policy (domain-weighted,
    scenarios holdout-only) and validate its policy conformance. Deterministic in draw_key.
    ``render`` (PR-10.2) emits the exposure receipt + burn warning any render path must honour."""
    mock = mock_exam.assemble(args.draw_key, count=args.count)
    if args.action == "assemble":
        print(json.dumps(mock, indent=2))
        return 0
    if args.action == "render":
        return _mock_render(mock)
    print(f"mock '{args.draw_key}': {mock['assembled']}/{mock['requested']} items"
          + (f"; notes: {mock['notes']}" if mock["notes"] else ""))
    return _report(
        "mock exam draw (holdout-only scenarios, banks in draw_from, no duplicates)",
        mock_exam.validate_mock(mock),
    )


def _mock_render(mock) -> int:
    """PR-10.2 exposure-receipt proof: emit the content-free receipt to stdout and, if the mock
    exposes any holdout scenario, the burn obligation to stderr — so this render path surfaces
    'these ids must be burned' rather than hiding it. The learner items themselves are NOT printed
    here: the receipt (ids + counts, no content) is the operational artifact; a real UI renders items
    via mock_exam.render_mock, the sanctioned public render that carries this same receipt."""
    receipt = mock_exam.mock_exposure_receipt(mock)
    print(json.dumps(receipt, indent=2))
    if receipt["burn_required"]:
        print(f"WARNING burn-on-exposure: this mock exposes {receipt['holdout_exposure_count']} "
              f"holdout scenario(s) {receipt['exposed_holdout_ids']}; the caller MUST persist these "
              f"as burned before discarding the mock (PR-10 F2 / PR-10.2).", file=sys.stderr)
    else:
        print("note: no holdout scenarios exposed in this mock; nothing to burn.", file=sys.stderr)
    return 0


def cmd_ingest(args) -> int:
    dictionary = json.loads(Path(args.dictionary).read_text(encoding="utf-8"))
    domains = set(args.domains.split(",")) if args.domains else None
    note = ingest_mod.ingest(
        Path(args.source), args.source_doc_id, dictionary,
        source_tier=args.source_tier, outline_version=args.outline_version,
        reviewed_by=args.reviewed_by, status=args.status, domains=domains,
    )
    fm_problems = ingest_mod.validate_note_frontmatter(note)
    if fm_problems:
        print("FAIL produced note failed front-matter validation:", file=sys.stderr)
        for problem in fm_problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    if args.out:
        Path(args.out).write_text(note, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(note)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cc_spine.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="run the PR-1 scaffold gate").set_defaults(func=cmd_validate)

    p_src = sub.add_parser("validate-sources", help="source-registry freshness guard")
    p_src.add_argument("--today", help="override reference date (ISO), for testing")
    p_src.set_defaults(func=cmd_validate_sources)

    sub.add_parser("check-ip", help="IP-boundary support-span guard").set_defaults(func=cmd_check_ip)

    p_fs = sub.add_parser(
        "factstore",
        help="fact-store validator (PR-3): provenance, drift, tombstones, "
             "eligibility, answer-key quarantine")
    p_fs.add_argument("action", nargs="?", default="validate",
                      choices=["validate", "coverage", "freeze"])
    p_fs.add_argument("--goldset", default=None, help="override goldset path (testing)")
    p_fs.add_argument("--json", action="store_true", help="emit the full JSON report")
    p_fs.set_defaults(func=cmd_factstore)

    p_quiz = sub.add_parser(
        "quiz",
        help="quiz-engine gate (PR-8a): validate gold items + answer-key isolation")
    p_quiz.add_argument("action", nargs="?", default="validate",
                        choices=["validate", "export-learner", "validate-holdout", "render"])
    p_quiz.add_argument("--goldset", default=None, help="override goldset path (testing)")
    p_quiz.add_argument("--answer-keys", default=None, help="override answer-key store path (testing)")
    p_quiz.add_argument("--json", action="store_true", help="emit the full JSON report")
    p_quiz.add_argument("--attempt-seed", default=None,
                        help="PR-10.3 render: REQUIRED per-attempt seed for the choice shuffle. "
                             "Supply a fresh, distinct value per attempt (a counter/uuid) — reusing "
                             "one reproduces the same order and defeats the anti-memorization intent")
    p_quiz.add_argument("--item-id", default=None, help="PR-10.3 render: render a single item")
    p_quiz.set_defaults(func=cmd_quiz)

    p_mock = sub.add_parser("mock",
        help="mock-exam assembler (PR-10): assemble/validate/render (render prints the burn receipt)")
    p_mock.add_argument("action", nargs="?", default="validate",
                        choices=["assemble", "validate", "render"])
    p_mock.add_argument("--draw-key", required=True, help="deterministic seed for the draw")
    p_mock.add_argument("--count", type=int, default=15, help="target item count")
    p_mock.set_defaults(func=cmd_mock)

    p_learn = sub.add_parser(
        "learner", help="learner-state demo (PR-9): replay a synthetic attempt stream")
    p_learn.add_argument("action", nargs="?", default="replay", choices=["replay"])
    p_learn.add_argument("--attempts", required=True, help="path to a JSON attempt stream")
    p_learn.add_argument("--now", type=int, default=0, help="injected current time unit")
    p_learn.add_argument("--json", action="store_true", help="emit the full state as JSON")
    p_learn.set_defaults(func=cmd_learner)

    p_ing = sub.add_parser("ingest", help="extract + suggest corrections + build a note")
    p_ing.add_argument("--source", required=True, help="path to a .docx or .txt source")
    p_ing.add_argument("--source-doc-id", required=True, help="stable local id for provenance")
    p_ing.add_argument("--dictionary", default=str(DEFAULT_DICTIONARY))
    p_ing.add_argument("--source-tier", type=int, default=3)
    p_ing.add_argument("--outline-version", default="2025-10")
    p_ing.add_argument("--reviewed-by", default=None)
    p_ing.add_argument("--status", default="draft")
    p_ing.add_argument("--domains", default=None, help="comma-separated domain filter (e.g. D4,D5)")
    p_ing.add_argument("--out", default=None, help="write note here instead of stdout")
    p_ing.set_defaults(func=cmd_ingest)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
