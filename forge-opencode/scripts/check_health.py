#!/usr/bin/env python3
"""Gate G8-004: health checks pass.

Runs with cwd = project root. Reads pipeline/09-monitor/health-report.md and
fails if it is missing or contains an unhealthy marker (unhealthy / down /
critical / failed / ❌). Exit 0 only when a report exists with no such markers.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPORT = Path("pipeline/09-monitor/health-report.md")
UNHEALTHY = re.compile(r"\b(unhealthy|down|critical|failed|fail)\b|❌", re.IGNORECASE)


def main() -> int:
    if not REPORT.exists():
        print(f"health report not found: {REPORT}", file=sys.stderr)
        return 1
    text = REPORT.read_text()
    hits = [ln.strip()[:80] for ln in text.splitlines() if UNHEALTHY.search(ln)]
    if hits:
        print("health report shows unhealthy signals:", file=sys.stderr)
        for h in hits[:10]:
            print(f"  {h}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
