#!/usr/bin/env python3
"""Gate G6-004: test coverage above a threshold.

Usage: check_coverage.py [--min N]   (runs with cwd = project root)
Reads a coverage report if present:
  - coverage.xml  (Cobertura `line-rate` attribute), or
  - coverage.json (`totals.percent_covered`).
Exit 1 if measured coverage < N. If no report exists there is nothing to
measure, so exit 0 (this is a warning-severity gate; absence is not a failure).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def _coverage_pct() -> float | None:
    xml = Path("coverage.xml")
    if xml.exists():
        m = re.search(r'line-rate="([0-9.]+)"', xml.read_text())
        if m:
            return float(m.group(1)) * 100.0
    js = Path("coverage.json")
    if js.exists():
        try:
            data = json.loads(js.read_text())
            pct = data.get("totals", {}).get("percent_covered")
            if isinstance(pct, (int, float)):
                return float(pct)
        except (json.JSONDecodeError, OSError):
            return None
    return None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="check_coverage.py")
    parser.add_argument("--min", type=float, default=80.0)
    args = parser.parse_args(argv)

    pct = _coverage_pct()
    if pct is None:
        print("no coverage report found (coverage.xml / coverage.json) — skipping",
              file=sys.stderr)
        return 0
    if pct < args.min:
        print(f"coverage {pct:.1f}% is below the {args.min:.0f}% threshold", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
