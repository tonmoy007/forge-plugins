"""Tests for scripts/trace-matrix.py — the id x stage matrix generator and gap
notice writer. Covers build_matrix_table/build_gap_rows/format_report directly,
plus the CLI's file-writing side effects (pipeline/traceability-matrix.md and
.forge/traceability-gaps.jsonl).
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
SCRIPT = _ROOT / "scripts" / "trace-matrix.py"
PYTHON = sys.executable

# Hyphenated filename — must use importlib
_spec = importlib.util.spec_from_file_location("root_trace_matrix", SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["root_trace_matrix"] = _mod
_spec.loader.exec_module(_mod)

build_matrix_table = _mod.build_matrix_table
build_gap_rows = _mod.build_gap_rows
format_report = _mod.format_report
write_gaps_jsonl = _mod.write_gaps_jsonl


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestBuildMatrixTable:
    def test_empty_cells_returns_placeholder(self):
        table = build_matrix_table({}, _ROOT)
        assert "No ids found" in table

    def test_define_marked_diamond(self):
        table = build_matrix_table({"REQ-001": {"01-srs": "define"}}, _ROOT)
        assert "◆" in table
        assert "REQ-001" in table
        assert "S1" in table

    def test_reference_marked_dot(self):
        table = build_matrix_table({"REQ-001": {"05-plan": "reference"}}, _ROOT)
        assert "●" in table
        assert "S5" in table

    def test_columns_sorted_by_stage_number(self):
        table = build_matrix_table(
            {"REQ-001": {"05-plan": "reference", "01-srs": "define"}}, _ROOT
        )
        header_line = table.splitlines()[0]
        assert header_line.index("S1") < header_line.index("S5")


class TestBuildGapRows:
    def test_empty_issues_returns_empty(self, tmp_path):
        assert build_gap_rows([], tmp_path, _ROOT) == []

    def test_gap_carries_attribution_fields(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### req-001\nSomething.\n")
        sys.path.insert(0, str(_ROOT / "scripts"))
        import _trace_scan as scan
        issues = scan.scan_malformed(tmp_path)
        rows = build_gap_rows(issues, tmp_path, _ROOT)
        assert len(rows) == 1
        assert rows[0]["id"] == "req-001"
        assert rows[0]["category"] == "malformed"
        assert rows[0]["stage"] == 1
        assert rows[0]["agent"] == "requirements-analyst"
        assert "generated_at" in rows[0]


class TestFormatReport:
    def test_no_gaps_says_none_found(self):
        report = format_report("some table", [])
        assert "None found." in report
        assert "Total gaps: 0" in report

    def test_gaps_rendered_as_table_rows(self):
        gap = {
            "id": "REQ-004", "category": "unimplemented", "file": "pipeline/01-srs/srs.md",
            "detail": "never referenced", "stage": 5, "agent": "planner",
            "generated_at": "2026-01-01T00:00:00Z",
        }
        report = format_report("some table", [gap])
        assert "REQ-004" in report
        assert "planner" in report
        assert "Total gaps: 1" in report

    def test_unassigned_agent_rendered_explicitly(self):
        gap = {
            "id": "REQ-1", "category": "malformed", "file": "not-a-pipeline-file.md",
            "detail": "x", "stage": None, "agent": None, "generated_at": "2026-01-01T00:00:00Z",
        }
        report = format_report("some table", [gap])
        assert "unassigned" in report


class TestWriteGapsJsonl:
    def test_writes_one_line_per_gap(self, tmp_path):
        out = tmp_path / ".forge" / "traceability-gaps.jsonl"
        write_gaps_jsonl(out, [
            {"id": "REQ-1", "category": "malformed", "file": "f.md", "detail": "d",
             "stage": 1, "agent": "requirements-analyst", "generated_at": "t"},
        ])
        lines = out.read_text().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["id"] == "REQ-1"

    def test_overwrites_stale_snapshot(self, tmp_path):
        """A fixed gap must not linger — the file is a snapshot, not a log."""
        out = tmp_path / ".forge" / "traceability-gaps.jsonl"
        write_gaps_jsonl(out, [{"id": "OLD-1", "category": "x", "file": "f", "detail": "d",
                                  "stage": 1, "agent": "a", "generated_at": "t"}])
        write_gaps_jsonl(out, [])
        assert out.read_text() == ""


class TestCLI:
    def test_writes_matrix_and_gaps_files(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### REQ-001\nSomething.\n")
        result = subprocess.run(
            [PYTHON, str(SCRIPT), "--cwd", str(tmp_path), "--plugin-dir", str(_ROOT)],
            capture_output=True, text=True,
        )
        assert (tmp_path / "pipeline" / "traceability-matrix.md").exists()
        assert (tmp_path / ".forge" / "traceability-gaps.jsonl").exists()
        assert "# Traceability Matrix" in result.stdout

    def test_no_write_flag_skips_files(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### REQ-001\nSomething.\n")
        subprocess.run(
            [PYTHON, str(SCRIPT), "--cwd", str(tmp_path), "--plugin-dir", str(_ROOT), "--no-write"],
            capture_output=True, text=True,
        )
        assert not (tmp_path / "pipeline" / "traceability-matrix.md").exists()

    def test_exit_code_reflects_gap_presence(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### req-001\nmalformed.\n")
        result = subprocess.run(
            [PYTHON, str(SCRIPT), "--cwd", str(tmp_path), "--plugin-dir", str(_ROOT)],
            capture_output=True, text=True,
        )
        assert result.returncode == 1

    def test_clean_project_exits_0(self, tmp_path):
        result = subprocess.run(
            [PYTHON, str(SCRIPT), "--cwd", str(tmp_path), "--plugin-dir", str(_ROOT)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
