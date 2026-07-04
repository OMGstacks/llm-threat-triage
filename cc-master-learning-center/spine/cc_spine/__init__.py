"""CC Master Learning Center spine.

Standard-library-only package (Python >= 3.10) for the governed CC exam-prep
content system. The fact-store machinery is copy-adapted from
``osai-prep-studio/spine/osai_spine`` rather than path-imported: the OSAI
factstore hard-codes OSAI claim types, banks, eligibility, flag regexes, and
registry checks that back a frozen ship gate, so this package defines its own
domain tables while keeping the mechanical helpers (fingerprinting, JSON-path
and markdown-anchor resolvers, loader, freeze) verbatim. See
``00-governance-spec.md`` section 14 for the decision record and parity
checklist.

PR-1 ships only the scaffold validator. PR-2 adds the deterministic ingestion
engine (``ingest``), the source-registry freshness guard (``sources``), the
IP-boundary support-span guard (``ipboundary``), and the CLI (``cli``). PR-3
adds the copy-adapted fact store (``factstore``), the CC registry over the
objective matrix and source registry (``registry``), and the note review-state
lifecycle (``notes_lifecycle``). PR-4 completes the 2026-09 outline + crosswalk
in the objective matrix and adds the source-freshness ledger (``next_review``).
PR-4.1 adds the two-lane verification evidence ledger, the official 19-objective
2026 set, and the attestation guard (``sources`` + scaffold evidence check).
PR-5 ingests the transcripts by semantic distillation: a source manifest
(raw_committed:false), an IP-safe correction audit, objective coverage/gap maps,
compact original concept inventories, and the no_verbatim_bulk_reproduction
guard (``ipboundary.scan_verbatim``).
PR-5.1 hardens the no-verbatim guard against table-cell bypass (per-cell/row word
caps), expands the raw-file scan to repo root, anonymises the manifest's
``authorized_by`` field, adds ``grading_policy`` to the coverage map, documents
concept inventories as authoring aids, and tracks flagged-but-unresolved
corrections.
PR-6 seeds the first real fact cards: 59 cards across D4 objectives 4.1/4.3 and D5
objective 5.1, grounded on tier-0 blueprint anchors (isc2.cc-outline.2025-10) and
tier-1 NIST anchors (nist.sp800-145, nist.sp800-88r2, nist.pqc.fips-203-204-205).
No bank items, no holdout, no mnemonic cards. Scaffold validator updated to allow
non-empty fact arrays.
PR-7 completes fact-card seeding across the remaining domains: 90 cards over D1
(1.1-1.4), D2 (2.1-2.3), and D3 (3.1-3.2), grounded on new tier-0 blueprint anchors
(the incident-response lifecycle is taught as the ISC2 CC four-phase model, with
NIST SP 800-61r3's CSF-2.0 reframing kept as a tier-1 note). An adversarial content
review flagged a six-vs-four phase error and two near-duplicate cards, both fixed.
Fact store now holds 149 validated cards; all five domains have seed coverage.
PR-7.1 persists the slice acceptance evidence under ``reports/`` (a data-derived
distribution report + the adversarial-review record) and records two content-slice
rules in the governance spec: 40-75 items per growth slice, and no content commit
until its adversarial review completes. No cards changed.
"""

__version__ = "0.2.1"
