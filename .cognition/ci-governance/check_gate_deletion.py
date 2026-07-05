#!/usr/bin/env python3
"""check_gate_deletion.py - deletion guard, collapsed to a single-file diff.

Under the old three-surface design, a dedicated script diffed the gate-name
SET across three independently hand-edited files (local runner, CI workflow,
parity checker) because any of the three could silently drop a gate. Under
this redesign, gates.yml is the ONE declarative source; gen_ci.py's
generated outputs cannot drift from it (they are regenerated, not
hand-edited). So the only remaining place a gate can silently vanish is
gates.yml itself, across a merge/rebase. This script is that single-file
diff, carried over in spirit (same allowlist semantics, same fail-open
BASE_UNAVAILABLE sentinel) but reduced from a 3-way to a 1-way comparison.

USAGE
-----
    python check_gate_deletion.py --gates gates.yml \\
        --base origin/main --allowlist gate_deletion_allowlist.txt

BEHAVIOR
--------
- Retrieves the base version of --gates via `git show <base>:<path>`.
- Parses both versions with a real YAML loader (not text scraping).
- Diffs the gate NAME sets: base_names - head_names = removed gates.
- For each removed gate, looks it up in the allowlist:
    - No matching entry                          -> HARD FAIL
    - Matching entry, EXPIRED (past expires date) -> HARD FAIL (forces
      cleanup or renewal - an expiry is not a life sentence for the removal,
      it is a deadline to either finish removing all traces or renew)
    - Matching entry, not expired                 -> PASS, printed note
- An allowlist entry whose name is NOT actually missing (still present at
  HEAD) is a WARN (stale allowlist entry, consider pruning) - not a failure.
- A missing `ref=#NNN` token on an otherwise-valid entry is a soft WARN.
- If the base ref cannot be resolved locally (e.g. this checkout never
  fetched it - common on a dev machine that hasn't done `git fetch origin`),
  print the sentinel GATE_DELETION_BASE_UNAVAILABLE and exit 0. This is a
  deliberate fail-OPEN: real enforcement happens in CI, where the base ref is
  always fetched. Locally, a missing base ref must never cause either a
  false HARD FAIL or a silent, unannounced pass - it always prints the
  sentinel so the operator knows enforcement did not run.

ALLOWLIST FILE FORMAT (plain text, one entry per line)
-------------------------------------------------------
    <gate-name> | <justification> [| expires=YYYY-MM-DD] [| ref=#NNN]

Blank lines and lines starting with # are ignored.
"""
from __future__ import annotations

import argparse
import datetime
import subprocess
import sys
from pathlib import Path

import yaml

BASE_UNAVAILABLE_SENTINEL = "GATE_DELETION_BASE_UNAVAILABLE"


class AllowlistEntry:
    __slots__ = ("name", "justification", "expires", "ref", "raw_line")

    def __init__(self, name: str, justification: str, expires: str | None, ref: str | None, raw_line: str):
        self.name = name
        self.justification = justification
        self.expires = expires
        self.ref = ref
        self.raw_line = raw_line

    def is_expired(self, today: datetime.date) -> bool:
        if not self.expires:
            return False
        try:
            expiry_date = datetime.datetime.strptime(self.expires, "%Y-%m-%d").date()
        except ValueError:
            # Malformed expiry date - treat as expired (fail closed) since we
            # cannot verify it is still valid.
            return True
        return today > expiry_date


def parse_allowlist(path: Path) -> dict[str, AllowlistEntry]:
    entries: dict[str, AllowlistEntry] = {}
    if not path.exists():
        return entries

    with open(path, "r", encoding="utf-8") as f:
        for lineno, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 2:
                print(
                    f"WARN: allowlist line {lineno} malformed (need at least 'name | justification'): {line!r}",
                    file=sys.stderr,
                )
                continue
            name = parts[0]
            justification = parts[1]
            expires = None
            ref = None
            for extra in parts[2:]:
                if extra.startswith("expires="):
                    expires = extra.split("=", 1)[1]
                elif extra.startswith("ref="):
                    ref = extra.split("=", 1)[1]
            entries[name] = AllowlistEntry(name, justification, expires, ref, line)
    return entries


