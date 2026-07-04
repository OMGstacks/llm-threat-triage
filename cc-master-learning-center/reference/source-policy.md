# Source Policy — Tiers, IP Boundaries, and Copyright Rules

Status: normative for the CC Master Learning Center. Every source used by this project is
assigned a tier in [`source-registry.json`](source-registry.json), and every fact, note, and
bank item must trace to a registered source through its `source_id`.

## 1. Source authority tiers

| Tier | Source class | Allowed use |
|---|---|---|
| 0 | Official ISC2 exam outline and exam pages | Normative exam facts: domains, weights, objectives, exam logistics |
| 1 | NIST, CISA, MITRE, and other official standards bodies | Reference enrichment (sanitization, incident response, PQC, cloud definitions) |
| 2 | User-approved cleaned notes | Study content, fact-card grounding |
| 3 | Raw course transcripts | Input only — never learner-facing without cleanup and review |
| 4 | Generated content | Requires fact grounding and human review before any learner-facing use |

Rules:

- Tier 0 is the only authority for what the exam covers and how it is weighted. Tier 1–4
  sources may enrich but never override Tier 0.
- Tier 3 material is pipeline input. It is never quoted at length, never published, and never
  treated as authoritative exam truth.
- Tier 4 (generated) content is untrusted until it passes fact grounding against Tier 0–2
  sources and human review.

## 2. ISC2 IP boundary

- No verbatim real-exam content, ever. This is an immutable constraint.
- ISC2 site contents are ISC2 property and may not be copied, reproduced, or distributed
  without permission. Official outline content is **referenced and minimally summarized**,
  never wholesale copied.
- Reference files carry a `copyright_note` and link to the official source instead of
  reproducing it.

## 3. Course Transcript IP boundary

Distinct from the ISC2 boundary — this governs instructor/course material:

- Raw course transcripts are **not** checked into this repository unless explicitly authorized.
- No long verbatim transcript passages in learner-facing notes.
- Only minimal reviewed support spans are stored for provenance.
- Prefer paraphrased cleaned notes, concept cards, and objective mappings.
- Raw-source fingerprints and local source IDs are kept separate from published content.

## 4. Numeric support-span limits (enforceable)

| Source kind | Limit |
|---|---|
| Structured JSON | Exact field value only |
| Markdown reference | One heading excerpt or ≤ 50 words, whichever is smaller |
| Transcript | ≤ 25 words unless explicitly authorized; prefer paraphrase |

No support span may contain a full practice question, a full answer key, or a long lecture
passage.

## 5. Source freshness

Every registry entry records `retrieved_at`, `effective_date`, and (where applicable) a
`superseded_by_notice`. The CC exam outline is volatile right now: the current outline is
effective 2025-10-01 and a new outline becomes effective 2026-09-01. The
`source_freshness_guard` (reserved; activates with the validator suite) fails validation when
a source passes its re-review date or its successor becomes effective.

## 6. Registered guard names

The following validators enforce this policy as the spine grows (reserved in PR-1, activated
in later PRs):

- `source_freshness_guard`
- `ip_boundary_guard`
- `no_verbatim_bulk_reproduction`
