"""Exportable study-artifact generation (08-reporting-and-canva.md §4) — offline-first.

Turns a learner's ``/analytics`` payload (``ProgressStore.analytics``) into portable,
zero-dependency study materials:

* ``flashcards_csv``    — an Anki / Quizlet-importable ``front,back,tags`` deck.
* ``studypack_markdown``— a readiness + weakness-drill + lab-plan sheet.
* ``marp_deck``         — a Marp slide deck (Markdown; ``marp: true`` front-matter).
* ``mermaid_lab_map``   — a Mermaid diagram of the lab→topic progress map.

These are the **MVP-safe fallback path** (Marp / Mermaid) in doc 08's export pipeline;
the Canva Connect API is a documented optional target layered on the *same* content, never
a runtime dependency. Everything is a pure function of the analytics dict, so it stays
stdlib-only and unit-testable with no server, model, or network.
"""

from __future__ import annotations

import csv
import io


def _pct(mastery: float) -> int:
    return round(max(0.0, min(1.0, mastery or 0.0)) * 100)


def _bar(mastery: float, width: int = 10) -> str:
    filled = int(round(max(0.0, min(1.0, mastery or 0.0)) * width))
    return "█" * filled + "░" * (width - filled)


def _short(tag: str) -> str:
    return (tag or "").replace(":2025", "")


def _labs_for_topic(analytics: dict, owasp_tag: str, only_open: bool = True) -> list:
    return [
        it["lab_id"]
        for it in analytics.get("labs", {}).get("items", [])
        if it.get("owasp") == owasp_tag and (not only_open or it.get("status") != "passed")
    ]


