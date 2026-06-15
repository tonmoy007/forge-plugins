"""Tests for scripts/telemetry.py (v0.3.4 / M4 — REQ-F-053).

Opt-in, **default-off**, **local-only** skill-mining telemetry. Nothing is recorded unless
the user explicitly enables it; data stays in `.forge/telemetry.jsonl` and is only ever
emitted by an explicit `export`. The module never raises into its caller.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
_mod_path = _ROOT / "scripts" / "telemetry.py"
_spec = importlib.util.spec_from_file_location("telemetry", _mod_path)
_tm = importlib.util.module_from_spec(_spec)
sys.modules["telemetry"] = _tm
_spec.loader.exec_module(_tm)

PYTHON = sys.executable


# --- opt-in state ----------------------------------------------------------

def test_disabled_by_default(tmp_path):
    assert _tm.is_enabled(tmp_path / ".forge") is False


def test_enable_then_disable(tmp_path):
    forge = tmp_path / ".forge"
    assert _tm.enable(forge) is True
    assert _tm.is_enabled(forge) is True
    assert _tm.disable(forge) is True
    assert _tm.is_enabled(forge) is False


def test_config_yaml_enables(tmp_path):
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    (forge / "config.yaml").write_text("telemetry:\n  enabled: true\n")
    assert _tm.is_enabled(forge) is True


# --- recording: gated on opt-in, local-only --------------------------------

def test_record_is_noop_when_disabled(tmp_path):
    forge = tmp_path / ".forge"
    assert _tm.record(forge, "skill_mined", name="x") is False
    assert not (forge / "telemetry.jsonl").exists()  # nothing written


def test_record_writes_when_enabled(tmp_path):
    forge = tmp_path / ".forge"
    _tm.enable(forge)
    assert _tm.record(forge, "skill_mined", name="batch-build", count=3) is True
    data = (forge / "telemetry.jsonl").read_text().strip().splitlines()
    assert len(data) == 1
    row = json.loads(data[0])
    assert row["event"] == "skill_mined" and row["name"] == "batch-build"
    assert "ts" in row


def test_summary_counts_by_event(tmp_path):
    forge = tmp_path / ".forge"
    _tm.enable(forge)
    _tm.record(forge, "skill_mined", name="a")
    _tm.record(forge, "skill_mined", name="b")
    _tm.record(forge, "proposal_shown")
    s = _tm.summary(forge)
    assert s.get("skill_mined") == 2
    assert s.get("proposal_shown") == 1


def test_export_emits_recorded_lines(tmp_path):
    forge = tmp_path / ".forge"
    _tm.enable(forge)
    _tm.record(forge, "skill_mined", name="x")
    out = _tm.export_data(forge)
    assert "skill_mined" in out


def test_export_empty_when_none(tmp_path):
    assert _tm.export_data(tmp_path / ".forge") == ""


def test_helpers_never_raise_on_bad_dir(tmp_path):
    # A path whose parent is a file (cannot mkdir) must not raise.
    f = tmp_path / "afile"
    f.write_text("x")
    assert _tm.record(f / "nested" / ".forge", "e") is False
    assert _tm.is_enabled(f / "nested" / ".forge") is False


# --- CLI -------------------------------------------------------------------

def test_cli_status_default_disabled(tmp_path):
    r = subprocess.run([PYTHON, str(_mod_path), "status", "--cwd", str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "disabled" in r.stdout.lower() or "off" in r.stdout.lower()


def test_cli_enable_record_summary_cycle(tmp_path):
    cwd = str(tmp_path)
    assert subprocess.run([PYTHON, str(_mod_path), "enable", "--cwd", cwd],
                          capture_output=True, text=True).returncode == 0
    assert subprocess.run([PYTHON, str(_mod_path), "record", "--cwd", cwd,
                           "--event", "skill_mined"],
                          capture_output=True, text=True).returncode == 0
    r = subprocess.run([PYTHON, str(_mod_path), "summary", "--cwd", cwd],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "skill_mined" in r.stdout


def test_cli_record_noop_when_disabled_is_clean(tmp_path):
    r = subprocess.run([PYTHON, str(_mod_path), "record", "--cwd", str(tmp_path),
                        "--event", "skill_mined"], capture_output=True, text=True)
    assert r.returncode == 0  # disabled → silent no-op, not an error
    assert not (tmp_path / ".forge" / "telemetry.jsonl").exists()
