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

# Domain 2 — BC/DR/IR Concept Inventory

> **Authoring-aid only.** This file is a candidate-selection tool for PR-7, not an
> authoritative fact source. Fact cards must be grounded on blueprint/NIST/official
> anchors, not on this inventory. Do not cite this file as a `source_id` in any fact card.

Compact, original fact-card candidates distilled from the CC Overview transcript
(graded `strong` for 2.1). IR lifecycle is grounded on NIST SP 800-61r3.

## 2.1 — Business continuity

| Concept | Type | Gloss |
|---|---|---|
| BC vs DR | comparison | BC keeps the business operating during disruption; DR restores IT after a disaster. |
| BIA | definition | Business Impact Analysis: identifies critical functions and quantifies disruption impact. |
| MTD | definition | Maximum Tolerable Downtime: longest a function can be offline before causing unacceptable harm. |
| RTO | definition | Recovery Time Objective: target time to restore a function after disruption; must be ≤ MTD. |
| RPO | definition | Recovery Point Objective: maximum acceptable data loss measured in time. |
| MTD vs RTO | comparison | MTD is the hard limit; RTO is the target — RTO must always be less than or equal to MTD. |
| Hot site | definition | Fully configured, operational backup site; immediate failover. |
| Warm site | definition | Partially configured backup site; activation takes hours to days. |
| Cold site | definition | Space and power only; lowest cost, longest activation time. |
| Full backup | comparison | Copies all data; slowest to create, fastest to restore. |
| Incremental backup | comparison | Copies only changes since last backup of any type; fastest to create, slowest to restore. |
| Differential backup | comparison | Copies all changes since last full backup; middle ground for creation and restore time. |

## 2.3 — Incident response (NIST SP 800-61r3)

| Concept | Type | Gloss |
|---|---|---|
| IR Preparation phase | definition | Establish policy, team, tools, and training before incidents occur. |
| Detection and Analysis phase | definition | Identify, validate, and classify the incident; notify stakeholders. |
| Containment phase | definition | Limit damage; isolate affected systems; short- and long-term containment. |
| Eradication phase | definition | Remove root cause: malware, unauthorized accounts, exploited vulnerabilities. |
| Recovery phase | definition | Restore and validate systems; monitor for re-infection before returning to production. |
| Post-Incident Activity | definition | Lessons-learned meeting; update policies/controls; retain evidence; measure metrics. |
| IR lifecycle order | exam_trap | Preparation → Detection/Analysis → Containment → Eradication → Recovery → Post-Incident. |
