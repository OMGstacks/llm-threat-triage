"""cc_spine.cram_sheet — weak-area review packets (PR-11c).

The other half of the deferred "dashboard + cram sheets" slice (PR-10's report). Where the readiness
dashboard (PR-11a/11b) is deliberately CONTENT-FREE (ids, counts, accuracies — a live status panel),
a cram sheet's entire purpose is the opposite: surface the teaching content behind the learner's own
past misses so they can actually study the weak spots. This is not a leak — every fact shown here
came from an item the learner already attempted and got wrong; the correction/one_sentence_rule/trap
text is the misconception registry's committed, vetted explanation, exactly what
``learner_state.replay`` already writes into the open journal for this purpose.

What is still withheld, deliberately, even here: the item's ``choices`` (so this stays a conceptual
review, not a "here's the answer key" list), the raw ``correct_index`` / ``answer_key_ref`` /
``rationale_refs`` / ``distractor_misconceptions`` map / hashes (the isolated-key fields never belong
in a learner-facing surface, full stop), and the learner's own ``selected_index`` (not useful for
review). ``fact_ids`` / ``expected_keywords`` stay internal too — grounding metadata, not teaching
content. Holdout content can never appear: ``learner_state.replay`` rejects holdout attempts
fail-closed, so no holdout item id ever reaches the journal this module reads.

``build_cram_sheet(state, now)`` is a pure, deterministic function: no clock/random, only the
injected ``now`` and the already-replayed state. Domains with a scored accuracy (``per_domain``)
are ordered weakest-accuracy-first; domains with NO accuracy signal — ``exam_strategy`` items all
carry domain ``"global"``, and ``learner_state.readiness_report`` deliberately excludes that bank
from ``per_domain`` — sort LAST rather than being defaulted to "0% accuracy" (review F1: an
unscored domain is not the same as a failing one, and must not permanently outrank domains the
learner is actually weak in). Within a domain, entries are ordered priority-miss-first (an
overconfident wrong answer, the most dangerous kind), then most-recent-first, then item_id as a
stable tie-breaker. ``priority`` reflects the ITEM's current aggregate confidence flag from
``learner_state`` (the most recent overconfident miss on that item), not a per-misconception
attribution — today's goldset never maps two distinct misconceptions to one item's distractors, so
this is not yet observable, but a future item authored that way would share one ``priority`` value
across its open entries (review F3, documented rather than re-plumbed through the journal schema).

Stdlib only. Imports ``learner_state`` (for its constants) is unnecessary — this module reads only
the already-built ``state`` dict — and ``quiz`` (for the practice item's neutral stem/domain via the
same learner-facing lookup pattern used elsewhere). Imported by none of them.
"""

from __future__ import annotations

from . import quiz

CRAM_SHEET_SCHEMA_VERSION = "1.0.0"
_MAX_RECAP = 5
# review F2: a schema-valid, non-null fallback for a journal entry whose item_id no longer resolves
# in the goldset (e.g. a persisted attempt stream replayed against an updated store).
_UNKNOWN_DOMAIN = "unknown"


def _entry(journal_row: dict, item: dict, priority: bool) -> dict:
    return {
        "item_id": journal_row["item_id"],
        "objective": journal_row["objective"],
        "bank": journal_row["bank"],
        "misconception_id": journal_row["misconception_id"],
        "trap": journal_row["trap"],
        "correction": journal_row["correction"],
        "one_sentence_rule": journal_row["one_sentence_rule"],
        "recorded_at_day": journal_row["recorded_at"],
        "priority": priority,
        "stem": item.get("stem") if item else None,
    }


def build_cram_sheet(state: dict, now: int = 0) -> dict:
    """Assemble the weak-area review packet. Pure function of ``state`` and ``now``."""
    practice = {i["id"]: i for i in quiz.load_goldset()}
    items_state = state.get("items", {})
    per_domain = state.get("readiness", {}).get("per_domain", {})
    journal = state.get("journal", [])

    open_rows = [j for j in journal if not j.get("closed")]
    closed_rows = [j for j in journal if j.get("closed")]

    by_domain: dict = {}
    for j in open_rows:
        item = practice.get(j["item_id"])
        # review F2: an item_id that no longer resolves in the goldset (e.g. a replayed stream
        # against an updated store) must not surface a Python None as the "domain" — that would
        # emit invalid JSON against the schema's string enum and crash the HTML render's
        # html.escape(None). Fall back to an explicit, schema-valid sentinel instead.
        dom = ((item or {}).get("domain")) or _UNKNOWN_DOMAIN
        priority = bool(items_state.get(j["item_id"], {}).get("priority"))
        by_domain.setdefault(dom, []).append(_entry(j, item, priority))

    for entries in by_domain.values():
        entries.sort(key=lambda e: (not e["priority"], -e["recorded_at_day"], e["item_id"]))

    def _domain_accuracy(dom):
        return per_domain.get(dom, {}).get("accuracy", 0.0)

    # review F1: per_domain (from learner_state.readiness_report) explicitly EXCLUDES the
    # exam_strategy bank, whose items all carry domain "global" — so "global" (and the
    # _UNKNOWN_DOMAIN sentinel) never has a per_domain entry. Defaulting its accuracy to 0.0 and
    # sorting purely by accuracy would treat "unscored" as "the single worst domain", permanently
    # pinning it above domains that are genuinely failing. Sort unscored domains LAST instead —
    # they still need review, just not falsely badged as the weakest.
    domains = [
        {
            "domain": dom,
            "accuracy": per_domain.get(dom, {}).get("accuracy"),
            "attempts": per_domain.get(dom, {}).get("attempts", 0),
            "entries": entries,
        }
        for dom, entries in sorted(by_domain.items(),
                                   key=lambda kv: (kv[0] not in per_domain, _domain_accuracy(kv[0]), kv[0]))
    ]

    # a short, positive recap of recently-closed misconceptions — dedup to the latest occurrence
    # per misconception_id so a single closed trap isn't listed once per item it appeared on.
    latest_closed: dict = {}
    for j in closed_rows:
        prev = latest_closed.get(j["misconception_id"])
        if prev is None or j["recorded_at"] > prev["recorded_at"]:
            latest_closed[j["misconception_id"]] = j
    recap_rows = sorted(latest_closed.values(), key=lambda j: (-j["recorded_at"], j["misconception_id"]))
    closed_recap = [{"misconception_id": j["misconception_id"], "one_sentence_rule": j["one_sentence_rule"]}
                    for j in recap_rows[:_MAX_RECAP]]

    return {
        "schema_version": CRAM_SHEET_SCHEMA_VERSION,
        "generated_at_day": now,
        "open_count": len(open_rows),
        "closed_count": len(closed_rows),
        "priority_count": sum(1 for entries in by_domain.values() for e in entries if e["priority"]),
        "domains": domains,
        "closed_recap": closed_recap,
    }
