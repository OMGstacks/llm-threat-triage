#!/usr/bin/env python3
"""
friction_cli.py — CLI for the operational friction diary.

Operates directly on a JSONL log file (default: friction_log.jsonl in the
current directory, overridable via --log). See SCHEMA.md for the canonical
entry schema that every line in the log must conform to.

Subcommands:
    log      <title>   Search for a possible duplicate, then create a new
                        entry (or delegate to bump if the user confirms a
                        match).
    bump     <id>       Append an evidence_log entry + increment
                        recurrence_count on an existing entry.
    review              Recompute build-eligibility for every CANDIDATE /
                        QUALIFYING entry per threshold_config.yml and print
                        a diff against stored status. Never mutates.
    promote  <id>       Move status forward exactly one lifecycle step.

Design notes:
    - The JSONL file is treated as line-oriented storage. `bump` and
      `promote` rewrite only the single line that changed — never the whole
      file — so concurrent/worktree-based git merges stay diff-friendly.
    - No entry is ever silently merged. `log` always surfaces candidate
      matches and requires explicit confirmation (interactive prompt or
      --match-id) before delegating to bump.
    - review is read-only. Promotion is always a separate, explicit,
      human-run command (verifier/proposer separation — see SCHEMA.md).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

# Force UTF-8 stdout/stderr so non-ASCII characters (e.g. em-dashes in
# titles/notes) render correctly regardless of the host console's default
# codepage (notably Windows cp1252). Safe no-op on platforms where stdout
# is already UTF-8.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

DEFAULT_LOG_PATH = "friction_log.jsonl"
DEFAULT_CONFIG_PATH = "threshold_config.yml"

STATUS_ORDER = ["CANDIDATE", "QUALIFYING", "BUILD_ELIGIBLE", "BUILT"]
OFF_RAMP_STATUSES = ["DISQUALIFIED", "DEFERRED"]
ALL_STATUSES = STATUS_ORDER + OFF_RAMP_STATUSES

REQUIRED_FIELDS = [
    "id", "title", "status", "created_date", "last_seen_date",
    "affected_component", "domain_extensions", "recurrence_count",
    "evidence_log", "manual_procedure", "proposed_fix", "recurrence_signal",
    "severity_signal", "falsifiability_gate", "golden_rule_answer",
    "built_as", "built_pr", "post_build_check",
]


# --------------------------------------------------------------------------
# JSONL I/O helpers
# --------------------------------------------------------------------------

def read_log(log_path: Path) -> list[dict[str, Any]]:
    """Read all entries from the JSONL log. Missing file -> empty list."""
    if not log_path.exists():
        return []
    entries = []
    with log_path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise SystemExit(
                    f"error: {log_path}:{lineno}: invalid JSON ({e})"
                )
    return entries


def append_entry(log_path: Path, entry: dict[str, Any]) -> None:
    """Append a single new entry as one JSONL line. Never rewrites others."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def rewrite_single_line(log_path: Path, entry_id: str, new_entry: dict[str, Any]) -> None:
    """
    Replace exactly the JSONL line whose `id` matches entry_id with
    new_entry, leaving every other line byte-for-byte untouched. This is a
    targeted line replace, not a full-file rewrite, so JSONL stays diffable
    and git-merge-friendly across concurrent sessions.
    """
    if not log_path.exists():
        raise SystemExit(f"error: log file not found: {log_path}")

    with log_path.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    found = False
    out_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            out_lines.append(line)
            continue
        obj = json.loads(stripped)
        if obj.get("id") == entry_id:
            out_lines.append(json.dumps(new_entry, ensure_ascii=False) + "\n")
            found = True
        else:
            out_lines.append(line)

    if not found:
        raise SystemExit(f"error: no entry with id {entry_id!r} found in {log_path}")

    with log_path.open("w", encoding="utf-8", newline="\n") as f:
        f.writelines(out_lines)


def find_entry(entries: list[dict[str, Any]], entry_id: str) -> Optional[dict[str, Any]]:
    for e in entries:
        if e.get("id") == entry_id:
            return e
    return None


