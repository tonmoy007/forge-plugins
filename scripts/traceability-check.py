#!/usr/bin/env python3
"""Gate G5-006 / G12-006: traceability between two pipeline artifacts.

Usage: traceability-check.py --from <src.md> --to <target.md>
Exit 0 if every requirement reference in <src> resolves to an ID defined in
<target>, and (when <src> contains task IDs) every task references at least one
such requirement; 1 otherwise.

Example: --from task-dag.md --to srs.md  → every task references a real REQ.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REF_ID = re.compile(r"\b(?:REQ|NFR|FEAT)-[A-Z0-9]+(?:-[A-Z0-9]+)*\b")
TASK_ID = re.compile(r"\bT-\d+\b")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="traceability-check.py")
    parser.add_argument("--from", dest="src", required=True)
    parser.add_argument("--to", dest="target", required=True)
    args = parser.parse_args(argv)

    src_path, target_path = Path(args.src), Path(args.target)
    for p in (src_path, target_path):
        if not p.exists():
            print(f"file not found: {p}", file=sys.stderr)
            return 1

    src_text = src_path.read_text()
    target_text = target_path.read_text()
    target_ids = set(REF_ID.findall(target_text))

    # 1) Every requirement reference in src must resolve to a target id.
    dangling = sorted({r for r in REF_ID.findall(src_text) if r not in target_ids})
    if dangling:
        print(f"references with no match in {target_path.name}: {', '.join(dangling)}",
              file=sys.stderr)
        return 1

    # 2) If src has task blocks, each task must reference at least one requirement.
    task_matches = list(TASK_ID.finditer(src_text))
    if task_matches:
        unreferenced: list[str] = []
        for i, m in enumerate(task_matches):
            start = m.start()
            end = task_matches[i + 1].start() if i + 1 < len(task_matches) else len(src_text)
            block = src_text[start:end]
            if not REF_ID.search(block):
                unreferenced.append(m.group(0))
        seen: set[str] = set()
        unreferenced = [t for t in unreferenced if not (t in seen or seen.add(t))]
        if unreferenced:
            print(f"tasks not referencing any requirement: {', '.join(unreferenced)}",
                  file=sys.stderr)
            return 1
    else:
        # No tasks and no references at all → nothing to trace; treat as a gap.
        if not REF_ID.search(src_text):
            print(f"no requirement references found in {src_path.name}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
