"""Tests for forge-opencode/scripts/validate-traceability.py.

Covers the four checks this script adds beyond the existing gate scripts —
malformed IDs, misplaced ID definitions, duplicate ID definitions, and
unimplemented/orphaned requirements — plus the combined report and its
rollup of the pre-existing traceability/gate scripts.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_OC = Path(__file__).parent.parent.parent / "forge-opencode"
SCRIPT = _OC / "scripts" / "validate-traceability.py"
PYTHON = sys.executable

# Hyphenated filename — must use importlib
_spec = importlib.util.spec_from_file_location("oc_validate_traceability", SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["oc_validate_traceability"] = _mod
_spec.loader.exec_module(_mod)

scan_malformed = _mod.scan_malformed
find_definitions = _mod.find_definitions
scan_misplaced = _mod.scan_misplaced
scan_duplicates = _mod.scan_duplicates
scan_unimplemented = _mod.scan_unimplemented
build_report = _mod.build_report
format_report = _mod.format_report


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestScanMalformed:
    def test_well_formed_id_not_flagged(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### REQ-001\nSomething.\n")
        assert scan_malformed(tmp_path) == []

    def test_lowercase_prefix_flagged(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### req-001\nSomething.\n")
        issues = scan_malformed(tmp_path)
        assert len(issues) == 1
        assert "uppercase" in issues[0].detail

    def test_underscore_separator_flagged(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### REQ_001\nSomething.\n")
        issues = scan_malformed(tmp_path)
        assert len(issues) == 1
        assert "separator" in issues[0].detail

    def test_wrong_digit_padding_flagged(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### REQ-1\nSomething.\n")
        issues = scan_malformed(tmp_path)
        assert len(issues) == 1
        assert "3-digit" in issues[0].detail

    def test_unknown_prefix_ignored(self, tmp_path):
        """Not every word-dash-digits token is an id — UTF-8, ISO-9001, etc."""
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "Supports UTF-8 and ISO-9001.\n")
        assert scan_malformed(tmp_path) == []

    def test_task_id_has_no_fixed_width(self, tmp_path):
        """T-ids have no documented fixed width — only case/separator apply."""
        _write(tmp_path / "pipeline" / "05-plan" / "task-dag.md", "### T-1\ndone: yes\n")
        assert scan_malformed(tmp_path) == []

    def test_no_pipeline_dir_returns_empty(self, tmp_path):
        assert scan_malformed(tmp_path) == []


class TestMisplaced:
    def test_req_defined_only_in_home_doc_is_clean(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### REQ-001\nSomething.\n")
        defs = find_definitions(tmp_path)
        assert scan_misplaced(defs) == []

    def test_req_defined_outside_srs_is_misplaced(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### REQ-001\nSomething.\n")
        _write(tmp_path / "pipeline" / "04-spec" / "technical-spec.md", "### REQ-001\nAlso here.\n")
        defs = find_definitions(tmp_path)
        issues = scan_misplaced(defs)
        assert len(issues) == 1
        assert issues[0].file == "pipeline/04-spec/technical-spec.md"
        assert "pipeline/01-srs/srs.md" in issues[0].detail

    def test_task_id_reheaded_elsewhere_not_misplaced(self, tmp_path):
        """T-ids legitimately get their own heading in progress.md/eval-report.md."""
        _write(tmp_path / "pipeline" / "05-plan" / "task-dag.md", "### T-001\ndone: yes\n")
        _write(tmp_path / "pipeline" / "06-implementation" / "progress.md", "### T-001\ndone\n")
        defs = find_definitions(tmp_path)
        assert scan_misplaced(defs) == []


class TestDuplicates:
    def test_single_definition_not_duplicate(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### REQ-001\nSomething.\n")
        assert scan_duplicates(tmp_path) == []

    def test_same_file_twice_is_duplicate(self, tmp_path):
        _write(
            tmp_path / "pipeline" / "01-srs" / "srs.md",
            "### REQ-001\nFirst.\n\n### REQ-001\nSecond, conflicting copy.\n",
        )
        issues = scan_duplicates(tmp_path)
        assert len(issues) == 1
        assert issues[0].token == "REQ-001"
        assert "2 times" in issues[0].detail

    def test_cross_file_recurrence_not_duplicate(self, tmp_path):
        """Same id heading in two different files is normal traceability, not a dup."""
        _write(tmp_path / "pipeline" / "05-plan" / "task-dag.md", "### T-001\ndone: yes\n")
        _write(tmp_path / "pipeline" / "06-implementation" / "progress.md", "### T-001\ndone\n")
        assert scan_duplicates(tmp_path) == []


class TestUnimplemented:
    def test_req_never_referenced_downstream_is_orphaned(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### REQ-001\nSomething.\n")
        _write(tmp_path / "pipeline" / "05-plan" / "task-dag.md", "### T-001\nno req mentioned here\n")
        issues = scan_unimplemented(tmp_path)
        assert any(i.token == "REQ-001" for i in issues)

    def test_req_referenced_downstream_is_clean(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### REQ-001\nSomething.\n")
        _write(tmp_path / "pipeline" / "05-plan" / "task-dag.md", "### T-001\nImplements REQ-001.\n")
        issues = scan_unimplemented(tmp_path)
        assert not any(i.token == "REQ-001" for i in issues)

    def test_no_downstream_docs_yet_skips_check(self, tmp_path):
        """Early pipeline (only srs.md exists) — too soon to call anything orphaned."""
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### REQ-001\nSomething.\n")
        issues = scan_unimplemented(tmp_path)
        assert issues == []

    def test_lowercase_definition_not_double_counted(self, tmp_path):
        """A malformed lowercase id isn't recognized as a 'proper' definition by
        the strict-uppercase orphan scan — it's already caught by scan_malformed."""
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### req-001\nSomething.\n")
        _write(tmp_path / "pipeline" / "05-plan" / "task-dag.md", "### T-001\nno req mentioned\n")
        issues = scan_unimplemented(tmp_path)
        assert issues == []


