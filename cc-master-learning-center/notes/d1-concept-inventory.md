---
source_doc_id: cc-overview
source_tier: 4
type: concept-inventory
status: draft
outline_version: "2025-10"
reviewed_by: null
distilled_from: CC Overview.docx (raw_committed:false; see ../spine/ingest/source-manifest.json)
ip_note: Original distilled learning objects. Glosses are written from domain knowledge, not transcript wording. No verbatim transcript content.
---

# Domain 1 — Security Principles Concept Inventory

> **Authoring-aid only.** This file is a candidate-selection tool for PR-7, not an
> authoritative fact source. Fact cards must be grounded on blueprint/NIST/official
> anchors, not on this inventory. Do not cite this file as a `source_id` in any fact card.

Compact, original fact-card candidates distilled from the CC Overview transcript
(graded `strong` for 1.1–1.4). PR-7 grounds these on the blueprint anchors.

## 1.1 — Security concepts of information assurance

| Concept | Type | Gloss |
|---|---|---|
| CIA triad | definition | Confidentiality, integrity, and availability are the three core information security goals. |
| Confidentiality | definition | Preventing unauthorized disclosure of information. |
| Integrity | definition | Ensuring information is accurate, complete, and unaltered. |
| Availability | definition | Ensuring systems and data are accessible to authorized users when needed. |
| Non-repudiation | definition | Inability to deny having sent or received a message; supported by digital signatures. |
| Authentication | definition | Verifying the identity of a user, process, or device before granting access. |
| Authorization | definition | Granting or denying access to resources after successful authentication. |
| Accounting (audit) | definition | Recording and reviewing subject activity to establish accountability. |
| AAA vs CIA | exam_trap | AAA (auth, authz, accounting) is an access-control framework; CIA is a security goals triad — do not conflate. |
| Privacy | concept | Protecting PII from unauthorized collection, use, or disclosure. |

## 1.2 — Risk management process

| Concept | Type | Gloss |
|---|---|---|
| Threat | definition | Any circumstance with the potential to harm organizational operations or assets. |
| Vulnerability | definition | A weakness that a threat can exploit. |
| Likelihood | concept | Probability a threat event will occur. |
| Impact | concept | Magnitude of harm if a threat event occurs. |
| Risk | concept | Likelihood × impact; the combined measure of threat and vulnerability. |
| Risk accept | concept | Acknowledge risk and take no action; acceptable when cost > benefit. |
| Risk avoid | concept | Eliminate the activity that causes the risk. |
| Risk transfer | concept | Shift financial impact via insurance or contract. |
| Risk mitigate | concept | Reduce likelihood or impact via controls. |
| Due care | definition | Doing what a prudent professional would do to protect assets. |
| Due diligence | definition | Ongoing investigation and verification that controls remain effective. |

## 1.3 — Security controls

| Concept | Type | Gloss |
|---|---|---|
| Technical controls | definition | Hardware/software safeguards: firewalls, encryption, ACLs, antivirus. |
| Administrative controls | definition | Policies, procedures, training, and background checks. |
| Physical controls | definition | Physical barriers: locks, guards, CCTV, fencing. |
| Preventive controls | definition | Block or reduce threats before they occur. |
| Detective controls | definition | Identify and log incidents; do not prevent but enable response. |
| Corrective controls | definition | Restore systems to normal after an incident. |
| Deterrent controls | definition | Discourage would-be attackers through visible presence or warning. |
| Compensating controls | definition | Alternative safeguard used when a primary control is not feasible. |

## 1.4 — ISC2 Code of Ethics

| Concept | Type | Gloss |
|---|---|---|
| ISC2 Code of Ethics | definition | Professional obligations governing ISC2 member conduct. |
| Canon 1 | definition | Protect society, the common good, public trust and confidence, and the infrastructure. |
| Canon 2 | definition | Act honorably, honestly, justly, responsibly, and legally. |
| Canon 3 | definition | Provide diligent and competent service to principals. |
| Canon 4 | definition | Advance and protect the profession. |
| Ethics canon order | exam_trap | Canon 1 (society) outranks Canon 3 (principals) — public good supersedes client interest. |

## Exam traps distilled

| Trap | Type | Gloss |
|---|---|---|
| Non-repudiation ≠ confidentiality | exam_trap | Non-repudiation provides proof of origin/receipt; it is not a confidentiality mechanism. |
| Risk transfer does not eliminate risk | exam_trap | Financial impact shifts; the underlying threat and vulnerability remain. |
| Detective ≠ corrective | exam_trap | Detective controls identify events; corrective controls fix them — they are different functions. |
