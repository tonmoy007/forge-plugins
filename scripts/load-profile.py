#!/usr/bin/env python3
"""Load project-type profile overrides from references/project-type-profiles.md.

Reads `pipeline/state.md` for `project_type`, parses the profile's YAML block in
`references/project-type-profiles.md`, and emits the relevant section to stdout
(either a formatted markdown context block for the stage agent, or JSON for tooling).

Usage:
  python3 load-profile.py --cwd PATH [--stage N] [--profiles-file PATH] [--format markdown|json]

Exit codes:
  0 — always; missing state / unknown type / no overrides → empty body, still exit 0
  1 — only on argument or filesystem errors

Note: this script is read-only and side-effect free. It is safe to call from any
stage-skill pre-flight without modifying anything.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

import yaml

_PLUGIN_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_PROFILES_REL = "references/project-type-profiles.md"


def _read_project_type(cwd: Path) -> Optional[str]:
    """Return project_type from pipeline/state.md, or None if missing/unreadable."""
    state_path = cwd / "pipeline" / "state.md"
    if not state_path.exists():
        return None
    try:
        import frontmatter  # type: ignore
        post = frontmatter.load(state_path)
        ptype = post.metadata.get("project_type")
        if isinstance(ptype, str) and ptype.strip():
            return ptype.strip()
    except Exception:
        return None
    return None


def _extract_profile(profiles_text: str, profile_name: str) -> Optional[dict]:
    """Find the `## Profile: <name>` block and parse the first YAML fence under it."""
    # Match `## Profile: <name>` (allow trailing whitespace), then capture the next
    # ```yaml ... ``` block before the next `## Profile:` or `---` divider.
    pattern = re.compile(
        rf"^##\s+Profile:\s+{re.escape(profile_name)}\s*\n.*?```yaml\n(.*?)\n```",
        re.DOTALL | re.MULTILINE,
    )
    m = pattern.search(profiles_text)
    if not m:
        return None
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _stage_block(profile: dict, stage: int) -> Optional[dict]:
    """Return the `stage_overrides.stage_N` dict, or None if absent."""
    overrides = profile.get("stage_overrides") or {}
    return overrides.get(f"stage_{stage}")


def _format_markdown(
    profile_name: str,
    profile: dict,
    stage: Optional[int],
) -> str:
    """Render a compact markdown context block for the agent."""
    lines: list[str] = []
    lines.append(f"## Project profile: {profile_name}")
    desc = profile.get("description")
    if desc:
        lines.append(f"_{desc}_")
    emphasis = profile.get("stage_emphasis") or {}
    if emphasis:
        lines.append("")
        lines.append("**Stage emphasis**")
        for level in ("high", "low"):
            stages = emphasis.get(level)
            if stages:
                lines.append(f"- {level}: {', '.join(stages)}")
    if stage is not None:
        block = _stage_block(profile, stage)
        if block:
            lines.append("")
            lines.append(f"**Overrides for stage {stage}**")
            for key, val in block.items():
                if isinstance(val, list):
                    lines.append(f"- **{key}**:")
                    for item in val:
                        if isinstance(item, dict):
                            # Criterion-like entries: render id + description + severity
                            cid = item.get("id", "")
                            cdesc = item.get("description", "")
                            sev = item.get("severity", "")
                            sev_tag = f" *(severity: {sev})*" if sev else ""
                            label = f"{cid}: {cdesc}".strip(": ").strip()
                            lines.append(f"    - {label}{sev_tag}")
                        else:
                            lines.append(f"    - {item}")
                elif isinstance(val, bool):
                    lines.append(f"- **{key}**: {str(val).lower()}")
                else:
                    lines.append(f"- **{key}**: {val}")
        else:
            lines.append("")
            lines.append(f"_(no overrides for stage {stage} in this profile)_")
    return "\n".join(lines) + "\n"


def load_profile(
    cwd: Path,
    stage: Optional[int] = None,
    profiles_file: Optional[Path] = None,
) -> tuple[Optional[str], Optional[dict]]:
    """Return (profile_name, profile_dict) or (project_type, None) when no match.

    Returns (None, None) if state.md is missing or has no project_type.
    """
    ptype = _read_project_type(cwd)
    if ptype is None:
        return None, None
    profiles_path = profiles_file or (_PLUGIN_DIR / _DEFAULT_PROFILES_REL)
    if not profiles_path.exists():
        return ptype, None
    profile = _extract_profile(profiles_path.read_text(), ptype)
    return ptype, profile


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", required=True, type=Path, help="Project directory containing pipeline/state.md")
    parser.add_argument("--stage", type=int, default=None, help="Pipeline stage number (1–12)")
    parser.add_argument(
        "--profiles-file",
        type=Path,
        default=None,
        help="Override path to project-type-profiles.md (default: plugin-relative)",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format (default: markdown)",
    )
    args = parser.parse_args(argv)

    ptype, profile = load_profile(args.cwd, args.stage, args.profiles_file)

    if args.format == "json":
        out = {
            "project_type": ptype,
            "stage": args.stage,
            "profile": profile,
            "stage_overrides": _stage_block(profile, args.stage) if (profile and args.stage is not None) else None,
        }
        sys.stdout.write(json.dumps(out, indent=2))
        sys.stdout.write("\n")
        return 0

    # markdown
    if ptype is None:
        # No state.md or no project_type — silent
        return 0
    if profile is None:
        sys.stdout.write(f"## Project profile: {ptype}\n_(profile not found in registry; using base stage definition only)_\n")
        return 0
    sys.stdout.write(_format_markdown(ptype, profile, args.stage))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
