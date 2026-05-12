"""Unit tests for scripts/sync-lessons.py (T-021)."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Import via importlib (hyphenated filename)
# ---------------------------------------------------------------------------

_SCRIPT = Path(__file__).parent.parent.parent / "scripts" / "sync-lessons.py"
_PYTHON = sys.executable


def _load_module():
    spec = importlib.util.spec_from_file_location("sync_lessons", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["sync_lessons"] = mod  # must register before exec_module for @dataclass
    spec.loader.exec_module(mod)
    return mod


mod = _load_module()
parse_lessons_md = mod.parse_lessons_md
merge = mod.merge
sync = mod.sync
LessonEntry = mod.LessonEntry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASIC_MD = """\
# Lessons Learned

## Lessons

### 2026-05-07 — System python is Python 2; use python3 explicitly
- **Trigger**: Any time a script is run via python
- **Rule**: Always use python3 not python
- **Why**: Python 2 rejects type annotations
- **Tags**: [python, hooks]

### 2026-05-10 — PyYAML parses timestamps as datetime objects
- **Trigger**: Any time PyYAML loads ISO timestamps
- **Rule**: Normalize datetime values to strings after loading
- **Why**: Schema expects str type
- **Tags**: [python, yaml]
"""


def _write_md(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "tasks" / "lessons.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_PYTHON, str(_SCRIPT)] + args,
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# parse_lessons_md
# ---------------------------------------------------------------------------


class TestParseLessonsMd:
    def test_missing_file_returns_empty(self, tmp_path):
        result = parse_lessons_md(tmp_path / "nonexistent.md")
        assert result == []

    def test_parses_two_entries(self, tmp_path):
        p = _write_md(tmp_path, _BASIC_MD)
        entries = parse_lessons_md(p)
        assert len(entries) == 2

    def test_entry_has_correct_date(self, tmp_path):
        p = _write_md(tmp_path, _BASIC_MD)
        entries = parse_lessons_md(p)
        assert entries[0].date == "2026-05-07"

    def test_entry_has_correct_title(self, tmp_path):
        p = _write_md(tmp_path, _BASIC_MD)
        entries = parse_lessons_md(p)
        assert "python" in entries[0].title.lower()

    def test_trigger_extracted(self, tmp_path):
        p = _write_md(tmp_path, _BASIC_MD)
        entries = parse_lessons_md(p)
        assert "python" in entries[0].trigger.lower()

    def test_rule_extracted(self, tmp_path):
        p = _write_md(tmp_path, _BASIC_MD)
        entries = parse_lessons_md(p)
        assert "python3" in entries[0].rule.lower()

    def test_why_extracted(self, tmp_path):
        p = _write_md(tmp_path, _BASIC_MD)
        entries = parse_lessons_md(p)
        assert "type" in entries[0].why.lower()

    def test_tags_parsed_as_list(self, tmp_path):
        p = _write_md(tmp_path, _BASIC_MD)
        entries = parse_lessons_md(p)
        assert "python" in entries[0].tags
        assert "hooks" in entries[0].tags

    def test_id_generated(self, tmp_path):
        p = _write_md(tmp_path, _BASIC_MD)
        entries = parse_lessons_md(p)
        assert entries[0].id.startswith("L-")

    def test_entry_without_trigger_skipped(self, tmp_path):
        content = """\
## Lessons

### 2026-05-07 — Title only, no fields
"""
        p = _write_md(tmp_path, content)
        entries = parse_lessons_md(p)
        assert entries == []

    def test_duplicate_slug_suffixed(self, tmp_path):
        content = """\
## Lessons

### 2026-05-07 — Same title here
- **Trigger**: first trigger
- **Rule**: first rule
- **Why**: first why
- **Tags**: []

### 2026-05-08 — Same title here
- **Trigger**: second trigger
- **Rule**: second rule
- **Why**: second why
- **Tags**: []
"""
        p = _write_md(tmp_path, content)
        entries = parse_lessons_md(p)
        assert len(entries) == 2
        assert entries[0].id != entries[1].id

    def test_em_dash_heading_parsed(self, tmp_path):
        content = """\
## Lessons

