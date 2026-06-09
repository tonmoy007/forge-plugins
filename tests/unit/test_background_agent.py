"""Tests for hooks/_background_agent.py (v0.2 P0 — REQ-F-001/002/003).

The adapter must (a) report capability TRUE only when `claude agents --json`
returns a JSON array, and (b) degrade to a structured no-op on every failure
mode without ever raising. We exercise it with a fake `claude` shim passed as
`claude_bin`, so no real CLI / network is touched.
"""

from __future__ import annotations

import importlib.util
import stat
import sys
from pathlib import Path

import pytest

_mod_path = Path(__file__).resolve().parent.parent.parent / "hooks" / "_background_agent.py"
_spec = importlib.util.spec_from_file_location("_background_agent", _mod_path)
_ba = importlib.util.module_from_spec(_spec)
# Register before exec so @dataclass under `from __future__ import annotations`
# can resolve its own module via sys.modules (otherwise AttributeError).
sys.modules["_background_agent"] = _ba
_spec.loader.exec_module(_ba)


def _fake_claude(tmp_path: Path, body: str) -> str:
    """Write an executable fake `claude` whose `agents --json` runs `body`."""
    script = tmp_path / "claude"
    script.write_text("#!/bin/sh\n" + body + "\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(script)


def test_available_with_no_sessions(tmp_path: Path) -> None:
    bin_ = _fake_claude(tmp_path, "echo '[]'")
    cap = _ba.detect_capability(claude_bin=bin_)
    assert cap.available is True
    assert cap.active_sessions == 0
    assert cap.as_dict()["forge_background_available"] is True


def test_available_counts_sessions(tmp_path: Path) -> None:
    bin_ = _fake_claude(tmp_path, "echo '[{\"pid\": 1}, {\"pid\": 2}]'")
    cap = _ba.detect_capability(claude_bin=bin_)
    assert cap.available is True
    assert cap.active_sessions == 2
    assert _ba.list_sessions(claude_bin=bin_) == [{"pid": 1}, {"pid": 2}]


def test_missing_binary_degrades(tmp_path: Path) -> None:
    cap = _ba.detect_capability(claude_bin=str(tmp_path / "does-not-exist"))
    assert cap.available is False
    assert "fail" in cap.reason.lower() or "not" in cap.reason.lower()
    # Degraded no-op, never raises:
    assert _ba.list_sessions(claude_bin=str(tmp_path / "does-not-exist")) == []


def test_nonzero_exit_degrades(tmp_path: Path) -> None:
    bin_ = _fake_claude(tmp_path, "echo 'boom' >&2; exit 1")
    cap = _ba.detect_capability(claude_bin=bin_)
    assert cap.available is False
    assert "failed" in cap.reason.lower()


def test_non_json_output_degrades(tmp_path: Path) -> None:
    bin_ = _fake_claude(tmp_path, "echo 'not json at all'")
    cap = _ba.detect_capability(claude_bin=bin_)
    assert cap.available is False
    assert "non-json" in cap.reason.lower()


def test_json_but_not_array_degrades(tmp_path: Path) -> None:
    bin_ = _fake_claude(tmp_path, "echo '{\"agents\": []}'")
    cap = _ba.detect_capability(claude_bin=bin_)
    assert cap.available is False
    assert "array" in cap.reason.lower()


def test_timeout_degrades(tmp_path: Path) -> None:
    bin_ = _fake_claude(tmp_path, "sleep 5; echo '[]'")
    cap = _ba.detect_capability(claude_bin=bin_, timeout=0.3)
    assert cap.available is False
    assert "timeout" in cap.reason.lower() or "failed" in cap.reason.lower()


def test_no_cli_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    # claude_bin=None and nothing resolvable on PATH → not-found, no raise.
    monkeypatch.setattr(_ba.shutil, "which", lambda _name: None)
    cap = _ba.detect_capability()
    assert cap.available is False
    assert "not found" in cap.reason.lower()
