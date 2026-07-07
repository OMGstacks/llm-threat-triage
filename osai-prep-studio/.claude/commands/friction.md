---
description: End-of-session friction capture — log recurring manual work into the friction diary. Docs-only; builds nothing.
argument-hint: [optional focus area]
---

> Fill in every placeholder token (`<LIKE_THIS>`) before this command is safe to use in
> a new project.

**Purpose.** A thin end-of-session playbook, not a reimplementation. It wraps the
friction-diary toolkit component at `.cognition/friction/` — that directory
owns the actual schema, storage format, and threshold-computation tooling. This command
just tells you when and how to invoke it. This is a documentation pass: make no code or
production changes. Optional focus: $ARGUMENTS

---

1. **Ask the question.** Did this session do something manually that you've done
   before, or that you expect to have to do again? If no — stop, nothing to log.

2. **Search before creating.** Search the existing friction log for a matching entry
   BEFORE writing a new one — free-text/keyword search first, then narrow by any
   domain-specific taxonomy field the project's diary uses second. Never search in the
   reverse order (taxonomy first hides matches that use different category framing but
   are the same underlying friction).

3. **Found a match** → append a one-line dated evidence note and increment its
   recurrence count.

4. **No match** → create a new entry, but only after it passes both mandatory intake
   questions:
   - **Recurrence test:** "Would I hit this again next week if I did nothing?" A NO
     means don't log it — one-off forensic/incident work belongs in an incident
     document, not the friction log.
   - **Falsifiability test:** "What evidence would prove this entry is WRONG?" An entry
     that can't specify this is a vague complaint, not a logged gap — sharpen it or
     don't log it.

5. **Everything else** — the entry schema, state/lifecycle fields, scoring/threshold
   logic for when a recurring gap becomes build-eligible, and the storage format — is
   owned by `.cognition/friction/`. Follow that component's actual interface;
   do not invent a parallel format here.

Report back briefly: what was searched, what was found/created, and stop.

---

## What this replaces / why it exists

This generalizes an end-of-session habit of noticing repeated manual work and capturing
it cheaply, so a third or fourth recurrence is visible as a pattern instead of being
re-discovered as friction each time. Kept intentionally short: the actual mechanics live
in the friction-diary component, and restating its schema here would create exactly the
"same rule in two places, drifts when one is updated" problem this toolkit exists to
avoid.
