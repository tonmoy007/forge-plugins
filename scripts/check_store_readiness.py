#!/usr/bin/env python3
"""Gate G12-MOBILE-001: app store metadata present for each targeted platform.

Detects which mobile platform(s) the project targets and requires their store
metadata. Only platforms that are actually present are checked; if no mobile
platform is detected at all, the gate is a no-op (exit 0).

Requirements per platform:
  - iOS:     an `Info.plist` (anywhere in the tree) containing both
             `CFBundleIdentifier` and `CFBundleShortVersionString`.
  - Android: a `build.gradle` (anywhere in the tree) containing `applicationId`,
             `versionCode`, and `versionName`.
  - Flutter: a `pubspec.yaml` at the root with a `version:` line.

Exit 0 when every present-platform requirement is met (or no platform present).
Exit 1 listing what is missing. Robust to unreadable files. Stdlib only.

Ref: T-132 / REQ-PROFILE-MOBILE-001
"""

from __future__ import annotations

import argparse
import os
import re
import sys

# Directories not worth walking for platform metadata.
_IGNORE_DIRS = frozenset({
    ".git", ".hg", ".svn",
    "node_modules", ".venv", "venv", "env",
    "__pycache__", ".pytest_cache", ".mypy_cache",
    ".forge", "pipeline", "build", "dist",
    ".idea", ".vscode", ".gradle", "Pods",
})


def _read(path: str) -> str:
    """Read a file's text, returning '' on any error (robust to unreadable files)."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except OSError:
        return ""


def _walk_files(cwd: str, filename: str) -> list[str]:
    """Return paths to every file named `filename` under cwd, skipping ignore dirs."""
    found: list[str] = []
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]
        if filename in files:
            found.append(os.path.join(root, filename))
    return found


def _check_ios(cwd: str, missing: list[str]) -> bool:
    """Return True if iOS is targeted (an Info.plist exists). Append gaps to `missing`."""
    plists = _walk_files(cwd, "Info.plist")
    if not plists:
        return False
    # Any single Info.plist satisfying both keys is enough.
    for path in plists:
        text = _read(path)
        if "CFBundleIdentifier" in text and "CFBundleShortVersionString" in text:
            return True
    missing.append(
        "iOS: Info.plist must contain CFBundleIdentifier and CFBundleShortVersionString"
    )
    return True


def _check_android(cwd: str, missing: list[str]) -> bool:
    """Return True if Android is targeted (a build.gradle exists). Append gaps."""
    gradles = _walk_files(cwd, "build.gradle")
    if not gradles:
        return False
    for path in gradles:
        text = _read(path)
        if all(field in text for field in ("applicationId", "versionCode", "versionName")):
            return True
    missing.append(
        "Android: build.gradle must contain applicationId, versionCode, and versionName"
    )
    return True


def _check_flutter(cwd: str, missing: list[str]) -> bool:
    """Return True if Flutter is targeted (root pubspec.yaml exists). Append gaps."""
    pubspec = os.path.join(cwd, "pubspec.yaml")
    if not os.path.isfile(pubspec):
        return False
    text = _read(pubspec)
    if re.search(r"(?m)^\s*version:\s*\S+", text):
        return True
    missing.append("Flutter: pubspec.yaml must contain a version: line")
    return True


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", default=".", help="project root to inspect (default: .)")
    args = parser.parse_args(argv)

    cwd = os.path.abspath(args.cwd)
    missing: list[str] = []

    targeted = [
        _check_ios(cwd, missing),
        _check_android(cwd, missing),
        _check_flutter(cwd, missing),
    ]

    if not any(targeted):
        # No mobile platform present — nothing to gate.
        print("G12-MOBILE-001 PASS: no mobile platform detected; nothing to gate.")
        return 0

    if missing:
        print("G12-MOBILE-001 FAIL: missing app store metadata:")
        for item in missing:
            print(f"  - {item}")
        return 1

    print("G12-MOBILE-001 PASS: store metadata present for all targeted platform(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
