#!/usr/bin/env python3
"""Gate G6-003: no raw CSS values in UI files (design tokens must be used).

Runs with cwd = project root. Scans UI files (.css/.scss/.tsx/.jsx/.vue/.html)
for raw hex colors and literal font-family declarations that bypass design
tokens (var(--...)). Exit 0 if none found (or there are no UI files); 1 otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

UI_EXT = {".css", ".scss", ".sass", ".less", ".tsx", ".jsx", ".vue", ".html"}
SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".forge", "__pycache__"}

HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
FONT_LITERAL = re.compile(r"font-family\s*:")


def _ui_files(root: Path) -> list[Path]:
    files = []
    for p in root.rglob("*"):
        if p.is_dir():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in UI_EXT:
            files.append(p)
    return files


def main() -> int:
    root = Path(".")
    violations: list[str] = []
    for f in _ui_files(root):
        try:
            text = f.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if HEX.search(line):
                violations.append(f"{f}:{i}: raw hex color")
            elif FONT_LITERAL.search(line) and "var(--" not in line:
                violations.append(f"{f}:{i}: literal font-family (use a token)")
    if violations:
        print("raw CSS values found (use design tokens):", file=sys.stderr)
        for v in violations[:20]:
            print(f"  {v}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
