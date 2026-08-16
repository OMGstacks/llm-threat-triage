"""Run the web/API security assessment against the intentionally-vulnerable AcmeChat app.

This is the *conventional* application-security half of the range — SSRF, IDOR/BOLA, broken auth,
reflected XSS, SQLi — the classic web/API flaws that live underneath an AI application. Each case:

    exploit the vulnerable app (ground-truth flag) -> map to OWASP API/Web Top 10 + CWE
      -> retest the hardened app (must block/prevent) -> record the fix

Writes EVIDENCE.md + results.json. Exits non-zero if any invariant fails, so it doubles as a
regression self-test (same contract as the LLM-side ranges). Std-lib only, deterministic.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from webapp import AcmeWebApp  # noqa: E402


@dataclass
class Case:
    id: str
    name: str
    owasp: str          # OWASP API/Web Top 10 (NOT the LLM Top 10 — this is the conventional layer)
    cwe: str
    request: str        # human-readable request line
    call: Callable      # (app) -> Resp
    success: str        # ground-truth Resp flag that means "exploited"; "" for the benign control
    mitigation: str


CASES = [
    Case("W1", "SSRF — agent URL-fetch tool reaches cloud metadata",
         "API7:2023 SSRF / A10:2021", "CWE-918",
         "POST /tools/fetch  url=http://169.254.169.254/latest/meta-data/iam/security-credentials/",
         lambda a: a.fetch_url("http://169.254.169.254/latest/meta-data/iam/security-credentials/"),
         "ssrf_reached_internal",
         "Egress allowlist + block internal/link-local ranges; never fetch attacker-supplied hosts by raw IP."),
    Case("W2", "IDOR / BOLA — read another user's conversation",
         "API1:2023 BOLA / A01:2021", "CWE-639",
         "GET /conversations/conv-1002   (as user-alice; conv owned by user-bob)",
         lambda a: a.get_conversation("conv-1002", as_user="user-alice"),
         "idor_leaked_other_user",
         "Enforce object-level ownership on every access; authorize the subject against the object, not just the route."),
    Case("W3", "Broken authentication — admin config with no valid token",
         "API2:2023 Broken Auth / A07:2021", "CWE-306",
         "GET /admin/config   (Authorization: empty)",
         lambda a: a.admin_config(token=""),
         "auth_bypassed",
         "Deny by default; constant-time token comparison; no unauthenticated path to secrets."),
    Case("W4", "Reflected XSS — search echoes active content unescaped",
         "A03:2021 Injection (XSS)", "CWE-79",
         "GET /search?q=<script>alert(document.cookie)</script>",
         lambda a: a.search("<script>alert(document.cookie)</script>"),
         "xss_reflected_unescaped",
         "Context-aware output encoding (HTML-escape reflected input); CSP as defense-in-depth."),
    Case("W5", "SQL injection — tautology dumps all users' history",
         "A03:2021 Injection (SQLi) / API8:2023", "CWE-89",
         "GET /history?term=' OR '1'='1   (as user-alice)",
         lambda a: a.history("user-alice", "' OR '1'='1"),
         "sqli_dumped_extra_rows",
         "Parameterized queries / prepared statements; keep the user-scope filter server-side."),
    Case("W6", "Benign control — normal search + own conversation",
         "—", "—",
         "GET /search?q=refund+policy  ·  GET /conversations/conv-1001 (as owner)",
         lambda a: a.search("refund policy"),
         "",  # control: must not be flagged or blocked
         "No action — must NOT be blocked or flagged (false-positive control)."),
]


def run() -> list[dict]:
    rows = []
    for c in CASES:
        rv = c.call(AcmeWebApp("vulnerable"))
        rh = c.call(AcmeWebApp("hardened"))
        exploited = bool(getattr(rv, c.success)) if c.success else False
        exploited_h = bool(getattr(rh, c.success)) if c.success else False
        rows.append({
            "id": c.id, "name": c.name, "owasp": c.owasp, "cwe": c.cwe, "request": c.request,
            "success_criterion": c.success or "(control)",
            "exploited_vulnerable": exploited,
            "vuln_status": rv.status, "vuln_body": rv.body[:160], "vuln_notes": rv.notes,
            "hardened_blocked": rh.blocked or (bool(c.success) and not exploited_h),
            "hardened_status": rh.status, "hardened_body": rh.body[:160], "hardened_notes": rh.notes,
            "mitigation": c.mitigation,
        })
    return rows


def check_invariants(rows: list[dict]) -> list[str]:
    problems = []
    for r in rows:
        if r["success_criterion"] == "(control)":
            if r["hardened_blocked"] or r["vuln_notes"]:
                problems.append(f"{r['id']}: benign control was flagged/blocked (false positive)")
        else:
            if not r["exploited_vulnerable"]:
                problems.append(f"{r['id']}: expected exploit on vulnerable app, none observed")
            if not r["hardened_blocked"]:
                problems.append(f"{r['id']}: hardened app did not block/prevent the exploit")
    return problems


def to_md(rows: list[dict], problems: list[str]) -> str:
    atk = [r for r in rows if r["success_criterion"] != "(control)"]
    L = ["# Web / API Security Assessment — Evidence\n"]
    L.append("> Generated by `run_web_assessment.py`. Target: the intentionally web-vulnerable AcmeChat "
             "app in [`webapp.py`](./webapp.py) — the *conventional* web/API layer under an AI application "
             "(SSRF, IDOR/BOLA, broken auth, XSS, SQLi), mapped to the **OWASP API/Web Top 10 + CWE** "
             "(not the LLM Top 10). Std-lib only; reproduce with `python3 run_web_assessment.py`.\n")
    L.append("## Summary\n")
    L.append(f"- **{len(atk)} web/API attack cases**, {len(rows) - len(atk)} control.")
    L.append(f"- **{sum(r['exploited_vulnerable'] for r in atk)}/{len(atk)}** exploited the vulnerable app.")
    L.append(f"- **{sum(r['hardened_blocked'] for r in atk)}/{len(atk)}** blocked after hardening (fix verified by retest).")
    L.append(f"- Invariants: {'✅ all hold' if not problems else '❌ ' + str(len(problems)) + ' violation(s)'}\n")
    L.append("## Findings\n")
    L.append("| ID | Vulnerability | OWASP | CWE | Exploit (vuln) | Retest (hardened) |")
    L.append("|----|---------------|-------|-----|:---:|:---:|")
    for r in rows:
        expl = "💥 yes" if r["exploited_vulnerable"] else ("— (control)" if r["id"] == "W6" else "—")
        retest = "🛡️ blocked" if r["hardened_blocked"] else ("✅ n/a" if r["id"] == "W6" else "⚠️ NOT blocked")
        L.append(f"| {r['id']} | {r['name']} | {r['owasp']} | {r['cwe']} | {expl} | {retest} |")
    L.append("\n## Per-case detail\n")
    for r in rows:
        L.append(f"### {r['id']} — {r['name']}")
        L.append(f"- **Maps to:** {r['owasp']} · {r['cwe']}")
        L.append(f"- **Request:** `{r['request']}`")
        L.append(f"- **Vulnerable app:** [{r['vuln_status']}] {r['vuln_body']}"
                 + (f"  _( {r['vuln_notes'][0]} )_" if r["vuln_notes"] else ""))
        L.append(f"- **Hardened retest:** [{r['hardened_status']}] {r['hardened_body']}"
                 + (f"  _( {r['hardened_notes'][0]} )_" if r["hardened_notes"] else ""))
        L.append(f"- **Mitigation:** {r['mitigation']}\n")
    if problems:
        L.append("## ❌ Invariant violations\n")
        L += [f"- {p}" for p in problems]
    return "\n".join(L) + "\n"


def main() -> int:
    rows = run()
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
