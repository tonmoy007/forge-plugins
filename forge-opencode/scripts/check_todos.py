#!/usr/bin/env python3
"""Gate G6-005: no TODO/FIXME comments without a ticket reference.

Runs with cwd = project root. Scans source files for TODO/FIXME markers; a marker
is acceptable only if its line also carries a ticket reference (T-NNN, #NNN, an
UPPER-NNN issue key, or a parenthesised owner). Exit 0 if all markers are
ticketed (or none exist); 1 otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CODE_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".rb",
            ".c", ".h", ".cpp", ".cs", ".sh", ".css", ".scss", ".vue"}
SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".forge", "__pycache__",
             "venv", ".venv"}

MARKER = re.compile(r"\b(TODO|FIXME)\b")
TICKET = re.compile(r"T-\d+|#\d+|[A-Z]{2,}-\d+|\([^)]+\)")


def main() -> int:
    root = Path(".")
    offenders: list[str] = []
    for p in root.rglob("*"):
        if p.is_dir() or any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() not in CODE_EXT:
            continue
        try:
            text = p.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if MARKER.search(line) and not TICKET.search(line):
                offenders.append(f"{p}:{i}: {line.strip()[:80]}")
    if offenders:
        print("TODO/FIXME without a ticket reference:", file=sys.stderr)
        for o in offenders[:20]:
            print(f"  {o}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
