#!/usr/bin/env python3
"""Resolve and read a stage document in either layout (REQ-LARGEDOC-001 / T-123).

A stage document may live as a single file or, once it grows past a readable
size, as a directory with an `index.md` manifest listing its parts in order:

    pipeline/04-spec/technical-spec.md                 # single-file (legacy)
    pipeline/04-spec/technical-spec/index.md           # multi-file manifest
    pipeline/04-spec/technical-spec/01-overview.md
    pipeline/04-spec/technical-spec/02-interfaces.md

Usage (cwd = project root):
    read-doc.py <doc-base-path>     # e.g. pipeline/04-spec/technical-spec  (.md optional)

Prints the concatenated document content to stdout (manifest order for the
multi-file layout). Exit 1 if neither layout is present.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

MD_LINK = re.compile(r"([A-Za-z0-9._\-/]+\.md)")


def resolve(base: Path) -> list[Path]:
    """Return the ordered list of files backing the document, or [] if absent."""
    base = Path(str(base))
    # Normalize: allow callers to pass either `foo` or `foo.md`.
    stem = base.with_suffix("") if base.suffix == ".md" else base

    single = stem.with_suffix(".md")
    if single.is_file():
        return [single]

    index = stem / "index.md"
    if index.is_file():
        parts: list[Path] = []
        seen: set[str] = set()
        for name in MD_LINK.findall(index.read_text()):
            fname = Path(name).name
            if fname == "index.md" or fname in seen:
                continue
            candidate = stem / fname
            if candidate.is_file():
                seen.add(fname)
                parts.append(candidate)
        # Fall back to all .md files (sorted) if the manifest lists nothing usable.
        if not parts:
            parts = sorted(p for p in stem.glob("*.md") if p.name != "index.md")
        return [index] + parts
    return []


def load(base: Path) -> str:
    files = resolve(base)
    return "\n\n".join(f.read_text() for f in files)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("usage: read-doc.py <doc-base-path>", file=sys.stderr)
        return 2
    base = Path(args[0])
    files = resolve(base)
    if not files:
        print(f"document not found in either layout: {base}", file=sys.stderr)
        return 1
    sys.stdout.write(load(base))
    return 0


if __name__ == "__main__":
    sys.exit(main())
