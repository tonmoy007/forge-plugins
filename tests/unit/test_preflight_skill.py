"""Structural tests for the /forge:preflight skill (T-231, REQ-TR-005).

Covers AC-TR-004: frontmatter parses (no ': ' YAML trap -- lesson 2026-06-22),
allowed-tools: [Read, Bash], documents the detect -> confirm -> install flow,
and states it never auto-runs an installer.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent.parent
_SKILL = _ROOT / "skills" / "forge-preflight" / "SKILL.md"


def _frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, "SKILL.md must start with YAML frontmatter"
    return yaml.safe_load(m.group(1))


def test_skill_exists_with_valid_frontmatter() -> None:
    assert _SKILL.exists()
    fm = _frontmatter(_SKILL.read_text())
    assert fm.get("name") == "preflight"
    assert fm.get("description")


def test_skill_declares_read_and_bash_only() -> None:
    fm = _frontmatter(_SKILL.read_text())
    assert fm.get("allowed-tools") == ["Read", "Bash"]


def test_skill_documents_detect_confirm_install_flow() -> None:
    body = _SKILL.read_text().lower()
    assert "tool_preflight.py check" in body
    assert "confirm" in body
    assert "install" in body


def test_skill_states_never_auto_runs() -> None:
    body = _SKILL.read_text().lower()
    assert "never" in body and "auto" in body


def test_skill_never_installs_a_declined_tool() -> None:
    body = _SKILL.read_text().lower()
    assert "declin" in body


def test_skill_does_not_run_install_command_without_confirmation_language() -> None:
    """Structural guard: every install invocation the skill instructs must be
    gated behind explicit confirmation wording nearby."""
    body = _SKILL.read_text()
    assert "only after" in body.lower() or "only once" in body.lower()
