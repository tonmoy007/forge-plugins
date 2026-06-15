"""Tests for scripts/rules.py (v0.3.0 — REQ-RULES-001..004).

The rules loader parses `.forge/rules/*.md` (user-authored constraint files with
YAML frontmatter + a markdown body) and selects them by scope:
  - always  → every session
  - stage   → only when current_stage ∈ stages
  - glob    → only on writes to files matching globs
  - manual  → never auto-selected

It must be FAIL-SOFT (malformed file skipped, absent dir → []) and NEVER raise
(it is imported by session-start.py and pre-tool-write.py hooks).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_mod_path = Path(__file__).resolve().parent.parent.parent / "scripts" / "rules.py"
_spec = importlib.util.spec_from_file_location("rules", _mod_path)
_rules = importlib.util.module_from_spec(_spec)
# Register before exec so @dataclass (under `from __future__ import annotations`)
# can resolve its own module via sys.modules.
sys.modules["rules"] = _rules
_spec.loader.exec_module(_rules)


def _write_rule(forge: Path, name: str, body: str) -> None:
    d = forge / "rules"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(body)


# --- load: absent dir / empty ----------------------------------------------

def test_absent_dir_returns_empty(tmp_path: Path) -> None:
    assert _rules.load_rules(tmp_path / ".forge") == []


def test_empty_dir_returns_empty(tmp_path: Path) -> None:
    (tmp_path / ".forge" / "rules").mkdir(parents=True)
    assert _rules.load_rules(tmp_path / ".forge") == []


# --- load: well-formed ------------------------------------------------------

def test_parses_always_rule(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _write_rule(
        forge, "10-tone.md",
        "---\ndescription: Keep prose terse\nscope: always\n---\nBe concise.\n",
    )
    rules = _rules.load_rules(forge)
    assert len(rules) == 1
    r = rules[0]
    assert r.name == "10-tone"
    assert r.scope == "always"
    assert r.description == "Keep prose terse"
    assert "Be concise." in r.body


def test_parses_stage_and_glob_fields(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _write_rule(forge, "s.md", "---\nscope: stage\nstages: [6, 7]\n---\nbuild rule\n")
    _write_rule(forge, "g.md", "---\nscope: glob\nglobs: ['**/*.tsx']\n---\nui rule\n")
    by_name = {r.name: r for r in _rules.load_rules(forge)}
    assert by_name["s"].stages == [6, 7]
    assert by_name["g"].globs == ["**/*.tsx"]


# --- select: scope semantics ------------------------------------------------

def test_select_always_and_matching_stage(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _write_rule(forge, "a.md", "---\nscope: always\n---\nalways\n")
    _write_rule(forge, "s6.md", "---\nscope: stage\nstages: [6]\n---\nstage6\n")
    _write_rule(forge, "s9.md", "---\nscope: stage\nstages: [9]\n---\nstage9\n")
    _write_rule(forge, "m.md", "---\nscope: manual\n---\nmanual\n")
    rules = _rules.load_rules(forge)

    names = {r.name for r in _rules.select(rules, stage=6)}
    assert names == {"a", "s6"}  # always + matching stage; NOT s9, NOT manual


def test_select_glob_only_matches_path(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _write_rule(forge, "ui.md", "---\nscope: glob\nglobs: ['**/*.tsx']\n---\nui\n")
    rules = _rules.load_rules(forge)

    hit = _rules.select(rules, file_path="app/Button.tsx", scope="glob")
    miss = _rules.select(rules, file_path="README.md", scope="glob")
    assert [r.name for r in hit] == ["ui"]
    assert miss == []


def test_select_stage_without_stage_arg_excludes(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _write_rule(forge, "s.md", "---\nscope: stage\nstages: [6]\n---\nx\n")
    rules = _rules.load_rules(forge)
    # session-start passes no file_path; a stage rule needs a matching stage.
    assert _rules.select(rules, stage=None) == []


# --- glob matching edge cases ----------------------------------------------

def test_glob_matches_root_and_nested(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _write_rule(forge, "py.md", "---\nscope: glob\nglobs: ['**/*.py']\n---\npy\n")
    rules = _rules.load_rules(forge)
    assert _rules.select(rules, file_path="main.py", scope="glob")        # root file
    assert _rules.select(rules, file_path="a/b/c.py", scope="glob")       # nested
    assert not _rules.select(rules, file_path="a/b/c.md", scope="glob")


# --- fail-soft --------------------------------------------------------------

def test_malformed_file_skipped_others_load(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _write_rule(forge, "good.md", "---\nscope: always\n---\nok\n")
    _write_rule(forge, "noscope.md", "---\ndescription: missing scope\n---\nbody\n")
    _write_rule(forge, "badyaml.md", "---\nscope: [unclosed\n---\nbody\n")
    _write_rule(forge, "plain.md", "no frontmatter at all\n")
    _write_rule(forge, "README.md", "# Rules\nNot a rule file.\n")
    rules = _rules.load_rules(forge)
    assert [r.name for r in rules] == ["good"]  # only the valid one survives


def test_invalid_scope_skipped(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _write_rule(forge, "x.md", "---\nscope: whenever\n---\nbody\n")
    assert _rules.load_rules(forge) == []


# --- priority ordering ------------------------------------------------------

def test_priority_orders_descending(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _write_rule(forge, "low.md", "---\nscope: always\npriority: 1\n---\nlow\n")
    _write_rule(forge, "high.md", "---\nscope: always\npriority: 10\n---\nhigh\n")
    names = [r.name for r in _rules.load_rules(forge)]
    assert names == ["high", "low"]


# --- render -----------------------------------------------------------------

def test_render_empty_is_blank() -> None:
    assert _rules.render([]) == ""


def test_render_is_budget_bounded(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    for i in range(20):
        _write_rule(forge, f"r{i:02d}.md",
                    f"---\nscope: always\npriority: {i}\n---\n" + ("x" * 200) + "\n")
    rules = _rules.load_rules(forge)
    out = _rules.render(rules, max_chars=300)
    assert out and len(out) <= 300


# --- never raises -----------------------------------------------------------

def test_load_never_raises_on_unreadable(tmp_path: Path, monkeypatch) -> None:
    forge = tmp_path / ".forge"
    _write_rule(forge, "a.md", "---\nscope: always\n---\nok\n")

    def boom(*_a, **_k):
        raise OSError("disk gone")

    monkeypatch.setattr(Path, "read_text", boom)
    # Must degrade, not raise.
    assert _rules.load_rules(forge) == []


# --- CLI: init / add --------------------------------------------------------

def test_init_scaffolds_and_is_idempotent(tmp_path: Path) -> None:
    rc = _rules.main(["init", "--cwd", str(tmp_path)])
    assert rc == 0
    d = tmp_path / ".forge" / "rules"
    assert (d / "README.md").exists()
    assert (d / "00-style.md").exists()
    # The scaffolded example is a valid, loadable rule.
    loaded = _rules.load_rules(tmp_path / ".forge")
    assert [r.name for r in loaded] == ["00-style"]  # README skipped (no scope)
    # Re-running keeps existing files (idempotent, no clobber).
    (d / "00-style.md").write_text("---\nscope: always\n---\nEDITED\n")
    assert _rules.main(["init", "--cwd", str(tmp_path)]) == 0
    assert "EDITED" in (d / "00-style.md").read_text()


def test_add_creates_and_refuses_clobber(tmp_path: Path) -> None:
    assert _rules.main(["add", "20-ui", "--scope", "glob",
                        "--description", "UI rules", "--cwd", str(tmp_path)]) == 0
    path = tmp_path / ".forge" / "rules" / "20-ui.md"
    assert path.exists()
    rule = _rules.load_rules(tmp_path / ".forge")[0]
    assert rule.name == "20-ui" and rule.scope == "glob"
    # Second add must not overwrite the edited file.
    path.write_text("---\nscope: glob\nglobs: ['**/*.ts']\n---\nKEEP ME\n")
    assert _rules.main(["add", "20-ui", "--cwd", str(tmp_path)]) == 0
    assert "KEEP ME" in path.read_text()


def test_add_invalid_scope_is_usage_error(tmp_path: Path) -> None:
    assert _rules.main(["add", "x", "--scope", "whenever", "--cwd", str(tmp_path)]) == 2


# --- enforcing rules (T-175, REQ-AUTO-006) ---------------------------------

def test_enforce_defaults_off_and_severity_error(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _write_rule(forge, "a.md", "---\nscope: glob\nglobs: ['**/*.py']\n---\nx\n")
    r = _rules.load_rules(forge)[0]
    assert r.enforce is False        # advisory by default — unchanged from v0.3.0
    assert r.severity == "error"     # default severity


def test_parses_enforce_and_severity(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _write_rule(
        forge, "lock.md",
        "---\nscope: glob\nglobs: ['**/*.lock']\nenforce: true\nseverity: error\n---\n"
        "Do not touch lockfiles.\n",
    )
    r = _rules.load_rules(forge)[0]
    assert r.enforce is True
    assert r.severity == "error"


def test_enforcing_for_file_matches_only_enforcing_globs(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _write_rule(forge, "lock.md",
                "---\nscope: glob\nglobs: ['**/*.lock']\nenforce: true\n---\nprotected\n")
    _write_rule(forge, "adv.md",
                "---\nscope: glob\nglobs: ['**/*.py']\n---\nadvisory only\n")
    rules = _rules.load_rules(forge)
    # enforcing match on a lockfile:
    hit = _rules.enforcing_for_file(rules, "poetry.lock")
    assert [r.name for r in hit] == ["lock"]
    # advisory glob rule is NOT enforcing:
    assert _rules.enforcing_for_file(rules, "app/main.py") == []
    # non-matching path:
    assert _rules.enforcing_for_file(rules, "README.md") == []


def test_enforcing_ignores_non_glob_scopes(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    # enforce on a non-glob scope has nothing to match a file against → never blocks.
    _write_rule(forge, "always.md",
                "---\nscope: always\nenforce: true\n---\nx\n")
    rules = _rules.load_rules(forge)
    assert _rules.enforcing_for_file(rules, "anything.py") == []