def next_id(entries: list[dict[str, Any]], prefix: str) -> str:
    """
    Derive the next available ID for `prefix` as
    max(existing numeric suffix for that prefix) + 1, scanning the actual
    log file. Never guessed, never reused even if the max entry was later
    disqualified.
    """
    max_n = 0
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    for e in entries:
        m = pattern.match(str(e.get("id", "")))
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"{prefix}-{max_n + 1}"


def today_str() -> str:
    return date.today().isoformat()


# --------------------------------------------------------------------------
# Fuzzy / keyword search (no ML dependency — simple token-overlap scoring)
# --------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is",
    "was", "it", "this", "that", "with", "by", "at", "as", "be", "are",
    "each", "every", "after", "before", "via", "into", "when", "then",
    # Domain-boilerplate words that recur in nearly every friction-diary
    # title/procedure by convention (e.g. "Manually re-run...",
    # "Manual restart...") and therefore have near-zero discriminating
    # power for duplicate detection. Excluding them avoids false-positive
    # matches between two entries that share only "manual"/"manually" and
    # nothing else in common.
    "manual", "manually", "process", "step", "steps",
}


def _tokenize(text: str) -> set[str]:
    tokens = set(_TOKEN_RE.findall(text.lower()))
    return tokens - _STOPWORDS


def score_match(query: str, entry: dict[str, Any]) -> float:
    """
    Simple token-overlap score across title, affected_component, and
    manual_procedure. Score = overlap / max(1, len(query_tokens)), summed
    across the three fields with title weighted highest. Deliberately
    dependency-free (no embeddings/ML) — good enough to surface likely
    duplicates for a human to confirm, never to auto-merge.
    """
    q_tokens = _tokenize(query)
    if not q_tokens:
        return 0.0

    weights = {
        "title": 2.0,
        "affected_component": 1.0,
        "manual_procedure": 0.5,
    }
    total = 0.0
    for field, weight in weights.items():
        field_tokens = _tokenize(str(entry.get(field, "")))
        overlap = q_tokens & field_tokens
        total += weight * (len(overlap) / len(q_tokens))
    return total


def top_candidate_matches(
    query: str, entries: list[dict[str, Any]], k: int = 3
) -> list[tuple[float, dict[str, Any]]]:
    scored = [(score_match(query, e), e) for e in entries]
    scored = [(s, e) for s, e in scored if s > 0.0]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[:k]


# --------------------------------------------------------------------------
# Threshold config
# --------------------------------------------------------------------------

@dataclass
class ThresholdConfig:
    severity_values: list[str]
    required_severity_values: list[str]
    min_recurrence_count: int
    min_days_between_first_and_last: int


def _minimal_yaml_load(text: str) -> dict[str, Any]:
    """
    Minimal YAML subset loader (no external dependency) sufficient for
    threshold_config.yml's shape: top-level scalar keys, and a top-level
    key followed by a `- item` list. Good enough for this config's schema;
    if a project needs richer YAML, swap in pyyaml and keep this function's
    signature.
    """
    data: dict[str, Any] = {}
    current_list_key: Optional[str] = None

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        stripped = line.strip()

        if stripped.startswith("- "):
            if current_list_key is None:
                raise SystemExit(f"error: list item with no preceding key: {raw_line!r}")
            item = stripped[2:].strip().strip('"').strip("'")
            data.setdefault(current_list_key, []).append(item)
            continue

        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if value == "":
                # Start of a list block
                current_list_key = key
                data[key] = []
            else:
                current_list_key = None
                value = value.strip('"').strip("'")
                # try int, else keep as string
                try:
                    data[key] = int(value)
                except ValueError:
                    data[key] = value
    return data


