"""Tests for scripts/autopilot.py (v0.3.1 — REQ-AP-001..003).

The autopilot planner is deterministic (no LLM): it reads pipeline state + the canonical
stage table and emits the ordered list of stages to run, honoring targets (--to/--stages),
cycle entry/exit, stage bounds, the optional `autopilot:` config block, and --resume.
It must NEVER raise (missing state, odd values -> []).
"""

from __future__ import annotations

import datetime
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
_mod_path = _ROOT / "scripts" / "autopilot.py"
_spec = importlib.util.spec_from_file_location("autopilot", _mod_path)
_ap = importlib.util.module_from_spec(_spec)
sys.modules["autopilot"] = _ap
_spec.loader.exec_module(_ap)

PYTHON = sys.executable


def _make_state(tmp_path: Path, stage: int) -> None:
    (tmp_path / "pipeline").mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "pipeline" / "state.md").write_text(
        f"---\nschema_version: 1\nproject_type: api\ncycle: 1\n"
        f"current_stage: {stage}\ncurrent_task: null\ncurrent_milestone: null\n"
        f"total_tasks: null\nlast_updated: {now}\nblockers: []\n---\n\n# State\n"
    )


# --- resolve_plan: pure target logic ---------------------------------------

def test_full_run_from_zero():
    assert _ap.resolve_plan(0) == list(range(1, 13))


def test_run_from_mid_pipeline():
    assert _ap.resolve_plan(6) == [6, 7, 8, 9, 10, 11, 12]


def test_to_target():
    assert _ap.resolve_plan(6, to=8) == [6, 7, 8]


def test_stages_count():
    assert _ap.resolve_plan(6, stages_count=2) == [6, 7]


def test_to_above_max_clamps():
    assert _ap.resolve_plan(6, to=99) == [6, 7, 8, 9, 10, 11, 12]


def test_to_below_start_is_empty():
    assert _ap.resolve_plan(6, to=3) == []


def test_stop_before_caps_end():
    cfg = _ap.AutopilotConfig(stop_before=8)
    assert _ap.resolve_plan(6, config=cfg) == [6, 7]


def test_max_stages_caps_length():
    cfg = _ap.AutopilotConfig(max_stages=2)
    assert _ap.resolve_plan(6, config=cfg) == [6, 7]


def test_until_gate_plans_to_cycle_exit():
    # until_gate runs to the end; the loop stops on a blocker at run time.
    assert _ap.resolve_plan(6, until_gate=True) == [6, 7, 8, 9, 10, 11, 12]


def test_hotfix_cycle_clamps_entry_and_exit():
    # hotfix cycle is stages 6..9 in stage-order.md.
    assert _ap.resolve_plan(6, cycle="hotfix") == [6, 7, 8, 9]


# --- plan_stages: reads state, resolves skills, resume ----------------------

def test_plan_stages_resolves_skills(tmp_path):
    _make_state(tmp_path, 6)
    plan = _ap.plan_stages(tmp_path, to=7)
    assert [p["stage"] for p in plan] == [6, 7]
    assert plan[0]["skill"] == "/forge:build"
    assert plan[1]["skill"] == "/forge:eval"


def test_plan_stages_no_state_is_empty(tmp_path):
    assert _ap.plan_stages(tmp_path, to=7) == []


def test_resume_skips_completed_stages(tmp_path):
    _make_state(tmp_path, 6)
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    (forge / "autopilot-runs.jsonl").write_text(
        json.dumps({"stage": 6, "status": "done"}) + "\n"
    )
    plan = _ap.plan_stages(tmp_path, to=8, resume=True)
    assert [p["stage"] for p in plan] == [7, 8]  # stage 6 already done


def test_plan_stages_never_raises_on_bad_state(tmp_path):
    (tmp_path / "pipeline").mkdir(parents=True)
    (tmp_path / "pipeline" / "state.md").write_text("not: valid: [[\n")
    # Must degrade to [], not raise.
    assert _ap.plan_stages(tmp_path, to=7) == []


# --- config loading ---------------------------------------------------------

def test_load_config_defaults_when_absent(tmp_path):
    cfg = _ap.load_config(tmp_path / ".forge")
    assert cfg.max_stages is None and cfg.stop_before is None
    assert cfg.allow_force is False


