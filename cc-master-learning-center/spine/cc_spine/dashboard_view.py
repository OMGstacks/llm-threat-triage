"""cc_spine.dashboard_view — the visual readiness dashboard (PR-11b).

The visual layer over the PR-11a data model. ``render_html(dashboard)`` is a PURE, deterministic
function: it formats exactly the fields ``cc_spine.dashboard.build_dashboard`` already vetted as
content-free (ids, counts, accuracies, verdicts) — it never receives, reads, or has access to a
stem, an answer, a key, or a PII field, so there is nothing here that could leak one. It adds no
readiness policy either: the verdict, score, and blockers are rendered verbatim from the dashboard,
never recomputed.

Two output modes, one template (no drift between them):
- ``standalone=True`` (default; CLI ``dashboard --html``) — a complete, self-opening HTML document.
- ``standalone=False`` — a head-less fragment (``<title>`` + ``<style>`` + body content, no
  ``<!DOCTYPE>``/``<html>``/``<head>``/``<body>``) for embedding inside a host page that supplies its
  own document skeleton.

Stdlib only (``html.escape`` for defensive escaping of data-derived strings). Imports nothing from
``cc_spine`` — it is a pure formatter over whatever dict it is given, so it cannot itself expand what
the data model already decided is safe to show.
"""

from __future__ import annotations

from html import escape as _e

SCHEMA_VERSION = "1.0.0"           # the readiness-dashboard schema version this view renders
_DOMAIN_GOOD = 0.75                # the ONLY domain threshold: matches learner_state.readiness_report's
                                    # hard-blocker gate exactly (accuracy < 0.75 = blocker). Strictly
                                    # two-tone on purpose (review F1): an earlier three-tier version
                                    # colored 0.60-0.749 "warn" (amber) even though that whole range IS
                                    # an active hard blocker, contradicting the Attention card's red
                                    # listing of the same domain. The fill WIDTH already shows exactly
                                    # how far a domain is from the gate; color must never imply a
                                    # blocker is "less bad" than the gate says it is.


def _pct(x, decimals: int = 1) -> str:
    return "—" if x is None else f"{x * 100:.{decimals}f}%"


def _domain_status(acc: float) -> str:
    return "good" if acc >= _DOMAIN_GOOD else "bad"


def _chip(label: str, status: str) -> str:
    return f'<span class="chip chip-{status}">{_e(label)}</span>'


def _masthead(d: dict) -> str:
    r = d["readiness"]
    if r["verdict"] == "ready":
        chip_label, chip_status = "READY", "good"
    elif not r["complete"]:
        chip_label, chip_status = "NOT READY — INCOMPLETE", "warn"
    else:
        chip_label, chip_status = "NOT READY", "bad"
    return f"""
<header class="masthead">
  <div class="wordmark-block">
    <p class="eyebrow">CC Master Learning Center &middot; ISC2 Certified in Cybersecurity</p>
    <h1 class="wordmark">Exam Readiness</h1>
  </div>
  <div class="verdict-block">
    {_chip(chip_label, chip_status)}
    <p class="score" title="weighted over {len(r['weighted_over'])} of 5 components">{_pct(r['score'])}</p>
    <p class="score-caption">scored over {len(r['weighted_over'])} of 5 components</p>
  </div>
</header>"""


def _content_scale_banner(d: dict) -> str:
    cs = d["content_scale"]
    if cs["status"] != "proof_scale" or not cs.get("caveat"):
        return ""
    return f"""
<div class="banner">
  <span class="banner-label">Proof-scale content</span>
  <p>{_e(cs['caveat'])}</p>
</div>"""


