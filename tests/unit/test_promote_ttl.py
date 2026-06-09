"""T-115 / REQ-LESSON-SOURCES-001 (EF-026): global-lessons TTL + promotion gate.

AC-LESSON-SOURCES-001d:
  - a one-shot (frequency 1) lesson is NOT promoted;
  - a lesson with last_used > 30 days is NOT surfaced at recall;
  - the suite never writes the real ~/.forge/global-lessons.yaml.
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
HOOKS = ROOT / "hooks"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


pm = _load("promote_lessons", SCRIPTS / "promote-lessons.py")
ss = _load("session_start", HOOKS / "session-start.py")


def _write_project(proj: Path, frequency: int) -> None:
    (proj / ".forge").mkdir(parents=True, exist_ok=True)
    (proj / ".forge" / "lessons.yaml").write_text(yaml.safe_dump({
        "schema_version": 1,
        "lessons": [{
            "id": "L1", "title": "tmp lesson", "trigger": "when running pytest tmp_path",
            "rule": "do X", "why": "because", "tags": ["t"], "stage": [],
            "project_types": [], "frequency": frequency, "last_used": "2026-06-09",
        }],
    }))


# ---------- promotion gate: frequency 1 not promoted ----------

def test_frequency_one_not_promoted(tmp_path: Path) -> None:
    gdir = tmp_path / "global"
    proj = tmp_path / "proj"
    _write_project(proj, frequency=1)
    pm.register_project(gdir, proj)
    promoted = pm.promote(gdir, threshold=1)  # breadth gate satisfied; freq gate must block
    assert promoted == []


def test_frequency_two_is_promoted(tmp_path: Path) -> None:
    gdir = tmp_path / "global"
    proj = tmp_path / "proj"
    _write_project(proj, frequency=2)
    pm.register_project(gdir, proj)
    promoted = pm.promote(gdir, threshold=1)
    assert len(promoted) == 1


# ---------- is_stale TTL logic ----------

def test_is_stale_boundaries() -> None:
    today = datetime.date(2026, 6, 9)
    assert pm.is_stale("2026-04-01", today=today) is True          # ~69 days
    assert pm.is_stale("2026-06-01", today=today) is False         # 8 days
    assert pm.is_stale(None, today=today) is False                 # unknown → keep
    assert pm.is_stale("not-a-date", today=today) is False         # unparseable → keep


# ---------- recall TTL: stale global lesson not surfaced ----------

def _global_file(tmp_path: Path, last_used: str) -> Path:
    p = tmp_path / "global-lessons.yaml"
    p.write_text(yaml.safe_dump({
        "schema_version": 1,
        "lessons": [{
            "title": "old", "trigger": "x", "rule": "y", "tags": [],
            "stage": [], "project_types": [], "frequency": 5, "last_used": last_used,
        }],
    }))
    return p


def test_recall_skips_stale_global(tmp_path: Path) -> None:
    stale = (datetime.date.today() - datetime.timedelta(days=60)).isoformat()
    p = _global_file(tmp_path, stale)
    assert ss._load_lessons(p, stage=1, project_type="api", max_age_days=30) == []


def test_recall_keeps_fresh_global(tmp_path: Path) -> None:
    fresh = (datetime.date.today() - datetime.timedelta(days=5)).isoformat()
    p = _global_file(tmp_path, fresh)
    assert len(ss._load_lessons(p, stage=1, project_type="api", max_age_days=30)) == 1


def test_recall_no_ttl_keeps_old_project_lessons(tmp_path: Path) -> None:
    old = (datetime.date.today() - datetime.timedelta(days=400)).isoformat()
    p = _global_file(tmp_path, old)
    # project recall passes no max_age_days → not pruned
    assert len(ss._load_lessons(p, stage=1, project_type="api")) == 1


# ---------- isolation guard ----------

def test_no_test_writes_real_home_global_store() -> None:
    offenders = []
    for path in (ROOT / "tests").rglob("*.py"):
        if path.name == Path(__file__).name:
            continue  # this guard file names the strings on purpose
        text = path.read_text()
        # a write target combining the real home dir with the global store
        if ("Path.home()" in text or "expanduser" in text) and "global-lessons" in text:
            # allow comments referencing it, not code that builds the path
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if ("home()" in line or "expanduser" in line) and "global-lessons" in line:
                    offenders.append(f"{path.name}: {stripped[:80]}")
    assert offenders == [], f"tests touch the real ~/.forge global store: {offenders}"
