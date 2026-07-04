---
source_doc_id: domain-4
source_tier: 4
type: concept-inventory
status: draft
outline_version: "2025-10"
reviewed_by: null
distilled_from: Domain 4.docx (raw_committed:false; see ../spine/ingest/source-manifest.json)
ip_note: Original distilled learning objects. Glosses are written from domain knowledge, not transcript wording. No verbatim transcript content.
---

# Domain 4 — Networking Concept Inventory

> **Authoring-aid only.** This file is a candidate-selection tool for PR-6/7, not an
> authoritative fact source. Fact cards must be grounded on blueprint/NIST/official
> anchors, not on this inventory. Do not cite this file as a `source_id` in any fact card.

Compact, original fact-card candidates distilled from the Domain 4 transcript's coverage
(graded `strong` for 4.1/4.3). Each gloss is exam-accurate and written fresh; PR-6 turns these
into provenance-backed fact cards grounded on the blueprint/NIST anchors, not this file.

## 4.1 — Computer networking

| Concept | Type | Gloss |
|---|---|---|
| OSI model | definition | Seven-layer reference model: Physical, Data Link, Network, Transport, Session, Presentation, Application. |
| TCP/IP model | definition | Practical four-layer internet model: Link, Internet, Transport, Application. |
| TCP vs UDP | comparison | TCP is connection-oriented and reliable; UDP is connectionless and fast. |
| IPv4 vs IPv6 | comparison | IPv4 is 32-bit; IPv6 is 128-bit with a vastly larger address space. |
| MAC address | definition | 48-bit hardware address identifying a network interface at Layer 2. |
| ARP | definition | Address Resolution Protocol maps an IP address to a MAC address on a LAN. |
| ICMP | definition | Internet Control Message Protocol carries diagnostics and errors (ping, unreachable). |
| DHCP | definition | Dynamically assigns IP configuration to hosts. |
| DNS | numeric_fact | Resolves names to IP addresses; runs on port 53. |
| HTTP / HTTPS | numeric_fact | Web traffic on ports 80 (HTTP) and 443 (HTTPS/TLS). |
| SSH | numeric_fact | Encrypted remote administration on TCP port 22. |
| PAN / LAN / MAN / WAN | comparison | Network scopes by size: personal, local, metropolitan, wide-area. |

## 4.2 — Network threats and attacks

| Concept | Type | Gloss |
|---|---|---|
| Rogue access point | definition | Unauthorized AP attached to a network, bypassing controls. |
| Evil twin | definition | Malicious AP impersonating a legitimate SSID to capture traffic. |
| Bluejacking vs bluesnarfing | comparison | Bluejacking sends unsolicited messages; bluesnarfing steals data over Bluetooth. |
| On-path (MITM) | definition | Attacker relays/alters traffic between two parties who believe they talk directly. |

## 4.3 — Network security infrastructure

| Concept | Type | Gloss |
|---|---|---|
| Firewall | definition | Enforces an allow/deny policy on traffic between zones. |
| IDS vs IPS | comparison | IDS detects and alerts; IPS detects and blocks inline. |
| DMZ | definition | Screened subnet exposing public services while shielding the internal network. |
| VLAN | definition | Logical Layer-2 segmentation of one physical switch into isolated broadcast domains. |
| VPN | definition | Encrypted tunnel carrying private traffic across an untrusted network. |
| NAC | definition | Enforces posture/identity checks before granting network access. |
| Zero Trust | concept | Never trust, always verify; no implicit trust by network location. |
| IaaS / PaaS / SaaS | comparison | Cloud service models trading control for managed responsibility. |
| Shared responsibility | concept | Cloud security duties split between provider and customer by service model. |