def _attention_card(d: dict) -> str:
    r = d["readiness"]
    rows = []
    for b in r["hard_blockers"]:
        rows.append(f'<li class="attn-row"><span class="dot dot-bad"></span>{_e(b)}</li>')
    if not r["complete"]:
        # fall back to a generic line even if `note` is empty/None — an incomplete state must never
        # render as a silent, row-less attention card (review F5: don't depend on an unstated
        # note-is-truthy contract with dashboard.py).
        note = r.get("note") or "readiness is incomplete — see the readiness report for details"
        rows.append(f'<li class="attn-row"><span class="dot dot-warn"></span>{_e(note)}</li>')
    if r["complete"] and not r["hard_blockers"] and r["verdict"] != "ready":
        rows.append('<li class="attn-row"><span class="dot dot-warn"></span>'
                    f'score {_pct(r["score"])} is below the 80% readiness target</li>')
    if not rows:
        return ""
    return f"""
<section class="card attn-card">
  <h2 class="card-title">Attention</h2>
  <ul class="attn-list">{''.join(rows)}</ul>
</section>"""


def _domain_card(d: dict) -> str:
    rows = []
    for dom, s in d["domain_accuracy"].items():
        status = _domain_status(s["accuracy"])
        fill = max(0.0, min(100.0, s["accuracy"] * 100))
        rows.append(f"""
    <div class="gauge-row">
      <span class="gauge-label">{_e(dom)}</span>
      <div class="gauge-track">
        <div class="gauge-threshold" style="left:{_DOMAIN_GOOD * 100:.0f}%"></div>
        <div class="gauge-fill gauge-{status}" style="width:{fill:.1f}%"></div>
      </div>
      <span class="gauge-value">{_pct(s['accuracy'])}</span>
      <span class="gauge-attempts">{s['attempts']} attempt{'s' if s['attempts'] != 1 else ''}</span>
    </div>""")
    body = "".join(rows) if rows else '<p class="empty">No domain attempts recorded yet.</p>'
    return f"""
<section class="card">
  <h2 class="card-title">Domain accuracy</h2>
  <p class="card-caption">threshold marks the 75% hard-blocker gate</p>
  {body}
</section>"""


def _bank_card(d: dict) -> str:
    rows = []
    for bank, s in d["bank_accuracy"].items():
        fill = max(0.0, min(100.0, s["accuracy"] * 100))
        rows.append(f"""
    <div class="gauge-row gauge-row-compact">
      <span class="gauge-label">{_e(bank)}</span>
      <div class="gauge-track">
        <div class="gauge-fill gauge-accent" style="width:{fill:.1f}%"></div>
      </div>
      <span class="gauge-value">{_pct(s['accuracy'])}</span>
      <span class="gauge-attempts">{s['total']} item{'s' if s['total'] != 1 else ''}</span>
    </div>""")
    body = "".join(rows) if rows else '<p class="empty">No bank attempts recorded yet.</p>'
    return f"""
<section class="card">
  <h2 class="card-title">Bank accuracy</h2>
  {body}
</section>"""


def _mock_card(d: dict) -> str:
    m = d["mock"]
    if m is None:
        return """
<section class="card">
  <h2 class="card-title">Mock exam</h2>
  <div class="empty-state">
    <p>No mock graded yet.</p>
    <p class="muted">Fresh-scenario accuracy needs a graded mock (<code>mock_exam.grade_mock</code>)
       before readiness can complete.</p>
  </div>
</section>"""
    return f"""
<section class="card">
  <h2 class="card-title">Mock exam</h2>
  <div class="stat-row">
    <div class="stat">
      <span class="stat-value">{_pct(m['fresh_scenario_accuracy'])}</span>
      <span class="stat-label">fresh-scenario accuracy ({m['fresh_scenario_count']} submitted)</span>
    </div>
    <div class="stat">
      <span class="stat-value">{_pct(m['overall_accuracy'])}</span>
      <span class="stat-label">overall accuracy</span>
    </div>
    <div class="stat">
      <span class="stat-value">{m['burned_holdout_count']}</span>
      <span class="stat-label">holdout scenario(s) burned</span>
    </div>
  </div>
</section>"""


