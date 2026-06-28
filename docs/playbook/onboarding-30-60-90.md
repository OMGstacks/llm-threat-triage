# First 90 days — Technical Intelligence Analyst (SIA)

A concrete onboarding plan for the role. The shape mirrors how you'd ramp on *any* intelligence
team: learn the ground truth, ship small and useful early, then move from reactive to proactive.
Adapt specifics to the actual stack and team norms once you're in.

> Guiding principle: **earn trust by shipping decision-ready output fast, then widen scope.**
> Weeks 1–4 you're learning the data; by day 90 you're surfacing novel harms others miss.

---

## Days 0–30 — Learn the ground truth, ship something small

**Goals:** understand the data, the tooling, the taxonomy in *this* environment; deliver one
real, useful artifact.

- **Data & tooling:** map where LLM logs live, the schema, the channels/provenance model, and the
  existing detection/query tooling. Re-create the analyst loop locally so you can move fast.
- **Taxonomy in context:** learn how the team maps abuse to OWASP LLM / ATLAS (or their internal
  taxonomy), the severity rubric, and the escalation path. Read recent briefs to learn the house style.
- **Shadow & triage:** work the existing queue alongside someone senior; learn what "confirmed vs
  suspected" means here and where the false-positive landmines are.
- **Ship one thing:** a single useful query or a tightened detector for a known noisy pattern —
  small, correct, and reviewed. Your first PR sets your reputation.
- **Relationships:** meet the product/safety/eng partners who *consume* the intelligence — learn
  what decisions they actually make, so your output targets them.

**30-day success looks like:** you can independently triage a finding end-to-end and have shipped
one reviewed improvement.

## Days 31–60 — Own a slice, write the briefs

**Goals:** own an attack class or surface area; produce regular, trusted intelligence.

- **Own a class/surface:** take primary coverage of one area (e.g. indirect injection in RAG, or
  consumption/abuse). Know its baseline rates, its repeat offenders, its trend.
- **Investigate chains, not just rows:** correlate injection → tool call → egress; pull campaigns
  vs one-offs. Graduate from "alerts" to "incidents."
- **Brief on cadence:** deliver the weekly brief for your area in the team's format — top risks,
  what's rising, what you shipped, what you recommend. Make it decision-ready.
- **Close FP loops:** every recurring false positive becomes a tuned rule with a regression test;
  every recurring gap becomes a new detector.
- **Start the anomaly on-ramp:** stand up per-principal behavioral baselines (token volume, query
  diversity, tool-call rate); prototype a PyOD pass to surface low-prevalence outliers.

**60-day success looks like:** you own a surface, your briefs are trusted, and you've turned at
least one investigation into a durable detector.

## Days 61–90 — Go proactive, surface the novel

**Goals:** move from reactive triage to forecasting and novel-harm discovery; multiply the team.

- **Forecast, don't just report:** track slopes and emerging clusters; tie internal signals to
  external context; deliver a forward-looking outlook ("what's likely next, and why").
- **Discover a novel harm:** use anomaly + clustering to surface something the signatures missed,
  name it, measure it, brief it, and ship a detector for it. This is the headline deliverable of
  the role — do it once well and you've proven the loop.
- **Multiply yourself:** turn your best one-off analyses into reusable playbooks/queries/tools the
  whole team can run (the zero-to-one → reusable-tool pattern).
- **Propose an improvement to the system:** a coverage gap (an uncovered OWASP class), a workflow
  bottleneck, or a better signal — with a concrete plan, not just a complaint.

**90-day success looks like:** you've surfaced and operationalized at least one novel harm,
your tooling is used beyond you, and you're trusted to forecast, not just triage.

---

## Anti-goals (what *not* to do)
- Don't boil the ocean in month one — ship small and correct before broad.
- Don't blur confirmed and suspected to look productive; calibrated credibility compounds.
- Don't build a detector with no test, or a dashboard no one reads. Output that drives a decision
  beats output that looks busy.
- Don't hoard a clever analysis as a one-off — operationalize it or it dies with your attention.
