#!/usr/bin/env python3
"""Gate check G6-SCRIPT-001: at least one runnable script exists.

A script is "runnable" if any of:
  - It's a .py file that parses successfully (invokable via `python <file>`).
  - It's a .sh / .bash / .zsh file with a shebang line.
  - It's an extensionless file with a shebang line (typical for installed CLIs).

Searches the project tree, skipping Forge's own directories (.forge/, pipeline/,
tasks/, build/) and standard build/cache directories.

Exits 0 if at least one runnable script is found, 1 otherwise.

Used by: references/gate-criteria.md (script-profile additions)
Ref: T-107
"""

from __future__ import annotations

import argparse
import ast
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

_SHELL_EXTS = frozenset({".sh", ".bash", ".zsh", ".fish"})


def _iter_candidate_files(cwd: Path):
    """Yield candidate script files, skipping hidden and ignored directories."""
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [
            d for d in dirs
            if d not in _IGNORE_DIRS and not d.startswith(".")
        ]
        for f in files:
            if f.startswith("."):
                continue
            yield Path(root) / f


def _is_python_runnable(path: Path) -> bool:
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
        ast.parse(source)
        return True
    except (SyntaxError, OSError):
        return False


def _has_shebang(path: Path) -> bool:
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            first = f.readline()
        return first.startswith("#!")
    except OSError:
        return False


def find_runnable(cwd: Path) -> tuple[bool, str]:
    """Return (found, message). On success, message names the runnable script."""
    for path in _iter_candidate_files(cwd):
        ext = path.suffix.lower()
        rel = path.relative_to(cwd)
        if ext == ".py":
            if _is_python_runnable(path):
                return True, f"runnable: {rel} (Python parses cleanly)"
        elif ext in _SHELL_EXTS:
            if _has_shebang(path):
                return True, f"runnable: {rel} (shell script with shebang)"
        elif ext == "":
            # Extensionless file — typical for installed CLIs. Check shebang.
            if _has_shebang(path):
                return True, f"runnable: {rel} (extensionless with shebang)"
    return False, "no runnable script found (looked for *.py, *.sh, shebang'd files)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check-script-runnable.py",
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

    found, msg = find_runnable(cwd)
    if found:
        print(msg)
        return 0
    print(msg, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())