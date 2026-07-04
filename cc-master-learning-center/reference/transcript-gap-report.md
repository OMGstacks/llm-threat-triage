# Transcript Gap Report (PR-5)

What the four source transcripts do and do **not** cover, graded from an IP-safe
keyword-frequency scan (signal-term counts, never transcript text). This tells the roadmap
which objectives can seed fact cards from distilled transcript concepts and which must be
built from the blueprint + NIST Tier-0/1 sources instead.

Source: [`transcript-coverage-map.json`](transcript-coverage-map.json) ·
Audit: [`../spine/ingest/transcript-audit-summary.json`](../spine/ingest/transcript-audit-summary.json)

## Well covered (transcript can seed fact cards)

| Objective | Title | Primary source |
|---|---|---|
| 4.1 | Understand computer networking | Domain 4 (net signal 287) |
| 4.3 | Understand network security infrastructure | Domain 4 (infra 154, cloud 109) |
| 5.1 | Understand data security | Domain 5 (crypto 252, data 39) |
| 1.2 | Understand the risk management process | CC overview + How2Study |
| 1.1 / 1.3 / 1.4 | Info assurance, controls, ethics | CC overview |
| 2.1 | Understand business continuity | CC overview + How2Study |
| 3.1 / 3.2 | Physical + logical access controls | CC overview + Domain 4 |

## Thin — touched but needs blueprint/NIST reinforcement

| Objective | Title | Note |
|---|---|---|
| 4.2 | Network threats and attacks | Domain 4 touches rogue AP / evil twin / jamming only |
| 2.2 | Disaster recovery | Mentioned within BC, not developed |
| 5.3 | Best-practice security policies | Only incidental in CC overview |
| 5.4 | Security awareness training | Only via How2Study's study layer |

## Gaps — NOT a transcript strength (seed from blueprint + NIST)

| Objective | Title | Evidence |
|---|---|---|
| 2.3 | Understand incident response | IR signal 2–3 counts across all four docs |
| 5.2 | Understand system hardening | logging/monitoring/config signal ~1 in Domain 5 |

## Forward-looking gaps (2026-09 outline)

The transcripts predate the 2026 D5 expansion. Not covered anywhere and reserved for
blueprint/NIST-grounded authoring: logging & monitoring, event triage, threat actors, cyber
threat intelligence, threat frameworks (MITRE ATLAS / ATT&CK, Cyber Kill Chain, Diamond),
incident-response exercises, asset lifecycle / EOL-EOS, configuration/change management, and
security testing (vuln scanning, SAST/DAST, threat modeling). NIST SP 800-61r3 (IR) and
SP 800-88r2 (sanitization) are the Tier-1 anchors for this build-out.

## Consequence for the roadmap

- **PR-6 (D4/D5 seed facts):** ground D4 (4.1/4.3) and D5 (5.1) from distilled transcript
  concepts + the blueprint; these are the corpus's strongest areas.
- **Gap objectives (2.3, 5.2) + all 2026 D5 secops topics:** author from the blueprint and
  NIST Tier-0/1 sources, not the transcripts.
