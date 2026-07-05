"""test_gen_ci_self.py - self-test proving the gates.yml -> codegen redesign
actually works: schema validation, codegen correctness, idempotency, --check
mode, and the deletion guard's real git-backed detection.

Run with:
    python -m pytest ci-governance/tests/test_gen_ci_self.py -v
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

CI_GOV_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CI_GOV_DIR))

import gen_ci  # noqa: E402
import check_gate_deletion  # noqa: E402


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

SMALL_GATES_YAML = textwrap.dedent(
    """
    version: 1
    gates:
      - name: unit-tests
        description: "Unit test suite"
        group: "core"
        command: "python -m pytest tests/unit -q"

      - name: some-lint
        description: "A non-pytest lint"
        group: "governance"
        command: "python scripts/some_lint.py"
        non_pytest: true
        sibling_test_gate: lint-tests

      - name: lint-tests
        description: "Tests for the lint"
        group: "governance"
        command: "python -m pytest tests/test_some_lint.py -q"

      - name: docker-only
        description: "Docker-only local smoke test"
        group: "docker"
        command: "docker build -t x . && docker run --rm x"
        allow_ci: false
        requires: ["docker"]

      - name: integration
        description: "Integration suite"
        group: "core"
        command: "python -m pytest tests/integration -q"
        ci_command: "python -m pytest tests/integration -vv"
        extra_yaml: |
          env:
            FOO: bar
    """
).strip() + "\n"


@pytest.fixture()
def gates_file(tmp_path: Path) -> Path:
    p = tmp_path / "gates.yml"
    p.write_text(SMALL_GATES_YAML, encoding="utf-8")
    return p


@pytest.fixture()
def local_out(tmp_path: Path) -> Path:
    return tmp_path / "local_ci.sh"


@pytest.fixture()
def ci_out(tmp_path: Path) -> Path:
    return tmp_path / "ci.yml"


def run_gen_ci(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CI_GOV_DIR / "gen_ci.py"), *args],
        capture_output=True,
        text=True,
    )


# --------------------------------------------------------------------------
# Schema / load_gates validation tests
# --------------------------------------------------------------------------

def test_example_gates_file_validates_against_schema():
    """gates.example.yml must actually conform to gates.schema.json."""
    doc = gen_ci.load_gates(CI_GOV_DIR / "gates.example.yml")
    assert doc["version"] == 1
    names = {g["name"] for g in doc["gates"]}
    assert "unit-tests" in names
    assert "check-no-gate-deletion" in names
    assert "docker-image-smoke-test" in names
    assert "integration-tests" in names


def test_load_gates_rejects_duplicate_names(tmp_path):
    bad = tmp_path / "gates.yml"
    bad.write_text(
        textwrap.dedent(
            """
            version: 1
            gates:
              - name: dupe
                description: "one"
                command: "echo 1"
              - name: dupe
                description: "two"
                command: "echo 2"
            """
        ),
        encoding="utf-8",
    )
    with pytest.raises(gen_ci.GatesValidationError, match="duplicate gate name"):
        gen_ci.load_gates(bad)


def test_load_gates_rejects_orphan_sibling_test_gate(tmp_path):
    bad = tmp_path / "gates.yml"
    bad.write_text(
        textwrap.dedent(
            """
            version: 1
            gates:
              - name: some-lint
                description: "lint"
                command: "echo lint"
                sibling_test_gate: does-not-exist
            """
        ),
        encoding="utf-8",
    )
    with pytest.raises(gen_ci.GatesValidationError, match="sibling_test_gate"):
        gen_ci.load_gates(bad)


def test_load_gates_rejects_both_allow_flags_false(tmp_path):
    bad = tmp_path / "gates.yml"
    bad.write_text(
        textwrap.dedent(
            """
            version: 1
            gates:
              - name: nowhere
                description: "runs nowhere"
                command: "echo nope"
                allow_local: false
                allow_ci: false
            """
        ),
        encoding="utf-8",
    )
    with pytest.raises(gen_ci.GatesValidationError, match="allow_local=false and allow_ci=false"):
        gen_ci.load_gates(bad)


def test_load_gates_rejects_missing_required_field(tmp_path):
    bad = tmp_path / "gates.yml"
    bad.write_text(
        textwrap.dedent(
            """
            version: 1
            gates:
              - name: no-description
                command: "echo hi"
            """
        ),
        encoding="utf-8",
    )
    with pytest.raises(gen_ci.GatesValidationError):
        gen_ci.load_gates(bad)


def test_load_gates_rejects_bad_name_pattern(tmp_path):
    bad = tmp_path / "gates.yml"
    bad.write_text(
        textwrap.dedent(
            """
            version: 1
            gates:
              - name: "bad name with spaces"
                description: "x"
                command: "echo hi"
            """
        ),
        encoding="utf-8",
    )
    with pytest.raises(gen_ci.GatesValidationError):
        gen_ci.load_gates(bad)


# --------------------------------------------------------------------------
# Codegen content tests
# --------------------------------------------------------------------------

def test_write_generates_expected_content(gates_file, local_out, ci_out):
    result = run_gen_ci(
        "--gates", str(gates_file),
        "--local-ci-out", str(local_out),
        "--ci-yml-out", str(ci_out),
        "--write",
    )
    assert result.returncode == 0, result.stderr

    local_text = local_out.read_text(encoding="utf-8")
    ci_text = ci_out.read_text(encoding="utf-8")

    # Local runner: all allow_local gates present, in run_check form.
    assert 'run_check "unit-tests"' in local_text
    assert 'run_check "some-lint"' in local_text
    assert 'run_check "lint-tests"' in local_text
    assert 'run_check "docker-only"' in local_text
    assert 'run_check "integration"' in local_text
    # requires guard present for docker-only
    assert "command -v docker" in local_text
    # unit-tests has no requires -> no guard immediately preceding it
    assert "python -m pytest tests/unit -q" in local_text

    # CI workflow: docker-only must be ABSENT (allow_ci: false)
    ci_doc = yaml.safe_load(ci_text)
    job_keys = set(ci_doc["jobs"].keys())
    assert "docker-only" not in job_keys
    assert {"unit-tests", "some-lint", "lint-tests", "integration"}.issubset(job_keys)

    # integration job uses ci_command override, not command
    integration_job_yaml = yaml.dump(ci_doc["jobs"]["integration"])
    assert "-vv" in integration_job_yaml
    assert "FOO" in integration_job_yaml  # extra_yaml merged in


def test_write_is_idempotent(gates_file, local_out, ci_out):
    r1 = run_gen_ci(
        "--gates", str(gates_file),
        "--local-ci-out", str(local_out),
        "--ci-yml-out", str(ci_out),
        "--write",
    )
    assert r1.returncode == 0, r1.stderr
    local_bytes_1 = local_out.read_bytes()
    ci_bytes_1 = ci_out.read_bytes()

    r2 = run_gen_ci(
        "--gates", str(gates_file),
        "--local-ci-out", str(local_out),
        "--ci-yml-out", str(ci_out),
        "--write",
    )
    assert r2.returncode == 0, r2.stderr
    local_bytes_2 = local_out.read_bytes()
    ci_bytes_2 = ci_out.read_bytes()

    assert local_bytes_1 == local_bytes_2, "local_ci.sh output not byte-identical across two --write runs"
    assert ci_bytes_1 == ci_bytes_2, "ci.yml output not byte-identical across two --write runs"

    # A third pass, for extra confidence there's no slow oscillation/growth.
    r3 = run_gen_ci(
        "--gates", str(gates_file),
        "--local-ci-out", str(local_out),
        "--ci-yml-out", str(ci_out),
        "--write",
    )
    assert r3.returncode == 0, r3.stderr
    assert local_out.read_bytes() == local_bytes_1
    assert ci_out.read_bytes() == ci_bytes_1


def test_check_passes_after_write(gates_file, local_out, ci_out):
    run_gen_ci(
        "--gates", str(gates_file),
        "--local-ci-out", str(local_out),
        "--ci-yml-out", str(ci_out),
        "--write",
    )
    result = run_gen_ci(
        "--gates", str(gates_file),
        "--local-ci-out", str(local_out),
        "--ci-yml-out", str(ci_out),
        "--check",
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"


def test_check_fails_on_hand_edit_drift(gates_file, local_out, ci_out):
    run_gen_ci(
        "--gates", str(gates_file),
        "--local-ci-out", str(local_out),
        "--ci-yml-out", str(ci_out),
        "--write",
    )
    # Hand-edit the marked region -- simulate someone editing generated output.
    text = local_out.read_text(encoding="utf-8")
    tampered = text.replace('run_check "unit-tests"', 'run_check "unit-tests-TAMPERED"')
    local_out.write_text(tampered, encoding="utf-8")

    result = run_gen_ci(
        "--gates", str(gates_file),
        "--local-ci-out", str(local_out),
        "--ci-yml-out", str(ci_out),
        "--check",
    )
    assert result.returncode == 1
    assert "GATE_CODEGEN_DRIFT" in result.stderr


def test_marker_region_preserves_surrounding_handauthored_content(gates_file, local_out, ci_out):
    """Content outside the BEGIN/END markers must survive untouched -- this
    is the core promise that makes a project's own preamble (concurrency
    blocks, run_check function defs, checkout steps) safe to hand-author."""
    local_out.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n\nrun_check() {\n  echo \"running: $1\"\n  shift\n  \"$@\"\n}\n",
        encoding="utf-8",
    )
    ci_out.write_text(
        "name: My Custom CI\non:\n  push:\n    branches: [main]\nconcurrency:\n  group: ci-${{ github.ref }}\njobs:\n",
        encoding="utf-8",
    )

    run_gen_ci(
        "--gates", str(gates_file),
        "--local-ci-out", str(local_out),
        "--ci-yml-out", str(ci_out),
        "--write",
    )

    local_text = local_out.read_text(encoding="utf-8")
    ci_text = ci_out.read_text(encoding="utf-8")

    assert "set -euo pipefail" in local_text
    assert 'echo "running: $1"' in local_text
    assert "name: My Custom CI" in ci_text
    assert "concurrency:" in ci_text
    assert 'group: ci-${{ github.ref }}' in ci_text

    # And the generated content is still there too.
    assert 'run_check "unit-tests"' in local_text
    ci_doc = yaml.safe_load(ci_text)
    assert "unit-tests" in ci_doc["jobs"]

    # Idempotency still holds with hand-authored preamble present.
    before = (local_out.read_bytes(), ci_out.read_bytes())
    run_gen_ci(
        "--gates", str(gates_file),
        "--local-ci-out", str(local_out),
        "--ci-yml-out", str(ci_out),
        "--write",
    )
    after = (local_out.read_bytes(), ci_out.read_bytes())
    assert before == after


def test_multiline_command_wrapped_correctly_and_shell_safe(tmp_path):
    """A multi-line command containing a single quote must be wrapped in a
    valid bash -c block with correct escaping."""
    gates = tmp_path / "gates.yml"
    gates.write_text(
        textwrap.dedent(
            """
            version: 1
            gates:
              - name: multi
                description: "multi-line with quotes"
                command: |
                  echo 'hello world'
                  echo "second line"
            """
        ),
        encoding="utf-8",
    )
    doc = gen_ci.load_gates(gates)
    body = gen_ci.generate_local_section(doc["gates"])
    assert "bash -c '" in body
    # The embedded single quote must be escaped via '\'' sequence.
    assert "'\\''" in body


# --------------------------------------------------------------------------
# check_gate_deletion.py: real git-backed tests
# --------------------------------------------------------------------------

def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)


@pytest.fixture()
def scratch_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "scratch_repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    return repo


def test_deletion_guard_catches_real_removal_no_allowlist(scratch_git_repo):
    gates_path = scratch_git_repo / "gates.yml"
    gates_path.write_text(
        "version: 1\ngates:\n  - name: gate-a\n    description: A\n    command: echo a\n"
        "  - name: gate-b\n    description: B\n    command: echo b\n",
        encoding="utf-8",
    )
    _git(scratch_git_repo, "add", "gates.yml")
    _git(scratch_git_repo, "commit", "-q", "-m", "v1")

    gates_path.write_text(
        "version: 1\ngates:\n  - name: gate-a\n    description: A\n    command: echo a\n",
        encoding="utf-8",
    )
    _git(scratch_git_repo, "add", "gates.yml")
    _git(scratch_git_repo, "commit", "-q", "-m", "v2 removed gate-b")

    result = subprocess.run(
        [
            sys.executable, str(CI_GOV_DIR / "check_gate_deletion.py"),
            "--gates", "gates.yml",
            "--base", "HEAD~1",
            "--repo-root", str(scratch_git_repo),
        ],
        cwd=scratch_git_repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "GATE_DELETION_HARD_FAIL" in result.stderr
    assert "gate-b" in result.stderr


def test_deletion_guard_respects_valid_allowlist_entry(scratch_git_repo):
    gates_path = scratch_git_repo / "gates.yml"
    gates_path.write_text(
        "version: 1\ngates:\n  - name: gate-a\n    description: A\n    command: echo a\n"
        "  - name: gate-b\n    description: B\n    command: echo b\n",
        encoding="utf-8",
    )
    _git(scratch_git_repo, "add", "gates.yml")
    _git(scratch_git_repo, "commit", "-q", "-m", "v1")

    gates_path.write_text(
        "version: 1\ngates:\n  - name: gate-a\n    description: A\n    command: echo a\n",
        encoding="utf-8",
    )
    _git(scratch_git_repo, "add", "gates.yml")
    _git(scratch_git_repo, "commit", "-q", "-m", "v2 removed gate-b")

    allowlist = scratch_git_repo / "allowlist.txt"
    allowlist.write_text("gate-b | superseded by gate-a | expires=2099-01-01 | ref=#1\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable, str(CI_GOV_DIR / "check_gate_deletion.py"),
            "--gates", "gates.yml",
            "--base", "HEAD~1",
            "--allowlist", "allowlist.txt",
            "--repo-root", str(scratch_git_repo),
        ],
        cwd=scratch_git_repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "gate-b" in result.stdout


def test_deletion_guard_hard_fails_on_expired_allowlist_entry(scratch_git_repo):
    gates_path = scratch_git_repo / "gates.yml"
    gates_path.write_text(
        "version: 1\ngates:\n  - name: gate-a\n    description: A\n    command: echo a\n"
        "  - name: gate-b\n    description: B\n    command: echo b\n",
        encoding="utf-8",
    )
    _git(scratch_git_repo, "add", "gates.yml")
    _git(scratch_git_repo, "commit", "-q", "-m", "v1")

    gates_path.write_text(
        "version: 1\ngates:\n  - name: gate-a\n    description: A\n    command: echo a\n",
        encoding="utf-8",
    )
    _git(scratch_git_repo, "add", "gates.yml")
    _git(scratch_git_repo, "commit", "-q", "-m", "v2 removed gate-b")

    allowlist = scratch_git_repo / "allowlist.txt"
    allowlist.write_text("gate-b | superseded by gate-a | expires=2020-01-01 | ref=#1\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable, str(CI_GOV_DIR / "check_gate_deletion.py"),
            "--gates", "gates.yml",
            "--base", "HEAD~1",
            "--allowlist", "allowlist.txt",
            "--repo-root", str(scratch_git_repo),
        ],
        cwd=scratch_git_repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "EXPIRED" in result.stderr


def test_deletion_guard_warns_on_stale_allowlist_entry(scratch_git_repo):
    """A gate that IS still present but has an allowlist entry anyway must
    WARN (stale entry), not fail."""
    gates_path = scratch_git_repo / "gates.yml"
    gates_path.write_text(
        "version: 1\ngates:\n  - name: gate-a\n    description: A\n    command: echo a\n",
        encoding="utf-8",
    )
    _git(scratch_git_repo, "add", "gates.yml")
    _git(scratch_git_repo, "commit", "-q", "-m", "v1")
    _git(scratch_git_repo, "commit", "--allow-empty", "-q", "-m", "v2 no changes")

    allowlist = scratch_git_repo / "allowlist.txt"
    allowlist.write_text("gate-a | not actually removed | expires=2099-01-01\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable, str(CI_GOV_DIR / "check_gate_deletion.py"),
            "--gates", "gates.yml",
            "--base", "HEAD~1",
            "--allowlist", "allowlist.txt",
            "--repo-root", str(scratch_git_repo),
        ],
        cwd=scratch_git_repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "STALE" in result.stdout


def test_deletion_guard_base_unavailable_sentinel(scratch_git_repo):
    gates_path = scratch_git_repo / "gates.yml"
    gates_path.write_text(
        "version: 1\ngates:\n  - name: gate-a\n    description: A\n    command: echo a\n",
        encoding="utf-8",
    )
    _git(scratch_git_repo, "add", "gates.yml")
    _git(scratch_git_repo, "commit", "-q", "-m", "v1")

    result = subprocess.run(
        [
            sys.executable, str(CI_GOV_DIR / "check_gate_deletion.py"),
            "--gates", "gates.yml",
            "--base", "origin/definitely-does-not-exist",
            "--repo-root", str(scratch_git_repo),
        ],
        cwd=scratch_git_repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "GATE_DELETION_BASE_UNAVAILABLE" in result.stdout


# --------------------------------------------------------------------------
# check_gate_semantic_drift.py smoke test
# --------------------------------------------------------------------------

def test_semantic_drift_check_passes_on_example_gates():
    result = subprocess.run(
        [sys.executable, str(CI_GOV_DIR / "check_gate_semantic_drift.py"), "--gates", str(CI_GOV_DIR / "gates.example.yml")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_semantic_drift_check_catches_narrowed_local_coverage(tmp_path):
    gates = tmp_path / "gates.yml"
    gates.write_text(
        textwrap.dedent(
            """
            version: 1
            gates:
              - name: narrowed
                description: "local narrower than CI -- should fail"
                command: "python -m pytest tests/unit -q"
                ci_command: "python -m pytest tests/unit tests/integration -q"
            """
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(CI_GOV_DIR / "check_gate_semantic_drift.py"), "--gates", str(gates)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "SEMANTIC DRIFT" in result.stderr
