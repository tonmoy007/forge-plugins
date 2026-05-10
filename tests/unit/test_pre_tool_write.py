"""Unit tests for hooks/pre-tool-write.py (tested via subprocess)."""
from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = str(Path(__file__).parent.parent.parent / "hooks" / "pre-tool-write.py")
PYTHON = sys.executable


def _run(
    tool_name: str,
    file_path: str,
    content: str,
    cwd: str,
    tool_type: str = "Write",
) -> subprocess.CompletedProcess:
    tool_input: dict = {"file_path": file_path}
    if tool_type == "Write":
        tool_input["content"] = content
    else:
        tool_input["new_string"] = content

    payload = json.dumps({
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": tool_input,
        "cwd": cwd,
        "session_id": "test-session",
    })
    return subprocess.run(
        [PYTHON, HOOK],
        input=payload,
        capture_output=True,
        text=True,
    )


def _make_state(tmp_path: Path, stage: int = 6) -> None:
    (tmp_path / "pipeline").mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "pipeline" / "state.md").write_text(
        f"---\nschema_version: 1\nproject_type: fullstack\ncycle: 1\n"
        f"current_stage: {stage}\ncurrent_task: null\ncurrent_milestone: null\n"
        f"total_tasks: null\nlast_updated: {now}\nblockers: []\n---\n\n# State\n"
    )


def _make_design_system(tmp_path: Path) -> None:
    ds_dir = tmp_path / "pipeline" / "02-product-ux"
    ds_dir.mkdir(parents=True, exist_ok=True)
    (ds_dir / "design-system.md").write_text("# Design System\n\n## Colors\n")


class TestToolNameFiltering:
    def test_read_tool_no_output(self, tmp_path):
        _make_state(tmp_path)
        _make_design_system(tmp_path)
        r = _run("Read", "src/app.tsx", "color: #fff;", str(tmp_path))
        assert r.returncode == 0
        assert r.stdout.strip() == ""

    def test_bash_tool_no_output(self, tmp_path):
        _make_state(tmp_path)
        _make_design_system(tmp_path)
        r = _run("Bash", "src/app.tsx", "color: #fff;", str(tmp_path))
        assert r.returncode == 0
        assert r.stdout.strip() == ""

    def test_write_tool_fires(self, tmp_path):
        _make_state(tmp_path)
        _make_design_system(tmp_path)
        r = _run("Write", "src/app.css", "color: #fff;", str(tmp_path))
        assert r.returncode == 0
        assert r.stdout.strip() != ""

    def test_edit_tool_fires(self, tmp_path):
        _make_state(tmp_path)
        _make_design_system(tmp_path)
        r = _run("Edit", "src/app.css", "color: #fff;", str(tmp_path), tool_type="Edit")
        assert r.returncode == 0
        assert r.stdout.strip() != ""


class TestFileTypeFiltering:
    def test_python_file_skipped(self, tmp_path):
        _make_state(tmp_path)
        _make_design_system(tmp_path)
        r = _run("Write", "scripts/foo.py", "color: #fff;", str(tmp_path))
        assert r.returncode == 0
        assert r.stdout.strip() == ""

    def test_markdown_file_skipped(self, tmp_path):
        _make_state(tmp_path)
        _make_design_system(tmp_path)
        r = _run("Write", "README.md", "color: #fff;", str(tmp_path))
        assert r.returncode == 0
        assert r.stdout.strip() == ""

    def test_tsx_file_scanned(self, tmp_path):
        _make_state(tmp_path)
        _make_design_system(tmp_path)
        r = _run("Write", "src/Button.tsx", "color: #fff;", str(tmp_path))
        assert r.stdout.strip() != ""

    def test_css_file_scanned(self, tmp_path):
        _make_state(tmp_path)
        _make_design_system(tmp_path)
        r = _run("Write", "styles/main.css", "color: #abc123;", str(tmp_path))
        assert r.stdout.strip() != ""

    def test_scss_file_scanned(self, tmp_path):
        _make_state(tmp_path)
        _make_design_system(tmp_path)
        r = _run("Write", "styles/main.scss", "!important", str(tmp_path))
        assert r.stdout.strip() != ""

    def test_vue_file_scanned(self, tmp_path):
        _make_state(tmp_path)
        _make_design_system(tmp_path)
        r = _run("Write", "components/App.vue", "color: #fff;", str(tmp_path))
        assert r.stdout.strip() != ""


class TestStageGate:
    def test_stage_5_no_enforcement(self, tmp_path):
        _make_state(tmp_path, stage=5)
        _make_design_system(tmp_path)
        r = _run("Write", "src/app.tsx", "color: #fff;", str(tmp_path))
        assert r.stdout.strip() == ""

    def test_stage_6_enforced(self, tmp_path):
        _make_state(tmp_path, stage=6)
        _make_design_system(tmp_path)
        r = _run("Write", "src/app.tsx", "color: #fff;", str(tmp_path))
        assert r.stdout.strip() != ""

    def test_stage_10_enforced(self, tmp_path):
        _make_state(tmp_path, stage=10)
        _make_design_system(tmp_path)
        r = _run("Write", "src/app.tsx", "color: #fff;", str(tmp_path))
        assert r.stdout.strip() != ""


