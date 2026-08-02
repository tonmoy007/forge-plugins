#!/usr/bin/env python3
"""Gate G12-004: the release version is tagged in git.

Runs with cwd = project root. Passes if `git tag` lists at least one
version-like tag (optional leading 'v', then N.N[.N...]). Exit 1 if there is no
such tag, or if cwd is not a git repository.
"""

from __future__ import annotations

import re
import subprocess
import sys

VERSION_TAG = re.compile(r"^v?\d+\.\d+(\.\d+)*")


def main() -> int:
    try:
        result = subprocess.run(
            ["git", "tag", "--list"], capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print(f"could not run git: {exc}", file=sys.stderr)
        return 1
    if result.returncode != 0:
        print(f"not a git repository: {result.stderr.strip()}", file=sys.stderr)
        return 1

    tags = [t.strip() for t in result.stdout.splitlines() if t.strip()]
    version_tags = [t for t in tags if VERSION_TAG.match(t)]
    if not version_tags:
        print("no version tag found (expected e.g. v0.1.5)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
