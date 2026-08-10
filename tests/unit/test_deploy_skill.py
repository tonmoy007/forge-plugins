"""Structural tests for the /forge:deploy skill's cross-cutting Docker wiring
(T-232, REQ-DK-002).

Covers AC-DK-002: skills/forge-deploy/SKILL.md invokes check_docker_readiness.py
--cwd . unconditionally in pre-flight and relays findings as advisory, worded
non-blocking.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
_SKILL = _ROOT / "skills" / "forge-deploy" / "SKILL.md"


def test_skill_exists() -> None:
    assert _SKILL.exists()


def test_skill_runs_docker_readiness_check_unconditionally() -> None:
    body = _SKILL.read_text()
    assert "check_docker_readiness.py --cwd ." in body


def test_docker_check_is_in_pre_flight_not_gated_on_profile() -> None:
    body = _SKILL.read_text()
    pre_flight_idx = body.index("## Pre-flight Check")
    check_idx = body.index("check_docker_readiness.py --cwd .")
    steps_idx = body.index("## Steps")
    assert pre_flight_idx < check_idx < steps_idx, (
        "the Docker readiness check must run unconditionally in pre-flight, "
        "for every project regardless of profile — not gated behind a profile check"
    )


def test_docker_check_worded_as_advisory_never_blocking() -> None:
    body = _SKILL.read_text().lower()
    assert "advisory" in body
    assert "never block" in body or "not block" in body or "does not block" in body
