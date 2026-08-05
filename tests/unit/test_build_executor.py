"""T-248 / REQ-BUILDEXEC-001: scripts/build_executor.py, the deterministic Stage 6
Pro execution engine.

Covers the task-dag's own "Done when" bar: context-resolve scoping
(AC-BUILDEXEC-001a), gate per-check reporting (AC-BUILDEXEC-001b),
commit/progress-write-only-on-pass, traceability-chain extension after commit
(AC-BUILDEXEC-001d), build-log.jsonl append shape, resume skip-logic, DEFECT-###
escalation, and that the batch path delegates to parallel_build.run_parallel_build
rather than duplicating it (AC-BUILDEXEC-001c).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_executor as be  # noqa: E402


DAG_TEXT = """\
## Milestone 1: Foundation

### T-001 [S] First task
- **Description**: Implement the first thing.
- **Files**: `pkg/first.py`, `tests/unit/test_first.py`
- **Done when**: pkg/first.py exists and is tested.
- **Depends on**: none
- **REQ-IDs**: REQ-FIRST-001

### T-002 [S] Second task
- **Description**: Implement the second thing.
- **Files**: `pkg/second.py`
- **Done when**: pkg/second.py exists.
- **Depends on**: T-001
- **REQ-IDs**: REQ-SECOND-001
"""

SPEC_TEXT = """\
## MOD-001 First module

Covers REQ-FIRST-001. Implement `pkg/first.py` to do the first thing.

## MOD-002 Second module

Covers REQ-SECOND-001. Implement `pkg/second.py` to do the second thing.
"""

SRS_TEXT = """\
## Functional Requirements

