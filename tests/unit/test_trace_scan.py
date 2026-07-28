"""Tests for scripts/_trace_scan.py — the shared module validate-traceability.py
and trace-matrix.py both import. Covers what those two test files don't:
find_matrix_cells() and the responsible-agent attribute()/stage_for_path()
helpers built on _stage_table.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))

import _trace_scan as scan  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestPipelineMdFilesExcludesGeneratedReports:
    """Regression: pipeline/traceability-matrix.md is written back into pipeline/
    by trace-matrix.py. If the scanner swept it as input, the gap table's own
    prose (e.g. a malformed id quoted in the Detail column) would be re-detected
    as a fresh instance on the next run — a self-referential feedback loop."""

    def test_traceability_matrix_md_excluded(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### REQ-001\nSomething.\n")
        _write(
            tmp_path / "pipeline" / "traceability-matrix.md",
            "| `req-002` | malformed | pipeline/01-srs/srs.md | bad case |\n",
        )
        files = scan.pipeline_md_files(tmp_path)
        assert not any(p.name == "traceability-matrix.md" for p in files)
        assert scan.scan_malformed(tmp_path) == []

    def test_validation_report_md_excluded(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### REQ-001\nSomething.\n")
        _write(tmp_path / "pipeline" / "validation-report.md", "mentions req-002 as an example\n")
        files = scan.pipeline_md_files(tmp_path)
        assert not any(p.name == "validation-report.md" for p in files)

    def test_other_md_files_still_included(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### REQ-001\nSomething.\n")
        files = scan.pipeline_md_files(tmp_path)
        assert any(p.name == "srs.md" for p in files)


class TestFindMatrixCells:
    def test_definition_marked_define(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### REQ-001\nSomething.\n")
        cells = scan.find_matrix_cells(tmp_path)
        assert cells["REQ-001"] == {"01-srs": "define"}

    def test_inline_mention_marked_reference(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### REQ-001\nSomething.\n")
        _write(tmp_path / "pipeline" / "05-plan" / "task-dag.md", "### T-001\nImplements REQ-001.\n")
        cells = scan.find_matrix_cells(tmp_path)
        assert cells["REQ-001"]["01-srs"] == "define"
        assert cells["REQ-001"]["05-plan"] == "reference"

    def test_define_wins_over_reference_in_same_stage_dir(self, tmp_path):
        _write(
            tmp_path / "pipeline" / "01-srs" / "srs.md",
            "Mentions REQ-001 in prose.\n\n### REQ-001\nThe actual definition.\n",
        )
        cells = scan.find_matrix_cells(tmp_path)
        assert cells["REQ-001"]["01-srs"] == "define"

    def test_unknown_prefix_excluded(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "Supports UTF-8 encoding.\n")
        assert scan.find_matrix_cells(tmp_path) == {}

    def test_no_pipeline_dir_returns_empty(self, tmp_path):
        assert scan.find_matrix_cells(tmp_path) == {}


class TestStageForPath:
    def test_known_stage_dir_resolves(self, tmp_path):
        entry = scan.stage_for_path("pipeline/01-srs/srs.md", _ROOT)
        assert entry is not None
        assert entry["stage"] == 1
        assert entry["agent"] == "requirements-analyst"

    def test_plan_stage_resolves_to_planner(self):
        entry = scan.stage_for_path("pipeline/05-plan/task-dag.md", _ROOT)
        assert entry["stage"] == 5
        assert entry["agent"] == "planner"

    def test_non_pipeline_path_returns_none(self):
        assert scan.stage_for_path("tasks/lessons.md", _ROOT) is None

    def test_unknown_stage_dir_returns_none(self):
        assert scan.stage_for_path("pipeline/99-nonexistent/foo.md", _ROOT) is None


class TestAttribute:
    def test_malformed_attributed_to_doc_owner(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### req-001\nSomething.\n")
        issue = scan.scan_malformed(tmp_path)[0]
        stage, agent = scan.attribute(issue, tmp_path, _ROOT)
        assert stage == 1
        assert agent == "requirements-analyst"

    def test_misplaced_attributed_to_wrong_doc_owner(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### REQ-001\nSomething.\n")
        _write(tmp_path / "pipeline" / "02-product-ux" / "prd.md", "### REQ-001\nAlso here.\n")
        defs = scan.find_definitions(tmp_path)
        issue = scan.scan_misplaced(defs)[0]
        stage, agent = scan.attribute(issue, tmp_path, _ROOT)
        assert stage == 2
        assert agent == "product-designer"

    def test_unimplemented_attributed_to_earliest_existing_downstream_stage(self, tmp_path):
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### REQ-004\nOrphaned.\n")
        _write(tmp_path / "pipeline" / "05-plan" / "task-dag.md", "### T-001\nno req mentioned\n")
        issue = scan.scan_unimplemented(tmp_path)[0]
        stage, agent = scan.attribute(issue, tmp_path, _ROOT)
        # task-dag.md (stage 5, planner) is the earliest existing downstream doc
        # for REQ — progress.md/eval-report.md don't exist yet in this fixture.
        assert stage == 5
        assert agent == "planner"

    def test_unimplemented_skips_missing_downstream_docs(self, tmp_path):
        """If task-dag.md doesn't exist yet but progress.md somehow does, attribute
        to whichever existing downstream doc is earliest in pipeline order."""
        _write(tmp_path / "pipeline" / "01-srs" / "srs.md", "### REQ-004\nOrphaned.\n")
        _write(tmp_path / "pipeline" / "06-implementation" / "progress.md", "nothing relevant\n")
        issue = scan.scan_unimplemented(tmp_path)[0]
        stage, agent = scan.attribute(issue, tmp_path, _ROOT)
        assert stage == 6
        assert agent == "builder"

    def test_unresolvable_path_returns_none_none(self, tmp_path):
        issue = scan.Issue("malformed", "REQ-1", "not-a-pipeline-file.md", "detail")
        stage, agent = scan.attribute(issue, tmp_path, _ROOT)
        assert stage is None
        assert agent is None
