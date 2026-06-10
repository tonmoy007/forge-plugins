#!/usr/bin/env python3
"""`/forge:set-profile <type>` — switch the project_type in pipeline/state.md
(T-140, REQ-F-051).

Validates the requested type against the known profile list (the `## Profile:`
blocks in references/project-type-profiles.md, so it stays in sync with detection)
and updates state.md atomically via _state_lib. `--dry-run` previews without writing.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_PLUGIN_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).parent))
import _state_lib as lib  # noqa: E402


def known_profiles(plugin_dir: Path) -> list[str]:
    """Profile names declared in references/project-type-profiles.md."""
    try:
        text = (plugin_dir / "references" / "project-type-profiles.md").read_text()
    except OSError:
        return []
    return sorted(set(re.findall(r"^## Profile:\s*([a-z0-9-]+)", text, re.MULTILINE)))


def set_profile(cwd: str, profile: str, *, plugin_dir: Path, dry_run: bool = False) -> tuple[int, str]:
    """Set project_type to `profile`. Returns (exit_code, message). Never sys.exits."""
    state_path = Path(cwd) / "pipeline" / "state.md"
    if not state_path.exists():
        return 1, "pipeline/state.md not found — run /forge:init first."

    names = known_profiles(plugin_dir)
    if profile not in names:
        valid = ", ".join(names) if names else "(none found)"
        return 1, f"unknown profile '{profile}'. Valid profiles: {valid}"

    current = lib.read_state(cwd)
    old = current.get("project_type", "unknown")
    if old == profile:
        return 0, f"project_type is already '{profile}' — no change."
    if dry_run:
        return 0, f"[dry-run] would set project_type: {old} → {profile}"

    current["project_type"] = profile
    lib.write_state(cwd, current)
    return 0, f"project_type set: {old} → {profile}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="set-profile")
    parser.add_argument("profile", help="project type to switch to")
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--plugin-dir", default=str(_PLUGIN_DIR))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    code, msg = set_profile(args.cwd, args.profile, plugin_dir=Path(args.plugin_dir), dry_run=args.dry_run)
    print(msg, file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
