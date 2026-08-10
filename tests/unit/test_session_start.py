"""Unit tests for hooks/session-start.py (tested via subprocess)."""
from __future__ import annotations

import datetime
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

HOOK = str(Path(__file__).parent.parent.parent / "hooks" / "session-start.py")
PLUGIN_DIR = str(Path(__file__).parent.parent.parent)
PYTHON = sys.executable


def _load_hook_module():
    """Load hooks/session-start.py in-process (hyphenated filename → importlib).

    The module's top-level inserts ``scripts/`` + ``hooks/`` on ``sys.path`` and
    imports the real plugin libs, so exec resolves against the live plugin — the
    same code path the subprocess hook runs. Used to unit-test the in-process
    graduation wiring (``_register_and_promote``) directly (T-210)."""
    spec = importlib.util.spec_from_file_location("session_start", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(cwd: str, env: dict | None = None) -> subprocess.CompletedProcess:
    payload = json.dumps({"cwd": cwd, "hook_event_name": "SessionStart"})
    # Default to the kill switch so tests never spawn a real `claude` refresh
    # (T-138). A test that exercises the capability path passes its own env.
    run_env = env if env is not None else {**os.environ, "FORGE_NO_BACKGROUND": "1"}
    return subprocess.run(
        [PYTHON, HOOK],
        input=payload,
        capture_output=True,
        text=True,
        env=run_env,
    )


def _make_state(
    tmp_path: Path,
    *,
    stage: int = 0,
    project_type: str = "unknown",
    task: str | None = None,
    blockers: list | None = None,
) -> Path:
    (tmp_path / "pipeline").mkdir(parents=True, exist_ok=True)
    state = tmp_path / "pipeline" / "state.md"
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    state.write_text(
        f"---\n"
        f"schema_version: 1\n"
        f"project_type: {project_type}\n"
        f"cycle: 1\n"
        f"current_stage: {stage}\n"
        f"current_task: {task!r}\n"
        f"current_milestone: null\n"
        f"total_tasks: null\n"
        f"last_updated: {now}\n"
        f"blockers: {json.dumps(blockers or [])}\n"
        f"---\n\n# Pipeline State\n\n## Stage History\n\n## Last Reflection\n"
    )
    return state


def _make_lessons(tmp_path: Path, lessons: list[dict]) -> None:
    forge_dir = tmp_path / ".forge"
    forge_dir.mkdir(exist_ok=True)
    data = {"schema_version": 1, "lessons": lessons}
    import yaml
    (forge_dir / "lessons.yaml").write_text(yaml.dump(data))


def _make_rule(tmp_path: Path, name: str, body: str) -> None:
    d = tmp_path / ".forge" / "rules"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(body)


class TestAutopilotResumeAfterCompact:
    """T-188 / REQ-CTX-007: after a compaction, re-inject a resume pointer when an
    autopilot run is active so the loop continues without redoing completed stages."""

    def _run_src(self, cwd: str, source: str) -> subprocess.CompletedProcess:
        payload = json.dumps({"cwd": cwd, "hook_event_name": "SessionStart", "source": source})
        env = {**os.environ, "FORGE_NO_BACKGROUND": "1"}
        return subprocess.run([PYTHON, HOOK], input=payload, capture_output=True,
                              text=True, env=env)

    def _activate(self, tmp_path: Path, stage: int = 6) -> None:
        forge = tmp_path / ".forge"
        forge.mkdir(parents=True, exist_ok=True)
        (forge / "autopilot-session.json").write_text(json.dumps({"status": "running"}))
        (forge / "autopilot-checkpoint.json").write_text(json.dumps(
            {"schema_version": 1, "current_stage": stage,
             "next_action": f"resume at stage {stage} via /forge:build"}))

    def test_compact_with_active_run_injects_resume(self, tmp_path):
        _make_state(tmp_path, stage=6)
        self._activate(tmp_path, 6)
        r = self._run_src(str(tmp_path), "compact")
        assert r.returncode == 0
        assert "resuming after compaction" in r.stdout.lower()
        assert "do not redo" in r.stdout.lower()
        assert "stage 6" in r.stdout.lower()

    def test_compact_without_active_run_no_resume(self, tmp_path):
        _make_state(tmp_path, stage=6)  # no session/checkpoint ⇒ no active run
        r = self._run_src(str(tmp_path), "compact")
        assert r.returncode == 0
        assert "resuming after compaction" not in r.stdout.lower()

    def test_non_compact_source_no_resume(self, tmp_path):
        _make_state(tmp_path, stage=6)
        self._activate(tmp_path, 6)
        r = self._run_src(str(tmp_path), "startup")
        assert r.returncode == 0
        assert "resuming after compaction" not in r.stdout.lower()


class TestTraceabilityGapNote:
    """_traceability_gap_note: advisory surfacing of .forge/traceability-gaps.jsonl,
    filtered to gaps assigned to the CURRENT stage's agent. Read-only, fail-soft,
    never blocking — mirrors the _health_surface_note / _unread_findings_note
    pattern."""

    def _write_gaps(self, tmp_path: Path, gaps: list[dict]) -> None:
        forge = tmp_path / ".forge"
        forge.mkdir(parents=True, exist_ok=True)
        content = "\n".join(json.dumps(g) for g in gaps)
        (forge / "traceability-gaps.jsonl").write_text(content + ("\n" if gaps else ""))

    def test_no_file_returns_empty(self, tmp_path):
        mod = _load_hook_module()
        assert mod._traceability_gap_note(tmp_path, 5) == ""

    def test_gap_matching_current_stage_surfaced(self, tmp_path):
        self._write_gaps(tmp_path, [
            {"id": "REQ-004", "category": "unimplemented", "file": "pipeline/01-srs/srs.md",
             "detail": "never referenced", "stage": 5, "agent": "planner"},
        ])
        mod = _load_hook_module()
        note = mod._traceability_gap_note(tmp_path, 5)
        assert "1 gap(s)" in note
        assert "planner" in note
        assert "REQ-004" in note

    def test_gap_for_different_stage_stays_silent(self, tmp_path):
        self._write_gaps(tmp_path, [
            {"id": "REQ-004", "category": "unimplemented", "file": "pipeline/01-srs/srs.md",
             "detail": "never referenced", "stage": 5, "agent": "planner"},
        ])
        mod = _load_hook_module()
        assert mod._traceability_gap_note(tmp_path, 3) == ""

    def test_multiple_gaps_same_stage_counted(self, tmp_path):
        self._write_gaps(tmp_path, [
            {"id": "REQ-004", "category": "unimplemented", "file": "pipeline/01-srs/srs.md",
             "detail": "x", "stage": 5, "agent": "planner"},
            {"id": "NFR-001", "category": "unimplemented", "file": "pipeline/01-srs/srs.md",
             "detail": "y", "stage": 5, "agent": "planner"},
        ])
        mod = _load_hook_module()
        note = mod._traceability_gap_note(tmp_path, 5)
        assert "2 gap(s)" in note

    def test_malformed_line_skipped_not_crashed(self, tmp_path):
        forge = tmp_path / ".forge"
        forge.mkdir(parents=True, exist_ok=True)
        (forge / "traceability-gaps.jsonl").write_text("not json\n{\"stage\": 5, \"agent\": \"planner\", \"id\": \"REQ-1\"}\n")
        mod = _load_hook_module()
        note = mod._traceability_gap_note(tmp_path, 5)
        assert "1 gap(s)" in note

    def test_end_to_end_via_subprocess(self, tmp_path):
        _make_state(tmp_path, stage=5)
        self._write_gaps(tmp_path, [
            {"id": "REQ-004", "category": "unimplemented", "file": "pipeline/01-srs/srs.md",
             "detail": "never referenced", "stage": 5, "agent": "planner"},
        ])
        r = _run(str(tmp_path))
        assert r.returncode == 0
        assert "Traceability" in r.stdout
        assert "planner" in r.stdout
        assert "REQ-004" in r.stdout

    def test_end_to_end_no_gaps_no_mention(self, tmp_path):
        _make_state(tmp_path, stage=5)
        r = _run(str(tmp_path))
        assert r.returncode == 0
        assert "Traceability" not in r.stdout


class TestNonForgeDir:
    def test_no_pipeline_silent_exit_0(self, tmp_path):
        r = _run(str(tmp_path))
        assert r.returncode == 0
        assert r.stdout.strip() == ""

    def test_no_pipeline_no_stderr(self, tmp_path):
        r = _run(str(tmp_path))
        assert r.stderr.strip() == ""


class TestFreshState:
    def test_stage_0_outputs_forge_lines(self, tmp_path):
        _make_state(tmp_path, stage=0)
        r = _run(str(tmp_path))
        assert r.returncode == 0
        assert "[Forge]" in r.stdout

    def test_stage_0_shows_not_started(self, tmp_path):
        _make_state(tmp_path, stage=0)
        r = _run(str(tmp_path))
        assert "Stage 0" in r.stdout
        assert "not started" in r.stdout

    def test_stage_0_suggests_srs(self, tmp_path):
        _make_state(tmp_path, stage=0)
        r = _run(str(tmp_path))
        assert "srs" in r.stdout.lower()


class TestContextContent:
    def test_shows_project_type(self, tmp_path):
        _make_state(tmp_path, stage=3, project_type="ml-pipeline")
        r = _run(str(tmp_path))
        assert "ml-pipeline" in r.stdout

    def test_shows_current_task(self, tmp_path):
        _make_state(tmp_path, stage=6, task="T-007")
        r = _run(str(tmp_path))
        assert "T-007" in r.stdout

    def test_shows_blockers(self, tmp_path):
        _make_state(tmp_path, stage=6, blockers=["GPU out of memory"])
        r = _run(str(tmp_path))
        assert "GPU out of memory" in r.stdout

    def test_no_blockers_not_shown(self, tmp_path):
        _make_state(tmp_path, stage=3, blockers=[])
        r = _run(str(tmp_path))
        assert "Blockers" not in r.stdout

    def test_gate_criteria_line_present(self, tmp_path):
        _make_state(tmp_path, stage=1)
        r = _run(str(tmp_path))
        assert "gate criteria" in r.stdout.lower()


class TestLessonsFiltering:
    def test_no_lessons_shows_zero(self, tmp_path):
        _make_state(tmp_path, stage=6, project_type="fullstack")
        _make_lessons(tmp_path, [])
        r = _run(str(tmp_path), env={**os.environ, "HOME": str(tmp_path)})
        assert "Active lessons (0)" in r.stdout

    def test_matching_lesson_included(self, tmp_path):
        _make_state(tmp_path, stage=6, project_type="fullstack")
        _make_lessons(tmp_path, [{
            "id": "L-001",
            "stage": [6],
            "project_types": ["fullstack"],
            "trigger": "use design tokens not raw values",
            "rule": "always use --color- variables",
            "why": "audit fails",
            "frequency": 3,
            "last_used": "2026-05-01",
            "tags": ["design"],
        }])
        r = _run(str(tmp_path), env={**os.environ, "HOME": str(tmp_path)})
        assert "Active lessons (1)" in r.stdout
        assert "design token" in r.stdout.lower()

    def test_non_matching_stage_excluded(self, tmp_path):
        _make_state(tmp_path, stage=3, project_type="fullstack")
        _make_lessons(tmp_path, [{
            "id": "L-001",
            "stage": [6],  # only relevant at stage 6
            "project_types": [],
            "trigger": "stage-6-only lesson",
            "rule": "skip this",
            "why": "irrelevant",
            "frequency": 5,
            "last_used": "2026-05-01",
            "tags": [],
        }])
        r = _run(str(tmp_path))
        assert "stage-6-only" not in r.stdout

    def test_fifty_lessons_capped_at_five(self, tmp_path):
        _make_state(tmp_path, stage=6, project_type="fullstack")
        lessons = [
            {
                "id": f"L-{i:03d}",
                "stage": [],
                "project_types": [],
                "trigger": f"lesson trigger {i}",
                "rule": f"rule {i}",
                "why": "why",
                "frequency": i,
                "last_used": "2026-05-01",
                "tags": [],
            }
            for i in range(50)
        ]
        _make_lessons(tmp_path, lessons)
        r = _run(str(tmp_path), env={**os.environ, "HOME": str(tmp_path)})
        # Should show at most 5 project lessons
        import re
        m = re.search(r"Active lessons \((\d+)\)", r.stdout)
        assert m is not None
        assert int(m.group(1)) <= 5

    def test_ml_project_shows_gpu_lesson_not_docs_lesson(self, tmp_path):
        # done-when criterion for T-020: stage 6 ML project sees GPU lessons,
        # not documentation-only lessons
        _make_state(tmp_path, stage=6, project_type="ml-pipeline")
        _make_lessons(tmp_path, [
            {
                "id": "L-gpu",
                "stage": [6],
                "project_types": ["ml-pipeline"],
                "trigger": "GPU out-of-memory error during training",
                "rule": "always set PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True",
                "why": "prevents fragmentation OOM",
                "frequency": 4,
                "last_used": "2026-05-10",
                "tags": ["gpu", "ml"],
            },
            {
                "id": "L-docs",
                "stage": [1],
                "project_types": ["documentation"],
                "trigger": "writing docs for a docs-only project",
                "rule": "use mkdocs not sphinx",
                "why": "team convention",
                "frequency": 2,
                "last_used": "2026-05-01",
                "tags": ["docs"],
            },
        ])
        r = _run(str(tmp_path))
        assert "GPU out-of-memory" in r.stdout
        assert "mkdocs" not in r.stdout

    def test_non_matching_project_type_excluded(self, tmp_path):
        _make_state(tmp_path, stage=6, project_type="fullstack")
        _make_lessons(tmp_path, [{
            "id": "L-001",
            "stage": [],
            "project_types": ["ml-pipeline"],  # only for ML projects
            "trigger": "ml-only lesson trigger",
            "rule": "use GPU",
            "why": "ML needs GPU",
            "frequency": 5,
            "last_used": "2026-05-01",
            "tags": ["ml"],
        }])
        r = _run(str(tmp_path))
        assert "ml-only lesson trigger" not in r.stdout

    def test_lessons_sorted_by_frequency_descending(self, tmp_path):
        _make_state(tmp_path, stage=6, project_type="fullstack")
        _make_lessons(tmp_path, [
            {
                "id": "L-low",
                "stage": [],
                "project_types": [],
                "trigger": "low-frequency trigger",
                "rule": "rare rule",
                "why": "why",
                "frequency": 1,
                "last_used": "2026-05-01",
                "tags": [],
            },
            {
                "id": "L-high",
                "stage": [],
                "project_types": [],
                "trigger": "high-frequency trigger",
                "rule": "common rule",
                "why": "why",
                "frequency": 10,
                "last_used": "2026-05-01",
                "tags": [],
            },
        ])
        r = _run(str(tmp_path))
        high_pos = r.stdout.find("high-frequency")
        low_pos = r.stdout.find("low-frequency")
        assert high_pos != -1 and low_pos != -1
        assert high_pos < low_pos


class TestTokenBudget:
    def test_output_under_2000_tokens(self, tmp_path):
        _make_state(tmp_path, stage=6, project_type="fullstack")
        lessons = [
            {
                "id": f"L-{i:03d}",
                "stage": [],
                "project_types": [],
                "trigger": "x" * 200,  # long triggers
                "rule": "r" * 200,
                "why": "w",
                "frequency": i,
                "last_used": "2026-05-01",
                "tags": [],
            }
            for i in range(10)
        ]
        _make_lessons(tmp_path, lessons)
        r = _run(str(tmp_path))
        assert r.returncode == 0
        # rough token estimate: len / 4 < 2000 → len < 8000
        assert len(r.stdout) < 8000


class TestCorruptedState:
    def test_corrupted_state_exits_0(self, tmp_path):
        (tmp_path / "pipeline").mkdir()
        (tmp_path / "pipeline" / "state.md").write_text("not: valid: yaml: [[\n")
        r = _run(str(tmp_path))
        assert r.returncode == 0

    def test_corrupted_state_no_crash(self, tmp_path):
        (tmp_path / "pipeline").mkdir()
        (tmp_path / "pipeline" / "state.md").write_text("")
        r = _run(str(tmp_path))
        assert r.returncode == 0


class TestBackgroundCapability:
    """T-138 — REQ-F-001: session-start maintains .forge/capabilities.json and
    surfaces unread Observer findings, without blocking (NF-004)."""

    def test_capabilities_written_when_cli_absent(self, tmp_path):
        # No `claude` on PATH + kill switch OFF → synchronous available:false write.
        _make_state(tmp_path, stage=1, project_type="api")
        env = {**os.environ, "PATH": "/nonexistent", "FORGE_NO_BACKGROUND": "0"}
        r = _run(str(tmp_path), env=env)
        assert r.returncode == 0
        cap = json.loads((tmp_path / ".forge" / "capabilities.json").read_text())
        assert cap["forge_background_available"] is False

    def test_kill_switch_skips_capability_work(self, tmp_path):
        # Default _run sets FORGE_NO_BACKGROUND=1 → no capabilities.json, no crash.
        _make_state(tmp_path, stage=1, project_type="api")
        r = _run(str(tmp_path))
        assert r.returncode == 0
        assert not (tmp_path / ".forge" / "capabilities.json").exists()

    def test_unread_findings_surfaced(self, tmp_path):
        _make_state(tmp_path, stage=2, project_type="api")
        forge = tmp_path / ".forge"
        forge.mkdir(exist_ok=True)
        (forge / "observer-findings.jsonl").write_text('{"a":1}\n{"b":2}\n')
        r = _run(str(tmp_path))
        assert "2 unread Observer finding(s)" in r.stdout

    def test_no_findings_no_note(self, tmp_path):
        _make_state(tmp_path, stage=2, project_type="api")
        r = _run(str(tmp_path))
        assert "unread Observer" not in r.stdout

    def test_read_cursor_subtracted_from_unread(self, tmp_path):
        # T-142: only findings past the read cursor count as unread.
        _make_state(tmp_path, stage=2, project_type="api")
        forge = tmp_path / ".forge"
        forge.mkdir(exist_ok=True)
        (forge / "observer-findings.jsonl").write_text('{"a":1}\n{"b":2}\n{"c":3}\n')
        (forge / "observer-findings.read").write_text("2")  # first two already seen
        r = _run(str(tmp_path))
        assert "1 unread Observer finding(s)" in r.stdout

    def test_all_findings_read_no_note(self, tmp_path):
        _make_state(tmp_path, stage=2, project_type="api")
        forge = tmp_path / ".forge"
        forge.mkdir(exist_ok=True)
        (forge / "observer-findings.jsonl").write_text('{"a":1}\n{"b":2}\n')
        (forge / "observer-findings.read").write_text("2")
        r = _run(str(tmp_path))
        assert "unread Observer" not in r.stdout

    def test_health_surface_alert_shown(self, tmp_path):
        # T-144 / REQ-F-026: a pending auto-disable warning is surfaced at start.
        _make_state(tmp_path, stage=2, project_type="api")
        forge = tmp_path / ".forge"
        forge.mkdir(exist_ok=True)
        (forge / "health-surface.txt").write_text(
            "[2026-06-11T00:00:00Z] Forge Health: FAILING — auto-disable policy triggered.\n"
            "more detail on the next line\n"
        )
        r = _run(str(tmp_path))
        assert "Health alert" in r.stdout
        assert "FAILING" in r.stdout

    def test_no_health_surface_no_alert(self, tmp_path):
        _make_state(tmp_path, stage=2, project_type="api")
        r = _run(str(tmp_path))
        assert "Health alert" not in r.stdout


class TestToolPreflightAdvisory:
    """T-230 / REQ-TR-004: session-start surfaces one advisory line per missing
    required tool, read from the cached .forge/tool-status.json (stdlib only),
    dropped first under token pressure, silent when nothing missing / no cache."""

    def test_missing_required_tool_surfaced(self, tmp_path):
        _make_state(tmp_path, stage=8, project_type="api")
        forge = tmp_path / ".forge"
        forge.mkdir(exist_ok=True)
        (forge / "tool-status.json").write_text(json.dumps({
            "docker": {"present": False, "version": None, "required": True,
                       "reason": "Docker artifacts present", "install_cmd": "brew install docker"},
        }))
        r = _run(str(tmp_path))
        assert "docker" in r.stdout
        assert "/forge:preflight" in r.stdout

    def test_present_required_tool_not_surfaced(self, tmp_path):
        _make_state(tmp_path, stage=8, project_type="api")
        forge = tmp_path / ".forge"
        forge.mkdir(exist_ok=True)
        (forge / "tool-status.json").write_text(json.dumps({
            "docker": {"present": True, "version": "27.0", "required": True,
                       "reason": "x", "install_cmd": None},
        }))
        r = _run(str(tmp_path))
        assert "/forge:preflight" not in r.stdout

    def test_missing_but_not_required_tool_not_surfaced(self, tmp_path):
        _make_state(tmp_path, stage=1, project_type="api")
        forge = tmp_path / ".forge"
        forge.mkdir(exist_ok=True)
        (forge / "tool-status.json").write_text(json.dumps({
            "docker": {"present": False, "version": None, "required": False,
                       "reason": "no Docker artifacts", "install_cmd": "brew install docker"},
        }))
        r = _run(str(tmp_path))
        assert "/forge:preflight" not in r.stdout

    def test_no_cache_file_no_advisory_no_crash(self, tmp_path):
        _make_state(tmp_path, stage=1, project_type="api")
        r = _run(str(tmp_path))
        assert r.returncode == 0
        assert "/forge:preflight" not in r.stdout

    def test_unreadable_cache_no_advisory_no_crash(self, tmp_path):
        _make_state(tmp_path, stage=1, project_type="api")
        forge = tmp_path / ".forge"
        forge.mkdir(exist_ok=True)
        (forge / "tool-status.json").write_text("{not valid json")
        r = _run(str(tmp_path))
        assert r.returncode == 0
        assert "/forge:preflight" not in r.stdout

    def test_tool_block_dropped_first_under_token_pressure(self, tmp_path):
        """A large tool-status.json alone must not push output over budget --
        it is dropped before lessons/rules trim, not after (AC-TR-003)."""
        _make_state(tmp_path, stage=8, project_type="api")
        forge = tmp_path / ".forge"
        forge.mkdir(exist_ok=True)
        many_missing = {
            f"tool-{i}": {"present": False, "version": None, "required": True,
                          "reason": "x" * 50, "install_cmd": "y" * 50}
            for i in range(80)
        }
        (forge / "tool-status.json").write_text(json.dumps(many_missing))
        r = _run(str(tmp_path))
        assert r.returncode == 0
        assert len(r.stdout) < 8000  # stays under the ~2000-token budget
        assert "[Forge] Pipeline: Stage 8" in r.stdout  # core context untouched
        assert "/forge:preflight" not in r.stdout  # the oversized tool block was dropped

    def test_ensure_tool_status_skips_fresh_cache(self, tmp_path, monkeypatch):
        mod = _load_hook_module()
        forge = tmp_path / ".forge"
        forge.mkdir(parents=True)
        (forge / "tool-status.json").write_text("{}")
        calls = []
        monkeypatch.setattr(mod.subprocess, "Popen", lambda *a, **k: calls.append(a))
        mod._ensure_tool_status(tmp_path)
        assert calls == []

    def test_ensure_tool_status_refreshes_stale_cache(self, tmp_path, monkeypatch):
        mod = _load_hook_module()
        forge = tmp_path / ".forge"
        forge.mkdir(parents=True)
        stale = forge / "tool-status.json"
        stale.write_text("{}")
        old = os.path.getmtime(stale) - mod._TOOL_TTL_SECONDS - 10
        os.utime(stale, (old, old))
        calls = []
        monkeypatch.setattr(mod.subprocess, "Popen", lambda *a, **k: calls.append(a) or object())
        mod._ensure_tool_status(tmp_path)
        assert len(calls) == 1
        assert "tool_preflight.py" in calls[0][0][1]
        assert "refresh" in calls[0][0]

    def test_ensure_tool_status_respects_kill_switch(self, tmp_path, monkeypatch):
        mod = _load_hook_module()
        monkeypatch.setenv("FORGE_NO_BACKGROUND", "1")
        calls = []
        monkeypatch.setattr(mod.subprocess, "Popen", lambda *a, **k: calls.append(a))
        mod._ensure_tool_status(tmp_path)
        assert calls == []

    def test_ensure_tool_status_never_raises(self, tmp_path, monkeypatch):
        mod = _load_hook_module()

        def _boom(*a, **k):
            raise OSError("boom")

        monkeypatch.setattr(mod.subprocess, "Popen", _boom)
        mod._ensure_tool_status(tmp_path)  # must not raise


class TestRulesInjection:
    """T-159 / REQ-RULES-009: session-start injects always + current-stage rules
    within the token budget; absent rules dir is a clean no-op."""

    def _env(self, tmp_path):
        # Isolate HOME so the global-lessons store can't add stray lines.
        return {**os.environ, "HOME": str(tmp_path), "FORGE_NO_BACKGROUND": "1"}

    def test_always_rule_injected_any_stage(self, tmp_path):
        _make_state(tmp_path, stage=3, project_type="api")
        _make_rule(tmp_path, "10-tone.md",
                   "---\ndescription: Be terse\nscope: always\n---\nKeep prose short.\n")
        r = _run(str(tmp_path), env=self._env(tmp_path))
        assert "[Forge] Rules" in r.stdout
        assert "10-tone" in r.stdout

    def test_stage_rule_present_at_its_stage(self, tmp_path):
        _make_state(tmp_path, stage=6, project_type="api")
        _make_rule(tmp_path, "20-build.md",
                   "---\ndescription: Build-stage rule\nscope: stage\nstages: [6]\n---\nx\n")
        r = _run(str(tmp_path), env=self._env(tmp_path))
        assert "[Forge] Rules" in r.stdout
        assert "20-build" in r.stdout

    def test_stage_rule_absent_off_stage(self, tmp_path):
        _make_state(tmp_path, stage=3, project_type="api")
        _make_rule(tmp_path, "20-build.md",
                   "---\ndescription: Build-stage rule\nscope: stage\nstages: [6]\n---\nx\n")
        r = _run(str(tmp_path), env=self._env(tmp_path))
        assert "[Forge] Rules" not in r.stdout  # no always/matching-stage rules

    def test_no_rules_dir_no_rules_line(self, tmp_path):
        _make_state(tmp_path, stage=6, project_type="api")
        r = _run(str(tmp_path), env=self._env(tmp_path))
        assert "[Forge] Rules" not in r.stdout

    def test_glob_rule_not_injected_at_session_start(self, tmp_path):
        # glob rules are write-time only (pre-tool-write), not session-start.
        _make_state(tmp_path, stage=6, project_type="api")
        _make_rule(tmp_path, "30-ui.md",
                   "---\nscope: glob\nglobs: ['**/*.tsx']\n---\nui rule\n")
        r = _run(str(tmp_path), env=self._env(tmp_path))
        assert "[Forge] Rules" not in r.stdout

    def test_rules_stay_within_token_budget(self, tmp_path):
        _make_state(tmp_path, stage=6, project_type="api")
        for i in range(30):
            _make_rule(tmp_path, f"r{i:02d}.md",
                       f"---\nscope: always\npriority: {i}\n---\n" + ("x" * 300) + "\n")
        r = _run(str(tmp_path), env=self._env(tmp_path))
        assert r.returncode == 0
        assert "[Forge] Rules" in r.stdout
        assert len(r.stdout) < 8000  # ~2000-token budget (len/4)


# ---------------------------------------------------------------------------
# T-210 / REQ-GR-006 (NF-034 / NF-037, AC-GR-005): session-start runs the
# in-process THREE-TIER graduation (lessons + skills + workflows), fail-soft
# and silent on the happy path, with a FORGE_NO_GRADUATE escape hatch.
# These exercise `_register_and_promote` in-process (not via subprocess) so we
# can assert the global-store side effects and that nothing ever raises.
# ---------------------------------------------------------------------------

# A workflow that validates clean (mirrors _VALID_WF in test_graduation_workflows).
_VALID_WORKFLOW = "name: {name}\nnodes:\n  - id: a\n    prompt: \"do a\"\n"


def _workflow_run_record(name: str, ts: str) -> dict:
    """A successful `workflow_run` event: names the flow, completed ≥1 node, no fail."""
    return {
        "schema_version": 1, "ts": ts, "event": "workflow_run", "name": name,
        "nodes": 1, "waves": 1, "completed": ["a"], "dropped": [],
        "total_cost_usd": 0.01, "verdicts": {}, "admitted": ["a"],
    }


def _seed_qualifying_workflow(project: Path, name: str = "deploy", runs: int = 2) -> None:
    """Give `project` a clean workflow YAML + `runs` successful runs in events.jsonl."""
    wf_dir = project / ".forge" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / f"{name}.yaml").write_text(_VALID_WORKFLOW.format(name=name), encoding="utf-8")
    events = project / ".forge" / "events.jsonl"
    lines = [json.dumps(_workflow_run_record(name, f"2026-06-0{i + 1}T10:00:00Z"))
             for i in range(runs)]
    events.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestThreeTierGraduationWiring:
    """AC-GR-005: `_register_and_promote` drives all three graduation tiers in
    process — lessons, skills, AND workflows — fail-soft and never raising."""

    def test_three_tier_graduation_promotes_workflow(self, tmp_path, monkeypatch):
        """A qualifying workflow in the registered project graduates — proving the
        workflows tier (not just lessons) is wired through `_register_and_promote`."""
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: home))

        project = tmp_path / "proj"
        project.mkdir()
        _seed_qualifying_workflow(project, "deploy", runs=2)

        mod = _load_hook_module()
        mod._register_and_promote(project)

        global_dir = home / ".forge"
        # Registry written (lessons-preserving register step still happens).
        assert (global_dir / "projects.yaml").exists()
        # Workflows tier promoted the flow → file copied + indexed.
        assert (global_dir / "workflows" / "deploy.yaml").exists()
        index = yaml.safe_load((global_dir / "global-workflows.yaml").read_text())
        names = [w.get("name") for w in (index.get("workflows") or [])]
        assert "deploy" in names

    def test_simultaneous_broken_inputs_never_raise(self, tmp_path, monkeypatch):
        """THE core AC: an unwritable ~/.forge, a MALFORMED events.jsonl, and a
        MISSING skill-stats.jsonl all at once — `_register_and_promote` returns
        normally and raises NOTHING (fail-soft per tier + a top-level guard)."""
        home = tmp_path / "home"
        home.mkdir(mode=0o500)  # read+exec only → writes under it fail
        monkeypatch.setattr(Path, "home", staticmethod(lambda: home))

        project = tmp_path / "proj"
        (project / ".forge" / "workflows").mkdir(parents=True)
        # Malformed events.jsonl (broken JSON lines) — workflows tier must skip it.
        (project / ".forge" / "events.jsonl").write_text("{not json\n[[[\n", encoding="utf-8")
        # A clean workflow exists, but its runs can't be counted from broken events.
        (project / ".forge" / "workflows" / "x.yaml").write_text(
            _VALID_WORKFLOW.format(name="x"), encoding="utf-8")
        # .forge/skill-stats.jsonl intentionally MISSING (skills tier degrades).

        mod = _load_hook_module()
        try:
            result = mod._register_and_promote(project)
        except Exception as exc:  # pragma: no cover — the whole point is no raise
            pytest.fail(f"_register_and_promote raised under broken inputs: {exc!r}")
        assert result is None  # returns normally (None), never propagates

    def test_unwritable_home_via_register_raise_is_swallowed(self, tmp_path, monkeypatch):
        """Even if the very first step (register_project) raises, the top-level
        guard swallows it — no exception escapes the hook."""
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: home))

        project = tmp_path / "proj"
        project.mkdir()

        mod = _load_hook_module()
        import _graduation as core

        def _boom(*a, **k):  # noqa: ANN001, ANN002, ANN003
            raise OSError("read-only file system")

        monkeypatch.setattr(core, "register_project", _boom)
        try:
            assert mod._register_and_promote(project) is None
        except Exception as exc:  # pragma: no cover
            pytest.fail(f"register_project failure escaped: {exc!r}")

    def test_forge_no_graduate_escape_skips_everything(self, tmp_path, monkeypatch):
        """FORGE_NO_GRADUATE set → no registry write and graduate() is NOT called."""
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
        monkeypatch.setenv("FORGE_NO_GRADUATE", "1")

        project = tmp_path / "proj"
        project.mkdir()

        mod = _load_hook_module()
        import _graduation as core

        called: list[bool] = []
        monkeypatch.setattr(core, "graduate", lambda *a, **k: called.append(True))
        monkeypatch.setattr(core, "register_project",
                            lambda *a, **k: called.append(True))

        assert mod._register_and_promote(project) is None
        assert called == []  # neither register_project nor graduate ran
        assert not (home / ".forge" / "projects.yaml").exists()
