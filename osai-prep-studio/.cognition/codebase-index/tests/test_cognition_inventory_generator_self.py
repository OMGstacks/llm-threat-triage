#!/usr/bin/env python3
"""
tests/test_cognition_inventory_generator_self.py — self-test for
CognitionInventoryGenerator's marker-mapping logic.

Unlike test_framework_self.py (which only exercises the generic protocol
against a throwaway fake generator) or the CI drift-check (which only
proves *this repo's* current output matches its current source), this test
directly exercises `extract()` against a synthetic `.cognition/`-shaped temp
directory with a KNOWN, hand-picked mix of present/absent marker files --
so a subsystem-name/marker-path transposition typo would fail this test
even though it would still render as a plausible-looking table and pass
`--check` (which only proves internal consistency, not that the mapping
itself is correct).

Run directly:
    python tests/test_cognition_inventory_generator_self.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from cognition_inventory_generator import CognitionInventoryGenerator, _SUBSYSTEMS  # noqa: E402

FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        FAILURES.append(message)
        print(f"  FAIL: {message}")
    else:
        print(f"  ok:   {message}")


def main() -> int:
    print("CASE 1: every declared subsystem's marker maps to a status, in declared order")
    with tempfile.TemporaryDirectory() as tmp:
        source_root = Path(tmp) / ".cognition"
        source_root.mkdir()
        gen = CognitionInventoryGenerator(source_root=source_root, output_dir=Path(tmp) / "out")

        data = gen.extract()
        check(len(data) == len(_SUBSYSTEMS), f"extract() returns one record per declared subsystem (got {len(data)})")
        check(
            [d["subsystem"] for d in data] == [s["name"] for s in _SUBSYSTEMS],
            "record order matches declared _SUBSYSTEMS order",
        )
        check(
            all(d["status"] == "TEMPLATE-ONLY" for d in data),
            "with zero marker files present, every subsystem reports TEMPLATE-ONLY",
        )

    print("\nCASE 2: creating exactly the marker files flips exactly those subsystems to INSTANTIATED")
    with tempfile.TemporaryDirectory() as tmp:
        source_root = Path(tmp) / ".cognition"
        source_root.mkdir()
        gen = CognitionInventoryGenerator(source_root=source_root, output_dir=Path(tmp) / "out")

        # Instantiate only "memory" and "active-work" -- an arbitrary,
        # non-adjacent subset, to catch an off-by-one / transposed mapping.
        to_instantiate = {"memory", "active-work"}
        for s in _SUBSYSTEMS:
            if s["name"] in to_instantiate:
                marker_path = source_root / s["marker"]
                marker_path.parent.mkdir(parents=True, exist_ok=True)
                marker_path.write_text("real content\n")

        data = gen.extract()
        by_name = {d["subsystem"]: d for d in data}

        for s in _SUBSYSTEMS:
            expected = "INSTANTIATED" if s["name"] in to_instantiate else "TEMPLATE-ONLY"
            actual = by_name[s["name"]]["status"]
            check(
                actual == expected,
                f"subsystem {s['name']!r} reports {expected} (got {actual})",
            )
            check(
                by_name[s["name"]]["marker"] == s["marker"],
                f"subsystem {s['name']!r}'s reported marker path matches its declared marker ({s['marker']!r})",
            )

    print("\nCASE 3: no two subsystems share the same marker path (a copy-paste bug would collide)")
    markers = [s["marker"] for s in _SUBSYSTEMS]
    check(len(markers) == len(set(markers)), "all declared marker paths are unique")

    print("\nCASE 4: inputs() is empty (missing markers are the signal, not a precondition failure)")
    with tempfile.TemporaryDirectory() as tmp:
        source_root = Path(tmp) / ".cognition"
        source_root.mkdir()
        gen = CognitionInventoryGenerator(source_root=source_root, output_dir=Path(tmp) / "out")
        check(gen.inputs() == [], "inputs() returns an empty list regardless of marker presence")

    print()
    if FAILURES:
        print(f"SELF-TEST FAILED: {len(FAILURES)} check(s) failed.")
        return 1
    print("SELF-TEST PASSED: all cases behaved as expected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
