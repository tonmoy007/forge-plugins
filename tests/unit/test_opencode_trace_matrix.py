"""Tests for forge-opencode/scripts/trace-matrix.py.

The underlying logic is shared with the root copy via _trace_scan.py (see
tests/unit/test_trace_matrix.py and test_trace_scan.py for full coverage of the
scanning/attribution primitives) — this file pins the forge-opencode/ copy's own
CLI behavior and file-writing side effects, guarding against future drift between
the two trees the way test_opencode_validate_traceability.py already does for
validate-traceability.py.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_OC = Path(__file__).parent.parent.parent / "forge-opencode"
SCRIPT = _OC / "scripts" / "trace-matrix.py"
PYTHON = sys.executable


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestOpencodeTraceMatrixCLI:
    def test_writes_matrix_and_gaps_files(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### REQ-001\nSomething.\n")
        result = subprocess.run(
            [PYTHON, str(SCRIPT), "--cwd", str(tmp_path), "--plugin-dir", str(_OC)],
            capture_output=True, text=True,
        )
        assert (tmp_path / "pipeline" / "traceability-matrix.md").exists()
        assert (tmp_path / ".forge" / "traceability-gaps.jsonl").exists()
        assert "# Traceability Matrix" in result.stdout

    def test_gap_attribution_present(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### req-001\nmalformed.\n")
        result = subprocess.run(
            [PYTHON, str(SCRIPT), "--cwd", str(tmp_path), "--plugin-dir", str(_OC)],
            capture_output=True, text=True,
        )
        assert result.returncode == 1
        assert "requirements-analyst" in result.stdout

    def test_clean_project_exits_0(self, tmp_path):
        result = subprocess.run(
            [PYTHON, str(SCRIPT), "--cwd", str(tmp_path), "--plugin-dir", str(_OC)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0

    def test_gaps_snapshot_overwrites_not_appends(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### req-001\nmalformed.\n")
        subprocess.run(
            [PYTHON, str(SCRIPT), "--cwd", str(tmp_path), "--plugin-dir", str(_OC)],
            capture_output=True, text=True,
        )
        # Fix the malformed id, re-run — the stale gap must not linger.
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### REQ-001\nfixed.\n")
        subprocess.run(
            [PYTHON, str(SCRIPT), "--cwd", str(tmp_path), "--plugin-dir", str(_OC)],
            capture_output=True, text=True,
        )
        gaps_file = tmp_path / ".forge" / "traceability-gaps.jsonl"
        assert "req-001" not in gaps_file.read_text()
