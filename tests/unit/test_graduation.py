"""Unit tests for scripts/_graduation.py — the tier-agnostic graduation core (T-207).

Covers the moved/shared primitives (registry, atomic IO, TTL, generic keyed
merge) and the fail-soft ``graduate()`` driver. The lessons-adapter behavior is
pinned by tests/unit/test_promote_lessons.py + test_promote_ttl.py (unchanged);
here we additionally assert the unified driver runs lessons through the SAME
logic as the legacy ``promote()`` (behavior-preserving, REQ-NF-036 / AC-GR-001).
"""
from __future__ import annotations

import datetime
import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # @dataclass / Protocol need the module registered
    spec.loader.exec_module(mod)
    return mod


gr = _load("_graduation", SCRIPTS / "_graduation.py")
pm = _load("promote_lessons", SCRIPTS / "promote-lessons.py")


# ---------------------------------------------------------------------------
# Registry: register / load / dedup
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_ensure_registry_creates_projects_yaml(self, tmp_path):
        d = tmp_path / ".forge"
        gr.ensure_registry(d)
        assert (d / "projects.yaml").exists()
        data = yaml.safe_load((d / "projects.yaml").read_text())
        assert data["projects"] == []

    def test_ensure_registry_does_not_create_global_lessons(self, tmp_path):
        # The registry concern is core; the global-lessons.yaml scaffold belongs
        # to the lessons adapter (ensure_global_dir), not the core.
        d = tmp_path / ".forge"
        gr.ensure_registry(d)
        assert not (d / "global-lessons.yaml").exists()

    def test_ensure_registry_idempotent(self, tmp_path):
        d = tmp_path / ".forge"
        gr.ensure_registry(d)
        gr.ensure_registry(d)  # must not raise or wipe
        assert (d / "projects.yaml").exists()

    def test_register_new_returns_true(self, tmp_path):
        d = tmp_path / ".forge"
        assert gr.register_project(d, tmp_path / "p") is True

    def test_register_duplicate_returns_false(self, tmp_path):
        d = tmp_path / ".forge"
        proj = tmp_path / "p"
        gr.register_project(d, proj)
        assert gr.register_project(d, proj) is False

    def test_register_dedup_no_duplicate_entry(self, tmp_path):
        d = tmp_path / ".forge"
        proj = tmp_path / "p"
        gr.register_project(d, proj)
        gr.register_project(d, proj)
        assert gr.load_registry(d).count(str(proj.resolve())) == 1

    def test_load_registry_missing_returns_empty(self, tmp_path):
        assert gr.load_registry(tmp_path / "nope") == []

    def test_load_registry_malformed_returns_empty(self, tmp_path):
        d = tmp_path / ".forge"
        d.mkdir()
        (d / "projects.yaml").write_text("{[ this is : not valid yaml")
        assert gr.load_registry(d) == []  # fail-soft, never raises


# ---------------------------------------------------------------------------
# merge_by_key: generic, idempotent, exact-key
# ---------------------------------------------------------------------------


class TestMergeByKey:
    def test_new_records_appended(self):
        out = gr.merge_by_key(
            [{"slug": "a"}, {"slug": "b"}], [], lambda r: r["slug"]
        )
        assert [r["slug"] for r in out] == ["a", "b"]

    def test_idempotent_second_merge_no_dups(self):
        existing = [{"slug": "a", "use": 2}]
        once = gr.merge_by_key(existing, existing, lambda r: r["slug"])
        twice = gr.merge_by_key(existing, once, lambda r: r["slug"])
        assert len(twice) == 1

    def test_exact_key_update_replaces(self):
        existing = [{"slug": "a", "use": 1}]
        out = gr.merge_by_key(
            [{"slug": "a", "use": 9}], existing, lambda r: r["slug"]
        )
        assert len(out) == 1
        assert out[0]["use"] == 9

    def test_merge_fn_accumulates(self):
        # exact-key update with a merge_fn accumulates fields (e.g. source projects)
        existing = [{"slug": "a", "projects": ["/p1"]}]
        new = [{"slug": "a", "projects": ["/p2"]}]

        def _accumulate(old, fresh):
            return {**fresh, "projects": sorted(set(old["projects"]) | set(fresh["projects"]))}

        out = gr.merge_by_key(new, existing, lambda r: r["slug"], merge_fn=_accumulate)
        assert len(out) == 1
        assert out[0]["projects"] == ["/p1", "/p2"]

    def test_distinct_keys_kept_separate(self):
        out = gr.merge_by_key(
            [{"slug": "b"}], [{"slug": "a"}], lambda r: r["slug"]
        )
        assert {r["slug"] for r in out} == {"a", "b"}


