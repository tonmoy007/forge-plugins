#!/usr/bin/env python3
"""Gate G5-005: every task in the DAG declares done criteria.

Runs with cwd = project root. Reads pipeline/05-plan/task-dag.md, splits it into
per-task blocks (each starting at a `T-NNN` id) and requires each block to state
its done criteria ("done when" / "done:" / "done-when", case-insensitive).

Exit 0 if every task has done criteria; 1 otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DAG = Path("pipeline/05-plan/task-dag.md")
TASK_ID = re.compile(r"\bT-\d+\b")
DONE = re.compile(r"done[\s\-]*when|done\s*:", re.IGNORECASE)


def main() -> int:
    if not DAG.exists():
        print(f"task DAG not found: {DAG}", file=sys.stderr)
        return 1
    text = DAG.read_text()
    matches = list(TASK_ID.finditer(text))
    if not matches:
        print("no tasks (T-NNN) found in the DAG", file=sys.stderr)
        return 1

    missing: list[str] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        if not DONE.search(text[start:end]):
            missing.append(m.group(0))
    seen: set[str] = set()
    missing = [t for t in missing if not (t in seen or seen.add(t))]
    if missing:
        print(f"tasks without done criteria: {', '.join(missing)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
