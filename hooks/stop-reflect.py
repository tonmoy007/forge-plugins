#!/usr/bin/env python3
"""Stop hook: reflect, extract lessons, check gate, mine skills (v4.1-hardened).

Pipeline (T-009 v4.1 — Proposal → Validator → Executor):
  0. Pre-flight  — session-meta loop guard + daily cost guard
  1. Reflector   — builds ReflectionProposal (lightweight v0.1; T-016 adds LLM)
  2. Lesson Extractor — LessonProposals when corrections are flagged
  3. Gate Check  — GateProposal; exit 2 on unmet blockers + done signal
  4. Skill Miner — async fire-and-forget
  5+6. Validate → Execute (atomic writes + HMAC event log)

Errors are logged to .forge/errors.log and never crash the session.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

_PLUGIN_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(_PLUGIN_DIR / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))

import _state_lib as lib
import _event_log as event_log
import _executor as executor
import _session_meta as session_meta_mod
import _validator as validator
from _proposals import (
    GateProposal,
    LessonProposal,
    ReflectionProposal,
    StageAdvanceProposal,
)

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
    try:
        forge_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = json.dumps({"ts": ts, "kind": kind, "detail": str(detail)}) + "\n"
        with (forge_dir / "errors.log").open("a") as f:
            f.write(line)
    except Exception:
        pass


def _read_transcript_tail(transcript_path: str, last_n: int = 10) -> list[dict]:
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
    except Exception:
        return []


def _extract_text(content: object) -> str:
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
    """Return True only if the user explicitly signalled stage completion.

    Conservative — false positives block the user; false negatives just require
    the user to be more explicit.
    """
    messages = _read_transcript_tail(transcript_path, last_n=5)
    for msg in reversed(messages):
        if msg.get("role") != "user":
            continue
        text = _extract_text(msg.get("content", "")).lower()
        if any(pat in text for pat in _DONE_PATTERNS):
            return True
    return False


def _compose_reflection_prose(state: dict, messages: list[dict]) -> str:
    """Build lightweight reflection prose (v0.1). T-016 replaces with LLM reflector."""
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


_MAX_PROPOSALS_SHOWN = 3


def _print_pending_proposals(forge_dir: Path) -> None:
    """Surface mined skill proposals so the user can approve/modify/reject.

    Reads `.forge/proposed-skills/*/SKILL.md` directly (no subprocess) so the
    hook stays fast and dependency-free. Truncates to the first
    `_MAX_PROPOSALS_SHOWN` slugs to avoid swamping context.
    """
    proposed_root = forge_dir / "proposed-skills"
    if not proposed_root.exists():
        return
    slugs = sorted(p.parent.name for p in proposed_root.glob("*/SKILL.md"))
    if not slugs:
        return
    print(f"📜 {len(slugs)} skill proposal(s) pending review:")
    for slug in slugs[:_MAX_PROPOSALS_SHOWN]:
        print(f"  - {slug}")
    if len(slugs) > _MAX_PROPOSALS_SHOWN:
        print(f"  … and {len(slugs) - _MAX_PROPOSALS_SHOWN} more")
    print(
        "Review `.forge/proposed-skills/<slug>/SKILL.md`, then:"
        "\n  python3 scripts/skill-approval.py approve --slug <slug>"
        "\n  python3 scripts/skill-approval.py reject  --slug <slug>"
    )


def _run_gate_check(cwd: Path, stage: int, plugin_dir: Path) -> dict:
    script = plugin_dir / "scripts" / "check-gate.py"
    if not script.exists():
        return {}
    try:
        result = subprocess.run(
            [
                sys.executable, str(script),
                "--stage", str(stage),
                "--cwd", str(cwd),
                "--plugin-dir", str(plugin_dir),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    except Exception:
        pass
    return {}


def _parse_lesson_output(
    stdout: str, session_id: str, stage: int
) -> list[LessonProposal]:
    """Parse extract-lessons.py YAML stdout into LessonProposal objects.

    Expected: a YAML list of dicts with trigger / rule / why keys.
    """
    import yaml
    try:
        items = yaml.safe_load(stdout)
        if not isinstance(items, list):
            return []
    except Exception:
        return []

    proposals: list[LessonProposal] = []
    now = datetime.datetime.now(datetime.timezone.utc)
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            proposals.append(LessonProposal(
                trigger=str(item.get("trigger", ""))[:200],
                rule=str(item.get("rule", ""))[:500],
                why=str(item.get("why", ""))[:500],
                stage_tags=item.get("stage_tags", [stage]),
                trust="ephemeral",
                source_session=session_id,
                source_corrections=[],
                model="extract-lessons.py",
                prompt_hash="",
                temperature=0.0,
                created_at=now,
            ))
        except Exception:
            pass
    return proposals


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}

    # Claude can Stop during hook execution — prevent recursion
    if payload.get("stop_hook_active"):
        sys.exit(0)

    cwd = Path(payload.get("cwd", os.getcwd()))
    session_id: str = payload.get("session_id", "unknown")
    transcript_path: str = payload.get("transcript_path", "")

    if not (cwd / "pipeline" / "state.md").exists():
        sys.exit(0)

    forge_dir = cwd / ".forge"

    try:
        state = lib.read_state(str(cwd))
    except Exception as e:
        _log_error(forge_dir, "state_read_failed", str(e))
        sys.exit(0)

    # --- Step 0: Pre-flight ---
    try:
        meta = session_meta_mod.load(forge_dir, session_id)
        meta = session_meta_mod.increment_reflection(forge_dir, meta)
        if session_meta_mod.is_loop_detected(meta):
            print(
                f"[forge] Reflection limit reached "
                f"({meta.max_reflections_per_session}/session). Skipping."
            )
            sys.exit(0)
        if session_meta_mod.is_cost_exceeded(meta):
            print(
                f"[forge] Daily cost cap reached "
                f"(${meta.cost_cap_today_usd:.2f}). Skipping."
            )
            sys.exit(0)
    except Exception as e:
        _log_error(forge_dir, "session_meta_failed", str(e))
        # Non-fatal — continue without guards rather than silently skip session

    current_stage: int = state.get("current_stage", 0)
    messages = _read_transcript_tail(transcript_path, last_n=10)

    # Proposals are collected first; writes happen only after gate check
    reflection_proposal: ReflectionProposal | None = None
    lesson_proposals: list[LessonProposal] = []

    # --- Step 1: Reflector ---
    try:
        prose = _compose_reflection_prose(state, messages)
        prompt_hash = hashlib.sha256(prose.encode()).hexdigest()[:16]
        proposal = ReflectionProposal(
            stage=current_stage,
            score=5,
            gaps=[],
            prose=prose,
            model="v0.1-lightweight",
            prompt_hash=prompt_hash,
            temperature=0.0,
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
        ok, reason = validator.validate(proposal, forge_dir)
        if ok:
            reflection_proposal = proposal
        else:
            _log_error(forge_dir, "reflection_rejected", reason)
    except Exception as e:
        _log_error(forge_dir, "reflection_failed", str(e))

    # --- Step 2: Lesson Extractor ---
    correction_flags = forge_dir / "correction-flags.jsonl"
    if correction_flags.exists() and correction_flags.stat().st_size > 0:
        script = _PLUGIN_DIR / "scripts" / "extract-lessons.py"
        if script.exists():
            try:
                result = subprocess.run(
                    [
                        sys.executable, str(script),
                        "--transcript", transcript_path,
                        "--since-flag", str(correction_flags),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if result.returncode == 0 and result.stdout.strip():
                    for raw in _parse_lesson_output(result.stdout, session_id, current_stage):
                        ok, reason = validator.validate(raw, forge_dir)
                        if ok:
                            lesson_proposals.append(raw)
                        else:
                            _log_error(forge_dir, "lesson_rejected", reason)
            except subprocess.TimeoutExpired:
                _log_error(forge_dir, "extract_lessons_timeout", "")
            except Exception as e:
                _log_error(forge_dir, "extract_lessons_failed", str(e))

    # --- Step 3: Gate Check ---
    gate_raw = _run_gate_check(cwd, current_stage, _PLUGIN_DIR)
    stage_advance: StageAdvanceProposal | None = None
    user_done = _detect_done_signal(transcript_path)

    if gate_raw:
        passed = gate_raw.get("passed", 0)
        total = gate_raw.get("total", 0)
        details = gate_raw.get("details", [])
        unmet_blockers = [
            d for d in details
            if not d.get("passed") and d.get("severity") == "blocker"
        ]

        if user_done:
            if not unmet_blockers:
                stage_advance = StageAdvanceProposal(
                    from_stage=current_stage,
                    to_stage=current_stage + 1,
                    triggered_by="done_signal_with_passing_gate",
                    created_at=datetime.datetime.now(datetime.timezone.utc),
                )
            else:
                print(f"🚫 Cannot advance from Stage {current_stage}. Unmet blockers:")
                for b in unmet_blockers:
                    print(f"  - {b.get('check', '?')}: {b.get('description', '')}")
                sys.exit(2)
        else:
            if total > 0:
                print(f"⚠️ Stage {current_stage}: {passed}/{total} gate criteria met.")

    # --- Step 4: Skill Miner (async fire-and-forget) ---
    mine_script = _PLUGIN_DIR / "scripts" / "mine-skills.py"
    if mine_script.exists():
        try:
            subprocess.Popen(
                [sys.executable, str(mine_script), "--session", session_id],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception as e:
            _log_error(forge_dir, "skill_mining_spawn_failed", str(e))

    # --- Step 4b: Surface pending proposals (T-028 approval flow) ---
    _print_pending_proposals(forge_dir)

    # --- Steps 5+6: Validate → Execute (atomic writes + event log) ---
    if reflection_proposal is not None:
        if not executor.execute_reflection(cwd, reflection_proposal, forge_dir, session_id):
            _log_error(forge_dir, "execute_reflection_failed", "")

    if lesson_proposals:
        count = executor.execute_lessons(cwd, lesson_proposals, forge_dir, session_id)
        if count > 0:
            print(f"📚 Captured {count} lesson(s) from corrections.")
            try:
                correction_flags.write_text("")
            except Exception:
                pass

    if stage_advance is not None:
        if executor.execute_stage_advance(cwd, stage_advance, forge_dir, session_id):
            print(
                f"✅ Stage {current_stage} gate passed."
                f" Advanced to stage {current_stage + 1}."
            )
        else:
            _log_error(forge_dir, "advance_stage_failed", "")

    sys.exit(0)


if __name__ == "__main__":
    main()
