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


# --- dispatch half (T-137 — REQ-F-002, ADR-005) -----------------------------

_ENVELOPE = (
    '{"session_id":"sess-123","total_cost_usd":0.0528,'
    '"usage":{"input_tokens":10,"output_tokens":68},'
    '"is_error":false,"result":"pong"}'
)


def _fake_dispatch_claude(tmp_path: Path, envelope: str = _ENVELOPE) -> tuple[str, Path]:
    """Fake `claude` whose `-p` logs its argv to argv.log and prints `envelope`."""
    argv_log = tmp_path / "argv.log"
    body = f'printf "%s\\n" "$*" >> "{argv_log}"\ncat <<\'EOF\'\n{envelope}\nEOF'
    return _fake_claude(tmp_path, body), argv_log


def test_dispatch_ok_records_cost(tmp_path: Path) -> None:
    bin_, _ = _fake_dispatch_claude(tmp_path)
    forge = tmp_path / ".forge"
    res = _ba.dispatch("say pong", forge_dir=forge, feature="probe", claude_bin=bin_)
    assert res.status == "ok"
    assert res.session_id == "sess-123"
    assert res.cost_usd == 0.0528
    assert res.result == "pong"
    # actual cost recorded to the ledger
    rows = [l for l in (forge / "cost-ledger.jsonl").read_text().splitlines() if l.strip()]
    assert len(rows) == 1
    import json
    assert json.loads(rows[0])["actual_usd"] == 0.0528


def test_dispatch_passes_resume_and_json_flags(tmp_path: Path) -> None:
    bin_, argv_log = _fake_dispatch_claude(tmp_path)
    forge = tmp_path / ".forge"
    _ba.dispatch("poll", forge_dir=forge, feature="obs", resume="sess-123", claude_bin=bin_)
    argv = argv_log.read_text()
    assert "-p" in argv
    assert "--output-format json" in argv
    assert "--resume sess-123" in argv


def test_dispatch_skips_when_over_cap(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    # Pre-fill today's ledger near the $0.50 default so the floor tips it over.
    import json
    import datetime as dt
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (forge / "cost-ledger.jsonl").write_text(
        json.dumps({"ts": ts, "feature": "x", "session_id": "s",
                    "input_tokens": 1, "output_tokens": 1,
                    "estimated_usd": 0.49, "actual_usd": 0.49}) + "\n"
    )
    bin_, argv_log = _fake_dispatch_claude(tmp_path)
    res = _ba.dispatch("poll", forge_dir=forge, feature="obs", claude_bin=bin_)
    assert res.status == "skipped"
    assert "cap" in res.reason.lower()
    assert not argv_log.exists()  # claude never invoked
    # skip event logged
    assert (forge / "events.jsonl").exists()


def test_dispatch_missing_binary_degrades(tmp_path: Path) -> None:
    res = _ba.dispatch("x", forge_dir=tmp_path / ".forge", feature="f",
                       claude_bin=str(tmp_path / "nope"))
    assert res.status in ("unavailable", "error")
    # no ledger row written on a failed dispatch
    assert not (tmp_path / ".forge" / "cost-ledger.jsonl").exists()


def test_dispatch_nonzero_exit_degrades(tmp_path: Path) -> None:
    bin_ = _fake_claude(tmp_path, "echo boom >&2; exit 1")
    res = _ba.dispatch("x", forge_dir=tmp_path / ".forge", feature="f", claude_bin=bin_)
    assert res.status == "error"


def test_dispatch_non_json_degrades(tmp_path: Path) -> None:
    bin_ = _fake_claude(tmp_path, "echo 'not json'")
    res = _ba.dispatch("x", forge_dir=tmp_path / ".forge", feature="f", claude_bin=bin_)
    assert res.status == "error"
    assert "json" in res.reason.lower()


def test_dispatch_timeout_degrades(tmp_path: Path) -> None:
    bin_ = _fake_claude(tmp_path, "sleep 5; echo '{}'")
    res = _ba.dispatch("x", forge_dir=tmp_path / ".forge", feature="f",
                       claude_bin=bin_, timeout=0.3)
    assert res.status == "error"


# --- capabilities cache (T-138 — REQ-F-001) ---------------------------------

def test_write_capabilities_available(tmp_path: Path) -> None:
    bin_ = _fake_claude(tmp_path, "echo '[{\"pid\":1},{\"pid\":2}]'")
    forge = tmp_path / ".forge"
    data = _ba.write_capabilities(forge, claude_bin=bin_)
    assert data["forge_background_available"] is True
    assert data["active_sessions"] == 2
    assert "checked_at" in data
    # persisted + round-trips
    assert _ba.read_capabilities(forge)["forge_background_available"] is True


def test_write_capabilities_missing_bin(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    data = _ba.write_capabilities(forge, claude_bin=str(tmp_path / "nope"))
    assert data["forge_background_available"] is False
    assert _ba.read_capabilities(forge)["forge_background_available"] is False


def test_read_capabilities_missing_returns_none(tmp_path: Path) -> None:
    assert _ba.read_capabilities(tmp_path / ".forge") is None
