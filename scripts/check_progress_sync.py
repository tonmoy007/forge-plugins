#!/usr/bin/env python3
"""Gate G6-006: progress.md reflects every task in the DAG.

Runs with cwd = project root. Every task id in pipeline/05-plan/task-dag.md must
appear in pipeline/06-implementation/progress.md (the tracker is in sync with the
plan). Exit 0 if every task is present; 1 otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DAG = Path("pipeline/05-plan/task-dag.md")
PROGRESS = Path("pipeline/06-implementation/progress.md")
TASK_ID = re.compile(r"\bT-\d+\b")


def main() -> int:
    if not DAG.exists():
        print(f"task DAG not found: {DAG}", file=sys.stderr)
        return 1
    if not PROGRESS.exists():
        print(f"progress tracker not found: {PROGRESS}", file=sys.stderr)
        return 1

    dag_ids = []
    seen: set[str] = set()
    for t in TASK_ID.findall(DAG.read_text()):
        if t not in seen:
            seen.add(t)
            dag_ids.append(t)
    progress_ids = set(TASK_ID.findall(PROGRESS.read_text()))

    missing = [t for t in dag_ids if t not in progress_ids]
    if missing:
        print(f"tasks in the DAG missing from progress.md: {', '.join(missing)}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
