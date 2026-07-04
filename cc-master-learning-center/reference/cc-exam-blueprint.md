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

### CIA Triad and Information Assurance

Confidence: `seeded-pending-review` (Tier 0). Source: `isc2.cc-outline.2025-10`.

| Concept | Definition |
|---|---|
| Confidentiality | Preventing unauthorized disclosure of information |
| Integrity | Ensuring information is accurate, complete, and unaltered |
| Availability | Ensuring information and systems are accessible when needed |
| Non-repudiation | Inability to deny having taken an action; supported by digital signatures and audit logs |
| Authentication | Verifying the identity of a user, process, or device |
| Authorization | Granting or denying permissions to authenticated subjects |
| Accounting (audit) | Recording and tracking subject activity for accountability and forensic review |
| Privacy | Protecting personally identifiable information from unauthorized collection or use |

### Risk Management Fundamentals

Confidence: `seeded-pending-review` (Tier 0). Source: `isc2.cc-outline.2025-10`.

| Term | Definition |
|---|---|
| Threat | Any circumstance or event with the potential to adversely impact organizational operations |
| Vulnerability | A weakness in a system, process, or control that could be exploited by a threat |
| Likelihood | Probability that a threat will exploit a vulnerability |
| Impact | Magnitude of harm that would result from a threat exploiting a vulnerability |
| Risk | The combination of the likelihood of a threat event and its impact |
| Risk treatment options | Accept, avoid, transfer (share), mitigate (reduce) |
| Due care | Taking reasonable steps to protect assets; doing what a prudent person would do |
| Due diligence | Ongoing investigation and monitoring to ensure controls remain effective |

### Security Controls

Confidence: `seeded-pending-review` (Tier 0). Source: `isc2.cc-outline.2025-10`.

| Category / Function | Examples |
|---|---|
| Technical controls | Firewalls, encryption, access control lists, antivirus |
| Administrative controls | Policies, procedures, training, background checks |
| Physical controls | Locks, guards, CCTV, fencing, bollards |
| Preventive controls | Block threats before they occur (e.g., firewall, lock) |
| Detective controls | Identify and record threat events (e.g., IDS, audit log, CCTV) |
| Corrective controls | Restore systems after an incident (e.g., backup restore, patch) |
| Deterrent controls | Discourage attackers (e.g., warning signs, visible CCTV) |
| Compensating controls | Alternative control when a primary control is not feasible |

### ISC2 Code of Ethics

Confidence: `seeded-pending-review` (Tier 0). Source: `isc2.cc-outline.2025-10`.

| Principle | Summary |
|---|---|
| Code of Ethics Preamble | Safety of the commonwealth, duty to principals, and the profession |
| Canon 1 | Protect society, common good, public trust and confidence, and the infrastructure |
| Canon 2 | Act honorably, honestly, justly, responsibly, and legally |
| Canon 3 | Provide diligent and competent service to principals |
| Canon 4 | Advance and protect the profession |
| Due care | Taking reasonable protective steps; doing what a prudent professional would do |
| Due diligence | Ongoing investigation and monitoring to verify controls remain effective |

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

### Business Continuity and Disaster Recovery

Confidence: `seeded-pending-review` (Tier 0). Source: `isc2.cc-outline.2025-10`.

| Term | Definition |
|---|---|
| Business Continuity (BC) | Keeping the organization operational during and after a disruption |
| Disaster Recovery (DR) | Restoring IT systems and data after a disaster |
| Business Impact Analysis (BIA) | Identifying critical functions and quantifying the effect of their disruption |
| Maximum Tolerable Downtime (MTD) | Maximum time a business function can be offline before unacceptable harm |
| Recovery Time Objective (RTO) | Target time to restore a function after a disruption |
| Recovery Point Objective (RPO) | Maximum acceptable data loss measured in time |
| Hot site | Fully operational backup site; immediate failover capability |
| Warm site | Partially configured backup site; activation takes hours to days |
| Cold site | Space and power only; no pre-configured equipment; lowest cost, longest activation |
| Full backup | Complete copy of all data; slowest to create, fastest to restore |
| Incremental backup | Copies data changed since the last backup of any type; fastest to create, slowest restore |
| Differential backup | Copies all data changed since the last full backup; middle cost and restore time |

