#!/usr/bin/env python3
"""
tests/test_friction_cli_self.py — self-test for the friction diary tooling.

Runs friction_cli.py and friction_render.py as subprocesses against a fresh
temp directory (so it never touches the real friction_log.jsonl / example
files), asserting on stdout, exit codes, and the resulting JSONL content.

Run directly:
    python tests/test_friction_cli_self.py

Or via pytest if available:
    pytest tests/test_friction_cli_self.py -v
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "friction_cli.py"
RENDER = REPO_ROOT / "friction_render.py"

FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        FAILURES.append(message)
        print(f"  FAIL: {message}")
    else:
        print(f"  ok:   {message}")


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(args[0])] + args[1:],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def read_jsonl(path: Path) -> list[dict]:
    entries = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        log_path = tmp_path / "friction_log.jsonl"
        config_path = tmp_path / "threshold_config.yml"

        config_path.write_text(
            textwrap.dedent(
                """
                severity_values:
                  - critical_path
                  - normal
                  - low
                required_severity_values:
                  - critical_path
                min_recurrence_count: 3
                min_days_between_first_and_last: 7
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

        # --------------------------------------------------------------
        # Step 1: `log` creates 2 entries; golden_rule false is refused.
        # --------------------------------------------------------------
        print("\n[1] log: create entry with golden_rule_answer true")
        result = run(
            [
                CLI, "--log", str(log_path), "log", "Manual DB URL reconstruction in container",
                "--non-interactive",
                "--golden-rule-yes", "true",
                "--affected-component", "checkout-service container",
                "--manual-procedure", "reconstruct DATABASE_URL by hand from the secret file",
                "--proposed-fix", "wrapper script that exports DATABASE_URL automatically",
                "--severity", "critical_path",
                "--falsifiability-gate", "if this stops recurring over 30 days",
                "--prefix", "GAP",
            ],
            cwd=tmp_path,
        )
        check(result.returncode == 0, f"first log call exits 0 (got {result.returncode}, stderr={result.stderr!r})")
        check("Created GAP-1" in result.stdout, f"stdout confirms GAP-1 created (stdout={result.stdout!r})")
        check(log_path.exists(), "log file was created")

        print("\n[2] log: golden_rule_answer false is REFUSED")
        result = run(
            [
                CLI, "--log", str(log_path), "log", "One-off forensic investigation of outage",
                "--non-interactive",
                "--golden-rule-yes", "false",
                "--affected-component", "payments consumer",
                "--manual-procedure", "manual restart during a one-time outage",
                "--proposed-fix", "n/a",
                "--severity", "low",
                "--falsifiability-gate", "n/a",
            ],
            cwd=tmp_path,
        )
        check(result.returncode != 0, f"golden_rule_answer=false is refused (exit={result.returncode})")
        check("Refusing to create entry" in result.stderr, "refusal message printed to stderr")
        check(
            "file it as incident documentation" in result.stderr,
            "refusal redirects user to file one-off work elsewhere",
        )

        entries_after_refusal = read_jsonl(log_path)
        check(
            len(entries_after_refusal) == 1,
            f"refused entry was NOT appended to the log (found {len(entries_after_refusal)} entries, expected 1)",
        )

        print("\n[2b] log: create a second, distinct entry (for a clean multi-entry log)")
        result = run(
            [
                CLI, "--log", str(log_path), "log", "Manual TLS cert rotation on staging ingress",
                "--non-interactive",
                "--golden-rule-yes", "true",
                "--affected-component", "staging ingress gateway",
                "--manual-procedure", "manually rotate cert via cloud console",
                "--proposed-fix", "automate rotation via ACME client cronjob",
                "--severity", "normal",
                "--falsifiability-gate", "if rotation is not needed again in 60 days",
            ],
            cwd=tmp_path,
        )
        check(result.returncode == 0, f"second log call exits 0 (got {result.returncode})")
        check("Created GAP-2" in result.stdout, f"stdout confirms GAP-2 created (id derived as max+1) (stdout={result.stdout!r})")

        entries = read_jsonl(log_path)
        check(len(entries) == 2, f"log file has exactly 2 entries after refusal + 2 creates (found {len(entries)})")

        # --------------------------------------------------------------
        # Step 2: duplicate-detection path — matching title should
        # surface GAP-1 as a candidate and refuse silent creation.
        # --------------------------------------------------------------
        print("\n[3] log: near-duplicate title triggers match surfacing + refusal (non-interactive, no --match-id)")
        result = run(
            [
                CLI, "--log", str(log_path), "log", "Manual reconstruction of DB URL in the container",
                "--non-interactive",
                "--golden-rule-yes", "true",
                "--affected-component", "checkout-service container",
                "--manual-procedure", "same as before",
                "--proposed-fix", "z",
                "--severity", "critical_path",
                "--falsifiability-gate", "g",
            ],
            cwd=tmp_path,
        )
        check(result.returncode != 0, f"near-duplicate title without --match-id is refused (exit={result.returncode})")
        check("GAP-1" in result.stderr, "GAP-1 surfaced as a candidate match")
        check("--match-id" in result.stderr, "message tells user how to confirm the match")

        entries = read_jsonl(log_path)
        check(len(entries) == 2, "no new entry was created by the ambiguous near-duplicate attempt")

        # --------------------------------------------------------------
        # Step 3: bump GAP-1 three times to push recurrence_count to 4,
        # with dates spread far enough apart to also clear the
        # min_days_between_first_and_last gate. We directly edit
        # created_date backward to simulate a multi-week spread without
        # sleeping in the test.
        # --------------------------------------------------------------
        print("\n[4] bump: push GAP-1 recurrence_count from 1 -> 4 (3 bumps)")

        # Backdate GAP-1's created_date so that once we bump (which sets
        # last_seen_date to "today"), the elapsed-day gate is satisfied.
        entries = read_jsonl(log_path)
        for e in entries:
            if e["id"] == "GAP-1":
                e["created_date"] = "2026-06-01"
                e["evidence_log"][0]["date"] = "2026-06-01"
        with log_path.open("w", encoding="utf-8", newline="\n") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        for i in range(3):
            result = run(
                [CLI, "--log", str(log_path), "bump", "GAP-1", "--note", f"recurrence #{i + 2}"],
                cwd=tmp_path,
            )
            check(result.returncode == 0, f"bump #{i + 1} on GAP-1 exits 0 (got {result.returncode})")

        entries = read_jsonl(log_path)
        gap1 = next(e for e in entries if e["id"] == "GAP-1")
        check(gap1["recurrence_count"] == 4, f"GAP-1 recurrence_count is 4 after 3 bumps (got {gap1['recurrence_count']})")
        check(len(gap1["evidence_log"]) == 4, f"GAP-1 evidence_log has 4 entries (got {len(gap1['evidence_log'])})")

        gap2 = next(e for e in entries if e["id"] == "GAP-2")
        check(
            gap2["recurrence_count"] == 1 and len(gap2["evidence_log"]) == 1,
            "bump on GAP-1 did NOT mutate GAP-2's line (targeted line replace, not full-file rewrite)",
        )

        # --------------------------------------------------------------
        # Step 4: review should flag GAP-1 as drift: stored=CANDIDATE,
        # but recurrence_count=4 >= 3, severity=critical_path (required),
        # and days_span (2026-06-01 -> today, 2026-07-05) >= 7.
        # GAP-1's status was never explicitly promoted, so it is still
        # CANDIDATE in storage -- this is exactly the drift review exists
        # to catch (spec calls for "still marked QUALIFYING"; our GAP-1
        # is still CANDIDATE, which is the same drift class: stored status
        # lags the recomputed formula).
        # --------------------------------------------------------------
        print("\n[5] review: recompute build-eligibility, expect GAP-1 flagged as drift")
        result = run(
            [CLI, "--log", str(log_path), "review", "--config", str(config_path), "--json"],
            cwd=tmp_path,
        )
        check(result.returncode == 0, f"review exits 0 (got {result.returncode}, stderr={result.stderr!r})")
        review_json = json.loads(result.stdout)
        flagged_ids = [d["id"] for d in review_json["flagged"]]
        check("GAP-1" in flagged_ids, f"GAP-1 is flagged as drift by review (flagged={flagged_ids})")

        gap1_diff = next(d for d in review_json["diffs"] if d["id"] == "GAP-1")
        check(
            gap1_diff["recomputed_status"] == "BUILD_ELIGIBLE",
            f"review recomputes GAP-1 as BUILD_ELIGIBLE (got {gap1_diff['recomputed_status']})",
        )
        check(
            gap1_diff["stored_status"] == "CANDIDATE",
            f"review reports GAP-1's stored status is still CANDIDATE, i.e. un-promoted (got {gap1_diff['stored_status']})",
        )

        # review must NOT mutate the log.
        entries_after_review = read_jsonl(log_path)
        gap1_after_review = next(e for e in entries_after_review if e["id"] == "GAP-1")
        check(
            gap1_after_review["status"] == "CANDIDATE",
            "review did not mutate GAP-1's stored status (read-only, as required)",
        )

        # --------------------------------------------------------------
        # Step 5: promote through the lifecycle; confirm state-skipping
        # is refused; confirm QUALIFYING->BUILD_ELIGIBLE requires
        # --evidence; confirm BUILT requires --built-as/--built-pr.
        # --------------------------------------------------------------
        print("\n[6] promote: state-skipping is refused")
        result = run(
            [CLI, "--log", str(log_path), "promote", "GAP-1", "--to", "BUILD_ELIGIBLE"],
            cwd=tmp_path,
        )
        check(result.returncode != 0, f"CANDIDATE -> BUILD_ELIGIBLE direct skip is refused (exit={result.returncode})")
        check("one step at a time" in result.stderr, "refusal explains one-step-at-a-time rule")

        print("\n[7] promote: CANDIDATE -> QUALIFYING (one valid step)")
        result = run([CLI, "--log", str(log_path), "promote", "GAP-1"], cwd=tmp_path)
        check(result.returncode == 0, f"CANDIDATE -> QUALIFYING promotion succeeds (exit={result.returncode})")
        check("CANDIDATE -> QUALIFYING" in result.stdout, "stdout confirms the transition")

        print("\n[8] promote: QUALIFYING -> BUILD_ELIGIBLE without --evidence is refused")
        result = run([CLI, "--log", str(log_path), "promote", "GAP-1"], cwd=tmp_path)
        check(result.returncode != 0, f"promotion without --evidence is refused (exit={result.returncode})")
        check("--evidence" in result.stderr, "refusal message names --evidence as required")

        print("\n[9] promote: QUALIFYING -> BUILD_ELIGIBLE with --evidence succeeds")
        result = run(
            [
                CLI, "--log", str(log_path), "promote", "GAP-1",
                "--evidence", "review run confirms recurrence_count=4, severity=critical_path, days_span>=7",
            ],
            cwd=tmp_path,
        )
        check(result.returncode == 0, f"promotion with --evidence succeeds (exit={result.returncode})")
        check("QUALIFYING -> BUILD_ELIGIBLE" in result.stdout, "stdout confirms the transition")

        print("\n[10] promote: BUILD_ELIGIBLE -> BUILT without --built-as/--built-pr is refused")
        result = run([CLI, "--log", str(log_path), "promote", "GAP-1"], cwd=tmp_path)
        check(result.returncode != 0, f"promotion to BUILT without required flags is refused (exit={result.returncode})")

        print("\n[11] promote: BUILD_ELIGIBLE -> BUILT with required flags + post_build_check succeeds")
        result = run(
            [
                CLI, "--log", str(log_path), "promote", "GAP-1",
                "--built-as", "scripts/db_env_wrapper.sh",
                "--built-pr", "PR-501",
                "--post-build-due", "2026-08-01",
                "--post-build-procedure", "confirm engineers use the wrapper on next 3 container debug sessions",
            ],
            cwd=tmp_path,
        )
        check(result.returncode == 0, f"promotion to BUILT succeeds (exit={result.returncode})")
        check("BUILD_ELIGIBLE -> BUILT" in result.stdout, "stdout confirms the transition")

        print("\n[12] promote: already-BUILT entry refuses further promotion")
        result = run([CLI, "--log", str(log_path), "promote", "GAP-1"], cwd=tmp_path)
        check(result.returncode != 0, f"promoting past BUILT is refused (exit={result.returncode})")

        entries = read_jsonl(log_path)
        gap1_final = next(e for e in entries if e["id"] == "GAP-1")
        check(gap1_final["status"] == "BUILT", f"GAP-1 final status is BUILT (got {gap1_final['status']})")
        check(gap1_final["built_as"] == "scripts/db_env_wrapper.sh", "built_as recorded correctly")
        check(gap1_final["built_pr"] == "PR-501", "built_pr recorded correctly")
        check(
            gap1_final["post_build_check"] is not None and gap1_final["post_build_check"]["due_date"] == "2026-08-01",
            "post_build_check recorded with correct due_date",
        )

        # --------------------------------------------------------------
        # Step 6: render, confirm expected content appears.
        # --------------------------------------------------------------
        print("\n[13] friction_render.py: render markdown and check expected content")
        out_md = tmp_path / "FRICTION_DIARY.md"
        result = run(
            [
                RENDER, "--log", str(log_path), "--config", str(config_path), "--out", str(out_md),
            ],
            cwd=tmp_path,
        )
        check(result.returncode == 0, f"friction_render.py exits 0 (got {result.returncode}, stderr={result.stderr!r})")
        check(out_md.exists(), "FRICTION_DIARY.md was created")

        md_text = out_md.read_text(encoding="utf-8")
        check("GENERATED FILE" in md_text, "generated-file header comment present")
        check("DO NOT HAND-EDIT" in md_text, "do-not-hand-edit warning present")
        check("GAP-1" in md_text, "GAP-1 appears in rendered output")
        check("GAP-2" in md_text, "GAP-2 appears in rendered output")
        check("scripts/db_env_wrapper.sh" in md_text, "built_as value appears in rendered output")
        check("PR-501" in md_text, "built_pr value appears in rendered output")
        check("Rollup" in md_text, "rollup table section present")
        # GAP-1 is now BUILT, so it should NOT appear in the active rollup table,
        # only GAP-2 (still CANDIDATE) should.
        rollup_section = md_text.split("## All entries")[0]
        check(
            "GAP-2" in rollup_section and "| GAP-1 |" not in rollup_section,
            "rollup table includes only non-BUILT/non-DISQUALIFIED entries (GAP-2 present, GAP-1 excluded)",
        )

    print()
    if FAILURES:
        print(f"=== {len(FAILURES)} FAILURE(S) ===")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("=== ALL CHECKS PASSED ===")
    return 0


def test_friction_cli_self() -> None:
    """pytest entry point — wraps main() and asserts a clean run.

    The bulk of this file is written as a standalone script (see main())
    so it can also be run directly with `python tests/test_friction_cli_self.py`
    for quick iteration without a pytest install. This wrapper just makes it
    additionally discoverable by `pytest`.
    """
    FAILURES.clear()
    exit_code = main()
    assert exit_code == 0, f"self-test had failures: {FAILURES}"


if __name__ == "__main__":
    raise SystemExit(main())