class TestDesignSystemGate:
    def test_no_design_system_no_enforcement(self, tmp_path):
        _make_state(tmp_path, stage=6)
        # design-system.md NOT created
        r = _run("Write", "src/app.tsx", "color: #fff;", str(tmp_path))
        assert r.stdout.strip() == ""

    def test_with_design_system_enforced(self, tmp_path):
        _make_state(tmp_path, stage=6)
        _make_design_system(tmp_path)
        r = _run("Write", "src/app.tsx", "color: #fff;", str(tmp_path))
        assert r.stdout.strip() != ""


class TestViolationDetection:
    def _violations(self, tmp_path, content: str, ext: str = ".css") -> str:
        _make_state(tmp_path, stage=6)
        _make_design_system(tmp_path)
        r = _run("Write", f"src/styles{ext}", content, str(tmp_path))
        return r.stdout

    def test_hex_color_3char_flagged(self, tmp_path):
        out = self._violations(tmp_path, "color: #fff;")
        assert "#fff" in out or "hex" in out.lower()

    def test_hex_color_6char_flagged(self, tmp_path):
        out = self._violations(tmp_path, "background-color: #1a2b3c;")
        assert "#1a2b3c" in out or "hex" in out.lower()

    def test_hex_color_in_var_not_flagged(self, tmp_path):
        out = self._violations(tmp_path, "color: var(--color-primary-500);")
        assert out.strip() == ""

    def test_raw_px_off_scale_flagged(self, tmp_path):
        out = self._violations(tmp_path, "padding: 17px;")
        assert "17px" in out

    def test_raw_px_on_scale_not_flagged(self, tmp_path):
        out = self._violations(tmp_path, "padding: 16px;")
        assert out.strip() == ""

    def test_raw_px_zero_not_flagged(self, tmp_path):
        out = self._violations(tmp_path, "margin: 0px;")
        assert out.strip() == ""

    def test_font_family_raw_flagged(self, tmp_path):
        out = self._violations(tmp_path, "font-family: Arial, sans-serif;")
        assert "font-family" in out

    def test_font_family_var_not_flagged(self, tmp_path):
        out = self._violations(tmp_path, "font-family: var(--font-sans);")
        assert out.strip() == ""

    def test_z_index_raw_flagged(self, tmp_path):
        out = self._violations(tmp_path, "z-index: 100;")
        assert "z-index" in out

    def test_z_index_var_not_flagged(self, tmp_path):
        out = self._violations(tmp_path, "z-index: var(--z-modal);")
        assert out.strip() == ""

    def test_important_flagged(self, tmp_path):
        out = self._violations(tmp_path, "color: red !important;")
        assert "important" in out

    def test_comment_line_skipped(self, tmp_path):
        out = self._violations(tmp_path, "// color: #fff; use var(--color-primary)")
        assert out.strip() == ""

    def test_clean_content_no_output(self, tmp_path):
        out = self._violations(tmp_path, "color: var(--color-primary);\npadding: 16px;")
        assert out.strip() == ""


class TestOutputFormat:
    def test_output_is_valid_json(self, tmp_path):
        _make_state(tmp_path, stage=6)
        _make_design_system(tmp_path)
        r = _run("Write", "src/app.tsx", "color: #fff;", str(tmp_path))
        data = json.loads(r.stdout)
        assert "hookSpecificOutput" in data
        assert "additionalContext" in data["hookSpecificOutput"]

    def test_output_mentions_filename(self, tmp_path):
        _make_state(tmp_path, stage=6)
        _make_design_system(tmp_path)
        r = _run("Write", "src/Button.tsx", "color: #fff;", str(tmp_path))
        data = json.loads(r.stdout)
        assert "Button.tsx" in data["hookSpecificOutput"]["additionalContext"]

    def test_violations_capped_at_10(self, tmp_path):
        _make_state(tmp_path, stage=6)
        _make_design_system(tmp_path)
        # 15 unique off-scale px values
        lines = [f"padding: {v}px;" for v in range(3, 60, 4)]  # 3,7,11,... all off-scale
        content = "\n".join(lines[:15])
        r = _run("Write", "src/app.css", content, str(tmp_path))
        data = json.loads(r.stdout)
        ctx = data["hookSpecificOutput"]["additionalContext"]
        assert "more violation" in ctx

    def test_never_exits_nonzero(self, tmp_path):
        _make_state(tmp_path, stage=6)
        _make_design_system(tmp_path)
        r = _run("Write", "src/app.tsx", "color: #fff; !important", str(tmp_path))
        assert r.returncode == 0


class TestEdgeCases:
    def test_empty_stdin_exits_0(self):
        r = subprocess.run(
            [PYTHON, HOOK], input="", capture_output=True, text=True
        )
        assert r.returncode == 0

    def test_empty_content_no_output(self, tmp_path):
        _make_state(tmp_path, stage=6)
        _make_design_system(tmp_path)
        r = _run("Write", "src/app.tsx", "", str(tmp_path))
        assert r.stdout.strip() == ""

    def test_no_pipeline_exits_0(self, tmp_path):
        r = _run("Write", "src/app.tsx", "color: #fff;", str(tmp_path))
        assert r.returncode == 0
