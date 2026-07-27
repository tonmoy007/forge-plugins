#!/usr/bin/env python3
"""Forge uninstall — remove Forge state from a project.

Removes pipeline/ and .forge/ from the current project, and optionally
~/.forge/ (shared cross-project state). Always shows what will be removed
before doing anything; requires confirmation unless --yes.

Does NOT unregister the plugin from Claude Code itself — that's a separate
action: `/plugin uninstall forge@forge-plugins`. The script reminds the user.

Usage:
    python scripts/uninstall.py
    python scripts/uninstall.py --dry-run             # preview only
    python scripts/uninstall.py --keep-artifacts      # keep pipeline/, remove runtime only
    python scripts/uninstall.py --include-global      # also offer to remove ~/.forge/
    python scripts/uninstall.py --yes                 # skip confirmation prompts
    python scripts/uninstall.py --json                # machine-readable output

Exit codes:
    0 — completed successfully (or nothing to do, or cancelled)
    1 — one or more removals failed
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

REINSTALL_HINT = (
    "/plugin marketplace add tonmoy007/forge-plugins  "
    "&&  /plugin install forge@forge-plugins"
)
PLUGIN_UNREGISTER_HINT = "/plugin uninstall forge@forge-plugins"


@dataclass
class Target:
    path: str           # str for JSON serializability
    kind: str           # "dir" | "file"
    size_bytes: int
    file_count: int
    label: str


@dataclass
class Removal:
    path: str
    status: str         # "removed" | "skipped" | "error"
    detail: str = ""


def directory_stats(path: Path) -> tuple[int, int]:
    """Return (total_bytes, file_count) for a directory tree."""
    total = 0
    count = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                fp = Path(root) / f
                total += fp.stat().st_size
                count += 1
            except OSError:
                continue
    return total, count


def format_size(n: int | float) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def discover_targets(
    cwd: Path,
    keep_artifacts: bool,
    include_global: bool,
) -> list[Target]:
    targets: list[Target] = []
    runtime = cwd / ".forge"
    if runtime.exists() and runtime.is_dir():
        size, cnt = directory_stats(runtime)
        targets.append(Target(
            path=str(runtime), kind="dir",
            size_bytes=size, file_count=cnt,
            label="Forge runtime state (sessions, lessons.yaml, hook errors)",
        ))
    if not keep_artifacts:
        pipeline = cwd / "pipeline"
        if pipeline.exists() and pipeline.is_dir():
            size, cnt = directory_stats(pipeline)
            targets.append(Target(
                path=str(pipeline), kind="dir",
                size_bytes=size, file_count=cnt,
                label="Pipeline artifacts (srs.md, prd.md, arch.md, etc.)",
            ))
    if include_global:
        home_forge = Path.home() / ".forge"
        if home_forge.exists() and home_forge.is_dir():
            size, cnt = directory_stats(home_forge)
            targets.append(Target(
                path=str(home_forge), kind="dir",
                size_bytes=size, file_count=cnt,
                label="GLOBAL state — lessons promoted from ALL your Forge projects",
            ))
    return targets


def print_plan(targets: list[Target], keep_artifacts: bool) -> None:
    print("Forge uninstall — plan")
    print("=" * 22)
    print()
    if not targets:
        print("Nothing to remove. Forge state not detected in this project.")
        return
    print("Will remove:")
    for t in targets:
        print(f"  • {t.path}")
        print(f"      {t.label}")
        print(f"      {t.file_count} files, {format_size(t.size_bytes)}")
    if keep_artifacts and (Path.cwd() / "pipeline").exists():
        print()
        print("Will keep:")
        print("  • pipeline/  (omit --keep-artifacts to remove it too)")
    print()


def confirm(prompt: str) -> bool:
    try:
        ans = input(prompt + " [y/N] ").strip().lower()
    except EOFError:
        return False
    return ans in ("y", "yes")


def remove_targets(
    targets: list[Target],
    dry_run: bool,
) -> list[Removal]:
    out: list[Removal] = []
    for t in targets:
        path = Path(t.path)
        if dry_run:
            out.append(Removal(path=t.path, status="skipped", detail="dry-run"))
            continue
        if not path.exists():
            # Already gone (e.g., concurrent run); idempotent
            out.append(Removal(path=t.path, status="skipped", detail="not present"))
            continue
        try:
            shutil.rmtree(path)
            out.append(Removal(path=t.path, status="removed"))
        except OSError as e:
            out.append(Removal(path=t.path, status="error", detail=str(e)))
    return out


def print_results(removals: list[Removal], cwd: Path) -> None:
    print()
    for r in removals:
        icon = {"removed": "✓", "skipped": "·", "error": "✗"}.get(r.status, "?")
        suffix = f": {r.detail}" if r.detail else ""
        print(f"  {icon} {r.path}  ({r.status}{suffix})")
    errors = sum(1 for r in removals if r.status == "error")
    print()
    if errors:
        print(f"Completed with {errors} error{'s' if errors != 1 else ''}.")
    else:
        print(f"Forge state removed from {cwd}.")
    print()
    print("Next steps:")
    print(f"  • To unregister the plugin from Claude Code:  {PLUGIN_UNREGISTER_HINT}")
    print(f"  • To reinstall later:                          {REINSTALL_HINT}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Remove Forge state from a project (filesystem cleanup only).",
    )
    parser.add_argument("--cwd", default=os.getcwd(),
                        help="Project directory (default: cwd)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show plan without removing anything")
    parser.add_argument("--keep-artifacts", action="store_true",
                        help="Keep pipeline/ (preserve SDLC artifacts)")
    parser.add_argument("--include-global", action="store_true",
                        help="Offer to remove ~/.forge/ (shared across all projects)")
    parser.add_argument("--yes", action="store_true",
                        help="Skip confirmation prompts (CI/scripting only)")
    parser.add_argument("--json", action="store_true",
                        help="Emit machine-readable JSON result")
    args = parser.parse_args(argv)

    cwd = Path(args.cwd).resolve()
    targets = discover_targets(
        cwd=cwd,
        keep_artifacts=args.keep_artifacts,
        include_global=args.include_global,
    )

    if not args.json:
        print_plan(targets, args.keep_artifacts)

    if not targets:
        if args.json:
            print(json.dumps({"targets": [], "removals": [], "cancelled": False}))
        return 0

    if args.dry_run:
        if args.json:
            print(json.dumps({
                "targets": [asdict(t) for t in targets],
                "removals": [],
                "dry_run": True,
            }))
        else:
            print(f"Dry run — nothing removed.")
            print(f"To proceed: {sys.argv[0]} --cwd {cwd}"
                  + (" --keep-artifacts" if args.keep_artifacts else "")
                  + (" --include-global" if args.include_global else ""))
        return 0

    # Confirmation
    if not args.yes:
        global_path = str(Path.home() / ".forge")
        has_global = any(t.path == global_path for t in targets)

        if not confirm("Proceed with removal?"):
            if not args.json:
                print("Cancelled.")
            else:
                print(json.dumps({"targets": [asdict(t) for t in targets],
                                  "removals": [], "cancelled": True}))
            return 0

        # Separate confirmation for global state — it affects other projects
        if has_global:
            warning = (
                "~/.forge/ contains lessons promoted from ALL your Forge projects "
                "(not just this one). Remove it anyway?"
            )
            if not confirm(warning):
                targets = [t for t in targets if t.path != global_path]
                if not args.json:
                    print("Keeping ~/.forge/ (other targets will still be removed).")

    removals = remove_targets(targets, dry_run=False)

    if args.json:
        print(json.dumps({
            "targets": [asdict(t) for t in targets],
            "removals": [asdict(r) for r in removals],
            "cancelled": False,
            "plugin_unregister_hint": PLUGIN_UNREGISTER_HINT,
            "reinstall_hint": REINSTALL_HINT,
        }))
    else:
        print_results(removals, cwd)

    return 0 if all(r.status != "error" for r in removals) else 1


if __name__ == "__main__":
    sys.exit(main())