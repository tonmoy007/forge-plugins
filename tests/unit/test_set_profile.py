"""Tests for scripts/set-profile.py (v0.2 P0 — T-140, REQ-F-051).

`/forge:set-profile <type>` switches the project_type in pipeline/state.md
(atomic, validated) after checking the type against the known profile list.
"""

from __future__ import annotations

import datetime
import importlib.util
import json
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location("set_profile", _root / "scripts" / "set-profile.py")
_sp = importlib.util.module_from_spec(_spec)
sys.modules["set_profile"] = _sp
_spec.loader.exec_module(_sp)

PLUGIN_DIR = _root


def _make_state(tmp_path: Path, project_type: str = "unknown") -> None:
    (tmp_path / "pipeline").mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "pipeline" / "state.md").write_text(
        f"---\nschema_version: 1\nproject_type: {project_type}\ncycle: 1\n"
        f"current_stage: 0\ncurrent_task: null\ncurrent_milestone: null\n"
        f"total_tasks: null\nlast_updated: {now}\nblockers: []\n---\n\n# Pipeline State\n"
    )


def _project_type(tmp_path: Path) -> str:
    import re
    text = (tmp_path / "pipeline" / "state.md").read_text()
    return re.search(r"project_type:\s*(\S+)", text).group(1)


def test_known_profiles_lists_all(tmp_path: Path) -> None:
    names = _sp.known_profiles(PLUGIN_DIR)
    for expected in ("api", "fullstack", "ml-pipeline", "monorepo", "mobile", "data-contract", "docker"):
        assert expected in names
    assert len(names) >= 11


def test_set_profile_docker_accepted(tmp_path: Path) -> None:
    _make_state(tmp_path, "unknown")
    code, msg = _sp.set_profile(str(tmp_path), "docker", plugin_dir=PLUGIN_DIR)
    assert code == 0
    assert _project_type(tmp_path) == "docker"


def test_set_valid_profile_updates_state(tmp_path: Path) -> None:
    _make_state(tmp_path, "unknown")
    code, msg = _sp.set_profile(str(tmp_path), "api", plugin_dir=PLUGIN_DIR)
    assert code == 0
    assert _project_type(tmp_path) == "api"


def test_invalid_profile_rejected(tmp_path: Path) -> None:
    _make_state(tmp_path, "unknown")
    code, msg = _sp.set_profile(str(tmp_path), "bogus-type", plugin_dir=PLUGIN_DIR)
    assert code == 1
    assert "bogus-type" in msg or "unknown profile" in msg.lower()
    assert _project_type(tmp_path) == "unknown"  # unchanged


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    _make_state(tmp_path, "unknown")
    code, msg = _sp.set_profile(str(tmp_path), "mobile", plugin_dir=PLUGIN_DIR, dry_run=True)
    assert code == 0
    assert "would" in msg.lower()
    assert _project_type(tmp_path) == "unknown"  # not written


def test_missing_state_graceful(tmp_path: Path) -> None:
    # No pipeline/state.md → clean error, no crash/exit.
    code, msg = _sp.set_profile(str(tmp_path), "api", plugin_dir=PLUGIN_DIR)
    assert code == 1
    assert "state.md" in msg.lower() or "init" in msg.lower()


def test_main_cli(tmp_path: Path) -> None:
    _make_state(tmp_path, "unknown")
    rc = _sp.main(["data-contract", "--cwd", str(tmp_path), "--plugin-dir", str(PLUGIN_DIR)])
    assert rc == 0
    assert _project_type(tmp_path) == "data-contract"
