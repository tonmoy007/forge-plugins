#!/usr/bin/env python3
"""Gate G1-003: every requirement in the SRS has acceptance criteria.

Usage: check_srs_acceptance.py <srs.md>
Exit 0 if every REQ-* block declares acceptance criteria; 1 otherwise.

A requirement "has acceptance criteria" if its block (text from one REQ heading
up to the next REQ/NFR heading) contains an `AC-*` token or the word
"acceptance" (case-insensitive).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REQ_ID = re.compile(r"\bREQ-[A-Z0-9]+(?:-[A-Z0-9]+)*\b")
ACCEPTANCE = re.compile(r"\bAC-[A-Z0-9]|acceptance", re.IGNORECASE)


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: check_srs_acceptance.py <srs.md>", file=sys.stderr)
        return 2
    path = Path(argv[0])
    if not path.exists():
        print(f"SRS not found: {path}", file=sys.stderr)
        return 1

    text = path.read_text()
    # Split into blocks at each REQ id occurrence (keep order).
    matches = list(REQ_ID.finditer(text))
    if not matches:
        print("no requirements (REQ-*) found in SRS", file=sys.stderr)
        return 1

    missing: list[str] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end]
        if not ACCEPTANCE.search(block):
            missing.append(m.group(0))

    # de-dup while preserving order
    seen = set()
    missing = [r for r in missing if not (r in seen or seen.add(r))]
    if missing:
        print(f"requirements without acceptance criteria: {', '.join(missing)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
