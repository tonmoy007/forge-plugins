#!/usr/bin/env python3
"""SessionStart hook — inject pipeline state and lessons into Claude context.

Reads JSON from stdin, prints a context block (≤ 2000 tokens) to stdout.
Exits 0 silently if cwd is not a Forge project.

Wrapped by _hook_runner.run_hook() to ensure:
  - Any uncaught exception is logged to .forge/hook-errors.log, exit 0
  - 30s timeout (override via FORGE_HOOK_TIMEOUT_SESSION_START)
  - Non-blocking semantics enforced

Ref: T-007 (original), T-100 (resilience wrap)
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

import shutil
import subprocess
import time

# v0.1.5.1: fail soft when PyYAML is missing — a hook must never crash-spam the
# session with an import traceback (_state_lib and others require PyYAML).
try:
    import yaml  # noqa: F401
except ImportError:
    print(
        "[Forge] PyYAML is not installed — Forge hooks are inactive. "
        "Fix: pip install pyyaml (then run /forge:doctor).",
        file=sys.stderr,
    )
    raise SystemExit(0)

# Resolve plugin root and make _state_lib + _hook_runner importable
_PLUGIN_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(_PLUGIN_DIR / "scripts"))
sys.path.insert(0, str(_PLUGIN_DIR / "hooks"))
import _state_lib as lib  # noqa: E402
import _state_read  # noqa: E402
import _background_agent  # noqa: E402  (capability cache — REQ-F-001)
from _hook_runner import run_hook  # noqa: E402

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
_CAP_TTL_SECONDS = 86400  # re-probe background capability at most once/day


def _ensure_capabilities(cwd: Path) -> None:
    """Keep .forge/capabilities.json fresh without blocking (REQ-F-001, NF-004).

    The probe shells to `claude agents` (~0.3s) — too slow for the session-start
    budget — so it is offloaded to a detached refresh and this hook only reads the
    cached file. Refresh only when the cache is missing or older than the TTL.
    Never raises (startup must not break on capability maintenance).
    """
    if os.environ.get("FORGE_NO_BACKGROUND") == "1":
        return  # kill switch — no background work at all (also keeps tests hermetic)
    forge = cwd / ".forge"
    cap_file = forge / "capabilities.json"
    try:
        if cap_file.exists() and (time.time() - cap_file.stat().st_mtime) < _CAP_TTL_SECONDS:
            return  # fresh enough
        if shutil.which("claude") is None:
            # No CLI: write the negative result directly — cheap, no subprocess.
            _background_agent.write_capabilities(forge, cwd=str(cwd))
            return
        # CLI present: offload the slow probe; never wait (fire-and-forget).
        subprocess.Popen(
            [sys.executable, str(_PLUGIN_DIR / "hooks" / "_background_agent.py"),
             "--write-capabilities", "--forge-dir", str(forge), "--cwd", str(cwd)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:  # noqa: BLE001 — capability upkeep must never break startup
        return


def _unread_findings_note(cwd: Path) -> str:
    """One-line note when the Observer (T-142) has left **unread** findings; '' otherwise.

    Unread = total findings minus the read cursor (`.forge/observer-findings.read`,
    advanced when the user views /forge:status). Read-only — surfacing does not mark
    findings read here, so the note persists until the user actually looks.
    """
    forge = cwd / ".forge"
    path = forge / "observer-findings.jsonl"
    try:
        if not path.exists():
            return ""
        total = sum(1 for ln in path.read_text().splitlines() if ln.strip())
        try:
            seen = int((forge / "observer-findings.read").read_text().strip())
        except (OSError, ValueError):
            seen = 0
        unread = max(0, total - seen)
        return f"\n[Forge] {unread} unread Observer finding(s) — see /forge:status" if unread else ""
    except OSError:
        return ""


def _health_surface_note(cwd: Path) -> str:
    """Surface a pending Health auto-disable warning at session start (REQ-F-026).

    The Health daemon writes `.forge/health-surface.txt` only when status is FAILING
    *and* the explicit auto-disable policy is on — never silently. A healthy re-run
    clears it. Read-only here. '' when there is nothing to surface.
    """
    path = cwd / ".forge" / "health-surface.txt"
    try:
        if not path.exists():
            return ""
        note = path.read_text().strip()
        return f"\n[Forge] Health alert — {note.splitlines()[0]}" if note else ""
    except OSError:
        return ""


def _poll_observer_if_running(cwd: Path) -> None:
    """Lazily trigger an Observer poll at session start when it's overdue (REQ-F-008).

    Detached and fire-and-forget — the Stop/Start hooks never wait on the ~7s dispatch
    (NF-004). Gated on the kill switch, a running session, and a positive capability
    cache; observer.py itself re-checks staleness (`--poll-if-stale`). Never raises.
    """
    if os.environ.get("FORGE_NO_BACKGROUND") == "1":
        return  # kill switch (also keeps tests hermetic)
    forge = cwd / ".forge"
    try:
        session = forge / "observer-session.json"
        if not session.exists():
            return  # Observer never started — nothing to poll
        import json as _json
        try:
            if (_json.loads(session.read_text()) or {}).get("status") != "running":
                return
        except (OSError, ValueError):
            return
        caps = forge / "capabilities.json"
        if not caps.exists():
            return
        subprocess.Popen(
            [sys.executable, str(_PLUGIN_DIR / "scripts" / "observer.py"),
             "--poll-if-stale", "--cwd", str(cwd), "--forge-dir", str(forge)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:  # noqa: BLE001 — poll upkeep must never break startup
        return


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


def _is_stale(last_used: object, max_age_days: int) -> bool:
    """EF-026: True if last_used (YYYY-MM-DD/ISO) is older than max_age_days.
    Missing/unparseable dates are kept (not stale)."""
    if not last_used:
        return False
    try:
        date = datetime.date.fromisoformat(str(last_used)[:10])
    except ValueError:
        return False
    return (datetime.date.today() - date).days > max_age_days


def _load_lessons(path: Path, stage: int, project_type: str,
                  max_age_days: Optional[int] = None) -> list[dict]:
    """Load and filter lessons from a YAML file. Returns [] on any failure.

    When max_age_days is set (global store, EF-026), lessons whose last_used is
    older than that are skipped so abandoned entries decay out of recall.
    """
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text()) or {}
        lessons: list[dict] = data.get("lessons", []) or []

        def _matches(lesson: dict) -> bool:
            stages = lesson.get("stage", []) or []
            types = lesson.get("project_types", []) or []
            if max_age_days is not None and _is_stale(lesson.get("last_used"), max_age_days):
                return False
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


def run(cwd: Path, session_id: str = "") -> Optional[str]:
    """Return context string, or None to exit silently."""
    state_path = cwd / "pipeline" / "state.md"
    if not state_path.exists():
        return None  # not a Forge project

    # REQ-SILENTSTATE-001: surface read failures instead of swallowing them.
    state, warning = _state_read.read_state_safe(str(cwd), session_id)
    if not state:
        return warning or "[Forge] Warning: pipeline/state.md is unreadable — run /forge:doctor."

    stage = state.get("current_stage", 0)
    project_type = state.get("project_type", "unknown")

    _sync_lessons_if_stale(cwd)
    _register_and_promote(cwd)
    _ensure_capabilities(cwd)  # REQ-F-001 — refresh the cached capability probe
    _poll_observer_if_running(cwd)  # REQ-F-008 — lazy Observer poll, detached

    # Lessons: up to 5 project-level + 3 global
    project_lessons = _load_lessons(
        cwd / ".forge" / "lessons.yaml", stage, project_type
    )[:5]
    global_lessons = _load_lessons(
        Path.home() / ".forge" / "global-lessons.yaml", stage, project_type,
        max_age_days=30,  # EF-026: stale global lessons decay out of recall
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

    # REQ-F-012: surface unread Observer findings; REQ-F-026: Health auto-disable alert
    context += _unread_findings_note(cwd)
    context += _health_surface_note(cwd)

    return context


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}

    cwd = Path(payload.get("cwd", os.getcwd()))
    result = run(cwd, payload.get("session_id", ""))
    if result is not None:
        print(result)
    sys.exit(0)


if __name__ == "__main__":
    run_hook(main, hook_name="session-start")