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


# --- long-run context: session rotation (T-170, REQ-HARNESS-004) -----------

def test_should_rotate_session():
    cfg = _ap.AutopilotConfig(session_max_dispatches=5)
    assert _ap.should_rotate_session(5, cfg) is True
    assert _ap.should_rotate_session(6, cfg) is True
    assert _ap.should_rotate_session(4, cfg) is False


def test_should_rotate_session_unset_never_rotates():
    assert _ap.should_rotate_session(1000, _ap.AutopilotConfig()) is False


def test_load_config_reads_session_max_dispatches(tmp_path):
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    (forge / "config.yaml").write_text("autopilot:\n  session_max_dispatches: 8\n")
    assert _ap.load_config(forge).session_max_dispatches == 8


# --- v0.3.6 context-pressure rotation (REQ-CTX-001..003) -------------------

def test_should_rotate_for_context_threshold_boundary():
    cfg = _ap.AutopilotConfig(context_window_size=200000, context_threshold_percent=80.0)
    assert _ap.should_rotate_for_context(160000, cfg) is True   # exactly 80% of 200k
    assert _ap.should_rotate_for_context(170000, cfg) is True   # above threshold
    assert _ap.should_rotate_for_context(159999, cfg) is False  # below threshold


def test_should_rotate_for_context_window_unset_never():
    cfg = _ap.AutopilotConfig(context_threshold_percent=80.0)  # no window ⇒ feature off
    assert _ap.should_rotate_for_context(10_000_000, cfg) is False


def test_should_rotate_for_context_garbage_never_raises():
    cfg = _ap.AutopilotConfig(context_window_size=200000)
    assert _ap.should_rotate_for_context(None, cfg) is False
    assert _ap.should_rotate_for_context("lots", cfg) is False
    assert _ap.should_rotate_for_context(-5, cfg) is False


def test_load_config_context_defaults(tmp_path):
    cfg = _ap.load_config(tmp_path / ".forge")
    assert cfg.context_window_size is None          # opt-in: off by default
    assert cfg.context_threshold_percent == 80.0    # default trigger


def test_load_config_reads_context_knobs(tmp_path):
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    (forge / "config.yaml").write_text(
        "autopilot:\n  context_window_size: 200000\n  context_threshold_percent: 70\n")
    cfg = _ap.load_config(forge)
    assert cfg.context_window_size == 200000
    assert cfg.context_threshold_percent == 70.0


def test_load_config_ignores_bad_context_values(tmp_path):
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    (forge / "config.yaml").write_text(
        "autopilot:\n  context_window_size: huge\n  context_threshold_percent: nope\n")
    cfg = _ap.load_config(forge)
    assert cfg.context_window_size is None
    assert cfg.context_threshold_percent == 80.0    # bad value ⇒ keep default


def test_dispatch_surfaces_input_tokens(tmp_path, monkeypatch):
    monkeypatch.delenv("FORGE_NO_BACKGROUND", raising=False)
    _caps(tmp_path / ".forge", True)

    class _Res:
        status = "ok"
        session_id = "S"
        cost_usd = 0.0
        reason = ""
        result = None
        raw = {"usage": {"input_tokens": 170000, "output_tokens": 12}}

    monkeypatch.setattr(_ap._background_agent, "dispatch", lambda prompt, **kw: _Res())
    out = _ap.run_stage(tmp_path, 6, "/forge:build", mode="background", session_id="S")
    assert out["input_tokens"] == 170000  # surfaced for the context-pressure check


# --- v0.3.6 checkpoint artifact (REQ-CTX-004, 005, 008) --------------------

def test_read_checkpoint_absent_returns_empty(tmp_path):
    assert _ap.read_checkpoint(tmp_path / ".forge") == {}


def test_read_checkpoint_malformed_returns_empty(tmp_path):
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    (forge / _ap._CHECKPOINT_NAME).write_text("{not json")
    assert _ap.read_checkpoint(forge) == {}


