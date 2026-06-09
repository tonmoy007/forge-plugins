#!/usr/bin/env python3
"""UserPromptSubmit hook — detect stage intent and flag corrections.

Reads JSON from stdin. Writes JSON additionalContext to stdout if a stage
transition is detected. Appends to .forge/correction-flags.jsonl on corrections.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import sys
from pathlib import Path

_PLUGIN_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(_PLUGIN_DIR / "scripts"))
sys.path.insert(0, str(_PLUGIN_DIR / "hooks"))
import _state_lib as lib
import _state_read
from _hook_runner import run_hook

# /forge:<command> → stage number (aliases keep backward compat; last alias wins _STAGE_NAMES)
_COMMAND_TO_STAGE: dict[str, int] = {
    "srs": 1,
    "ux": 2,
    "product": 2,
    "architecture": 3,
    "arch": 3,
    "spec": 4,
    "plan": 5,
    "build": 6,
    "eval": 7,
    "deploy": 8,
    "monitor": 9,
    "feedback": 10,
    "resolve": 11,
    "release": 12,
}

_STAGE_NAMES = {v: k for k, v in _COMMAND_TO_STAGE.items()}

# Secondary keyword patterns (lower confidence than explicit /forge: commands)
_KEYWORD_PATTERNS: list[tuple[re.Pattern, int]] = [
    (re.compile(r"\brequirements?\s+spec\b|\bsrs\b", re.I), 1),
    (re.compile(r"\bwireframe\b|\bprd\b|\buser\s+flow\b", re.I), 2),
    (re.compile(r"\barchitecture\b|\bc4\s+diagram\b|\bdata\s+model\b", re.I), 3),
    (re.compile(r"\btechnical\s+spec\b|\binterface\s+spec\b", re.I), 4),
    (re.compile(r"\btask\s+dag\b|\brisk\s+register\b", re.I), 5),
    (re.compile(r"\bimplement(?:ation)?\b|\bbuilding\b|\bcoding\b", re.I), 6),
    (re.compile(r"\bevaluat(?:e|ion)\b|\btest\s+results?\b", re.I), 7),
    (re.compile(r"\bdeploy(?:ment)?\b|\brollback\b", re.I), 8),
    (re.compile(r"\bmonitor(?:ing)?\b|\bobservability\b|\bslo\b", re.I), 9),
    (re.compile(r"\buser\s+feedback\b|\btriage\b", re.I), 10),
    (re.compile(r"\bhotfix\b|\bresolv(?:e|ing)\b", re.I), 11),
    (re.compile(r"\breleas(?:e|ing)\b|\bchangelog\b", re.I), 12),
]

_CORRECTION_RE = re.compile(
    r"\b(no[,!]?\s|wrong|not\s+right|instead|actually|i\s+told\s+you|"
    r"you\s+said|don'?t\s+do\s+that|stop\s+doing|incorrect|that'?s\s+not)\b",
    re.I,
)


def detect_stage_intent(prompt: str) -> int | None:
    """Return stage number if prompt expresses a clear stage intent, else None."""
    # Explicit /forge: command takes priority
    m = re.search(r"/forge:(\w+)", prompt)
    if m:
        cmd = m.group(1).lower()
        if cmd in _COMMAND_TO_STAGE:
            return _COMMAND_TO_STAGE[cmd]

    # Keyword fallback
    for pattern, stage in _KEYWORD_PATTERNS:
        if pattern.search(prompt):
            return stage

    return None


def detect_corrections(prompt: str) -> bool:
    return bool(_CORRECTION_RE.search(prompt))


def flag_correction(forge_dir: Path, session_id: str, prompt: str) -> None:
    """Append a correction signal to .forge/correction-flags.jsonl."""
    forge_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "session": session_id,
        "prompt": prompt[:200],
    }
    flags_file = forge_dir / "correction-flags.jsonl"
    with flags_file.open("a") as f:
        f.write(json.dumps(record) + "\n")


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}

    prompt: str = payload.get("prompt", "")
    cwd = Path(payload.get("cwd", os.getcwd()))
    session_id: str = payload.get("session_id", "")

    # Flag corrections regardless of Forge project status
    if detect_corrections(prompt):
        try:
            flag_correction(cwd / ".forge", session_id, prompt)
        except Exception:  # noqa: BLE001
            pass  # never block on logging failure

    # Stage intent only relevant for Forge projects
    state_path = cwd / "pipeline" / "state.md"
    if not state_path.exists():
        sys.exit(0)

    detected = detect_stage_intent(prompt)
    if detected is None:
        sys.exit(0)

    state, warning = _state_read.read_state_safe(str(cwd), payload.get("session_id", ""))
    if warning:
        print(warning)
    current_stage = state.get("current_stage", 0)

    if detected == current_stage:
        sys.exit(0)  # already on this stage

    stage_name = _STAGE_NAMES.get(detected, str(detected))
    msg = (
        f"[Forge] Stage intent detected: Stage {detected} ({stage_name}). "
        f"Current stage: {current_stage}. "
        f"Run /forge:status to check gate status before advancing."
    )
    print(json.dumps({"additionalContext": msg}))
    sys.exit(0)


if __name__ == "__main__":
    run_hook(main, hook_name="prompt-submit")
