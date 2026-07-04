# Cleaned Domain Notes — Contract

This directory holds **cleaned, reviewed domain notes** (`D1.md` … `D5.md`, plus optional
`global.md` for exam strategy). It is empty in PR-1 by design: transcripts are not checked
into this repository and are not authorized for repo ingestion in PR-1. Real transcript
extraction occurs in a later PR (PR-5) after the user explicitly supplies/approves source
files for repository processing.

## Front-matter contract

Every note produced by the ingestion pipeline must begin with a front-matter block:

```yaml
source_doc_id: local identifier of the raw source (never the raw file itself)
source_tier: 3            # raw transcript input
dictionary_version: correction-dictionary.json version used
corrections_applied:      # audit trail — every applied correction, with location
  - {wrong: "hedging", right: "hashing", paragraph: 42}
corrections_flagged:      # [VERIFY] items awaiting human review
reviewed_by: reviewer sign-off (required before status: reviewed)
status: draft | reviewed | promoted | rejected | deprecated
outline_version: "2025-10"
```

## Review-state lifecycle (enforced by `cc_spine.notes_lifecycle` from PR-3)

| From | Allowed transitions |
|---|---|
| `draft` | `reviewed`, `rejected` |
| `reviewed` | `promoted`, `deprecated`, `draft` (manual edit → re-review) |
| `promoted` | `deprecated` |
| `rejected` | — (terminal) |
| `deprecated` | — (terminal) |

**Only `reviewed` or `promoted` notes may ground fact cards.** The factstore enforces this
from PR-3: a card whose source cites a note in any other state — or with a missing/unknown
status — fails validation (fail-closed). Full pipeline-wide enforcement lands in PR-5.
Published (reviewed/promoted) notes are also subject to the transcript span limit via
`cc_spine.cli check-ip`.

## Anchor stability

Fact cards ground on this file's heading anchors (`notes/D4.md#common-ports-and-protocols`).
**Renaming a heading is a breaking change**: it invalidates the `source_fingerprint` of every
card citing that anchor, and the factstore drift detector flags it — by design. Add new
headings freely; rename existing ones only with a deliberate card-migration pass.

## IP rules (see [`../reference/source-policy.md`](../reference/source-policy.md))

- Paraphrase; do not reproduce long verbatim transcript passages.
- Support spans quoted from transcripts: ≤ 25 words unless explicitly authorized.
- No full practice questions or answer keys from any source.
- Raw-source fingerprints and local source IDs stay separate from published content.

## Determinism

The ingestion pipeline is deterministic: the same transcript plus the same dictionary
version must produce a byte-identical note. Manual edits after generation flip the note to
`status: draft` until re-reviewed.
