#!/usr/bin/env python3
"""tests/test_memory_decay_self.py

Embedded self-test for check_memory_decay.py.

Builds a temporary scratch git repo with one real file (containing one real
function), then a temporary markdown "memory" file that references:

    (a) that real file and function             -> should PASS (no finding)
    (b) a path that never existed                -> should HARD FAIL as
                                                     PATH_NEVER_EXISTED
    (c) the real file with a function name that
        does not exist in it                     -> should HARD FAIL as
                                                     FUNCTION_NOT_FOUND_IN_FILE
                                                     (distinct from (b))

Also covers PATH_REMOVED_SINCE (WARN, not HARD) by committing then deleting
a file, and the SKIPPED_CHECKS path for a non-git directory.

Run directly:
    python tests/test_memory_decay_self.py

Or via pytest:
    pytest tests/test_memory_decay_self.py -v
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from check_memory_decay import run_decay_check  # noqa: E402


def _run(cmd: list[str], cwd: Path) -> None:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed: {cmd}\nstdout={proc.stdout}\nstderr={proc.stderr}")


def _init_scratch_repo(root: Path) -> None:
    _run(["git", "init", "-q"], root)
    _run(["git", "config", "user.email", "test@example.com"], root)
    _run(["git", "config", "user.name", "Test"], root)


def _commit_all(root: Path, message: str) -> None:
    _run(["git", "add", "-A"], root)
    _run(["git", "commit", "-q", "-m", message], root)


def build_scratch_repo() -> Path:
    """Create a temp git repo with:
       - scripts/real_module.py defining `def real_function(): ...`
       - a file that is committed then deleted (for PATH_REMOVED_SINCE)
    Returns the repo root Path.
    """
    root = Path(tempfile.mkdtemp(prefix="memory_decay_selftest_"))
    _init_scratch_repo(root)

    scripts_dir = root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "real_module.py").write_text(
        "def real_function():\n"
        "    return 42\n"
        "\n"
        "\n"
        "class Thing:\n"
        "    def method_on_class(self):\n"
        "        return 'ok'\n",
        encoding="utf-8",
    )

    # A file that will exist in history but be deleted afterward.
    (scripts_dir / "removed_later.py").write_text("def gone(): pass\n", encoding="utf-8")

    _commit_all(root, "initial commit: real_module.py + removed_later.py")

    (scripts_dir / "removed_later.py").unlink()
    _commit_all(root, "remove removed_later.py")

    return root


def build_memory_text() -> str:
    return (
        "# Test Memory\n\n"
        "## Current State\n\n"
        "- (a) Real reference: `scripts/real_module.py::real_function` should verify clean.\n"
        "- (b) Hallucinated reference: `scripts/never_existed_file.py` was never real.\n"
        "- (c) Stale function claim: `scripts/real_module.py::function_that_was_renamed` "
        "no longer exists in that file.\n"
        "- (d) Historical reference: `scripts/removed_later.py` existed once, then was deleted.\n"
    )


def main() -> int:
    repo_root = build_scratch_repo()
    failures: list[str] = []

    try:
        memory_dir = Path(tempfile.mkdtemp(prefix="memory_decay_memfile_"))
        memory_path = memory_dir / "MEMORY.md"
        memory_path.write_text(build_memory_text(), encoding="utf-8")

        report = run_decay_check(memory_path, repo_root, check_topic_files=False)

        by_path = {(f.path, f.function): f for f in report.findings}

        # --- Case (a): real file + real function -> no finding at all ---
        case_a_key = ("scripts/real_module.py", "real_function")
        if case_a_key in by_path:
            failures.append(
                f"CASE (a) FAILED: expected no finding for {case_a_key}, got "
                f"{by_path[case_a_key].to_dict()}"
            )
        else:
            print(f"CASE (a) PASS: {case_a_key} verified clean (real file + real function)")

        # --- Case (b): path never existed -> HARD PATH_NEVER_EXISTED ---
        case_b_key = ("scripts/never_existed_file.py", None)
        case_b = by_path.get(case_b_key)
        if case_b is None:
            failures.append(f"CASE (b) FAILED: expected a finding for {case_b_key}, got none")
        elif case_b.kind != "PATH_NEVER_EXISTED" or case_b.severity != "HARD":
            failures.append(
                f"CASE (b) FAILED: expected PATH_NEVER_EXISTED/HARD, got "
                f"{case_b.kind}/{case_b.severity}"
            )
        else:
            print(f"CASE (b) PASS: {case_b_key} -> PATH_NEVER_EXISTED (HARD)")

        # --- Case (c): real file, fake function -> HARD FUNCTION_NOT_FOUND_IN_FILE ---
        case_c_key = ("scripts/real_module.py", "function_that_was_renamed")
        case_c = by_path.get(case_c_key)
        if case_c is None:
            failures.append(f"CASE (c) FAILED: expected a finding for {case_c_key}, got none")
        elif case_c.kind != "FUNCTION_NOT_FOUND_IN_FILE" or case_c.severity != "HARD":
            failures.append(
                f"CASE (c) FAILED: expected FUNCTION_NOT_FOUND_IN_FILE/HARD, got "
                f"{case_c.kind}/{case_c.severity}"
            )
        else:
            print(f"CASE (c) PASS: {case_c_key} -> FUNCTION_NOT_FOUND_IN_FILE (HARD)")

        # --- Distinctness: (b) and (c) must be different kinds ---
        if case_b is not None and case_c is not None and case_b.kind == case_c.kind:
            failures.append(
                f"DISTINCTNESS FAILED: case (b) and case (c) both classified as {case_b.kind} "
                f"-- they must be distinct decay classes"
            )
        else:
            print("DISTINCTNESS PASS: (b) PATH_NEVER_EXISTED != (c) FUNCTION_NOT_FOUND_IN_FILE")

        # --- Bonus case (d): PATH_REMOVED_SINCE (WARN, not HARD) ---
        case_d_key = ("scripts/removed_later.py", None)
        case_d = by_path.get(case_d_key)
        if case_d is None:
            failures.append(f"CASE (d) FAILED: expected a finding for {case_d_key}, got none")
        elif case_d.kind != "PATH_REMOVED_SINCE" or case_d.severity != "WARN":
            failures.append(
                f"CASE (d) FAILED: expected PATH_REMOVED_SINCE/WARN, got "
                f"{case_d.kind}/{case_d.severity}"
            )
        else:
            print(f"CASE (d) PASS: {case_d_key} -> PATH_REMOVED_SINCE (WARN, not HARD)")

        # --- checked count sanity ---
        if report.checked != 4:
            failures.append(f"CHECKED COUNT FAILED: expected 4 refs checked, got {report.checked}")
        else:
            print(f"CHECKED COUNT PASS: {report.checked} references checked")

        # --- no-git-repo SKIPPED_CHECKS path ---
        non_git_dir = Path(tempfile.mkdtemp(prefix="memory_decay_nogit_"))
        non_git_memory = non_git_dir / "MEMORY.md"
        non_git_memory.write_text(
            "## Current State\n- Reference to `scripts/whatever.py` in a non-git dir.\n",
            encoding="utf-8",
        )
        non_git_report = run_decay_check(non_git_memory, non_git_dir, check_topic_files=False)
        if not non_git_report.skipped_checks:
            failures.append(
                "SKIPPED_CHECKS FAILED: expected a skipped git-history check when no .git "
                "directory is present, got none"
            )
        elif not any("git-history check skipped" in s for s in non_git_report.skipped_checks):
            failures.append(
                f"SKIPPED_CHECKS FAILED: expected a git-history-skip message, got "
                f"{non_git_report.skipped_checks}"
            )
        else:
            print("SKIPPED_CHECKS PASS: no-git-repo correctly recorded as a skipped check")
        shutil.rmtree(non_git_dir, ignore_errors=True)

        shutil.rmtree(memory_dir, ignore_errors=True)
    finally:
        shutil.rmtree(repo_root, ignore_errors=True)

    print()
    if failures:
        print(f"SELF-TEST FAILED ({len(failures)} failure(s)):")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("SELF-TEST PASSED: all cases classified correctly.")
    return 0


def test_memory_decay_self() -> None:
    """Pytest-discoverable entrypoint. Wraps main() so `pytest tests/` collects and
    runs this suite instead of silently reporting zero tests (main() alone is not
    a pytest-recognized name)."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
