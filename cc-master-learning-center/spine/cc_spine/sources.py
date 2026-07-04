"""Source-registry validator — the source_freshness_guard (spec section 5).

Stdlib-only, fail-closed. Validates reference/source-registry.json structure
and freshness: a source marked ``current`` whose successor outline has become
effective (or an ``upcoming`` source whose effective date has passed) is a
freshness failure. This is what makes the CC exam outline's 2026-09-01
transition impossible to miss silently.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

VALID_STATUSES = {"current", "upcoming", "deprecated"}


def _parse_date(value):
    if value is None:
        return None
    return datetime.date.fromisoformat(value)


def validate_registry(registry: dict, *, today: datetime.date | None = None) -> list[str]:
    today = today or datetime.date.today()
    failures: list[str] = []
    sources = registry.get("sources", [])
    seen: set[str] = set()
    by_topic: dict[str, list[dict]] = {}

    for entry in sources:
        sid = entry.get("id", "<missing>")
        label = f"source {sid}"
        if sid in seen:
            failures.append(f"{label}: duplicate id")
        seen.add(sid)

        tier = entry.get("tier")
        if not isinstance(tier, int) or not 0 <= tier <= 4:
            failures.append(f"{label}: tier must be an integer 0-4")
        for req in ("type", "status", "topic", "source_url", "retrieved_at"):
            if not entry.get(req):
                failures.append(f"{label}: missing {req}")

        status = entry.get("status")
        if status not in VALID_STATUSES:
            failures.append(f"{label}: bad status {status!r}")

        try:
            retrieved = _parse_date(entry.get("retrieved_at"))
            if retrieved and retrieved > today:
                failures.append(f"{label}: retrieved_at {retrieved} is in the future")
        except ValueError:
            failures.append(f"{label}: retrieved_at not an ISO date")

        try:
            effective = _parse_date(entry.get("effective_date"))
        except ValueError:
            failures.append(f"{label}: effective_date not an ISO date")
            effective = None

        if status == "upcoming" and effective and effective <= today:
            failures.append(
                f"{label}: marked 'upcoming' but effective_date {effective} has passed "
                f"(as of {today}); flip to 'current' and re-review dependents"
            )

        by_topic.setdefault(entry.get("topic"), []).append(entry)

    # Cross-check supersession within a topic (e.g. the two CC exam outlines).
    for topic, entries in by_topic.items():
        currents = [e for e in entries if e.get("status") == "current"]
        upcomings = [e for e in entries if e.get("status") == "upcoming"]
        for cur in currents:
            for nxt in upcomings:
                try:
                    nxt_eff = _parse_date(nxt.get("effective_date"))
                except ValueError:
                    continue
                if nxt_eff and nxt_eff <= today:
                    failures.append(
                        f"source {cur.get('id')}: marked 'current' but successor "
                        f"{nxt.get('id')} (effective {nxt_eff}) is now effective as of {today}"
                    )
    return failures


def validate_registry_file(path: Path, *, today: datetime.date | None = None) -> list[str]:
    try:
        registry = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path}: could not load source registry: {exc}"]
    return validate_registry(registry, today=today)