def _spaced_repetition_card(d: dict) -> str:
    sr = d["spaced_repetition"]
    chips = "".join(f'<span class="tag">{_e(iid)}</span>' for iid in sr["next_review_items"])
    remainder = sr["due_now"] - len(sr["next_review_items"])
    more = f'<p class="muted more-note">+{remainder} more due</p>' if remainder > 0 else ""
    mature_pct = (sr["mature_items"] / sr["total_items"] * 100) if sr["total_items"] else 0.0
    return f"""
<section class="card">
  <h2 class="card-title">Spaced repetition</h2>
  <div class="stat-row">
    <div class="stat"><span class="stat-value">{sr['due_now']}</span><span class="stat-label">due now</span></div>
    <div class="stat"><span class="stat-value">{sr['total_items']}</span><span class="stat-label">tracked items</span></div>
    <div class="stat"><span class="stat-value">{sr['mature_items']}</span><span class="stat-label">mature ({mature_pct:.0f}%)</span></div>
  </div>
  <p class="card-caption">next up</p>
  <div class="tag-row">{chips}</div>
  {more}
</section>"""


def _misconceptions_card(d: dict) -> str:
    wa = d["wrong_answers"]
    tm = d["top_misconceptions"]
    max_missed = max((m["missed"] for m in tm), default=1)
    rows = []
    for m in tm:
        width = (m["missed"] / max_missed * 100) if max_missed else 0
        status = "good" if m["closed"] else "warn"
        state = "closed" if m["closed"] else "open"
        rows.append(f"""
    <div class="miss-row">
      <span class="miss-id">{_e(m['misconception_id'])}</span>
      <div class="miss-track"><div class="miss-fill miss-{status}" style="width:{width:.0f}%"></div></div>
      <span class="miss-count">{m['missed']}&times;</span>
      {_chip(state, status)}
    </div>""")
    body = "".join(rows) if rows else '<p class="empty">No missed misconceptions yet.</p>'
    return f"""
<section class="card">
  <h2 class="card-title">Wrong answers</h2>
  <div class="stat-row">
    <div class="stat"><span class="stat-value">{wa['open_count']}</span><span class="stat-label">open</span></div>
    <div class="stat"><span class="stat-value">{_pct(wa['closure_rate'])}</span><span class="stat-label">closure rate</span></div>
  </div>
  <p class="card-caption">top misconceptions</p>
  {body}
</section>"""


def _footer(d: dict) -> str:
    return f"""
<footer class="page-footer">
  <p>cc_spine.dashboard &middot; schema {_e(d['schema_version'])} &middot; day {d['generated_at_day']}
     &middot; deterministic, content-free projection &mdash; no answers, no PII.</p>
</footer>"""


