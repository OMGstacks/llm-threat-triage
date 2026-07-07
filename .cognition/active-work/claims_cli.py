#!/usr/bin/env python3
"""
claims_cli.py — CLI for the concurrency claims registry.

Operates on one committed JSON file per active task under a claims
directory (default: .cognition/active-work/ next to this script, overridable
via --dir). This is the "don't clobber" signal `_shared/concurrency-check.md`
says is missing: a live, git-native registry of who is working on what,
readable via a plain `git fetch` from any checkout, instead of a manual
grep-open-PRs-and-branches protocol.

Subcommands:
    claim   <task-slug>   Write a new claim file. Reports (does not block on)
                          any overlap with other currently-active claims'
                          files_scope, so the caller sees a collision the
                          moment they try to claim conflicting scope.
    release <task-slug>   Archive the claim file (move to archive/, never a
                          silent delete -- claim history is worth keeping).
    status                List all currently-active (unexpired) claims and
                          flag every pair whose files_scope overlaps -- the
                          actual clobber-prevention check.

Design notes:
    - Git-native, no lock server: a claim is just a committed JSON file.
      Two sessions racing to claim the same scope will see each other's
      claim as soon as they `git fetch` -- the registry's freshness is only
      as good as the last fetch, same limitation as the manual grep
      protocol it replaces, but now machine-checkable instead of
      easy-to-forget.
    - One file per task, one task per file: `rewrite_single_line`-style
      surgical writes don't apply here (JSON, not JSONL) but each claim's
      file is independent, so concurrent claims for *different* tasks never
      touch the same file and can't merge-conflict with each other.
    - `release` archives rather than deletes, mirroring the friction diary's
      "don't silently destroy institutional memory" convention -- a record
      of what was claimed and when is cheap to keep and useful for
      post-hoc "who touched this" questions.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

DEFAULT_CLAIMS_DIR = ".cognition/active-work"
DEFAULT_TTL_HOURS = 24

REQUIRED_FIELDS = [
    "task_slug", "owner", "session_id", "task_description", "branch",
    "files_scope", "claimed_at", "expires_at",
]

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


# --------------------------------------------------------------------------
# I/O helpers
# --------------------------------------------------------------------------

def claim_path(claims_dir: Path, task_slug: str) -> Path:
    return claims_dir / f"{task_slug}.json"


def archive_path(claims_dir: Path, task_slug: str) -> Path:
    return claims_dir / "archive" / f"{task_slug}.json"


def read_claim(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_claim(path: Path, claim: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(claim, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def list_active_claim_files(claims_dir: Path) -> list[Path]:
    """Every *.json directly under claims_dir, excluding archive/."""
    if not claims_dir.exists():
        return []
    return sorted(p for p in claims_dir.glob("*.json") if p.is_file())


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def is_expired(claim: dict[str, Any], at: Optional[datetime] = None) -> bool:
    at = at or now_utc()
    return parse_iso(claim["expires_at"]) <= at


def validate_slug(task_slug: str) -> None:
    if not _SLUG_RE.match(task_slug):
        raise SystemExit(
            f"error: task-slug {task_slug!r} must be lowercase alphanumeric "
            f"segments separated by single hyphens (e.g. 'slice-4-claims-registry')"
        )


def validate_claim_shape(claim: dict[str, Any]) -> None:
    missing = [f for f in REQUIRED_FIELDS if f not in claim]
    if missing:
        raise SystemExit(f"error: claim missing required fields: {missing}")


# --------------------------------------------------------------------------
# Overlap detection
# --------------------------------------------------------------------------

def _normalize_scope_path(p: str) -> str:
    """Strip a trailing slash so a directory scope and a file scope compare
    consistently; leave everything else (including case) untouched --
    filesystem paths are case-sensitive on the platforms this runs on."""
    p = p.strip().replace("\\", "/")
    while len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    return p


def _paths_overlap(a: str, b: str) -> bool:
    """True if `a` and `b` name the same file, or one names a directory that
    contains the other (prefix-of-a-path-segment, not a bare string prefix --
    'spine/cc' must not "overlap" 'spine/cc_spine/x.py')."""
    a, b = _normalize_scope_path(a), _normalize_scope_path(b)
    if a == b:
        return True
    return a.startswith(b + "/") or b.startswith(a + "/")


def scope_overlap(scope_a: list[str], scope_b: list[str]) -> list[tuple[str, str]]:
    """Every (path_a, path_b) pair from the two scopes that overlaps."""
    pairs = []
    for a in scope_a:
        for b in scope_b:
            if _paths_overlap(a, b):
                pairs.append((a, b))
    return pairs


@dataclass
class OverlapReport:
    other_task_slug: str
    other_owner: str
    overlapping_paths: list[tuple[str, str]] = field(default_factory=list)


def find_overlaps(
    target_slug: str, target_scope: list[str], other_claims: list[dict[str, Any]]
) -> list[OverlapReport]:
    reports = []
    for other in other_claims:
        if other["task_slug"] == target_slug:
            continue
        pairs = scope_overlap(target_scope, other["files_scope"])
        if pairs:
            reports.append(
                OverlapReport(
                    other_task_slug=other["task_slug"],
                    other_owner=other["owner"],
                    overlapping_paths=pairs,
                )
            )
    return reports


# --------------------------------------------------------------------------
# Subcommand: claim
# --------------------------------------------------------------------------

def cmd_claim(args: argparse.Namespace) -> dict[str, Any]:
    claims_dir = Path(args.dir)
    validate_slug(args.task_slug)
    path = claim_path(claims_dir, args.task_slug)

    if path.exists() and not args.force:
        existing = read_claim(path)
        if not is_expired(existing):
            raise SystemExit(
                f"error: an active, unexpired claim already exists for "
                f"{args.task_slug!r} (owner={existing['owner']}, "
                f"expires_at={existing['expires_at']}). Pass --force to "
                f"overwrite, or `release` it first."
            )

    claimed_at = now_utc()
    expires_at = claimed_at + timedelta(hours=args.ttl_hours)

    new_claim = {
        "task_slug": args.task_slug,
        "owner": args.owner,
        "session_id": args.session_id,
        "task_description": args.description or "",
        "branch": args.branch,
        "files_scope": [_normalize_scope_path(p) for p in args.scope],
        "claimed_at": claimed_at.isoformat(),
        "expires_at": expires_at.isoformat(),
    }
    validate_claim_shape(new_claim)

    others = [
        read_claim(p) for p in list_active_claim_files(claims_dir) if p != path
    ]
    others = [c for c in others if not is_expired(c)]
    overlaps = find_overlaps(args.task_slug, new_claim["files_scope"], others)

    write_claim(path, new_claim)

    return {
        "action": "claimed",
        "claim": new_claim,
        "overlaps": [
            {
                "other_task_slug": o.other_task_slug,
                "other_owner": o.other_owner,
                "overlapping_paths": o.overlapping_paths,
            }
            for o in overlaps
        ],
    }


# --------------------------------------------------------------------------
# Subcommand: release
# --------------------------------------------------------------------------

def cmd_release(args: argparse.Namespace) -> dict[str, Any]:
    claims_dir = Path(args.dir)
    path = claim_path(claims_dir, args.task_slug)
    if not path.exists():
        raise SystemExit(f"error: no active claim found for {args.task_slug!r} at {path}")

    claim = read_claim(path)
    dest = archive_path(claims_dir, args.task_slug)
    dest.parent.mkdir(parents=True, exist_ok=True)
    claim["released_at"] = now_utc().isoformat()
    write_claim(dest, claim)
    path.unlink()

    return {"action": "released", "task_slug": args.task_slug, "archived_to": str(dest)}


# --------------------------------------------------------------------------
# Subcommand: status
# --------------------------------------------------------------------------

def cmd_status(args: argparse.Namespace) -> dict[str, Any]:
    claims_dir = Path(args.dir)
    files = list_active_claim_files(claims_dir)
    all_claims = [read_claim(p) for p in files]

    if args.include_expired:
        active = all_claims
    else:
        active = [c for c in all_claims if not is_expired(c)]

    overlap_reports: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for claim in active:
        for report in find_overlaps(claim["task_slug"], claim["files_scope"], active):
            pair_key = tuple(sorted([claim["task_slug"], report.other_task_slug]))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            overlap_reports.append(
                {
                    "task_a": claim["task_slug"],
                    "task_b": report.other_task_slug,
                    "owner_a": claim["owner"],
                    "owner_b": report.other_owner,
                    "overlapping_paths": report.overlapping_paths,
                }
            )

    return {"active_claims": active, "overlaps": overlap_reports}


def print_status_report(result: dict[str, Any]) -> None:
    claims = result["active_claims"]
    overlaps = result["overlaps"]
    print(f"{len(claims)} active claim(s):")
    for c in claims:
        print(
            f"  [{c['task_slug']}] owner={c['owner']} branch={c['branch']} "
            f"expires_at={c['expires_at']}"
        )
        for p in c["files_scope"]:
            print(f"      scope: {p}")
    print()
    if overlaps:
        print(f"{len(overlaps)} overlapping claim pair(s) -- CLOBBER RISK:")
        for o in overlaps:
            print(f"  [{o['task_a']}] (owner={o['owner_a']}) overlaps "
                  f"[{o['task_b']}] (owner={o['owner_b']}):")
            for a, b in o["overlapping_paths"]:
                print(f"      {a}  <->  {b}")
    else:
        print("No overlaps -- no clobber risk detected among active claims.")


# --------------------------------------------------------------------------
# argparse wiring
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="claims_cli.py",
        description="CLI for the concurrency claims registry (see this file's module docstring).",
    )
    parser.add_argument(
        "--dir", default=DEFAULT_CLAIMS_DIR,
        help=f"path to the claims directory (default: {DEFAULT_CLAIMS_DIR})",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_claim = sub.add_parser("claim", help="claim a task's file scope")
    p_claim.add_argument("task_slug", help="lowercase-hyphenated task identifier, e.g. slice-4-claims-registry")
    p_claim.add_argument("--owner", required=True, help="human or session identifier making the claim")
    p_claim.add_argument("--scope", nargs="+", required=True, help="one or more repo-relative paths (files or directories) this task will touch")
    p_claim.add_argument("--description", default=None, help="one-line task description")
    p_claim.add_argument("--session-id", default=None, help="session identifier, if available")
    p_claim.add_argument("--branch", default=None, help="branch this task is working on")
    p_claim.add_argument("--ttl-hours", type=float, default=DEFAULT_TTL_HOURS, help=f"hours until this claim expires (default: {DEFAULT_TTL_HOURS})")
    p_claim.add_argument("--force", action="store_true", help="overwrite an existing unexpired claim for this task-slug")
    p_claim.add_argument("--json", action="store_true")
    p_claim.set_defaults(func=cmd_claim)

    p_release = sub.add_parser("release", help="archive a claim (remove it from the active set)")
    p_release.add_argument("task_slug")
    p_release.add_argument("--json", action="store_true")
    p_release.set_defaults(func=cmd_release)

    p_status = sub.add_parser("status", help="list active claims and flag overlaps")
    p_status.add_argument("--include-expired", action="store_true", help="also list expired claims still present in the directory")
    p_status.add_argument("--json", action="store_true")
    p_status.set_defaults(func=cmd_status)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    result = args.func(args)

    if getattr(args, "json", False):
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        if args.command == "claim":
            c = result["claim"]
            print(f"Claimed {c['task_slug']!r} for {c['owner']} (expires_at={c['expires_at']})")
            for p in c["files_scope"]:
                print(f"  scope: {p}")
            if result["overlaps"]:
                print(f"\nWARNING: {len(result['overlaps'])} overlapping active claim(s):")
                for o in result["overlaps"]:
                    print(f"  overlaps [{o['other_task_slug']}] (owner={o['other_owner']}):")
                    for a, b in o["overlapping_paths"]:
                        print(f"      {a}  <->  {b}")
        elif args.command == "release":
            print(f"Released {result['task_slug']!r} -> archived to {result['archived_to']}")
        elif args.command == "status":
            print_status_report(result)

    if args.command == "claim" and result["overlaps"]:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