### Incident Response Lifecycle

Confidence: `seeded-pending-review` (Tier 0). Source: `isc2.cc-outline.2025-10`.

The ISC2 CC incident response lifecycle has four phases: Preparation, Detection and Analysis,
Containment/Eradication/Recovery, and Post-Incident Activity. Containment, eradication, and
recovery form one combined phase, not three separate ones.

| Phase | Key Activities |
|---|---|
| 1. Preparation | Establish IR capability: policy, team, tools, training, communication plan |
| 2. Detection and Analysis | Identify and validate incidents; classify severity; notify stakeholders |
| 3. Containment, Eradication & Recovery | Limit damage; short-term and long-term containment strategies. Remove root cause (malware, unauthorized accounts, vulnerabilities). Restore and validate affected systems; return to normal operations |
| 4. Post-Incident Activity | Lessons-learned review; evidence retention; metrics collection |

Tier 1 note: NIST SP 800-61r3 reframes incident response around the CSF 2.0 functions (Govern,
Identify, Protect, Detect, Respond, Recover) rather than a phase lifecycle (`nist.sp800-61r3`).

## Domain 3: Access Controls Concepts

Weight: 22%. Confidence: `seeded-pending-review`.

Objectives: 3.1 physical access controls; 3.2 logical access controls.

High-yield scope (paraphrased): physical controls (badges, guards, CCTV, locks, mantraps);
logical access models (DAC, MAC, RBAC); least privilege; need to know; separation of duties;
privileged access management; account lifecycle basics (provision, review, deprovision).

### Physical Access Controls

Confidence: `seeded-pending-review` (Tier 0). Source: `isc2.cc-outline.2025-10`.

| Control | Description |
|---|---|
| Badges / access cards | Authenticate identity at controlled entry points |
| Guards | Human security personnel providing deterrence, presence, and response capability |
| CCTV | Surveillance cameras; primary detective control for physical security |
| Locks (mechanical / electronic) | Prevent unauthorized physical access to facilities and equipment |
| Mantrap (airlock) | Two-door entry with only one door open at a time; prevents tailgating |
| Fencing and bollards | Perimeter barriers against pedestrian and vehicle intrusion |
| Lighting | Deters unauthorized activity; supports CCTV effectiveness |
| Visitor logs | Record visitor identity, purpose, escort, and entry/exit time |

### Logical Access Controls

Confidence: `seeded-pending-review` (Tier 0). Source: `isc2.cc-outline.2025-10`.

| Model / Concept | Description |
|---|---|
| DAC (Discretionary Access Control) | Resource owner controls who may access the resource |
| MAC (Mandatory Access Control) | System enforces access by comparing classification labels; owner cannot override |
| RBAC (Role-Based Access Control) | Permissions tied to roles; users assigned to roles |
| Least privilege | Grant only the minimum permissions needed to perform a function |
| Need to know | Access granted only for information required for a specific task |
| Separation of duties | No single person has end-to-end control of a sensitive process |
| Privileged Access Management (PAM) | Controls, monitors, and audits accounts with elevated rights |
| Account lifecycle | Provision, periodic review, and timely deprovision of access |

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

### Cloud Computing (NIST SP 800-145)

Confidence: `confirmed` (Tier 1). Source: `nist.sp800-145`.

| Aspect | Detail |
|---|---|
| 5 essential characteristics | on-demand self-service, broad network access, resource pooling, rapid elasticity, measured service |
| Service models (3) | IaaS (infrastructure), PaaS (platform), SaaS (software as a service) |
| Deployment models (4) | private cloud, community cloud, public cloud, hybrid cloud |
| Shared responsibility | cloud provider secures underlying infrastructure; customer secures what they deploy and configure |

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

### Sanitization Methods (NIST SP 800-88r2)

Confidence: `confirmed` (Tier 1). Source: `nist.sp800-88r2`.