# ---------------------------------------------------------------------------
# is_stale: 30-day TTL boundaries (shared, moved from promote-lessons)
# ---------------------------------------------------------------------------


class TestIsStale:
    def test_old_is_stale(self):
        today = datetime.date(2026, 6, 9)
        assert gr.is_stale("2026-04-01", today=today) is True  # ~69 days

    def test_recent_not_stale(self):
        today = datetime.date(2026, 6, 9)
        assert gr.is_stale("2026-06-01", today=today) is False  # 8 days

    def test_boundary_exactly_30_days_not_stale(self):
        today = datetime.date(2026, 6, 9)
        # strictly > max_age_days is stale; exactly 30 is kept
        assert gr.is_stale("2026-05-10", today=today) is False  # 30 days
        assert gr.is_stale("2026-05-09", today=today) is True   # 31 days

    def test_none_kept(self):
        assert gr.is_stale(None) is False

    def test_unparseable_kept(self):
        assert gr.is_stale("not-a-date") is False

    def test_custom_max_age(self):
        today = datetime.date(2026, 6, 9)
        assert gr.is_stale("2026-06-01", today=today, max_age_days=5) is True

    def test_shared_with_promote_lessons(self):
        # promote-lessons re-exports the same is_stale; they must be the same object.
        assert pm.is_stale is gr.is_stale


# ---------------------------------------------------------------------------
# graduate() driver: fail-soft per tier, never raises
# ---------------------------------------------------------------------------


class _OkTier:
    name = "ok"

    def __init__(self):
        self.recalled = False

    def collect(self, project_path):
        return [{"from": project_path}]

    def gate(self, records):
        return records  # everything passes

    def key(self, record):
        return record.get("from", "")

    def promote(self, promotable, global_dir, *, dry_run=False):
        return promotable

    def recall(self, global_dir, project_path):
        self.recalled = True


class _ThrowingTier:
    name = "boom"

    def collect(self, project_path):
        raise RuntimeError("collect exploded")

    def gate(self, records):
        raise RuntimeError("gate exploded")

    def key(self, record):
        raise RuntimeError("key exploded")

    def promote(self, promotable, global_dir, *, dry_run=False):
        raise RuntimeError("promote exploded")

    def recall(self, global_dir, project_path):
        raise RuntimeError("recall exploded")


