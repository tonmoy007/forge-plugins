#!/usr/bin/env python3
"""Exit 0 if the directory argument has at least one non-hidden file, 1 otherwise."""
import sys
from pathlib import Path

if len(sys.argv) != 2:
    print(f"usage: {sys.argv[0]} <directory>", file=sys.stderr)
    sys.exit(2)

d = Path(sys.argv[1])
if not d.is_dir():
    print(f"not a directory: {d}", file=sys.stderr)
    sys.exit(1)

entries = [p for p in d.iterdir() if not p.name.startswith(".")]
if entries:
    sys.exit(0)
else:
    print(f"directory is empty: {d}", file=sys.stderr)
    sys.exit(1)
