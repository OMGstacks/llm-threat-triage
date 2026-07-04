# Reports — persisted acceptance evidence

This directory holds the **evidence trail** for content-growth slices. A slice is not accepted on
the strength of a chat transcript; it is accepted on the strength of a report committed here that
anyone can re-derive from the source files.

## Contract

Every content-growth slice (PR-6, PR-7, PR-9+) lands a persisted acceptance report before the next
slice starts. At minimum:

1. **Distribution report** — final card counts by domain / objective / claim_type / source_tier,
   bank-eligibility coverage, and a PR-readiness verdict. Numbers are derived from the committed
   card files, not hand-entered.
2. **Adversarial review report** — the semantic-review method, confirmed defects and fixes, the
   areas that came back clean, and any process findings.

## Rules recorded here (see governance spec §16.0)

- **Slice size:** 40–75 items per growth slice; a larger slice needs approval *before*
  implementation and a documented exception in the distribution report.
- **Review order:** no content-growth commit until its adversarial review completes.

## Index

| Report | Slice | Summary |
|---|---|---|
| [`pr7-fact-card-distribution.md`](pr7-fact-card-distribution.md) | PR-6 + PR-7 | 149 cards across 5 domains; 90-card slice-size exception documented |
| [`pr7-adversarial-review.md`](pr7-adversarial-review.md) | PR-7 | 2 defects + 2 near-duplicates fixed; misconception-registry seeds for PR-8 |
