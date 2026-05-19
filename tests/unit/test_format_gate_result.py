"""Tests for scripts/format-gate-result.py.

Run with: python -m pytest tests/unit/test_format_gate_result.py -q
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts"


def _import_module():
    """Import format-gate-result.py despite the hyphen in its filename."""
    path = SCRIPTS / "format-gate-result.py"
    spec = importlib.util.spec_from_file_location("format_gate_result", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["format_gate_result"] = mod
    spec.loader.exec_module(mod)
    return mod


fgr = _import_module()


# ---------- fix-hint lookup ----------

class TestLookupFixHint:
    def test_exact_gate_id_match(self):
        c = {"id": "G1-001", "check": "file_contains"}
        hint = fgr._lookup_fix_hint(c)
        assert "REQ-NNN" in hint or "functional requirement" in hint

    def test_longest_prefix_wins(self):
        # G7-API-001 should win over the more generic G7-
        c = {"id": "G7-API-001", "check": "script_returns_zero"}
        hint = fgr._lookup_fix_hint(c)
        assert "contract test" in hint.lower()

    def test_prefix_fallback(self):
        # G3-999 should fall back to the G3- generic hint
        c = {"id": "G3-999", "check": "file_exists"}
        hint = fgr._lookup_fix_hint(c)
        assert "pipeline/03-architecture" in hint

    def test_check_type_fallback(self):
        # No matching prefix; should use check-type fallback
        c = {"id": "X-UNKNOWN-001", "check": "file_exists"}
        hint = fgr._lookup_fix_hint(c)
        assert "Create the missing file" in hint

    def test_universal_fallback(self):
        # Unknown prefix AND unknown check type
        c = {"id": "X-UNKNOWN-001", "check": "unknown_check"}
        hint = fgr._lookup_fix_hint(c)
        assert "/forge:why" in hint or "criterion description" in hint

    def test_mas_gate_hint(self):
        c = {"id": "G7-MAS-001", "check": "script_returns_zero"}
        hint = fgr._lookup_fix_hint(c)
        assert "eval-agent" in hint.lower() or "parallel reviewers" in hint.lower()


# ---------- text formatting ----------

class TestFormatText:
    def test_all_passing(self):
        result = {
            "stage": 1,
            "total": 3,
            "passed": 3,
            "failed": 0,
            "details": [
                {"id": "G1-001", "description": "x", "passed": True, "severity": "blocker"},
                {"id": "G1-002", "description": "y", "passed": True, "severity": "blocker"},
                {"id": "G1-003", "description": "z", "passed": True, "severity": "warning"},
            ],
        }
        out = fgr.format_text(result)
        assert "Stage 1" in out
        assert "3/3 passed" in out
        assert "All criteria passed" in out
        assert "Stage may advance" in out

    def test_blocker_failure(self):
        result = {
            "stage": 3,
            "total": 2,
            "passed": 1,
            "failed": 1,
            "details": [
                {"id": "G3-001", "description": "Arch doc exists",
                 "check": "file_exists",
                 "passed": False, "severity": "blocker",
                 "message": "pipeline/03-architecture/architecture.md: file does not exist"},
                {"id": "G3-002", "description": "ADR present",
                 "check": "file_exists",
                 "passed": True, "severity": "blocker", "message": "OK"},
            ],
        }
        out = fgr.format_text(result)
        assert "BLOCKERS (1" in out
        assert "G3-001" in out
        assert "Create pipeline/03-architecture/architecture.md" in out
        assert "CANNOT advance" in out
        assert "/forge:force-advance" in out

    def test_warnings_dont_block(self):
        result = {
            "stage": 6, "total": 1, "passed": 0, "failed": 1,
            "details": [{
                "id": "G6-FS-002", "description": "bundle size",
                "check": "script_returns_zero",
                "passed": False, "severity": "warning",
                "message": "bundle is 1.2 MB (budget 800 KB)",
            }],
        }
        out = fgr.format_text(result)
        assert "WARNINGS" in out
        assert "BLOCKERS" not in out
        assert "Stage may advance" in out

    def test_passed_summary_compact(self):
        result = {
            "stage": 1, "total": 4, "passed": 3, "failed": 1,
            "details": [
                {"id": "G1-001", "description": "a", "check": "x",
                 "passed": False, "severity": "blocker", "message": "m"},
                {"id": "G1-002", "description": "b", "passed": True, "severity": "blocker"},
                {"id": "G1-003", "description": "c", "passed": True, "severity": "warning"},
                {"id": "G1-004", "description": "d", "passed": True, "severity": "blocker"},
            ],
        }
        out = fgr.format_text(result)
        # Passed criteria should appear inline, not as full blocks.
        assert "PASSED (3): G1-002, G1-003, G1-004" in out


# ---------- JSON enrichment ----------

class TestEnrichJson:
    def test_failing_criterion_gets_fix_hint(self):
        result = {
            "stage": 1, "total": 1, "passed": 0, "failed": 1,
            "details": [{
                "id": "G1-001", "description": "REQ-NNN", "check": "file_contains",
                "passed": False, "severity": "blocker", "message": "no match",
            }],
        }
        enriched = fgr.enrich_json(result)
        assert "fix_hint" in enriched["details"][0]
        assert enriched["details"][0]["fix_hint"]

    def test_passing_criterion_no_fix_hint(self):
        result = {
            "stage": 1, "total": 1, "passed": 1, "failed": 0,
            "details": [{
                "id": "G1-001", "description": "REQ", "check": "file_contains",
                "passed": True, "severity": "blocker", "message": "OK",
            }],
        }
        enriched = fgr.enrich_json(result)
        assert "fix_hint" not in enriched["details"][0]

    def test_preserves_other_fields(self):
        result = {
            "stage": 5, "total": 2, "passed": 1, "failed": 1, "extra": "data",
            "details": [],
        }
        enriched = fgr.enrich_json(result)
        assert enriched["extra"] == "data"
        assert enriched["stage"] == 5


# ---------- CLI ----------

class TestCLI:
    def test_input_file_mode(self, tmp_path, capsys):
        path = tmp_path / "result.json"
        path.write_text(json.dumps({
            "stage": 1, "total": 1, "passed": 1, "failed": 0,
            "details": [{"id": "G1-001", "description": "x",
                         "passed": True, "severity": "blocker"}],
        }))
        rc = fgr.main(["--input", str(path)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "All criteria passed" in out

    def test_input_file_failing(self, tmp_path, capsys):
        path = tmp_path / "result.json"
        path.write_text(json.dumps({
            "stage": 1, "total": 1, "passed": 0, "failed": 1,
            "details": [{"id": "G1-001", "description": "x",
                         "check": "file_contains",
                         "passed": False, "severity": "blocker", "message": "missing"}],
        }))
        rc = fgr.main(["--input", str(path)])
        out = capsys.readouterr().out
        assert rc == 1
        assert "BLOCKERS" in out

    def test_json_mode_emits_enriched(self, tmp_path, capsys):
        path = tmp_path / "result.json"
        path.write_text(json.dumps({
            "stage": 1, "total": 1, "passed": 0, "failed": 1,
            "details": [{"id": "G1-001", "description": "x",
                         "check": "file_contains",
                         "passed": False, "severity": "blocker", "message": "miss"}],
        }))
        rc = fgr.main(["--input", str(path), "--json"])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "fix_hint" in data["details"][0]
        assert rc == 1

    def test_malformed_input_fails(self, tmp_path, capsys):
        path = tmp_path / "bad.json"
        path.write_text("not json")
        with pytest.raises(SystemExit) as exc:
            fgr.main(["--input", str(path)])
        assert exc.value.code == 2