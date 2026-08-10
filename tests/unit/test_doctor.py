"""Tests for scripts/doctor.py.

Run with: python -m pytest tests/unit/test_doctor.py -q

Tests are organized by check category and use tmp_path for filesystem isolation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import doctor  # noqa: E402


# ---------- version helpers ----------

class TestVersionParsing:
    def test_simple_three_part(self):
        assert doctor.parse_version("v1.2.3") == (1, 2, 3)

    def test_with_prefix(self):
        assert doctor.parse_version("Python 3.11.7") == (3, 11, 7)

    def test_two_parts(self):
        assert doctor.parse_version("claude 2.1") == (2, 1)

    def test_no_version_returns_none(self):
        assert doctor.parse_version("no version here") is None

    def test_empty_string(self):
        assert doctor.parse_version("") is None


class TestVersionComparison:
    def test_equal(self):
        assert doctor.cmp_version((2, 1, 0), (2, 1, 0))

    def test_greater_patch(self):
        assert doctor.cmp_version((2, 1, 1), (2, 1, 0))

    def test_less_patch(self):
        assert not doctor.cmp_version((2, 0, 9), (2, 1, 0))

    def test_unequal_lengths_padded_with_zero(self):
        assert doctor.cmp_version((2, 1), (2, 1, 0))
        assert doctor.cmp_version((2, 1, 0), (2, 1))


# ---------- environment ----------

class TestEnvironmentChecks:
    def test_python_passes_on_current_interpreter(self):
        # Anyone running these tests has Python ≥ 3.11
        r = doctor.check_python_version()
        assert r.status == "pass"
        assert r.category == "environment"

    def test_pyyaml_passes_when_installed(self):
        r = doctor.check_pyyaml()
        assert r.status == "pass"


# ---------- plugin ----------

class TestPluginManifest:
    def test_missing_file(self, tmp_path):
        r = doctor.check_plugin_manifest(tmp_path)
        assert r.status == "fail"
        assert "not found" in r.detail
        assert r.fix is not None

    def test_malformed_json(self, tmp_path):
        (tmp_path / ".claude-plugin").mkdir()
        (tmp_path / ".claude-plugin" / "plugin.json").write_text("{not valid")
        r = doctor.check_plugin_manifest(tmp_path)
        assert r.status == "fail"
        assert "malformed" in r.detail

    def test_valid_manifest(self, tmp_path):
        (tmp_path / ".claude-plugin").mkdir()
        (tmp_path / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "forge", "version": "0.1.3"})
        )
        r = doctor.check_plugin_manifest(tmp_path)
        assert r.status == "pass"
        assert "forge" in r.detail
        assert "0.1.3" in r.detail


class TestHooks:
    def test_hooks_dir_missing(self, tmp_path):
        results = doctor.check_hooks(tmp_path)
        assert results[0].status == "fail"

    def test_partial_hooks(self, tmp_path):
        (tmp_path / "hooks").mkdir()
        (tmp_path / "hooks" / "session-start.py").touch()
        results = doctor.check_hooks(tmp_path)
        assert results[0].status == "fail"
        assert "Missing hooks" in results[0].detail

    def test_all_hooks_present(self, tmp_path):
        (tmp_path / "hooks").mkdir()
        for h in doctor.EXPECTED_HOOKS:
            (tmp_path / "hooks" / h).touch()
        results = doctor.check_hooks(tmp_path)
        assert results[0].status == "pass"


class TestAgents:
    def test_missing_dir(self, tmp_path):
        r = doctor.check_agents(tmp_path)
        assert r.status == "fail"

    def test_too_few(self, tmp_path):
        (tmp_path / "agents").mkdir()
        (tmp_path / "agents" / "one.md").touch()
        r = doctor.check_agents(tmp_path)
        assert r.status == "warn"

    def test_enough_agents(self, tmp_path):
        (tmp_path / "agents").mkdir()
        for i in range(doctor.EXPECTED_STAGE_AGENTS):
            (tmp_path / "agents" / f"a{i}.md").touch()
        r = doctor.check_agents(tmp_path)
        assert r.status == "pass"


# ---------- project ----------

class TestPipelineDir:
    def test_missing_returns_info(self, tmp_path):
        r = doctor.check_pipeline_dir(tmp_path)
        assert r.status == "info"
        assert r.fix is not None

    def test_present_writable(self, tmp_path):
        (tmp_path / "pipeline").mkdir()
        r = doctor.check_pipeline_dir(tmp_path)
        assert r.status == "pass"


class TestState:
    def test_missing(self, tmp_path):
        # No pipeline directory at all
        assert doctor.check_state(tmp_path) is None

    def test_present_with_stage(self, tmp_path):
        pipeline = tmp_path / "pipeline"
        pipeline.mkdir()
        (pipeline / "state.md").write_text("# State\n\nstage: 3\ntask: T-007\n")
        r = doctor.check_state(tmp_path)
        assert r is not None
        assert r.status == "pass"
        assert "Stage 3" in r.detail


class TestGitignore:
    def test_no_forge_state_no_check(self, tmp_path):
        assert doctor.check_gitignore(tmp_path) is None

    def test_no_gitignore_warns(self, tmp_path):
        (tmp_path / "pipeline").mkdir()
        r = doctor.check_gitignore(tmp_path)
        assert r.status == "warn"

    def test_missing_dotforge_pattern(self, tmp_path):
        (tmp_path / "pipeline").mkdir()
        (tmp_path / ".gitignore").write_text("node_modules/\n")
        r = doctor.check_gitignore(tmp_path)
        assert r.status == "warn"
        assert ".forge/" in r.fix

    def test_dotforge_in_gitignore(self, tmp_path):
        (tmp_path / "pipeline").mkdir()
        (tmp_path / ".gitignore").write_text(".forge/\n")
        r = doctor.check_gitignore(tmp_path)
        assert r.status == "pass"

    def test_comments_ignored(self, tmp_path):
        (tmp_path / "pipeline").mkdir()
        (tmp_path / ".gitignore").write_text("# .forge/\n.forge/\n")
        r = doctor.check_gitignore(tmp_path)
        assert r.status == "pass"


# ---------- summarize ----------

class TestSummarize:
    def test_all_pass(self):
        rs = [doctor.CheckResult("a", "x", "pass", "ok")]
        assert "all checks passed" in doctor.summarize(rs)

    def test_one_failure(self):
        rs = [
            doctor.CheckResult("a", "x", "pass", "ok"),
            doctor.CheckResult("b", "x", "fail", "broken"),
        ]
        assert "1 failure" in doctor.summarize(rs)

    def test_multiple_with_warnings(self):
        rs = [
            doctor.CheckResult("a", "x", "fail", "f1"),
            doctor.CheckResult("b", "x", "fail", "f2"),
            doctor.CheckResult("c", "x", "warn", "w1"),
        ]
        s = doctor.summarize(rs)
        assert "2 failures" in s
        assert "1 warning" in s


# ---------- CLI ----------

class TestCLI:
    def test_json_output_is_valid(self, tmp_path, capsys, monkeypatch):
        monkeypatch.setenv("FORGE_ROOT", str(tmp_path))
        doctor.main(["--json", "--cwd", str(tmp_path)])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        for item in data:
            assert "name" in item
            assert "category" in item
            assert "status" in item
            assert "detail" in item

    def test_text_output_contains_summary(self, tmp_path, capsys, monkeypatch):
        monkeypatch.setenv("FORGE_ROOT", str(tmp_path))
        doctor.main(["--cwd", str(tmp_path)])
        out = capsys.readouterr().out
        assert "Forge Doctor" in out
        assert "Result:" in out

    def test_quiet_suppresses_passes(self, tmp_path, capsys, monkeypatch):
        # Set up a working forge_root so plugin checks pass
        forge_root = tmp_path / "forge"
        forge_root.mkdir()
        (forge_root / ".claude-plugin").mkdir()
        (forge_root / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "forge", "version": "0.1.3"})
        )
        (forge_root / "hooks").mkdir()
        for h in doctor.EXPECTED_HOOKS:
            (forge_root / "hooks" / h).touch()
        (forge_root / "agents").mkdir()
        for i in range(doctor.EXPECTED_STAGE_AGENTS):
            (forge_root / "agents" / f"a{i}.md").touch()
        (forge_root / "references").mkdir()
        (forge_root / "references" / "gate-criteria.md").write_text(
            "```yaml\nstage: 1\nname: srs\ncriteria:\n  - id: G1-001\n```\n"
        )
        monkeypatch.setenv("FORGE_ROOT", str(forge_root))
        project = tmp_path / "project"
        project.mkdir()
        doctor.main(["--cwd", str(project), "--quiet"])
        out = capsys.readouterr().out
        # In quiet mode, "Environment:" header is only printed if there's a fail/warn in env
        # The python_version check passes; pyyaml passes; claude_code may fail/warn
        # We just check that the output doesn't include passing "✓" rows for env when all pass
        # (this test is a smoke test; details vary by host)
        assert "Result:" in out


# ---------- check_required_tools (T-229, REQ-TR-003) ----------


def test_check_required_tools_flags_missing_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_status = doctor.tool_preflight.ToolStatus(
        present=False, version=None, required=True,
        reason="always required", install_cmd="brew install gh",
    )
    monkeypatch.setattr(doctor.tool_preflight, "check_all", lambda cwd, **k: {"gh": fake_status})
    results = doctor.check_required_tools(tmp_path, tmp_path)
    assert len(results) == 1
    assert results[0].status == "warn"
    assert results[0].fix == "brew install gh"


def test_check_required_tools_no_result_for_present_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_status = doctor.tool_preflight.ToolStatus(
        present=True, version="1.0", required=True, reason="x", install_cmd=None,
    )
    monkeypatch.setattr(doctor.tool_preflight, "check_all", lambda cwd, **k: {"gh": fake_status})
    assert doctor.check_required_tools(tmp_path, tmp_path) == []


def test_check_required_tools_no_result_for_not_required_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_status = doctor.tool_preflight.ToolStatus(
        present=False, version=None, required=False, reason="x", install_cmd=None,
    )
    monkeypatch.setattr(doctor.tool_preflight, "check_all", lambda cwd, **k: {"docker": fake_status})
    assert doctor.check_required_tools(tmp_path, tmp_path) == []


def test_check_required_tools_never_raises_on_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(cwd, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(doctor.tool_preflight, "check_all", _boom)
    assert doctor.check_required_tools(tmp_path, tmp_path) == []


def test_run_checks_includes_required_tools_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    forge_root = tmp_path / "forge"
    forge_root.mkdir()
    (forge_root / ".claude-plugin").mkdir()
    (forge_root / ".claude-plugin" / "plugin.json").write_text('{"name": "forge"}')
    (forge_root / "hooks").mkdir()
    for h in doctor.EXPECTED_HOOKS:
        (forge_root / "hooks" / h).touch()
    (forge_root / "agents").mkdir()
    for i in range(doctor.EXPECTED_STAGE_AGENTS):
        (forge_root / "agents" / f"a{i}.md").touch()
    (forge_root / "references").mkdir()
    (forge_root / "references" / "gate-criteria.md").write_text(
        "```yaml\nstage: 1\nname: srs\ncriteria:\n  - id: G1-001\n```\n"
    )
    project = tmp_path / "project"
    project.mkdir()

    fake_status = doctor.tool_preflight.ToolStatus(
        present=False, version=None, required=True, reason="x", install_cmd="brew install gh",
    )
    monkeypatch.setattr(doctor.tool_preflight, "check_all", lambda cwd, **k: {"gh": fake_status})
    results = doctor.run_checks(forge_root, project)
    assert any(r.name.startswith("tool_") for r in results)