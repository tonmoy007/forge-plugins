"""Tests for scripts/set-context-depth.py (T-252, REQ-BUILDCTX-002).

`/forge:plan-pro`'s Stage 5 entry sets `build_context_depth` in pipeline/state.md
(atomic, validated, never re-prompts) after checking the depth against the three
allowed values.
"""

from __future__ import annotations

import datetime
import importlib.util
import re
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location(
    "set_context_depth", _root / "scripts" / "set-context-depth.py"
)
_scd = importlib.util.module_from_spec(_spec)
sys.modules["set_context_depth"] = _scd
_spec.loader.exec_module(_scd)


def _make_state(tmp_path: Path) -> None:
    (tmp_path / "pipeline").mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "pipeline" / "state.md").write_text(
        f"---\nschema_version: 1\nproject_type: api\ncycle: 1\n"
        f"current_stage: 5\ncurrent_task: null\ncurrent_milestone: null\n"
        f"total_tasks: null\nlast_updated: {now}\nblockers: []\n---\n\n# Pipeline State\n"
    )


def _depth(tmp_path: Path) -> str | None:
    text = (tmp_path / "pipeline" / "state.md").read_text()
    m = re.search(r"build_context_depth:\s*(\S+)", text)
    return m.group(1) if m else None


def test_set_valid_depth_updates_state(tmp_path: Path) -> None:
    _make_state(tmp_path)
    code, msg = _scd.set_context_depth(str(tmp_path), "spec_arch_plan")
    assert code == 0
    assert _depth(tmp_path) == "spec_arch_plan"


def test_invalid_depth_rejected(tmp_path: Path) -> None:
    _make_state(tmp_path)
    code, msg = _scd.set_context_depth(str(tmp_path), "bogus-depth")
    assert code == 1
    assert "bogus-depth" in msg or "unknown depth" in msg.lower()
    assert _depth(tmp_path) is None


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    _make_state(tmp_path)
    code, msg = _scd.set_context_depth(str(tmp_path), "full_chain", dry_run=True)
    assert code == 0
    assert "would" in msg.lower()
    assert _depth(tmp_path) is None


def test_missing_state_graceful(tmp_path: Path) -> None:
    code, msg = _scd.set_context_depth(str(tmp_path), "spec_plan")
    assert code == 1
    assert "state.md" in msg.lower() or "init" in msg.lower()


def test_already_set_is_not_reprompted(tmp_path: Path) -> None:
    """AC-BUILDCTX-002c: never re-prompt or silently overwrite an explicit prior choice."""
    _make_state(tmp_path)
    _scd.set_context_depth(str(tmp_path), "spec_arch_plan")
    code, msg = _scd.set_context_depth(str(tmp_path), "full_chain")
    assert code == 0
    assert "already" in msg.lower()
    assert _depth(tmp_path) == "spec_arch_plan"  # unchanged


def test_force_overwrites_an_already_set_value(tmp_path: Path) -> None:
    _make_state(tmp_path)
    _scd.set_context_depth(str(tmp_path), "spec_arch_plan")
    code, msg = _scd.set_context_depth(str(tmp_path), "full_chain", force=True)
    assert code == 0
    assert _depth(tmp_path) == "full_chain"


def test_main_cli(tmp_path: Path) -> None:
    _make_state(tmp_path)
    rc = _scd.main(["spec_plan", "--cwd", str(tmp_path)])
    assert rc == 0
    assert _depth(tmp_path) == "spec_plan"
