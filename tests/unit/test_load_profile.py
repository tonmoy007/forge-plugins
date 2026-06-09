"""Tests for scripts/load-profile.py — project profile loader."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT = _ROOT / "scripts" / "load-profile.py"
_PROFILES = _ROOT / "references" / "project-type-profiles.md"
_PYTHON = sys.executable


# Hyphenated filename → importlib (per tasks/lessons.md).
def _load_module():
    spec = importlib.util.spec_from_file_location("load_profile", str(_SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    # @dataclass-safe pre-registration (per lesson 351); this script doesn't use
    # dataclasses but the pattern is safe regardless.
    sys.modules["load_profile"] = mod
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()


def _make_state(tmp_path: Path, project_type: str) -> None:
    (tmp_path / "pipeline").mkdir(parents=True, exist_ok=True)
    (tmp_path / "pipeline" / "state.md").write_text(
        f"---\n"
        f"schema_version: 1\n"
        f"project_type: {project_type}\n"
        f"cycle: 1\n"
        f"current_stage: 0\n"
        f"current_task: null\n"
        f"current_milestone: null\n"
        f"total_tasks: null\n"
        f'last_updated: "2026-05-12T10:00:00Z"\n'
        f"blockers: []\n"
        f"---\n\n# Pipeline State\n"
    )


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_PYTHON, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Module-level API
# ---------------------------------------------------------------------------

class TestLoadProfileAPI:
    def test_no_state_returns_none_none(self, tmp_path):
        name, profile = _mod.load_profile(tmp_path)
        assert name is None
        assert profile is None

    def test_unknown_project_type_returns_name_no_profile(self, tmp_path):
        _make_state(tmp_path, "nonexistent-type")
        name, profile = _mod.load_profile(tmp_path)
        assert name == "nonexistent-type"
        assert profile is None

    def test_ml_pipeline_loads_profile(self, tmp_path):
        _make_state(tmp_path, "ml-pipeline")
        name, profile = _mod.load_profile(tmp_path)
        assert name == "ml-pipeline"
        assert isinstance(profile, dict)
        assert profile["name"] == "ml-pipeline"

    def test_extract_profile_returns_none_for_missing(self):
        text = "## Profile: api\n```yaml\nname: api\n```\n"
        assert _mod._extract_profile(text, "library") is None

    def test_extract_profile_handles_malformed_yaml(self):
        text = "## Profile: api\n```yaml\n: : :\n  invalid yaml\n```\n"
        # Either returns None or a non-dict — both are non-crashes
        result = _mod._extract_profile(text, "api")
        assert result is None or isinstance(result, dict)


# ---------------------------------------------------------------------------
# Stage-block extraction
# ---------------------------------------------------------------------------

class TestStageBlock:
    def test_ml_stage_7_has_criteria(self, tmp_path):
        _make_state(tmp_path, "ml-pipeline")
        _, profile = _mod.load_profile(tmp_path, stage=7)
        block = _mod._stage_block(profile, 7)
        assert block is not None
        crits = block.get("additional_criteria") or []
        ids = [c.get("id") for c in crits]
        assert "G7-ML-001" in ids
        assert "G7-ML-005" in ids  # the drift criterion

    def test_ml_stage_with_no_overrides_returns_none(self, tmp_path):
        _make_state(tmp_path, "ml-pipeline")
        _, profile = _mod.load_profile(tmp_path)
        assert _mod._stage_block(profile, 1) is None  # no stage_1 overrides
        assert _mod._stage_block(profile, 5) is None  # no stage_5 overrides

    def test_fullstack_stage_3_present(self, tmp_path):
        _make_state(tmp_path, "fullstack")
        _, profile = _mod.load_profile(tmp_path)
        block = _mod._stage_block(profile, 3)
        assert block is not None
        assert "additional_concerns" in block


# ---------------------------------------------------------------------------
# CLI: markdown output
# ---------------------------------------------------------------------------

class TestCLIMarkdown:
    def test_done_when_ml_stage_7_includes_drift(self, tmp_path):
        """T-025 done-when: /forge:eval on ML project must surface drift."""
        _make_state(tmp_path, "ml-pipeline")
        r = _run("--cwd", str(tmp_path), "--stage", "7")
        assert r.returncode == 0
        assert "G7-ML-005" in r.stdout
        assert "drift" in r.stdout.lower()

    def test_markdown_shows_profile_header(self, tmp_path):
        _make_state(tmp_path, "ml-pipeline")
        r = _run("--cwd", str(tmp_path), "--stage", "7")
        assert "## Project profile: ml-pipeline" in r.stdout

    def test_markdown_shows_stage_emphasis(self, tmp_path):
        _make_state(tmp_path, "ml-pipeline")
        r = _run("--cwd", str(tmp_path), "--stage", "7")
        assert "Stage emphasis" in r.stdout
        # ml-pipeline marks product-ux as low
        assert "product-ux" in r.stdout

    def test_no_state_silent_exit_0(self, tmp_path):
        r = _run("--cwd", str(tmp_path), "--stage", "7")
        assert r.returncode == 0
        assert r.stdout.strip() == ""

    def test_unknown_type_shows_fallback_message(self, tmp_path):
        _make_state(tmp_path, "weird-thing")
        r = _run("--cwd", str(tmp_path), "--stage", "7")
        assert r.returncode == 0
        assert "weird-thing" in r.stdout
        assert "profile not found" in r.stdout.lower()

    def test_stage_with_no_overrides_says_so(self, tmp_path):
        _make_state(tmp_path, "ml-pipeline")
        r = _run("--cwd", str(tmp_path), "--stage", "1")
        assert "no overrides for stage 1" in r.stdout.lower()

    def test_no_stage_arg_shows_emphasis_only(self, tmp_path):
        _make_state(tmp_path, "ml-pipeline")
        r = _run("--cwd", str(tmp_path))
        assert "Stage emphasis" in r.stdout
        assert "Overrides for stage" not in r.stdout


# ---------------------------------------------------------------------------
# CLI: JSON output
# ---------------------------------------------------------------------------

class TestCLIJson:
    def test_json_structure(self, tmp_path):
        _make_state(tmp_path, "ml-pipeline")
        r = _run("--cwd", str(tmp_path), "--stage", "7", "--format", "json")
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["project_type"] == "ml-pipeline"
        assert data["stage"] == 7
        assert data["profile"]["name"] == "ml-pipeline"
        assert data["stage_overrides"] is not None
        ids = [c["id"] for c in data["stage_overrides"]["additional_criteria"]]
        assert "G7-ML-005" in ids

    def test_json_no_state(self, tmp_path):
        r = _run("--cwd", str(tmp_path), "--format", "json")
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["project_type"] is None
        assert data["profile"] is None

    def test_json_unknown_type(self, tmp_path):
        _make_state(tmp_path, "weird")
        r = _run("--cwd", str(tmp_path), "--stage", "7", "--format", "json")
        data = json.loads(r.stdout)
        assert data["project_type"] == "weird"
        assert data["profile"] is None
        assert data["stage_overrides"] is None


# ---------------------------------------------------------------------------
# Custom profiles file
# ---------------------------------------------------------------------------

class TestCustomProfiles:
    def test_custom_profiles_file(self, tmp_path):
        _make_state(tmp_path, "tinytype")
        custom = tmp_path / "custom-profiles.md"
        custom.write_text(
            "# Custom\n\n"
            "## Profile: tinytype\n\n"
            "```yaml\n"
            "name: tinytype\n"
            "description: A test type\n"
            "stage_overrides:\n"
            "  stage_4:\n"
            "    additional_artifacts:\n"
            "      - 'pipeline/04-spec/tiny.md'\n"
            "```\n"
        )
        r = _run("--cwd", str(tmp_path), "--stage", "4", "--profiles-file", str(custom))
        assert r.returncode == 0
        assert "tinytype" in r.stdout
        assert "pipeline/04-spec/tiny.md" in r.stdout


# ---------------------------------------------------------------------------
# All five required profiles parse
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ptype", [
    "api", "fullstack", "ml-pipeline", "cli", "library",
    "monorepo", "mobile", "data-contract",   # v0.1.7
])
def test_all_standard_profiles_parse(tmp_path, ptype):
    _make_state(tmp_path, ptype)
    name, profile = _mod.load_profile(tmp_path)
    assert name == ptype
    assert profile is not None
    assert profile.get("name") == ptype
    overrides = profile.get("stage_overrides") or {}
    stage_keys = [k for k in overrides if k.startswith("stage_")]
    # T-024 invariant: every required profile has ≥3 stage overrides
    assert len(stage_keys) >= 3, f"{ptype} has only {len(stage_keys)} stage overrides"