_STYLE = """
:root {
  --bg: #F1F4F6; --surface: #FFFFFF; --surface-2: #E7ECEF;
  --text: #10181D; --text-muted: #51616B; --border: #D7DEE2;
  --accent: #0E7C86; --accent-strong: #0B636B;
  --good: #2F8F4E; --warn: #B4791A; --bad: #C13F32;
  --good-bg: rgba(47,143,78,.13); --warn-bg: rgba(180,121,26,.15); --bad-bg: rgba(193,63,50,.13);
  --serif: ui-serif, "Iowan Old Style", "Palatino Linotype", Georgia, serif;
  --sans: -apple-system, "Segoe UI", "Noto Sans", sans-serif;
  --mono: ui-monospace, "SF Mono", "Cascadia Code", "Roboto Mono", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0B1014; --surface: #121920; --surface-2: #1A232B;
    --text: #E7EEF1; --text-muted: #93A3AC; --border: #26313A;
    --accent: #3FC1CC; --accent-strong: #63D6DF;
    --good: #4CAF6D; --warn: #E0A548; --bad: #E36657;
    --good-bg: rgba(76,175,109,.18); --warn-bg: rgba(224,165,72,.18); --bad-bg: rgba(227,102,87,.18);
  }
}
:root[data-theme="dark"] {
  --bg: #0B1014; --surface: #121920; --surface-2: #1A232B;
  --text: #E7EEF1; --text-muted: #93A3AC; --border: #26313A;
  --accent: #3FC1CC; --accent-strong: #63D6DF;
  --good: #4CAF6D; --warn: #E0A548; --bad: #E36657;
  --good-bg: rgba(76,175,109,.18); --warn-bg: rgba(224,165,72,.18); --bad-bg: rgba(227,102,87,.18);
}
:root[data-theme="light"] {
  --bg: #F1F4F6; --surface: #FFFFFF; --surface-2: #E7ECEF;
  --text: #10181D; --text-muted: #51616B; --border: #D7DEE2;
  --accent: #0E7C86; --accent-strong: #0B636B;
  --good: #2F8F4E; --warn: #B4791A; --bad: #C13F32;
  --good-bg: rgba(47,143,78,.13); --warn-bg: rgba(180,121,26,.15); --bad-bg: rgba(193,63,50,.13);
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font-family: var(--sans);
       -webkit-font-smoothing: antialiased; }
.page { max-width: 960px; margin: 0 auto; padding: 40px 24px 64px; display: flex;
        flex-direction: column; gap: 24px; }
.masthead { display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap;
            gap: 16px; border-bottom: 1px solid var(--border); padding-bottom: 20px; }
.eyebrow { margin: 0 0 6px; font-family: var(--mono); font-size: 11px; letter-spacing: .08em;
           text-transform: uppercase; color: var(--text-muted); }
.wordmark { margin: 0; font-family: var(--serif); font-size: 34px; font-weight: 500;
            text-wrap: balance; border-left: 3px solid var(--accent); padding-left: 12px; }
.verdict-block { text-align: right; }
.score { margin: 6px 0 0; font-family: var(--mono); font-size: 32px; font-weight: 600;
         font-variant-numeric: tabular-nums; line-height: 1; }
.score-caption { margin: 4px 0 0; font-size: 12px; color: var(--text-muted); }
.chip { display: inline-block; font-family: var(--mono); font-size: 11px; letter-spacing: .06em;
        text-transform: uppercase; padding: 5px 10px; border-radius: 3px; }
.chip-good { background: var(--good-bg); color: var(--good); }
.chip-warn { background: var(--warn-bg); color: var(--warn); }
.chip-bad { background: var(--bad-bg); color: var(--bad); }
.banner { border: 1px dashed var(--warn); background: var(--warn-bg); border-radius: 4px;
          padding: 12px 16px; display: flex; flex-direction: column; gap: 4px; }
.banner-label { font-family: var(--mono); font-size: 11px; letter-spacing: .06em; text-transform: uppercase;
                color: var(--warn); }
.banner p { margin: 0; font-size: 13px; color: var(--text); }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
        padding: 20px; animation: rise .28s ease-out both; }
.attn-card { border-color: var(--bad); }
.card-title { margin: 0 0 4px; font-family: var(--mono); font-size: 12px; letter-spacing: .07em;
              text-transform: uppercase; color: var(--text-muted); }
.card-caption { margin: 12px 0 8px; font-size: 12px; color: var(--text-muted); }
.attn-list { list-style: none; margin: 12px 0 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.attn-row { display: flex; align-items: center; gap: 10px; font-size: 14px; }
.dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
.dot-bad { background: var(--bad); } .dot-warn { background: var(--warn); } .dot-good { background: var(--good); }
.grid { display: grid; grid-template-columns: 1.25fr 1fr; gap: 20px; }
.grid > .col { display: flex; flex-direction: column; gap: 20px; }
@media (max-width: 720px) { .grid { grid-template-columns: 1fr; } }
.gauge-row { display: grid; grid-template-columns: 44px 1fr 56px 90px; align-items: center;
             gap: 12px; padding: 8px 0; border-top: 1px solid var(--border); }
.gauge-row:first-of-type { border-top: none; }
.gauge-row-compact { grid-template-columns: 140px 1fr 56px 70px; }
.gauge-label { font-family: var(--mono); font-size: 13px; font-weight: 600; }
.gauge-track { position: relative; height: 8px; background: var(--surface-2); border-radius: 4px;
               overflow: hidden; }
.gauge-fill { height: 100%; border-radius: 4px; }
.gauge-good { background: var(--good); } .gauge-bad { background: var(--bad); }
.gauge-accent { background: var(--accent); }
.gauge-threshold { position: absolute; top: -2px; bottom: -2px; width: 2px; background: var(--text);
                   opacity: .35; }
.gauge-value { font-family: var(--mono); font-size: 13px; font-variant-numeric: tabular-nums;
               text-align: right; }
.gauge-attempts { font-size: 11px; color: var(--text-muted); text-align: right; }
.stat-row { display: flex; gap: 24px; flex-wrap: wrap; margin-top: 8px; }
.stat { display: flex; flex-direction: column; gap: 2px; }
.stat-value { font-family: var(--mono); font-size: 24px; font-weight: 600; font-variant-numeric: tabular-nums; }
.stat-label { font-size: 11px; color: var(--text-muted); }
.tag-row { display: flex; flex-wrap: wrap; gap: 6px; }
.tag { font-family: var(--mono); font-size: 12px; background: var(--surface-2); border: 1px solid var(--border);
       border-radius: 3px; padding: 3px 8px; }
.more-note { font-size: 12px; margin: 8px 0 0; }
.miss-row { display: grid; grid-template-columns: 1fr 100px 32px 64px; align-items: center; gap: 10px;
            padding: 7px 0; border-top: 1px solid var(--border); }
.miss-row:first-of-type { border-top: none; }
.miss-id { font-family: var(--mono); font-size: 12px; overflow-wrap: anywhere; }
.miss-track { height: 6px; background: var(--surface-2); border-radius: 3px; overflow: hidden; }
.miss-fill { height: 100%; border-radius: 3px; }
.miss-good { background: var(--good); } .miss-warn { background: var(--warn); }
.miss-count { font-family: var(--mono); font-size: 11px; text-align: right; color: var(--text-muted); }
.empty, .empty-state p { color: var(--text-muted); font-size: 13px; margin: 8px 0 0; }
.muted { color: var(--text-muted); }
code { font-family: var(--mono); background: var(--surface-2); padding: 1px 5px; border-radius: 3px;
       font-size: 12px; }
.page-footer { border-top: 1px solid var(--border); padding-top: 16px; }
.page-footer p { margin: 0; font-family: var(--mono); font-size: 11px; color: var(--text-muted); }
@keyframes rise { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
@media (prefers-reduced-motion: reduce) { .card { animation: none; } }
"""


def render_html(dashboard: dict, standalone: bool = True) -> str:
    """Render the dashboard to HTML. Pure and deterministic — same dashboard dict, same string.

    ``standalone=True`` (default) returns a complete document (doctype/html/head/body): open it
    directly in a browser. ``standalone=False`` returns a head-less fragment (title + style + body
    content only) for a host that supplies its own document skeleton."""
    body = f"""
<div class="page">
  {_masthead(dashboard)}
  {_content_scale_banner(dashboard)}
  {_attention_card(dashboard)}
  <div class="grid">
    <div class="col">
      {_domain_card(dashboard)}
      {_bank_card(dashboard)}
      {_mock_card(dashboard)}
    </div>
    <div class="col">
      {_spaced_repetition_card(dashboard)}
      {_misconceptions_card(dashboard)}
    </div>
  </div>
  {_footer(dashboard)}
</div>"""
    title = "<title>CC Exam Readiness Dashboard</title>"
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
