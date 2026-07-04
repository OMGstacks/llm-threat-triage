"""osai_spine CLI — the spine's runnable surface.

    python -m osai_spine.cli catalog
    python -m osai_spine.cli validate-manifests
    python -m osai_spine.cli derive-flag --seed S --learner alice --lab L01
    python -m osai_spine.cli grade --lab L01 --transcript t.json \
        --flag 'OSAI{...}' --seed S --learner alice
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import engine, flags
from . import manifest as manifest_mod
from .taxonomy import TaxonomyRegistry
from .validator import ChallengeValidator

LABS_DIR = Path(__file__).resolve().parents[1] / "labs"


def cmd_catalog(args) -> int:
    reg = TaxonomyRegistry()
    print(json.dumps(
        {
            "engine": engine.ENGINE_PATH,
            "detectors": reg.detector_names(),
            "owasp_llm_2025": reg.owasp,
            "owasp_agentic_T1_T15": reg.agentic,
        },
        indent=2,
    ))
    return 0


def cmd_validate(args) -> int:
    reg = TaxonomyRegistry()
    report = manifest_mod.validate_dir(args.labs or LABS_DIR, reg)
    ok = True
    if not report:
        print(f"(no manifests found in {args.labs or LABS_DIR})")
    for name, errs in report.items():
        if errs:
            ok = False
            print(f"FAIL {name}")
            for e in errs:
                print(f"   - {e}")
        else:
            print(f"OK   {name}")
    return 0 if ok else 1


def cmd_flag(args) -> int:
    print(flags.derive_flag(args.seed, args.learner, args.lab, args.attempt))
    return 0


def cmd_tutor(args) -> int:
    from . import llm as llm_mod
    from .tutor import Tutor

    # Wire the generative provider when the key is live (else offline extractive).
    provider = llm_mod.LLMProvider() if llm_mod.enabled() else None
    tutor = Tutor(registry=TaxonomyRegistry(), llm=provider)
    print(json.dumps(tutor.ask(args.query, args.mode), indent=2))
    return 0


def cmd_llm(args) -> int:
    """Safe presence check — prints only yes/no, NEVER the key value, prefix, suffix,
    length, or hash (docs/security/api-key-and-data-handling.md)."""
    from . import llm as llm_mod

    yn = lambda b: "yes" if b else "no"  # noqa: E731
    print(f"ANTHROPIC_API_KEY present: {yn(llm_mod.key_present())} (source: {llm_mod.key_source()})")
    print(f"anthropic SDK installed:   {yn(llm_mod.sdk_available())}")
    print(f"OSAI_LLM (tutor) enabled:  {yn(llm_mod.enabled())}")
    print(f"OSAI_LLM_TRANSCRIPTS gate: {yn(llm_mod.transcripts_enabled())}")
    print(f"model (quality / bulk):    {llm_mod.MODEL_QUALITY} / {llm_mod.MODEL_BULK}")
    if getattr(args, "ping", False):
        if not llm_mod.enabled():
            print("ping: skipped — need ANTHROPIC_API_KEY (or _FILE) + the anthropic SDK + OSAI_LLM=1")
            return 1
        try:
            out = llm_mod.LLMProvider().complete(
                "You are a connectivity check. Reply with exactly: OK", "ping", max_tokens=16)
            print(f"ping: live model replied -> {out!r}")
            return 0
        except Exception as exc:  # surface the real reason (401, bad base_url, network…)
            print(f"ping: FAILED -> {type(exc).__name__}: {exc}")
            return 1
    return 0


def cmd_narrate(args) -> int:
    """Narration (TTS) seam — the plumbing for narrated lessons (27-narrated-lessons.md).
    `status` prints the presence-only seam state; `plan` parses a lesson script and prints
    the offline render plan (segments / duration / cost / cache keys) needing no provider;
    `render` writes the timing manifest and renders audio when a provider is enabled."""
    import json as _json
    from . import narration as nar

    if args.action == "status":
        st = nar.status()
        yn = lambda b: "yes" if b else "no"  # noqa: E731
        print(f"provider:            {st['provider']} ({st['kind']})")
        print(f"key ({st['key_env'] or 'none'}):  present={yn(st['key_present'])} source={st['key_source']}")
        print(f"provider available:  {yn(st['available'])}")
        print(f"OSAI_TTS render on:  {yn(st['render_enabled'])}")
        print(f"cost (US$/1M chars): {st['rate_per_million_usd']}  [planning estimate]")
        print(f"providers:           {', '.join(st['providers'])}")
        return 0

    if not args.script:
        print("error: --script is required for this action")
        return 2
    src = Path(args.script).read_text(encoding="utf-8")
    try:
        script = _json.loads(src)          # structured script …
    except _json.JSONDecodeError:
        script = src                       # … or plain-text paragraphs

    if args.action == "plan":
        plan = nar.render_plan(script)
        if args.json:
            print(_json.dumps(plan, indent=2))
        else:
            print(f"lesson {plan['lesson_id']!r}: {plan['segment_count']} segments · "
                  f"{plan['total_chars']} chars · ~{plan['est_duration']} · "
                  f"provider={plan['provider']} · est ${plan['est_cost_usd']} one-time")
            for s in plan["segments"]:
                print(f"  {s['id']}  {s['chars']:>5}ch  ~{s['est_seconds']}s  -> {s['audio']}")
        return 0

    # action == "render": always writes the manifest; renders audio only when enabled.
    out = args.out or "narration"
    res = nar.write_manifest(script, out)
    print(f"manifest: {res['manifest']}  ({res['plan']['segment_count']} segments)")
    if not nar.render_enabled():
        print(f"audio: not rendered — seam off (set OSAI_TTS=1 + configure provider "
              f"'{nar.provider_name()}'). Manifest + captions are ready; drop audio in later.")
        return 0
    rendered = 0
    for s in res["plan"]["segments"]:
        seg = next(x for x in nar.parse_script(script)["segments"] if x["id"] == s["id"])
        r = nar.render_segment(seg["text"], Path(out) / s["audio"], voice=res["plan"]["voice"])
        if r.get("rendered"):
            rendered += 1
        else:
            print(f"  {s['id']}: {r['reason']}")
    print(f"audio: rendered {rendered}/{res['plan']['segment_count']} segments to {out}/")
    return 0


def cmd_transcripts(args) -> int:
    """Operate the transcript data-handling controls (consent + bounded retention).
    `status` needs no DB; `purge`/`purge-all`/`grant-consent`/`revoke-consent` require --db."""
    from . import datahandling as dh

    action = args.action
    if action == "status":
        store = dh.TranscriptStore(args.db) if args.db else None
        st = dh.policy_status(store)
        yn = lambda b: "yes" if b else "no"  # noqa: E731
        print(f"OSAI_LLM_TRANSCRIPTS gate: {yn(st['transcripts_enabled'])}")
        print(f"consent required:          {yn(st['consent_required'])}")
        print(f"retention (days):          {st['retention_days']}")
        print(f"redaction:                 {st['redaction']}")
        print(f"base URL approved:         {yn(st['base_url_approved'])}")
        print(f"retained transcripts:      {st['retained_count'] if st['retained_count'] is not None else '(no --db)'}")
        return 0
    if not args.db:
        print(f"'{action}' requires --db <sqlite path>")
        return 2
    store = dh.TranscriptStore(args.db)
    audit = None
    if os.environ.get("OSAI_AUDIT_DB"):
        from .audit import AuditLog
        audit = AuditLog(os.environ["OSAI_AUDIT_DB"])
    if action == "purge":
        n = store.purge_expired(audit=audit)
        print(f"purged {n} transcript(s) older than {dh.retention_days()} day(s)")
        return 0
    if action == "purge-all":  # incident rollback / kill switch
        n = store.purge_all(audit=audit)
        print(f"KILL-SWITCH: purged ALL {n} retained transcript(s)")
        return 0
    if not args.learner:
        print(f"'{action}' requires --learner <id>")
        return 2
    if action == "grant-consent":
        store.record_consent(args.learner)
        print(f"consent recorded for {args.learner!r}")
    else:  # revoke-consent
        n = store.revoke_consent(args.learner)
        print(f"consent revoked for {args.learner!r} (erased {n} retained transcript(s))")
    return 0


def cmd_signoff_preflight(args) -> int:
    """OSAI_LLM_TRANSCRIPTS sign-off preflight — prints GO/NO-GO and runs the self-redteam.
    Exits 0 only when every blocker passes AND the self-redteam is clean. Never sends data."""
    from . import selfredteam, signoff
    from .taxonomy import TaxonomyRegistry
    from .tutor import Tutor

    rep = signoff.run_preflight()
    srt = selfredteam.run(Tutor(registry=TaxonomyRegistry()))
    print("== OSAI_LLM_TRANSCRIPTS sign-off preflight ==")
    for c in rep["checks"]:
        print(f"  [{'OK' if c['ok'] else 'XX'}] {c['severity']:7} {c['kind']:7} {c['id']}")
        if not c["ok"]:
            print(f"         -> {c['detail']}")
    print("== self-redteam (payload + storage + tutor) ==")
    for p in srt["probes"]:
        print(f"  [{'OK' if p['ok'] else 'XX'}] {p['category']:20} {p['id']}")
        if not p["ok"]:
            print(f"         LEAK -> {p['detail']}")
    go = rep["go"] and srt["all_clean"]
    print()
    if rep["blockers_failed"]:
        print("config/control blockers failed:", ", ".join(rep["blockers_failed"]))
    if rep["warns_failed"]:
        print("warnings:", ", ".join(rep["warns_failed"]))
    if not srt["all_clean"]:
        print("SELF-REDTEAM LEAKS PRESENT — DO NOT ENABLE")
    print("VERDICT:", "GO — controls verified; the operator may enable OSAI_LLM_TRANSCRIPTS"
          if go else "NO-GO — resolve the failures above before enabling transcript judging")
    return 0 if go else 1


def cmd_goldset(args) -> int:
    from .goldset import GoldSetRunner, load_goldset

    gs = load_goldset(args.goldset) if args.goldset else None
    report = GoldSetRunner().run(gs)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"gold set: {report['total']} items {report['by_bank']}")
        for k, v in report["metrics"].items():
            print(f"  {'OK ' if report['gate'][k] else 'XXX'} {k}: {v}")
        for k, v in report["soft_metrics"].items():
            print(f"  ··· {k}: {v}  (tracked, not gated)")
        if report["failures"]:
            print("failures:", ", ".join(f"{f['id']}({f['bank']})" for f in report["failures"]))
        print("SHIP GATE:", "PASS" if report["passed"] else "FAIL")
    return 0 if report["passed"] else 1


def cmd_factstore(args) -> int:
    from . import factstore
    from .factstore import FactStore
    from .goldset import load_goldset
    from .taxonomy import TaxonomyRegistry

    fs = FactStore()
    cov = factstore.coverage_report(fs)
    if args.action == "coverage":
        print(json.dumps(cov, indent=2))
        return 0
    if args.action == "freeze":
        n = factstore.freeze()
        print(f"froze {n} source fingerprints")
        return 0
    # validate (default): cards against their sources + gold items against the cards
    store_rep = factstore.validate_store(fs, TaxonomyRegistry())
    gs = load_goldset(args.goldset) if args.goldset else load_goldset()
    item_rep = factstore.validate_items(fs, gs["items"])
    ok = store_rep["ok"] and item_rep["ok"]
    if args.json:
        print(json.dumps({"ok": ok, "store": store_rep, "items": item_rep, "coverage": cov}, indent=2))
    else:
        print("== fact store validate ==")
        print(f"  cards: {cov['cards_active']} active / {cov['cards_total']} total  ({cov['sensitive']} sensitive)")
        print(f"  per lab:            {cov['per_lab']}")
        print(f"  per claim_type:     {cov['per_claim_type']}")
        print(f"  per-bank capacity:  {cov['per_bank_capacity']}")
        print(f"  by status:          {cov['by_status']}")
        for b, c in cov["estimated_item_capacity"].items():
            if c["meets_floor_target"]:
                verdict = "clears target at 1 item/card floor"
            elif c["reachable_target"]:
                verdict = "reaches target only above the 1-item/card floor (<=2x phrasings)"
            else:
                verdict = "SHORT of target even at 2x"
            print(f"  capacity {b}: {c['cards_eligible']} cards -> {c['floor_items']}-{c['ceiling_items_2x']} "
                  f"items vs target {c['target']} ({verdict})")
        for e in store_rep["errors"]:
            print("  STORE ERR", e)
        for iid, errs in item_rep["errors"].items():
            print("  ITEM ERR ", iid, errs)
        print("FACTSTORE:", "OK" if ok else "FAIL")
    return 0 if ok else 1


def cmd_capstone(args) -> int:
    from .capstone import TriageCapstone

    cap = TriageCapstone()
    if args.brief:
        print(json.dumps(cap.public_brief(), indent=2))
        return 0
    if not args.submission:
        print("provide --submission <findings.json> or --brief")
        return 2
    submission = json.loads(Path(args.submission).read_text(encoding="utf-8"))
    result = cap.score(submission)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 2


def cmd_report(args) -> int:
    from .report import ReportReviewer

    finding = json.loads(Path(args.finding).read_text(encoding="utf-8"))
    transcript = json.loads(Path(args.transcript).read_text(encoding="utf-8")) if args.transcript else None
    card = ReportReviewer(TaxonomyRegistry()).review(finding, transcript)
    print(json.dumps(card.to_dict(), indent=2))
    return 0 if card.passed else 2


def cmd_serve(args) -> int:
    from .service import build_server

    server, state = build_server(host=args.host, port=args.port, seed=args.seed)
    host, port = server.server_address
    print(f"OSAI spine grader on http://{host}:{port}  (labs: {sorted(state.labs)})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover
        server.shutdown()
    return 0


def cmd_grade(args) -> int:
    path = Path(args.manifest) if args.manifest else (args.labs or LABS_DIR) / f"{args.lab}.json"
    manifest = manifest_mod.load(path)
    transcript = json.loads(Path(args.transcript).read_text(encoding="utf-8"))
    result = ChallengeValidator(manifest).grade(
        transcript, args.flag, args.seed, args.learner, args.attempt
    )
    if getattr(args, "db", None):
        from .progress import ProgressStore

        ProgressStore(args.db).record_attempt(args.learner, manifest, result)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.passed else 2


def cmd_progress(args) -> int:
    from .progress import ProgressStore

    store = ProgressStore(args.db)
    print(json.dumps(store.summary(args.learner, TaxonomyRegistry()), indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="osai_spine")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("catalog", help="print the canonical taxonomy registry")
    sp.set_defaults(fn=cmd_catalog)

    sp = sub.add_parser("validate-manifests", help="validate lab manifests (the binding rule)")
    sp.add_argument("--labs", type=Path)
    sp.set_defaults(fn=cmd_validate)

    sp = sub.add_parser("derive-flag", help="derive a per-learner evidence flag")
    sp.add_argument("--seed", required=True)
    sp.add_argument("--learner", required=True)
    sp.add_argument("--lab", required=True)
    sp.add_argument("--attempt", type=int, default=0)
    sp.set_defaults(fn=cmd_flag)

    sp = sub.add_parser("tutor", help="ask the retrieval-grounded tutor (offline, cited)")
    sp.add_argument("--query", required=True)
    sp.add_argument("--mode", default="tutor")
    sp.set_defaults(fn=cmd_tutor)

    sp = sub.add_parser("serve", help="run the HTTP grader service")
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--port", type=int, default=8077)
    sp.add_argument("--seed", default=None)
    sp.set_defaults(fn=cmd_serve)

    sp = sub.add_parser("grade", help="two-signal grade a learner submission")
    sp.add_argument("--lab", required=True)
    sp.add_argument("--transcript", required=True)
    sp.add_argument("--flag", required=True)
    sp.add_argument("--seed", required=True)
    sp.add_argument("--learner", required=True)
    sp.add_argument("--attempt", type=int, default=0)
    sp.add_argument("--labs", type=Path)
    sp.add_argument("--manifest", help="path to a manifest (overrides --lab/--labs)")
    sp.add_argument("--db", help="record the attempt to this SQLite progress DB")
    sp.set_defaults(fn=cmd_grade)

    sp = sub.add_parser("progress", help="show a learner's progress from a SQLite DB")
    sp.add_argument("--db", required=True)
    sp.add_argument("--learner", required=True)
    sp.set_defaults(fn=cmd_progress)

    sp = sub.add_parser("llm", help="safe LLM seam status (presence only — never the key value)")
    sp.add_argument("--ping", action="store_true",
                    help="send a tiny live request to verify the key answers (surfaces errors)")
    sp.set_defaults(fn=cmd_llm)

    sp = sub.add_parser("narrate", help="narration (TTS) seam for narrated lessons — status / plan / render")
    sp.add_argument("action", choices=["status", "plan", "render"])
    sp.add_argument("--script", help="path to a lesson narration script (JSON or plain text)")
    sp.add_argument("--out", help="output dir for the render manifest + audio (default: narration/)")
    sp.add_argument("--json", action="store_true", help="emit the full plan JSON")
    sp.set_defaults(fn=cmd_narrate)

    sp = sub.add_parser("transcripts", help="transcript data-handling controls (consent, retention, purge)")
    sp.add_argument("action", choices=["status", "purge", "purge-all", "grant-consent", "revoke-consent"])
    sp.add_argument("--db", help="SQLite path for the consent/retention store")
    sp.add_argument("--learner", help="learner id (for grant/revoke-consent)")
    sp.set_defaults(fn=cmd_transcripts)

    sp = sub.add_parser("signoff-preflight",
                        help="OSAI_LLM_TRANSCRIPTS go/no-go preflight + self-redteam (24-*)")
    sp.set_defaults(fn=cmd_signoff_preflight)

    sp = sub.add_parser("goldset", help="run the tutor gold-set ship gate (04-evaluation-harness.md)")
    sp.add_argument("--goldset", help="path to a gold-set JSON (defaults to gold/goldset.json)")
    sp.add_argument("--json", action="store_true", help="emit the full JSON report")
    sp.set_defaults(fn=cmd_goldset)

    sp = sub.add_parser("factstore", help="validate the structured fact store (25-fact-store-epic.md)")
    sp.add_argument("action", nargs="?", default="validate", choices=["validate", "coverage", "freeze"])
    sp.add_argument("--goldset", default=None, help="gold set path for item validation")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(fn=cmd_factstore)

    sp = sub.add_parser("capstone", help="L20 blue-team triage capstone (score a triage vs engine ground truth)")
    sp.add_argument("--brief", action="store_true", help="print the incident log + task (no answer key)")
    sp.add_argument("--submission", help="path to a triage submission JSON")
    sp.set_defaults(fn=cmd_capstone)

    sp = sub.add_parser("report", help="grade a learner finding vs the business-impact rubric")
    sp.add_argument("--finding", required=True, help="path to a finding JSON")
    sp.add_argument("--transcript", help="path to the attack transcript JSON (for classification check)")
    sp.set_defaults(fn=cmd_report)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
