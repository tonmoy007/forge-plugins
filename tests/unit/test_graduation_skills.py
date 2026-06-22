"""Unit tests for scripts/_graduation_skills.py — the skills graduation tier (T-208).

AC-GR-002 (REQ-GR-003 / GR-005 / NF-035 / NF-037):
  - two registered projects with an approved <slug> at ExpeL weight>0, use>=2
    promote it to ~/.forge/skills/<slug>/ + index it in global-skills.yaml;
  - weight<=0, use<2, or proposed-but-not-approved do NOT promote;
  - recall symlinks the global skill into the plugin skills path ONLY when no
    same-slug project/plugin skill exists (project/plugin-wins), never clobbers,
    and drops TTL-stale globals;
  - a second scan with no new artifacts is idempotent (no file/symlink churn).

All filesystem touch is confined to tmp dirs: a fake plugin skills/ path and a
fake ~/.forge are injected; nothing writes the real ~/.forge or real plugin.
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


gr = _load("_graduation", SCRIPTS / "_graduation.py")
sk = _load("_graduation_skills", SCRIPTS / "_graduation_skills.py")

_TODAY = datetime.date(2026, 6, 9)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _install_skill(plugin_skills: Path, slug: str) -> Path:
    """Create an *approved* skill dir (skill-approval.approve install layout)."""
    d = plugin_skills / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {slug}\ndescription: a {slug} skill\n---\n\n# {slug}\n",
        encoding="utf-8",
    )
    return d


def _write_stats(project: Path, slug: str, actions: list[str]) -> None:
    """Append ExpeL vote events to a project's .forge/skill-stats.jsonl."""
    forge = project / ".forge"
    forge.mkdir(parents=True, exist_ok=True)
    with (forge / "skill-stats.jsonl").open("a", encoding="utf-8") as f:
        for a in actions:
            f.write(json.dumps({"skill": slug, "action": a}) + "\n")


# Vote shorthands → folded (weight, uses):
_PASS = ["ADD", "UPVOTE", "UPVOTE"]   # weight 3, uses 2  → promotable
_LOW_WEIGHT = ["ADD", "DOWNVOTE", "DOWNVOTE"]  # weight -1, uses 2 → blocked
_LOW_USE = ["ADD", "UPVOTE"]          # weight 2, uses 1  → blocked


def _tier(plugin_skills: Path, **kw):
    return sk.SkillTier(plugin_skills, today=_TODAY, **kw)


def _index(global_dir: Path) -> list:
    p = global_dir / "global-skills.yaml"
    if not p.exists():
        return []
    return yaml.safe_load(p.read_text())["skills"]


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_skill_tier_satisfies_protocol(tmp_path):
    assert isinstance(_tier(tmp_path / "skills"), gr.Tier)


def test_key_returns_slug(tmp_path):
    t = _tier(tmp_path / "skills")
    assert t.key({"slug": "foo"}) == "foo"
    assert t.key(sk.SkillRecord("bar", 1, 2, None, "/p", "/d")) == "bar"


# ---------------------------------------------------------------------------
# collect + gate
# ---------------------------------------------------------------------------


class TestCollectGate:
    def test_collect_approved_skill(self, tmp_path):
        plugin_skills = tmp_path / "plugin" / "skills"
        _install_skill(plugin_skills, "foo")
        proj = tmp_path / "p1"
        _write_stats(proj, "foo", _PASS)
        recs = _tier(plugin_skills).collect(str(proj))
        assert [r.slug for r in recs] == ["foo"]
        assert recs[0].weight == 3 and recs[0].use == 2

    def test_collect_skips_unapproved_slug(self, tmp_path):
        # votes exist but the skill is not installed in the plugin skills path
        plugin_skills = tmp_path / "plugin" / "skills"
        plugin_skills.mkdir(parents=True)
        proj = tmp_path / "p1"
        _write_stats(proj, "ghost", _PASS)
        assert _tier(plugin_skills).collect(str(proj)) == []

    def test_collect_missing_project_is_empty(self, tmp_path):
        plugin_skills = tmp_path / "plugin" / "skills"
        plugin_skills.mkdir(parents=True)
        assert _tier(plugin_skills).collect(str(tmp_path / "nope")) == []

    def test_gate_passes_weight_pos_use_ge_min(self, tmp_path):
        plugin_skills = tmp_path / "plugin" / "skills"
        _install_skill(plugin_skills, "foo")
        rec = sk.SkillRecord("foo", 3, 2, "2026-06-01", "/p", str(plugin_skills / "foo"))
        assert _tier(plugin_skills).gate([rec]) == [rec]

    def test_gate_blocks_low_weight(self, tmp_path):
        plugin_skills = tmp_path / "plugin" / "skills"
        _install_skill(plugin_skills, "foo")
        rec = sk.SkillRecord("foo", 0, 5, "2026-06-01", "/p", str(plugin_skills / "foo"))
        assert _tier(plugin_skills).gate([rec]) == []

    def test_gate_blocks_low_use(self, tmp_path):
        plugin_skills = tmp_path / "plugin" / "skills"
        _install_skill(plugin_skills, "foo")
        rec = sk.SkillRecord("foo", 3, 1, "2026-06-01", "/p", str(plugin_skills / "foo"))
        assert _tier(plugin_skills).gate([rec]) == []


