#!/usr/bin/env python3
"""memory-system/check_memory_decay.py

Detects DECAYED references inside a MEMORY.md (and optionally its linked
topic files): mentions of repo files, or file+function pairs, that no
longer match reality. This is the highest-value net-new capability in the
memory-system toolkit -- cross-session memory is only as trustworthy as its
references are current, and nothing else in this toolkit checks that.

EXTRACTION
    Two regex families pull repo-relative path tokens out of memory text:
      1. Backtick-fenced paths, optionally with a "::function_name" suffix,
         e.g. `scripts/foo.py` or `core/bar.py::do_thing`.
      2. Bare (non-backtick) path-looking tokens with a recognized source
         extension, appearing under a common source-directory prefix, e.g.
         scripts/foo.py, src/lib/bar.ts, docs/runbooks/x.md.

VERIFICATION (deterministic, repo-local, no network)
    For each extracted path:
      - working-tree existence: a plain filesystem check under --repo-root.
      - git-history existence: `git cat-file -e <rev>:<path>` against HEAD,
        and (if not present at HEAD) a `git log --diff-filter=A --follow
        -- <path>` search for whether it was EVER added in history.
    This distinguishes:
      - PATH_NEVER_EXISTED   (HARD) -- no working-tree file AND no git
        history of the path ever existing. Almost certainly a hallucinated
        or mistyped reference -- the most dangerous "this never was true"
        class.
      - PATH_REMOVED_SINCE   (WARN) -- no working-tree file, BUT git history
        shows the path existed at some commit. May legitimately describe a
        past, now-resolved event (e.g. a deleted one-off migration script).

    For any path::function_name reference where the file CURRENTLY EXISTS,
    the file is parsed with Python's `ast` module (only for .py files) and
    checked for a matching function/method definition:
      - FUNCTION_NOT_FOUND_IN_FILE (HARD) -- the file is real and plausible,
        but the specific function claim is stale (renamed/removed/moved).
        This is the MOST dangerous decay class because everything about the
        reference *looks* right except the one fact that matters.

    Any check that cannot run (no git repo found, file not ast-parseable,
    etc.) is recorded explicitly in `skipped_checks` rather than silently
    omitted.

OUTPUT
    Same dual-mode contract as check_memory_size.py: human text by default,
    or a single-line JSON object with --json:
      {"status": "OK|WARN|FAIL", "checked": N, "stale_references": [...],
       "skipped_checks": [...], "hard_failures": [...], "warnings": [...]}

CLI
    check_memory_decay.py --file <memory.md> --repo-root <path>
                           [--check-topic-files] [--json]

Exit codes:
    0   no HARD findings (or --warn-only)
    1   at least one HARD finding (PATH_NEVER_EXISTED / FUNCTION_NOT_FOUND_IN_FILE)
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lint_common import Severity, emit  # noqa: E402


# -- Extraction regexes ---------------------------------------------------------

# Common source-directory prefixes a bare (non-backtick) path reference is
# expected to start with, to avoid false-positive matches on ordinary prose
# (e.g. "version 3.11.2" or a URL fragment). Extend this list as needed for
# your project's layout.
_SOURCE_DIR_PREFIXES = (
    "scripts/", "src/", "core/", "lib/", "app/", "apps/", "docs/", "tests/",
    "test/", "pipeline/", "deploy/", "migrations/", "tools/", "bin/",
    "packages/", "cmd/", "internal/",
)

_SOURCE_EXTENSIONS = (
    "py", "js", "jsx", "ts", "tsx", "go", "rb", "java", "rs", "sh", "sql",
    "md", "yml", "yaml", "json", "toml", "cfg", "ini",
)

# `path/to/file.ext` or `path/to/file.ext::function_name`, backtick-fenced.
_BACKTICK_PATH_RE = re.compile(
    r"`((?:[\w.\-]+/)+[\w.\-]+\.(?:" + "|".join(_SOURCE_EXTENSIONS) + r"))"
    r"(?:::([A-Za-z_][A-Za-z0-9_]*))?`"
)

# Bare path-looking token (no backticks) under a recognized source prefix.
# Word-boundary-ish: preceded by start/space/paren/quote, followed by a
# non-path-continuation character.
_BARE_PATH_RE = re.compile(
    r"(?<![`\w/.\-])"
    r"((?:" + "|".join(re.escape(p) for p in _SOURCE_DIR_PREFIXES) + r")"
    r"(?:[\w.\-]+/)*[\w.\-]+\.(?:" + "|".join(_SOURCE_EXTENSIONS) + r"))"
    r"(?:::([A-Za-z_][A-Za-z0-9_]*))?"
    r"(?![\w/.\-])"
)


@dataclass
class ExtractedRef:
    path: str
    function: Optional[str] = None
    source_line_excerpt: str = ""


@dataclass
class Finding:
    kind: str          # PATH_NEVER_EXISTED | PATH_REMOVED_SINCE | FUNCTION_NOT_FOUND_IN_FILE
    severity: str       # HARD | WARN
    path: str
    function: Optional[str]
    detail: str

    def to_text(self) -> str:
        fn = f"::{self.function}" if self.function else ""
        return f"[{self.kind}] {self.path}{fn} -- {self.detail}"

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "path": self.path,
            "function": self.function,
            "detail": self.detail,
        }


@dataclass
class DecayReport:
    checked: int = 0
    findings: list[Finding] = field(default_factory=list)
    skipped_checks: list[str] = field(default_factory=list)


# -- Extraction ------------------------------------------------------------------

def extract_references(text: str) -> list[ExtractedRef]:
    """Pull repo-relative path (and path::function) references out of memory text."""
    seen: dict[tuple[str, Optional[str]], ExtractedRef] = {}

    for m in _BACKTICK_PATH_RE.finditer(text):
        path, fn = m.group(1), m.group(2)
        key = (path, fn)
        if key not in seen:
            seen[key] = ExtractedRef(path=path, function=fn, source_line_excerpt=m.group(0))

    for m in _BARE_PATH_RE.finditer(text):
        path, fn = m.group(1), m.group(2)
        key = (path, fn)
        if key not in seen:
            seen[key] = ExtractedRef(path=path, function=fn, source_line_excerpt=m.group(0))

    return list(seen.values())


# -- Git helpers -------------------------------------------------------------------

def _is_git_repo(repo_root: Path) -> bool:
    return (repo_root / ".git").exists()


def _git(repo_root: Path, *args: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _exists_in_working_tree(repo_root: Path, rel_path: str) -> bool:
    return (repo_root / rel_path).exists()


def _exists_at_head(repo_root: Path, rel_path: str) -> bool:
    rc, _, _ = _git(repo_root, "cat-file", "-e", f"HEAD:{rel_path}")
    return rc == 0


def _existed_in_history(repo_root: Path, rel_path: str) -> bool:
    """True if `rel_path` was ever added/modified/present at any point in
    the repo's history (not just currently). Uses `git log` scoped to the
    path -- any output means the path is known to git history."""
    rc, out, _ = _git(repo_root, "log", "--all", "--oneline", "--", rel_path)
    return rc == 0 and out.strip() != ""


# -- Verification ------------------------------------------------------------------

def _parse_function_names(source: str) -> set[str]:
    """Return every function/method/class-level def name found via ast."""
    names: set[str] = set()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
    return names


def verify_reference(ref: ExtractedRef, repo_root: Path, report: DecayReport) -> None:
    report.checked += 1

    has_git = _is_git_repo(repo_root)
    in_working_tree = _exists_in_working_tree(repo_root, ref.path)

    if in_working_tree:
        # Path exists right now. If a function claim is attached, verify it
        # (Python files only -- ast is Python-specific).
        if ref.function:
            abs_path = repo_root / ref.path
            if not ref.path.endswith(".py"):
                report.skipped_checks.append(
                    f"function-check skipped for {ref.path}::{ref.function} "
                    f"(non-Python file; ast verification only supports .py)"
                )
                return
            try:
                source = abs_path.read_text(encoding="utf-8", errors="replace")
                fn_names = _parse_function_names(source)
            except (SyntaxError, ValueError) as exc:
                report.skipped_checks.append(
                    f"function-check skipped for {ref.path}::{ref.function} "
                    f"(file not ast-parseable: {exc})"
                )
                return
            except OSError as exc:
                report.skipped_checks.append(
                    f"function-check skipped for {ref.path}::{ref.function} (read error: {exc})"
                )
                return

            if ref.function not in fn_names:
                report.findings.append(Finding(
                    kind="FUNCTION_NOT_FOUND_IN_FILE",
                    severity="HARD",
                    path=ref.path,
                    function=ref.function,
                    detail=(
                        f"file exists but defines no function/method named '{ref.function}' "
                        f"(found {len(fn_names)} def(s) total) -- likely renamed, removed, or "
                        f"the reference was never accurate"
                    ),
                ))
        # Path exists and (if present) function checks out -> no finding.
        return

    # Path does NOT exist in the working tree.
    if not has_git:
        report.skipped_checks.append(
            f"git-history check skipped for {ref.path} (no .git directory found at {repo_root})"
        )
        return

    existed_at_head = _exists_at_head(repo_root, ref.path)
    existed_ever = existed_at_head or _existed_in_history(repo_root, ref.path)

    if existed_ever:
        report.findings.append(Finding(
            kind="PATH_REMOVED_SINCE",
            severity="WARN",
            path=ref.path,
            function=ref.function,
            detail=(
                "not present in the working tree, but git history shows this path existed "
                "at some point -- may legitimately describe a past, now-resolved event"
            ),
        ))
    else:
        report.findings.append(Finding(
            kind="PATH_NEVER_EXISTED",
            severity="HARD",
            path=ref.path,
            function=ref.function,
            detail=(
                "not present in the working tree AND no git history of this path ever "
                "existing -- likely a hallucinated or mistyped reference"
            ),
        ))


# -- Topic-file discovery ------------------------------------------------------------

def _find_topic_file_paths(text: str, memory_path: Path) -> list[Path]:
    """Resolve [label](some_file.md)-style links in memory text to sibling files."""
    parent = memory_path.parent
    paths: list[Path] = []
    for _label, target in re.findall(r"\[([^\]]+)\]\(([^)]+\.md)\)", text):
        if target.startswith(("http://", "https://")):
            continue
        candidate = (parent / target).resolve()
        if candidate.exists():
            paths.append(candidate)
    return paths


# -- Orchestration ------------------------------------------------------------------

def run_decay_check(
    memory_path: Path,
    repo_root: Path,
    check_topic_files: bool = False,
) -> DecayReport:
    report = DecayReport()

    text = memory_path.read_text(encoding="utf-8")
    all_texts = [text]

    if check_topic_files:
        topic_paths = _find_topic_file_paths(text, memory_path)
        if not topic_paths:
            report.skipped_checks.append(
                "--check-topic-files was set but no resolvable topic-file links were found"
            )
        for tp in topic_paths:
            try:
                all_texts.append(tp.read_text(encoding="utf-8"))
            except OSError as exc:
                report.skipped_checks.append(f"could not read topic file {tp}: {exc}")

    refs: dict[tuple[str, Optional[str]], ExtractedRef] = {}
    for t in all_texts:
        for r in extract_references(t):
            refs.setdefault((r.path, r.function), r)

    for ref in refs.values():
        verify_reference(ref, repo_root, report)

    return report


# -- Self-test entry point (importable by tests/test_memory_decay_self.py) ----------
# See tests/test_memory_decay_self.py for the full embedded self-test harness.


# -- Main ----------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--file", type=Path, required=True, help="Path to the memory .md file to scan")
    parser.add_argument("--repo-root", type=Path, required=True,
                        help="Repo root that extracted paths are relative to")
    parser.add_argument("--check-topic-files", action="store_true",
                        help="Also scan linked [label](*.md) topic files referenced from --file")
    parser.add_argument("--warn-only", action="store_true",
                        help="Print warnings/failures but exit 0 regardless")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()

    if not args.file.exists():
        payload_extra = {"checked": 0, "stale_references": [], "skipped_checks": []}
        if args.json:
            print(json.dumps({
                "status": "MEMORY_FILE_UNAVAILABLE",
                "file": str(args.file),
                **payload_extra,
            }))
        else:
            print(f"MEMORY_FILE_UNAVAILABLE -- {args.file} does not exist.", file=sys.stderr)
        return 0

    report = run_decay_check(args.file, repo_root, check_topic_files=args.check_topic_files)

    hard = [f.to_text() for f in report.findings if f.severity == "HARD"]
    warn = [f.to_text() for f in report.findings if f.severity == "WARN"]

    status = Severity.FAIL if (hard and not args.warn_only) else \
        (Severity.WARN if (warn or hard) else Severity.OK)

    extra_fields = {
        "checked": report.checked,
        "stale_references": [f.to_dict() for f in report.findings],
        "skipped_checks": report.skipped_checks,
    }

    ok_message = f"{report.checked} reference(s) checked in {args.file.name} -- no decay detected."
    fail_help = (
        "HARD findings mean a memory file cites something that is provably false right now:\n"
        "  - PATH_NEVER_EXISTED: remove or correct the reference -- it was never true.\n"
        "  - FUNCTION_NOT_FOUND_IN_FILE: the file is real but the cited function has moved, "
        "been renamed, or removed -- update the reference to match current code.\n"
        "WARN findings (PATH_REMOVED_SINCE) may be legitimate historical mentions -- review, "
        "don't blindly delete."
    )

    return emit(
        status,
        hard,
        warn,
        extra_fields=extra_fields,
        as_json=args.json,
        ok_message=ok_message,
        fail_help=fail_help,
        warn_only=args.warn_only,
    )


if __name__ == "__main__":
    sys.exit(main())
