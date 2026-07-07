---
name: feedback_css_class_substring_test_false_positive
description: Read before writing a test that asserts a CSS class name appears somewhere in
  rendered HTML output — a bare substring check against a class name is a false positive if the
  page's <style> block always defines that class regardless of what actually rendered.
metadata:
  type: feedback
---

# Feedback: CSS-class-substring test false positive

## The mistake, generalized

A test wants to prove "the warning chip rendered for this row." It asserts something like
`assert "chip-warn" in html_output`. This passes even when the chip never rendered on any row —
because the page's `<style>` block defines the `.chip-warn { ... }` CSS rule unconditionally, so
the literal string `chip-warn` is present in every page render regardless of what data-driven
content actually appears in the body.

## Why it keeps recurring

The bug is invisible from the test's own vantage point: the assertion is green, the string it's
looking for genuinely is in the output — just not for the reason the test believes. It reads as
correct on first write and stays green even after a regression removes the actual rendering
logic, because the stylesheet keeps supplying the substring. This recurred independently in two
sibling view-layer test files during the same development series, which is what promoted it from
"a bug" to "a pattern worth a standing rule."

## The rule

When testing that a specific element/class rendered in response to specific data:

1. Never assert a bare class-name substring against the whole page/output string.
2. Assert against the actual rendered *element*, scoped to the row/section under test — e.g. the
   class attribute of the specific DOM node (`class="chip chip-warn"` on the row's badge
   element), not a substring search over the entire document.
3. If using a plain-string HTML fixture without a DOM parser, scope the substring search to a
   delimited slice of the output containing only the row/component under test — not the full
   page — so the `<style>` block can't contribute a false match.
4. As a sanity check, verify the test actually fails when the rendering logic is disabled/removed
   (a quick mutation check) before trusting it as a regression guard.

## How this was learned

Found independently in two sibling test files (a dashboard view test and a cram-sheet view test)
during CC Master Learning Center's PR-11 development series on `claude/cc-cert-learning-plan-xqo5g7`
(not yet merged to `main`) — the same false-positive shape recurring in unrelated files is why
this is recorded as a standing rule rather than a one-off fix.