def flashcards_csv(analytics: dict) -> str:
    """An Anki/Quizlet-importable deck (``front,back,tags``) built from the learner's weak
    topics and unfinished labs. Answer-key-safe: references public framework tags and the
    *concept* of the evidence token, never a flag or the redacted detector."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["front", "back", "tags"])
    for wt in analytics.get("weak_topics", []):
        labs = _labs_for_topic(analytics, wt["tag"])
        drill = f" Drill: {', '.join(labs)}." if labs else ""
        w.writerow([
            f"{_short(wt['tag'])} — {wt['name']}: describe the attack and its primary defense.",
            f"{wt['name']} ({_short(wt['tag'])}). Current mastery {_pct(wt['mastery'])}%.{drill}",
            f"osai {wt.get('family', '')} {_short(wt['tag'])}".strip(),
        ])
    for it in analytics.get("labs", {}).get("items", []):
        if it.get("status") == "passed":
            continue
        w.writerow([
            f"Lab {it['lab_id']} ({it['title']}): which OWASP category, and what proves the exploit?",
            f"{it.get('owasp_name') or 'n/a'} ({_short(it.get('owasp') or '') or 'n/a'}), "
            f"module {it.get('module') or 'n/a'}. Pass = the reused detector fires AND you "
            f"capture the produced evidence token (flag / DB-state / callback).",
            f"osai lab {it['lab_id']}",
        ])
    return buf.getvalue()


def studypack_markdown(analytics: dict) -> str:
    """A one-page study sheet: readiness, missed-framework heatmap, weakest-first drill
    list with recommended labs, and the lab→topic progress map."""
    rd = analytics["readiness"]
    labs = analytics["labs"]
    out = [
        f"# OSAI Prep Studio — Study Pack: {analytics['learner_id']}",
        "",
        f"**Exam readiness: {rd['score']} / {rd['of']}**  ",
        f"avg OWASP mastery {_pct(rd['avg_owasp_mastery'])}% · "
        f"coverage {_pct(rd['owasp_coverage'])}% (≥0.5 mastery)  ",
        f"XP {analytics['xp']} · labs {labs['passed']}/{labs['total']} passed "
        f"({labs['completion_pct']}%) · flashcards due {analytics['flashcards']['due']}",
        "",
        "## Missed-framework heatmap (OWASP LLM 2025)",
        "",
    ]
    for h in analytics["heatmap"]:
        out.append(
            f"- `{_short(h['tag']):<6}` {_bar(h['mastery'])} {_pct(h['mastery']):3d}% — "
            f"{h['name']} ({h['labs_passed']}/{h['labs_total']} labs)"
        )
    out += ["", "## Drill these next (weakest first)", ""]
    if analytics["weak_topics"]:
        for wt in analytics["weak_topics"]:
            labs_open = _labs_for_topic(analytics, wt["tag"])
            rec = f" → run {', '.join(labs_open)}" if labs_open else ""
            out.append(f"- **{_short(wt['tag'])} {wt['name']}** ({_pct(wt['mastery'])}%){rec}")
    else:
        out.append("- No weak topics — every tracked topic is at ≥50% mastery. 🎯")
    out += ["", "## Lab → topic progress", ""]
    for oid, name, items in _group_labs_by_topic(analytics):
        passed = sum(1 for it in items if it["status"] == "passed")
        chips = ", ".join(f"{it['lab_id']} ({it['status'].replace('_', ' ')})" for it in items)
        out.append(f"- **{name}** — {passed}/{len(items)} passed: {chips}")
    out += ["", "_Generated offline by OSAI Prep Studio (08-reporting-and-canva.md §4)._"]
    return "\n".join(out) + "\n"


def marp_deck(analytics: dict) -> str:
    """A Marp slide deck (Markdown). Render with `marp deck.md` — the doc-08 fallback path
    that never blocks on Canva OAuth."""
    rd = analytics["readiness"]
    labs = analytics["labs"]
    s = [
        "---", "marp: true", "theme: default", "paginate: true", "---", "",
        "# OSAI Prep Studio", f"## Study deck — {analytics['learner_id']}", "",
        "---", "", "## Exam readiness", "", f"# {rd['score']} / {rd['of']}", "",
        f"- avg OWASP mastery **{_pct(rd['avg_owasp_mastery'])}%**",
        f"- coverage **{_pct(rd['owasp_coverage'])}%** (≥0.5 mastery)",
        f"- labs **{labs['passed']}/{labs['total']}** ({labs['completion_pct']}%) · "
        f"XP **{analytics['xp']}**",
        "", "---", "", "## Drill next (weakest first)", "",
    ]
    if analytics["weak_topics"]:
        for wt in analytics["weak_topics"][:6]:
            s.append(f"- **{_short(wt['tag'])} {wt['name']}** — {_pct(wt['mastery'])}%")
    else:
        s.append("- All tracked topics ≥ 50% mastery 🎯")
    s += ["", "---", "", "## OWASP heatmap", "", "```"]
    for h in analytics["heatmap"]:
        s.append(f"{_short(h['tag']):<6} {_bar(h['mastery'])} {_pct(h['mastery']):3d}%")
    s += ["```", ""]
    return "\n".join(s) + "\n"


def mermaid_lab_map(analytics: dict) -> str:
    """A Mermaid ``flowchart`` of the lab→topic map, labs colored by pass status —
    the doc-08 diagram builder for the learner's study pack / report appendix."""
    lines = [
        "flowchart LR",
        "  classDef passed fill:#123d1a,stroke:#3fb950,color:#e6edf3;",
        "  classDef attempted fill:#0d2b52,stroke:#2f81f7,color:#e6edf3;",
        "  classDef todo fill:#161b22,stroke:#30363d,color:#8b949e;",
    ]
    css = {"passed": "passed", "attempted": "attempted", "not_started": "todo"}
    for oid, name, items in _group_labs_by_topic(analytics):
        gid = (_short(oid) or "other").replace(".", "_").replace("-", "_")
        lines.append(f'  subgraph {gid}["{name}"]')
        for it in items:
            lines.append(f'    {it["lab_id"]}["{it["lab_id"]}"]:::{css[it["status"]]}')
        lines.append("  end")
    return "\n".join(lines) + "\n"


def _group_labs_by_topic(analytics: dict) -> list:
    """[(owasp_tag, display_name, [items])] preserving first-seen order."""
    order: list = []
    groups: dict = {}
    for it in analytics.get("labs", {}).get("items", []):
        key = it.get("owasp") or "other"
        if key not in groups:
            groups[key] = (it.get("owasp_name") or "Other", [])
            order.append(key)
        groups[key][1].append(it)
    return [(key, groups[key][0], groups[key][1]) for key in order]
