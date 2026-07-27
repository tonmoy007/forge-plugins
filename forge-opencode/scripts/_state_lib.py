#!/usr/bin/env python3
"""Reusable state library for pipeline/state.md. Imported directly by hooks.

Uses stdlib + PyYAML for frontmatter parsing — no python-frontmatter dependency.
Rationale: Claude Code plugin installs do not pip-install Python deps, and the bare
PyPI name `frontmatter` resolves to an unrelated package (v0.1.3 user reports). See
the v0.1.3.1 lesson in tasks/lessons.md.
"""

from __future__ import annotations

import datetime
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

import yaml


_FENCE = "---"


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Parse a frontmatter-style markdown document into (metadata, body).

    Returns ({}, text) if no opening `---` fence is found on the first line.
    Body is returned with a single leading newline stripped (matching the
    python-frontmatter behavior we previously relied on).
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != _FENCE:
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == _FENCE:
            yaml_block = "".join(lines[1:i])
            body = "".join(lines[i + 1 :])
            if body.startswith("\n"):
                body = body[1:]
            data = yaml.safe_load(yaml_block) or {}
            if not isinstance(data, dict):
                data = {}
            return data, body
    return {}, text


def _join_frontmatter(metadata: dict, body: str) -> str:
    """Serialize (metadata, body) into a frontmatter markdown document.

    Output format: `---\\n<yaml>---\\n\\n<body>` — matches the previous
    python-frontmatter dumps output so on-disk state.md byte layout is preserved.
    """
    yaml_block = yaml.safe_dump(
        metadata,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )
    return f"{_FENCE}\n{yaml_block}{_FENCE}\n\n{body}"


def _normalize_metadata(metadata: dict) -> dict:
    """Convert PyYAML-parsed datetime/date objects to ISO strings.

    PyYAML automatically parses bare ISO timestamps (e.g. 2026-05-07T12:00:00Z)
    as datetime objects. This ensures callers always see strings for last_updated.
    """
    result = {}
    for k, v in metadata.items():
        if isinstance(v, datetime.datetime):
            result[k] = v.strftime("%Y-%m-%dT%H:%M:%SZ")
        elif isinstance(v, datetime.date):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result


STATE_RELPATH = "pipeline/state.md"


def _stage_bounds() -> tuple[int, int]:
    """Return (min_stage, max_stage) from the canonical stage table (T-101).

    Falls back to the documented (0, 12) invariant if the table cannot be read,
    so this hot-path library never crashes a hook on a packaging glitch.
    """
    try:
        import _stage_table

        b = _stage_table.bounds()
        return int(b.get("min_stage", 0)), int(b.get("max_stage", 12))
    except Exception:
        return 0, 12

# Field name → expected Python type(s). Order matches state.md schema.
REQUIRED_FIELDS: dict[str, type | tuple[type, ...]] = {
    "schema_version": int,
    "project_type": str,
    "cycle": int,
    "current_stage": int,
    "current_task": (str, type(None)),
    "current_milestone": (str, type(None)),
    "total_tasks": (int, type(None)),
    "last_updated": str,
    "blockers": list,
}


def validate_frontmatter(data: dict) -> tuple[bool, list[str]]:
    """Return (is_valid, error_messages). Checks required fields and types."""
    errors: list[str] = []
    for field, expected in REQUIRED_FIELDS.items():
        if field not in data:
            errors.append(f"missing required field: '{field}'")
            continue
        val = data[field]
        types = expected if isinstance(expected, tuple) else (expected,)
        if not isinstance(val, types):
            type_names = " | ".join(t.__name__ for t in types)
            errors.append(f"'{field}' must be {type_names}, got {type(val).__name__}")
    # REQ-PIPEBOUNDS-001: current_stage must stay within the canonical bounds.
    # (Type already checked above; only range-check a well-typed int.)
    stage_val = data.get("current_stage")
    if isinstance(stage_val, int):
        lo, hi = _stage_bounds()
        if not lo <= stage_val <= hi:
            errors.append(f"'current_stage' must be in [{lo}, {hi}], got {stage_val}")
    return len(errors) == 0, errors


def _state_path(cwd: str) -> Path:
    return Path(cwd) / STATE_RELPATH


def _ensure_state_exists(cwd: str) -> Path:
    p = _state_path(cwd)
    if not p.exists():
        print(
            f"error: {STATE_RELPATH} not found in {cwd!r} — run /forge:init first",
            file=sys.stderr,
        )
        sys.exit(1)
    return p


