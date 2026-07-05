"""tests/test_framework_self.py — self-test of the framework using the example generator.

Run with: python -m pytest tests/test_framework_self.py -v
(from the codebase-index/ directory, or with codebase-index/ on sys.path).

Covers:
  1. --write produces the expected output files with expected content.
  2. --check passes (exit 0) immediately after --write.
  3. Mutating the source (adding a new env var reference) makes --check FAIL,
     with a diff that shows the new line.
  4. Re-running --write then --check passes again.
  5. An unregistered file dropped into the output directory triggers a WARNING
     but does NOT fail --check (mismatch-only is a hard fail; an unregistered
     file is advisory).
"""

from __future__ import annotations

import io
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

FRAMEWORK_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(FRAMEWORK_DIR))

from example_generator import EnvVarIndexGenerator  # noqa: E402
from framework import run_cli  # noqa: E402


def _run(generators, argv) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = run_cli(generators, argv)
    return code, out.getvalue(), err.getvalue()


def test_write_then_check_then_mutate_then_recheck():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        out_dir = tmp_path / "docs" / "codebase_index"

        source_file = src_dir / "app.py"
        source_file.write_text(
            "import os\n"
            "\n"
            "def get_db_url():\n"
            "    return os.environ.get('DATABASE_URL', 'sqlite://')\n"
            "\n"
            "def get_debug():\n"
            "    return os.getenv('DEBUG')\n",
            encoding="utf-8",
        )

        gen = EnvVarIndexGenerator(source_root=src_dir, output_dir=out_dir)
        generators = [gen]

        # --- Step 1: --write produces expected output files ---
        code, out, err = _run(generators, ["--write"])
        assert code == 0, f"--write should succeed, stderr={err}"

        md_path = out_dir / "env_var_index.md"
        json_path = out_dir / "env_var_index.json"
        assert md_path.exists(), "expected env_var_index.md to be written"
        assert json_path.exists(), "expected env_var_index.json to be written"

        md_content = md_path.read_text(encoding="utf-8")
        assert "DATABASE_URL" in md_content
        assert "DEBUG" in md_content
        assert "GENERATED FILE" in md_content

        json_content = json_path.read_text(encoding="utf-8")
        assert "DATABASE_URL" in json_content
        assert "DEBUG" in json_content
        assert "_generated_by" in json_content

        # --- Step 2: --check passes immediately after --write ---
        code, out, err = _run(generators, ["--check"])
        assert code == 0, f"--check should pass right after --write, stderr={err}"
        assert "OK" in out

        # --- Step 3: mutate source (add a new env var), --check now FAILS ---
        source_file.write_text(
            source_file.read_text(encoding="utf-8")
            + "\ndef get_new_flag():\n    return os.environ.get('NEW_FEATURE_FLAG')\n",
            encoding="utf-8",
        )
        code, out, err = _run(generators, ["--check"])
        assert code != 0, "expected --check to fail after adding a new env var reference"
        assert "DRIFT" in err
        assert "NEW_FEATURE_FLAG" in err, f"expected diff to mention new var, got: {err}"

        # --- Step 4: re-run --write, --check passes again ---
        code, out, err = _run(generators, ["--write"])
        assert code == 0
        code, out, err = _run(generators, ["--check"])
        assert code == 0, f"--check should pass again after --write, stderr={err}"
        md_content_after = md_path.read_text(encoding="utf-8")
        assert "NEW_FEATURE_FLAG" in md_content_after


def test_unregistered_file_warns_but_does_not_fail_check():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        out_dir = tmp_path / "docs" / "codebase_index"

        (src_dir / "app.py").write_text(
            "import os\nos.environ.get('SOME_VAR')\n", encoding="utf-8"
        )

        gen = EnvVarIndexGenerator(source_root=src_dir, output_dir=out_dir)
        generators = [gen]

        code, _, _ = _run(generators, ["--write"])
        assert code == 0

        # Drop an unregistered, hand-maintained-looking file into the output dir.
        stray = out_dir / "hand_written_notes.md"
        stray.write_text("# Notes\nSomeone wrote this by hand.\n", encoding="utf-8")

        code, out, err = _run(generators, ["--check"])
        assert code == 0, (
            "an unregistered file must NOT fail --check (warning-only), "
            f"stderr={err}"
        )
        assert "WARNING" in err
        assert "hand_written_notes.md" in err


def test_list_mode_prints_registered_generators_without_running():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        out_dir = tmp_path / "docs" / "codebase_index"
        # Deliberately do NOT create any source files — --list must not touch them.

        gen = EnvVarIndexGenerator(source_root=src_dir, output_dir=out_dir)
        code, out, err = _run([gen], ["--list"])
        assert code == 0
        assert gen.name in out
        assert not out_dir.exists(), "--list must not create/write any output"


def test_only_flag_restricts_to_named_generator():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        out_dir = tmp_path / "docs" / "codebase_index"
        (src_dir / "app.py").write_text("import os\nos.getenv('X')\n", encoding="utf-8")

        gen = EnvVarIndexGenerator(source_root=src_dir, output_dir=out_dir)
        code, out, err = _run([gen], ["--write", "--only", "env_var_index"])
        assert code == 0

        code, out, err = _run([gen], ["--write", "--only", "nonexistent_generator"])
        assert code != 0
        assert "no registered generator named" in err


if __name__ == "__main__":
    # Allow running directly without pytest for a quick smoke pass.
    failures = 0
    tests = [
        test_write_then_check_then_mutate_then_recheck,
        test_unregistered_file_warns_but_does_not_fail_check,
        test_list_mode_prints_registered_generators_without_running,
        test_only_flag_restricts_to_named_generator,
    ]
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL: {t.__name__}: {e}")
    sys.exit(1 if failures else 0)
