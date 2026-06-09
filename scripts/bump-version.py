#!/usr/bin/env python3
"""Advance the plugin version in one command.

The plugin version lives in exactly two files — `.claude-plugin/plugin.json` and
`.claude-plugin/marketplace.json` — and every release also opens a dated
CHANGELOG section. Doing this by hand is what produced the inverted-ordering
gotcha during the v0.1.5 release (newest section landed at the bottom). This
script makes it mechanical and ordering-correct:

  bump-version.py X.Y.Z [--date YYYY-MM-DD] [--repo-root DIR]

It (1) asserts both manifests currently hold the *same* version, (2) rewrites
that key in both to X.Y.Z, and (3) inserts a `## [X.Y.Z] — <date>` skeleton
directly under `## [Unreleased]`, above the previous release. It refuses to run
(exit 2, nothing written) if the manifests disagree or a `## [X.Y.Z]` section
already exists, so re-runs are safe.

Stdlib only — no new runtime dependency.
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

_VERSION_RE = re.compile(r'("version"\s*:\s*")([^"]*)(")')


def read_manifest_version(text: str) -> str:
    """Return the value of the (single) "version" key in a manifest's text."""
    matches = _VERSION_RE.findall(text)
    if len(matches) != 1:
        raise ValueError(f'expected exactly one "version" key, found {len(matches)}')
    return matches[0][1]


def set_manifest_version(text: str, new_version: str) -> str:
    """Rewrite the single "version" value, preserving all other formatting."""
    new_text, n = _VERSION_RE.subn(rf'\g<1>{new_version}\g<3>', text)
    if n != 1:
        raise ValueError(f'expected exactly one "version" key to rewrite, found {n}')
    return new_text


def insert_changelog(text: str, version: str, date: str) -> str:
    """Insert a dated release skeleton above the most recent release section.

    The skeleton goes directly below the `## [Unreleased]` block (its `---`
    separator) and above the first existing `## [x.y.z]` heading, keeping the
    file newest-first. Raises if a `## [{version}]` section already exists.
    """
    if f"## [{version}]" in text:
        raise ValueError(f"CHANGELOG already has a [{version}] section")

    skeleton = (
        f"## [{version}] — {date}\n\n"
        "### Added\n\n"
        "### Changed\n\n"
        "### Fixed\n\n"
        "---\n\n"
    )

    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("## [") and not line.startswith("## [Unreleased]"):
            return "".join(lines[:i]) + skeleton + "".join(lines[i:])

    # No prior release section — append at the end.
    sep = "" if text.endswith("\n") else "\n"
    return text + sep + "\n" + skeleton


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="bump-version.py")
    parser.add_argument("version", help="new semver, e.g. 0.1.6")
    parser.add_argument("--date", help="release date YYYY-MM-DD (default: today)")
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).parent.parent),
        help="repo root containing .claude-plugin/ and CHANGELOG.md",
    )
    args = parser.parse_args(argv)

    root = Path(args.repo_root)
    plugin_path = root / ".claude-plugin" / "plugin.json"
    marketplace_path = root / ".claude-plugin" / "marketplace.json"
    changelog_path = root / "CHANGELOG.md"
    date = args.date or datetime.date.today().isoformat()

    plugin_text = plugin_path.read_text()
    marketplace_text = marketplace_path.read_text()
    changelog_text = changelog_path.read_text()

    # Validate everything BEFORE writing so a bad run leaves the tree untouched.
    try:
        plugin_ver = read_manifest_version(plugin_text)
        marketplace_ver = read_manifest_version(marketplace_text)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if plugin_ver != marketplace_ver:
        print(
            f"ERROR: manifests disagree — plugin.json={plugin_ver!r}, "
            f"marketplace.json={marketplace_ver!r}; fix before bumping.",
            file=sys.stderr,
        )
        return 2

    try:
        new_changelog = insert_changelog(changelog_text, args.version, date)
        new_plugin = set_manifest_version(plugin_text, args.version)
        new_marketplace = set_manifest_version(marketplace_text, args.version)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    plugin_path.write_text(new_plugin)
    marketplace_path.write_text(new_marketplace)
    changelog_path.write_text(new_changelog)

    print(f"Bumped {plugin_ver} → {args.version} (date {date})")
    print("  - .claude-plugin/plugin.json")
    print("  - .claude-plugin/marketplace.json")
    print(f"  - CHANGELOG.md  (new ## [{args.version}] — {date} section)")
    print("Next: fill in the CHANGELOG section, then run pre-release verification.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
