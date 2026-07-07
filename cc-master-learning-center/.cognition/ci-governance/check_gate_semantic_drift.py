#!/usr/bin/env python3
"""check_gate_semantic_drift.py - residual parity concern after gen_ci.py.

gen_ci.py's --check already PROVES, by construction, that every gate whose
`command` == effective ci_command (i.e. no explicit ci_command override) is
byte-identical between the local and CI generated sections - there is nothing
left to check there.

The only gates that can still diverge in *behavior* (not just text) are the
handful that declare an explicit `ci_command` different from `command`. For
those, this script extracts the pytest target paths (file/dir arguments)
referenced by each version and asserts:

    set(local test paths) is a SUPERSET of set(ci test paths)

i.e. local must cover at least what CI covers. A local command that silently
narrowed its test targets relative to CI (e.g. someone edited `command` to
scope down for a fast local iteration loop and forgot to keep it a superset)
is caught here.

This intentionally does NOT attempt to be a general test-coverage comparator
across arbitrary shell pipelines - it targets pytest invocations specifically,
since that is the dominant case in this codebase. Non-pytest gates (gates with
`non_pytest: true`, or ones with no discernible pytest path) are skipped.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent

# Matches `pytest` or `python -m pytest` invocations and captures the
# remainder of that shell "word sequence" up to the next pipe/semicolon/&&,
# from which we then pull out path-like tokens (not flags, not -k/-m
# expression values).
PYTEST_INVOCATION_RE = re.compile(
    r"(?:python[0-9.]*\s+-m\s+pytest|(?<![\w./-])pytest)\b([^|;&]*)"
)

# A "path-like" token: contains a / or ends in .py, or is a bare directory
# name we recognize as a test root (tests, test). Excludes flags (start with -)
# and known flag-value pairs we don't want to misread as paths.
FLAG_WITH_VALUE = {"-k", "-m", "--maxfail", "-n", "--cov", "--durations"}


def extract_pytest_paths(command: str) -> set[str]:
    """Extract the set of file/dir path arguments passed to pytest
    invocations within `command`. Best-effort regex-based extraction - good
    enough for the declarative, well-formed commands this repo's gates use."""
    paths: set[str] = set()
    for match in PYTEST_INVOCATION_RE.finditer(command):
        remainder = match.group(1)
        tokens = remainder.split()
        skip_next = False
        for tok in tokens:
            if skip_next:
                skip_next = False
                continue
            if tok in FLAG_WITH_VALUE:
                skip_next = True
                continue
            if tok.startswith("-"):
                continue
            # Heuristic: looks like a path if it contains '/' or ends in .py
            # or starts with a known test-root prefix.
            if "/" in tok or tok.endswith(".py") or tok.startswith("test"):
                paths.add(tok.rstrip("/"))
    return paths


def load_gates(gates_path: Path) -> list[dict]:
    with open(gates_path, "r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    return doc.get("gates", []) if doc else []


def check_gate(gate: dict) -> tuple[bool, str]:
    """Returns (ok, message). ok=True means no drift (or nothing to check)."""
    name = gate["name"]
    if gate.get("non_pytest"):
        return True, f"{name}: skipped (non_pytest)"

    command = gate.get("command", "")
    ci_command = gate.get("ci_command")
    if not ci_command or ci_command == command:
        return True, f"{name}: skipped (no ci_command override)"

    local_paths = extract_pytest_paths(command)
    ci_paths = extract_pytest_paths(ci_command)

    if not local_paths and not ci_paths:
        return True, f"{name}: skipped (no pytest paths found in either command)"

    if not ci_paths.issubset(local_paths):
        missing = ci_paths - local_paths
        return False, (
            f"{name}: SEMANTIC DRIFT - local test-path set is NOT a superset of CI's.\n"
            f"    local command:    {command!r}\n"
            f"    ci_command:       {ci_command!r}\n"
            f"    local test paths: {sorted(local_paths)}\n"
            f"    ci test paths:    {sorted(ci_paths)}\n"
            f"    missing from local: {sorted(missing)}"
        )

    return True, (
        f"{name}: OK - local {sorted(local_paths)} covers ci {sorted(ci_paths)}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gates", required=True, type=Path, help="Path to gates.yml")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print all results, not just failures")
    args = parser.parse_args(argv)

    gates = load_gates(args.gates)
    failures = []
    for gate in gates:
        ok, msg = check_gate(gate)
        if not ok:
            failures.append(msg)
        elif args.verbose:
            print(msg)

    if failures:
        print("GATE_SEMANTIC_DRIFT_DETECTED:", file=sys.stderr)
        for f in failures:
            print(f"\n{f}", file=sys.stderr)
        return 1

    print("check_gate_semantic_drift: OK (no divergent gates, or all divergent gates are consistent)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
