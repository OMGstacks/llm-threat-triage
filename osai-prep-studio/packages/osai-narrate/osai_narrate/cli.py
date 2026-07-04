"""`narrate` CLI — status / plan / render for narrated lessons. Offline; render is gated."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import core


def _load(path: str):
    src = Path(path).read_text(encoding="utf-8")
    try:
        return json.loads(src)          # structured script …
    except json.JSONDecodeError:
        return src                      # … or plain-text paragraphs


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="narrate", description="narrated-lesson renderer")
    sub = p.add_subparsers(dest="action", required=True)
    sub.add_parser("status", help="presence-only seam state (never the key value)")
    pl = sub.add_parser("plan", help="parse a script and print the offline render plan")
    pl.add_argument("--script", required=True)
    pl.add_argument("--json", action="store_true", help="emit the full plan JSON")
    rn = sub.add_parser("render", help="write the manifest + captions; render audio if enabled")
    rn.add_argument("--script", required=True)
    rn.add_argument("--out", default="narration", help="output dir (default: narration/)")
    args = p.parse_args(argv)

    if args.action == "status":
        st = core.status()
        yn = lambda b: "yes" if b else "no"  # noqa: E731
        print(f"provider:            {st['provider']} ({st['kind']})")
        print(f"key ({st['key_env'] or 'none'}):  present={yn(st['key_present'])} source={st['key_source']}")
        print(f"provider available:  {yn(st['available'])}")
        print(f"render enabled:      {yn(st['render_enabled'])}")
        print(f"cost (US$/1M chars): {st['rate_per_million_usd']}  [planning estimate]")
        print(f"providers:           {', '.join(st['providers'])}")
        return 0

    script = _load(args.script)

    if args.action == "plan":
        plan = core.render_plan(script)
        if args.json:
            print(json.dumps(plan, indent=2))
        else:
            print(f"lesson {plan['lesson_id']!r}: {plan['segment_count']} segments · "
                  f"{plan['total_chars']} chars · ~{plan['est_duration']} · "
                  f"provider={plan['provider']} · est ${plan['est_cost_usd']} one-time")
            for s in plan["segments"]:
                print(f"  {s['id']}  {s['chars']:>5}ch  ~{s['est_seconds']}s  -> {s['audio']}")
        return 0

    # render
    res = core.write_manifest(script, args.out)
    print(f"manifest: {res['manifest']}")
    print(f"captions: {res['captions']}  ({res['plan']['segment_count']} segments)")
    if not core.render_enabled():
        print(f"audio: not rendered — seam off (set NARRATE=1 + configure provider "
              f"'{core.provider_name()}'). Manifest + captions are ready; drop audio in later.")
        return 0
    rendered = 0
    for planseg, seg in zip(res["plan"]["segments"], core.parse_script(script)["segments"]):
        r = core.render_segment(seg["text"], Path(args.out) / planseg["audio"], voice=res["plan"]["voice"])
        if r.get("rendered"):
            rendered += 1
        else:
            print(f"  {planseg['id']}: {r['reason']}")
    print(f"audio: rendered {rendered}/{res['plan']['segment_count']} segments to {args.out}/")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
