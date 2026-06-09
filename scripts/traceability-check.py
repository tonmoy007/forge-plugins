#!/usr/bin/env python3
"""Traceability gate (G2-007, G3-006, G5-006, G12-006).

Modes:
  --from A --to B               every reference in A whose ID-type is defined in B
                                must resolve to a B id; if A has task ids, each
                                task must reference a resolvable requirement.
  --from A --to B --prefix P     each P-prefixed item in A must reference at least
                                one id defined in B.
  --full-chain                  validate the standard pipeline chain
                                (PRD FEATs → SRS REQs, task-dag tasks → SRS REQs).

Runs with cwd = project root. Exit 0 on an intact chain; 1 otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REF_ID = re.compile(r"\b(?:REQ|NFR|FEAT|UF)-[A-Z0-9]+(?:-[A-Z0-9]+)*\b")
TASK_ID = re.compile(r"\bT-\d+\b")
# A task *definition* is a heading carrying a T-id; falls back to any line-leading
# T-id so simple `## T-001` fixtures still work and dependency graphs don't count.
TASK_HEADING = re.compile(r"^#{1,6}\s+.*?\b(T-\d+)\b.*$", re.MULTILINE)
TASK_LINE = re.compile(r"^\s*[-*]?\s*\**(T-\d+)\b.*$", re.MULTILINE)


def _ids(text: str) -> list[str]:
    return REF_ID.findall(text)


def _prefix(token: str) -> str:
    return token.split("-", 1)[0]


def _blocks(text: str, marker: re.Pattern) -> list[tuple[str, str]]:
    """Return (id, block-text) for each marker occurrence (block runs to the next)."""
    matches = list(marker.finditer(text))
    out = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((m.group(0), text[start:end]))
    return out


def _check_pair(src_text: str, target_text: str, prefix: str | None) -> list[str]:
    """Return a list of error strings (empty = pass)."""
    target_ids = set(_ids(target_text))
    errors: list[str] = []

    if prefix:
        marker = re.compile(rf"\b{prefix}-[A-Z0-9]+(?:-[A-Z0-9]+)*\b")
        items = _blocks(src_text, marker)
        if not items:
            return [f"no {prefix}-* items found in source"]
        for item_id, block in items:
            refs = [r for r in _ids(block) if r in target_ids]
            if not refs:
                errors.append(f"{item_id} references no defined requirement")
        # de-dup
        seen: set[str] = set()
        return [e for e in errors if not (e in seen or seen.add(e))]

    # default mode: same-prefix-gated dangling check
    target_prefixes = {_prefix(t) for t in target_ids}
    dangling = sorted({
        r for r in _ids(src_text)
        if _prefix(r) in target_prefixes and r not in target_ids
    })
    if dangling:
        errors.append("references with no match in target: " + ", ".join(dangling))

    # if the source defines tasks, each must reference a resolvable requirement
    task_matches = list(TASK_HEADING.finditer(src_text)) or list(TASK_LINE.finditer(src_text))
    seen: set[str] = set()
    for i, m in enumerate(task_matches):
        tid = m.group(1)
        if tid in seen:
            continue
        seen.add(tid)
        start = m.start()
        end = task_matches[i + 1].start() if i + 1 < len(task_matches) else len(src_text)
        block = src_text[start:end]
        if not any(r in target_ids for r in _ids(block)):
            errors.append(f"task {tid} references no defined requirement")
    return errors


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="traceability-check.py")
    parser.add_argument("--from", dest="src")
    parser.add_argument("--to", dest="target")
    parser.add_argument("--prefix")
    parser.add_argument("--full-chain", action="store_true")
    args = parser.parse_args(argv)

    if args.full_chain:
        chain = [
            ("pipeline/02-product-ux/prd.md", "pipeline/01-srs/srs.md", "FEAT"),
            ("pipeline/05-plan/task-dag.md", "pipeline/01-srs/srs.md", None),
        ]
        errors: list[str] = []
        for src, target, prefix in chain:
            sp, tp = Path(src), Path(target)
            if not sp.exists() or not tp.exists():
                errors.append(f"chain link missing: {src} -> {target}")
                continue
            errors += _check_pair(sp.read_text(), tp.read_text(), prefix)
        if errors:
            print("traceability chain broken:", file=sys.stderr)
            for e in errors[:20]:
                print(f"  {e}", file=sys.stderr)
            return 1
        return 0

    if not args.src or not args.target:
        print("error: --from and --to are required (or use --full-chain)", file=sys.stderr)
        return 2
    sp, tp = Path(args.src), Path(args.target)
    for p in (sp, tp):
        if not p.exists():
            print(f"file not found: {p}", file=sys.stderr)
            return 1
    errors = _check_pair(sp.read_text(), tp.read_text(), args.prefix)
    if errors:
        for e in errors[:20]:
            print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