### 2026-05-10 — Entry with em dash
- **Trigger**: em dash trigger
- **Rule**: em dash rule
- **Why**: em dash why
- **Tags**: [test]
"""
        p = _write_md(tmp_path, content)
        entries = parse_lessons_md(p)
        assert len(entries) == 1
        assert entries[0].title == "Entry with em dash"

    def test_empty_file_returns_empty(self, tmp_path):
        p = _write_md(tmp_path, "")
        entries = parse_lessons_md(p)
        assert entries == []


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------


class TestMerge:
    def _entry(self, **kwargs) -> LessonEntry:
        defaults = dict(
            id="L-test",
            date="2026-05-10",
            title="test lesson",
            trigger="test trigger",
            rule="test rule",
            why="test why",
            tags=["test"],
        )
        defaults.update(kwargs)
        return LessonEntry(**defaults)

    def test_new_entry_gets_default_fields(self):
        entry = self._entry()
        records = merge([entry], [])
        assert records[0]["stage"] == []
        assert records[0]["project_types"] == []
        assert records[0]["frequency"] == 0
        assert records[0]["last_used"] is None

    def test_preserves_stage_from_existing(self):
        entry = self._entry()
        existing = [{"title": "test lesson", "trigger": "test trigger",
                     "stage": [6], "project_types": [], "frequency": 3, "last_used": "2026-05-01"}]
        records = merge([entry], existing)
        assert records[0]["stage"] == [6]

    def test_preserves_project_types_from_existing(self):
        entry = self._entry()
        existing = [{"title": "test lesson", "trigger": "test trigger",
                     "stage": [], "project_types": ["ml-pipeline"], "frequency": 0, "last_used": None}]
        records = merge([entry], existing)
        assert records[0]["project_types"] == ["ml-pipeline"]

    def test_preserves_frequency_from_existing(self):
        entry = self._entry()
        existing = [{"title": "test lesson", "trigger": "test trigger",
                     "stage": [], "project_types": [], "frequency": 7, "last_used": "2026-05-10"}]
        records = merge([entry], existing)
        assert records[0]["frequency"] == 7

    def test_preserves_last_used_from_existing(self):
        entry = self._entry()
        existing = [{"title": "test lesson", "trigger": "test trigger",
                     "stage": [], "project_types": [], "frequency": 0, "last_used": "2026-04-01"}]
        records = merge([entry], existing)
        assert records[0]["last_used"] == "2026-04-01"

    def test_matches_by_trigger_similarity(self):
        entry = self._entry(title="slightly different title", trigger="test trigger text")
        existing = [{"title": "other title", "trigger": "test trigger text",
                     "stage": [3], "project_types": [], "frequency": 5, "last_used": None}]
        records = merge([entry], existing)
        assert records[0]["stage"] == [3]
        assert records[0]["frequency"] == 5

    def test_no_existing_match_uses_defaults(self):
        entry = self._entry(title="completely new lesson", trigger="brand new trigger")
        existing = [{"title": "unrelated", "trigger": "different",
                     "stage": [1], "project_types": ["fullstack"], "frequency": 10, "last_used": "2026-01-01"}]
        records = merge([entry], existing)
        assert records[0]["stage"] == []
        assert records[0]["frequency"] == 0

    def test_content_fields_taken_from_entry_not_existing(self):
        entry = self._entry(rule="updated rule text")
        existing = [{"title": "test lesson", "trigger": "test trigger",
                     "rule": "old rule", "stage": [], "project_types": [], "frequency": 0, "last_used": None}]
        records = merge([entry], existing)
        assert records[0]["rule"] == "updated rule text"

    def test_empty_entries_returns_empty(self):
        assert merge([], []) == []


# ---------------------------------------------------------------------------
# sync (integration)
# ---------------------------------------------------------------------------


class TestSync:
    def test_writes_lessons_yaml(self, tmp_path):
        p = _write_md(tmp_path, _BASIC_MD)
        out = tmp_path / ".forge" / "lessons.yaml"
        sync(p, out)
        assert out.exists()

    def test_creates_forge_dir(self, tmp_path):
        p = _write_md(tmp_path, _BASIC_MD)
        out = tmp_path / ".forge" / "lessons.yaml"
        assert not out.parent.exists()
        sync(p, out)
        assert out.parent.exists()

    def test_output_is_valid_yaml(self, tmp_path):
        p = _write_md(tmp_path, _BASIC_MD)
        out = tmp_path / ".forge" / "lessons.yaml"
        sync(p, out)
        data = yaml.safe_load(out.read_text())
        assert data["schema_version"] == 1
        assert isinstance(data["lessons"], list)

    def test_output_has_correct_lesson_count(self, tmp_path):
        p = _write_md(tmp_path, _BASIC_MD)
        out = tmp_path / ".forge" / "lessons.yaml"
        records = sync(p, out)
        assert len(records) == 2

    def test_dry_run_does_not_write(self, tmp_path, capsys):
        p = _write_md(tmp_path, _BASIC_MD)
        out = tmp_path / ".forge" / "lessons.yaml"
        sync(p, out, dry_run=True)
        assert not out.exists()

    def test_dry_run_prints_yaml(self, tmp_path, capsys):
        p = _write_md(tmp_path, _BASIC_MD)
        out = tmp_path / ".forge" / "lessons.yaml"
        sync(p, out, dry_run=True)
        captured = capsys.readouterr()
        assert "lessons:" in captured.out

    def test_preserves_enrichment_on_second_run(self, tmp_path):
        p = _write_md(tmp_path, _BASIC_MD)
        out = tmp_path / ".forge" / "lessons.yaml"
        # First sync — write defaults
        sync(p, out)
        # Manually enrich
        data = yaml.safe_load(out.read_text())
        data["lessons"][0]["stage"] = [6]
        data["lessons"][0]["frequency"] = 5
        out.write_text(yaml.dump(data))
        # Second sync — should preserve enrichment
        records = sync(p, out)
        assert records[0]["stage"] == [6]
        assert records[0]["frequency"] == 5


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCLI:
    def test_cwd_flag(self, tmp_path):
        _write_md(tmp_path, _BASIC_MD)
        (tmp_path / ".forge").mkdir()
        r = _run_cli(["--cwd", str(tmp_path)])
        assert r.returncode == 0
        assert (tmp_path / ".forge" / "lessons.yaml").exists()

    def test_input_output_flags(self, tmp_path):
        p = _write_md(tmp_path, _BASIC_MD)
        out = tmp_path / "custom_output.yaml"
        r = _run_cli(["--input", str(p), "--output", str(out)])
        assert r.returncode == 0
        assert out.exists()

    def test_dry_run_flag_no_write(self, tmp_path):
        p = _write_md(tmp_path, _BASIC_MD)
        out = tmp_path / ".forge" / "lessons.yaml"
        r = _run_cli(["--input", str(p), "--output", str(out), "--dry-run"])
        assert r.returncode == 0
        assert not out.exists()

    def test_dry_run_prints_yaml(self, tmp_path):
        p = _write_md(tmp_path, _BASIC_MD)
        out = tmp_path / ".forge" / "lessons.yaml"
        r = _run_cli(["--input", str(p), "--output", str(out), "--dry-run"])
        assert "lessons:" in r.stdout

    def test_missing_input_exits_0(self, tmp_path):
        r = _run_cli(["--input", str(tmp_path / "nonexistent.md"),
                      "--output", str(tmp_path / ".forge" / "lessons.yaml")])
        assert r.returncode == 0

    def test_output_yaml_is_parseable(self, tmp_path):
        p = _write_md(tmp_path, _BASIC_MD)
        out = tmp_path / ".forge" / "lessons.yaml"
        _run_cli(["--input", str(p), "--output", str(out)])
        data = yaml.safe_load(out.read_text())
        assert "lessons" in data


# ---------------------------------------------------------------------------
# Done-when: edit lessons.md → sync → lessons.yaml updated
# ---------------------------------------------------------------------------


class TestDoneWhenCriterion:
    def test_edit_lessons_md_reflects_in_yaml(self, tmp_path):
        # Initial state
        initial = """\