def _atomic_write(path: Path, content: str) -> None:
    """Write content to path atomically via tempfile + fsync + rename."""
    dir_ = path.parent
    fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        if path.exists():
            os.chmod(tmp, path.stat().st_mode)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_state(cwd: str) -> dict:
    """Load and return the frontmatter dict from pipeline/state.md."""
    p = _ensure_state_exists(cwd)
    metadata, _ = _split_frontmatter(p.read_text())
    return _normalize_metadata(metadata)


def write_state(cwd: str, frontmatter_dict: dict) -> None:
    """Validate and atomically write updated frontmatter, preserving markdown body."""
    p = _ensure_state_exists(cwd)
    normalized = _normalize_metadata(frontmatter_dict)
    valid, errors = validate_frontmatter(normalized)
    if not valid:
        print(f"error: invalid frontmatter — {'; '.join(errors)}", file=sys.stderr)
        sys.exit(1)
    current, body = _split_frontmatter(p.read_text())
    current.update(normalized)
    _atomic_write(p, _join_frontmatter(current, body))


def check_prerequisite(cwd: str, stage: int) -> tuple[bool, str]:
    """REQ-GATE-ENTRY-001: is stage `stage`'s prior-stage artifact present?

    Returns (ok, message). ok=True (empty message) when the stage has no
    prerequisite (stage 1) or the prerequisite file exists under `cwd`. ok=False
    with a one-line message naming the missing file and the skill to run instead.
    """
    try:
        import _stage_table

        prereq = _stage_table.prerequisite(stage)
        prereq_skill = _stage_table.prerequisite_skill(stage)
    except Exception:
        # Without the table we cannot assert a prerequisite; don't block.
        return True, ""
    if not prereq:
        return True, ""
    if (Path(cwd) / prereq).exists():
        return True, ""
    skill_hint = f" — run {prereq_skill} first" if prereq_skill else ""
    return False, f"Stage {stage} requires {prereq}, which is missing{skill_hint}."


def advance_stage(cwd: str, to: Optional[int] = None, force: bool = False) -> dict:
    """Increment current_stage (or jump to `to`), update last_updated, return new state.

    REQ-GATE-ENTRY-001: a jump of more than one stage (`to > old + 1`) is rejected
    unless `force=True`. `/forge:force-advance` is the documented forced path.
    """
    p = _ensure_state_exists(cwd)
    metadata, body = _split_frontmatter(p.read_text())

    lo, hi = _stage_bounds()
    old = metadata.get("current_stage", 0)

    if to is not None:
        # REQ-PIPEBOUNDS-001: out-of-range jumps are rejected, not warned-and-written.
        if not lo <= to <= hi:
            print(
                f"error: cannot advance to stage {to} — outside valid range [{lo}, {hi}]",
                file=sys.stderr,
            )
            sys.exit(1)
        if to < old:
            print(f"warning: moving backward from stage {old} to {to}", file=sys.stderr)
        elif to > old + 1 and not force:
            # REQ-GATE-ENTRY-001: skipping stages requires an explicit force path.
            print(
                f"error: cannot skip stages {old + 1}–{to - 1} (stage {old} → {to}). "
                f"Complete them in order, or use /forge:force-advance to skip intentionally.",
                file=sys.stderr,
            )
            sys.exit(1)
        elif to > old + 1:
            print(f"warning: skipping stages {old + 1}–{to - 1}", file=sys.stderr)
        new = to
    else:
        new = old + 1
        # REQ-PIPEBOUNDS-001 cycle-wrap: advancing past the last stage wraps to
        # (cycle + 1, min_stage) per the stage table's on_overflow: cycle-wrap.
        if new > hi:
            new = lo
            metadata["cycle"] = int(metadata.get("cycle", 1)) + 1
            print(
                f"cycle complete — wrapping to cycle {metadata['cycle']}, stage {lo}",
                file=sys.stderr,
            )

    metadata["current_stage"] = new
    metadata["last_updated"] = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    _atomic_write(p, _join_frontmatter(metadata, body))
    return _normalize_metadata(metadata)


def append_to_section(cwd: str, section_title: str, content: str) -> None:
    """Append content at the end of a ## section in the markdown body."""
    p = _ensure_state_exists(cwd)
    metadata, body = _split_frontmatter(p.read_text())
    header = f"## {section_title}"
    lines = body.split("\n")

    header_idx = next((i for i, ln in enumerate(lines) if ln.strip() == header), None)
    if header_idx is None:
        body = body.rstrip("\n") + f"\n\n{header}\n{content}\n"
    else:
        end_idx = len(lines)
        for i in range(header_idx + 1, len(lines)):
            if lines[i].startswith("## "):
                end_idx = i
                break
        lines.insert(end_idx, content)
        body = "\n".join(lines)

    _atomic_write(p, _join_frontmatter(metadata, body))
