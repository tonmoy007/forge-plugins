#!/usr/bin/env python3
"""Gate G6-001: every DAG task is marked done.

Runs with cwd = project root. Reads the task ids from
pipeline/05-plan/task-dag.md and checks each is marked complete in
pipeline/06-implementation/progress.md (a row containing the T-id plus a
done marker: 🟢, ✅, "done", or "[x]").

Exit 0 if every task is marked done; 1 otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DAG = Path("pipeline/05-plan/task-dag.md")
PROGRESS = Path("pipeline/06-implementation/progress.md")
TASK_ID = re.compile(r"\bT-\d+\b")
DONE_MARK = re.compile(r"🟢|✅|\bdone\b|\[x\]", re.IGNORECASE)


def main() -> int:
    if not DAG.exists():
        print(f"task DAG not found: {DAG}", file=sys.stderr)
        return 1
    if not PROGRESS.exists():
        print(f"progress tracker not found: {PROGRESS}", file=sys.stderr)
        return 1

    task_ids = []
    seen: set[str] = set()
    for t in TASK_ID.findall(DAG.read_text()):
        if t not in seen:
            seen.add(t)
            task_ids.append(t)
    if not task_ids:
        print("no tasks (T-NNN) found in the DAG", file=sys.stderr)
        return 1

    incomplete: list[str] = []
    progress_lines = PROGRESS.read_text().splitlines()
    for tid in task_ids:
        # A task is done if some line names it AND carries a done marker.
        rows = [ln for ln in progress_lines if re.search(rf"\b{re.escape(tid)}\b", ln)]
        if not rows or not any(DONE_MARK.search(ln) for ln in rows):
            incomplete.append(tid)
    if incomplete:
        print(f"tasks not marked done in progress.md: {', '.join(incomplete)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
