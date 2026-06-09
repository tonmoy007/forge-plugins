"""Unit tests for scripts/check-gate.py (CLI tested via subprocess)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = str(Path(__file__).parent.parent.parent / "scripts" / "check-gate.py")
PLUGIN_DIR = str(Path(__file__).parent.parent.parent)
PYTHON = sys.executable


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, SCRIPT] + args,
        capture_output=True,
        text=True,
    )


def _write_srs(pipeline: Path, content: str = "") -> None:
    (pipeline / "01-srs").mkdir(parents=True, exist_ok=True)
    (pipeline / "01-srs" / "srs.md").write_text(content)


class TestOutputStructure:
    def test_json_has_required_keys(self, tmp_path):
        _write_srs(
            tmp_path / "pipeline",
            "# SRS\n\nREQ-001: the system shall work\nNFR-001: fast\n\n## Open Questions\n\n## Glossary\n",
        )
        r = run([
            "--stage", "1",
            "--cwd", str(tmp_path),
            "--plugin-dir", PLUGIN_DIR,
        ])
        # exit 0 when all scripts exist, exit 2 while any are unimplemented (REQ-GATESTUB-001)
        assert r.returncode in (0, 2), r.stderr
        data = json.loads(r.stdout)
        assert "stage" in data
        assert "total" in data
        assert "passed" in data
        assert "failed" in data
        assert "details" in data

    def test_detail_has_required_keys(self, tmp_path):
        _write_srs(tmp_path / "pipeline", "REQ-001: works\n")
        r = run([
            "--stage", "1",
            "--cwd", str(tmp_path),
            "--plugin-dir", PLUGIN_DIR,
        ])
        data = json.loads(r.stdout)
        detail = data["details"][0]
        assert "id" in detail
        assert "description" in detail
        assert "check" in detail
        assert "severity" in detail
        assert "passed" in detail
        assert "message" in detail

    def test_stage_field_matches_requested_stage(self, tmp_path):
        _write_srs(tmp_path / "pipeline", "")
        r = run([
            "--stage", "1",
            "--cwd", str(tmp_path),
            "--plugin-dir", PLUGIN_DIR,
        ])
        data = json.loads(r.stdout)
        assert data["stage"] == 1

    def test_passed_plus_failed_equals_total(self, tmp_path):
        _write_srs(tmp_path / "pipeline", "REQ-001: works\n")
        r = run([
            "--stage", "1",
            "--cwd", str(tmp_path),
            "--plugin-dir", PLUGIN_DIR,
        ])
        data = json.loads(r.stdout)
        assert data["passed"] + data["failed"] == data["total"]


class TestFileExistsCheck:
    def test_passes_when_file_present(self, tmp_path):
        _write_srs(tmp_path / "pipeline", "content")
        r = run([
            "--stage", "1",
            "--cwd", str(tmp_path),
            "--plugin-dir", PLUGIN_DIR,
        ])
        data = json.loads(r.stdout)
        g1_001 = next(d for d in data["details"] if d["id"] == "G1-001")
        assert g1_001["passed"] is True

    def test_fails_when_file_missing(self, tmp_path):
        (tmp_path / "pipeline").mkdir()
        r = run([
            "--stage", "1",
            "--cwd", str(tmp_path),
            "--plugin-dir", PLUGIN_DIR,
        ])
        data = json.loads(r.stdout)
        g1_001 = next(d for d in data["details"] if d["id"] == "G1-001")
        assert g1_001["passed"] is False

    def test_fails_when_file_empty(self, tmp_path):
        (tmp_path / "pipeline" / "01-srs").mkdir(parents=True)
        (tmp_path / "pipeline" / "01-srs" / "srs.md").write_text("")
        r = run([
            "--stage", "1",
            "--cwd", str(tmp_path),
            "--plugin-dir", PLUGIN_DIR,
        ])
        data = json.loads(r.stdout)
        g1_001 = next(d for d in data["details"] if d["id"] == "G1-001")
        assert g1_001["passed"] is False


class TestFileContainsCheck:
    def test_passes_when_pattern_matches(self, tmp_path):
        _write_srs(tmp_path / "pipeline", "REQ-001: the system shall do something\n")
        r = run([
            "--stage", "1",
            "--cwd", str(tmp_path),
            "--plugin-dir", PLUGIN_DIR,
        ])
        data = json.loads(r.stdout)
        g1_002 = next(d for d in data["details"] if d["id"] == "G1-002")
        assert g1_002["passed"] is True

    def test_fails_when_pattern_absent(self, tmp_path):
        _write_srs(tmp_path / "pipeline", "# just a header with no requirements\n")
        r = run([
            "--stage", "1",
            "--cwd", str(tmp_path),
            "--plugin-dir", PLUGIN_DIR,
        ])
        data = json.loads(r.stdout)
        g1_002 = next(d for d in data["details"] if d["id"] == "G1-002")
        assert g1_002["passed"] is False


class TestScriptReturnsZeroCheck:
    def test_missing_script_fails_with_message(self, tmp_path):
        """A criterion whose check script is missing is inconclusive + blocker.

        REQ-GATESTUB-001: this is a config bug, not a soft pass. (Once the M4
        scripts land this stage's scripts all exist; the test then no-ops since
        G1-003 is implemented — guarded below.)
        """
        _write_srs(tmp_path / "pipeline", "REQ-001: works\n")
        r = run([
            "--stage", "1",
            "--cwd", str(tmp_path),
            "--plugin-dir", PLUGIN_DIR,
        ])
        data = json.loads(r.stdout)
        g1_003 = next(d for d in data["details"] if d["id"] == "G1-003")
        if g1_003.get("inconclusive"):
            assert g1_003["passed"] is False
            assert "not implemented" in g1_003["message"]
            assert g1_003["severity"] == "blocker"  # promoted regardless of declared
            assert r.returncode == 2


class TestErrorCases:
    def test_invalid_stage_exits_1(self, tmp_path):
        r = run([
            "--stage", "99",
            "--cwd", str(tmp_path),
            "--plugin-dir", PLUGIN_DIR,
        ])
        assert r.returncode == 1
        assert "stage 99" in r.stderr

    def test_missing_gate_criteria_file_exits_1(self, tmp_path):
        r = run([
            "--stage", "1",
            "--cwd", str(tmp_path),
            "--plugin-dir", str(tmp_path),  # no gate-criteria.md here
        ])
        assert r.returncode == 1


class TestMultipleStages:
    def test_stage_12_has_release_criteria(self, tmp_path):
        r = run([
            "--stage", "12",
            "--cwd", str(tmp_path),
            "--plugin-dir", PLUGIN_DIR,
        ])
        # exit 2 while stage-12 scripts are unimplemented; 0 once M4 lands them
        assert r.returncode in (0, 2)
        data = json.loads(r.stdout)
        assert data["stage"] == 12
        assert data["total"] > 0
        ids = [d["id"] for d in data["details"]]
        assert any(i.startswith("G12-") for i in ids)

    def test_stage_6_has_build_criteria(self, tmp_path):
        r = run([
            "--stage", "6",
            "--cwd", str(tmp_path),
            "--plugin-dir", PLUGIN_DIR,
        ])
        data = json.loads(r.stdout)
        assert data["stage"] == 6
        ids = [d["id"] for d in data["details"]]
        assert any(i.startswith("G6-") for i in ids)
