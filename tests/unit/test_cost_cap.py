"""Tests for hooks/_cost_cap.py (v0.2 P0 — REQ-F-004/005/006/007, ADR-007).

The cost cap is the hard-prerequisite spend gate. It must:
  - read caps from .forge/config.yaml (fail-soft to defaults),
  - sum spend from .forge/cost-ledger.jsonl using actual_usd where present
    else estimated_usd,
  - pre-check `spent + floor` against the daily (and optional monthly) cap,
  - append well-formed ledger entries,
  - log an over-cap skip event to .forge/events.jsonl,
  - NEVER raise (REQ-NF-006), even on missing/corrupt config or ledger.

Stdlib + a fake-friendly yaml import only; no real CLI / network touched.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_mod_path = Path(__file__).resolve().parent.parent.parent / "hooks" / "_cost_cap.py"
_spec = importlib.util.spec_from_file_location("_cost_cap", _mod_path)
_cc = importlib.util.module_from_spec(_spec)
# Register before exec so @dataclass under `from __future__ import annotations`
# can resolve its own module via sys.modules (otherwise AttributeError).
sys.modules["_cost_cap"] = _cc
_spec.loader.exec_module(_cc)

NOW = dt.datetime(2026, 6, 10, 12, 0, 0, tzinfo=dt.timezone.utc)


def _write_config(forge: Path, body: str) -> None:
    forge.mkdir(parents=True, exist_ok=True)
    (forge / "config.yaml").write_text(body)


def _ledger_lines(forge: Path) -> list[dict]:
    path = forge / "cost-ledger.jsonl"
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


# --- caps loading -----------------------------------------------------------

def test_default_caps_when_no_config(tmp_path: Path) -> None:
    caps = _cc.load_caps(tmp_path / ".forge")
    assert caps.daily_usd == _cc.DEFAULT_DAILY_USD == 0.50
    assert caps.monthly_usd is None


def test_config_overrides_caps(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _write_config(forge, "cost_cap:\n  daily_usd: 2.0\n  monthly_usd: 25.0\n")
    caps = _cc.load_caps(forge)
    assert caps.daily_usd == 2.0
    assert caps.monthly_usd == 25.0


def test_malformed_config_falls_back_to_defaults(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _write_config(forge, "cost_cap: [this is not a mapping\n:::")
    caps = _cc.load_caps(forge)  # must not raise
    assert caps.daily_usd == _cc.DEFAULT_DAILY_USD


# --- precheck (the gate) ----------------------------------------------------

def test_precheck_allows_on_empty_ledger(tmp_path: Path) -> None:
    d = _cc.precheck(tmp_path / ".forge", floor_usd=0.06, now=NOW)
    assert d.allowed is True
    assert d.spent_today == 0.0


def test_precheck_denies_when_floor_would_exceed_daily(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _cc.record(forge, feature="obs", session_id="s1", input_tokens=10,
               output_tokens=5, estimated_usd=0.06, actual_usd=0.47, now=NOW)
    d = _cc.precheck(forge, floor_usd=0.06, now=NOW)  # 0.47 + 0.06 = 0.53 > 0.50
    assert d.allowed is False
    assert "daily" in d.reason.lower()


def test_precheck_uses_actual_where_present_else_estimated(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    # actual present -> counts 0.40 (NOT the 0.01 estimate)
    _cc.record(forge, feature="a", session_id="s", input_tokens=1, output_tokens=1,
               estimated_usd=0.01, actual_usd=0.40, now=NOW)
    # actual missing -> counts the estimate 0.05
    _cc.record(forge, feature="b", session_id="s", input_tokens=1, output_tokens=1,
               estimated_usd=0.05, actual_usd=None, now=NOW)
    d = _cc.precheck(forge, floor_usd=0.0, now=NOW)
    assert d.spent_today == pytest.approx(0.45)


def test_daily_window_excludes_prior_days(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    yesterday = NOW - dt.timedelta(days=1)
    _cc.record(forge, feature="old", session_id="s", input_tokens=1, output_tokens=1,
               estimated_usd=0.40, actual_usd=0.40, now=yesterday)
    d = _cc.precheck(forge, floor_usd=0.06, now=NOW)
    assert d.spent_today == 0.0
    assert d.allowed is True  # yesterday's spend doesn't count today


# --- monthly cap ------------------------------------------------------------

def test_monthly_cap_enforced(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _write_config(forge, "cost_cap:\n  daily_usd: 100.0\n  monthly_usd: 1.0\n")
    _cc.record(forge, feature="x", session_id="s", input_tokens=1, output_tokens=1,
               estimated_usd=0.9, actual_usd=0.9, now=NOW - dt.timedelta(days=10))
    d = _cc.precheck(forge, floor_usd=0.2, now=NOW)  # 0.9 + 0.2 = 1.1 > 1.0
    assert d.allowed is False
    assert "month" in d.reason.lower()


def test_monthly_window_excludes_older_than_30_days(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _write_config(forge, "cost_cap:\n  daily_usd: 100.0\n  monthly_usd: 1.0\n")
    _cc.record(forge, feature="x", session_id="s", input_tokens=1, output_tokens=1,
               estimated_usd=0.9, actual_usd=0.9, now=NOW - dt.timedelta(days=40))
    d = _cc.precheck(forge, floor_usd=0.2, now=NOW)
    assert d.allowed is True  # 40 days ago is outside the rolling 30-day window


# --- record + ledger schema -------------------------------------------------

def test_record_appends_full_schema(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _cc.record(forge, feature="observer", session_id="abc", input_tokens=10,
               output_tokens=68, estimated_usd=0.06, actual_usd=0.0528, now=NOW)
    rows = _ledger_lines(forge)
    assert len(rows) == 1
    row = rows[0]
    for k in ("ts", "feature", "session_id", "input_tokens", "output_tokens",
              "estimated_usd", "actual_usd"):
        assert k in row
    assert row["feature"] == "observer"
    assert row["session_id"] == "abc"
    assert row["actual_usd"] == 0.0528


# --- skip event -------------------------------------------------------------

def test_note_skip_logs_event(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _cc.note_skip(forge, feature="observer", session_id="abc", reason="daily cap reached")
    events = (forge / "events.jsonl").read_text().splitlines()
    assert len(events) == 1
    ev = json.loads(events[0])
    assert "cost" in ev["type"].lower()


# --- never raises -----------------------------------------------------------

def test_precheck_tolerates_corrupt_ledger(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    (forge / "cost-ledger.jsonl").write_text("not json\n{partial\n")
    d = _cc.precheck(forge, floor_usd=0.06, now=NOW)  # must not raise
    assert d.allowed is True  # unreadable lines ignored -> spend 0


def test_precheck_degrades_when_yaml_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate PyYAML absent: loader returns None -> defaults, never raises.
    monkeypatch.setattr(_cc, "_safe_yaml_load", lambda _text: None)
    forge = tmp_path / ".forge"
    _write_config(forge, "cost_cap:\n  daily_usd: 2.0\n")
    caps = _cc.load_caps(forge)
    assert caps.daily_usd == _cc.DEFAULT_DAILY_USD  # fell back, didn't crash
