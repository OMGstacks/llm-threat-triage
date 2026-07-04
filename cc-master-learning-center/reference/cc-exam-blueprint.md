# ISC2 Certified in Cybersecurity (CC) — Exam Blueprint (Reference)

```yaml
source_name: ISC2 Certified in Cybersecurity Exam Outline
source_url: https://www.isc2.org/certifications/cc/cc-certification-exam-outline
source_id: isc2.cc-outline.2025-10
retrieved_at: 2026-07-04
effective_date: 2025-10-01
superseded_by_notice: A new CC exam outline becomes effective 2026-09-01
confidence: official-current
copyright_note: Minimal summary; see official source. ISC2 site contents are ISC2 property.
```

This file is a Tier 0 reference (see [`source-policy.md`](source-policy.md) and
[`source-registry.json`](source-registry.json)). It is a **minimal summary** of official exam
facts, written so that fact cards can ground on its heading anchors. Heading text is
**anchor-stable**: renaming a heading is a breaking change that triggers card drift detection
by design. Per-section confidence labels: `confirmed` (verified against the official source),
`seeded-pending-review` (seeded from program notes; needs official-source review).

## Exam Facts

Confidence: `confirmed`.

| Fact | Value |
|---|---|
| Certification | ISC2 Certified in Cybersecurity (CC) |
| Delivery | CAT (computerized adaptive testing) |
| Duration | 2 hours (120 minutes) |
| Items | 100–125 |
| Item formats | Multiple-choice and advanced innovative items |
| Passing grade | 700 out of 1000 (scaled) |
| Current outline effective | 2025-10-01 |
| Next outline effective | 2026-09-01 |

Domain weights (current outline):

| Domain | Title | Weight |
|---|---|---:|
| D1 | Security Principles | 26% |
| D2 | Business Continuity (BC), Disaster Recovery (DR) & Incident Response Concepts | 10% |
| D3 | Access Controls Concepts | 22% |
| D4 | Network Security | 24% |
| D5 | Security Operations | 18% |

## Domain 1: Security Principles

Weight: 26%. Confidence: `seeded-pending-review`.

Objectives: 1.1 security concepts of information assurance; 1.2 risk management process;
1.3 security controls; 1.4 ISC2 Code of Ethics; 1.5 governance processes.

High-yield scope (paraphrased): the CIA triad (confidentiality, integrity, availability);
authentication, authorization, and accounting; non-repudiation; privacy fundamentals; risk
terminology (threat, vulnerability, likelihood, impact) and risk treatment; control categories
(technical, administrative, physical) and functions (preventive, detective, corrective,
deterrent, compensating); policies, standards, procedures, and regulations; professional
ethics, due care, and due diligence.

## Domain 2: Business Continuity, Disaster Recovery and Incident Response Concepts

Weight: 10%. Confidence: `seeded-pending-review`.

Objectives: 2.1 business continuity; 2.2 disaster recovery; 2.3 incident response.

High-yield scope (paraphrased): the purpose of BC (keep the business operating during
disruption) versus DR (restore IT after disruption); business impact analysis and the
MTD/RTO/RPO family; DR site types (hot, warm, cold); backup strategies (full, incremental,
differential); the incident response lifecycle from preparation through detection and
analysis, containment, eradication, recovery, and lessons learned. Tier 1 enrichment:
NIST SP 800-61 Rev. 3 aligns incident response with cybersecurity risk management and the
CSF 2.0 functions (`nist.sp800-61r3` in the source registry).

## Domain 3: Access Controls Concepts

Weight: 22%. Confidence: `seeded-pending-review`.

Objectives: 3.1 physical access controls; 3.2 logical access controls.

High-yield scope (paraphrased): physical controls (badges, guards, CCTV, locks, mantraps);
logical access models (DAC, MAC, RBAC); least privilege; need to know; separation of duties;
privileged access management; account lifecycle basics (provision, review, deprovision).

## Domain 4: Network Security

Weight: 24%. Confidence: `seeded-pending-review`.

Objectives: 4.1 computer networking; 4.2 network threats and attacks; 4.3 network security
infrastructure.

High-yield scope (paraphrased): OSI and TCP/IP models; IPv4/IPv6 addressing; TCP vs UDP;
common ports and protocols; network device roles (switch, router, firewall, IDS/IPS, proxy);
network threats (DoS/DDoS, man-in-the-middle, spoofing, wireless attacks); security
architecture (DMZ, VLAN, segmentation, VPN, NAC, defense in depth, Zero Trust); cloud
fundamentals — service models (IaaS/PaaS/SaaS), deployment models, shared responsibility.
Tier 1 enrichment: NIST SP 800-145 defines cloud computing's essential characteristics,
service models, and deployment models (`nist.sp800-145` in the source registry).

## Domain 5: Security Operations

Weight: 18%. Confidence: `seeded-pending-review`.

Objectives: 5.1 data security; 5.2 system hardening; 5.3 best practice security policies;
5.4 security awareness training.

High-yield scope (paraphrased): data handling lifecycle (classification, labeling, retention,
destruction); encryption basics (symmetric, asymmetric, hashing); media sanitization —
Tier 1 enrichment: NIST SP 800-88 Rev. 2 defines sanitization as making access to target data
infeasible for a given level of effort (`nist.sp800-88r2`); configuration management and
patching; logging and monitoring fundamentals; security policies (AUP, BYOD, change
management, privacy); social engineering awareness and password protection.

### Crypto-agility enrichment note

Confidence: `confirmed` (Tier 1). Crypto-agility is the ability to inventory, replace, test,
and validate cryptographic algorithms as standards and threats change. It is the practical
bridge between CC-level crypto basics and post-quantum migration: NIST approved FIPS 203
(ML-KEM key encapsulation) and FIPS 204/205 (digital signatures) as quantum-resistant
standards (`nist.pqc.fips-203-204-205` in the source registry).

## AI Security Integration (Current Outline)

Confidence: `seeded-pending-review`.

ISC2 states that foundational AI concepts are integrated across all five current CC domains.
Tracked in the objective matrix as the `global.ai-security` extension (volatility: emerging),
covering: AI impact on the CIA triad; AI governance, risk, and compliance; AI service
accounts; AI-assisted IDS/SIEM and alert fatigue; model poisoning; model drift; data leakage
through public AI tools.

## 2026-09 Outline Crosswalk Policy

Confidence: `confirmed` (policy), `seeded-pending-review` (2026 details).

The primary study target is the **current (2025-10) outline**. A new outline becomes
effective 2026-09-01 with reshaped domains (approximate: Security Principles 24%; Security
Governance 17.3%; IAM Concepts 20%; Networking and Cloud Security Concepts 21.3%; Security
Operations and Incident Response 17.3% — pending verification). The crosswalk lives **only**
in `objective-matrix.json` (`outlines.2026-09.crosswalk_map`, populated in PR-4), never on
individual fact cards, so there is a single source of truth. If the learner's exam date moves
to 2026-09-01 or later, the matrix flips primary target and the crosswalk drives re-mapping.

## Confidence Ledger

| Section | Confidence | Re-review trigger |
|---|---|---|
| Exam Facts | confirmed | Outline change notice or 2026-09-01 |
| Domain 1–5 scope summaries | seeded-pending-review | PR-4 official-source review |
| Crypto-agility note | confirmed | New NIST PQC guidance |
| AI Security Integration | seeded-pending-review | PR-4 official-source review |
| 2026-09 crosswalk details | seeded-pending-review | PR-4 official-source review |
