"""cc_spine.cram_sheet_view — the visual cram sheet (PR-11c).

The visual layer over ``cram_sheet.build_cram_sheet``. ``render_html`` is a PURE, deterministic
formatter: it renders exactly the fields the data model already decided are safe teaching content
(item stem, the registry's trap/correction/rule text, ids) — never a choice list, an isolated-key
field, or the learner's own selected index, because it never receives one.

Unlike the readiness dashboard (a live status panel, scanned not read), a cram sheet is a study
document — read top to bottom, printable. The layout reflects that: weakest domain first, one
"trap card" per open misconception (the trap you believed, the fix, the one-line rule), a positive
recap of what's already been fixed.

Shares the dashboard's color/type tokens (same product, same visual language) but is otherwise a
self-contained template — no import from ``dashboard_view``, so this module review carries no risk
to the already-shipped dashboard render.

Two output modes, one template: ``standalone=True`` (CLI ``cram-sheet --html``) is a complete
document; ``standalone=False`` is a head-less fragment for host embedding (e.g. an Artifact).

Stdlib only (``html.escape``).
"""

from __future__ import annotations

from html import escape as _e


def _pct(x, decimals: int = 0) -> str:
    return "—" if x is None else f"{x * 100:.{decimals}f}%"


def _masthead(c: dict) -> str:
    return f"""
<header class="masthead">
  <div>
    <p class="eyebrow">CC Master Learning Center &middot; Weak-Area Review</p>
    <h1 class="wordmark">Cram Sheet</h1>
  </div>
  <div class="stat-row">
    <div class="stat"><span class="stat-value">{c['open_count']}</span><span class="stat-label">open</span></div>
    <div class="stat"><span class="stat-value">{c['closed_count']}</span><span class="stat-label">closed lifetime</span></div>
    <div class="stat"><span class="stat-value">{c['priority_count']}</span><span class="stat-label">confidently wrong</span></div>
  </div>
</header>"""


def _trap_card(e: dict) -> str:
    priority = '<span class="chip chip-warn">confidently wrong</span>' if e["priority"] else ""
    stem = (f'<blockquote class="stem-quote">{_e(e["stem"])}</blockquote>' if e.get("stem") else "")
    return f"""
<article class="trap-card">
  {stem}
  <div class="trap-row"><span class="trap-label">The trap</span><p>{_e(e['trap'])}</p></div>
  <div class="trap-row"><span class="trap-label">The fix</span><p>{_e(e['correction'])}</p></div>
  <div class="trap-row trap-rule"><span class="trap-label">One-line rule</span><p>{_e(e['one_sentence_rule'])}</p></div>
  <div class="trap-foot">
    <span class="tag">{_e(e['misconception_id'])}</span>
    <span class="tag">{_e(e['objective'])}</span>
    {priority}
  </div>
</article>"""


def _domain_section(d: dict) -> str:
    cards = "".join(_trap_card(e) for e in d["entries"])
    return f"""
<section class="domain-block">
  <h2 class="domain-title">{_e(d['domain'])}
    <span class="domain-acc">{_pct(d['accuracy'])} accuracy &middot; {d['attempts']} attempt{'s' if d['attempts'] != 1 else ''}</span>
  </h2>
  {cards}
</section>"""


def _recap(c: dict) -> str:
    if not c["closed_recap"]:
        return ""
    rows = "".join(f'<li><span class="dot dot-good"></span>{_e(r["one_sentence_rule"])} '
                   f'<span class="tag">{_e(r["misconception_id"])}</span></li>'
                   for r in c["closed_recap"])
    return f"""
<section class="card recap-card">
  <h2 class="card-title">Recently closed</h2>
  <ul class="recap-list">{rows}</ul>
</section>"""


def _empty_state() -> str:
    return """
<section class="card empty-card">
  <p>Nothing open right now &mdash; nice work.</p>
  <p class="muted">Keep reviewing to stay sharp; new misses will show up here.</p>
</section>"""


def _footer(c: dict) -> str:
    return f"""
<footer class="page-footer">
  <p>cc_spine.cram_sheet &middot; schema {_e(c['schema_version'])} &middot; day {c['generated_at_day']}
     &middot; every fact here is from an item you already attempted &mdash; no answer keys, no PII.</p>
</footer>"""


