#!/usr/bin/env python3
"""memory-system/lint_common.py

Tiny shared module for the memory-system lint tools in this toolkit.

Provides:
    Severity        - an OK/WARN/FAIL enum used consistently across tools.
    emit(...)        - a single function that produces the same dual-mode
                        (human text / --json) output contract for every lint
                        tool in this toolkit, so new tools get the same CLI
                        ergonomics for free.

Design notes:
    - No third-party dependencies (stdlib only) so any tool importing this
      can run with a bare `python3` interpreter.
    - `emit` does not read argv or exit the process itself -- it prints and
      RETURNS the process exit code the caller should use. This keeps the
      function testable (no sys.exit inside a helper) and lets callers do
      any last cleanup before exiting.
"""

from __future__ import annotations

import json as _json
import sys
from enum import Enum
from typing import Any, Iterable, Mapping


class Severity(str, Enum):
    """Overall verdict of a lint run."""

    OK = "OK"
    WARN = "WARN"
    FAIL = "FAIL"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


def determine_status(hard_failures: Iterable[Any], warnings: Iterable[Any]) -> Severity:
    """Pure function: hard_failures present -> FAIL; else warnings present -> WARN; else OK."""
    if list(hard_failures):
        return Severity.FAIL
    if list(warnings):
        return Severity.WARN
    return Severity.OK


def emit(
    status: Severity | str,
    hard_failures: Iterable[str],
    warnings: Iterable[str],
    extra_fields: Mapping[str, Any] | None = None,
    as_json: bool = False,
    *,
    ok_message: str | None = None,
    fail_help: str | None = None,
    warn_only: bool = False,
    stream=None,
) -> int:
    """Print a lint result in this toolkit's shared dual-mode contract and
    return the exit code the caller should use.

    Text mode:
        [WARN] N warning(s): ...
        [FAIL] N hard violation(s): ...          (or [WARN] if warn_only)
        [OK] <ok_message>                        (only if nothing to report)

    JSON mode (single line, machine-parseable):
        {"status": "OK|WARN|FAIL", "hard_failures": [...], "warnings": [...],
         ...extra_fields}

    Exit code:
        1 if hard_failures present and not warn_only, else 0.
    """
    out = stream or sys.stdout
    hard_failures = list(hard_failures)
    warnings = list(warnings)
    status_value = Severity(status) if not isinstance(status, Severity) else status

    if as_json:
        payload: dict[str, Any] = {
            "status": status_value.value,
            "hard_failures": hard_failures,
            "warnings": warnings,
        }
        if extra_fields:
            payload.update(extra_fields)
        print(_json.dumps(payload), file=out)
        return 1 if (hard_failures and not warn_only) else 0

    if warnings:
        print(f"[WARN] {len(warnings)} warning(s):", file=out)
        for w in warnings:
            print(f"  - {w}", file=out)

    if hard_failures:
        prefix = "[WARN] " if warn_only else "[FAIL] "
        print(f"\n{prefix}{len(hard_failures)} hard violation(s):", file=out)
        for f in hard_failures:
            print(f"  {f}", file=out)
        if fail_help and not warn_only:
            print(f"\n{fail_help}", file=out)
        if not warn_only:
            return 1

    if not hard_failures and not warnings and ok_message:
        print(f"[OK] {ok_message}", file=out)

    return 0
