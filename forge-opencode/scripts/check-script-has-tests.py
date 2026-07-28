#!/usr/bin/env python3
"""Gate check G7-SCRIPT-001: at least one test exists.

A "test" is any of:
  - A file matching pytest naming conventions: test_*.py or *_test.py
  - A bash test: test_*.sh, *_test.sh, or *.test.sh
  - Any non-hidden script-language file (.py/.sh/.bash/.js/.mjs) inside a
    tests/ directory
  - Any non-hidden script-language file inside an examples/ directory
    (small scripts often demo themselves via runnable examples)

Searches the project tree, skipping Forge's own directories.

Exits 0 if at least one test is found, 1 otherwise.

Used by: references/gate-criteria.md (script-profile additions)
Ref: T-107
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_IGNORE_DIRS = frozenset({
    ".git", ".hg", ".svn",
    "node_modules", ".venv", "venv", "env",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".forge", "pipeline", "tasks", "build", "dist",
    ".idea", ".vscode",
})

_RUNNABLE_EXTS = frozenset({".py", ".sh", ".bash", ".js", ".mjs"})


def _is_within_ignored(path: Path, cwd: Path) -> bool:
    """True if any component of path (relative to cwd) is an ignored directory."""
    try:
        rel = path.relative_to(cwd)
    except ValueError:
        return False
    return any(part in _IGNORE_DIRS or part.startswith(".")
               for part in rel.parts[:-1])


def _looks_like_test_filename(name: str) -> bool:
    """Match common test naming conventions across Python and shell."""
    if name.startswith("."):
        return False
    if name.startswith("test_") and (name.endswith(".py") or name.endswith(".sh")):
        return True
    if name.endswith("_test.py") or name.endswith("_test.sh"):
        return True
    if name.endswith(".test.sh") or name.endswith(".test.js"):
        return True
    return False


def find_tests(cwd: Path) -> tuple[bool, str]:
    """Return (found, message). On success, message describes the first test found."""
    # 1) Test files anywhere under the project
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [
            d for d in dirs
            if d not in _IGNORE_DIRS and not d.startswith(".")
        ]
        for f in files:
            if _looks_like_test_filename(f):
                rel = (Path(root) / f).relative_to(cwd)
                return True, f"test file found: {rel}"

    # 2) Any runnable file inside a tests/ or examples/ directory at the project root.
    for candidate_dir in ("tests", "examples"):
        d = cwd / candidate_dir
        if not d.is_dir():
            continue
        for child in sorted(d.iterdir()):
            if child.name.startswith("."):
                continue
            if not child.is_file():
                continue
            if child.suffix.lower() in _RUNNABLE_EXTS:
                rel = child.relative_to(cwd)
                return True, f"{candidate_dir}/ contains runnable: {rel}"

    return (
        False,
        "no tests found "
        "(looked for test_*.py, *_test.py, test_*.sh, *_test.sh, "
        "*.test.sh, tests/*.py, examples/*.py)",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check-script-has-tests.py",
        description=__doc__,
    )
    parser.add_argument(
        "--cwd", default=os.getcwd(), metavar="PATH",
        help="project root (default: cwd)",
    )
    args = parser.parse_args(argv)

    cwd = Path(args.cwd).resolve()
    if not cwd.is_dir():
        print(f"error: not a directory: {cwd}", file=sys.stderr)
        return 1

    found, msg = find_tests(cwd)
    if found:
        print(msg)
        return 0
    print(msg, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())