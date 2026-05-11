"""Unit tests for scripts/context-pruner.py."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import importlib.util

import pytest

# context-pruner.py uses a hyphenated filename — import via importlib
_SCRIPT_PATH = Path(__file__).parent.parent.parent / "scripts" / "context-pruner.py"
_spec = importlib.util.spec_from_file_location("context_pruner", _SCRIPT_PATH)
cp = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(cp)  # type: ignore[union-attr]

SCRIPT = str(Path(__file__).parent.parent.parent / "scripts" / "context-pruner.py")
PYTHON = sys.executable


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(stage: int, cwd: str, budget: int | None = None) -> subprocess.CompletedProcess:
    cmd = [PYTHON, SCRIPT, "--stage", str(stage), "--cwd", cwd]
    if budget is not None:
        cmd += ["--budget", str(budget)]
    return subprocess.run(cmd, capture_output=True, text=True)


def _scaffold(tmp_path: Path, stage: int = 6) -> Path:
    """Create a minimal Forge project with state.md at the given stage."""
    (tmp_path / "pipeline").mkdir()
    (tmp_path / "pipeline" / "state.md").write_text(
        "---\ncurrent_stage: {}\n---\n# Pipeline State\n".format(stage)
    )
    (tmp_path / "tasks").mkdir()
    return tmp_path


def _write(tmp_path: Path, rel: str, content: str) -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


# ---------------------------------------------------------------------------
# token_estimate
# ---------------------------------------------------------------------------

class TestTokenEstimate:
    def test_empty_string(self):
        assert cp.token_estimate("") == 1  # max(1, 0)

    def test_four_chars_is_one_token(self):
        assert cp.token_estimate("abcd") == 1

    def test_hundred_chars(self):
        assert cp.token_estimate("x" * 100) == 25

    def test_returns_int(self):
        assert isinstance(cp.token_estimate("hello"), int)


# ---------------------------------------------------------------------------
# extract_section
# ---------------------------------------------------------------------------

class TestExtractSection:
    def test_extracts_matching_section(self):
        text = "# Intro\nsome text\n## Stage 1\nstage content\n## Stage 2\nother\n"
        result = cp.extract_section(text, "Stage 1")
        assert result is not None
        assert "stage content" in result
        assert "other" not in result

    def test_case_insensitive(self):
        text = "## STAGE 6\ncontent here\n"
        result = cp.extract_section(text, "stage 6")
        assert result is not None
        assert "content here" in result

    def test_partial_match(self):
        text = "## Stage 1 — SRS\nreqs here\n"
        result = cp.extract_section(text, "Stage 1")
        assert result is not None
        assert "reqs here" in result

    def test_no_match_returns_none(self):
        text = "## Section A\nfoo\n## Section B\nbar\n"
        assert cp.extract_section(text, "Stage 99") is None

    def test_empty_text(self):
        assert cp.extract_section("", "Stage 1") is None

    def test_stops_at_next_heading(self):
        text = "## Stage 1\npart1\n## Stage 2\npart2\n"
        result = cp.extract_section(text, "Stage 1")
        assert "part1" in result
        assert "part2" not in result


# ---------------------------------------------------------------------------
# read_artifact
# ---------------------------------------------------------------------------

class TestReadArtifact:
    def test_missing_file_returns_none(self, tmp_path):
        spec = {"path": "pipeline/nonexistent.md", "priority": 1}
        assert cp.read_artifact(tmp_path, spec) is None

    def test_reads_existing_file(self, tmp_path):
        _write(tmp_path, "pipeline/state.md", "hello world")
        spec = {"path": "pipeline/state.md", "priority": 1}
        result = cp.read_artifact(tmp_path, spec)
        assert result is not None
        assert "hello world" in result["content"]
        assert result["priority"] == 1
        assert result["path"] == "pipeline/state.md"

    def test_max_tokens_truncates(self, tmp_path):
        _write(tmp_path, "pipeline/state.md", "x" * 2000)
        spec = {"path": "pipeline/state.md", "priority": 1, "max_tokens": 10}
        result = cp.read_artifact(tmp_path, spec)
        assert result is not None
        # "\n... [truncated]" is 16 chars ≈ 4 tokens of overhead on top of max_tokens
        assert result["tokens"] <= spec["max_tokens"] + 5
        assert "[truncated]" in result["content"]

    def test_section_extracts_matching_part(self, tmp_path):
        _write(tmp_path, "references/gate-criteria.md",
               "## Stage 1\nSRS criteria here\n## Stage 2\nProduct criteria\n")
        spec = {
            "path": "references/gate-criteria.md",
            "priority": 3,
            "section": "Stage 1",
        }
        result = cp.read_artifact(tmp_path, spec)
        assert result is not None
        assert "SRS criteria" in result["content"]
        assert "Product criteria" not in result["content"]

    def test_section_miss_returns_full_content(self, tmp_path):
        _write(tmp_path, "pipeline/state.md", "full content here")
        spec = {"path": "pipeline/state.md", "priority": 1, "section": "Nonexistent"}
        result = cp.read_artifact(tmp_path, spec)
        assert result is not None
        assert "full content here" in result["content"]


# ---------------------------------------------------------------------------
# select_artifacts / prune
# ---------------------------------------------------------------------------

class TestSelectArtifacts:
    def test_respects_budget(self, tmp_path):
        _write(tmp_path, "pipeline/state.md", "x" * 4000)
        _write(tmp_path, "pipeline/05-plan/task-dag.md", "y" * 4000)
        artifacts, used = cp.select_artifacts(tmp_path, stage=6, budget=200)
        assert used <= 200

    def test_skips_missing_files(self, tmp_path):
        # Only state.md exists; other stage-6 files are absent
        _scaffold(tmp_path, stage=6)
        artifacts, used = cp.select_artifacts(tmp_path, stage=6, budget=1800)
        paths = [a["path"] for a in artifacts]
        assert "pipeline/state.md" in paths
        assert "pipeline/05-plan/task-dag.md" not in paths

    def test_zero_budget_returns_nothing(self, tmp_path):
        _scaffold(tmp_path, stage=6)
        artifacts, used = cp.select_artifacts(tmp_path, stage=6, budget=0)
        assert artifacts == []
        assert used == 0

    def test_artifacts_sorted_by_priority(self, tmp_path):
        _scaffold(tmp_path, stage=6)
        _write(tmp_path, "pipeline/05-plan/task-dag.md", "task dag content")
        artifacts, _ = cp.select_artifacts(tmp_path, stage=6, budget=1800)
        priorities = [a["priority"] for a in artifacts]
        assert priorities == sorted(priorities)

    def test_partial_include_on_tight_budget(self, tmp_path):
        """When remaining budget is ≥ PARTIAL_INCLUDE_MIN, trim and include."""
        _scaffold(tmp_path, stage=6)
        # state.md fits; task-dag is large but remaining budget allows partial
        _write(tmp_path, "pipeline/05-plan/task-dag.md", "z" * 4000)
        state_tokens = cp.token_estimate(
            (tmp_path / "pipeline" / "state.md").read_text()
        )
        budget = state_tokens + 100  # room for partial task-dag
        artifacts, used = cp.select_artifacts(tmp_path, stage=6, budget=budget)
        paths = [a["path"] for a in artifacts]
        assert "pipeline/05-plan/task-dag.md" in paths
        assert "[truncated]" in next(
            a["content"] for a in artifacts if "task-dag" in a["path"]
        )


class TestStage6Exclusions:
    """The done-when criterion: stage 6 returns task-dag + spec + design system,
    NOT full SRS or architecture."""

    def _stage6_paths(self) -> list[str]:
        return [s["path"] for s in cp._STAGE_ARTIFACTS[6]]

    def test_task_dag_included(self):
        assert "pipeline/05-plan/task-dag.md" in self._stage6_paths()

    def test_spec_included(self):
        assert "pipeline/04-spec/spec.md" in self._stage6_paths()

    def test_design_system_included(self):
        assert "pipeline/02-product-ux/design-system.md" in self._stage6_paths()

    def test_srs_excluded(self):
        assert "pipeline/01-srs/srs.md" not in self._stage6_paths()

    def test_architecture_excluded(self):
        assert "pipeline/03-architecture/architecture.md" not in self._stage6_paths()


class TestPruneOutput:
    def test_returns_dict_with_required_keys(self, tmp_path):
        _scaffold(tmp_path, stage=6)
        result = cp.prune(6, tmp_path, budget=1800)
        for key in ("stage", "budget", "total_tokens", "artifacts"):
            assert key in result

    def test_total_tokens_matches_artifact_sum(self, tmp_path):
        _scaffold(tmp_path, stage=6)
        _write(tmp_path, "pipeline/05-plan/task-dag.md", "content here")
        result = cp.prune(6, tmp_path, budget=1800)
        expected = sum(a["tokens"] for a in result["artifacts"])
        assert result["total_tokens"] == expected

    def test_total_tokens_within_budget(self, tmp_path):
        _scaffold(tmp_path, stage=6)
        budget = 500
        result = cp.prune(6, tmp_path, budget=budget)
        assert result["total_tokens"] <= budget

    def test_unknown_stage_returns_empty_artifacts(self, tmp_path):
        result = cp.prune(99, tmp_path)
        assert result["artifacts"] == []
        assert result["total_tokens"] == 0


# ---------------------------------------------------------------------------
# CLI (subprocess)
# ---------------------------------------------------------------------------

class TestCLI:
    def test_valid_stage_exits_0(self, tmp_path):
        _scaffold(tmp_path, stage=6)
        r = _run(6, str(tmp_path))
        assert r.returncode == 0

    def test_output_is_valid_json(self, tmp_path):
        _scaffold(tmp_path, stage=6)
        r = _run(6, str(tmp_path))
        data = json.loads(r.stdout)
        assert "artifacts" in data

    def test_invalid_stage_exits_1(self, tmp_path):
        r = _run(99, str(tmp_path))
        assert r.returncode == 1

    def test_budget_flag_respected(self, tmp_path):
        _scaffold(tmp_path, stage=6)
        r = _run(6, str(tmp_path), budget=100)
        data = json.loads(r.stdout)
        assert data["total_tokens"] <= 100
        assert data["budget"] == 100

    def test_stage_0_exits_0(self, tmp_path):
        _scaffold(tmp_path, stage=0)
        r = _run(0, str(tmp_path))
        assert r.returncode == 0

    def test_all_12_stages_exit_0(self, tmp_path):
        """All stage values 0-12 produce valid JSON without errors."""
        _scaffold(tmp_path)
        for stage in range(13):
            r = _run(stage, str(tmp_path))
            assert r.returncode == 0, f"stage {stage} failed: {r.stderr}"
            data = json.loads(r.stdout)
            assert data["stage"] == stage