def load_gate_names_from_text(yaml_text: str) -> set[str]:
    doc = yaml.safe_load(yaml_text)
    if not doc:
        return set()
    return {g["name"] for g in doc.get("gates", [])}


def git_show(base_ref: str, path: str, cwd: Path | None = None) -> str | None:
    """Return file contents at base_ref:path, or None if unresolvable."""
    try:
        result = subprocess.run(
            ["git", "show", f"{base_ref}:{path}"],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gates", required=True, type=Path, help="Path to gates.yml (HEAD/working-tree version)")
    parser.add_argument("--base", default="origin/main", help="Base ref to compare against (default: origin/main)")
    parser.add_argument("--allowlist", type=Path, default=None, help="Path to allowlist file")
    parser.add_argument("--repo-root", type=Path, default=None, help="Repo root for git commands (default: cwd)")
    parser.add_argument("--today", default=None, help="Override today's date (YYYY-MM-DD) for testing expiry logic")
    args = parser.parse_args(argv)

    if args.today:
        today = datetime.datetime.strptime(args.today, "%Y-%m-%d").date()
    else:
        today = datetime.date.today()

    # Resolve path relative to repo root for `git show <ref>:<path>` (git
    # wants a path relative to the repo root, not the cwd, in general -
    # but since we invoke with cwd=repo_root, a relative path from there works).
    repo_root = args.repo_root or Path.cwd()
    try:
        gates_path_for_git = str(args.gates.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        gates_path_for_git = str(args.gates)

    base_text = git_show(args.base, gates_path_for_git, cwd=repo_root)
    if base_text is None:
        print(BASE_UNAVAILABLE_SENTINEL)
        print(
            f"note: could not resolve '{args.base}:{gates_path_for_git}' locally. "
            "This is expected on a dev machine that hasn't fetched the base ref. "
            "Fail-open locally; CI always fetches the base ref and enforces this for real.",
            file=sys.stderr,
        )
        return 0

    if not args.gates.exists():
        print(f"ERROR: --gates path does not exist at HEAD: {args.gates}", file=sys.stderr)
        return 1

    head_text = args.gates.read_text(encoding="utf-8")

    base_names = load_gate_names_from_text(base_text)
    head_names = load_gate_names_from_text(head_text)

    removed = base_names - head_names
    allowlist = parse_allowlist(args.allowlist) if args.allowlist else {}

    hard_failures: list[str] = []
    warnings: list[str] = []
    passes: list[str] = []

    for name in sorted(removed):
        entry = allowlist.get(name)
        if entry is None:
            hard_failures.append(
                f"gate '{name}' was removed from {args.gates} (present at {args.base}, "
                f"absent at HEAD) with NO matching allowlist entry."
            )
            continue

        if entry.is_expired(today):
            hard_failures.append(
                f"gate '{name}' removal's allowlist entry has EXPIRED "
                f"(expires={entry.expires}, today={today.isoformat()}). "
                f"Either finish removing all traces of '{name}' and delete this allowlist "
                f"line, or renew it with a new expires= date. Entry: {entry.raw_line!r}"
            )
            continue

        note = f"gate '{name}' removal ALLOWED: {entry.justification}"
        if entry.expires:
            note += f" (expires={entry.expires})"
        if entry.ref:
            note += f" (ref={entry.ref})"
        else:
            warnings.append(
                f"allowlist entry for '{name}' has no ref=#NNN token - consider adding one "
                f"for traceability (soft warning, not a failure)."
            )
        passes.append(note)

    # Stale allowlist entries: allowlisted names that are NOT actually missing.
    for name, entry in allowlist.items():
        if name not in removed:
            warnings.append(
                f"allowlist entry for '{name}' is STALE - gate is still present at HEAD "
                f"(not actually removed). Consider pruning this line. Entry: {entry.raw_line!r}"
            )

    for p in passes:
        print(f"PASS: {p}")
    for w in warnings:
        print(f"WARN: {w}")

    if hard_failures:
        print("\nGATE_DELETION_HARD_FAIL:", file=sys.stderr)
        for f in hard_failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print(
        f"check_gate_deletion: OK - {len(removed)} removal(s), all allowlisted "
        f"({len(warnings)} warning(s))."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
