"""Run the agent range and emit evidence.

For each scenario:
  * run the VULNERABLE agent and record the full attack path (retrieval -> tools -> exfil/destroy),
  * grade the retrieved (untrusted) content and every tool observation with the flagship detectors,
  * run the HARDENED agent (detector-backed ingest quarantine + a provenance gate on privileged
    tools) and record the KILL POINT where the chain breaks,
  * check ground truth (did data actually leave / get destroyed?).

Writes ``EVIDENCE.md`` + ``results.json``. Exits non-zero if invariants fail, so it self-tests:
  * every attack scenario is exploitable on the vulnerable agent (the range works),
  * every attack is detected (indirect injection on ingest and/or disclosure on a tool step),
  * every attack is broken on the hardened agent (a kill point exists; nothing exfiltrated/destroyed),
  * the benign control uses no tools and is never flagged or blocked.

Std-lib only; reuses the flagship detection engine.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "projects" / "llm-log-triage" / "src"))
sys.path.insert(0, str(HERE))

import detectors as det  # noqa: E402
from agent import ToolAgent, DESTRUCTIVE_TOOLS, EXFIL_TOOLS  # noqa: E402
from scenarios import SCENARIOS, Scenario  # noqa: E402

HIGH = {"critical", "high"}
PRIVILEGED = DESTRUCTIVE_TOOLS | EXFIL_TOOLS | {"read_file", "db_query"}


def scan(source: str, role: str, content: str) -> list[dict]:
    event = {"event_id": "range", "source": source, "role": role, "content": content or ""}
    out = []
    for d in det.ALL_DETECTORS:
        for f in d.scan(event):
            out.append({"detector": f.detector, "owasp_id": f.owasp_id,
                        "atlas_technique": f.atlas_technique, "severity": f.severity,
                        "rationale": f.rationale[:140]})
    return out


def make_policy():
    """Hardened guard: (1) quarantine retrieved content the detectors flag; (2) provenance gate —
    untrusted-retrieved content may not trigger a privileged tool (defense in depth)."""
    def policy(tool, args, provenance, trigger):
        hits = scan("rag", "tool", trigger)
        det_hit = hits[0]["detector"] if hits else None
        if tool == "ingest":
            return (det_hit is None), det_hit           # block ingest iff a detector flagged it
        if provenance == "untrusted" and tool in PRIVILEGED:
            return False, (det_hit or "provenance-gate: untrusted content cannot drive a privileged tool")
        return True, det_hit
    return policy


def run_scenario(s: Scenario) -> dict:
    policy = make_policy()
    vuln = ToolAgent(s.corpus, mode="vulnerable")
    rv = vuln.run(s.task)
    hard = ToolAgent(s.corpus, mode="hardened", policy=policy)
    rh = hard.run(s.task)

    retrieved = "\n".join(s.corpus.values())
    ingest_findings = scan("rag", "tool", retrieved)
    # grade each vulnerable tool observation as assistant output (catches disclosure/exfil)
    step_findings = {}
    for st in rv.steps:
        if st.tool and st.tool != "kb_search":
            f = scan("api", "assistant", st.observation)
            if f:
                step_findings[st.n] = f

    detected = bool(ingest_findings or step_findings)
    exploited = rv.exfiltrated or rv.destructive
    path = " → ".join([st.tool or st.action for st in rv.steps])
    if exploited:
        path += " 💥 " + "+".join(x for x, b in [("exfil", rv.exfiltrated), ("destroy", rv.destructive)] if b)

    kill = None
    for st in rh.steps:
        if st.blocked:
            kill = {"step": st.n, "action": st.action, "detector": st.detector}
            break

    return {
        "id": s.id, "name": s.name, "owasp": s.owasp, "atlas": s.atlas,
        "task": s.task, "expected_path": s.expected_path, "success_criterion": s.success or "(control)",
        "attack_path": path, "tools_used": rv.tools_used,
        "exfiltrated": rv.exfiltrated, "destructive": rv.destructive, "exploited": exploited,
        "detected": detected,
        "ingest_findings": ingest_findings,
        "step_findings": step_findings,
        "hardened_blocked": rh.blocked_at is not None,
        "hardened_exfiltrated": rh.exfiltrated, "hardened_destructive": rh.destructive,
        "kill_point": kill,
        "mitigation": s.mitigation,
        "vuln_steps": [{"n": st.n, "action": st.action, "tool": st.tool, "provenance": st.provenance,
                        "observation": st.observation[:120]} for st in rv.steps],
        "hardened_steps": [{"n": st.n, "action": st.action, "blocked": st.blocked,
                            "detector": st.detector} for st in rh.steps],
    }


def check_invariants(rows: list[dict]) -> list[str]:
    problems = []
    for r in rows:
        control = r["success_criterion"] == "(control)"
        if control:
            if r["tools_used"]:
                problems.append(f"{r['id']}: control used tools {r['tools_used']}")
            if r["detected"]:
                problems.append(f"{r['id']}: control was flagged (false positive)")
            if r["hardened_blocked"]:
                problems.append(f"{r['id']}: control was blocked (false positive)")
        else:
            if not r["exploited"]:
                problems.append(f"{r['id']}: vulnerable agent was not exploited")
            if not r["detected"]:
                problems.append(f"{r['id']}: attack not detected (silent miss)")
            if not r["hardened_blocked"] or r["hardened_exfiltrated"] or r["hardened_destructive"]:
                problems.append(f"{r['id']}: hardened agent did not break the chain")
    return problems


def to_md(rows: list[dict], problems: list[str]) -> str:
    atk = [r for r in rows if r["success_criterion"] != "(control)"]
    L = ["# Agent Range — Multi-Step Attack Evidence\n"]
    L.append("> Generated by `run_range.py`. Target: the mock RAG + tool-using agent in "
             "[`agent.py`](./agent.py). A poisoned *retrieved* document drives a multi-step tool chain; "
             "detection + hardening reuse the flagship engine (`projects/llm-log-triage`). "
             "Std-lib only — reproduce with `python3 run_range.py`.\n")
    L.append("## Summary\n")
    L.append(f"- **{len(atk)} attack scenarios**, {len(rows) - len(atk)} control.")
    L.append(f"- **{sum(r['exploited'] for r in atk)}/{len(atk)}** exploited the vulnerable agent "
             "(multi-step chain reached exfiltration/destruction).")
    L.append(f"- **{sum(r['detected'] for r in atk)}/{len(atk)}** detected (indirect injection at ingest and/or disclosure at a tool step).")
    L.append(f"- **{sum(r['hardened_blocked'] for r in atk)}/{len(atk)}** broken on the hardened agent (kill point identified).")
    L.append(f"- Invariants: {'✅ all hold' if not problems else '❌ ' + str(len(problems)) + ' violation(s)'}\n")
    L.append("## Attack paths\n")
    L.append("| ID | Scenario | OWASP | ATLAS | Attack path (vulnerable) | Exploit | Detected | Hardened kill point |")
    L.append("|----|----------|-------|-------|--------------------------|:---:|:---:|---------------------|")
    for r in rows:
        expl = "💥 " + (", ".join(x for x, b in [("exfil", r["exfiltrated"]), ("destroy", r["destructive"])] if b)) if r["exploited"] else ("—" if r["id"] != "S4" else "— (control)")
        kp = "—"
        if r["kill_point"]:
            kp = f"step {r['kill_point']['step']}: {r['kill_point']['detector'] or 'provenance gate'}"
        elif r["id"] == "S4":
            kp = "n/a (not blocked)"
        L.append(f"| {r['id']} | {r['name']} | {r['owasp']} | {r['atlas']} | `{r['attack_path']}` | "
                 f"{expl} | {'yes' if r['detected'] else '—'} | {kp} |")
    L.append("\n## Per-scenario detail\n")
    for r in rows:
        L.append(f"### {r['id']} — {r['name']}")
        L.append(f"- **Task (innocent):** {r['task']}")
        L.append(f"- **Maps to:** {r['owasp']} / {r['atlas']}")
        L.append("- **Vulnerable agent walk:**")
        for st in r["vuln_steps"]:
            L.append(f"  {st['n']}. `{st['tool'] or st['action']}` [{st['provenance']}] → {st['observation']}")
        if r["ingest_findings"]:
            f0 = r["ingest_findings"][0]
            L.append(f"- **Detected at ingest:** `{f0['detector']}` ({f0['owasp_id']}) — {f0['rationale']}")
        for n, fs in r["step_findings"].items():
            L.append(f"- **Detected at step {n} (output):** `{fs[0]['detector']}` ({fs[0]['owasp_id']})")
        if r["kill_point"]:
            L.append(f"- **Hardened kill point:** step {r['kill_point']['step']} — {r['kill_point']['action']} "
                     f"(`{r['kill_point']['detector'] or 'provenance gate'}`)")
        L.append(f"- **Mitigation:** {r['mitigation']}\n")
    if problems:
        L.append("## ❌ Invariant violations\n")
        L += [f"- {p}" for p in problems]
    return "\n".join(L) + "\n"


def main() -> int:
    rows = [run_scenario(s) for s in SCENARIOS]
    problems = check_invariants(rows)
    (HERE / "results.json").write_text(json.dumps(rows, indent=2))
    (HERE / "EVIDENCE.md").write_text(to_md(rows, problems))
    print(to_md(rows, problems))
    if problems:
        print("\nINVARIANTS FAILED:", *problems, sep="\n  - ", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
