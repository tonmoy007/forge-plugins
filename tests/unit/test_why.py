"""Tests for scripts/why.py.

Run with: python -m pytest tests/unit/test_why.py -q
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

import yaml

SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _import_why():
    path = SCRIPTS / "why.py"
    spec = importlib.util.spec_from_file_location("why", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["why"] = mod
    spec.loader.exec_module(mod)
    return mod


why = _import_why()


def _make_plugin_dir(root: Path) -> Path:
    """Create a minimal Forge plugin dir layout with gate-criteria.md + format-gate-result.py."""
    pd = root / "plugin"
    (pd / "references").mkdir(parents=True)
    (pd / "scripts").mkdir()
    (pd / "references" / "gate-criteria.md").write_text(
        "```yaml\n"
        "stage: 1\n"
        "name: srs\n"
        "criteria:\n"
        "  - id: G1-001\n"
        "    description: SRS file exists\n"
        "    check: file_exists\n"
        "    args: { path: pipeline/01-srs/srs.md }\n"
        "    severity: blocker\n"
        "  - id: G1-002\n"
        "    description: REQ-NNN IDs present\n"
        "    check: file_contains\n"
        "    severity: blocker\n"
        "```\n"
        "\n"
        "```yaml\n"
        "stage: 3\n"
        "name: architecture\n"
        "criteria:\n"
        "  - id: G3-001\n"
        "    description: Architecture doc exists\n"
        "    check: file_exists\n"
        "    severity: blocker\n"
        "```\n"
    )
    # Copy our format-gate-result.py into the plugin dir so the dynamic import works
    src = SCRIPTS / "format-gate-result.py"
    if src.exists():
        (pd / "scripts" / "format-gate-result.py").write_text(src.read_text())
    return pd


def _make_project(root: Path, current_stage: int = 1) -> Path:
    """Minimal project layout with state.md and .forge/lessons.yaml."""
    proj = root / "proj"
    (proj / "pipeline").mkdir(parents=True)
    (proj / ".forge").mkdir()
    (proj / "pipeline" / "state.md").write_text(
        "---\n"
        "schema_version: 1\n"
        "project_type: api\n"
        "cycle: 1\n"
        f"current_stage: {current_stage}\n"
        "current_task: null\n"
        "current_milestone: null\n"
        "total_tasks: null\n"
        "last_updated: '2026-05-15T00:00:00Z'\n"
        "blockers: []\n"
        "---\n# State\n"
    )
    return proj


# ---------- classifier ----------

class TestClassify:
    def test_gate_id(self):
        assert why._classify("G1-001") == "gate"
        assert why._classify("G7-API-001") == "gate"
        assert why._classify("G12-LIB-002") == "gate"

    def test_stage_terse(self):
        assert why._classify("3") == "stage"
        assert why._classify("12") == "stage"

    def test_stage_prefixed(self):
        assert why._classify("stage-3") == "stage"
        assert why._classify("Stage-7") == "stage"

    def test_stage_out_of_range_falls_to_tag(self):
        # 13 doesn't match the stage regex, so it's treated as a tag
        assert why._classify("13") == "tag"
        assert why._classify("0") == "tag"

    def test_tag_for_anything_else(self):
        assert why._classify("force-advance") == "tag"
        assert why._classify("slow-consumer") == "tag"


# ---------- gate explanation ----------

class TestExplainGate:
    def test_lookup_existing_gate(self, tmp_path):
        pd = _make_plugin_dir(tmp_path)
        answer = why._explain_gate("G1-001", pd)
        assert answer is not None
        assert answer["kind"] == "gate"
        assert answer["id"] == "G1-001"
        assert answer["stage"] == 1
        assert answer["severity"] == "blocker"
        assert "SRS file" in answer["description"]
        # Fix hint should be present (format-gate-result.py available)
        assert answer["fix_hint"]

    def test_lookup_missing_gate(self, tmp_path):
        pd = _make_plugin_dir(tmp_path)
        assert why._explain_gate("G99-999", pd) is None

    def test_lookup_works_without_format_gate_result(self, tmp_path):
        # Remove format-gate-result.py from the plugin dir to simulate older install
        pd = _make_plugin_dir(tmp_path)
        (pd / "scripts" / "format-gate-result.py").unlink()
        answer = why._explain_gate("G1-001", pd)
        assert answer is not None
        # fix_hint is empty when the formatter is unavailable; rest of fields still populated
        assert answer["fix_hint"] == ""
        assert answer["description"]


# ---------- stage explanation ----------

class TestExplainStage:
    def test_known_stage(self, tmp_path):
        pd = _make_plugin_dir(tmp_path)
        a = why._explain_stage(1, pd)
        assert a is not None
        assert a["stage"] == 1
        assert "srs" in a["name"].lower()
        assert a["gate_blockers"] == 2  # G1-001 + G1-002

    def test_out_of_range_stage(self, tmp_path):
        pd = _make_plugin_dir(tmp_path)
        assert why._explain_stage(0, pd) is None
        assert why._explain_stage(13, pd) is None

    def test_stage_with_no_criteria(self, tmp_path):
        pd = _make_plugin_dir(tmp_path)
        # Stage 2 is in STAGE_NAMES but has no criteria in our fixture
        a = why._explain_stage(2, pd)
        assert a is not None
        assert a["gate_blockers"] == 0
        assert a["gate_warnings"] == 0


# ---------- lesson tag explanation ----------

class TestExplainLessonTag:
    def test_existing_tag(self, tmp_path):
        proj = _make_project(tmp_path)
        (proj / ".forge" / "lessons.yaml").write_text(
            "schema_version: 1\n"
            "lessons:\n"
            "  - trigger: t1\n"
            "    rule: r1\n"
            "    tags: [force-advance]\n"
            "    date: '2026-05-15'\n"
            "    stage: [1]\n"
            "  - trigger: t2\n"
            "    rule: r2\n"
            "    tags: [force-advance]\n"
            "    date: '2026-05-14'\n"
            "    stage: [3]\n"
            "  - trigger: t3\n"
            "    rule: r3\n"
            "    tags: [other]\n"
            "    date: '2026-05-15'\n"
        )
        a = why._explain_lesson_tag("force-advance", proj)
        assert a is not None
        assert a["match_count"] == 2
        # Most recent first
        assert a["lessons"][0]["trigger"] == "t1"
        assert a["lessons"][1]["trigger"] == "t2"

    def test_no_match(self, tmp_path):
        proj = _make_project(tmp_path)
        (proj / ".forge" / "lessons.yaml").write_text(
            "schema_version: 1\nlessons: []\n"
        )
        assert why._explain_lesson_tag("anything", proj) is None

    def test_no_lessons_file(self, tmp_path):
        # .forge exists but no lessons.yaml
        proj = _make_project(tmp_path)
        assert why._explain_lesson_tag("anything", proj) is None

    def test_malformed_lessons_yaml(self, tmp_path):
        proj = _make_project(tmp_path)
        (proj / ".forge" / "lessons.yaml").write_text("not: valid: yaml: [")
        # Should not crash, just return None
        assert why._explain_lesson_tag("anything", proj) is None


# ---------- current blockers ----------

class TestCurrentBlockers:
    def test_no_check_gate_returns_note(self, tmp_path):
        # plugin_dir without check-gate.py
        pd = tmp_path / "plugin"
        pd.mkdir()
        (pd / "scripts").mkdir()
        (pd / "references").mkdir()
        proj = _make_project(tmp_path)
        a = why._explain_current_blockers(proj, pd)
        assert a["kind"] == "current_blockers"
        assert "missing" in a["note"].lower() or "no active" in a["note"].lower()

    def test_stage_zero_returns_note(self, tmp_path):
        pd = _make_plugin_dir(tmp_path)
        # Need a check-gate.py for this test path
        (pd / "scripts" / "check-gate.py").write_text("#!/usr/bin/env python3\nprint('{}')\n")
        proj = _make_project(tmp_path, current_stage=0)
        a = why._explain_current_blockers(proj, pd)
        assert a["stage"] == 0


# ---------- rendering ----------

class TestRendering:
    def test_render_gate(self):
        text = why._render({
            "kind": "gate", "id": "G1-001", "stage": 1,
            "description": "SRS file exists", "check": "file_exists",
            "args": {"path": "pipeline/01-srs/srs.md"},
            "severity": "blocker", "fix_hint": "Edit pipeline/01-srs/srs.md",
        })
        assert "G1-001" in text
        assert "Stage:" in text
        assert "Fix hint:" in text

    def test_render_stage(self):
        text = why._render({
            "kind": "stage", "stage": 1, "name": "srs",
            "purpose": "Capture requirements", "artifacts": ["x", "y"],
            "gate_blockers": 3, "gate_warnings": 1,
            "gate_criterion_ids": ["G1-001", "G1-002"],
        })
        assert "Stage 1 — srs" in text
        assert "3 blocker" in text
        assert "1 warning" in text

    def test_render_lesson_tag(self):
        text = why._render({
            "kind": "lesson_tag", "tag": "force-advance",
            "match_count": 1,
            "lessons": [{"date": "2026-05-15", "stage": [1],
                         "trigger": "t", "rule": "r", "blockers": ["G1-001"]}],
        })
        assert "force-advance" in text
        assert "G1-001" in text

    def test_render_current_no_blockers(self):
        text = why._render({
            "kind": "current_blockers", "stage": 3, "blockers": [],
        })
        assert "no blockers" in text.lower()
        assert "/forge:advance" in text


# ---------- CLI ----------

class TestCLI:
    def test_gate_target(self, tmp_path, capsys):
        pd = _make_plugin_dir(tmp_path)
        proj = _make_project(tmp_path)
        rc = why.main(["G1-001", "--cwd", str(proj), "--plugin-dir", str(pd)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "G1-001" in out

    def test_unknown_gate_exits_1(self, tmp_path, capsys):
        pd = _make_plugin_dir(tmp_path)
        proj = _make_project(tmp_path)
        rc = why.main(["G99-999", "--cwd", str(proj), "--plugin-dir", str(pd)])
        assert rc == 1
        err = capsys.readouterr().err
        assert "not found" in err.lower()

    def test_stage_terse(self, tmp_path, capsys):
        pd = _make_plugin_dir(tmp_path)
        proj = _make_project(tmp_path)
        rc = why.main(["3", "--cwd", str(proj), "--plugin-dir", str(pd)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Stage 3" in out

    def test_lesson_tag(self, tmp_path, capsys):
        pd = _make_plugin_dir(tmp_path)
        proj = _make_project(tmp_path)
        (proj / ".forge" / "lessons.yaml").write_text(
            "schema_version: 1\n"
            "lessons:\n"
            "  - tags: [force-advance]\n"
            "    rule: 'tested override'\n"
            "    date: '2026-05-15'\n"
            "    stage: [1]\n"
            "    trigger: 'test trigger'\n"
        )
        rc = why.main(["force-advance", "--cwd", str(proj), "--plugin-dir", str(pd)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "force-advance" in out

    def test_json_output(self, tmp_path, capsys):
        pd = _make_plugin_dir(tmp_path)
        proj = _make_project(tmp_path)
        why.main(["G1-001", "--cwd", str(proj), "--plugin-dir", str(pd), "--json"])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["kind"] == "gate"
        assert data["id"] == "G1-001"

class TestCaseInsensitiveGateLookup:
    """T-117 / REQ-WHYCI-001: gate-ID lookup is case-insensitive."""

    def test_lowercase_equals_uppercase(self, tmp_path, capsys):
        pd = _make_plugin_dir(tmp_path)
        proj = tmp_path / "proj"
        proj.mkdir()

        assert why.main(["g1-001", "--cwd", str(proj), "--plugin-dir", str(pd), "--json"]) == 0
        lower = json.loads(capsys.readouterr().out)
        assert why.main(["G1-001", "--cwd", str(proj), "--plugin-dir", str(pd), "--json"]) == 0
        upper = json.loads(capsys.readouterr().out)

        assert lower == upper
        assert lower["kind"] == "gate"
        assert lower["id"] == "G1-001"

    def test_mixed_case_resolves(self, tmp_path, capsys):
        pd = _make_plugin_dir(tmp_path)
        proj = tmp_path / "proj"
        proj.mkdir()
        assert why.main(["g1-001", "--cwd", str(proj), "--plugin-dir", str(pd)]) == 0

    def test_unknown_gate_still_not_found_any_case(self, tmp_path, capsys):
        pd = _make_plugin_dir(tmp_path)
        proj = tmp_path / "proj"
        proj.mkdir()
        # case-normalization must not mask a genuine miss
        assert why.main(["g9-999", "--cwd", str(proj), "--plugin-dir", str(pd)]) == 1
        assert why.main(["G9-999", "--cwd", str(proj), "--plugin-dir", str(pd)]) == 1
