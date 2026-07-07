---
name: feedback_default_missing_data_to_worst_case
description: Read before writing any sort/rank/aggregate over data that can be partially
  absent or excluded — coercing a missing signal to its worst possible value silently and
  permanently outranks genuinely weak-but-present data.
metadata:
  type: feedback
---

# Feedback: defaulting missing data to worst-case

## The mistake, generalized

A ranking or sorting routine aggregates a signal (e.g. an accuracy score) across several
sources, some of which may be excluded or have no data yet. The implementation defaults an
*absent* signal to the numeric floor of the scale (e.g. treats "no accuracy data" as 0%) so the
sort has something to compare. This silently makes "we have no signal" indistinguishable from
"we measured this and it's the worst," and — because 0% sorts below any genuinely low-but-real
score — a source with no data at all permanently outranks a source that was actually measured
and found weak.

## Why it keeps recurring

Defaulting missing-to-worst is the path of least resistance: it lets existing comparison/sort
code run unmodified against a value type it already knows how to compare, and the sort doesn't
crash or need a special case. The cost only shows up downstream, when someone reads the ranked
output and can't tell "this needs the most attention because it's weak" from "this needs the
most attention because we haven't looked at it yet" — two very different situations that call
for different actions.

## The rule

When aggregating over data that can be partially missing or excluded:

1. "No signal" must be a distinguishable state from "worst signal" in both the sort order and
   the rendered output — never coerced to the same numeric floor by default.
2. Prefer sorting missing-signal entries into their own group (e.g. rendered separately, or
   sorted last *and* visibly labeled "no data" rather than "0%"), so a reader can't mistake
   absence for a measured result.
3. If a single combined ranking is required, make the missing-vs-worst distinction an explicit,
   named parameter of the sort function — not an implicit default baked into how missing values
   get coerced.

## How this was learned

Found in CC Master Learning Center's PR-11 development series (on
`claude/cc-cert-learning-plan-xqo5g7`, not yet merged to `main`): a dashboard ranking treated an
excluded question bank's absent accuracy signal as 0%, permanently outranking genuinely weak but
scored banks — the fix generalized to this standing rule about missing-vs-worst-case defaults.