_STYLE = """
:root {
  --bg: #F1F4F6; --surface: #FFFFFF; --surface-2: #E7ECEF;
  --text: #10181D; --text-muted: #51616B; --border: #D7DEE2;
  --accent: #0E7C86; --accent-strong: #0B636B;
  --good: #2F8F4E; --warn: #B4791A;
  --good-bg: rgba(47,143,78,.13); --warn-bg: rgba(180,121,26,.15);
  --serif: ui-serif, "Iowan Old Style", "Palatino Linotype", Georgia, serif;
  --sans: -apple-system, "Segoe UI", "Noto Sans", sans-serif;
  --mono: ui-monospace, "SF Mono", "Cascadia Code", "Roboto Mono", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0B1014; --surface: #121920; --surface-2: #1A232B;
    --text: #E7EEF1; --text-muted: #93A3AC; --border: #26313A;
    --accent: #3FC1CC; --accent-strong: #63D6DF;
    --good: #4CAF6D; --warn: #E0A548;
    --good-bg: rgba(76,175,109,.18); --warn-bg: rgba(224,165,72,.18);
  }
}
:root[data-theme="dark"] {
  --bg: #0B1014; --surface: #121920; --surface-2: #1A232B;
  --text: #E7EEF1; --text-muted: #93A3AC; --border: #26313A;
  --accent: #3FC1CC; --accent-strong: #63D6DF;
  --good: #4CAF6D; --warn: #E0A548;
  --good-bg: rgba(76,175,109,.18); --warn-bg: rgba(224,165,72,.18);
}
:root[data-theme="light"] {
  --bg: #F1F4F6; --surface: #FFFFFF; --surface-2: #E7ECEF;
  --text: #10181D; --text-muted: #51616B; --border: #D7DEE2;
  --accent: #0E7C86; --accent-strong: #0B636B;
  --good: #2F8F4E; --warn: #B4791A;
  --good-bg: rgba(47,143,78,.13); --warn-bg: rgba(180,121,26,.15);
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font-family: var(--sans);
       -webkit-font-smoothing: antialiased; }
.page { max-width: 720px; margin: 0 auto; padding: 40px 24px 64px; display: flex;
        flex-direction: column; gap: 28px; }
.masthead { display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap;
            gap: 16px; border-bottom: 1px solid var(--border); padding-bottom: 20px; }
.eyebrow { margin: 0 0 6px; font-family: var(--mono); font-size: 11px; letter-spacing: .08em;
           text-transform: uppercase; color: var(--text-muted); }
.wordmark { margin: 0; font-family: var(--serif); font-size: 32px; font-weight: 500;
            text-wrap: balance; border-left: 3px solid var(--accent); padding-left: 12px; }
.stat-row { display: flex; gap: 20px; }
.stat { display: flex; flex-direction: column; gap: 2px; text-align: right; }
.stat-value { font-family: var(--mono); font-size: 22px; font-weight: 600; font-variant-numeric: tabular-nums; }
.stat-label { font-size: 11px; color: var(--text-muted); }
.domain-block { display: flex; flex-direction: column; gap: 14px; }
.domain-title { font-family: var(--serif); font-size: 22px; font-weight: 500; margin: 0;
                display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.domain-acc { font-family: var(--mono); font-size: 12px; font-weight: 400; color: var(--text-muted); }
.trap-card { background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
             padding: 18px 20px; display: flex; flex-direction: column; gap: 10px; }
.stem-quote { margin: 0 0 4px; padding-left: 12px; border-left: 2px solid var(--border);
              font-style: italic; color: var(--text-muted); font-size: 14px; }
.trap-row { display: grid; grid-template-columns: 100px 1fr; gap: 12px; align-items: baseline; }
.trap-row p { margin: 0; font-size: 14px; line-height: 1.5; }
.trap-rule p { font-weight: 600; }
.trap-label { font-family: var(--mono); font-size: 11px; letter-spacing: .06em; text-transform: uppercase;
              color: var(--text-muted); }
.trap-foot { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 4px; }
.tag { font-family: var(--mono); font-size: 11px; background: var(--surface-2); border: 1px solid var(--border);
       border-radius: 3px; padding: 3px 8px; color: var(--text-muted); }
.chip { display: inline-block; font-family: var(--mono); font-size: 11px; letter-spacing: .05em;
        text-transform: uppercase; padding: 3px 8px; border-radius: 3px; }
.chip-warn { background: var(--warn-bg); color: var(--warn); }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 20px; }
.card-title { margin: 0 0 12px; font-family: var(--mono); font-size: 12px; letter-spacing: .07em;
              text-transform: uppercase; color: var(--text-muted); }
.recap-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.recap-list li { display: flex; align-items: center; gap: 10px; font-size: 14px; }
.dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
.dot-good { background: var(--good); }
.empty-card p { margin: 0 0 6px; }
.muted { color: var(--text-muted); font-size: 13px; }
.page-footer { border-top: 1px solid var(--border); padding-top: 16px; }
.page-footer p { margin: 0; font-family: var(--mono); font-size: 11px; color: var(--text-muted); }
"""


def render_html(cram_sheet: dict, standalone: bool = True) -> str:
    """Render the cram sheet to HTML. Pure and deterministic — same dict, same string.

    ``standalone=True`` (default) returns a complete document. ``standalone=False`` returns a
    head-less fragment (title + style + body content only) for host embedding."""
    domains_html = "".join(_domain_section(d) for d in cram_sheet["domains"])
    body_main = domains_html if cram_sheet["domains"] else _empty_state()
    body = f"""
<div class="page">
  {_masthead(cram_sheet)}
  {body_main}
  {_recap(cram_sheet)}
  {_footer(cram_sheet)}
</div>"""
    title = "<title>CC Weak-Area Cram Sheet</title>"
    style = f"<style>{_STYLE}</style>"
    if not standalone:
        return f"{title}\n{style}\n{body}"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{title}
{style}
</head>
<body>
{body}
</body>
</html>"""
