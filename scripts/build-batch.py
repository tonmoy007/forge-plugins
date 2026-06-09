#!/usr/bin/env python3
"""Plan a milestone-scoped batch build (REQ-BUILDBATCH-001 / T-116).

`/forge:build --milestone N` drives every task under `## Milestone N:` in the
project's task DAG, in dependency order, one task at a time (build → test →
commit `feat(T-XXX)` → mark done). This helper does the deterministic part — it
emits the ordered task list the skill walks — so ordering, --resume, and the
large-batch warning are testable without the LLM in the loop.

Usage (cwd = project root):
    build-batch.py --milestone N [--cwd PATH] [--resume]

Prints the ordered T-IDs (one per line) to stdout. With --resume, tasks already
marked done in pipeline/06-implementation/progress.md are skipped. Warns on
stderr when the batch is larger than --warn-over (default 10). Exit 1 if the
milestone is not found.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DAG_RELPATH = "pipeline/05-plan/task-dag.md"
PROGRESS_RELPATH = "pipeline/06-implementation/progress.md"

TASK_HEADING = re.compile(r"^#{2,4}\s+.*?\b(T-\d+)\b", re.MULTILINE)
TASK_ID = re.compile(r"\bT-\d+\b")
DONE_MARK = re.compile(r"🟢|✅|\bdone\b|\[x\]", re.IGNORECASE)


def _milestone_section(text: str, n: int) -> str | None:
    """Return the text of `## Milestone N:` up to the next `## ` heading."""
    pat = re.compile(rf"^##\s+Milestone\s+{n}\b.*?$", re.MULTILINE)
    m = pat.search(text)
    if not m:
        return None
    start = m.end()
    nxt = re.search(r"^##\s+", text[start:], re.MULTILINE)
    return text[start:start + nxt.start()] if nxt else text[start:]


def _tasks_in_section(section: str) -> list[tuple[str, set[str]]]:
    """Return [(task_id, {dep_ids})] for each `### T-NNN` block in order."""
    matches = list(TASK_HEADING.finditer(section))
    tasks: list[tuple[str, set[str]]] = []
    for i, mt in enumerate(matches):
        tid = mt.group(1)
        start = mt.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(section)
        block = section[start:end]
        deps: set[str] = set()
        dm = re.search(r"Depends on\*?\*?:\s*(.+)", block, re.IGNORECASE)
        if dm:
            deps = {d for d in TASK_ID.findall(dm.group(1))}
        tasks.append((tid, deps))
    return tasks


def _topo_order(tasks: list[tuple[str, set[str]]]) -> list[str]:
    """Dependency-first order; ties broken by original (task-number) order."""
    in_set = {t for t, _ in tasks}
    order_index = {t: i for i, (t, _) in enumerate(tasks)}
    deps = {t: {d for d in ds if d in in_set} for t, ds in tasks}
    resolved: list[str] = []
    placed: set[str] = set()
    remaining = [t for t, _ in tasks]
    while remaining:
        ready = [t for t in remaining if deps[t] <= placed]
        if not ready:  # dependency cycle — fall back to declared order
            ready = [min(remaining, key=lambda t: order_index[t])]
        nxt = min(ready, key=lambda t: order_index[t])
        resolved.append(nxt)
        placed.add(nxt)
        remaining.remove(nxt)
    return resolved


def _done_tasks(cwd: Path) -> set[str]:
    progress = cwd / PROGRESS_RELPATH
    if not progress.exists():
        return set()
    done: set[str] = set()
    for line in progress.read_text().splitlines():
        if DONE_MARK.search(line):
            done.update(TASK_ID.findall(line))
    return done


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build-batch.py")
    parser.add_argument("--milestone", required=True, type=int, metavar="N")
    parser.add_argument("--cwd", default=".", metavar="PATH")
    parser.add_argument("--resume", action="store_true",
                        help="skip tasks already marked done in progress.md")
    parser.add_argument("--warn-over", type=int, default=10, metavar="K")
    args = parser.parse_args(argv)

    cwd = Path(args.cwd)
    dag = cwd / DAG_RELPATH
    if not dag.exists():
        print(f"task DAG not found: {dag}", file=sys.stderr)
        return 1

    section = _milestone_section(dag.read_text(), args.milestone)
    if section is None:
        print(f"milestone {args.milestone} not found in {DAG_RELPATH}", file=sys.stderr)
        return 1

    tasks = _tasks_in_section(section)
    if not tasks:
        print(f"milestone {args.milestone} has no tasks", file=sys.stderr)
        return 1

    if len(tasks) > args.warn_over:
        print(
            f"[Forge] large batch — {len(tasks)} tasks in milestone {args.milestone}; "
            f"consider splitting or building per-task.",
            file=sys.stderr,
        )

    ordered = _topo_order(tasks)
    if args.resume:
        done = _done_tasks(cwd)
        ordered = [t for t in ordered if t not in done]

    for tid in ordered:
        print(tid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
