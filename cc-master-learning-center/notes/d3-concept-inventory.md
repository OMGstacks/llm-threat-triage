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

# Domain 3 — Access Controls Concept Inventory

> **Authoring-aid only.** This file is a candidate-selection tool for PR-7, not an
> authoritative fact source. Fact cards must be grounded on blueprint/NIST/official
> anchors, not on this inventory. Do not cite this file as a `source_id` in any fact card.

Compact, original fact-card candidates distilled from the CC Overview transcript
(graded `strong` for 3.1 and 3.2). PR-7 grounds these on the blueprint anchors.

## 3.1 — Physical access controls

| Concept | Type | Gloss |
|---|---|---|
| Badges / access cards | definition | Tokens used to authenticate identity at controlled entry points. |
| Guards | definition | Human security personnel providing deterrence, presence, and incident response. |
| CCTV | definition | Video surveillance cameras; a detective physical control. |
| Locks | definition | Mechanical or electronic barriers preventing unauthorized physical access. |
| Mantrap (airlock) | definition | Two-door entry vestibule; only one door open at a time, preventing tailgating. |
| Fencing | definition | Perimeter barrier deterring or delaying unauthorized entry. |
| Bollards | definition | Sturdy posts blocking vehicle intrusion into pedestrian or sensitive areas. |
| Lighting | concept | Reduces concealment opportunities; deters unauthorized activity; enhances CCTV effectiveness. |
| Tailgating | exam_trap | Following an authorized person through a door without independent authentication; countered by mantraps and guard vigilance. |

## 3.2 — Logical access controls

| Concept | Type | Gloss |
|---|---|---|
| DAC | definition | Discretionary Access Control: resource owner grants/revokes access at their discretion. |
| MAC | definition | Mandatory Access Control: system enforces access by comparing classification labels; owner cannot override. |
| RBAC | definition | Role-Based Access Control: permissions assigned to roles; users inherit permissions by role membership. |
| Least privilege | concept | Grant only the minimum access needed to perform a task; limits blast radius of compromise. |
| Need to know | concept | Access granted only for information required for a specific, authorized task. |
| Separation of duties | concept | Divide critical tasks so no single person can complete a sensitive process alone. |
| PAM | definition | Privileged Access Management: controls, monitors, and audits elevated-rights accounts. |
| Account lifecycle | concept | Provision → periodic review → timely deprovision; stale accounts are a common attack vector. |
| DAC vs MAC | comparison | DAC is flexible and owner-controlled; MAC is rigid and system-enforced with classification labels. |
| Least privilege vs need-to-know | exam_trap | Least privilege concerns the scope of permissions; need-to-know concerns the information accessed — related but distinct. |
