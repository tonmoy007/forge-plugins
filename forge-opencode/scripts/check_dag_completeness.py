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
DONE = re.compile(r"done[\s\-]*when|done\s*:", re.IGNORECASE)
# A task *definition* is a heading line carrying a T-id (not a passing mention in a
# dependency graph), so a deps section listing the same ids doesn't create phantoms.
TASK_HEADING = re.compile(r"^#{1,6}\s+.*?\b(T-\d+)\b.*$", re.MULTILINE)
TASK_ANY = re.compile(r"^\s*[-*]?\s*\**(T-\d+)\b.*$", re.MULTILINE)


def _task_blocks(text: str) -> list[tuple[str, str]]:
    matches = list(TASK_HEADING.finditer(text)) or list(TASK_ANY.finditer(text))
    blocks = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        blocks.append((m.group(1), text[start:end]))
    return blocks


def main() -> int:
    if not DAG.exists():
        print(f"task DAG not found: {DAG}", file=sys.stderr)
        return 1
    blocks = _task_blocks(DAG.read_text())
    if not blocks:
        print("no tasks (T-NNN) found in the DAG", file=sys.stderr)
        return 1

    missing: list[str] = []
    seen: set[str] = set()
    for tid, block in blocks:
        if tid in seen:
            continue
        seen.add(tid)
        if not DONE.search(block):
            missing.append(tid)
    if missing:
        print(f"tasks without done criteria: {', '.join(missing)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
