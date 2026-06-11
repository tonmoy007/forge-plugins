"""Tests for scripts/health_check.py — the Health daemon (T-144, REQ-F-022..026).

Covers:
  - check_lesson_integrity: clean, missing fields, out-of-range confidence,
    malformed YAML, broken/valid [[xref]] cross-references
  - overall_status: healthy / degraded / failing
  - auto_disable_policy: True only on explicit config; False on absent/false/malformed
  - run(): injected runner — healthy path, failing+policy=True (event+surface written),
    failing+policy=False (nothing disabled, no event), missing files never raises

Uses the importlib load pattern from test_observer.py; injects `runner` so tests
never actually spawn pytest.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
_mod_path = _root / "scripts" / "health_check.py"
_spec = importlib.util.spec_from_file_location("health_check", _mod_path)
_hc = importlib.util.module_from_spec(_spec)
sys.modules["health_check"] = _hc
_spec.loader.exec_module(_hc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_lessons(tmp_path: Path, content: str) -> Path:
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True, exist_ok=True)
    p = forge / "lessons.yaml"
    p.write_text(content)
    return p


def _write_config(tmp_path: Path, content: str) -> Path:
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True, exist_ok=True)
    p = forge / "config.yaml"
    p.write_text(content)
    return p


def _passing_runner(**_kw):
    """Injected runner: simulates all hook tests passing."""
    return "12 passed, 0 failed"


def _failing_runner(**_kw):
    """Injected runner: simulates hook test failures."""
    return "8 passed, 4 failed"


# ---------------------------------------------------------------------------
# check_lesson_integrity
# ---------------------------------------------------------------------------

def test_clean_lessons_no_issues(tmp_path: Path) -> None:
    _write_lessons(tmp_path, """\
schema_version: 1
lessons:
  - trigger: "edit without read"
    rule: "always read before editing"
    confidence: 0.9
    tags: [editing]
    stage: [1, 2]
""")
    issues = _hc.check_lesson_integrity(tmp_path / ".forge" / "lessons.yaml")
    assert issues == []


def test_missing_trigger_flagged(tmp_path: Path) -> None:
    _write_lessons(tmp_path, """\
schema_version: 1
lessons:
  - rule: "always read before editing"
    tags: []
    stage: []
""")
    issues = _hc.check_lesson_integrity(tmp_path / ".forge" / "lessons.yaml")
    kinds = [i["kind"] for i in issues]
    assert "missing_field" in kinds


def test_missing_rule_flagged(tmp_path: Path) -> None:
    _write_lessons(tmp_path, """\
schema_version: 1
lessons:
  - trigger: "do something"
    tags: []
    stage: []
""")
    issues = _hc.check_lesson_integrity(tmp_path / ".forge" / "lessons.yaml")
    kinds = [i["kind"] for i in issues]
    assert "missing_field" in kinds


def test_confidence_too_high_flagged(tmp_path: Path) -> None:
    _write_lessons(tmp_path, """\
schema_version: 1
lessons:
  - trigger: "some trigger"
    rule: "some rule"
    confidence: 1.5
    tags: []
    stage: []
""")
    issues = _hc.check_lesson_integrity(tmp_path / ".forge" / "lessons.yaml")
    kinds = [i["kind"] for i in issues]
    assert "confidence_out_of_range" in kinds


def test_confidence_negative_flagged(tmp_path: Path) -> None:
    _write_lessons(tmp_path, """\
schema_version: 1
lessons:
  - trigger: "some trigger"
    rule: "some rule"
    confidence: -0.1
    tags: []
    stage: []
""")
    issues = _hc.check_lesson_integrity(tmp_path / ".forge" / "lessons.yaml")
    kinds = [i["kind"] for i in issues]
    assert "confidence_out_of_range" in kinds


def test_confidence_boundary_values_ok(tmp_path: Path) -> None:
    _write_lessons(tmp_path, """\
schema_version: 1
lessons:
  - trigger: "trigger a"
    rule: "rule a"
    confidence: 0.0
    tags: []
    stage: []
  - trigger: "trigger b"
    rule: "rule b"
    confidence: 1.0
    tags: []
    stage: []
