#!/usr/bin/env python3
"""
tests/test_claims_cli_self.py — self-test for the concurrency claims registry.

Runs claims_cli.py as a subprocess against a fresh temp directory (so it
never touches the real .cognition/active-work/), asserting on stdout, exit
codes, and the resulting claim-file JSON.

Run directly:
    python tests/test_claims_cli_self.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "claims_cli.py"

FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        FAILURES.append(message)
        print(f"  FAIL: {message}")
    else:
        print(f"  ok:   {message}")


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), "--dir", "claims"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        cwd = Path(tmp)

        print("CASE 1: claim a fresh task-slug succeeds, no overlap")
        r = run(
            [
                "claim", "task-a", "--owner", "alice",
                "--scope", "spine/cc_spine/dashboard.py", "spine/cc_spine/quiz.py",
                "--branch", "claude/task-a", "--json",
            ],
            cwd,
        )
        check(r.returncode == 0, f"claim task-a exits 0 (got {r.returncode}, stderr={r.stderr!r})")
        payload = json.loads(r.stdout) if r.stdout.strip() else {}
        check(payload.get("action") == "claimed", "claim task-a reports action=claimed")
        check(payload.get("overlaps") == [], "claim task-a reports no overlaps (nothing else active yet)")
        check((cwd / "claims" / "task-a.json").exists(), "claims/task-a.json was written")

        print("\nCASE 2: claiming an overlapping scope for a different task reports it and exits 1")
        r = run(
            [
                "claim", "task-b", "--owner", "bob",
                "--scope", "spine/cc_spine/dashboard.py",
                "--branch", "claude/task-b", "--json",
            ],
            cwd,
        )
        check(r.returncode == 1, f"claim task-b (overlapping) exits 1 (got {r.returncode})")
        payload = json.loads(r.stdout) if r.stdout.strip() else {}
        overlaps = payload.get("overlaps", [])
        check(len(overlaps) == 1, f"claim task-b reports exactly one overlapping claim (got {len(overlaps)})")
        if overlaps:
            check(overlaps[0]["other_task_slug"] == "task-a", "the reported overlap is against task-a")
            check(
                ["spine/cc_spine/dashboard.py", "spine/cc_spine/dashboard.py"] in [list(p) for p in overlaps[0]["overlapping_paths"]],
                "the overlapping path pair is the shared file",
            )
        check((cwd / "claims" / "task-b.json").exists(), "claims/task-b.json was still written despite the overlap warning")

        print("\nCASE 3: claiming a genuinely non-overlapping scope reports no overlap")
        r = run(
            [
                "claim", "task-c", "--owner", "carol",
                "--scope", "spine/cc_spine/factstore.py",
                "--branch", "claude/task-c", "--json",
            ],
            cwd,
        )
        check(r.returncode == 0, f"claim task-c (non-overlapping) exits 0 (got {r.returncode})")
        payload = json.loads(r.stdout) if r.stdout.strip() else {}
        check(payload.get("overlaps") == [], "claim task-c reports no overlaps")

        print("\nCASE 4: directory-scope overlaps a file inside it")
        r = run(
            [
                "claim", "task-d", "--owner", "dave",
                "--scope", "spine/cc_spine/",
                "--branch", "claude/task-d", "--json",
            ],
            cwd,
        )
        payload = json.loads(r.stdout) if r.stdout.strip() else {}
        check(r.returncode == 1, f"claim task-d (dir overlaps existing files) exits 1 (got {r.returncode})")
        check(len(payload.get("overlaps", [])) >= 1, "claim task-d reports at least one directory-vs-file overlap")

        print("\nCASE 5: `status` lists all active claims and every overlapping pair")
        r = run(["status", "--json"], cwd)
        check(r.returncode == 0, f"status exits 0 (got {r.returncode})")
        payload = json.loads(r.stdout)
        check(len(payload["active_claims"]) == 4, f"status sees all 4 active claims (got {len(payload['active_claims'])})")
        check(len(payload["overlaps"]) >= 2, f"status reports at least 2 overlapping pairs (got {len(payload['overlaps'])})")

        print("\nCASE 6: `release` archives the claim and removes it from active status")
        r = run(["release", "task-b"], cwd)
        check(r.returncode == 0, f"release task-b exits 0 (got {r.returncode})")
        check(not (cwd / "claims" / "task-b.json").exists(), "claims/task-b.json no longer active after release")
        check((cwd / "claims" / "archive" / "task-b.json").exists(), "claims/archive/task-b.json exists after release")

        r = run(["status", "--json"], cwd)
        payload = json.loads(r.stdout)
        slugs = {c["task_slug"] for c in payload["active_claims"]}
        check("task-b" not in slugs, "status no longer lists task-b as active after release")
        check(len(slugs) == 3, f"status now sees 3 active claims (got {len(slugs)})")

        print("\nCASE 7: re-claiming an already-active task-slug without --force is refused")
        r = run(
            ["claim", "task-a", "--owner", "eve", "--scope", "unrelated/path.py"],
            cwd,
        )
        check(r.returncode != 0, "re-claiming an active task-slug without --force fails")
        check("--force" in r.stderr, "the error message mentions --force as the escape hatch")

        print("\nCASE 8: invalid task-slug is rejected")
        r = run(["claim", "Not_A_Valid_Slug", "--owner", "x", "--scope", "y.py"], cwd)
        check(r.returncode != 0, "an invalid task-slug is rejected")

    print()
    if FAILURES:
        print(f"SELF-TEST FAILED: {len(FAILURES)} check(s) failed.")
        return 1
    print("SELF-TEST PASSED: all cases behaved as expected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
