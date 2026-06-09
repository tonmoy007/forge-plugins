#!/usr/bin/env python3
"""Gate G7-005: no unresolved bugs at the given severities.

Usage: check_open_bugs.py [--severity P0,P1]   (cwd = project root)
Scans pipeline/10-feedback/triage.md for item rows (FB-NNN / table / bullet) that
carry one of the severities and are NOT marked resolved/closed/fixed/done. Exit 1
if any such open item exists; 0 otherwise (including when there is no triage file).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TRIAGE = Path("pipeline/10-feedback/triage.md")
RESOLVED = re.compile(r"\b(resolved|closed|fixed|done|shipped)\b", re.IGNORECASE)
# Only flag actual tracked items (FB-id or table row), and only when they carry an
# explicit open status — so severity *legend* lines ("- **P0**: ...") aren't bugs.
ITEM = re.compile(r"FB-\d+|^\s*\|")
OPEN = re.compile(r"\b(open|unresolved|new|in[\s\-]?progress|todo|wip)\b", re.IGNORECASE)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="check_open_bugs.py")
    parser.add_argument("--severity", default="P0,P1")
    args = parser.parse_args(argv)
    severities = [s.strip() for s in args.severity.split(",") if s.strip()]
    sev_re = re.compile(r"\b(" + "|".join(re.escape(s) for s in severities) + r")\b")

    if not TRIAGE.exists():
        return 0  # nothing triaged, nothing open

    open_items: list[str] = []
    for line in TRIAGE.read_text().splitlines():
        if not ITEM.search(line):
            continue
        if sev_re.search(line) and OPEN.search(line) and not RESOLVED.search(line):
            open_items.append(line.strip()[:80])
    if open_items:
        print(f"{len(open_items)} unresolved {args.severity} item(s):", file=sys.stderr)
        for o in open_items[:20]:
            print(f"  {o}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
