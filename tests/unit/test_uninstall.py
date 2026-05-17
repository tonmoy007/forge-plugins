"""Tests for scripts/uninstall.py.

Run with: python -m pytest tests/unit/test_uninstall.py -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import uninstall  # noqa: E402


# ---------- discovery ----------

class TestDiscoverTargets:
    def test_empty_project_no_targets(self, tmp_path):
        targets = uninstall.discover_targets(
            tmp_path, keep_artifacts=False, include_global=False,
        )
        assert targets == []

    def test_runtime_only(self, tmp_path):
        (tmp_path / ".forge").mkdir()
        (tmp_path / ".forge" / "sessions").mkdir()
        (tmp_path / ".forge" / "sessions" / "s1.json").write_text("{}")
        targets = uninstall.discover_targets(
            tmp_path, keep_artifacts=False, include_global=False,
        )
        assert len(targets) == 1
        assert Path(targets[0].path) == tmp_path / ".forge"
        assert targets[0].file_count == 1

    def test_runtime_and_pipeline(self, tmp_path):
        (tmp_path / ".forge").mkdir()
        (tmp_path / ".forge" / "lessons.yaml").write_text("- id: L1")
        (tmp_path / "pipeline").mkdir()
        (tmp_path / "pipeline" / "state.md").write_text("stage: 1")
        targets = uninstall.discover_targets(
            tmp_path, keep_artifacts=False, include_global=False,
        )
        assert len(targets) == 2
        paths = {Path(t.path) for t in targets}
        assert paths == {tmp_path / ".forge", tmp_path / "pipeline"}

    def test_keep_artifacts_excludes_pipeline(self, tmp_path):
        (tmp_path / ".forge").mkdir()
        (tmp_path / "pipeline").mkdir()
        targets = uninstall.discover_targets(
            tmp_path, keep_artifacts=True, include_global=False,
        )
        assert len(targets) == 1
        assert Path(targets[0].path) == tmp_path / ".forge"

    def test_size_and_count_aggregated(self, tmp_path):
        (tmp_path / ".forge").mkdir()
        (tmp_path / ".forge" / "a.txt").write_text("hello")  # 5 bytes
        (tmp_path / ".forge" / "b.txt").write_text("world!")  # 6 bytes
        targets = uninstall.discover_targets(
            tmp_path, keep_artifacts=False, include_global=False,
        )
        assert targets[0].file_count == 2
        assert targets[0].size_bytes == 11


# ---------- size formatting ----------

class TestFormatSize:
    def test_bytes(self):
        assert uninstall.format_size(500) == "500 B"

    def test_kb(self):
        assert "KB" in uninstall.format_size(2048)

    def test_mb(self):
        assert "MB" in uninstall.format_size(5 * 1024 * 1024)

    def test_gb(self):
        assert "GB" in uninstall.format_size(3 * 1024 ** 3)


# ---------- removal ----------

class TestRemoveTargets:
    def test_remove_existing(self, tmp_path):
        d = tmp_path / "target"
        d.mkdir()
        (d / "file.txt").write_text("hello")
        t = uninstall.Target(
            path=str(d), kind="dir", size_bytes=5, file_count=1, label="test",
        )
        removals = uninstall.remove_targets([t], dry_run=False)
        assert removals[0].status == "removed"
        assert not d.exists()

    def test_dry_run_preserves(self, tmp_path):
        d = tmp_path / "target"
        d.mkdir()
        t = uninstall.Target(
            path=str(d), kind="dir", size_bytes=0, file_count=0, label="test",
        )
        removals = uninstall.remove_targets([t], dry_run=True)
        assert removals[0].status == "skipped"
        assert d.exists()

    def test_already_gone_is_skipped_not_error(self, tmp_path):
        # Idempotency: target listed but already removed
        t = uninstall.Target(
            path=str(tmp_path / "ghost"), kind="dir",
            size_bytes=0, file_count=0, label="test",
        )
        removals = uninstall.remove_targets([t], dry_run=False)
        assert removals[0].status == "skipped"
        assert "not present" in removals[0].detail


# ---------- CLI ----------

class TestCLI:
    def test_empty_project_exits_clean(self, tmp_path, capsys):
        rc = uninstall.main(["--cwd", str(tmp_path), "--yes"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Nothing to remove" in out

    def test_dry_run_does_not_remove(self, tmp_path):
        (tmp_path / ".forge").mkdir()
        (tmp_path / ".forge" / "x.txt").write_text("y")
        rc = uninstall.main(["--cwd", str(tmp_path), "--dry-run", "--yes"])
        assert rc == 0
        assert (tmp_path / ".forge").exists()
        assert (tmp_path / ".forge" / "x.txt").exists()

    def test_yes_removes_without_prompt(self, tmp_path):
        (tmp_path / ".forge").mkdir()
        (tmp_path / "pipeline").mkdir()
        (tmp_path / "pipeline" / "srs.md").write_text("# SRS")
        rc = uninstall.main(["--cwd", str(tmp_path), "--yes"])
        assert rc == 0
        assert not (tmp_path / ".forge").exists()
        assert not (tmp_path / "pipeline").exists()

    def test_keep_artifacts_preserves_pipeline(self, tmp_path):
        (tmp_path / ".forge").mkdir()
        (tmp_path / "pipeline").mkdir()
        (tmp_path / "pipeline" / "srs.md").write_text("# SRS")
        rc = uninstall.main(["--cwd", str(tmp_path), "--yes", "--keep-artifacts"])
        assert rc == 0
        assert not (tmp_path / ".forge").exists()
        assert (tmp_path / "pipeline").exists()
        assert (tmp_path / "pipeline" / "srs.md").exists()

    def test_idempotent_repeat(self, tmp_path):
        (tmp_path / ".forge").mkdir()
        rc1 = uninstall.main(["--cwd", str(tmp_path), "--yes"])
        rc2 = uninstall.main(["--cwd", str(tmp_path), "--yes"])
        assert rc1 == 0 and rc2 == 0

    def test_json_output_well_formed(self, tmp_path, capsys):
        (tmp_path / ".forge").mkdir()
        uninstall.main(["--cwd", str(tmp_path), "--yes", "--json"])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "targets" in data
        assert "removals" in data
        assert data["removals"][0]["status"] == "removed"
        assert "plugin_unregister_hint" in data
        assert "reinstall_hint" in data

    def test_json_dry_run_well_formed(self, tmp_path, capsys):
        (tmp_path / ".forge").mkdir()
        uninstall.main(["--cwd", str(tmp_path), "--dry-run", "--json"])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["dry_run"] is True
        assert data["removals"] == []

    def test_plan_output_mentions_reinstall(self, tmp_path, capsys):
        (tmp_path / ".forge").mkdir()
        uninstall.main(["--cwd", str(tmp_path), "--yes"])
        out = capsys.readouterr().out
        assert "/plugin uninstall" in out
        assert "/plugin install" in out

    def test_cancel_via_empty_input(self, tmp_path, capsys, monkeypatch):
        (tmp_path / ".forge").mkdir()
        # Simulate user pressing enter at the prompt (declines)
        monkeypatch.setattr("builtins.input", lambda _: "")
        rc = uninstall.main(["--cwd", str(tmp_path)])
        assert rc == 0
        assert (tmp_path / ".forge").exists()
        out = capsys.readouterr().out
        assert "Cancelled" in out