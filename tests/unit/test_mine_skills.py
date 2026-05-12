"""Unit tests for scripts/mine-skills.py.

mine-skills.py has a hyphen in its filename, so we load it via importlib
(see tasks/lessons.md 2026-05-07 — hyphenated script filenames).
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "mine-skills.py"
PYTHON = sys.executable


_spec = importlib.util.spec_from_file_location("mine_skills", SCRIPT_PATH)
assert _spec and _spec.loader
mine_skills = importlib.util.module_from_spec(_spec)
sys.modules["mine_skills"] = mine_skills  # @dataclass needs the module in sys.modules
_spec.loader.exec_module(mine_skills)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_patterns(tmp_path: Path, records: list[dict]) -> Path:
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True, exist_ok=True)
    p = forge / "patterns.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    return p


def _entry(
    sig: str = "abc123abc123",
    tools: list[str] | None = None,
    ts: str = "2026-05-12T18:00:00Z",
    session: str = "s1",
) -> dict:
    return {
        "ts": ts,
        "session": session,
        "kind": "tool_seq_3",
        "tools": tools if tools is not None else ["Read", "Edit", "Bash"],
        "signature": sig,
    }


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, str(SCRIPT_PATH), *args],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Slug + helpers
# ---------------------------------------------------------------------------


def test_short_tool_name_plain():
    assert mine_skills._short_tool_name("Read") == "read"


def test_short_tool_name_mcp_strips_prefix():
    assert mine_skills._short_tool_name("mcp__plugin_foo__do_thing") == "do-thing"


def test_short_tool_name_collapses_punctuation():
    assert mine_skills._short_tool_name("Tool With Spaces!") == "tool-with-spaces"


def test_slug_from_tools_joins_with_dashes():
    assert mine_skills.slug_from_tools(["Read", "Edit", "Bash"]) == "forge-read-edit-bash"


def test_slug_from_tools_handles_mcp():
    assert (
        mine_skills.slug_from_tools(["Read", "mcp__plugin_x__do_thing", "Bash"])
        == "forge-read-do-thing-bash"
    )


# ---------------------------------------------------------------------------
# parse_patterns + aggregate
# ---------------------------------------------------------------------------


def test_parse_patterns_missing_file_returns_empty(tmp_path: Path):
    records = mine_skills.parse_patterns(tmp_path / "nope.jsonl")
    assert records == []


def test_parse_patterns_skips_malformed_lines(tmp_path: Path):
    p = tmp_path / "patterns.jsonl"
    p.write_text("not-json\n" + json.dumps(_entry()) + "\n\n", encoding="utf-8")
    records = mine_skills.parse_patterns(p)
    assert len(records) == 1
    assert records[0].signature == "abc123abc123"


def test_parse_patterns_skips_records_missing_signature(tmp_path: Path):
    p = tmp_path / "patterns.jsonl"
    bad = {"ts": "2026-05-12T18:00:00Z", "session": "s1", "tools": ["Read", "Edit", "Bash"]}
    p.write_text(json.dumps(bad) + "\n" + json.dumps(_entry()) + "\n", encoding="utf-8")
    records = mine_skills.parse_patterns(p)
    assert len(records) == 1


def test_parse_patterns_session_filter(tmp_path: Path):
    p = _write_patterns(
        tmp_path,
        [_entry(session="s1"), _entry(session="s2"), _entry(session="s1")],
    )
    records = mine_skills.parse_patterns(p, session="s1")
    assert len(records) == 2
    assert all(r.session == "s1" for r in records)


def test_aggregate_counts_by_signature():
    records = [
        mine_skills.PatternRecord(ts="2026-05-12T18:00:00Z", session="s1",
                                  tools=["Read", "Edit", "Bash"], signature="aaa"),
        mine_skills.PatternRecord(ts="2026-05-12T18:01:00Z", session="s1",
                                  tools=["Read", "Edit", "Bash"], signature="aaa"),
        mine_skills.PatternRecord(ts="2026-05-12T18:02:00Z", session="s2",
                                  tools=["Glob", "Grep"], signature="bbb"),
    ]
    groups = mine_skills.aggregate(records)
    assert set(groups) == {"aaa", "bbb"}
    assert groups["aaa"].count == 2
    assert groups["bbb"].count == 1
    assert groups["aaa"].sessions == ["s1"]


def test_aggregate_tracks_first_and_last_seen():
    records = [
        mine_skills.PatternRecord(ts="2026-05-12T18:02:00Z", session="s1",
                                  tools=["A", "B", "C"], signature="x"),
        mine_skills.PatternRecord(ts="2026-05-12T18:00:00Z", session="s1",
                                  tools=["A", "B", "C"], signature="x"),
        mine_skills.PatternRecord(ts="2026-05-12T18:05:00Z", session="s2",
                                  tools=["A", "B", "C"], signature="x"),
    ]
    groups = mine_skills.aggregate(records)
    assert groups["x"].first_seen == "2026-05-12T18:00:00Z"
    assert groups["x"].last_seen == "2026-05-12T18:05:00Z"
    assert groups["x"].sessions == ["s1", "s2"]


# ---------------------------------------------------------------------------
# Blacklist + existing skill names
# ---------------------------------------------------------------------------


def test_blacklist_missing_file_returns_empty_set(tmp_path: Path):
    assert mine_skills.load_blacklist(tmp_path / "nope.txt") == set()


def test_blacklist_skips_comments_and_blanks(tmp_path: Path):
    p = tmp_path / "skill-blacklist.txt"
    p.write_text("# a comment\nsig-one\n\n  sig-two  \n", encoding="utf-8")
    assert mine_skills.load_blacklist(p) == {"sig-one", "sig-two"}


def test_existing_skill_names_finds_frontmatter(tmp_path: Path):
    skills = tmp_path / "skills"
    (skills / "alpha").mkdir(parents=True)
    (skills / "alpha" / "SKILL.md").write_text(
        "---\nname: forge-alpha\ndescription: x\n---\n# alpha\n", encoding="utf-8"
    )
    (skills / "beta").mkdir(parents=True)
    (skills / "beta" / "SKILL.md").write_text(
        "---\nname: forge-beta\n---\nbody\n", encoding="utf-8"
    )
    names = mine_skills.load_existing_skill_names(tmp_path)
    assert names == {"forge-alpha", "forge-beta"}


# ---------------------------------------------------------------------------
# plan_proposals — filtering logic
# ---------------------------------------------------------------------------


def _candidate(sig: str, tools: list[str], count: int) -> mine_skills.Candidate:
    return mine_skills.Candidate(
        signature=sig, tools=tools, count=count,
        first_seen="2026-05-12T18:00:00Z", last_seen="2026-05-12T18:05:00Z",
        sessions=["s1"],
    )


def test_plan_proposals_default_threshold(tmp_path: Path):
    cands = {
        "sig-3": _candidate("sig-3", ["Read", "Edit", "Bash"], 3),
        "sig-2": _candidate("sig-2", ["Read", "Edit", "Glob"], 2),
    }
    plans = mine_skills.plan_proposals(
        cands, threshold=3, blacklist=set(), existing_names=set(),
        proposed_root=tmp_path / "proposed-skills",
    )
    assert len(plans) == 1
    assert plans[0].signature == "sig-3"


def test_plan_proposals_custom_threshold_promotes_two(tmp_path: Path):
    cands = {"sig-2": _candidate("sig-2", ["A", "B", "C"], 2)}
    plans = mine_skills.plan_proposals(
        cands, threshold=2, blacklist=set(), existing_names=set(),
        proposed_root=tmp_path / "proposed-skills",
    )
    assert len(plans) == 1


def test_plan_proposals_blacklist_skips(tmp_path: Path):
    cands = {"sig-3": _candidate("sig-3", ["Read", "Edit", "Bash"], 3)}
    plans = mine_skills.plan_proposals(
        cands, threshold=3, blacklist={"sig-3"}, existing_names=set(),
        proposed_root=tmp_path / "proposed-skills",
    )
    assert plans == []


def test_plan_proposals_existing_name_collision_skips(tmp_path: Path):
    cands = {"sig-3": _candidate("sig-3", ["Read", "Edit", "Bash"], 3)}
    plans = mine_skills.plan_proposals(
        cands, threshold=3, blacklist=set(),
        existing_names={"forge-read-edit-bash"},
        proposed_root=tmp_path / "proposed-skills",
    )
    assert plans == []


# ---------------------------------------------------------------------------
# Render: SKILL.md draft shape
# ---------------------------------------------------------------------------


def test_render_skill_md_contains_required_fields():
    c = _candidate("sig-3", ["Read", "Edit", "Bash"], 3)
    out = mine_skills.render_skill_md("forge-read-edit-bash", c)
    assert out.startswith("---\n")
    assert "name: forge-read-edit-bash" in out
    assert "description:" in out
    assert "## Steps" in out
    assert "## When to Use" in out
    assert "## Provenance" in out
    assert "sig-3" in out
    assert "Occurrences: 3" in out


# ---------------------------------------------------------------------------
# End-to-end CLI (done-when criterion + integration scenarios)
# ---------------------------------------------------------------------------


def test_done_when_three_occurrences_produces_draft(tmp_path: Path):
    """T-027 done-when: frequency=3 → SKILL.md draft with name, description, steps."""
    _write_patterns(tmp_path, [_entry(sig="aaaaaaaa1111")] * 3)
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    result = _run_cli("--cwd", str(tmp_path), "--plugin-dir", str(plugin_dir))
    assert result.returncode == 1, result.stderr
    drafts = list((tmp_path / ".forge" / "proposed-skills").glob("*/SKILL.md"))
    assert len(drafts) == 1
    content = drafts[0].read_text(encoding="utf-8")
    assert "name: forge-read-edit-bash" in content
    assert "description:" in content
    assert "## Steps" in content


def test_frequency_two_no_proposal(tmp_path: Path):
    _write_patterns(tmp_path, [_entry()] * 2)
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    result = _run_cli("--cwd", str(tmp_path), "--plugin-dir", str(plugin_dir))
    assert result.returncode == 0
    assert not (tmp_path / ".forge" / "proposed-skills").exists()


def test_custom_threshold_two_promotes(tmp_path: Path):
    _write_patterns(tmp_path, [_entry()] * 2)
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    result = _run_cli(
        "--cwd", str(tmp_path), "--plugin-dir", str(plugin_dir), "--threshold", "2"
    )
    assert result.returncode == 1
    assert list((tmp_path / ".forge" / "proposed-skills").glob("*/SKILL.md"))


def test_empty_patterns_file_exits_zero(tmp_path: Path):
    (tmp_path / ".forge").mkdir()
    (tmp_path / ".forge" / "patterns.jsonl").write_text("", encoding="utf-8")
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    result = _run_cli("--cwd", str(tmp_path), "--plugin-dir", str(plugin_dir))
    assert result.returncode == 0
    assert result.stdout == ""


def test_missing_patterns_file_exits_zero(tmp_path: Path):
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    result = _run_cli("--cwd", str(tmp_path), "--plugin-dir", str(plugin_dir))
    assert result.returncode == 0


def test_two_distinct_signatures_both_qualify(tmp_path: Path):
    _write_patterns(
        tmp_path,
        [_entry(sig="aaa", tools=["Read", "Edit", "Bash"])] * 3
        + [_entry(sig="bbb", tools=["Glob", "Grep", "Read"])] * 3,
    )
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    result = _run_cli("--cwd", str(tmp_path), "--plugin-dir", str(plugin_dir))
    assert result.returncode == 2
    drafts = sorted((tmp_path / ".forge" / "proposed-skills").glob("*/SKILL.md"))
    assert len(drafts) == 2


def test_blacklist_signature_skipped(tmp_path: Path):
    _write_patterns(tmp_path, [_entry(sig="blacklisted-sig")] * 3)
    (tmp_path / ".forge" / "skill-blacklist.txt").write_text(
        "# rejected by user\nblacklisted-sig\n", encoding="utf-8"
    )
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    result = _run_cli("--cwd", str(tmp_path), "--plugin-dir", str(plugin_dir))
    assert result.returncode == 0
    assert not (tmp_path / ".forge" / "proposed-skills").exists()


def test_existing_skill_collision_skipped(tmp_path: Path):
    _write_patterns(tmp_path, [_entry()] * 3)
    plugin_dir = tmp_path / "plugin"
    skill = plugin_dir / "skills" / "forge-read-edit-bash"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: forge-read-edit-bash\ndescription: pre-existing\n---\n",
        encoding="utf-8",
    )
    result = _run_cli("--cwd", str(tmp_path), "--plugin-dir", str(plugin_dir))
    assert result.returncode == 0
    assert not (tmp_path / ".forge" / "proposed-skills").exists()


def test_dry_run_prints_but_writes_nothing(tmp_path: Path):
    _write_patterns(tmp_path, [_entry()] * 3)
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    result = _run_cli(
        "--cwd", str(tmp_path), "--plugin-dir", str(plugin_dir), "--dry-run"
    )
    assert result.returncode == 1
    assert "SKILL.md" in result.stdout
    assert not (tmp_path / ".forge" / "proposed-skills").exists()


def test_session_filter_narrows_count(tmp_path: Path):
    _write_patterns(
        tmp_path,
        [
            _entry(session="s1"),
            _entry(session="s2"),
            _entry(session="s2"),
        ],
    )
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    # Default threshold 3, only 1 in s1 — no proposal
    result_s1 = _run_cli(
        "--cwd", str(tmp_path), "--plugin-dir", str(plugin_dir), "--session", "s1"
    )
    assert result_s1.returncode == 0
    # Threshold 2 in s2 promotes
    result_s2 = _run_cli(
        "--cwd", str(tmp_path), "--plugin-dir", str(plugin_dir),
        "--session", "s2", "--threshold", "2",
    )
    assert result_s2.returncode == 1


def test_stdout_lists_written_paths(tmp_path: Path):
    _write_patterns(tmp_path, [_entry()] * 3)
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    result = _run_cli("--cwd", str(tmp_path), "--plugin-dir", str(plugin_dir))
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1
    assert lines[0].endswith("SKILL.md")
    assert Path(lines[0]).exists()


def test_idempotent_rerun(tmp_path: Path):
    _write_patterns(tmp_path, [_entry()] * 3)
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    r1 = _run_cli("--cwd", str(tmp_path), "--plugin-dir", str(plugin_dir))
    r2 = _run_cli("--cwd", str(tmp_path), "--plugin-dir", str(plugin_dir))
    # First run writes 1 (exit 1). Second run skips existing (exit 0).
    assert r1.returncode == 1
    assert r2.returncode == 0
    drafts = list((tmp_path / ".forge" / "proposed-skills").glob("*/SKILL.md"))
    assert len(drafts) == 1


def test_existing_proposal_preserves_user_edits(tmp_path: Path):
    """T-028 hand-off: user edits the proposal; re-mining must not clobber them."""
    _write_patterns(tmp_path, [_entry()] * 3)
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    _run_cli("--cwd", str(tmp_path), "--plugin-dir", str(plugin_dir))
    draft = next((tmp_path / ".forge" / "proposed-skills").glob("*/SKILL.md"))
    draft.write_text("EDITED BY USER\n", encoding="utf-8")
    # Re-run: must skip and not overwrite the edited content
    _run_cli("--cwd", str(tmp_path), "--plugin-dir", str(plugin_dir))
    assert draft.read_text(encoding="utf-8") == "EDITED BY USER\n"


def test_malformed_lines_skipped_in_e2e(tmp_path: Path):
    (tmp_path / ".forge").mkdir()
    (tmp_path / ".forge" / "patterns.jsonl").write_text(
        "this is not json\n"
        + json.dumps(_entry()) + "\n"
        + json.dumps(_entry()) + "\n"
        + "{partial json\n"
        + json.dumps(_entry()) + "\n",
        encoding="utf-8",
    )
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    result = _run_cli("--cwd", str(tmp_path), "--plugin-dir", str(plugin_dir))
    # 3 valid records of same signature → 1 proposal
    assert result.returncode == 1


def test_mcp_tool_names_slug_correctly(tmp_path: Path):
    _write_patterns(
        tmp_path,
        [_entry(sig="mcpsig", tools=["Read", "mcp__plugin_x__do_thing", "Bash"])] * 3,
    )
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    result = _run_cli("--cwd", str(tmp_path), "--plugin-dir", str(plugin_dir))
    assert result.returncode == 1
    drafts = list((tmp_path / ".forge" / "proposed-skills").glob("*/SKILL.md"))
    assert len(drafts) == 1
    assert drafts[0].parent.name == "forge-read-do-thing-bash"
