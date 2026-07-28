#!/usr/bin/env python3
"""Gate G7-003: every NFR target is evaluated.

Runs with cwd = project root. Each NFR id declared in pipeline/01-srs/srs.md must
appear in pipeline/07-evaluation/eval-report.md (it was evaluated). Exit 0 if
every NFR is evaluated (or the SRS declares no NFRs); 1 otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SRS = Path("pipeline/01-srs/srs.md")
EVAL = Path("pipeline/07-evaluation/eval-report.md")
NFR_ID = re.compile(r"\bNFR-[A-Z0-9]+(?:-[A-Z0-9]+)*\b")


def main() -> int:
    if not SRS.exists():
        print(f"SRS not found: {SRS}", file=sys.stderr)
        return 1

    nfr_ids = []
    seen: set[str] = set()
    for n in NFR_ID.findall(SRS.read_text()):
        if n not in seen:
            seen.add(n)
            nfr_ids.append(n)
    if not nfr_ids:
        return 0  # nothing to cover

    if not EVAL.exists():
        print(f"eval report not found: {EVAL} ({len(nfr_ids)} NFRs unevaluated)",
              file=sys.stderr)
        return 1
    eval_ids = set(NFR_ID.findall(EVAL.read_text()))
    missing = [n for n in nfr_ids if n not in eval_ids]
    if missing:
        print(f"NFRs not evaluated in the eval report: {', '.join(missing)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