# ---------------------------------------------------------------------------
# promote (via the unified driver) — AC-GR-002
# ---------------------------------------------------------------------------


class TestPromote:
    def _two_projects(self, tmp_path, slug, actions):
        gdir = tmp_path / ".forge_global"
        plugin_skills = tmp_path / "plugin" / "skills"
        _install_skill(plugin_skills, slug)
        projs = []
        for i in range(2):
            p = tmp_path / f"p{i}"
            _write_stats(p, slug, actions)
            gr.register_project(gdir, p)
            projs.append(p)
        return gdir, plugin_skills, projs

    def test_two_projects_promote_and_index(self, tmp_path):
        gdir, plugin_skills, projs = self._two_projects(tmp_path, "foo", _PASS)
        result = gr.graduate(gdir, [_tier(plugin_skills)])
        assert [r["slug"] for r in result["skills"]] == ["foo"]
        # copied into the global store
        assert (gdir / "skills" / "foo" / "SKILL.md").exists()
        # indexed with both source projects
        idx = _index(gdir)
        assert idx[0]["slug"] == "foo"
        assert set(idx[0]["projects"]) == {str(p.resolve()) for p in projs}
        assert idx[0]["weight"] == 3 and idx[0]["use"] == 2

    def test_low_weight_not_promoted(self, tmp_path):
        gdir, plugin_skills, _ = self._two_projects(tmp_path, "foo", _LOW_WEIGHT)
        result = gr.graduate(gdir, [_tier(plugin_skills)])
        assert result["skills"] == []
        assert not (gdir / "skills" / "foo").exists()

    def test_low_use_not_promoted(self, tmp_path):
        gdir, plugin_skills, _ = self._two_projects(tmp_path, "foo", _LOW_USE)
        result = gr.graduate(gdir, [_tier(plugin_skills)])
        assert result["skills"] == []

    def test_proposed_not_approved_not_promoted(self, tmp_path):
        # votes qualify, but the skill lives only under proposed-skills (not installed)
        gdir = tmp_path / ".forge_global"
        plugin_skills = tmp_path / "plugin" / "skills"
        plugin_skills.mkdir(parents=True)
        proj = tmp_path / "p0"
        (proj / ".forge" / "proposed-skills" / "foo").mkdir(parents=True)
        (proj / ".forge" / "proposed-skills" / "foo" / "SKILL.md").write_text("x")
        _write_stats(proj, "foo", _PASS)
        gr.register_project(gdir, proj)
        result = gr.graduate(gdir, [_tier(plugin_skills)])
        assert result["skills"] == []
        assert not (gdir / "skills" / "foo").exists()

    def test_dry_run_writes_nothing(self, tmp_path):
        gdir, plugin_skills, _ = self._two_projects(tmp_path, "foo", _PASS)
        result = gr.graduate(gdir, [_tier(plugin_skills)], dry_run=True)
        assert [r["slug"] for r in result["skills"]] == ["foo"]  # preview returned
        assert not (gdir / "skills" / "foo").exists()  # nothing copied
        assert not (gdir / "global-skills.yaml").exists()  # nothing indexed

    def test_second_scan_idempotent(self, tmp_path):
        gdir, plugin_skills, _ = self._two_projects(tmp_path, "foo", _PASS)
        gr.graduate(gdir, [_tier(plugin_skills)])
        first = (gdir / "global-skills.yaml").read_text()
        gr.graduate(gdir, [_tier(plugin_skills)])
        second = (gdir / "global-skills.yaml").read_text()
        assert first == second  # NF-037: no churn on re-scan


# ---------------------------------------------------------------------------
# recall: symlink with project/plugin-wins (ADR-009)
# ---------------------------------------------------------------------------


def _seed_global_skill(gdir: Path, slug: str, last_used: str) -> None:
    """Put a graduated skill in ~/.forge/skills + global-skills.yaml index."""
    d = gdir / "skills" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"name: {slug}\n", encoding="utf-8")
    gr.write_atomic(
        gdir / "global-skills.yaml",
        yaml.dump(
            {"schema_version": 1, "skills": [
                {"slug": slug, "projects": ["/p"], "weight": 3, "use": 2,
                 "last_used": last_used}
            ]},
            sort_keys=False,
        ),
    )


