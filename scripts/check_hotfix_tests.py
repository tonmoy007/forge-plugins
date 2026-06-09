#!/usr/bin/env python3
"""Gate G11-003: every hotfix has a regression test.

Runs with cwd = project root. Reads pipeline/11-resolve/hotfixes.md, splits it
into hotfix sections (a `##`/`###` heading that names a fix: FB-NNN, "fix",
"hotfix"), and requires each section to reference a test ("test"/"regression").
Exit 0 if every hotfix references a test (or there are no hotfixes); 1 otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HOTFIXES = Path("pipeline/11-resolve/hotfixes.md")
HEADING = re.compile(r"^#{2,4}\s+(.*)$")
IS_HOTFIX = re.compile(r"FB-\d+|hotfix|\bfix\b", re.IGNORECASE)
HAS_TEST = re.compile(r"\btest\b|\bregression\b", re.IGNORECASE)


def main() -> int:
    if not HOTFIXES.exists():
        print(f"hotfixes file not found: {HOTFIXES}", file=sys.stderr)
        return 1

    lines = HOTFIXES.read_text().splitlines()
    # collect (heading, body) sections
    sections: list[tuple[str, list[str]]] = []
    current: tuple[str, list[str]] | None = None
    for line in lines:
        m = HEADING.match(line)
        if m:
            if current:
                sections.append(current)
            current = (m.group(1), [])
        elif current:
            current[1].append(line)
    if current:
        sections.append(current)

    missing: list[str] = []
    hotfix_count = 0
    for heading, body in sections:
        block = heading + "\n" + "\n".join(body)
        if not IS_HOTFIX.search(block):
            continue
        hotfix_count += 1
        if not HAS_TEST.search(block):
            missing.append(heading.strip()[:60])

    if hotfix_count == 0:
        return 0  # no hotfixes to verify
    if missing:
        print(f"hotfixes without a regression test: {', '.join(missing)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
