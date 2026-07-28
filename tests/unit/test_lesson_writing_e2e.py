"""Regression tests for the lesson-writing path (root Claude Code plugin).

Root cause: hooks/stop-reflect.py invoked scripts/extract-lessons.py with
--transcript/--since-flag, but that script's argparse only ever defined
--cwd/--input/--output/--dry-run/--since/--llm — every invocation failed
with an argparse usage error (exit 2), so tasks/lessons.md and
.forge/lessons.yaml were never written. This bug was originally found and
fixed in the forge-opencode/ port (test_opencode_lesson_writing.py); this
file pins the same fix for the root plugin's own copies of these files.
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).parent.parent.parent
HOOK = str(_ROOT / "hooks" / "stop-reflect.py")
EXTRACT_SCRIPT = _ROOT / "scripts" / "extract-lessons.py"
PYTHON = sys.executable

# Hyphenated filename — must use importlib
_spec = importlib.util.spec_from_file_location("root_extract_lessons", EXTRACT_SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["root_extract_lessons"] = _mod
_spec.loader.exec_module(_mod)


def _run_hook(payload: dict, cwd: str) -> subprocess.CompletedProcess:
    data = json.dumps({**payload, "cwd": cwd})
    return subprocess.run(
        [PYTHON, HOOK],
        input=data,
        capture_output=True,
        text=True,
        env={"CLAUDE_PLUGIN_ROOT": str(_ROOT), **os.environ},
    )


def _make_state(tmp_path: Path, stage: int = 3) -> None:
    (tmp_path / "pipeline").mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "pipeline" / "state.md").write_text(
        f"---\nschema_version: 1\nproject_type: fullstack\ncycle: 1\n"
        f"current_stage: {stage}\ncurrent_task: null\ncurrent_milestone: null\n"
        f"total_tasks: null\nlast_updated: {now}\nblockers: []\n---\n\n"
        "# Pipeline State\n\n## Stage History\n\n## Last Reflection\n"
    )


def _write_correction(tmp_path: Path, prompt: str, session: str = "s1") -> Path:
    forge_dir = tmp_path / ".forge"
    forge_dir.mkdir(exist_ok=True)
    record = {
        "ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session": session,
        "prompt": prompt,
    }
    flags = forge_dir / "correction-flags.jsonl"
    flags.write_text(json.dumps(record) + "\n")
    return flags


class TestExtractLessonsProposeMode:
    def test_propose_flag_accepted(self, tmp_path):
        _write_correction(tmp_path, "no, don't do that, do this instead because it broke")
        result = subprocess.run(
            [
                PYTHON, str(EXTRACT_SCRIPT),
                "--cwd", str(tmp_path),
                "--input", str(tmp_path / ".forge" / "correction-flags.jsonl"),
                "--propose",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

    def test_propose_emits_yaml_without_writing_file(self, tmp_path):
        flags = _write_correction(
            tmp_path, "no, don't use subprocess here, use importlib.util instead because it broke"
        )
        result = subprocess.run(
            [PYTHON, str(EXTRACT_SCRIPT), "--cwd", str(tmp_path), "--input", str(flags), "--propose"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        parsed = yaml.safe_load(result.stdout)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert set(parsed[0]) >= {"trigger", "rule", "why"}
        assert not (tmp_path / "tasks" / "lessons.md").exists()

    def test_old_nonexistent_flags_now_rejected_by_argparse(self, tmp_path):
        result = subprocess.run(
            [PYTHON, str(EXTRACT_SCRIPT), "--transcript", "x", "--since-flag", "y"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "unrecognized arguments" in result.stderr


class TestStopReflectWritesLessons:
    def test_correction_produces_lesson_file(self, tmp_path):
        _make_state(tmp_path, stage=3)
        _write_correction(
            tmp_path,
            "no, don't use subprocess here, use importlib.util instead because it broke",
        )
        r = _run_hook({"hook_event_name": "Stop", "session_id": "s1"}, cwd=str(tmp_path))
        assert r.returncode == 0, r.stderr
        lessons_md = tmp_path / "tasks" / "lessons.md"
        assert lessons_md.exists(), f"tasks/lessons.md was not written. stdout={r.stdout!r} stderr={r.stderr!r}"
        assert "importlib.util" in lessons_md.read_text()

    def test_correction_produces_lessons_yaml(self, tmp_path):
        _make_state(tmp_path, stage=3)
        _write_correction(
            tmp_path,
            "no, don't use subprocess here, use importlib.util instead because it broke",
        )
        _run_hook({"hook_event_name": "Stop", "session_id": "s1"}, cwd=str(tmp_path))
        lessons_yaml = tmp_path / ".forge" / "lessons.yaml"
        assert lessons_yaml.exists()
        entries = yaml.safe_load(lessons_yaml.read_text())
        assert isinstance(entries, list) and len(entries) == 1
        assert entries[0]["trust"] == "ephemeral"

    def test_correction_flags_cleared_after_successful_write(self, tmp_path):
        _make_state(tmp_path, stage=3)
        flags = _write_correction(
            tmp_path,
            "no, don't use subprocess here, use importlib.util instead because it broke",
        )
        _run_hook({"hook_event_name": "Stop", "session_id": "s1"}, cwd=str(tmp_path))
        assert flags.read_text() == ""

    def test_subprocess_run_passes_cwd_kwarg(self):
        source = Path(HOOK).read_text()
        step2 = source[source.index("Step 2: Lesson Extractor"):source.index("Step 3: Gate Check")]
        assert "cwd=str(cwd)" in step2
        assert "--transcript" not in step2
        assert "--since-flag" not in step2