def test_write_checkpoint_round_trips(tmp_path):
    forge = tmp_path / ".forge"
    ok = _ap.write_checkpoint(forge, {"current_stage": 6, "remaining_stages": [6, 7],
                                      "dispatch_count": 3, "last_input_tokens": 170000,
                                      "last_session_id": "S", "next_action": "resume at 6"})
    assert ok is True
    cp = _ap.read_checkpoint(forge)
    assert cp["current_stage"] == 6
    assert cp["remaining_stages"] == [6, 7]
    assert cp["last_input_tokens"] == 170000
    assert cp["schema_version"] == _ap._CHECKPOINT_SCHEMA_VERSION
    assert cp["ts"]  # stamped


def test_write_checkpoint_is_atomic_no_tmp_left(tmp_path):
    forge = tmp_path / ".forge"
    _ap.write_checkpoint(forge, {"current_stage": 1})
    assert list(forge.glob("*.tmp")) == []


def test_write_checkpoint_preserves_run_started_at(tmp_path):
    forge = tmp_path / ".forge"
    _ap.write_checkpoint(forge, {"current_stage": 1})
    first = _ap.read_checkpoint(forge)["run_started_at"]
    _ap.write_checkpoint(forge, {"current_stage": 2})
    assert _ap.read_checkpoint(forge)["run_started_at"] == first  # stable across updates


def test_build_and_write_checkpoint_derives_from_planner(tmp_path):
    _make_state(tmp_path, 6)
    ok = _ap.build_and_write_checkpoint(tmp_path, dispatch_count=2,
                                        last_input_tokens=170000, last_session_id="S")
    assert ok is True
    cp = _ap.read_checkpoint(tmp_path / ".forge")
    assert cp["current_stage"] == 6
    assert cp["remaining_stages"][0] == 6
    assert cp["last_input_tokens"] == 170000
    assert "6" in cp["next_action"]


def test_checkpoint_cli_writes_artifact(tmp_path):
    _make_state(tmp_path, 6)
    res = subprocess.run([PYTHON, str(_mod_path), "checkpoint", "--cwd", str(tmp_path),
                          "--dispatch-count", "2", "--last-input-tokens", "170000",
                          "--session", "S"], capture_output=True, text=True)
    assert res.returncode == 0
    assert (tmp_path / ".forge" / _ap._CHECKPOINT_NAME).exists()


def test_run_stage_rotate_starts_fresh_session(tmp_path, monkeypatch):
    monkeypatch.delenv("FORGE_NO_BACKGROUND", raising=False)
    _caps(tmp_path / ".forge", True)
    calls = []

    class _Res:
        status = "ok"
        session_id = "NEW"
        cost_usd = 0.0
        reason = ""

    monkeypatch.setattr(_ap._background_agent, "dispatch",
                        lambda prompt, **kw: (calls.append(kw), _Res())[1])
    _ap.run_stage(tmp_path, 6, "/forge:build", mode="background",
                  session_id="OLD", rotate=True)
    assert calls[0]["resume"] is None  # rotated → fresh session (bounds context growth)


def test_run_stage_no_rotate_keeps_session(tmp_path, monkeypatch):
    monkeypatch.delenv("FORGE_NO_BACKGROUND", raising=False)
    _caps(tmp_path / ".forge", True)
    calls = []

    class _Res:
        status = "ok"
        session_id = "OLD"
        cost_usd = 0.0
        reason = ""

    monkeypatch.setattr(_ap._background_agent, "dispatch",
                        lambda prompt, **kw: (calls.append(kw), _Res())[1])
    _ap.run_stage(tmp_path, 6, "/forge:build", mode="background", session_id="OLD")
    assert calls[0]["resume"] == "OLD"  # default: reuse session (cost)


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


# --- self-heal loop (T-172, REQ-AUTO-001/002) ------------------------------

def test_max_heal_attempts_defaults_to_one():
    # Default policy: one bounded heal attempt per stage before STOP.
    assert _ap.AutopilotConfig().max_heal_attempts == 1


def test_load_config_reads_max_heal_attempts(tmp_path):
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    (forge / "config.yaml").write_text("autopilot:\n  max_heal_attempts: 3\n")
    assert _ap.load_config(forge).max_heal_attempts == 3


def test_load_config_max_heal_attempts_zero_is_stop_on_gate(tmp_path):
    # 0 is meaningful (not "unset"): it restores v0.3.1 stop-on-gate behavior.
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    (forge / "config.yaml").write_text("autopilot:\n  max_heal_attempts: 0\n")
    assert _ap.load_config(forge).max_heal_attempts == 0


