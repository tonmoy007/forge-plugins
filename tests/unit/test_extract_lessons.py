"""Tests for scripts/extract-lessons.py (T-019)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# Hyphenated filename — must use importlib
_SCRIPT = Path(__file__).parent.parent.parent / "scripts" / "extract-lessons.py"
spec = importlib.util.spec_from_file_location("extract_lessons", _SCRIPT)
_mod = importlib.util.module_from_spec(spec)
sys.modules["extract_lessons"] = _mod  # @dataclass needs the module in sys.modules
spec.loader.exec_module(_mod)

CorrectionFlag = _mod.CorrectionFlag
Lesson = _mod.Lesson
parse_flags = _mod.parse_flags
extract_lesson = _mod.extract_lesson
format_lesson = _mod.format_lesson
append_lessons = _mod.append_lessons
_is_duplicate = _mod._is_duplicate
_load_existing_titles = _mod._load_existing_titles
main = _mod.main


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_FLAG = CorrectionFlag(
    ts="2026-05-11T09:00:00Z",
    session="test",
    prompt=(
        "don't use subprocess here, use importlib.util instead "
        "because Python can't import hyphenated filenames"
    ),
)


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")


# ---------------------------------------------------------------------------
# parse_flags
# ---------------------------------------------------------------------------


class TestParseFlags:
    def test_missing_file_returns_empty(self, tmp_path):
        result = parse_flags(tmp_path / "missing.jsonl")
        assert result == []

    def test_valid_records_parsed(self, tmp_path):
        p = tmp_path / "flags.jsonl"
        _write_jsonl(p, [
            {"ts": "2026-05-11T09:00:00Z", "session": "s1", "prompt": "don't do X"},
            {"ts": "2026-05-11T10:00:00Z", "session": "s2", "prompt": "always use Y"},
        ])
        flags = parse_flags(p)
        assert len(flags) == 2
        assert flags[0].session == "s1"
        assert flags[1].prompt == "always use Y"

    def test_malformed_json_line_skipped(self, tmp_path):
        p = tmp_path / "flags.jsonl"
        p.write_text('{"ts": "2026-05-11T09:00:00Z", "session": "s1", "prompt": "ok"}\n'
                     'NOT JSON\n'
                     '{"ts": "2026-05-11T11:00:00Z", "session": "s2", "prompt": "fine"}\n')
        flags = parse_flags(p)
        assert len(flags) == 2
        assert flags[0].prompt == "ok"
        assert flags[1].prompt == "fine"

    def test_missing_key_line_skipped(self, tmp_path):
        p = tmp_path / "flags.jsonl"
        _write_jsonl(p, [
            {"ts": "2026-05-11T09:00:00Z", "session": "s1"},  # missing prompt
            {"ts": "2026-05-11T10:00:00Z", "session": "s2", "prompt": "ok"},
        ])
        flags = parse_flags(p)
        assert len(flags) == 1
        assert flags[0].prompt == "ok"

    def test_since_filter_excludes_older(self, tmp_path):
        p = tmp_path / "flags.jsonl"
        _write_jsonl(p, [
            {"ts": "2026-05-09T09:00:00Z", "session": "old", "prompt": "old"},
            {"ts": "2026-05-11T09:00:00Z", "session": "new", "prompt": "new"},
        ])
        flags = parse_flags(p, since="2026-05-10")
        assert len(flags) == 1
        assert flags[0].session == "new"

    def test_since_filter_includes_exact_date(self, tmp_path):
        p = tmp_path / "flags.jsonl"
        _write_jsonl(p, [
            {"ts": "2026-05-10T00:00:00Z", "session": "s1", "prompt": "edge"},
        ])
        flags = parse_flags(p, since="2026-05-10")
        assert len(flags) == 1

    def test_empty_lines_ignored(self, tmp_path):
        p = tmp_path / "flags.jsonl"
        p.write_text('\n\n{"ts": "2026-05-11T09:00:00Z", "session": "s1", "prompt": "x"}\n\n')
        flags = parse_flags(p)
        assert len(flags) == 1


# ---------------------------------------------------------------------------
# extract_lesson — rule-based patterns
# ---------------------------------------------------------------------------


class TestExtractLessonRuleBased:
    def test_dont_pattern(self):
        flag = CorrectionFlag("2026-05-11T09:00:00Z", "s", "don't edit files blindly")
        lesson = extract_lesson(flag)
        assert lesson is not None
        assert lesson.rule.startswith("Don't edit files")

    def test_never_pattern(self):
        flag = CorrectionFlag("2026-05-11T09:00:00Z", "s", "never hardcode secrets")
        lesson = extract_lesson(flag)
        assert lesson is not None
        assert "hardcode secrets" in lesson.rule

    def test_stop_pattern(self):
        flag = CorrectionFlag("2026-05-11T09:00:00Z", "s", "stop using print in hooks")
        lesson = extract_lesson(flag)
        assert lesson is not None
        assert lesson.rule.startswith("Don't")

    def test_always_pattern(self):
        flag = CorrectionFlag("2026-05-11T09:00:00Z", "s", "always run tests before committing")
        lesson = extract_lesson(flag)
        assert lesson is not None
        assert lesson.rule.startswith("Always")
        assert "tests" in lesson.rule

    def test_prefer_pattern(self):
        flag = CorrectionFlag("2026-05-11T09:00:00Z", "s", "prefer rg over grep -r")
        lesson = extract_lesson(flag)
        assert lesson is not None
        assert lesson.rule.startswith("Always")

    def test_use_instead_of_pattern(self):
        flag = CorrectionFlag("2026-05-11T09:00:00Z", "s", "use pathlib instead of os.path")
        lesson = extract_lesson(flag)
        assert lesson is not None
        assert "pathlib" in lesson.rule

    def test_use_not_pattern(self):
        flag = CorrectionFlag("2026-05-11T09:00:00Z", "s", "use python3 not python")
        lesson = extract_lesson(flag)
        assert lesson is not None
        assert "python3" in lesson.rule

    def test_unrecognised_prompt_returns_none(self):
        flag = CorrectionFlag("2026-05-11T09:00:00Z", "s", "the sky is blue today")
        lesson = extract_lesson(flag)
        assert lesson is None

    def test_because_clause_becomes_why(self):
        flag = CorrectionFlag(
            "2026-05-11T09:00:00Z", "s",
            "don't use subprocess because it has no coverage"
        )
        lesson = extract_lesson(flag)
        assert lesson is not None
        assert "coverage" in lesson.why
        assert lesson.why != "Prevents repeating this mistake"

    def test_otherwise_clause_becomes_why(self):
        flag = CorrectionFlag(
            "2026-05-11T09:00:00Z", "s",
            "always quote paths otherwise spaces break the command"
        )
        lesson = extract_lesson(flag)
        assert lesson is not None
        assert "spaces" in lesson.why.lower()

    def test_no_because_gives_default_why(self):
        flag = CorrectionFlag("2026-05-11T09:00:00Z", "s", "don't use bare except")
        lesson = extract_lesson(flag)
        assert lesson is not None
        assert lesson.why == "Prevents repeating this mistake"

    def test_dont_with_use_instead_combines_rule(self):
        lesson = extract_lesson(SAMPLE_FLAG)
        assert lesson is not None
        assert "Don't use subprocess" in lesson.rule
        assert "importlib.util" in lesson.rule
        assert "instead" in lesson.rule

    def test_date_extracted_from_ts(self):
        lesson = extract_lesson(SAMPLE_FLAG)
        assert lesson is not None
        assert lesson.date == "2026-05-11"

    def test_title_truncated_to_60_chars(self):
        long_prompt = "don't " + "x" * 80
        flag = CorrectionFlag("2026-05-11T09:00:00Z", "s", long_prompt)
        lesson = extract_lesson(flag)
        assert lesson is not None
        assert len(lesson.title) <= 60

    def test_trigger_default_value(self):
        lesson = extract_lesson(SAMPLE_FLAG)
        assert lesson is not None
        assert lesson.trigger == "When this pattern occurs"


# ---------------------------------------------------------------------------
# extract_lesson — tags
# ---------------------------------------------------------------------------


class TestExtractLessonTags:
    def test_python_keyword_tag(self):
        flag = CorrectionFlag("2026-05-11T09:00:00Z", "s", "don't use Python 2")
        lesson = extract_lesson(flag)
        assert lesson is not None
        assert "python" in lesson.tags

    def test_git_keyword_tag(self):
        flag = CorrectionFlag("2026-05-11T09:00:00Z", "s", "always run git status first")
        lesson = extract_lesson(flag)
        assert lesson is not None
        assert "git" in lesson.tags

    def test_py_filename_tag(self):
        flag = CorrectionFlag("2026-05-11T09:00:00Z", "s", "don't edit state.py directly")
        lesson = extract_lesson(flag)
        assert lesson is not None
        assert "state.py" in lesson.tags

    def test_sample_flag_has_python_tag(self):
        lesson = extract_lesson(SAMPLE_FLAG)
        assert lesson is not None
        assert "python" in lesson.tags


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


class TestDeduplication:
    def test_exact_title_is_duplicate(self):
        assert _is_duplicate("Don't use subprocess", ["Don't use subprocess"]) is True

    def test_similar_title_above_threshold_is_duplicate(self):
        assert _is_duplicate(
            "Don't use subprocess here",
            ["Don't use subprocess"]
        ) is True

    def test_different_title_passes(self):
        assert _is_duplicate(
            "Always run tests first",
            ["Don't use subprocess"]
        ) is False

    def test_empty_existing_never_duplicate(self):
        assert _is_duplicate("Some title", []) is False

    def test_load_existing_titles_parses_headings(self, tmp_path):
        md = tmp_path / "lessons.md"
        md.write_text(
            "## Lessons\n\n"
            "### 2026-05-07 — Python 2 is old\n"
            "- stuff\n"
            "### 2026-05-10 — Always test first\n"
            "- stuff\n"
        )
        titles = _load_existing_titles(md)
        assert "Python 2 is old" in titles
        assert "Always test first" in titles

    def test_load_existing_titles_missing_file(self, tmp_path):
        assert _load_existing_titles(tmp_path / "missing.md") == []


# ---------------------------------------------------------------------------
# format_lesson
# ---------------------------------------------------------------------------


class TestFormatLesson:
    def test_format_matches_expected_structure(self):
        lesson = Lesson(
            date="2026-05-11",
            title="Don't use subprocess; use importlib.util instead",
            trigger="When this pattern occurs",
            rule="Don't use subprocess; use importlib.util instead",
            why="Python can't import hyphenated filenames",
            tags=["python"],
        )
        text = format_lesson(lesson)
        assert text.startswith("### 2026-05-11 — Don't use subprocess")
        assert "- **Trigger**: When this pattern occurs" in text
        assert "- **Rule**: Don't use subprocess; use importlib.util instead" in text
        assert "- **Why**: Python can't import hyphenated filenames" in text
        assert "- **Tags**: [python]" in text

    def test_multiple_tags_comma_separated(self):
        lesson = Lesson("2026-05-11", "Title", "Trigger", "Rule", "Why", ["a", "b"])
        text = format_lesson(lesson)
        assert "[a, b]" in text

    def test_empty_tags(self):
        lesson = Lesson("2026-05-11", "Title", "Trigger", "Rule", "Why", [])
        text = format_lesson(lesson)
        assert "**Tags**: []" in text


# ---------------------------------------------------------------------------
# append_lessons
# ---------------------------------------------------------------------------


class TestAppendLessons:
    def _make_lesson(self, title: str = "Don't do X") -> Lesson:
        return Lesson("2026-05-11", title, "When X", title, "Because Y", ["python"])

    def test_dry_run_does_not_write(self, tmp_path, capsys):
        out = tmp_path / "lessons.md"
        append_lessons(out, [self._make_lesson()], dry_run=True)
        assert not out.exists()
        captured = capsys.readouterr()
        assert "Don't do X" in captured.out

    def test_real_write_creates_file_if_missing(self, tmp_path):
        out = tmp_path / "lessons.md"
        append_lessons(out, [self._make_lesson()])
        assert out.exists()
        assert "Don't do X" in out.read_text()

    def test_real_write_appends_after_lessons_header(self, tmp_path):
        out = tmp_path / "lessons.md"
        out.write_text("# Lessons\n\n## Lessons\n\n## Other\n")
        append_lessons(out, [self._make_lesson()])
        content = out.read_text()
        lessons_pos = content.index("## Lessons")
        entry_pos = content.index("### 2026-05-11")
        other_pos = content.index("## Other")
        assert lessons_pos < entry_pos < other_pos

    def test_no_lessons_does_not_write(self, tmp_path):
        out = tmp_path / "lessons.md"
        append_lessons(out, [])
        assert not out.exists()

    def test_existing_content_preserved(self, tmp_path):
        out = tmp_path / "lessons.md"
        out.write_text("## Lessons\n\n### 2026-01-01 — Old lesson\n- **Rule**: Old\n")
        append_lessons(out, [self._make_lesson("New lesson")])
        content = out.read_text()
        assert "Old lesson" in content
        assert "New lesson" in content


# ---------------------------------------------------------------------------
# End-to-end (done-when criterion)
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_done_when_criterion(self, tmp_path):
        """Spec done-when: sample flag → expected lesson in output."""
        flags_file = tmp_path / "correction-flags.jsonl"
        _write_jsonl(flags_file, [{
            "ts": "2026-05-11T09:00:00Z",
            "session": "test",
            "prompt": (
                "don't use subprocess here, use importlib.util instead "
                "because Python can't import hyphenated filenames"
            ),
        }])
        out = tmp_path / "lessons.md"
        out.write_text("# Lessons\n\n## Lessons\n")

        rc = main([
            "--input", str(flags_file),
            "--output", str(out),
        ])
        assert rc == 0

        content = out.read_text()
        assert "2026-05-11" in content
        assert "Don't use subprocess" in content
        assert "importlib.util" in content
        assert "Python can't import hyphenated filenames" in content
        assert "python" in content

    def test_missing_input_exits_zero(self, tmp_path):
        rc = main([
            "--input", str(tmp_path / "missing.jsonl"),
            "--output", str(tmp_path / "lessons.md"),
        ])
        assert rc == 0

    def test_duplicate_skipped_on_rerun(self, tmp_path):
        flags_file = tmp_path / "flags.jsonl"
        _write_jsonl(flags_file, [{
            "ts": "2026-05-11T09:00:00Z",
            "session": "s",
            "prompt": "don't use subprocess because it lacks coverage",
        }])
        out = tmp_path / "lessons.md"
        out.write_text("# Lessons\n\n## Lessons\n")

        main(["--input", str(flags_file), "--output", str(out)])
        content_after_first = out.read_text()

        main(["--input", str(flags_file), "--output", str(out)])
        content_after_second = out.read_text()

        # Heading should appear exactly once (not duplicated on rerun)
        heading = "### 2026-05-11 — Don't use subprocess"
        assert content_after_first.count(heading) == 1
        assert content_after_second.count(heading) == 1
