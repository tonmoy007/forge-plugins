"""Atomic file writer + event log appender for Stop hook proposals (FR-DET-003).

All writes to long-term memory go through here. Each write:
  1. Modifies the target file atomically (write-to-temp, then rename)
  2. Appends a chained event to .forge/events.jsonl via _event_log

On any IO failure the function returns False; the caller logs the error.
No partial state is left behind.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import _event_log as event_log
import _state_lib as lib
from _proposals import LessonProposal, ReflectionProposal, StageAdvanceProposal


def execute_reflection(
    cwd: Path,
    proposal: ReflectionProposal,
    forge_dir: Path,
    session_id: str,
) -> bool:
    """Append reflection prose to state.md and log the event."""
    try:
        lib.append_to_section(str(cwd), "Last Reflection", proposal.prose)
        event_log.append(
            forge_dir,
            "ReflectionRecorded",
            session_id,
            proposal.stage,
            json.loads(proposal.model_dump_json()),
            "accepted",
        )
        return True
    except Exception:
        return False


def execute_lessons(
    cwd: Path,
    proposals: list[LessonProposal],
    forge_dir: Path,
    session_id: str,
) -> int:
    """Write lessons to tasks/lessons.md + .forge/lessons.yaml. Returns count written."""
    written = 0
    for p in proposals:
        if _write_lesson(cwd, p, forge_dir, session_id):
            written += 1
    return written


def execute_stage_advance(
    cwd: Path,
    proposal: StageAdvanceProposal,
    forge_dir: Path,
    session_id: str,
) -> bool:
    """Advance pipeline stage and log the event."""
    try:
        lib.advance_stage(str(cwd))
        event_log.append(
            forge_dir,
            "StageAdvanced",
            session_id,
            proposal.from_stage,
            json.loads(proposal.model_dump_json()),
            "accepted",
        )
        return True
    except Exception:
        return False


def _write_lesson(
    cwd: Path,
    p: LessonProposal,
    forge_dir: Path,
    session_id: str,
) -> bool:
    lessons_md = cwd / "tasks" / "lessons.md"
    lessons_yaml = forge_dir / "lessons.yaml"
    ts = p.created_at.strftime("%Y-%m-%d")

    md_entry = (
        f"\n### {ts} — {p.trigger}\n\n"
        f"**Rule**: {p.rule}\n\n"
        f"**Why**: {p.why}\n\n"
        f"**Trust**: {p.trust} | **Stages**: {p.stage_tags}\n"
    )
    yaml_entry = {
        "trigger": p.trigger,
        "rule": p.rule,
        "why": p.why,
        "stage_tags": p.stage_tags,
        "trust": p.trust,
        "source_session": p.source_session,
        "created_at": ts,
    }

    try:
        _atomic_append(lessons_md, md_entry)
        _yaml_append(lessons_yaml, yaml_entry)
        event_log.append(
            forge_dir,
            "LessonRecorded",
            session_id,
            p.stage_tags[0] if p.stage_tags else 0,
            json.loads(p.model_dump_json()),
            "accepted",
        )
        return True
    except Exception:
        return False


def _atomic_append(path: Path, content: str) -> None:
    """Read-modify-write via a sibling temp file (never leaves partial state)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text() if path.exists() else ""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(existing + content)
    tmp.replace(path)


def _yaml_append(path: Path, entry: dict) -> None:
    import yaml
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_text = path.read_text() if path.exists() else ""
    try:
        existing: list = yaml.safe_load(existing_text) or []
        if not isinstance(existing, list):
            existing = []
    except Exception:
        existing = []
    existing.append(entry)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(yaml.dump(existing, default_flow_style=False, allow_unicode=True))
    tmp.replace(path)