def load_threshold_config(config_path: Path) -> ThresholdConfig:
    if not config_path.exists():
        raise SystemExit(
            f"error: threshold config not found at {config_path}. "
            f"Copy threshold_config.example.yml to {config_path.name} and tune it "
            f"for this project, or pass --config explicitly."
        )
    text = config_path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
        raw = yaml.safe_load(text) or {}
    except ImportError:
        raw = _minimal_yaml_load(text)

    try:
        return ThresholdConfig(
            severity_values=list(raw["severity_values"]),
            required_severity_values=list(raw["required_severity_values"]),
            min_recurrence_count=int(raw["min_recurrence_count"]),
            min_days_between_first_and_last=int(raw["min_days_between_first_and_last"]),
        )
    except KeyError as e:
        raise SystemExit(f"error: threshold config missing required key: {e}")


def compute_build_eligible(entry: dict[str, Any], config: ThresholdConfig) -> bool:
    """
    Two-(really three-)factor formula documented in SCHEMA.md /
    threshold_config.example.yml:
        1. recurrence_count >= min_recurrence_count
        2. severity_signal in required_severity_values
        3. elapsed days between created_date and last_seen_date
           >= min_days_between_first_and_last
    """
    recurrence_ok = entry.get("recurrence_count", 0) >= config.min_recurrence_count
    severity_ok = entry.get("severity_signal") in config.required_severity_values

    created = datetime.strptime(entry["created_date"], "%Y-%m-%d").date()
    last_seen = datetime.strptime(entry["last_seen_date"], "%Y-%m-%d").date()
    days_span = (last_seen - created).days
    span_ok = days_span >= config.min_days_between_first_and_last

    return recurrence_ok and severity_ok and span_ok


# --------------------------------------------------------------------------
# Validation helpers
# --------------------------------------------------------------------------

def validate_entry_shape(entry: dict[str, Any]) -> None:
    missing = [f for f in REQUIRED_FIELDS if f not in entry]
    if missing:
        raise SystemExit(f"error: entry missing required fields: {missing}")


def parse_iso_date(s: str, field_name: str) -> str:
    try:
        datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        raise SystemExit(f"error: {field_name} must be ISO YYYY-MM-DD, got {s!r}")
    return s


# --------------------------------------------------------------------------
# Subcommand: log
# --------------------------------------------------------------------------

def cmd_log(args: argparse.Namespace) -> dict[str, Any]:
    log_path = Path(args.log)
    entries = read_log(log_path)

    matches = top_candidate_matches(args.title, entries, k=3)

    match_id = args.match_id

    if matches and match_id is None and not args.no_search:
        print(f"Possible existing matches for {args.title!r}:", file=sys.stderr)
        for score, e in matches:
            print(
                f"  [{e['id']}] (score={score:.2f}) {e['title']} "
                f"— status={e['status']}, recurrence_count={e['recurrence_count']}",
                file=sys.stderr,
            )
        if args.non_interactive:
            print(
                "Non-interactive mode: pass --match-id <id> to confirm one of the "
                "above as the same friction (delegates to bump), or --no-search to "
                "force creation of a new entry despite the matches.",
                file=sys.stderr,
            )
            raise SystemExit(2)
        else:
            reply = input(
                "Is this the same friction as an existing entry? "
                "Enter an id to confirm (e.g. GAP-3), or press Enter to create new: "
            ).strip()
            if reply:
                match_id = reply

    if match_id:
        existing = find_entry(entries, match_id)
        if existing is None:
            raise SystemExit(f"error: --match-id {match_id!r} does not match any existing entry")
        bump_args = argparse.Namespace(
            log=args.log,
            id=match_id,
            note=args.note or f"Recurrence confirmed via `log` search for: {args.title}",
            json=args.json,
        )
        result = cmd_bump(bump_args)
        result["delegated_from_log"] = True
        return result

    # Creating a genuinely new entry.
    if not args.golden_rule_yes:
        print(
            "Refusing to create entry: --golden-rule-yes was not passed as true.\n"
            "The golden-rule intake filter requires an explicit yes to:\n"
            '  "Would this recur next week if nothing changed?"\n'
            "If the honest answer is no, this is one-off forensic/incident work — "
            "file it as incident documentation instead, not in the friction diary.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    required_flag_fields = {
        "affected_component": args.affected_component,
        "manual_procedure": args.manual_procedure,
        "proposed_fix": args.proposed_fix,
        "severity": args.severity,
        "falsifiability_gate": args.falsifiability_gate,
    }
    missing_flags = [name for name, val in required_flag_fields.items() if not val]
    if missing_flags:
        raise SystemExit(
            "error: missing required flags for non-interactive entry creation: "
            + ", ".join(f"--{m.replace('_', '-')}" for m in missing_flags)
        )

    prefix = args.prefix
    entry_id = next_id(entries, prefix)
    created = today_str()

    new_entry = {
        "id": entry_id,
        "title": args.title,
        "status": "CANDIDATE",
        "created_date": created,
        "last_seen_date": created,
        "affected_component": args.affected_component,
        "domain_extensions": json.loads(args.domain_extensions) if args.domain_extensions else {},
        "recurrence_count": 1,
        "evidence_log": [{"date": created, "note": args.note or "Initial observation."}],
        "manual_procedure": args.manual_procedure,
        "proposed_fix": args.proposed_fix,
        "recurrence_signal": args.recurrence_signal,
        "severity_signal": args.severity,
        "falsifiability_gate": args.falsifiability_gate,
        "golden_rule_answer": True,
        "built_as": None,
        "built_pr": None,
        "post_build_check": None,
    }
    validate_entry_shape(new_entry)
    append_entry(log_path, new_entry)
    return {"action": "created", "entry": new_entry}


