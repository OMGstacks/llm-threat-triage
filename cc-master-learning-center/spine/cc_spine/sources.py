"""Source-registry validator — the source_freshness_guard (spec section 5).

Stdlib-only, fail-closed. Validates reference/source-registry.json structure
and freshness: a source marked ``current`` whose successor outline has become
effective (or an ``upcoming`` source whose effective date has passed) is a
freshness failure. This is what makes the CC exam outline's 2026-09-01
transition impossible to miss silently.

PR-4.1 adds the **attestation guard**: a source that the operator could not
fetch directly (``operator_fetch_status == "blocked_403"``) may only carry an
``official*`` confidence if a reviewer attestation in
reference/verification-evidence.json backs each of its ``attestation_urls`` and
is dated on/after the source's ``retrieved_at``. This keeps every "official"
claim on an operator-unreachable source provably tied to a dated attestation,
rather than asserted from memory.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

VALID_STATUSES = {"current", "upcoming", "deprecated"}

EVIDENCE_PATH = Path(__file__).resolve().parents[2] / "reference" / "verification-evidence.json"


def _parse_date(value):
    if value is None:
        return None
    return datetime.date.fromisoformat(value)


def _attestation_index(evidence: dict | None) -> dict[str, datetime.date]:
    """Map attestation url -> attestation date (latest wins). Bad dates are skipped
    so the per-source guard reports them as 'unbacked' rather than crashing."""
    index: dict[str, datetime.date] = {}
    for att in (evidence or {}).get("reviewer_attestations", []):
        url = att.get("url")
        try:
            date = _parse_date(att.get("date"))
        except ValueError:
            continue
        if url and date and index.get(url, datetime.date.min) < date:
            index[url] = date
    return index


def validate_registry(registry: dict, *, today: datetime.date | None = None,
                      evidence: dict | None = None) -> list[str]:
    today = today or datetime.date.today()
    failures: list[str] = []
    sources = registry.get("sources", [])
    seen: set[str] = set()
    by_topic: dict[str, list[dict]] = {}
    attestations = _attestation_index(evidence)

    for entry in sources:
        sid = entry.get("id", "<missing>")
        label = f"source {sid}"
        if sid in seen:
            failures.append(f"{label}: duplicate id")
        seen.add(sid)

        tier = entry.get("tier")
        if not isinstance(tier, int) or not 0 <= tier <= 4:
            failures.append(f"{label}: tier must be an integer 0-4")
        for req in ("type", "status", "topic", "source_url", "retrieved_at", "next_review"):
            if not entry.get(req):
                failures.append(f"{label}: missing {req}")

        # Freshness ledger (PR-4): every source carries a next_review date; a
        # source past its review date is stale until a human re-reviews it.
        try:
            next_review = _parse_date(entry.get("next_review"))
            if next_review and next_review <= today and entry.get("status") != "deprecated":
                failures.append(
                    f"{label}: source review is due (next_review {next_review} <= {today}); "
                    "re-review against the official source and bump next_review")
        except ValueError:
            failures.append(f"{label}: next_review not an ISO date")

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

        # Attestation guard (PR-4.1): an operator-unreachable official source must
        # be backed by a dated reviewer attestation for each attestation_url.
        if entry.get("operator_fetch_status") == "blocked_403" \
                and str(entry.get("confidence", "")).startswith("official"):
            if evidence is None:
                failures.append(
                    f"{label}: operator could not fetch it (403) and no verification "
                    "evidence was loaded to back its 'official' confidence")
            else:
                urls = entry.get("attestation_urls") or []
                if not urls:
                    failures.append(
                        f"{label}: operator-unreachable official source lists no "
                        "attestation_urls (cannot substantiate 'official' confidence)")
                for url in urls:
                    att_date = attestations.get(url)
                    if att_date is None:
                        failures.append(
                            f"{label}: no reviewer attestation for {url} backs this "
                            "operator-unreachable official source")
                    elif retrieved and att_date < retrieved:
                        failures.append(
                            f"{label}: attestation for {url} dated {att_date} predates "
                            f"retrieved_at {retrieved}")

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


def load_evidence(path: Path | None = None) -> dict | None:
    try:
        return json.loads(Path(path or EVIDENCE_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def validate_registry_file(path: Path, *, today: datetime.date | None = None,
                           evidence_path: Path | None = None) -> list[str]:
    try:
        registry = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path}: could not load source registry: {exc}"]
    evidence = load_evidence(evidence_path)
    return validate_registry(registry, today=today, evidence=evidence)
