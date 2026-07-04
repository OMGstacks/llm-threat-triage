# PR-7 Adversarial Content Review

**Scope:** the 92 D1/D2/D3 fact cards authored in PR-7.
**Method:** multi-agent adversarial review (semantic layer), run *in addition to* the deterministic
validators. Deterministic gates prove a card is *well-formed and grounded*; they cannot prove a
claim is *factually correct for the exam*. This review closes that gap.
**Outcome:** 2 confirmed defects fixed + 2 near-duplicates removed, in commit `2784802`.

---

## 1. Why a semantic review at all

The deterministic pipeline (schema, eligibility, fingerprint drift, IP-span, no-verbatim,
notes-lifecycle) is necessary but not sufficient. A card can pass every structural gate and still
teach a **wrong fact** — the support span resolves, the fingerprint matches, the claim type is
eligible, yet the claim itself is false. For an exam-prep product, a confidently-wrong card is the
worst possible output: it trains the misconception. The semantic review is the gate that catches
that class of defect before it can reach the quiz layer.

## 2. Method

The review ran as a 3-phase multi-agent workflow over the exported card set:

| Phase | Agents | Job |
|---|---|---|
| Accuracy | 3 (one per domain) | Factual accuracy, claim↔support alignment, exam-trap correctness, precision |
| Near-duplicate | 3 (one per domain) | Redundant stems within a domain/objective (the "no near-dup" gate) |
| Verify | 1 per candidate finding | **Adversarially refute** each accuracy finding; default to *not-a-defect* unless the error is real and would mislead a candidate |

Each accuracy finding was independently re-examined by a skeptic agent instructed to *refute*, not
confirm — so surviving findings are the ones that withstood an attempt to dismiss them. Candidate
findings: 3. Confirmed after adversarial verification: 2.

## 3. Confirmed defects (fixed)

### 3.1 — BLOCKER · D2.23-ir-lifecycle · incident-response phase count

**Defect.** The card claimed the NIST IR lifecycle has **six phases** (Containment, Eradication,
and Recovery split into three). The tested ISC2 CC / NIST model has **four phases**, with
*Containment, Eradication & Recovery* as one combined phase. "How many phases?" is a high-frequency
exam item keyed to **four** — a learner studying this card would have answered six and lost the
point. Secondary error: the section was attributed to **NIST SP 800-61r3**, which reframes incident
response around the CSF 2.0 functions (Govern/Identify/Protect/Detect/Respond/Recover) and no longer
defines a phase lifecycle. The four-phase model is historically SP 800-61r2 (now withdrawn).

**Fix.** Rewrote the blueprint `Incident Response Lifecycle` anchor to the four-phase model;
re-grounded all 8 D2.23 cards on the tier-0 ISC2 blueprint (`isc2.cc-outline.2025-10`, tier 0),
keeping r3's CSF-2.0 reframing as an explicit tier-1 note; reworded the containment/eradication/
recovery cards as *steps within* the combined phase rather than standalone phases; corrected the
six-phase line in `d2-concept-inventory.md`.

### 3.2 — MAJOR · D1.12-threat-vs-vuln · threat defined as "external"

**Defect.** The card asserted "a threat is an **external** circumstance or actor." Insiders
(malicious/negligent employees, contractors) are threats in ISC2 CC and are directly tested; the
"external threat / internal vulnerability" split is a heuristic, not the ISC2 definition. It also
contradicted sibling card `D1.12-threat`, which correctly says threats can be "natural, human, or
environmental."

**Fix.** Reworded to "a threat is any circumstance or actor (**internal or external**) that may
cause harm," removing the absolute qualifier and resolving the intra-deck contradiction.

## 4. Near-duplicates removed

| Pair | Verdict | Action |
|---|---|---|
| `D1.12-due-care` ↔ `D1.14-due-care` | near-duplicate | removed the 1.4 copy |
| `D1.12-due-diligence` ↔ `D1.14-due-diligence` | near-duplicate | removed the 1.4 copy |