# --------------------------------------------------------------------------
# Subcommand: bump
# --------------------------------------------------------------------------

def cmd_bump(args: argparse.Namespace) -> dict[str, Any]:
    log_path = Path(args.log)
    entries = read_log(log_path)
    entry = find_entry(entries, args.id)
    if entry is None:
        raise SystemExit(f"error: no entry with id {args.id!r} found in {log_path}")

    note = args.note or "Recurrence observed."
    today = today_str()

    entry = dict(entry)  # shallow copy
    entry["evidence_log"] = list(entry.get("evidence_log", [])) + [
        {"date": today, "note": note}
    ]
    entry["recurrence_count"] = int(entry.get("recurrence_count", 0)) + 1
    entry["last_seen_date"] = today

    rewrite_single_line(log_path, args.id, entry)
    return {"action": "bumped", "entry": entry}


# --------------------------------------------------------------------------
# Subcommand: review
# --------------------------------------------------------------------------

def cmd_review(args: argparse.Namespace) -> dict[str, Any]:
    log_path = Path(args.log)
    config_path = Path(args.config)
    entries = read_log(log_path)
    config = load_threshold_config(config_path)

    diffs = []
    for entry in entries:
        if entry["status"] not in ("CANDIDATE", "QUALIFYING"):
            continue
        recomputed_eligible = compute_build_eligible(entry, config)
        recomputed_status = "BUILD_ELIGIBLE" if recomputed_eligible else entry["status"]
        agrees = recomputed_status == entry["status"]
        diffs.append(
            {
                "id": entry["id"],
                "title": entry["title"],
                "stored_status": entry["status"],
                "recomputed_status": recomputed_status,
                "agrees": agrees,
                "recurrence_count": entry.get("recurrence_count"),
                "severity_signal": entry.get("severity_signal"),
                "days_span": (
                    datetime.strptime(entry["last_seen_date"], "%Y-%m-%d").date()
                    - datetime.strptime(entry["created_date"], "%Y-%m-%d").date()
                ).days,
            }
        )

    flagged = [d for d in diffs if not d["agrees"]]
    return {"config_path": str(config_path), "diffs": diffs, "flagged": flagged}


