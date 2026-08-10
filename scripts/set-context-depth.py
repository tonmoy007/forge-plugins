#!/usr/bin/env python3
"""`/forge:plan-pro`'s Stage 5 entry sets `build_context_depth` in pipeline/state.md
(T-252, REQ-BUILDCTX-002).

Validates the requested depth against the three allowed values and updates
state.md atomically via _state_lib, mirroring set-profile.py's project_type
pattern. `--dry-run` previews without writing. Refuses to overwrite an
already-set value unless `--force` is passed -- the skill only calls this once,
when the field is absent (AC-BUILDCTX-002c: never re-prompt).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _state_lib as lib  # noqa: E402

VALID_DEPTHS = ("spec_plan", "spec_arch_plan", "full_chain")


def set_context_depth(
    cwd: str, depth: str, *, force: bool = False, dry_run: bool = False
) -> tuple[int, str]:
    """Set build_context_depth. Returns (exit_code, message). Never sys.exits."""
    state_path = Path(cwd) / "pipeline" / "state.md"
    if not state_path.exists():
        return 1, "pipeline/state.md not found — run /forge:init first."

    if depth not in VALID_DEPTHS:
        return 1, f"unknown depth '{depth}'. Valid depths: {', '.join(VALID_DEPTHS)}"

    current = lib.read_state(cwd)
    existing = current.get("build_context_depth")
    if existing and not force:
        return 0, (
            f"build_context_depth is already '{existing}' — not re-prompting "
            "(pass --force to override an explicit prior choice)."
        )
    if dry_run:
        return 0, f"[dry-run] would set build_context_depth: {existing or '(unset)'} → {depth}"

    current["build_context_depth"] = depth
    lib.write_state(cwd, current)
    return 0, f"build_context_depth set: {existing or '(unset)'} → {depth}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="set-context-depth")
    parser.add_argument("depth", choices=VALID_DEPTHS)
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--force", action="store_true", help="overwrite an already-set value")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    code, message = set_context_depth(args.cwd, args.depth, force=args.force, dry_run=args.dry_run)
    print(message)
    return code


if __name__ == "__main__":
    sys.exit(main())