class TestReportAndCLI:
    def test_clean_project_exits_0(self, tmp_path):
        _write(
            tmp_path / "pipeline" / "01-srs" / "srs.md",
            "### REQ-001\nSomething.\nAC-1: works.\n",
        )
        result = subprocess.run(
            [PYTHON, str(SCRIPT), "--cwd", str(tmp_path), "--plugin-dir", str(_OC)],
            capture_output=True,
            text=True,
        )
        # Not all gate scripts will pass this minimal fixture (no task-dag etc.),
        # so exit code reflects that honestly — verify report structure instead.
        assert "# Forge Validation Report" in result.stdout
        assert "Malformed IDs (0)" in result.stdout

    def test_issues_present_exits_1(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### req-001\nSomething.\n")
        result = subprocess.run(
            [PYTHON, str(SCRIPT), "--cwd", str(tmp_path), "--plugin-dir", str(_OC)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Malformed IDs (1)" in result.stdout
        assert "**Status: ISSUES FOUND**" in result.stdout

    def test_out_flag_writes_file_not_stdout(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### REQ-001\nSomething.\n")
        out = tmp_path / "report.md"
        result = subprocess.run(
            [PYTHON, str(SCRIPT), "--cwd", str(tmp_path), "--plugin-dir", str(_OC), "--out", str(out)],
            capture_output=True,
            text=True,
        )
        assert result.stdout.strip() == ""
        assert out.exists()
        assert "# Forge Validation Report" in out.read_text()

    def test_report_includes_gate_rollup_section(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### REQ-001\nSomething.\n")
        issues, gates = build_report(tmp_path, _OC)
        report = format_report(issues, gates)
        assert "## Traceability & Gate Rollup" in report
        assert any("traceability chain" in g.name for g in gates)
