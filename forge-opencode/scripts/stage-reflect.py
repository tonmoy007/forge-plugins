#!/usr/bin/env python3
"""Per-stage reflection rollup (REQ-STAGEREFLECT-001 / T-119).

When a stage's gate passes and the pipeline advances out of it, summarize what
happened across that stage's sessions into `pipeline/0X-stage/reflection.md`. The
rollup references the contributing session_ids and the gate outcome, and folds in
any per-session reflections written by stop-reflect. It complements — does not
replace — the per-session reflections.

Usage (cwd = project root):
    stage-reflect.py --stage N [--cwd PATH] [--gate-status pass|fail|wedged]

The session index comes from `.forge/session.jsonl` (rows with stage == N).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage_table  # noqa: E402


def _sessions_for_stage(forge_dir: Path, stage: int) -> list[dict]:
    log = forge_dir / "session.jsonl"
    if not log.exists():
        return []
    rows: list[dict] = []
    for line in log.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("stage") == stage:
            rows.append(row)
    return rows


def _session_reflections(forge_dir: Path) -> list[str]:
    """Reflection snippets from .forge/sessions/*.md (best-effort)."""
    sessions_dir = forge_dir / "sessions"
    if not sessions_dir.is_dir():
        return []
    out: list[str] = []
    for md in sorted(sessions_dir.glob("*.md")):
        try:
            out.append(md.read_text())
        except OSError:
            continue
    return out


def build_reflection(stage: int, sessions: list[dict], gate_status: str,
                     reflections: list[str]) -> str:
    entry = _stage_table.stage(stage) or {}
    label = entry.get("label", f"Stage {stage}")
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    session_ids = [s.get("session_id", "?") for s in sessions]
    lessons_total = sum(int(s.get("lessons_added", 0) or 0) for s in sessions)
    commands = sorted({c for s in sessions for c in s.get("commands", []) or []})

    lines = [
        f"# Stage {stage} Reflection — {label}",
        "",
        f"- **Generated**: {now}",
        f"- **Gate outcome**: {gate_status}",
        f"- **Contributing sessions ({len(session_ids)})**: "
        + (", ".join(session_ids) if session_ids else "_(none recorded)_"),
        f"- **Lessons captured this stage**: {lessons_total}",
        f"- **Commands used**: {', '.join(commands) if commands else '_(none)_'}",
        "",
        "## What happened",
        "",
        "_Summarize the key decisions and surprises across the sessions above._",
        "",
    ]
    if reflections:
        lines.append("## Session reflections")
        lines.append("")
        for r in reflections:
            for ln in r.splitlines():
                if ln.strip():
                    lines.append(f"> {ln}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="stage-reflect.py")
    parser.add_argument("--stage", required=True, type=int, metavar="N")
    parser.add_argument("--cwd", default=".", metavar="PATH")
    parser.add_argument("--gate-status", default="pass", metavar="STATUS")
    args = parser.parse_args(argv)

    cwd = Path(args.cwd)
    canonical = _stage_table.canonical_dir(args.stage)
    if not canonical:
        print(f"no canonical directory for stage {args.stage}", file=sys.stderr)
        return 1

    forge_dir = cwd / ".forge"
    sessions = _sessions_for_stage(forge_dir, args.stage)
    reflections = _session_reflections(forge_dir)

    content = build_reflection(args.stage, sessions, args.gate_status, reflections)
    out_dir = cwd / "pipeline" / canonical
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "reflection.md").write_text(content)
    print(f"wrote pipeline/{canonical}/reflection.md", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