def print_review_report(result: dict[str, Any]) -> None:
    diffs = result["diffs"]
    flagged = result["flagged"]
    print(f"Reviewed {len(diffs)} CANDIDATE/QUALIFYING entries against {result['config_path']}")
    print()
    if not diffs:
        print("(no CANDIDATE/QUALIFYING entries to review)")
        return

    for d in diffs:
        marker = "DRIFT" if not d["agrees"] else "ok   "
        print(
            f"[{marker}] {d['id']:<8} stored={d['stored_status']:<14} "
            f"recomputed={d['recomputed_status']:<14} "
            f"(recurrence_count={d['recurrence_count']}, "
            f"severity={d['severity_signal']}, days_span={d['days_span']}) "
            f"— {d['title']}"
        )

    print()
    if flagged:
        print(f"{len(flagged)} entr{'y' if len(flagged) == 1 else 'ies'} flagged for drift "
              f"(stored status disagrees with recomputed formula):")
        for d in flagged:
            print(f"  - {d['id']}: stored={d['stored_status']} but formula says "
                  f"{d['recomputed_status']}. Run `promote {d['id']} --evidence ...` "
                  f"if a human confirms this.")
    else:
        print("No drift — all stored statuses agree with the recomputed formula.")


# --------------------------------------------------------------------------
# Subcommand: promote
# --------------------------------------------------------------------------

def cmd_promote(args: argparse.Namespace) -> dict[str, Any]:
    log_path = Path(args.log)
    entries = read_log(log_path)
    entry = find_entry(entries, args.id)
    if entry is None:
        raise SystemExit(f"error: no entry with id {args.id!r} found in {log_path}")

    current_status = entry["status"]

    if args.to in OFF_RAMP_STATUSES:
        if current_status in ("BUILT",) + tuple(OFF_RAMP_STATUSES):
            raise SystemExit(
                f"error: cannot move entry {args.id} from {current_status} to {args.to} "
                f"(off-ramps only apply to pre-BUILT, non-terminal states)"
            )
        new_status = args.to
    else:
        if current_status in OFF_RAMP_STATUSES:
            raise SystemExit(
                f"error: entry {args.id} is in terminal off-ramp state {current_status}; "
                f"cannot promote forward"
            )
        if current_status not in STATUS_ORDER:
            raise SystemExit(f"error: entry {args.id} has unrecognized status {current_status!r}")
        current_idx = STATUS_ORDER.index(current_status)
        if current_idx == len(STATUS_ORDER) - 1:
            raise SystemExit(f"error: entry {args.id} is already BUILT — nothing further to promote")
        new_status = STATUS_ORDER[current_idx + 1]

        # refuse to skip states: if caller passed --to explicitly and it's
        # not the immediate next step, reject.
        if args.to is not None and args.to != new_status:
            raise SystemExit(
                f"error: cannot promote {args.id} from {current_status} directly to {args.to} "
                f"— lifecycle moves one step at a time. Next valid step is {new_status}."
            )

        if current_status == "QUALIFYING" and new_status == "BUILD_ELIGIBLE":
            if not args.evidence:
                raise SystemExit(
                    "error: promoting QUALIFYING -> BUILD_ELIGIBLE requires --evidence "
                    "citing concrete proof (verifier/proposer separation — a session "
                    "cannot declare its own threshold crossed without writing down why)."
                )

    entry = dict(entry)
    entry["status"] = new_status

    if new_status == "BUILT":
        if not args.built_as or not args.built_pr:
            raise SystemExit(
                "error: promoting to BUILT requires --built-as and --built-pr"
            )
        entry["built_as"] = args.built_as
        entry["built_pr"] = args.built_pr
        if args.post_build_due:
            entry["post_build_check"] = {
                "due_date": args.post_build_due,
                "procedure": args.post_build_procedure or "Confirm the automation is actually adopted.",
                "result": None,
            }

    rewrite_single_line(log_path, args.id, entry)

    result = {
        "action": "promoted",
        "id": args.id,
        "from_status": current_status,
        "to_status": new_status,
        "evidence": args.evidence,
        "entry": entry,
    }
    return result


