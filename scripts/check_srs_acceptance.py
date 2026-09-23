#!/usr/bin/env python3
"""Gate G1-003: every requirement in the SRS has acceptance criteria.

Usage: check_srs_acceptance.py <srs.md> [--id-pattern RE] [--acceptance-pattern RE]
                                        [--row-scoped]
Exit 0 if every REQ-* block declares acceptance criteria; 1 otherwise.

A requirement "has acceptance criteria" if its block (text from one REQ heading
up to the next REQ/NFR heading) contains an `AC-*` token or the word
"acceptance" (case-insensitive).

Options let a project whose SRS uses a different layout reuse this check from a
project gate override (pipeline/gate-criteria.md):

  --id-pattern RE          regex matching requirement definitions (MULTILINE). If it
                           has a capture group, group 1 is the reported ID.
  --acceptance-pattern RE  regex a block must match to count as having criteria.
  --row-scoped             when a match sits on a markdown table row (a line
                           starting with "|"), its block is that row alone.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REQ_ID = r"\bREQ-[A-Z0-9]+(?:-[A-Z0-9]+)*\b"
ACCEPTANCE = r"(?i)\bAC-[A-Z0-9]|acceptance"


def _block_end(text: str, start: int, next_start: int, row_scoped: bool) -> int:
    if row_scoped:
        line_start = text.rfind("\n", 0, start) + 1
        if text[line_start:start].lstrip().startswith("|"):
            line_end = text.find("\n", start)
            return len(text) if line_end == -1 else min(line_end, next_start)
    return next_start


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="check_srs_acceptance.py")
    parser.add_argument("srs")
    parser.add_argument("--id-pattern", default=REQ_ID)
    parser.add_argument("--acceptance-pattern", default=ACCEPTANCE)
    parser.add_argument("--row-scoped", action="store_true")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    try:
        req_id = re.compile(args.id_pattern, re.MULTILINE)
        acceptance = re.compile(args.acceptance_pattern)
    except re.error as exc:
        print(f"invalid regex: {exc}", file=sys.stderr)
        return 2

    path = Path(args.srs)
    if not path.exists():
        print(f"SRS not found: {path}", file=sys.stderr)
        return 1

    text = path.read_text()
    # Split into blocks at each REQ id occurrence (keep order).
    matches = list(req_id.finditer(text))
    if not matches:
        print("no requirements (REQ-*) found in SRS", file=sys.stderr)
        return 1

    missing: list[str] = []
    for i, m in enumerate(matches):
        start = m.start()
        next_start = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:_block_end(text, start, next_start, args.row_scoped)]
        if not acceptance.search(block):
            missing.append(m.group(1) if req_id.groups else m.group(0))

    # de-dup while preserving order
    seen = set()
    missing = [r for r in missing if not (r in seen or seen.add(r))]
    if missing:
        print(f"requirements without acceptance criteria: {', '.join(missing)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
