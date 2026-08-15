"""Run the AI application security assessment and emit evidence.

Loop, per attack case:

    attack -> vulnerable target -> response
      |-> grade INPUT  with the flagship detectors (was the attack visible on the way in?)
      |-> grade OUTPUT with the flagship detectors (did the response leak / exfiltrate?)
      |-> record GROUND TRUTH (did the app actually get exploited?)
    attack -> hardened target (same detectors as an input+output guard) -> retest

Writes ``EVIDENCE.md`` (human-readable, committed) and ``results.json`` (machine-readable).
Exits non-zero if the range's invariants don't hold, so it doubles as a self-test:
  * every offensive case is actually exploitable on the vulnerable target,
  * every offensive case is blocked on the hardened target (the mitigation works),
  * detection catches every exploit (no silent miss),
  * the benign control is neither flagged nor blocked (no false positive).

Std-lib only; reuses the flagship detection engine — no network, no API keys.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]  # red-team/assessment -> repo root
sys.path.insert(0, str(REPO / "projects" / "llm-log-triage" / "src"))
sys.path.insert(0, str(HERE.parent / "vulnerable-app"))

import detectors as det  # noqa: E402  (flagship engine — reused verbatim)
from vulnerable_app import VulnerableAssistant  # noqa: E402
from attack_corpus import CORPUS, Attack  # noqa: E402

HIGH = {"critical", "high"}


def scan_event(source: str, role: str, content: str) -> list[dict]:
    """Run every flagship detector over one synthetic event; return finding rows."""
    event = {"event_id": "assess", "source": source, "role": role, "content": content}
    rows = []
    for d in det.ALL_DETECTORS:
        for f in d.scan(event):
            rows.append({
                "detector": f.detector, "owasp_id": f.owasp_id,
                "atlas_technique": f.atlas_technique, "severity": f.severity,
                "matched_snippet": f.matched_snippet[:120], "rationale": f.rationale[:160],
            })
    return rows


def grade_input(a: Attack) -> list[dict]:
    findings = scan_event("chat_ui", "user", a.user_message)
    if a.untrusted:
        findings += scan_event(a.source, "tool", a.untrusted)
    return findings


def make_defense():
    """A detector-backed guard the hardened target consults on input and output."""
    def defense(phase: str, **kw):
        if phase == "input":
            findings = []
            findings += scan_event("chat_ui", "user", kw.get("user_message") or "")
            if kw.get("untrusted"):
                findings += scan_event("tool", "tool", kw["untrusted"])
            hot = [f for f in findings if f["severity"] in HIGH]
            if hot:
                return True, f"{hot[0]['detector']} ({hot[0]['owasp_id']}, {hot[0]['severity']})"
            return False, ""
        # output phase: block on any disclosure (LLM02) or output-handling/exfil (LLM05) finding
        findings = scan_event("api", "assistant", kw.get("response") or "")
        hot = [f for f in findings if f["owasp_id"].startswith(("LLM02", "LLM05"))]
        if hot:
            return True, f"{hot[0]['detector']} ({hot[0]['owasp_id']})"
        return False, ""
    return defense


def worst(findings: list[dict]) -> str:
    return det.max_severity(f["severity"] for f in findings) if findings else "info"


def run() -> dict:
    defense = make_defense()
    rows = []
    for a in CORPUS:
        vuln = VulnerableAssistant("vulnerable")
        tv = vuln.respond(a.user_message, a.untrusted)
        hard = VulnerableAssistant("hardened", defense=defense)
        th = hard.respond(a.user_message, a.untrusted)

        in_find = grade_input(a)
        out_find = scan_event("api", "assistant", tv.response)

        exploited_vuln = bool(getattr(tv, a.success)) if a.success else False
        exploited_hard = bool(getattr(th, a.success)) if a.success else False
        detected = bool(in_find or out_find)

        rows.append({
            "id": a.id, "name": a.name, "attack_class": a.attack_class,
            "channel": a.source, "owasp": a.owasp, "atlas": a.atlas,
            "success_criterion": a.success or "(detection-only / control)",
            "exploited_vulnerable": exploited_vuln,
            "detected_on_input": bool(in_find),
            "detected_on_output": bool(out_find),
            "worst_severity": worst(in_find + out_find),
            "blocked_hardened": th.refused,
            "exploited_hardened": exploited_hard,
            "vuln_response": tv.response[:200],
            "hardened_response": th.response[:200],
            "input_findings": in_find,
            "output_findings": out_find,
            "mitigation": a.mitigation,
        })
    return {"attacks": rows}


def check_invariants(res: dict) -> list[str]:
    problems = []
    for r in res["attacks"]:
        offensive = r["success_criterion"] not in ("(detection-only / control)",)
        control = r["id"] == "A11"
        if offensive:
            if not r["exploited_vulnerable"]:
                problems.append(f"{r['id']}: expected exploit on vulnerable target, none observed")
            if not r["detected_on_input"] and not r["detected_on_output"]:
                problems.append(f"{r['id']}: exploit not detected on input OR output (silent miss)")
            if r["exploited_hardened"] or not r["blocked_hardened"]:
                problems.append(f"{r['id']}: hardened target did not block the exploit")
        if control:
            if r["detected_on_input"] or r["detected_on_output"]:
                problems.append(f"{r['id']}: benign control was flagged (false positive)")
            if r["blocked_hardened"]:
                problems.append(f"{r['id']}: benign control was blocked (false positive)")
    return problems


def to_markdown(res: dict, problems: list[str]) -> str:
    rows = res["attacks"]
    offensive = [r for r in rows if r["success_criterion"] not in ("(detection-only / control)",)]
    n_expl = sum(r["exploited_vulnerable"] for r in offensive)
    n_det = sum((r["detected_on_input"] or r["detected_on_output"]) for r in offensive)
    n_block = sum(r["blocked_hardened"] for r in offensive)
    L = []
    L.append("# AI Application Security Assessment — Evidence\n")
    L.append("> Generated by `run_assessment.py`. Target: the intentionally-vulnerable mock agent in "
             "[`../vulnerable-app/`](../vulnerable-app/vulnerable_app.py). Grading reuses the flagship "
             "detection engine (`projects/llm-log-triage/src/detectors.py`) — the same OWASP/ATLAS "
             "taxonomy on both offense and defense. Std-lib only; reproduce with `python3 run_assessment.py`.\n")
    L.append("## Summary\n")
    L.append(f"- **{len(offensive)} offensive cases**, **{len(rows) - len(offensive)} control/detection-only** case(s).")
    L.append(f"- **{n_expl}/{len(offensive)}** exploited the vulnerable target (the range actually works).")
    L.append(f"- **{n_det}/{len(offensive)}** were caught by detection on input and/or output (no silent misses).")
    L.append(f"- **{n_block}/{len(offensive)}** were blocked on the hardened target (mitigation verified by retest).")
    L.append(f"- Invariants: {'✅ all hold' if not problems else '❌ ' + str(len(problems)) + ' violation(s)'}\n")
    L.append("## Findings\n")
    L.append("| ID | Attack | Channel | OWASP | ATLAS | Sev | Exploit (vuln) | Detected in/out | Retest (hardened) |")
    L.append("|----|--------|---------|-------|-------|-----|:---:|:---:|:---:|")
    for r in rows:
        det_io = ("in" if r["detected_on_input"] else "—") + "/" + ("out" if r["detected_on_output"] else "—")
        expl = "💥 yes" if r["exploited_vulnerable"] else ("— (control)" if r["id"] == "A11" else "— (detect-only)")
        retest = "🛡️ blocked" if r["blocked_hardened"] else ("✅ n/a" if r["id"] == "A11" else "⚠️ NOT blocked")
        L.append(f"| {r['id']} | {r['name']} | `{r['channel']}` | {r['owasp']} | {r['atlas']} | "
                 f"{r['worst_severity']} | {expl} | {det_io} | {retest} |")
    L.append("\n## Per-case detail\n")
    for r in rows:
        L.append(f"### {r['id']} — {r['name']}")
        L.append(f"- **Class:** {r['attack_class']} · **Channel:** `{r['channel']}` · "
                 f"**Maps to:** {r['owasp']} / {r['atlas']}")
        L.append(f"- **Vulnerable target response:** `{r['vuln_response']}`")
        if r["input_findings"]:
            f0 = r["input_findings"][0]
            L.append(f"- **Detected on input:** `{f0['detector']}` — {f0['rationale']}")
        if r["output_findings"]:
            f0 = r["output_findings"][0]
            L.append(f"- **Detected on output:** `{f0['detector']}` — {f0['rationale']}")
        L.append(f"- **Hardened retest:** {r['hardened_response']}")
        L.append(f"- **Mitigation:** {r['mitigation']}\n")
    if problems:
        L.append("## ❌ Invariant violations\n")
        for p in problems:
            L.append(f"- {p}")
    return "\n".join(L) + "\n"


def main() -> int:
    res = run()
    problems = check_invariants(res)
    (HERE / "results.json").write_text(json.dumps(res, indent=2))
    (HERE / "EVIDENCE.md").write_text(to_markdown(res, problems))
    print(to_markdown(res, problems))
    if problems:
        print("\nINVARIANTS FAILED:", *problems, sep="\n  - ", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