class TestRecall:
    def test_symlinks_when_no_local_skill(self, tmp_path):
        gdir = tmp_path / ".forge_global"
        plugin_skills = tmp_path / "plugin" / "skills"
        plugin_skills.mkdir(parents=True)
        _seed_global_skill(gdir, "bar", "2026-06-01")  # fresh
        _tier(plugin_skills).recall(gdir, str(tmp_path / "proj"))
        link = plugin_skills / "bar"
        assert link.is_symlink()
        assert (link / "SKILL.md").exists()  # resolves to the global store
        assert link.resolve() == (gdir / "skills" / "bar").resolve()

    def test_no_clobber_existing_real_dir(self, tmp_path):
        gdir = tmp_path / ".forge_global"
        plugin_skills = tmp_path / "plugin" / "skills"
        local = _install_skill(plugin_skills, "bar")  # a real local/plugin skill
        (local / "SKILL.md").write_text("LOCAL VERSION", encoding="utf-8")
        _seed_global_skill(gdir, "bar", "2026-06-01")
        _tier(plugin_skills).recall(gdir, str(tmp_path / "proj"))
        # project/plugin-wins: the real dir is untouched, not turned into a symlink
        assert not (plugin_skills / "bar").is_symlink()
        assert (plugin_skills / "bar" / "SKILL.md").read_text() == "LOCAL VERSION"

    def test_skips_stale_global(self, tmp_path):
        gdir = tmp_path / ".forge_global"
        plugin_skills = tmp_path / "plugin" / "skills"
        plugin_skills.mkdir(parents=True)
        _seed_global_skill(gdir, "bar", "2026-04-01")  # >30d before _TODAY → stale
        _tier(plugin_skills).recall(gdir, str(tmp_path / "proj"))
        assert not (plugin_skills / "bar").exists()
        assert not (plugin_skills / "bar").is_symlink()

    def test_recall_idempotent(self, tmp_path):
        gdir = tmp_path / ".forge_global"
        plugin_skills = tmp_path / "plugin" / "skills"
        plugin_skills.mkdir(parents=True)
        _seed_global_skill(gdir, "bar", "2026-06-01")
        t = _tier(plugin_skills)
        t.recall(gdir, str(tmp_path / "proj"))
        t.recall(gdir, str(tmp_path / "proj"))  # second time: no error, still one link
        assert (plugin_skills / "bar").is_symlink()

    def test_recall_copy_fallback_when_symlink_unsupported(self, tmp_path, monkeypatch):
        gdir = tmp_path / ".forge_global"
        plugin_skills = tmp_path / "plugin" / "skills"
        plugin_skills.mkdir(parents=True)
        _seed_global_skill(gdir, "bar", "2026-06-01")

        def _no_symlink(*a, **k):
            raise OSError("symlinks unsupported on this platform")

        monkeypatch.setattr(sk.os, "symlink", _no_symlink)
        _tier(plugin_skills).recall(gdir, str(tmp_path / "proj"))
        # ADR-009 fallback: a guarded copy, not a symlink
        assert (plugin_skills / "bar" / "SKILL.md").exists()
        assert not (plugin_skills / "bar").is_symlink()


# ---------------------------------------------------------------------------
# never-raises (REQ-NF-034)
# ---------------------------------------------------------------------------


class TestFailSoft:
    def test_collect_malformed_stats_no_raise(self, tmp_path):
        plugin_skills = tmp_path / "plugin" / "skills"
        _install_skill(plugin_skills, "foo")
        proj = tmp_path / "p"
        (proj / ".forge").mkdir(parents=True)
        (proj / ".forge" / "skill-stats.jsonl").write_text("not json\n{also bad\n")
        assert _tier(plugin_skills).collect(str(proj)) == []  # no raise

    def test_recall_missing_global_dir_no_raise(self, tmp_path):
        plugin_skills = tmp_path / "plugin" / "skills"
        plugin_skills.mkdir(parents=True)
        _tier(plugin_skills).recall(tmp_path / "no_such_global", str(tmp_path / "p"))

    def test_graduate_isolates_skill_tier_failure(self, tmp_path):
        # a totally broken plugin path must not crash the driver
        gdir = tmp_path / ".forge_global"
        gr.register_project(gdir, tmp_path / "p")
        bad = tmp_path / "afile"
        bad.write_text("x")  # not a directory
        result = gr.graduate(gdir, [_tier(bad / "skills")])
        assert result["skills"] == []
