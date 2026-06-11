"""Tests for scripts/skill_miner_bg.py (v0.2 P0 — T-139, REQ-F-027/028).

The background skill-miner is the spike's guinea pig: a real background dispatch,
instrumented so every run records a completion marker + cost to
.forge/skill-miner-runs.jsonl. completion_stats() reads those markers to produce
the O-2 number (≥90% completion over ≥5 sessions). Must never raise.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import stat
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
_mod_path = _root / "scripts" / "skill_miner_bg.py"
_spec = importlib.util.spec_from_file_location("skill_miner_bg", _mod_path)
_smb = importlib.util.module_from_spec(_spec)
sys.modules["skill_miner_bg"] = _smb
_spec.loader.exec_module(_smb)

NOW = dt.datetime(2026, 6, 10, 12, 0, 0, tzinfo=dt.timezone.utc)
_ENVELOPE = (
    '{"session_id":"miner-1","total_cost_usd":0.0046,'
    '"usage":{"input_tokens":5,"output_tokens":3},'
    '"is_error":false,"result":"done"}'
)


def _fake_claude(tmp_path: Path, body: str) -> str:
    script = tmp_path / "claude"
    script.write_text("#!/bin/sh\n" + body + "\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(script)


# --- completion stats math --------------------------------------------------

def test_completion_stats_excludes_skipped(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    for _ in range(4):
        _smb.record_run(forge, "s", "completed", 0.005, now=NOW)
    _smb.record_run(forge, "s", "failed", 0.0, now=NOW)
    for _ in range(5):
        _smb.record_run(forge, "s", "skipped", 0.0, now=NOW)
    stats = _smb.completion_stats(forge)
    assert stats["completed"] == 4
    assert stats["failed"] == 1
    assert stats["skipped"] == 5
    assert stats["completion_rate"] == 0.8  # 4 / (4+1), skipped excluded


def test_completion_stats_empty_is_safe(tmp_path: Path) -> None:
    stats = _smb.completion_stats(tmp_path / ".forge")
    assert stats["n"] == 0
    assert stats["completion_rate"] is None  # no runs yet → undefined, not a crash


def test_completion_stats_90_boundary(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    for _ in range(9):
        _smb.record_run(forge, "s", "completed", 0.005, now=NOW)
    _smb.record_run(forge, "s", "failed", 0.0, now=NOW)
    assert _smb.completion_stats(forge)["completion_rate"] == 0.9


# --- run() dispatch + recording --------------------------------------------

def test_run_records_completed_and_saves_session(tmp_path: Path) -> None:
    bin_ = _fake_claude(tmp_path, f"cat <<'EOF'\n{_ENVELOPE}\nEOF")
    forge = tmp_path / ".forge"
    status = _smb.run(forge, session_id="sess", cwd=str(tmp_path), claude_bin=bin_)
    assert status == "completed"
    runs = [json.loads(l) for l in (forge / "skill-miner-runs.jsonl").read_text().splitlines() if l.strip()]
    assert runs[-1]["status"] == "completed"
    assert runs[-1]["cost_usd"] == 0.0046
    # session persisted for reuse
    assert _smb._load_miner_session(forge) == "miner-1"


def test_run_failure_records_failed_never_raises(tmp_path: Path) -> None:
    bin_ = _fake_claude(tmp_path, "echo boom >&2; exit 1")
    forge = tmp_path / ".forge"
    status = _smb.run(forge, session_id="sess", cwd=str(tmp_path), claude_bin=bin_)
    assert status == "failed"
    runs = [json.loads(l) for l in (forge / "skill-miner-runs.jsonl").read_text().splitlines() if l.strip()]
    assert runs[-1]["status"] == "failed"


def test_run_over_cap_records_skipped(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    # The ledger entry must fall in the cost-cap's "today" bucket, which _cost_cap
    # computes from the real wall clock (run()→dispatch()→precheck() does not inject a
    # clock). Stamp it with the actual current UTC time, not a frozen constant —
    # otherwise the entry ages into "yesterday" the day after this test was written and
    # the over-cap precheck stops firing (regression: 'completed' != 'skipped').
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (forge / "cost-ledger.jsonl").write_text(
        json.dumps({"ts": ts, "feature": "x", "session_id": "s",
                    "input_tokens": 1, "output_tokens": 1,
                    "estimated_usd": 0.49, "actual_usd": 0.49}) + "\n"
    )
    bin_ = _fake_claude(tmp_path, f"cat <<'EOF'\n{_ENVELOPE}\nEOF")
    status = _smb.run(forge, session_id="sess", cwd=str(tmp_path), claude_bin=bin_)
    assert status == "skipped"
    runs = [json.loads(l) for l in (forge / "skill-miner-runs.jsonl").read_text().splitlines() if l.strip()]
    assert runs[-1]["status"] == "skipped"


def test_run_pins_cheap_model(tmp_path: Path) -> None:
    # Regression: background mining must dispatch on a cheap model (haiku), not the
    # expensive session default (real usage showed ~$1/run on the default model).
    argv_log = tmp_path / "argv.log"
    bin_ = _fake_claude(tmp_path, f'printf "%s\\n" "$*" >> "{argv_log}"\ncat <<\'EOF\'\n{_ENVELOPE}\nEOF')
    forge = tmp_path / ".forge"
    _smb.run(forge, session_id="s", cwd=str(tmp_path), claude_bin=bin_)
    assert "--model haiku" in argv_log.read_text()


def test_main_cli_smoke(tmp_path: Path) -> None:
    bin_ = _fake_claude(tmp_path, f"cat <<'EOF'\n{_ENVELOPE}\nEOF")
    forge = tmp_path / ".forge"
    rc = _smb.main(["--forge-dir", str(forge), "--session", "s",
                    "--cwd", str(tmp_path), "--claude-bin", bin_])
    assert rc == 0
    assert (forge / "skill-miner-runs.jsonl").exists()
