#!/usr/bin/env python3
"""Gate G4-004: the technical spec covers every component from the architecture.

Runs with cwd = project root (no positional args). Reads:
  pipeline/03-architecture/architecture.md   (component source of truth)
  pipeline/04-spec/technical-spec.md         (must mention each component)

Exit 0 if every architecture component name appears in the spec; 1 otherwise.
Component names are taken from `### <Name>` / `#### <Name>` headings and from
bold list markers `- **<Name>**` under the architecture doc.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ARCH = Path("pipeline/03-architecture/architecture.md")
SPEC = Path("pipeline/04-spec/technical-spec.md")

HEADING = re.compile(r"^#{3,4}\s+(.+?)\s*$", re.MULTILINE)
BOLD_ITEM = re.compile(r"^\s*[-*]\s+\*\*(.+?)\*\*", re.MULTILINE)
# Headings that are structural, not components.
SKIP = {"overview", "components", "data model", "adrs", "summary", "context",
        "containers", "diagram", "c4", "architecture"}


def _components(arch_text: str) -> list[str]:
    names: list[str] = []
    for m in HEADING.finditer(arch_text):
        name = m.group(1).strip()
        if name.lower() not in SKIP:
            names.append(name)
    for m in BOLD_ITEM.finditer(arch_text):
        names.append(m.group(1).strip())
    # de-dup, preserve order
    seen: set[str] = set()
    return [n for n in names if not (n.lower() in seen or seen.add(n.lower()))]


def main() -> int:
    if not ARCH.exists():
        print(f"architecture not found: {ARCH}", file=sys.stderr)
        return 1
    if not SPEC.exists():
        print(f"technical spec not found: {SPEC}", file=sys.stderr)
        return 1

    components = _components(ARCH.read_text())
    if not components:
        # Nothing identifiable to cover — warning-severity gate, treat as pass.
        return 0

    spec_text = SPEC.read_text().lower()
    uncovered = [c for c in components if c.lower() not in spec_text]
    if uncovered:
        print(f"components not covered by the spec: {', '.join(uncovered)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