""")
    issues = _hc.check_lesson_integrity(tmp_path / ".forge" / "lessons.yaml")
    assert not any(i["kind"] == "confidence_out_of_range" for i in issues)


def test_malformed_yaml_yields_malformed_issue_no_crash(tmp_path: Path) -> None:
    _write_lessons(tmp_path, ":\n  bad: [unclosed\n")
    issues = _hc.check_lesson_integrity(tmp_path / ".forge" / "lessons.yaml")
    assert len(issues) >= 1
    kinds = [i["kind"] for i in issues]
    assert "malformed_yaml" in kinds


def test_missing_lessons_file_no_crash(tmp_path: Path) -> None:
    p = tmp_path / ".forge" / "lessons.yaml"
    # file does not exist
    issues = _hc.check_lesson_integrity(p)
    # should return an issue (file missing) or empty list — must not raise
    assert isinstance(issues, list)


def test_broken_xref_flagged(tmp_path: Path) -> None:
    _write_lessons(tmp_path, """\
schema_version: 1
lessons:
  - trigger: "check [[nonexistent-lesson]]"
    rule: "do the thing"
    tags: []
    stage: []
""")
    issues = _hc.check_lesson_integrity(tmp_path / ".forge" / "lessons.yaml")
    kinds = [i["kind"] for i in issues]
    assert "broken_xref" in kinds


def test_valid_xref_not_flagged(tmp_path: Path) -> None:
    _write_lessons(tmp_path, """\
schema_version: 1
lessons:
  - trigger: "first lesson"
    rule: "always read before editing"
    tags: []
    stage: []
  - trigger: "references [[first-lesson]]"
    rule: "cascade rule"
    tags: []
    stage: []
""")
    issues = _hc.check_lesson_integrity(tmp_path / ".forge" / "lessons.yaml")
    assert not any(i["kind"] == "broken_xref" for i in issues)


def test_multiple_lessons_multiple_issues_no_crash(tmp_path: Path) -> None:
    _write_lessons(tmp_path, """\
schema_version: 1
lessons:
  - trigger: "missing rule lesson"
    tags: []
    stage: []
  - rule: "missing trigger lesson"
    tags: []
    stage: []
  - trigger: "out of range"
    rule: "confidence too high"
    confidence: 2.5
    tags: []
    stage: []
""")
    issues = _hc.check_lesson_integrity(tmp_path / ".forge" / "lessons.yaml")
    assert len(issues) >= 3


# ---------------------------------------------------------------------------
# overall_status
# ---------------------------------------------------------------------------

def test_overall_status_healthy() -> None:
    hook_result = {"passed": 10, "failed": 0, "ok": True, "detail": ""}
    lesson_issues: list = []
    assert _hc.overall_status(hook_result, lesson_issues) == "healthy"


def test_overall_status_degraded_lesson_issues() -> None:
    hook_result = {"passed": 10, "failed": 0, "ok": True, "detail": ""}
    lesson_issues = [{"kind": "missing_field", "detail": "lesson 0 missing trigger"}]
    assert _hc.overall_status(hook_result, lesson_issues) == "degraded"


def test_overall_status_failing_hooks() -> None:
    hook_result = {"passed": 5, "failed": 3, "ok": False, "detail": "3 tests failed"}
    lesson_issues: list = []
    assert _hc.overall_status(hook_result, lesson_issues) == "failing"


def test_overall_status_failing_hooks_with_lesson_issues() -> None:
    hook_result = {"passed": 5, "failed": 3, "ok": False, "detail": "3 tests failed"}
    lesson_issues = [{"kind": "broken_xref", "detail": "[[bad-ref]]"}]
    assert _hc.overall_status(hook_result, lesson_issues) == "failing"


# ---------------------------------------------------------------------------
# auto_disable_policy
# ---------------------------------------------------------------------------

def test_auto_disable_true_when_explicitly_set(tmp_path: Path) -> None:
    _write_config(tmp_path, """\
health:
  auto_disable_hooks: true
""")
    assert _hc.auto_disable_policy(tmp_path / ".forge") is True


def test_auto_disable_false_when_set_false(tmp_path: Path) -> None:
    _write_config(tmp_path, """\
health:
  auto_disable_hooks: false
""")
    assert _hc.auto_disable_policy(tmp_path / ".forge") is False


def test_auto_disable_false_when_key_absent(tmp_path: Path) -> None:
    _write_config(tmp_path, """\
health:
  some_other_key: true
""")
    assert _hc.auto_disable_policy(tmp_path / ".forge") is False


def test_auto_disable_false_when_section_absent(tmp_path: Path) -> None:
    _write_config(tmp_path, """\
cost_cap:
  daily_usd: 1.0
