---
source_doc_id: domain-5
source_tier: 4
type: concept-inventory
status: draft
outline_version: "2025-10"
reviewed_by: null
distilled_from: Domain 5.docx (raw_committed:false; see ../spine/ingest/source-manifest.json)
ip_note: Original distilled learning objects. Glosses are written from domain knowledge, not transcript wording. No verbatim transcript content.
---

# Domain 5 — Data Security & Cryptography Concept Inventory

> **Authoring-aid only.** This file is a candidate-selection tool for PR-6/7, not an
> authoritative fact source. Fact cards must be grounded on blueprint/NIST/official
> anchors, not on this inventory. Do not cite this file as a `source_id` in any fact card.

Compact, original fact-card candidates distilled from the Domain 5 transcript (graded `strong`
for 5.1; a dedicated crypto + data-security source). PR-6 grounds these on the blueprint and
NIST SP 800-88r2 (sanitization) / FIPS 203–205 (post-quantum) anchors.

## 5.1 — Data security: handling and sanitization

| Concept | Type | Gloss |
|---|---|---|
| Data classification | definition | Assigning sensitivity labels that drive handling and protection. |
| Data retention | concept | Keep data only as long as required by policy or law, then dispose. |
| Data masking | definition | Replacing sensitive values with realistic but non-sensitive substitutes. |
| Tokenization | comparison | Swaps sensitive data for a non-sensitive token mapped in a secure vault. |
| Clear / Purge / Destroy | comparison | NIST SP 800-88 sanitization tiers by increasing assurance. |
| Degaussing | definition | Erasing magnetic media by disrupting its magnetic field. |
| Cross-cut shredding | definition | Physically destroying media into small fragments. |
| Overwriting | definition | Replacing stored data with new patterns so the original is unrecoverable. |

## 5.1 — Cryptography

| Concept | Type | Gloss |
|---|---|---|
| Symmetric encryption | definition | One shared secret key encrypts and decrypts; fast, key-distribution is the challenge. |
| Asymmetric encryption | comparison | Public/private key pair; encrypt with one, decrypt with the other. |
| Hybrid encryption | concept | Asymmetric key exchange establishes a symmetric session key. |
| Hashing | exam_trap | One-way fixed-length fingerprint for integrity; not encryption, cannot be reversed. |
| Digital signature | definition | Hash encrypted with a private key; gives integrity, authentication, non-repudiation. |
| Caesar cipher | definition | Classical substitution cipher shifting letters by a fixed amount. |
| Scytale | definition | Ancient transposition cipher using a rod of fixed diameter. |
| Crypto-agility | concept | Ability to inventory, replace, and validate algorithms as standards/threats change. |
| Post-quantum crypto | concept | Algorithms (FIPS 203–205) designed to resist future quantum attacks. |

## Exam traps distilled

| Trap | Type | Gloss |
|---|---|---|
| Hashing is not encryption | exam_trap | Hashing is one-way and provides integrity, not confidentiality. |
| Degauss vs delete | exam_trap | Deleting leaves data recoverable; degaussing/destroying does not. |
| Symmetric ≠ asymmetric key count | exam_trap | Symmetric shares one key; asymmetric uses a public/private pair. |