def test_should_heal_default_allows_one_attempt():
    cfg = _ap.AutopilotConfig()  # max_heal_attempts == 1
    assert _ap.should_heal(0, cfg) is True   # first blocker → heal
    assert _ap.should_heal(1, cfg) is False  # after one heal → STOP


def test_should_heal_zero_never_heals():
    cfg = _ap.AutopilotConfig(max_heal_attempts=0)
    assert _ap.should_heal(0, cfg) is False  # == v0.3.1 stop-on-gate


def test_should_heal_respects_higher_cap():
    cfg = _ap.AutopilotConfig(max_heal_attempts=3)
    assert _ap.should_heal(2, cfg) is True
    assert _ap.should_heal(3, cfg) is False


def test_run_heal_in_session_marker(tmp_path):
    out = _ap.run_heal(tmp_path, 6, "/forge:resolve", "Build")
    assert out["status"] == "in-session"
    assert out["stage"] == 6


def test_run_heal_background_killswitch_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_NO_BACKGROUND", "1")
    out = _ap.run_heal(tmp_path, 6, "/forge:resolve", mode="background")
    assert out["status"] == "unavailable"


def test_run_heal_background_dispatches_resolve(tmp_path, monkeypatch):
    monkeypatch.delenv("FORGE_NO_BACKGROUND", raising=False)
    _caps(tmp_path / ".forge", True)
    calls = []

    class _Res:
        status = "ok"
        session_id = "S2"
        cost_usd = 0.004
        reason = "healed"

    def fake_dispatch(prompt, **kw):
        calls.append((prompt, kw))
        return _Res()

    monkeypatch.setattr(_ap._background_agent, "dispatch", fake_dispatch)
    out = _ap.run_heal(tmp_path, 6, "/forge:resolve", "Build",
                       mode="background", session_id="S1", blockers="gate X failed")
    assert out["status"] == "ok"
    assert out["session_id"] == "S2"
    prompt, kw = calls[0]
    assert kw["feature"] == "autopilot-heal"   # distinct ledger feature from stage runs
    assert kw["resume"] == "S1"                 # heal reuses the run session
    assert "resolve" in prompt.lower()          # routes through the Stage-11 resolver
    assert "gate X failed" in prompt            # blockers threaded into the heal prompt


def test_run_heal_background_passes_budget_and_model(tmp_path, monkeypatch):
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
    _ap.run_heal(tmp_path, 6, "/forge:resolve", mode="background",
                 model="claude-haiku-4-5", max_budget_usd=0.10)
    assert calls[0]["max_budget_usd"] == 0.10
    assert calls[0]["model"] == "claude-haiku-4-5"