## Lessons

### 2026-05-07 — Original lesson
- **Trigger**: original trigger text
- **Rule**: original rule text
- **Why**: original why text
- **Tags**: [python]
"""
        p = _write_md(tmp_path, initial)
        out = tmp_path / ".forge" / "lessons.yaml"
        sync(p, out)

        data = yaml.safe_load(out.read_text())
        assert len(data["lessons"]) == 1

        # Edit lessons.md — add a new lesson
        updated = initial + """\

### 2026-05-10 — New lesson added later
- **Trigger**: new trigger after edit
- **Rule**: new rule after edit
- **Why**: new why text
- **Tags**: [testing]
"""
        p.write_text(updated, encoding="utf-8")
        sync(p, out)

        data = yaml.safe_load(out.read_text())
        assert len(data["lessons"]) == 2
        triggers = [l["trigger"] for l in data["lessons"]]
        assert any("new trigger" in t for t in triggers)

    def test_session_start_triggers_sync_when_stale(self, tmp_path):
        """session-start.py regenerates lessons.yaml when lessons.md is newer."""
        import datetime
        import json as json_mod

        # Create a Forge project state
        (tmp_path / "pipeline").mkdir(parents=True)
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        (tmp_path / "pipeline" / "state.md").write_text(
            f"---\nschema_version: 1\nproject_type: fullstack\ncycle: 1\n"
            f"current_stage: 6\ncurrent_task: null\ncurrent_milestone: null\n"
            f"total_tasks: null\nlast_updated: {now}\nblockers: []\n---\n\n"
            "# Pipeline State\n\n## Stage History\n\n## Last Reflection\n"
        )

        # Write lessons.md
        (tmp_path / "tasks").mkdir()
        (tmp_path / "tasks" / "lessons.md").write_text(
            """\
## Lessons

### 2026-05-10 — GPU memory lesson for ML
- **Trigger**: GPU out-of-memory during training
- **Rule**: set PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
- **Why**: prevents fragmentation OOM
- **Tags**: [gpu, ml]
""",
            encoding="utf-8",
        )

        # Ensure no lessons.yaml exists yet
        forge_dir = tmp_path / ".forge"
        forge_dir.mkdir()
        lessons_yaml = forge_dir / "lessons.yaml"
        assert not lessons_yaml.exists()

        # Run session-start.py
        hook = str(Path(__file__).parent.parent.parent / "hooks" / "session-start.py")
        payload = json_mod.dumps({"cwd": str(tmp_path)})
        r = subprocess.run(
            [_PYTHON, hook],
            input=payload,
            capture_output=True,
            text=True,
        )

        assert r.returncode == 0
        # lessons.yaml should now exist (created by sync)
        assert lessons_yaml.exists()
        data = yaml.safe_load(lessons_yaml.read_text())
        assert len(data["lessons"]) == 1
        assert "GPU" in data["lessons"][0]["trigger"]