- REQ-FIRST-001: The system does the first thing.
- REQ-SECOND-001: The system does the second thing.
"""


def _seed_project(tmp_path: Path) -> Path:
    (tmp_path / "pipeline" / "05-plan").mkdir(parents=True)
    (tmp_path / "pipeline" / "05-plan" / "task-dag.md").write_text(DAG_TEXT)
    (tmp_path / "pipeline" / "04-spec").mkdir(parents=True)
    (tmp_path / "pipeline" / "04-spec" / "technical-spec.md").write_text(SPEC_TEXT)
    (tmp_path / "pipeline" / "01-srs").mkdir(parents=True)
    (tmp_path / "pipeline" / "01-srs" / "srs.md").write_text(SRS_TEXT)
    return tmp_path


# --------------------------------------------------------------------------- #
# resolve_task_entry — pure parsing
# --------------------------------------------------------------------------- #


def test_resolve_task_entry_extracts_all_fields() -> None:
    entry = be.resolve_task_entry(DAG_TEXT, "T-001")
    assert entry is not None
    assert entry.id == "T-001"
    assert entry.files == ["pkg/first.py", "tests/unit/test_first.py"]
    assert entry.depends_on == []
    assert entry.req_ids == ["REQ-FIRST-001"]
    assert "first thing" in entry.description


def test_resolve_task_entry_depends_on_parsed() -> None:
    entry = be.resolve_task_entry(DAG_TEXT, "T-002")
    assert entry is not None
    assert entry.depends_on == ["T-001"]


def test_resolve_task_entry_missing_task_returns_none() -> None:
    assert be.resolve_task_entry(DAG_TEXT, "T-999") is None


# --------------------------------------------------------------------------- #
# resolve_context — AC-BUILDEXEC-001a scoping + hard requirement invariant
# --------------------------------------------------------------------------- #


def test_resolve_context_scopes_to_task_relevant_spec_only(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    bundle = be.resolve_context(tmp_path, "T-001")
    assert bundle.task_id == "T-001"
    assert any("MOD-001" in s for s in bundle.spec_excerpts)
    assert not any("MOD-002" in s for s in bundle.spec_excerpts), (
        "context bundle must not include the other task's spec section"
    )


def test_resolve_context_architecture_not_resolved_at_default_depth(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    bundle = be.resolve_context(tmp_path, "T-001")
    assert bundle.architecture_excerpts is None


def test_resolve_context_fails_closed_without_resolvable_requirement(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    dag = (tmp_path / "pipeline" / "05-plan" / "task-dag.md").read_text()
    dag = dag.replace("REQ-FIRST-001", "REQ-NOT-DEFINED-999")
    (tmp_path / "pipeline" / "05-plan" / "task-dag.md").write_text(dag)
    with pytest.raises(be.ContextResolutionError):
        be.resolve_context(tmp_path, "T-001")


def test_resolve_context_missing_task_raises(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    with pytest.raises(be.ContextResolutionError):
        be.resolve_context(tmp_path, "T-999")


# --------------------------------------------------------------------------- #
# Gate — AC-BUILDEXEC-001b per-check reporting, never one aggregate boolean
# --------------------------------------------------------------------------- #


def test_run_check_skips_with_reason_when_no_command_detected() -> None:
    check = be.run_check(Path("."), "compile", be.DetectedCommand(None, "no compile step"))
    assert check.status == "skipped"
    assert check.detail == "no compile step"


def test_run_check_reports_pass_on_zero_exit(tmp_path: Path) -> None:
    detected = be.DetectedCommand([sys.executable, "-c", "pass"])
    check = be.run_check(tmp_path, "test", detected)
    assert check.status == "pass"


def test_run_check_reports_fail_with_detail_on_nonzero_exit(tmp_path: Path) -> None:
    detected = be.DetectedCommand([sys.executable, "-c", "import sys; sys.exit(1)"])
    check = be.run_check(tmp_path, "test", detected)
    assert check.status == "fail"


def test_gate_report_passed_false_if_any_check_failed() -> None:
    report = be.GateReport(checks=[
        be.GateCheck(name="compile", status="pass"),
        be.GateCheck(name="lint", status="fail", detail="boom"),
        be.GateCheck(name="test", status="skipped", detail="n/a"),
    ])
    assert report.passed is False


def test_gate_report_passed_true_when_no_failures() -> None:
    report = be.GateReport(checks=[
        be.GateCheck(name="compile", status="skipped", detail="n/a"),
        be.GateCheck(name="lint", status="pass"),
    ])
    assert report.passed is True


def test_gate_report_never_collapses_to_single_boolean() -> None:
    report = be.GateReport(checks=[
        be.GateCheck(name="compile", status="pass"),
        be.GateCheck(name="lint", status="fail", detail="boom"),
    ])
    lines = report.to_lines()
    assert len(lines) == 2, "per-check report must have one line per check, not one aggregate"


def test_detect_gate_commands_python_project(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
    detected = be.detect_gate_commands(tmp_path)
    assert detected["compile"].argv is None
    assert detected["test"].argv is not None


def test_detect_gate_commands_no_stack_skips_all() -> None:
    empty = Path("/tmp") / "definitely-not-a-real-project-dir-xyz"
    detected = be.detect_gate_commands(Path("/"))
    for name in ("compile", "lint", "test", "static_analysis"):
        assert detected[name].argv is None


# --------------------------------------------------------------------------- #
# build-log.jsonl append shape
# --------------------------------------------------------------------------- #


def test_append_build_log_writes_one_json_line(tmp_path: Path) -> None:
    be.append_build_log(tmp_path, {"task_id": "T-001", "passed": True})
    log_path = tmp_path / be.BUILD_LOG_RELPATH
    lines = log_path.read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["task_id"] == "T-001"


def test_append_build_log_appends_without_truncating(tmp_path: Path) -> None:
    be.append_build_log(tmp_path, {"task_id": "T-001", "passed": False})
    be.append_build_log(tmp_path, {"task_id": "T-001", "passed": True})
    lines = (tmp_path / be.BUILD_LOG_RELPATH).read_text().splitlines()
    assert len(lines) == 2


def test_consecutive_failures_fails_closed_on_corrupted_line(tmp_path: Path) -> None:
    """A malformed build-log.jsonl line must count as a failure (fail closed), not
    be silently skipped -- silent skipping would undercount and could suppress the
    DEFECT-### escalation gate on a corrupted log."""
    path = tmp_path / be.BUILD_LOG_RELPATH
    path.parent.mkdir(parents=True)
    path.write_text('{not valid json\n')
    assert be.consecutive_failures(tmp_path, "T-001") == 1


