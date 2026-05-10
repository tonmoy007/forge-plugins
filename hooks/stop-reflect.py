#!/usr/bin/env python3
"""Stop hook: reflect, extract lessons, check gate, mine skills.

Four-step sequential pipeline per ADR-004:
  1. Reflection (always) — lightweight summary written to state.md
  2. Lesson extraction (when corrections flagged) — calls extract-lessons.py
  3. Gate check (always) — calls check-gate.py; exit 2 on unmet blockers + done signal
  4. Skill mining (async, fire-and-forget) — Popen mine-skills.py if present

Errors are logged to .forge/errors.log and never crash the session.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

_PLUGIN_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(_PLUGIN_DIR / "scripts"))
import _state_lib as lib

logger = logging.getLogger(__name__)

_DONE_PATTERNS = [
    "ship it",
    "we're done",
    "we are done",
    "stage is done",
    "move to next stage",
    "advance to",
    "next stage",
    "mark this done",
    "/forge:advance",
    "mark stage",
    "move on to stage",
]


def _log_error(forge_dir: Path, kind: str, detail: str) -> None:
    """Append one JSON line to .forge/errors.log — never raises."""
    try:
        forge_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        line = json.dumps({"ts": ts, "kind": kind, "detail": str(detail)}) + "\n"
        with (forge_dir / "errors.log").open("a") as f:
            f.write(line)
    except Exception:  # noqa: BLE001
        pass


def _read_transcript_tail(transcript_path: str, last_n: int = 10) -> list[dict]:
    """Read last N messages from a JSONL transcript. Returns [] on any failure."""
    if not transcript_path:
        return []
    p = Path(transcript_path)
    if not p.exists():
        return []
    try:
        lines = [ln for ln in p.read_text(errors="replace").splitlines() if ln.strip()]
        messages: list[dict] = []
        for line in lines:
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return messages[-last_n:]
    except Exception:  # noqa: BLE001
        return []


def _extract_text(content: object) -> str:
    """Flatten message content (str or list of content blocks) to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return " ".join(parts)
    return ""


def _detect_done_signal(transcript_path: str) -> bool:
    """Return True only if the user explicitly signaled stage completion.

    Conservative — false positives block the user; false negatives just require
    them to be more explicit.
    """
    messages = _read_transcript_tail(transcript_path, last_n=5)
    for msg in reversed(messages):
        if msg.get("role") != "user":
            continue
        text = _extract_text(msg.get("content", "")).lower()
        if any(pat in text for pat in _DONE_PATTERNS):
            return True
    return False


def _compose_reflection(state: dict, messages: list[dict]) -> str:
    """Lightweight reflection without LLM (v0.1). T-016 adds LLM-backed reflector."""
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stage = state.get("current_stage", "?")
    task = state.get("current_task") or "none"
    user_turns = sum(1 for m in messages if m.get("role") == "user")

    lines = [
        f"**Timestamp**: {ts}",
        f"**Stage**: {stage} | **Task**: {task}",
        f"**Turns this session segment**: {user_turns} user message(s)",
    ]

    files_touched: list[str] = []
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            inp = block.get("input", {})
            for field in ("file_path", "path"):
                if field in inp:
                    files_touched.append(inp[field])

    if files_touched:
        unique = list(dict.fromkeys(files_touched))[:5]
        lines.append(f"**Files touched**: {', '.join(unique)}")

    return "\n".join(lines)


def _run_extract_lessons(
    forge_dir: Path, transcript_path: str, plugin_dir: Path
) -> int:
    """Call extract-lessons.py if it exists. Returns count of lessons captured."""
    script = plugin_dir / "scripts" / "extract-lessons.py"
    if not script.exists():
        return 0
    flags_path = forge_dir / "correction-flags.jsonl"
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--transcript",
                transcript_path,
                "--since-flag",
                str(flags_path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.count("- id:")
    except subprocess.TimeoutExpired:
        _log_error(forge_dir, "extract_lessons_timeout", "")
    except Exception as e:  # noqa: BLE001
        _log_error(forge_dir, "extract_lessons_failed", str(e))
    return 0


def _run_gate_check(cwd: Path, stage: int, plugin_dir: Path) -> dict:
    """Call check-gate.py and return parsed result dict. Returns {} on failure."""
    script = plugin_dir / "scripts" / "check-gate.py"
    if not script.exists():
        return {}
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--stage",
                str(stage),
                "--cwd",
                str(cwd),
                "--plugin-dir",
                str(plugin_dir),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    except Exception:  # noqa: BLE001
        pass
    return {}


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}

    # Loop prevention — Claude can Stop during hook execution
    if payload.get("stop_hook_active"):
        sys.exit(0)

    cwd = Path(payload.get("cwd", os.getcwd()))
    session_id: str = payload.get("session_id", "")
    transcript_path: str = payload.get("transcript_path", "")

    if not (cwd / "pipeline" / "state.md").exists():
        sys.exit(0)

    forge_dir = cwd / ".forge"

    try:
        state = lib.read_state(str(cwd))
    except Exception as e:  # noqa: BLE001
        _log_error(forge_dir, "state_read_failed", str(e))
        sys.exit(0)

    current_stage: int = state.get("current_stage", 0)
    messages = _read_transcript_tail(transcript_path, last_n=10)

    # Step 1: Reflection
    try:
        reflection = _compose_reflection(state, messages)
        lib.append_to_section(str(cwd), "Last Reflection", reflection)
    except Exception as e:  # noqa: BLE001
        _log_error(forge_dir, "reflection_failed", str(e))

    # Step 2: Lesson extraction
    correction_flags = forge_dir / "correction-flags.jsonl"
    if correction_flags.exists() and correction_flags.stat().st_size > 0:
        count = _run_extract_lessons(forge_dir, transcript_path, _PLUGIN_DIR)
        if count > 0:
            print(f"📚 Captured {count} lesson(s) from corrections.")
            try:
                correction_flags.write_text("")
            except Exception:  # noqa: BLE001
                pass

    # Step 3: Gate check
    gate_result = _run_gate_check(cwd, current_stage, _PLUGIN_DIR)
    if gate_result:
        passed = gate_result.get("passed", 0)
        total = gate_result.get("total", 0)
        details = gate_result.get("details", [])
        unmet_blockers = [
            d for d in details
            if not d.get("passed") and d.get("severity") == "blocker"
        ]
        user_done = _detect_done_signal(transcript_path)

        if user_done:
            if not unmet_blockers:
                try:
                    lib.advance_stage(str(cwd))
                    print(
                        f"✅ Stage {current_stage} gate passed."
                        f" Advanced to stage {current_stage + 1}."
                    )
                except Exception as e:  # noqa: BLE001
                    _log_error(forge_dir, "advance_stage_failed", str(e))
            else:
                print(
                    f"🚫 Cannot advance from Stage {current_stage}."
                    " Unmet blockers:"
                )
                for b in unmet_blockers:
                    print(f"  - {b.get('check', '?')}: {b.get('description', '')}")
                sys.exit(2)
        else:
            if total > 0:
                print(
                    f"⚠️ Stage {current_stage}:"
                    f" {passed}/{total} gate criteria met."
                )

    # Step 4: Skill mining (async, fire-and-forget)
    mine_script = _PLUGIN_DIR / "scripts" / "mine-skills.py"
    if mine_script.exists():
        try:
            subprocess.Popen(
                [sys.executable, str(mine_script), "--session", session_id],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception as e:  # noqa: BLE001
            _log_error(forge_dir, "skill_mining_spawn_failed", str(e))

    sys.exit(0)


if __name__ == "__main__":
    main()