def test_load_config_reads_autopilot_section(tmp_path):
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    (forge / "config.yaml").write_text(
        "autopilot:\n  max_stages: 3\n  stop_before: 8\n  allow_force: true\n"
    )
    cfg = _ap.load_config(forge)
    assert cfg.max_stages == 3 and cfg.stop_before == 8 and cfg.allow_force is True


# --- CLI smoke --------------------------------------------------------------

def test_cli_json_plan(tmp_path):
    _make_state(tmp_path, 6)
    r = subprocess.run(
        [PYTHON, str(_mod_path), "--cwd", str(tmp_path), "--to", "7", "--json"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    plan = json.loads(r.stdout)
    assert [p["stage"] for p in plan] == [6, 7]


def test_cli_dry_run_no_side_effects(tmp_path):
    _make_state(tmp_path, 6)
    r = subprocess.run(
        [PYTHON, str(_mod_path), "--cwd", str(tmp_path), "--to", "7", "--dry-run"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    # planner never writes; the run-log must not appear from a dry-run plan.
    assert not (tmp_path / ".forge" / "autopilot-runs.jsonl").exists()


# --- record (run-log) -------------------------------------------------------

def test_record_run_appends_and_completed_reads(tmp_path):
    forge = tmp_path / ".forge"
    assert _ap.record_run(forge, 6, "done") is True
    assert 6 in _ap._completed_stages(forge)


def test_cli_record_then_resume_skips(tmp_path):
    _make_state(tmp_path, 6)
    r = subprocess.run(
        [PYTHON, str(_mod_path), "record", "--cwd", str(tmp_path),
         "--stage", "6", "--status", "done"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert (tmp_path / ".forge" / "autopilot-runs.jsonl").exists()
    plan = _ap.plan_stages(tmp_path, to=8, resume=True)
    assert [p["stage"] for p in plan] == [7, 8]


def test_cli_record_requires_stage(tmp_path):
    r = subprocess.run(
        [PYTHON, str(_mod_path), "record", "--cwd", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert r.returncode == 2  # usage error: --stage required


# --- background substrate (REQ-AP-006) -------------------------------------

def _caps(forge: Path, available: bool) -> None:
    forge.mkdir(parents=True, exist_ok=True)
    (forge / "capabilities.json").write_text(
        json.dumps({"forge_background_available": available})
    )


def test_run_stage_in_session_marker(tmp_path):
    out = _ap.run_stage(tmp_path, 6, "/forge:build", mode="in-session")
    assert out["status"] == "in-session"


def test_run_stage_background_killswitch_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_NO_BACKGROUND", "1")
    _caps(tmp_path / ".forge", True)
    called = []
    monkeypatch.setattr(_ap._background_agent, "dispatch",
                        lambda *a, **k: called.append(1))
    out = _ap.run_stage(tmp_path, 6, "/forge:build", mode="background")
    assert out["status"] == "unavailable"
    assert not called  # never dispatched under the kill switch


def test_run_stage_background_no_capability_noop(tmp_path, monkeypatch):
    monkeypatch.delenv("FORGE_NO_BACKGROUND", raising=False)
    called = []
    monkeypatch.setattr(_ap._background_agent, "dispatch",
                        lambda *a, **k: called.append(1))
    out = _ap.run_stage(tmp_path, 6, "/forge:build", mode="background")  # no caps file
    assert out["status"] == "unavailable"
    assert not called


def test_run_stage_background_dispatches_with_session_reuse(tmp_path, monkeypatch):
    monkeypatch.delenv("FORGE_NO_BACKGROUND", raising=False)
    _caps(tmp_path / ".forge", True)

    calls = []

    class _Res:
        status = "ok"
        session_id = "S2"
        cost_usd = 0.004
        reason = "dispatched"

    def fake_dispatch(prompt, **kw):
        calls.append(kw)
        return _Res()

    monkeypatch.setattr(_ap._background_agent, "dispatch", fake_dispatch)
    out = _ap.run_stage(tmp_path, 6, "/forge:build", "Build",
                        mode="background", session_id="S1")
    assert out["status"] == "ok"
    assert out["session_id"] == "S2"
    assert calls and calls[0]["resume"] == "S1"  # reuses the session
    assert calls[0]["feature"] == "autopilot-stage"


def test_cli_dispatch_unavailable_killswitch(tmp_path):
    _make_state(tmp_path, 6)
    env = {**os.environ, "FORGE_NO_BACKGROUND": "1"}
    r = subprocess.run(
        [PYTHON, str(_mod_path), "dispatch", "--cwd", str(tmp_path),
         "--stage", "6", "--skill", "/forge:build"],
        capture_output=True, text=True, env=env,
    )
    assert r.returncode == 0
    assert json.loads(r.stdout)["status"] == "unavailable"


def test_cli_dispatch_requires_stage(tmp_path):
    r = subprocess.run(
        [PYTHON, str(_mod_path), "dispatch", "--cwd", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert r.returncode == 2


# --- run-level task budget (T-168, REQ-HARNESS-002) ------------------------

def test_load_config_reads_max_budget(tmp_path):
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    (forge / "config.yaml").write_text("autopilot:\n  max_budget_usd: 0.25\n")
    assert _ap.load_config(forge).max_budget_usd == 0.25


def test_run_stage_background_passes_max_budget(tmp_path, monkeypatch):
    monkeypatch.delenv("FORGE_NO_BACKGROUND", raising=False)
    _caps(tmp_path / ".forge", True)

    calls = []

    class _Res:
        status = "ok"
        session_id = "S2"
        cost_usd = 0.0
        reason = ""

    monkeypatch.setattr(_ap._background_agent, "dispatch",
                        lambda prompt, **kw: (calls.append(kw), _Res())[1])
    _ap.run_stage(tmp_path, 6, "/forge:build", mode="background", max_budget_usd=0.25)
    assert calls[0]["max_budget_usd"] == 0.25


# --- per-stage model routing (T-169, REQ-HARNESS-003) ----------------------

def test_load_config_reads_models(tmp_path):
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    (forge / "config.yaml").write_text(
        "autopilot:\n  models:\n    6: claude-opus-4-8\n    eval: claude-haiku-4-5\n"
    )
    cfg = _ap.load_config(forge)
    assert isinstance(cfg.models, dict) and cfg.models


def test_model_for_stage_numeric_key():
    cfg = _ap.AutopilotConfig(models={6: "claude-opus-4-8", 7: "claude-haiku-4-5"})
    assert _ap.model_for_stage(cfg, 6) == "claude-opus-4-8"
    assert _ap.model_for_stage(cfg, 7) == "claude-haiku-4-5"


def test_model_for_stage_command_word_key():
    # stage 6's skill is /forge:build → keyable as "build"
    cfg = _ap.AutopilotConfig(models={"build": "claude-opus-4-8"})
    assert _ap.model_for_stage(cfg, 6) == "claude-opus-4-8"


def test_model_for_stage_falls_back_to_single_model():
    cfg = _ap.AutopilotConfig(model="claude-haiku-4-5")  # no per-stage map
    assert _ap.model_for_stage(cfg, 6) == "claude-haiku-4-5"


def test_model_for_stage_none_when_unset():
    assert _ap.model_for_stage(_ap.AutopilotConfig(), 6) is None


# --- session / cancel (REQ-AP-007) -----------------------------------------

def test_start_session_idempotent(tmp_path):
    forge = tmp_path / ".forge"
    assert _ap.start_session(forge)["status"] == "started"
    assert _ap.start_session(forge)["status"] == "already_running"


def test_request_stop_sets_flag(tmp_path):
    forge = tmp_path / ".forge"
    _ap.start_session(forge)
    assert _ap.stop_requested(forge) is False
    _ap.request_stop(forge)
    assert _ap.stop_requested(forge) is True


def test_finish_clears_stop_and_idles(tmp_path):
    forge = tmp_path / ".forge"
    _ap.start_session(forge)
    _ap.request_stop(forge)
    _ap.finish_session(forge)
    assert _ap.stop_requested(forge) is False
    assert _ap.read_session(forge)["status"] == "idle"
    # After finishing, a fresh start is allowed again (not already_running).
    assert _ap.start_session(forge)["status"] == "started"


def test_read_session_absent_is_empty(tmp_path):
    assert _ap.read_session(tmp_path / ".forge") == {}


def test_cli_stop_then_status(tmp_path):
    cwd = str(tmp_path)
    subprocess.run([PYTHON, str(_mod_path), "start", "--cwd", cwd],
                   capture_output=True, text=True)
    r_stop = subprocess.run([PYTHON, str(_mod_path), "stop", "--cwd", cwd],
                            capture_output=True, text=True)
    assert r_stop.returncode == 0
    r_status = subprocess.run([PYTHON, str(_mod_path), "status", "--cwd", cwd],
                              capture_output=True, text=True)
    assert json.loads(r_status.stdout)["stop_requested"] is True
