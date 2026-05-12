#!/usr/bin/env python3
"""SessionStart hook — inject pipeline state and lessons into Claude context.

Reads JSON from stdin, prints a context block (≤ 2000 tokens) to stdout.
Exits 0 silently if cwd is not a Forge project.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

import subprocess

import yaml

# Resolve plugin root and make _state_lib importable by hooks
_PLUGIN_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(_PLUGIN_DIR / "scripts"))
import _state_lib as lib

_LOG = logging.getLogger(__name__)

STAGE_NAMES: dict[int, str] = {
    0: "not started",
    1: "srs",
    2: "product",
    3: "architecture",
    4: "spec",
    5: "plan",
    6: "build",
    7: "eval",
    8: "deploy",
    9: "monitor",
    10: "feedback",
    11: "resolve",
    12: "release",
}

_MAX_TOKENS = 2000
_CHARS_PER_TOKEN = 4  # rough approximation; avoids tiktoken dependency


def _token_estimate(text: str) -> int:
    return len(text) // _CHARS_PER_TOKEN


def _sync_lessons_if_stale(cwd: Path) -> None:
    """Regenerate .forge/lessons.yaml if tasks/lessons.md is newer."""
    lessons_md = cwd / "tasks" / "lessons.md"
    lessons_yaml = cwd / ".forge" / "lessons.yaml"
    if not lessons_md.exists():
        return
    if lessons_yaml.exists() and lessons_md.stat().st_mtime <= lessons_yaml.stat().st_mtime:
        return
    sync_script = _PLUGIN_DIR / "scripts" / "sync-lessons.py"
    if not sync_script.exists():
        return
    try:
        subprocess.run(
            [sys.executable, str(sync_script), "--cwd", str(cwd)],
            timeout=10,
            check=False,
            capture_output=True,
        )
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("sync-lessons failed: %s", exc)


def _register_and_promote(cwd: Path) -> None:
    """Register current project in ~/.forge and run cross-project promotion."""
    promote_script = _PLUGIN_DIR / "scripts" / "promote-lessons.py"
    if not promote_script.exists():
        return
    try:
        subprocess.run(
            [sys.executable, str(promote_script), "--register", str(cwd), "--promote"],
            timeout=15,
            check=False,
            capture_output=True,
        )
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("promote-lessons failed: %s", exc)


def _load_lessons(path: Path, stage: int, project_type: str) -> list[dict]:
    """Load and filter lessons from a YAML file. Returns [] on any failure."""
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text()) or {}
        lessons: list[dict] = data.get("lessons", []) or []

        def _matches(lesson: dict) -> bool:
            stages = lesson.get("stage", []) or []
            types = lesson.get("project_types", []) or []
            return (not stages or stage in stages) and (
                not types or project_type in types
            )

        filtered = [l for l in lessons if _matches(l)]
        filtered.sort(key=lambda l: l.get("frequency", 0), reverse=True)
        return filtered
    except Exception:  # noqa: BLE001
        return []


def _gate_summary(plugin_dir: Path, stage: int) -> str:
    """Return a one-line summary of blocker criteria for the stage."""
    if stage == 0:
        return "run /forge:srs to begin Stage 1"
    gate_file = plugin_dir / "references" / "gate-criteria.md"
    if not gate_file.exists():
        return ""
    blocks = re.findall(r"```yaml\n(.*?)```", gate_file.read_text(), re.DOTALL)
    for block in blocks:
        try:
            data = yaml.safe_load(block)
            if isinstance(data, dict) and data.get("stage") == stage:
                blockers = [
                    c["description"]
                    for c in data.get("criteria", [])
                    if c.get("severity") == "blocker"
                ]
                if not blockers:
                    return "no blockers"
                summary = "; ".join(blockers[:3])
                if len(blockers) > 3:
                    summary += f" (+{len(blockers) - 3} more)"
                return summary
        except yaml.YAMLError:
            continue
    return ""


def _design_summary(design_path: Path) -> str:
    """Extract brief stats from design-system.md."""
    try:
        text = design_path.read_text()
        tokens = sum(text.count(p) for p in ("--color-", "--font-", "--space-"))
        components = text.lower().count("## component")
        return f"{tokens} design token(s), {components} component spec(s)"
    except Exception:  # noqa: BLE001
        return ""


def _compose(
    state: dict,
    lessons: list[dict],
    design: str,
    gate: str,
) -> str:
    stage = state.get("current_stage", 0)
    stage_name = STAGE_NAMES.get(stage, "unknown")
    task = state.get("current_task") or "(none)"
    milestone = state.get("current_milestone") or "(none)"
    total = state.get("total_tasks") or "?"
    ptype = state.get("project_type", "unknown")
    blockers: list = state.get("blockers") or []

    lines = [
        f"[Forge] Pipeline: Stage {stage} — {stage_name} | Task: {task} | Milestone: {milestone}/{total}",
        f"[Forge] Project type: {ptype}",
    ]

    if blockers:
        lines.append(f"[Forge] Blockers: {'; '.join(str(b) for b in blockers[:3])}")

    if lessons:
        abbrev = "; ".join(
            (l.get("trigger") or l.get("rule") or "")[:60] for l in lessons
        )
        lines.append(f"[Forge] Active lessons ({len(lessons)}): {abbrev}")
    else:
        lines.append("[Forge] Active lessons (0): (none)")

    if design:
        lines.append(f"[Forge] Design system: {design}")

    if gate:
        lines.append(f"[Forge] Next gate criteria: {gate}")

    return "\n".join(lines)


def run(cwd: Path) -> Optional[str]:
    """Return context string, or None to exit silently."""
    state_path = cwd / "pipeline" / "state.md"
    if not state_path.exists():
        return None  # not a Forge project

    try:
        state = lib.read_state(str(cwd))
    except SystemExit:
        return "[Forge] Warning: pipeline/state.md is unreadable — run /forge:init."
    except Exception as exc:
        _LOG.warning("session-start: state read failed: %s", exc)
        return None

    stage = state.get("current_stage", 0)
    project_type = state.get("project_type", "unknown")

    _sync_lessons_if_stale(cwd)
    _register_and_promote(cwd)

    # Lessons: up to 5 project-level + 3 global
    project_lessons = _load_lessons(
        cwd / ".forge" / "lessons.yaml", stage, project_type
    )[:5]
    global_lessons = _load_lessons(
        Path.home() / ".forge" / "global-lessons.yaml", stage, project_type
    )[:3]
    lessons = project_lessons + global_lessons

    # Design summary — only relevant at stage 6+
    design = ""
    if stage >= 6:
        ds_path = cwd / "pipeline" / "02-product-ux" / "design-system.md"
        if ds_path.exists():
            design = _design_summary(ds_path)

    gate = _gate_summary(_PLUGIN_DIR, stage)
    context = _compose(state, lessons, design, gate)

    # Enforce token budget by trimming lessons
    if _token_estimate(context) > _MAX_TOKENS:
        lessons = lessons[:2]
        context = _compose(state, lessons, design, gate)

    return context


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}

    cwd = Path(payload.get("cwd", os.getcwd()))
    result = run(cwd)
    if result is not None:
        print(result)
    sys.exit(0)


if __name__ == "__main__":
    main()
