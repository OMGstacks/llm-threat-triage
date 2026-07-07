# PR-11b Visual Readiness Dashboard

**Slice:** PR-11b — the **visual layer** (`cc_spine/dashboard_view.py`) over the PR-11a data model.
No new data, no new policy: a pure HTML formatter over exactly the fields
`cc_spine.dashboard.build_dashboard` already vetted as content-free.

---

## 1. What it is

`render_html(dashboard, standalone=True)` — a **pure, deterministic** function from the PR-11a
dashboard dict to an HTML string. Two output modes from one template (no drift between them):

- `standalone=True` (default; CLI `dashboard --html`) — a complete, self-opening document.
- `standalone=False` — a head-less fragment (`<title>` + `<style>` + body content, no
  `<!DOCTYPE>`/`<html>`/`<head>`/`<body>`) for a host that supplies its own document skeleton (e.g.
  an Artifact viewer).

The renderer imports nothing from `cc_spine` — it formats whatever dict it is handed. It cannot
itself expand what the data model already decided is safe to show, because it never receives a
stem, an answer, a key, or a PII field in the first place.

## 2. Design

Read as an **instrument panel**, not a generic analytics dashboard — the subject is a certification
exam-readiness gate, not a SaaS metrics page. Verdict surfaces first (the summary before the
detail, since a dashboard is scanned, not read top-to-bottom); blockers next, if any; then the
supporting instrument grid.

- **Color:** cool-neutral grounds (`#F1F4F6` light / `#0B1014` dark); a restrained instrument-teal
  accent (`#0E7C86` / `#3FC1CC`) used only for the wordmark rule and focus states; semantic
  good/bad (`#2F8F4E`/`#C13F32` light, `#4CAF6D`/`#E36657` dark) kept **distinct from the accent**
  and reserved for domain-accuracy gauges and status chips — the gauges that gate readiness get
  semantic color, **strictly two-tone at the exact 75% hard-blocker threshold** (no intermediate
  "near miss" tier — see §3); informational bars (bank accuracy) get the accent, never a semantic
  color, since bank accuracy gates nothing.
- **Type:** a serif masthead only (`ui-serif, "Iowan Old Style", Georgia`) for certification
  gravitas; a humanist sans for prose; **monospace for every data figure, id, and label** — an
  instrument-panel reading that "this is measured data," applied consistently throughout.
- **Layout:** masthead (wordmark + verdict chip + score) → proof-scale banner if applicable →
  attention card (blockers / incompleteness / below-target score) if applicable → a two-column
  instrument grid (domain/bank/mock gauges left; spaced-repetition/misconceptions right) → footer.
  Both themes (`prefers-color-scheme` + `data-theme` override) are fully styled via CSS custom
  properties, never hardcoded inside a media query.

## 3. Domain-gauge calibration (the review's central catch)

The domain gauge color is **strictly two-tone**, matching `learner_state.readiness_report`'s hard-blocker
gate exactly (`accuracy < 0.75` ⇒ blocker). There is deliberately **no third "near miss" color tier** —
an earlier draft added one (amber, 0.60–0.749) purely for visual nuance, and the independent review
caught that it was miscalibrated: a domain at 70% accuracy is an **active hard blocker** (and shows red
in the Attention card) while the same domain's gauge rendered amber, silently implying it was less
serious than the Attention card said. The gauge's fill **width** already shows exactly how far a
domain is from the 75% line; color must never suggest a real blocker is "less bad" than the gate says.
Bank-accuracy bars use the accent (informational — bank accuracy gates nothing) and never borrow the
semantic palette, so there is no risk of the same confusion there.

## 4. Honesty in the render

- **Truncation is honest, not implied.** `spaced_repetition.due_now` is the true total;
  `next_review_items` is capped at 10 by the data model. The view shows "+N more due" **only** where
  the two counts share a basis (the due queue) and a true remainder is computable — it does **not**
  fabricate a similar "+N more" for `top_misconceptions` or `open_misconceptions`, where the data
  model gives no comparable total. Two tests pin this (`test_remainder_note_shown_when_due_exceeds_shown`,
  `test_no_remainder_note_when_due_matches_shown`).
- **No fake interactivity.** Item-id chips and misconception rows are static tags, not styled as
  clickable — this is a read-only render with no click handlers, so nothing looks actionable that
  isn't.
- **Every verdict branch renders honestly**, not just the top-level chip: `ready` (good, no attention
  card), `not-ready` from incompleteness (warn chip, the model's own note text), `not-ready` from hard
  blockers (bad chip, each blocker listed), and the otherwise-uncovered case — complete, no
  blockers, but score under the 80% target — gets its own line rather than silently falling through.

## 5. Content-freedom (inherited, re-verified)

The view cannot leak what it never receives, but content-freedom is tested at this layer too, not
just assumed from PR-11a: no answer-bearing field name appears in the rendered markup; no practice
*or* holdout stem/choice text appears anywhere in the output; HTML-special characters in any data
field are escaped (`html.escape`), so a hostile-looking string in a blocker message cannot inject
markup.

## 6. Demonstration

```
python3 -m cc_spine.cli dashboard --attempts tests/fixtures/synthetic_attempt_stream.json --now 5 --html --out report.html
make dashboard-html-check
```

## 7. Review before commit (§16.0)

Independent review — **completed before commit** (PR-9 lesson). Verdict **needs-work**: one major
(the domain-gauge miscalibration, §3) plus 4 minor/nit findings, all fixed before this commit:

| # | Sev | Finding | Fix |
|---|---|---|---|
| F1 | **major** | domain gauge had a three-tier good/warn/bad classification; the 0.60–0.749 "warn" band sat entirely inside the real hard-blocker range (<0.75), rendering an active blocker as amber ("near miss") while the Attention card correctly showed it red | collapsed to strict two-tone matching the gate exactly (§3); dead `.gauge-warn` CSS rule removed; regression test sweeps the whole former warn band, asserting every value renders `gauge-bad` |
| F2 | minor | the HTML-validity test overrode `HTMLParser.error()`, which the stdlib parser never calls — a near-tautological check | replaced with a real open/close tag-balance tracker |
| F3 | minor | no test exercised a non-empty domain/bank gauge or its threshold classification — the exact gap that let F1 ship | added `DomainGaugeTest`/`BankGaugeTest`: every value in the former warn band, the good boundary, the accent-not-semantic bank check, both empty states |
| F4 | nit | gauge fill width clamped the upper bound but not the lower | symmetric `max(0.0, min(100.0, …))` in both domain and bank cards |
| F5 | nit | the incomplete-state attention row depended on `note` being truthy — an unstated contract with the data model | falls back to a generic "readiness is incomplete" line if `note` is empty, so an incomplete state can never render a silently-empty attention card |

The reviewer also caught two now-fixed test-suite instances of the same false-positive pattern (a
bare substring check matching the CSS rule definition, not the rendered element) while verifying the
fixes — both corrected to check the actual rendered class attribute. Full record in
`pr11b-visual-dashboard-review.json`.

## 8. Next → cram sheets

The dashboard closes the PR-11 slice (data model + visual layer). Next: cram sheets / weak-area
review packets over the same misconception/journal data.