def test_cli_heal_requires_stage(tmp_path):
    r = subprocess.run([PYTHON, str(_mod_path), "heal", "--cwd", str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 2


def test_cli_heal_unavailable_killswitch(tmp_path):
    _make_state(tmp_path, 6)
    env = {**os.environ, "FORGE_NO_BACKGROUND": "1"}
    r = subprocess.run(
        [PYTHON, str(_mod_path), "heal", "--cwd", str(tmp_path),
         "--stage", "6", "--skill", "/forge:resolve"],
        capture_output=True, text=True, env=env,
    )
    assert r.returncode == 0
    assert json.loads(r.stdout)["status"] == "unavailable"


# --- self-verification (T-173, REQ-AUTO-003) -------------------------------

def test_verify_disabled_by_default():
    assert _ap.AutopilotConfig().verify is False


def test_load_config_reads_verify(tmp_path):
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    (forge / "config.yaml").write_text("autopilot:\n  verify: true\n")
    assert _ap.load_config(forge).verify is True


def test_run_verify_in_session_marker(tmp_path):
    out = _ap.run_verify(tmp_path, 6, "/forge:build", "Build")
    assert out["status"] == "in-session"
    assert out["stage"] == 6


def test_run_verify_background_fresh_context_and_schema(tmp_path, monkeypatch):
    monkeypatch.delenv("FORGE_NO_BACKGROUND", raising=False)
    _caps(tmp_path / ".forge", True)
    calls = []

    class _Res:
        status = "ok"
        session_id = "V1"
        cost_usd = 0.003
        reason = ""
        result = '{"verdict": "pass"}'

    def fake_dispatch(prompt, **kw):
        calls.append((prompt, kw))
        return _Res()

    monkeypatch.setattr(_ap._background_agent, "dispatch", fake_dispatch)
    out = _ap.run_verify(tmp_path, 6, "/forge:build", "Build", mode="background")
    prompt, kw = calls[0]
    assert kw["feature"] == "autopilot-verify"
    assert kw["resume"] is None                       # fresh context — never reuse the stage session
    assert kw["output_schema"] == _ap.VERIFY_SCHEMA   # structured verdict
    assert "independent" in prompt.lower()
    assert out["result"] == '{"verdict": "pass"}'


def test_verdict_failed_true_on_fail():
    assert _ap.verdict_failed({"result": '{"verdict": "fail", "reasons": ["x"]}'}) is True


def test_verdict_failed_false_on_pass():
    assert _ap.verdict_failed({"result": '{"verdict": "pass"}'}) is False


def test_verdict_failed_degrades_on_garbage():
    # A broken/empty/unavailable verifier must NOT block an already-passing gate.
    assert _ap.verdict_failed({"result": "not json"}) is False
    assert _ap.verdict_failed({"status": "unavailable"}) is False
    assert _ap.verdict_failed({}) is False


def test_cli_verify_requires_stage(tmp_path):
    r = subprocess.run([PYTHON, str(_mod_path), "verify", "--cwd", str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 2


def test_cli_verify_unavailable_killswitch(tmp_path):
    _make_state(tmp_path, 6)
    env = {**os.environ, "FORGE_NO_BACKGROUND": "1"}
    r = subprocess.run(
        [PYTHON, str(_mod_path), "verify", "--cwd", str(tmp_path),
         "--stage", "6", "--skill", "/forge:build"],
        capture_output=True, text=True, env=env,
    )
    assert r.returncode == 0
    assert json.loads(r.stdout)["status"] == "unavailable"


# --- unattended mode (T-174, REQ-AUTO-004/005) -----------------------------

def test_read_answers_absent_is_empty(tmp_path):
    assert _ap.read_answers(tmp_path / ".forge") == {}


def test_read_answers_json(tmp_path):
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    (forge / "autopilot-answers.json").write_text('{"1": "use postgres", "4": "rest"}')
    assert _ap.read_answers(forge)["1"] == "use postgres"


def test_read_answers_yaml(tmp_path):
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    (forge / "autopilot-answers.yaml").write_text("1: use postgres\n4: rest\n")
    ans = _ap.read_answers(forge)
    assert str(ans.get(1) or ans.get("1")) == "use postgres"


def test_read_answers_malformed_is_empty(tmp_path):
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    (forge / "autopilot-answers.json").write_text("{not json")
    assert _ap.read_answers(forge) == {}


def test_answers_for_stage_numeric_and_string():
    ans = {1: "a", "4": "b"}
    assert _ap.answers_for_stage(ans, 1) == "a"
    assert _ap.answers_for_stage(ans, 4) == "b"
    assert _ap.answers_for_stage(ans, 9) is None


def test_record_assumption_logs_but_not_completed(tmp_path):
    forge = tmp_path / ".forge"
    assert _ap.record_assumption(forge, 1, "assumed REST API") is True
    # An assumption alone must NOT mark the stage complete for --resume.
    assert 1 not in _ap._completed_stages(forge)


def test_cli_answers_echoes_loaded(tmp_path):
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    (forge / "autopilot-answers.json").write_text('{"1": "x"}')
    r = subprocess.run([PYTHON, str(_mod_path), "answers", "--cwd", str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert json.loads(r.stdout)["1"] == "x"


def test_cli_plan_unattended_accepted(tmp_path):
    _make_state(tmp_path, 6)
    r = subprocess.run([PYTHON, str(_mod_path), "--cwd", str(tmp_path),
                        "--unattended", "--json"], capture_output=True, text=True)
    assert r.returncode == 0
    plan = json.loads(r.stdout)
    assert [p["stage"] for p in plan] == [6, 7, 8, 9, 10, 11, 12]
