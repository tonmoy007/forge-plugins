"""Structural tests for the /forge:autopilot skill (T-163).

Guards the in-session loop contract: gate-checked advance, stop-on-gate (never force by
default), narration, and the run-log record step.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
_SKILL = _ROOT / "skills" / "forge-autopilot" / "SKILL.md"


def _frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, "SKILL.md must start with YAML frontmatter"
    fm: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def test_skill_exists_with_name():
    assert _SKILL.exists()
    fm = _frontmatter(_SKILL.read_text())
    assert fm.get("name") == "forge-autopilot"
    assert fm.get("description")


def test_skill_drives_gate_checked_advance():
    body = _SKILL.read_text()
    assert "autopilot.py" in body            # uses the planner
    assert "check-gate.py" in body           # checks each gate
    assert "state-manager.py advance" in body  # advances via the sanctioned path
    assert "record" in body                  # records the run-log


def test_skill_is_stop_on_gate_and_never_forces():
    body = _SKILL.read_text().lower()
    assert "stop-on-gate" in body or "stop on gate" in body
    assert "never" in body and "force" in body  # never force by default


def test_skill_narrates_and_is_interruptible():
    body = _SKILL.read_text()
    assert "[Forge] autopilot:" in body
    assert "/forge:autopilot-stop" in body


def test_skill_starts_and_finishes_session():
    body = _SKILL.read_text()
    assert "autopilot.py start" in body
    assert "autopilot.py finish" in body


_STOP_SKILL = _ROOT / "skills" / "forge-autopilot-stop" / "SKILL.md"


def test_stop_skill_exists_and_requests_stop():
    assert _STOP_SKILL.exists()
    fm = _frontmatter(_STOP_SKILL.read_text())
    assert fm.get("name") == "forge-autopilot-stop"
    body = _STOP_SKILL.read_text()
    assert "autopilot.py stop" in body
    assert "--resume" in body  # tells the user how to continue later