# --------------------------------------------------------------------------
# argparse wiring
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="friction_cli.py",
        description="CLI for the operational friction diary (see SCHEMA.md).",
    )
    parser.add_argument(
        "--log", default=DEFAULT_LOG_PATH,
        help=f"path to the JSONL log file (default: {DEFAULT_LOG_PATH})",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # log
    p_log = sub.add_parser("log", help="search for a duplicate, then create a new entry")
    p_log.add_argument("title", help="one-line summary of the friction")
    p_log.add_argument("--match-id", default=None, help="confirm this id as the same friction (delegates to bump)")
    p_log.add_argument("--no-search", action="store_true", help="skip duplicate search, force new-entry path")
    p_log.add_argument("--non-interactive", action="store_true", help="never prompt; require --match-id or --no-search on matches")
    p_log.add_argument("--note", default=None, help="evidence note (used for both new-entry seed and delegated bump)")
    p_log.add_argument("--prefix", default="GAP", help="ID prefix for a new entry (default: GAP)")
    p_log.add_argument("--affected-component", default=None)
    p_log.add_argument("--manual-procedure", default=None)
    p_log.add_argument("--proposed-fix", default=None)
    p_log.add_argument("--severity", default=None, help="severity_signal value (validated against threshold_config on review, not at log time)")
    p_log.add_argument("--recurrence-signal", default="rare", help="qualitative label: daily/weekly/monthly/rare (default: rare)")
    p_log.add_argument("--falsifiability-gate", default=None)
    p_log.add_argument("--domain-extensions", default=None, help="JSON object string for domain_extensions, e.g. '{\"plane\":\"ci-cd\"}'")
    p_log.add_argument(
        "--golden-rule-yes", type=lambda s: s.strip().lower() in ("true", "yes", "1"),
        default=False,
        help="must be explicitly passed as true: 'would this recur next week if nothing changed?'",
    )
    p_log.add_argument("--json", action="store_true", help="machine-readable JSON output")
    p_log.set_defaults(func=cmd_log)

    # bump
    p_bump = sub.add_parser("bump", help="record another occurrence of an existing entry")
    p_bump.add_argument("id", help="entry id, e.g. GAP-3")
    p_bump.add_argument("--note", default=None, help="evidence note for this occurrence")
    p_bump.add_argument("--json", action="store_true")
    p_bump.set_defaults(func=cmd_bump)

    # review
    p_review = sub.add_parser("review", help="recompute build-eligibility and diff against stored status")
    p_review.add_argument("--config", default=DEFAULT_CONFIG_PATH, help=f"path to threshold config (default: {DEFAULT_CONFIG_PATH})")
    p_review.add_argument("--json", action="store_true")
    p_review.set_defaults(func=cmd_review)

    # promote
    p_promote = sub.add_parser("promote", help="move an entry's status forward one step (or off-ramp)")
    p_promote.add_argument("id", help="entry id, e.g. GAP-3")
    p_promote.add_argument("--to", default=None, help="explicit target status; must be the immediate next step, or DISQUALIFIED/DEFERRED")
    p_promote.add_argument("--evidence", default=None, help="required for QUALIFYING -> BUILD_ELIGIBLE: proof supporting the promotion")
    p_promote.add_argument("--built-as", default=None, help="required when promoting to BUILT")
    p_promote.add_argument("--built-pr", default=None, help="required when promoting to BUILT")
    p_promote.add_argument("--post-build-due", default=None, help="due_date (YYYY-MM-DD) for post_build_check, set when promoting to BUILT")
    p_promote.add_argument("--post-build-procedure", default=None, help="procedure text for post_build_check")
    p_promote.add_argument("--json", action="store_true")
    p_promote.set_defaults(func=cmd_promote)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    result = args.func(args)

    if getattr(args, "json", False):
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        if args.command == "review":
            print_review_report(result)
        elif args.command == "log":
            if result.get("delegated_from_log"):
                e = result["entry"]
                print(f"Delegated to bump: {e['id']} now recurrence_count={e['recurrence_count']}, "
                      f"last_seen_date={e['last_seen_date']}")
            else:
                e = result["entry"]
                print(f"Created {e['id']}: {e['title']} (status={e['status']})")
        elif args.command == "bump":
            e = result["entry"]
            print(f"Bumped {e['id']}: recurrence_count={e['recurrence_count']}, "
                  f"last_seen_date={e['last_seen_date']}")
        elif args.command == "promote":
            print(f"Promoted {result['id']}: {result['from_status']} -> {result['to_status']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