| Method | Description |
|---|---|
| Definition | Making access to target data infeasible for a given level of effort |
| Clear | Logical techniques (e.g., overwrite); effective against software-based recovery |
| Purge | Physical or cryptographic techniques (e.g., degauss, cryptographic erase); effective against laboratory attacks |
| Destroy | Physical destruction (incinerate, disintegrate, shred, pulverize, melt); highest assurance tier |

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
effective 2026-09-01 with reshaped domains. The crosswalk lives **only** in
`objective-matrix.json` (`outlines.2026-09.crosswalk_map`, completed in PR-4), never on
individual fact cards, so there is a single source of truth. If the learner's exam date moves
to 2026-09-01 or later, the matrix flips primary target and the crosswalk drives re-mapping.

## 2026-09 Outline (Upcoming)

Confidence: `official-upcoming-verified` — verified from the official ISC2 2026 CC outline PDF
via reviewer attestation ([`verification-evidence.json`](verification-evidence.json)). This
environment could not fetch ISC2 directly (HTTP 403 on 2026-07-04); the two-lane evidence
model records the operator-blocked fetch and the reviewer's official attestation separately
(governance spec §17).

| Domain | Title | Weight |
|---|---|---:|
| D1 | Security Principles | 24% |
| D2 | Security Governance | 17.3% |
| D3 | Identity and Access Management (IAM) Concepts | 20% |
| D4 | Networking and Cloud Security Concepts | 21.3% |
| D5 | Security Operations and Incident Response | 17.3% |

Official 2026 objectives (19, from the ISC2 PDF; minimal titles only). Documented for the
crosswalk and future flip — **not yet valid for fact-card tagging** (cards stay on the 2025-10
outline until a deliberate primary-target flip):

| Domain | Objectives |
|---|---|
| D1 | 1.1 Understand cybersecurity concepts · 1.2 Understand risk management concepts · 1.3 Understand governance concepts · 1.4 Understand cybersecurity controls · 1.5 Maintain professional and ethical conduct |
| D2 | 2.1 Plan Governance, Risk, and Compliance (GRC) · 2.2 Understand redundancy · 2.3 Understand security awareness · 2.4 Measure cybersecurity effectiveness |
| D3 | 3.1 Understand identity life cycle management · 3.2 Understand logical access controls |
| D4 | 4.1 Understand network security · 4.2 Understand network security architecture · 4.3 Understand cloud security |
| D5 | 5.1 Understand data security · 5.2 Understand security operations · 5.3 Understand Incident Response (IR) · 5.4 Understand asset protection · 5.5 Understand security testing |

Crosswalk summary (current objective → 2026 domain; normative map in the matrix):

| Current | → 2026 | Rationale |
|---|---|---|
| 1.1, 1.3, 1.4 | D1 | Information assurance, controls, ethics stay Security Principles |
| 1.2 | D1 + D2 | Risk process splits across principles and GRC governance |
| 1.5, 5.3, 5.4 | D2 | Governance processes, policies, awareness → Security Governance |
| 2.1, 2.2 | D2 | BC/DR/redundancy fold into Security Governance |
| 2.3 | D5 | Incident response joins Security Operations and IR |
| 3.1, 3.2 | D3 | Physical + logical access controls → IAM Concepts |
| 4.1, 4.3 | D4 | Networking + infrastructure (incl. cloud) → Networking and Cloud Security |
| 4.2 | D4 + D5 | Network threats stay D4; threat actors/CTI/frameworks move to D5 |
| 5.1, 5.2 | D5 | Data security and hardening/config management stay operations |

## Confidence Ledger

| Section | Confidence | Re-review trigger |
|---|---|---|
| Exam Facts | confirmed | Outline change notice or 2026-09-01 |
| Domain 1–5 scope summaries | seeded-pending-review | Official-source review (isc2.org 403 to this environment on 2026-07-04 — deferred) |
| Crypto-agility note | confirmed | New NIST PQC guidance |
| AI Security Integration | seeded-pending-review | Official-source review (deferred as above) |
| 2026-09 outline + 19 objectives + crosswalk | official-upcoming-verified (ISC2 PDF, reviewer attestation) | Hard stop at 2026-09-01 (source-registry next_review); re-attest if PDF changes |