def test_consecutive_failures_corrupted_line_still_stops_at_a_real_pass(tmp_path: Path) -> None:
    path = tmp_path / be.BUILD_LOG_RELPATH
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"task_id": "T-001", "passed": True}) + "\n"
        + "{not valid json\n"
    )
    # newest-first scan: the corrupted line (counted as a failure) comes before the
    # earlier passing entry, which still stops the count.
    assert be.consecutive_failures(tmp_path, "T-001") == 1


# --------------------------------------------------------------------------- #
# record_attempt — commit/progress-write only on pass; traceability extension
# --------------------------------------------------------------------------- #


def _fake_git_ok(argv, **kwargs):
    if argv[:2] == ["git", "rev-parse"]:
        return subprocess.CompletedProcess(argv, 0, stdout="abc1234\n", stderr="")
    return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")


def test_record_attempt_commits_and_writes_progress_on_pass(tmp_path: Path) -> None:
    report = be.GateReport(checks=[be.GateCheck(name="test", status="pass")])
    result = be.record_attempt(
        tmp_path, "T-001", ["pkg/first.py"], report, run=_fake_git_ok, now=1000.0,
    )
    assert result.committed is True
    assert result.commit_sha == "abc1234"


def test_record_attempt_git_add_uses_dashdash_pathspec_separator(tmp_path: Path) -> None:
    """A file path that happens to start with '-' must never be interpreted as a
    git flag -- 'git add' needs a '--' separator before the pathspecs."""
    calls: list[list[str]] = []

    def _spy(argv, **kwargs):
        calls.append(argv)
        return _fake_git_ok(argv, **kwargs)

    report = be.GateReport(checks=[be.GateCheck(name="test", status="pass")])
    be.record_attempt(
        tmp_path, "T-001", ["-evil-looking-path.py"], report, run=_spy, now=1000.0,
    )
    add_call = next(c for c in calls if c[:2] == ["git", "add"])
    assert add_call == ["git", "add", "--", "-evil-looking-path.py"]
    progress = (tmp_path / be.PROGRESS_RELPATH).read_text()
    assert "T-001" in progress
    assert "[x]" in progress


