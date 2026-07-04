# CC Master Learning Center

A governed exam-prep content system for the **ISC2 Certified in Cybersecurity (CC)**
certification, built on the fact-store governance pattern proven by the sibling
[`osai-prep-studio/`](../osai-prep-studio/) program: provenance-backed fact cards,
learning-objective-true question banks, fail-closed validation gates, and disciplined growth
in small proven slices.

**Primary exam target:** current CC outline (effective 2025-10-01), with a maintained
crosswalk to the 2026-09-01 outline. See
[`reference/cc-exam-blueprint.md`](reference/cc-exam-blueprint.md).

## The deliverable

[`00-governance-spec.md`](00-governance-spec.md) — the governance specification. Everything
else in this directory is the scaffold that spec governs.

## Directory map

| Path | Purpose |
|---|---|
| [`00-governance-spec.md`](00-governance-spec.md) | Governance spec: constraints, schemas, banks, gates, roadmap |
| [`reference/cc-exam-blueprint.md`](reference/cc-exam-blueprint.md) | Tier 0 exam facts (minimal summary; anchor-stable headings) |
| [`reference/objective-matrix.json`](reference/objective-matrix.json) | Domain/objective registry + 2026-09 crosswalk stub + AI-security extension |
| [`reference/source-registry.json`](reference/source-registry.json) | Registered sources with tiers, freshness, and copyright notes |
| [`reference/source-policy.md`](reference/source-policy.md) | Source tiers + ISC2/transcript IP boundaries + support-span limits |
| [`notes/`](notes/README.md) | Cleaned domain notes (empty until PR-5; contract documented) |
| [`learner-state/`](learner-state/README.md) | Learner progress layer (reserved; separate from content by design) |
| [`spine/cc_spine/`](spine/cc_spine/__init__.py) | Stdlib-only package: scaffold validator, ingestion engine, freshness + IP guards, fact store, registry, notes lifecycle, CLI |
| [`spine/cc_spine/ingest.py`](spine/cc_spine/ingest.py) | Deterministic DOCX/text extraction + suggest-only correction engine + audit-trail note builder |
| [`spine/cc_spine/factstore.py`](spine/cc_spine/factstore.py) | Copy-adapted fact store: provenance resolvers, fingerprint drift, tombstones, bank eligibility, answer-key quarantine, deterministic `ground()` |
| [`spine/cc_spine/registry.py`](spine/cc_spine/registry.py) | CC registry over the objective matrix + source registry (tags/source_id validation) |
| [`spine/cc_spine/notes_lifecycle.py`](spine/cc_spine/notes_lifecycle.py) | Note review-state machine; only reviewed/promoted notes may ground cards |
| [`spine/cc_spine/cli.py`](spine/cc_spine/cli.py) | Runnable surface: `validate`, `validate-sources`, `check-ip`, `ingest`, `factstore` |
| [`spine/schemas/`](spine/schemas/fact-card.schema.json) | Contracts: fact card, bank item, objective matrix, correction dictionary |
| [`spine/ingest/correction-dictionary.json`](spine/ingest/correction-dictionary.json) | ASR-error corrections (suggest-only, confidence-guarded) |
| [`spine/facts/`](spine/facts/D1.json) | Fact store, one file per scope (empty in PR-1) |
| [`spine/banks/banks.json`](spine/banks/banks.json) | Bank manifest: eligibility, targets, holdouts, mock draw, readiness math |
| [`spine/gold/goldset.json`](spine/gold/goldset.json) | Gold set (empty until PR-8) |
| [`spine/tests/`](spine/tests/test_scaffold.py) | Scaffold gate (stdlib unittest) |

## Status

| Milestone | Status |
|---|---|
| PR-1 — governance spec + scaffold | done |
| PR-2 — ingestion engine + freshness/IP guards + CI | done |
| PR-3 — factstore + registry + notes lifecycle + retrieval-stability gates | done |
| PR-4 — 2026-09 outline + crosswalk + source-freshness ledger | done |
| PR-4.1 — official 2026 verification: two-lane evidence + 19 objectives + attestation guard | **this PR** |
| PR-3 — copy-adapt factstore + validators | planned |
| PR-4 — verified outline + 2026-09 crosswalk | planned |
| PR-5 — transcript ingestion (after explicit authorization) | planned |
| PR-6/7 — fact-card seeds (D4/D5, then D1–D3) | planned |
| PR-8 — quiz engine + first gold items (ship gate activates) | planned |
| PR-9+ — growth slices; mock exam, dashboard, journal, cram sheets | planned |

Full roadmap and gate-activation table: spec §15.

## Verify (PR-1, local)

```bash
cd cc-master-learning-center/spine
make ci          # scaffold gate + freshness guard + IP guard + tests + ingestion determinism
```

Or run the steps individually: `python3 -m cc_spine.scaffold_validate`,
`python3 -m cc_spine.cli validate-sources`, `python3 -m cc_spine.cli check-ip`,
`python3 -m cc_spine.cli factstore validate`, `python3 -m unittest discover -s tests`.
Stdlib only — no dependencies to install. CI (`.github/workflows/cc-spine.yml`) runs the
same steps, path-filtered to this directory.

## Relationship to osai-prep-studio

Same governance DNA, zero shared code paths: the fact-store machinery is **copy-adapted**
(spec §14), never path-imported, so nothing here can affect the frozen OSAI ship gates. This
project never touches the no-touch surfaces listed in spec §3.
