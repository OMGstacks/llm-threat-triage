---
description: CI failure triage — classify a red check (transient / mine / pre-existing-on-shared-branch) before reacting. Never merge over an unclassified red check.
argument-hint: [review-request number or failing check name]
---

> Fill in every placeholder token (`<LIKE_THIS>`) before this command is safe to use in
> a new project.

**Purpose.** A red CI check is a classification problem before it is a fixing problem.
Reacting to the check's name alone (instead of its actual error) wastes effort on the
wrong fix, and merging or proceeding over a check that was never actually classified
turns "I don't know why this is red" into silent risk. Target: $ARGUMENTS

Evidence tier for this command: see
`.claude/commands/_shared/evidence-contract.md`. You must reach
`EVIDENCE_CURRENT` on the actual job log before classifying — a check's pass/fail label
alone is not sufficient evidence.

---

## Step 1 — fetch the actual evidence (read-only)

Never react to the check's name. Fetch the real error output:
- List failing checks: `gh pr checks <review-request-id>`
- Pull the actual job log: `gh run view --job <job-id>`

Identify the ACTUAL error class: collection error, assertion failure, lint violation,
or infra/transient failure. Do not proceed to classification without having read the
real output — the check name (e.g. "tests failed") is not enough information.

**STOP POINT:** do not classify or act until you have the real error text in hand.

## Step 2 — classify against known-transient patterns

Check the failure against your project's maintained list of known-transient infra
patterns. Keep this list current as a project artifact — do not rebuild it from memory
each time. Suggested location: `this file's own "Known-transient CI patterns" section below (no separate doc yet — inline is fine at this project's current CI size)`. Typical entries:

- Checkout/auth failures at the source-fetch step (e.g. an auth prompt / credential
  error during repo checkout) → the job's real work never ran.
- Network timeouts, 5xx from a package registry, TLS handshake failures → network
  transient.
- A path-filtered pipeline showing "no/few checks" on a docs-only change → nothing
  relevant ran; the merge-readiness status from the host is authoritative, not the
  raw check list.
- A "mismatch" between two runtime identities that are expected to sometimes differ
  intentionally (e.g. two components that deploy independently) → not a failure class;
  confirm against your project's deploy-surface facts before treating it as red.

**Anti-abuse condition — label a failure "transient/unrelated" ONLY if ALL hold:**
1. The failing job shares ZERO touched files with this change.
2. A documented known-pattern from the list above actually matches (not "looks similar").
3. The authoritative, path-scoped remote CI result is the arbiter — not a local
   flake or a guess.

If transient: re-run the job (`gh run rerun <run-id>`). Touch NO
code. Re-verify green afterward.

**STOP POINT:** do not label something transient to avoid doing the work of a real fix.
The three-condition test above is intentionally strict.

## Step 3 — if not transient: mine, or pre-existing on the shared branch?

Determine whether the failure is caused by your own diff, or was already broken on the
shared/default branch before your change. If unsure, reproduce on a clean checkout of
the current default branch with your diff NOT applied — does it fail there too?

- **Mine** → fix it within this change, re-run, confirm green.
- **Pre-existing red on the shared branch (unrelated cause)** → apply the ordered
  preference below. Do not silently fix it inline as a side effect of your unrelated
  change, and do not merge over it.

### Ordered preference for pre-existing shared-branch red

1. **PAUSE** — stop and report the red gate to a human. Default choice for anything
   non-trivial, ambiguous, or touching code you don't fully understand.
2. **SMALL DEDICATED FIX PR** — open a narrowly-scoped review request for the fix only,
   separate from whatever you were originally doing. Preferred when the fix is clear
   but not time-critical. Preserves the review trail and doesn't entangle the fix with
   unrelated work.
3. **EMERGENCY DIRECT COMMIT** — only when the red gate is blocking a time-sensitive
   operation AND the fix is unambiguous (e.g. an established, previously-used exclusion
   pattern). If used, the commit message MUST be a structured receipt containing:
   - `reason` — why the shared branch was red
   - `scope` — exactly what changed
   - `local reproduction` — the command + output that proved the failure
   - `post-fix check` — the command + output proving green afterward
   - `why no PR` — why the small-fix-PR path was not used instead

**Do not normalize path 3.** It is an exception path, not a pattern. During active
concurrent work on the shared branch from other sessions/teammates, prefer PAUSE or the
dedicated fix PR — a direct commit raises race risk on a moving target.

## Step 4 — report

State explicitly: classification (transient / mine / pre-existing) + the path chosen +
the evidence that justified it.

---

## The hard invariant

**Never merge or proceed past an UNCLASSIFIED red check.** "Unclassified" means you have
not yet fetched the real error and matched it to one of the three paths above. A red
check with no classification is not a "probably fine, re-run it" — it is a stop.

## What this replaces / why it exists

This generalizes a repair protocol written after a real incident where a pre-existing,
unrelated red check on a shared branch was blocking an in-progress merge; the ordered
preference (pause > dedicated fix > emergency direct commit) exists specifically to
prevent direct-to-shared-branch fixes from becoming a normalized shortcut. The
known-transient list and its three-condition anti-abuse test exist because "just re-run
it" is exactly the failure mode that lets real, recurring issues get waved through as
if they were infra noise.