def test_record_attempt_does_not_commit_on_gate_failure(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def _spy(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    report = be.GateReport(checks=[be.GateCheck(name="test", status="fail", detail="broke")])
    result = be.record_attempt(
        tmp_path, "T-001", ["pkg/first.py"], report, run=_spy, now=1000.0,
    )
    assert result.committed is False
    assert not any(c[:2] == ["git", "commit"] for c in calls), "must not commit on gate failure"
    progress_path = tmp_path / be.PROGRESS_RELPATH
    if progress_path.exists():
        assert "[x]" not in progress_path.read_text()


def test_record_attempt_extends_traceability_only_on_pass(tmp_path: Path) -> None:
    trace_dir = tmp_path / "pipeline" / "05-plan"
    trace_dir.mkdir(parents=True)
    (trace_dir / "traceability.md").write_text("### T-001\n\n- **Requirement:** REQ-FIRST-001\n")

    report = be.GateReport(checks=[be.GateCheck(name="test", status="pass")])
    be.record_attempt(tmp_path, "T-001", ["pkg/first.py"], report, run=_fake_git_ok, now=1000.0)

    trace_text = (trace_dir / "traceability.md").read_text()
    assert "**Code:**" in trace_text
    assert "pkg/first.py" in trace_text


def test_record_attempt_appends_build_log_entry_every_attempt(tmp_path: Path) -> None:
    report_fail = be.GateReport(checks=[be.GateCheck(name="test", status="fail", detail="x")])
    be.record_attempt(tmp_path, "T-001", ["pkg/first.py"], report_fail, run=_fake_git_ok, now=1.0)
    report_pass = be.GateReport(checks=[be.GateCheck(name="test", status="pass")])
    be.record_attempt(tmp_path, "T-001", ["pkg/first.py"], report_pass, run=_fake_git_ok, now=2.0)
    lines = (tmp_path / be.BUILD_LOG_RELPATH).read_text().splitlines()
    assert len(lines) == 2


# --------------------------------------------------------------------------- #
# DEFECT-### escalation — opens on the SECOND consecutive failure, not the first
# --------------------------------------------------------------------------- #


def test_defect_not_opened_on_first_failure(tmp_path: Path) -> None:
    report = be.GateReport(checks=[be.GateCheck(name="test", status="fail", detail="x")])
    result = be.record_attempt(tmp_path, "T-001", ["pkg/first.py"], report, run=_fake_git_ok, now=1.0)
    assert result.defect_id is None


def test_defect_opened_on_second_consecutive_failure(tmp_path: Path) -> None:
    report = be.GateReport(checks=[be.GateCheck(name="test", status="fail", detail="x")])
    be.record_attempt(tmp_path, "T-001", ["pkg/first.py"], report, run=_fake_git_ok, now=1.0)
    result = be.record_attempt(tmp_path, "T-001", ["pkg/first.py"], report, run=_fake_git_ok, now=2.0)
    assert result.defect_id == "DEFECT-001"


def test_defect_resets_after_a_passing_attempt(tmp_path: Path) -> None:
    fail = be.GateReport(checks=[be.GateCheck(name="test", status="fail", detail="x")])
    passed = be.GateReport(checks=[be.GateCheck(name="test", status="pass")])
    be.record_attempt(tmp_path, "T-001", ["pkg/first.py"], fail, run=_fake_git_ok, now=1.0)
    be.record_attempt(tmp_path, "T-001", ["pkg/first.py"], passed, run=_fake_git_ok, now=2.0)
    result = be.record_attempt(tmp_path, "T-001", ["pkg/first.py"], fail, run=_fake_git_ok, now=3.0)
    assert result.defect_id is None, "a passing attempt must reset the consecutive-failure count"


# --------------------------------------------------------------------------- #
# Resume skip-logic
# --------------------------------------------------------------------------- #


def test_done_tasks_empty_when_no_progress_file(tmp_path: Path) -> None:
    assert be.done_tasks(tmp_path) == set()


def test_done_tasks_parses_marked_lines(tmp_path: Path) -> None:
    path = tmp_path / be.PROGRESS_RELPATH
    path.parent.mkdir(parents=True)
    path.write_text("- [x] T-001 — done (commit abc1234)\n- [ ] T-002 — not started\n")
    assert be.done_tasks(tmp_path) == {"T-001"}


def test_record_attempt_marks_task_done_for_resume(tmp_path: Path) -> None:
    report = be.GateReport(checks=[be.GateCheck(name="test", status="pass")])
    be.record_attempt(tmp_path, "T-001", ["pkg/first.py"], report, run=_fake_git_ok, now=1.0)
    assert be.done_tasks(tmp_path) == {"T-001"}


# --------------------------------------------------------------------------- #
# Batch path — AC-BUILDEXEC-001c: delegates to parallel_build, never duplicates it
# --------------------------------------------------------------------------- #


def test_run_batch_delegates_to_parallel_build_run_parallel_build(tmp_path: Path, monkeypatch) -> None:
    _seed_project(tmp_path)
    calls = {}

    def _fake_run_parallel_build(tasks, done, **kwargs):
        calls["tasks"] = [t.id for t in tasks]
        calls["done"] = done
        return "sentinel-result"

    monkeypatch.setattr(be._pb, "run_parallel_build", _fake_run_parallel_build)

    result = be.run_batch(
        tmp_path, 1, config=object(), forge_dir=tmp_path / ".forge", feature="build",
    )

    assert result == "sentinel-result"
    assert calls["tasks"] == ["T-001", "T-002"]


def test_run_batch_resume_passes_done_set(tmp_path: Path, monkeypatch) -> None:
    _seed_project(tmp_path)
    progress = tmp_path / be.PROGRESS_RELPATH
    progress.parent.mkdir(parents=True)
    progress.write_text("- [x] T-001 — done\n")

    calls = {}

    def _fake_run_parallel_build(tasks, done, **kwargs):
        calls["done"] = done
        return None

    monkeypatch.setattr(be._pb, "run_parallel_build", _fake_run_parallel_build)
    be.run_batch(
        tmp_path, 1, config=object(), forge_dir=tmp_path / ".forge", feature="build", resume=True,
    )
    assert calls["done"] == {"T-001"}