class TestGraduateDriver:
    def test_returns_dict_keyed_by_tier_name(self, tmp_path):
        d = tmp_path / ".forge"
        gr.register_project(d, tmp_path / "p1")
        result = gr.graduate(d, [_OkTier()])
        assert set(result) == {"ok"}

    def test_collects_across_registry(self, tmp_path):
        d = tmp_path / ".forge"
        gr.register_project(d, tmp_path / "p1")
        gr.register_project(d, tmp_path / "p2")
        result = gr.graduate(d, [_OkTier()])
        assert len(result["ok"]) == 2  # one record collected per registered project

    def test_throwing_tier_degrades_to_empty(self, tmp_path):
        d = tmp_path / ".forge"
        gr.register_project(d, tmp_path / "p1")
        result = gr.graduate(d, [_ThrowingTier()])
        assert result["boom"] == []  # isolated, not fatal

    def test_sibling_tier_still_completes(self, tmp_path):
        d = tmp_path / ".forge"
        gr.register_project(d, tmp_path / "p1")
        ok = _OkTier()
        result = gr.graduate(d, [_ThrowingTier(), ok])
        assert result["boom"] == []
        assert len(result["ok"]) == 1  # sibling unaffected by the thrown tier

    def test_driver_never_raises_on_broken_tier(self, tmp_path):
        d = tmp_path / ".forge"
        gr.register_project(d, tmp_path / "p1")
        # must not raise even when every tier explodes
        gr.graduate(d, [_ThrowingTier(), _ThrowingTier()])

    def test_driver_never_raises_on_unwritable_registry(self, tmp_path):
        # a totally bogus global dir (parent is a file) must not crash the driver
        bogus_parent = tmp_path / "afile"
        bogus_parent.write_text("x")
        d = bogus_parent / ".forge"
        result = gr.graduate(d, [_OkTier()])
        assert result["ok"] == []  # no projects loadable → nothing collected

    def test_no_projects_is_noop_per_tier(self, tmp_path):
        d = tmp_path / ".forge"
        gr.ensure_registry(d)  # registry exists, but empty
        result = gr.graduate(d, [_OkTier()])
        assert result["ok"] == []

    def test_recall_invoked_when_current_project_given(self, tmp_path):
        d = tmp_path / ".forge"
        gr.register_project(d, tmp_path / "p1")
        ok = _OkTier()
        gr.graduate(d, [ok], project_path=tmp_path / "current")
        assert ok.recalled is True

    def test_recall_skipped_without_current_project(self, tmp_path):
        # No current project → recall is not invoked (recall targets the
        # session's own project; the driver only promotes across the registry).
        d = tmp_path / ".forge"
        gr.register_project(d, tmp_path / "p1")
        ok = _OkTier()
        gr.graduate(d, [ok])
        assert ok.recalled is False

    def test_recall_failure_isolated_from_promotion(self, tmp_path):
        # A throwing recall must not sink the tier's promotion result nor raise.
        d = tmp_path / ".forge"
        gr.register_project(d, tmp_path / "p1")

        class _BadRecall(_OkTier):
            name = "badrecall"

            def recall(self, global_dir, project_path):
                raise RuntimeError("recall exploded")

        result = gr.graduate(d, [_BadRecall()], project_path=tmp_path / "current")
        assert len(result["badrecall"]) == 1  # promotion still succeeded


# ---------------------------------------------------------------------------
# Behavior-preservation: graduate([LessonTier]) == legacy promote() output
# ---------------------------------------------------------------------------


def _make_project(tmp_path: Path, name: str, lessons: list[dict]) -> Path:
    proj = tmp_path / name
    (proj / ".forge").mkdir(parents=True)
    (proj / ".forge" / "lessons.yaml").write_text(
        yaml.dump({"schema_version": 1, "lessons": lessons}), encoding="utf-8"
    )
    return proj


def _lesson(trigger: str, frequency: int = 2) -> dict:
    return {
        "id": "L-test", "date": "2026-05-10", "title": trigger[:40],
        "trigger": trigger, "rule": "rule", "why": "why", "tags": [],
        "stage": [], "project_types": [], "frequency": frequency,
        "last_used": "2026-05-10",
    }


class TestLessonTierMatchesLegacy:
    def test_lesson_tier_satisfies_protocol(self):
        assert isinstance(pm.LessonTier(), gr.Tier)

    def test_graduate_emits_byte_identical_global_yaml(self, tmp_path):
        # Same inputs through legacy promote() vs the unified driver/LessonTier
        # must yield byte-identical global-lessons.yaml (AC-GR-001). The same
        # project paths feed both runs so the recorded `projects:` field matches.
        lesson = _lesson("GPU OOM error during training")
        projs = [_make_project(tmp_path / "src", f"proj{i}", [lesson]) for i in range(3)]

        legacy_dir = tmp_path / "legacy"
        for proj in projs:
            pm.register_project(legacy_dir, proj)
        pm.promote(legacy_dir, threshold=3)
        legacy_bytes = (legacy_dir / "global-lessons.yaml").read_text()

        driver_dir = tmp_path / "driver"
        for proj in projs:
            pm.register_project(driver_dir, proj)
        gr.graduate(driver_dir, [pm.LessonTier(threshold=3)])
        driver_bytes = (driver_dir / "global-lessons.yaml").read_text()

        assert driver_bytes == legacy_bytes

    def test_graduate_lesson_promotion_idempotent(self, tmp_path):
        lesson = _lesson("GPU OOM error during training")
        d = tmp_path / ".forge"
        for i in range(3):
            proj = _make_project(tmp_path / "src", f"proj{i}", [lesson])
            pm.register_project(d, proj)
        gr.graduate(d, [pm.LessonTier(threshold=3)])
        first = (d / "global-lessons.yaml").read_text()
        gr.graduate(d, [pm.LessonTier(threshold=3)])
        second = (d / "global-lessons.yaml").read_text()
        assert first == second  # second scan changes nothing (NF-037)