""")
    assert _hc.auto_disable_policy(tmp_path / ".forge") is False


def test_auto_disable_false_when_config_missing(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True, exist_ok=True)
    # no config.yaml
    assert _hc.auto_disable_policy(forge) is False


def test_auto_disable_false_when_config_malformed(tmp_path: Path) -> None:
    _write_config(tmp_path, ":\n  bad: [unclosed\n")
    assert _hc.auto_disable_policy(tmp_path / ".forge") is False


# ---------------------------------------------------------------------------
# run() integration tests (injected runner)
# ---------------------------------------------------------------------------

def test_run_healthy_path_no_autodisable(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True, exist_ok=True)
    # clean lessons
    (forge / "lessons.yaml").write_text("""\
schema_version: 1
lessons:
  - trigger: "a"
    rule: "b"
    tags: []
    stage: []
""")

    result = _hc.run(str(tmp_path), runner=_passing_runner)

    assert result["status"] == "healthy"
    assert isinstance(result["report"], str)
    assert result["auto_disabled"] == []
    assert "healthy" in result["report"].lower() or "health" in result["report"].lower()
    # no event log written when healthy
    events_path = forge / "events.jsonl"
    assert not events_path.exists() or events_path.read_text().strip() == ""


def test_run_failing_hooks_policy_true_writes_event_and_surface(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True, exist_ok=True)
    _write_config(tmp_path, "health:\n  auto_disable_hooks: true\n")
    (forge / "lessons.yaml").write_text("""\
schema_version: 1
lessons:
  - trigger: "a"
    rule: "b"
    tags: []
    stage: []
""")

    result = _hc.run(str(tmp_path), runner=_failing_runner)

    assert result["status"] == "failing"
    # Must NOT be silent: event appended
    events_path = forge / "events.jsonl"
    assert events_path.exists(), "events.jsonl must exist when auto-disable fires"
    lines = [l for l in events_path.read_text().splitlines() if l.strip()]
    assert len(lines) >= 1
    event = json.loads(lines[-1])
    assert event["type"] == "health_auto_disable"
    # surface note written
    surface_candidates = list(forge.glob("health-surface*"))
    assert len(surface_candidates) >= 1, "health surface file must be written"
    surface_text = surface_candidates[0].read_text()
    assert len(surface_text.strip()) > 0


def test_run_failing_hooks_policy_false_no_event_no_surface(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True, exist_ok=True)
    # no config — policy defaults to False
    (forge / "lessons.yaml").write_text("""\
schema_version: 1
lessons:
  - trigger: "a"
    rule: "b"
    tags: []
    stage: []
""")

    result = _hc.run(str(tmp_path), runner=_failing_runner)

    assert result["status"] == "failing"
    assert result["auto_disabled"] == []
    events_path = forge / "events.jsonl"
    assert not events_path.exists() or events_path.read_text().strip() == ""
    surface_candidates = list(forge.glob("health-surface*"))
    assert len(surface_candidates) == 0


def test_run_never_raises_no_lessons_file(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True, exist_ok=True)
    # no lessons.yaml, no config.yaml
    result = _hc.run(str(tmp_path), runner=_passing_runner)
    assert isinstance(result, dict)
    assert "status" in result


def test_run_never_raises_no_forge_dir(tmp_path: Path) -> None:
    # .forge doesn't exist
    result = _hc.run(str(tmp_path), runner=_passing_runner)
    assert isinstance(result, dict)
    assert "status" in result


def test_run_result_shape(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True, exist_ok=True)
    result = _hc.run(str(tmp_path), runner=_passing_runner)
    for key in ("status", "report", "issues", "hook_result", "auto_disabled"):
        assert key in result, f"missing key: {key}"
    assert result["status"] in ("healthy", "degraded", "failing")
    assert isinstance(result["issues"], list)
    assert isinstance(result["hook_result"], dict)
    assert isinstance(result["auto_disabled"], list)


def test_recovered_run_clears_stale_surface(tmp_path: Path) -> None:
    # F-026 lifecycle: a failing+policy run writes the surface; a later healthy run
    # clears it so session-start stops showing a resolved auto-disable warning.
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True, exist_ok=True)
    _write_config(tmp_path, "health:\n  auto_disable_hooks: true\n")
    _hc.run(str(tmp_path), runner=_failing_runner)
    assert (forge / "health-surface.txt").exists()  # surfaced while failing

    _hc.run(str(tmp_path), runner=_passing_runner)   # recovered
    assert not (forge / "health-surface.txt").exists()  # stale warning cleared
