"""Tests for scripts/observer.py — the Observer daemon (T-142, REQ-F-008..014).

The Observer is a reused-session background dispatch: `/forge:watch` starts it
(idempotent), each poll reuses one session and appends findings to
`.forge/observer-findings.jsonl`, `/forge:watch-stop` stops it while preserving the
last poll output, and a compact status line reports running/last-poll/unread. Every
path is capability-gated and never raises. Tests drive a fake `claude` binary, exactly
like test_skill_miner_bg.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import stat
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
_mod_path = _root / "scripts" / "observer.py"
_spec = importlib.util.spec_from_file_location("observer", _mod_path)
_obs = importlib.util.module_from_spec(_spec)
sys.modules["observer"] = _obs
_spec.loader.exec_module(_obs)

NOW = dt.datetime(2026, 6, 11, 12, 0, 0, tzinfo=dt.timezone.utc)


def _envelope(session_id: str, result: str) -> str:
    return json.dumps({
        "session_id": session_id,
        "total_cost_usd": 0.012,
        "usage": {"input_tokens": 20, "output_tokens": 8},
        "is_error": False,
        "result": result,
    })


def _fake_claude(tmp_path: Path, body: str) -> str:
    script = tmp_path / "claude"
    script.write_text("#!/bin/sh\n" + body + "\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(script)


def _findings_claude(tmp_path: Path, session_id: str, findings: list) -> str:
    env = _envelope(session_id, json.dumps(findings))
    return _fake_claude(tmp_path, f"cat <<'EOF'\n{env}\nEOF")


def _cap(forge: Path, available: bool = True) -> None:
    forge.mkdir(parents=True, exist_ok=True)
    (forge / "capabilities.json").write_text(json.dumps(
        {"forge_background_available": available, "reason": "test"}))


# --- capability gating ------------------------------------------------------

def test_start_noop_without_capability(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _cap(forge, available=False)
    code, _ = _obs.start(forge, cwd=str(tmp_path), claude_bin="/nonexistent", now=NOW)
    assert code == "unavailable"
    assert not _obs.is_running(forge)


def test_start_noop_when_no_capabilities_file(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    forge.mkdir()
    code, _ = _obs.start(forge, cwd=str(tmp_path), claude_bin="/nonexistent", now=NOW)
    assert code == "unavailable"


# --- start / idempotency ----------------------------------------------------

def test_start_dispatches_and_records_session(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _cap(forge)
    bin_ = _findings_claude(tmp_path, "obs-1", [{"severity": "medium", "source": "git", "message": "5 files changed, no tests"}])
    code, _ = _obs.start(forge, cwd=str(tmp_path), claude_bin=bin_, now=NOW)
    assert code == "started"
    assert _obs.is_running(forge)
    sess = _obs._load_session(forge)
    assert sess["session_id"] == "obs-1"
    assert sess["status"] == "running"
    # initial poll wrote the finding
    findings = _obs.read_findings(forge)
    assert len(findings) == 1
    assert findings[0]["message"] == "5 files changed, no tests"
    assert findings[0]["severity"] == "medium"
    assert "ts" in findings[0]


def test_start_is_idempotent_warns_when_running(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _cap(forge)
    bin_ = _findings_claude(tmp_path, "obs-1", [])
    _obs.start(forge, cwd=str(tmp_path), claude_bin=bin_, now=NOW)
    code, msg = _obs.start(forge, cwd=str(tmp_path), claude_bin=bin_, now=NOW)
    assert code == "already_running"
    assert "obs-1" in msg or "running" in msg.lower()


# --- poll reuses session ----------------------------------------------------

def test_poll_reuses_session_and_appends(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _cap(forge)
    # start with one finding, then poll adds another, reusing --resume obs-1
    start_bin = _findings_claude(tmp_path, "obs-1", [{"severity": "low", "source": "a", "message": "first"}])
    _obs.start(forge, cwd=str(tmp_path), claude_bin=start_bin, now=NOW)
    argv_log = tmp_path / "argv.log"
    poll_bin = _fake_claude(
        tmp_path,
        f'printf "%s\\n" "$*" >> "{argv_log}"\ncat <<\'EOF\'\n{_envelope("obs-1", json.dumps([{"severity":"high","source":"b","message":"second"}]))}\nEOF',
    )
    later = NOW + dt.timedelta(minutes=31)
    status = _obs.poll(forge, cwd=str(tmp_path), claude_bin=poll_bin, now=later)
    assert status == "ok"
    assert "--resume obs-1" in argv_log.read_text()
    assert "--model haiku" in argv_log.read_text()  # cost rule: cheap model
    findings = _obs.read_findings(forge)
    assert [f["message"] for f in findings] == ["first", "second"]


def test_poll_noop_when_not_running(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _cap(forge)
    bin_ = _findings_claude(tmp_path, "x", [])
    assert _obs.poll(forge, cwd=str(tmp_path), claude_bin=bin_, now=NOW) == "skipped"


# --- stop preserves last output ---------------------------------------------

def test_stop_preserves_last_output(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _cap(forge)
    bin_ = _findings_claude(tmp_path, "obs-1", [{"severity": "low", "source": "a", "message": "keep me"}])
    _obs.start(forge, cwd=str(tmp_path), claude_bin=bin_, now=NOW)
    code, _ = _obs.stop(forge, now=NOW)
    assert code == "stopped"
    assert not _obs.is_running(forge)
    sess = _obs._load_session(forge)
    assert sess["status"] == "stopped"
    assert sess["last_result"]  # last poll output preserved
    # findings survive a stop
    assert len(_obs.read_findings(forge)) == 1


def test_stop_when_not_running(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    forge.mkdir()
    code, _ = _obs.stop(forge, now=NOW)
    assert code == "not_running"


# --- findings boundary: only .forge, never pipeline -------------------------

def test_poll_writes_only_to_forge_dir(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _cap(forge)
    pipeline = tmp_path / "pipeline"
    pipeline.mkdir()
    before = sorted(p.name for p in pipeline.iterdir())
    bin_ = _findings_claude(tmp_path, "obs-1", [{"severity": "high", "source": "x", "message": "m"}])
    _obs.start(forge, cwd=str(tmp_path), claude_bin=bin_, now=NOW)
    after = sorted(p.name for p in pipeline.iterdir())
    assert before == after  # REQ-F-013: never writes pipeline artifacts


# --- malformed agent output is tolerated ------------------------------------

def test_malformed_findings_yield_no_entries_no_raise(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _cap(forge)
    bin_ = _fake_claude(tmp_path, f"cat <<'EOF'\n{_envelope('obs-1', 'not json at all')}\nEOF")
    code, _ = _obs.start(forge, cwd=str(tmp_path), claude_bin=bin_, now=NOW)
    assert code == "started"            # session still starts
    assert _obs.read_findings(forge) == []  # nothing parsed, no crash


# --- status + unread cursor -------------------------------------------------

def test_status_line_and_unread(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _cap(forge)
    bin_ = _findings_claude(tmp_path, "obs-1", [
        {"severity": "low", "source": "a", "message": "one"},
        {"severity": "high", "source": "b", "message": "two"},
    ])
    _obs.start(forge, cwd=str(tmp_path), claude_bin=bin_, now=NOW)
    assert _obs.unread_count(forge) == 2
    line = _obs.status_line(forge, now=NOW)
    assert "running" in line.lower()
    assert "2" in line  # unread count surfaced
    # viewing status marks them read
    _obs.status(forge, now=NOW, mark_read=True)
    assert _obs.unread_count(forge) == 0


def test_status_line_when_never_started(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    forge.mkdir()
    line = _obs.status_line(forge, now=NOW)
    assert "not running" in line.lower() or "stopped" in line.lower()


# --- should_poll (lazy interval) --------------------------------------------

def test_should_poll_respects_interval(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _cap(forge)
    bin_ = _findings_claude(tmp_path, "obs-1", [])
    _obs.start(forge, cwd=str(tmp_path), claude_bin=bin_, now=NOW)
    # just polled at NOW (start does an initial poll)
    assert _obs.should_poll(forge, now=NOW + dt.timedelta(minutes=5)) is False
    assert _obs.should_poll(forge, now=NOW + dt.timedelta(minutes=31)) is True


def test_run_never_raises_on_dispatch_failure(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _cap(forge)
    bin_ = _fake_claude(tmp_path, "echo boom >&2; exit 1")
    code, _ = _obs.start(forge, cwd=str(tmp_path), claude_bin=bin_, now=NOW)
    assert code in ("error", "started")  # dispatch failed but did not raise
    assert _obs.read_findings(forge) == []


def test_observer_prompt_unchanged_not_tightened() -> None:
    # T-223 (REQ-CM-004): the Observer poll expects compact JSON — it is NOT tightened, and its
    # JSON-only output spec is preserved verbatim so caveman/tightening never risks its parse.
    p = _obs._PROMPT
    assert "ONLY a compact JSON" in p
    assert "No prose." in p
    assert "Forge's Observer (Stage 9)" in p