Both terms were defined near-identically under risk management (1.2) and ethics (1.4). Kept the 1.2
risk-management definitions (their canonical home); D1 1.4 now stays focused on the Code of Ethics
canons. D1: 43 → 41.

## 5. What the review did **not** flag (coverage evidence)

Absence of findings is itself a signal, so it is recorded rather than assumed:

- **D3 (Access Controls), all 23 cards:** zero accuracy findings, zero near-duplicates.
- **D1 accuracy:** only the single threat-wording issue; the CIA/AAA, risk, controls, and ethics
  canon cards passed.
- **D2 accuracy:** only the IR lifecycle issue; the BC/DR cards (MTD/RTO/RPO, BIA, backup types)
  passed — including the MTD ≥ RTO relationship, a classic trap, stated correctly.
- **Claim↔support alignment:** no drift findings survived verification across all 92 cards.

## 6. R&D — misconception registry seeds (feeds PR-8)

**Insight:** a confirmed accuracy defect is not just a bug to fix — it is a *catalogued exam
misconception*. The same wrong belief that slipped into a card is the belief a real candidate holds.
PR-8 distractors should be built to detect exactly these misconceptions, and each wrong answer's
rationale should name the misconception it targets. This turns the review's output into assessment
infrastructure instead of a throwaway bug list.

Proposed seeds for a `reference/misconception-registry.json` (to be created as the first artifact of
PR-8, then referenced by gold-item `misconception_tags`):

```json
[
  {
    "id": "ir-six-phase",
    "misconception": "The NIST incident-response lifecycle has six phases.",
    "correct": "Four phases; Containment, Eradication & Recovery is one combined phase.",
    "objective": "2.3",
    "origin": "pr7-adversarial-review 3.1",
    "distractor_use": "IR phase-count and phase-ordering items"
  },
  {
    "id": "threat-external-only",
    "misconception": "A threat is always external; insiders are not threats.",
    "correct": "Threats may be internal or external; insider threat is a tested concept.",
    "objective": "1.2",
    "origin": "pr7-adversarial-review 3.2",
    "distractor_use": "threat-vs-vulnerability and insider-threat items"
  },
  {
    "id": "hashing-is-encryption",
    "misconception": "Hashing is a form of encryption and can be reversed.",
    "correct": "Hashing is one-way; it provides integrity, not confidentiality.",
    "objective": "5.1",
    "origin": "existing exam_trap card D5.51 family",
    "distractor_use": "cryptography discrimination items"
  },
  {
    "id": "rto-exceeds-mtd",
    "misconception": "RTO can be longer than MTD.",
    "correct": "RTO must be less than or equal to MTD.",
    "objective": "2.1",
    "origin": "existing exam_trap card D2.21 family",
    "distractor_use": "BC/DR metric items"
  }
]
```

The 13 existing `exam_trap` cards are the natural harvest set for the rest of the registry; each
already encodes a misconception in its claim.

## 7. Process finding (adopted going forward)

**What happened:** the PR-7 cards were committed *before* the adversarial workflow finished; the
defects were caught and fixed in a follow-up commit. The end state is correct, but the sequence is
not acceptable once answer keys and gold items exist — a wrong item could ship in the window between
commit and review.

**Rule (now recorded in governance spec §16):** *no content-growth commit until the adversarial
review completes.* If the review is still running, the commit waits. This is a hard rule from PR-8
onward, where leakage-safety and answer-key correctness raise the cost of a bad window.

## 8. Summary

| | |
|---|---|
| Cards reviewed | 92 (D1/D2/D3) |
| Candidate findings | 3 accuracy + 2 near-dup pairs |
| Confirmed after adversarial verification | 2 accuracy + 2 near-dup |
| Blocker defects | 1 (IR lifecycle) — fixed |
| Major defects | 1 (threat wording) — fixed |
| Cards removed | 2 (near-duplicates) |
| Final deck | 149 cards, all gates green |
| Fix commit | `2784802` |
