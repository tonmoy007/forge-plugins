"""Unit tests for scripts/skill-approval.py.

Loaded via importlib (hyphenated filename) — register in sys.modules
before exec_module, otherwise @dataclass introspection crashes
(see tasks/lessons.md 2026-05-12).
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "skill-approval.py"
PYTHON = sys.executable

_spec = importlib.util.spec_from_file_location("skill_approval", SCRIPT_PATH)
assert _spec and _spec.loader
skill_approval = importlib.util.module_from_spec(_spec)
sys.modules["skill_approval"] = skill_approval
_spec.loader.exec_module(skill_approval)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SAMPLE_SKILL = """\
---
name: forge-read-edit-bash
description: PROPOSED auto-mined. Read → Edit → Bash, 3 occurrences.
status: proposed
---

# forge-read-edit-bash (proposed)

## When to Use
After observing Read → Edit → Bash 3 times.

## Steps
1. Invoke `Read`
2. Invoke `Edit`
3. Invoke `Bash`

## Verification
Replay and confirm.

## Provenance
- Pattern signature: `aaaaaaaaaaaa`
- Occurrences: 3
- First seen: 2026-05-12T18:00:00Z
- Last seen: 2026-05-12T18:00:02Z
- Sessions: s1
"""


def _make_proposal(tmp_path: Path, slug: str = "forge-read-edit-bash",
                   content: str = _SAMPLE_SKILL) -> Path:
    d = tmp_path / ".forge" / "proposed-skills" / slug
    d.mkdir(parents=True)
    p = d / "SKILL.md"
    p.write_text(content, encoding="utf-8")
    return p


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, str(SCRIPT_PATH), *args],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def test_parse_proposal_extracts_name_signature_and_description(tmp_path: Path):
    p = _make_proposal(tmp_path)
    parsed = skill_approval._parse_proposal(p)
    assert parsed is not None
    assert parsed.slug == "forge-read-edit-bash"
    assert parsed.name == "forge-read-edit-bash"
    assert parsed.signature == "aaaaaaaaaaaa"
    assert "Read" in parsed.description


def test_parse_proposal_returns_none_when_signature_missing(tmp_path: Path):
    bad = _SAMPLE_SKILL.replace("Pattern signature: `aaaaaaaaaaaa`", "Pattern signature: missing")
    p = _make_proposal(tmp_path, content=bad)
    assert skill_approval._parse_proposal(p) is None


def test_parse_proposal_returns_none_when_name_missing(tmp_path: Path):
    bad = _SAMPLE_SKILL.replace("name: forge-read-edit-bash\n", "")
    p = _make_proposal(tmp_path, content=bad)
    assert skill_approval._parse_proposal(p) is None


# ---------------------------------------------------------------------------
# list_pending
# ---------------------------------------------------------------------------


def test_list_pending_empty_when_no_directory(tmp_path: Path):
    assert skill_approval.list_pending(tmp_path) == []


def test_list_pending_returns_sorted_slugs(tmp_path: Path):
    _make_proposal(tmp_path, slug="forge-bbb")
    _make_proposal(tmp_path, slug="forge-aaa")
    results = skill_approval.list_pending(tmp_path)
    slugs = [r.slug for r in results]
    assert slugs == ["forge-aaa", "forge-bbb"]


def test_list_pending_skips_unparseable(tmp_path: Path):
    _make_proposal(tmp_path, slug="forge-good")
    bad_dir = tmp_path / ".forge" / "proposed-skills" / "forge-bad"
    bad_dir.mkdir(parents=True)
    (bad_dir / "SKILL.md").write_text("not a valid proposal\n", encoding="utf-8")
    results = skill_approval.list_pending(tmp_path)
    assert [r.slug for r in results] == ["forge-good"]


# ---------------------------------------------------------------------------
# Approve
# ---------------------------------------------------------------------------


def test_approve_moves_proposal_to_skills_dir(tmp_path: Path):
    _make_proposal(tmp_path)
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    dest = skill_approval.approve(tmp_path, "forge-read-edit-bash", plugin_dir)
    assert dest == plugin_dir / "skills" / "forge-read-edit-bash" / "SKILL.md"
    assert dest.exists()
    # Source proposal directory removed
    assert not (tmp_path / ".forge" / "proposed-skills" / "forge-read-edit-bash").exists()


def test_approve_strips_status_proposed_from_frontmatter(tmp_path: Path):
    _make_proposal(tmp_path)
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    dest = skill_approval.approve(tmp_path, "forge-read-edit-bash", plugin_dir)
    content = dest.read_text(encoding="utf-8")
    assert "status: proposed" not in content
    assert "name: forge-read-edit-bash" in content


def test_approve_preserves_user_modifications(tmp_path: Path):
    """Done-when: modifications are persisted."""
    modified = _SAMPLE_SKILL.replace(
        "1. Invoke `Read`", "1. Invoke `Read` with explicit path"
    )
    _make_proposal(tmp_path, content=modified)
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    dest = skill_approval.approve(tmp_path, "forge-read-edit-bash", plugin_dir)
    assert "Invoke `Read` with explicit path" in dest.read_text(encoding="utf-8")


def test_approve_raises_when_slug_missing(tmp_path: Path):
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    try:
        skill_approval.approve(tmp_path, "forge-nope", plugin_dir)
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError")


def test_approve_refuses_to_overwrite_existing_skill(tmp_path: Path):
    _make_proposal(tmp_path)
    plugin_dir = tmp_path / "plugin"
    pre = plugin_dir / "skills" / "forge-read-edit-bash"
    pre.mkdir(parents=True)
    (pre / "SKILL.md").write_text("pre-existing\n", encoding="utf-8")
    try:
        skill_approval.approve(tmp_path, "forge-read-edit-bash", plugin_dir)
    except FileExistsError:
        return
    raise AssertionError("expected FileExistsError")


# ---------------------------------------------------------------------------
# Reject + blacklist
# ---------------------------------------------------------------------------


def test_reject_appends_signature_to_blacklist(tmp_path: Path):
    """Done-when: rejections blacklist pattern."""
    _make_proposal(tmp_path)
    sig = skill_approval.reject(tmp_path, "forge-read-edit-bash")
    assert sig == "aaaaaaaaaaaa"
    blacklist = (tmp_path / ".forge" / "skill-blacklist.txt").read_text(encoding="utf-8")
    assert "aaaaaaaaaaaa" in blacklist


def test_reject_removes_proposal_directory(tmp_path: Path):
    _make_proposal(tmp_path)
    skill_approval.reject(tmp_path, "forge-read-edit-bash")
    assert not (tmp_path / ".forge" / "proposed-skills" / "forge-read-edit-bash").exists()


def test_reject_creates_blacklist_with_header(tmp_path: Path):
    _make_proposal(tmp_path)
    skill_approval.reject(tmp_path, "forge-read-edit-bash")
    blacklist = (tmp_path / ".forge" / "skill-blacklist.txt").read_text(encoding="utf-8")
    assert blacklist.startswith("#")  # header comment line
    assert blacklist.rstrip().endswith("aaaaaaaaaaaa")


def test_reject_preserves_existing_blacklist_entries(tmp_path: Path):
    _make_proposal(tmp_path)
    blacklist_path = tmp_path / ".forge" / "skill-blacklist.txt"
    blacklist_path.parent.mkdir(parents=True, exist_ok=True)
    blacklist_path.write_text("# header\nold-sig\n", encoding="utf-8")
    skill_approval.reject(tmp_path, "forge-read-edit-bash")
    content = blacklist_path.read_text(encoding="utf-8")
    assert "old-sig" in content
    assert "aaaaaaaaaaaa" in content


def test_reject_is_idempotent_on_already_blacklisted_signature(tmp_path: Path):
    """Reject a proposal whose signature is already blacklisted — no duplicate line."""
    blacklist_path = tmp_path / ".forge" / "skill-blacklist.txt"
    blacklist_path.parent.mkdir(parents=True, exist_ok=True)
    blacklist_path.write_text("# header\naaaaaaaaaaaa\n", encoding="utf-8")
    _make_proposal(tmp_path)
    skill_approval.reject(tmp_path, "forge-read-edit-bash")
    content = blacklist_path.read_text(encoding="utf-8")
    assert content.count("aaaaaaaaaaaa") == 1


def test_reject_raises_when_slug_missing(tmp_path: Path):
    try:
        skill_approval.reject(tmp_path, "forge-nope")
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_list_emits_json(tmp_path: Path):
    _make_proposal(tmp_path)
    r = _run_cli("--cwd", str(tmp_path), "list")
    assert r.returncode == 0
    payload = json.loads(r.stdout)
    assert isinstance(payload, list)
    assert payload[0]["slug"] == "forge-read-edit-bash"
    assert payload[0]["signature"] == "aaaaaaaaaaaa"


def test_cli_list_emits_empty_array_when_no_proposals(tmp_path: Path):
    r = _run_cli("--cwd", str(tmp_path), "list")
    assert r.returncode == 0
    assert json.loads(r.stdout) == []


def test_cli_approve_succeeds(tmp_path: Path):
    _make_proposal(tmp_path)
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    r = _run_cli(
        "--cwd", str(tmp_path), "approve",
        "--slug", "forge-read-edit-bash",
        "--plugin-dir", str(plugin_dir),
    )
    assert r.returncode == 0
    assert "approved" in r.stdout
    assert (plugin_dir / "skills" / "forge-read-edit-bash" / "SKILL.md").exists()


def test_cli_approve_missing_slug_exits_nonzero(tmp_path: Path):
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    r = _run_cli(
        "--cwd", str(tmp_path), "approve",
        "--slug", "forge-nope",
        "--plugin-dir", str(plugin_dir),
    )
    assert r.returncode == 1
    assert "error" in r.stderr


def test_cli_reject_succeeds(tmp_path: Path):
    _make_proposal(tmp_path)
    r = _run_cli(
        "--cwd", str(tmp_path), "reject", "--slug", "forge-read-edit-bash",
    )
    assert r.returncode == 0
    assert "rejected" in r.stdout
    blacklist = (tmp_path / ".forge" / "skill-blacklist.txt").read_text(encoding="utf-8")
    assert "aaaaaaaaaaaa" in blacklist
