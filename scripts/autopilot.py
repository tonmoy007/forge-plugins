#!/usr/bin/env python3
"""Autopilot planner — deterministic cross-stage execution plan (REQ-AP-001..003, v0.3.1).

No LLM. Reads `pipeline/state.md` + the canonical stage table and emits the ordered list
of stages to run, honoring targets (`--to N` / `--stages K` / `--until-gate`), the cycle
entry/exit + stage bounds, an optional `.forge/config.yaml` → `autopilot:` block, and
`--resume` (skip stages already completed in `.forge/autopilot-runs.jsonl`).

The `/forge:autopilot` skill walks this plan **in-session** — a Python script cannot drive
Claude's in-session Agent tool (ADR-006) — running each stage's agent, then `check-gate.py`,
then advancing on a passing gate and STOPPING on a blocker. `--mode {in-session,background}`
selects the substrate the skill uses (background dispatches via `_background_agent`). This
script is side-effect-free: it only computes and prints the plan.

Generalizes `force-advance` (one gated advance) and `build-batch` (within-stage batch) to
a cross-stage loop. Stdlib + PyYAML (fail-soft). Never raises.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_PLUGIN_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PLUGIN_DIR / "scripts"))
sys.path.insert(0, str(_PLUGIN_DIR / "hooks"))
import _stage_table  # noqa: E402
import _state_lib  # noqa: E402
import _error_log  # noqa: E402  (shared rotation for the run-log)
import _background_agent  # noqa: E402  (the sole `claude -p` wrapper — background mode)
import _verify  # noqa: E402  (shared verify/heal primitives — REQ-WF-002)

# Re-exported so autopilot's public API is unchanged after the T-192 extraction: the verdict
# schema and interpreter now live in `_verify` and are shared with the workflow engine.
VERIFY_SCHEMA = _verify.VERIFY_SCHEMA
verdict_failed = _verify.verdict_failed

VALID_MODES = ("in-session", "background")
_RUNLOG_NAME = "autopilot-runs.jsonl"
_SESSION_NAME = "autopilot-session.json"
_DONE_STATUSES = {"done", "passed", "advanced", "ok"}

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
@dataclass
class AutopilotConfig:
    max_stages: Optional[int] = None
    stop_before: Optional[int] = None
    checkpoint: str = "gate"  # every | gate | never
    allow_force: bool = False
    model: Optional[str] = None  # background-mode model override (else inherits default)
    max_budget_usd: Optional[float] = None  # per-dispatch hard $ ceiling (REQ-HARNESS-002)
    models: dict = field(default_factory=dict)  # per-stage model routing (REQ-HARNESS-003)
    session_max_dispatches: Optional[int] = None  # rotate reused session after N (REQ-HARNESS-004)
    max_heal_attempts: int = 1  # bounded self-heal per stage (REQ-AUTO-002; 0 = stop-on-gate)
    verify: bool = False  # opt-in independent self-verification after a passing gate (REQ-AUTO-003)
    # Context-pressure rotation (REQ-CTX-001..003, v0.3.6). Opt-in: the feature is OFF
    # unless context_window_size is set (Forge cannot auto-detect the model's window).
    context_window_size: Optional[int] = None  # estimated context window in tokens
    context_threshold_percent: float = 80.0  # rotate when input_tokens ≥ this % of the window


def _safe_yaml_load(text: str) -> Optional[dict]:
    try:
        import yaml  # noqa: F401
    except ImportError:
        return None
    try:
        data = yaml.safe_load(text)
    except Exception:  # noqa: BLE001
        return None
    return data if isinstance(data, dict) else None


def _coerce_int(value: object) -> Optional[int]:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def load_config(forge_dir) -> AutopilotConfig:
    """Read `<forge_dir>/config.yaml` → `autopilot:`; fail-soft to defaults. Never raises."""
    cfg = AutopilotConfig()
    path = Path(forge_dir) / "config.yaml"
    try:
        if not path.exists():
            return cfg
        data = _safe_yaml_load(path.read_text())
    except OSError:
        return cfg
    section = data.get("autopilot") if data else None
    if not isinstance(section, dict):
        return cfg
    cfg.max_stages = _coerce_int(section.get("max_stages"))
    cfg.stop_before = _coerce_int(section.get("stop_before"))
    checkpoint = section.get("checkpoint")
    if checkpoint in ("every", "gate", "never"):
        cfg.checkpoint = checkpoint
    cfg.allow_force = section.get("allow_force") is True
    model = section.get("model")
    if isinstance(model, str) and model.strip():
        cfg.model = model.strip()
    budget = section.get("max_budget_usd")
    if budget is not None:
        try:
            cfg.max_budget_usd = float(budget)
        except (TypeError, ValueError):
            pass
    models = section.get("models")
    if isinstance(models, dict):
        cfg.models = models
    smax = _coerce_int(section.get("session_max_dispatches"))
    if smax is not None:
        cfg.session_max_dispatches = smax
    heal = _coerce_int(section.get("max_heal_attempts"))
    if heal is not None:  # 0 is valid (stop-on-gate); only an absent/garbage value keeps the default
        cfg.max_heal_attempts = max(0, heal)
    cfg.verify = section.get("verify") is True
    window = _coerce_int(section.get("context_window_size"))
    if window is not None and window > 0:
        cfg.context_window_size = window
    pct = section.get("context_threshold_percent")
    if pct is not None:
        try:
            pct_f = float(pct)
        except (TypeError, ValueError):
            pct_f = None
        if pct_f is not None and 0 < pct_f <= 100:
            cfg.context_threshold_percent = pct_f
    return cfg


def should_heal(attempts_used: int, config: AutopilotConfig) -> bool:
    """True when autopilot may attempt another bounded self-heal for the current stage
    (REQ-AUTO-001/002). Capped by `max_heal_attempts` (default 1; 0 = v0.3.1 stop-on-gate).
    `attempts_used` is the number of heals already tried for this stage. Delegates to the
    shared `_verify.should_heal` primitive (REQ-WF-002). Never raises.
    """
    return _verify.should_heal(attempts_used, config.max_heal_attempts)


def should_rotate_session(dispatch_count: int, config: AutopilotConfig) -> bool:
    """True when the reused session should rotate to a fresh one to bound context growth
    on long runs (REQ-HARNESS-004). The CLI auto-compacts *within* a session; this caps
    how long one session is reused *across* dispatches. Unset → never rotate. Never raises.
    """
    cap = config.session_max_dispatches
    return isinstance(cap, int) and cap > 0 and dispatch_count >= cap


def should_rotate_for_context(last_input_tokens, config: AutopilotConfig) -> bool:
    """True when the reused session should rotate because the last dispatch's input-token
    count crossed the configured context-pressure threshold (REQ-CTX-003, v0.3.6). For a
    *resumed* `claude -p` session, the envelope's `usage.input_tokens` approximates current
    context size, so this is a real (if approximate) context-pressure signal — unlike the
    pure dispatch-count proxy in `should_rotate_session`. Opt-in: returns False unless
    `context_window_size` is set. Fail-soft on garbage input. Never raises.
    """
    window = config.context_window_size
    if not isinstance(window, int) or window <= 0:
        return False
    tokens = _coerce_int(last_input_tokens)
    if tokens is None or tokens < 0:
        return False
    pct = config.context_threshold_percent
    if not isinstance(pct, (int, float)) or pct <= 0:
        return False
    return tokens >= (pct / 100.0) * window


def model_for_stage(config: AutopilotConfig, stage: int, plugin_root=None) -> Optional[str]:
    """Resolve the model for a stage (REQ-HARNESS-003): per-stage `models` mapping first
    (numeric key or the stage's command word, e.g. `build` from `/forge:build`), then the
    single `model` override, else None (host default). Never raises.
    """
    models = config.models if isinstance(config.models, dict) else {}

    def _clean(v):
        return v.strip() if isinstance(v, str) and v.strip() else None

    for key in (stage, str(stage)):
        if key in models:
            m = _clean(models[key])
            if m:
                return m
    try:
        entry = _stage_table.stage(stage, plugin_root) or {}
        skill = entry.get("skill") or ""
        word = skill.split(":")[-1] if ":" in skill else ""
        if word and word in models:
            m = _clean(models[word])
            if m:
                return m
    except Exception:  # noqa: BLE001 — routing must never crash a dispatch
        pass
    return config.model


# --------------------------------------------------------------------------- #
# Planning
# --------------------------------------------------------------------------- #
def resolve_plan(
    current_stage: int,
    *,
    to: Optional[int] = None,
    stages_count: Optional[int] = None,
    until_gate: bool = False,
    cycle: str = "full",
    config: Optional[AutopilotConfig] = None,
    plugin_root: Optional[Path] = None,
) -> list[int]:
    """Return the ordered stage numbers to run. Empty when nothing is runnable.

    Start at the current stage (or 1 when not started / below the cycle entry); end at
    the target, clamped to the cycle exit, the max stage, `stop_before - 1`, and
    `start + max_stages - 1`. Never raises.
    """
    cfg = config or AutopilotConfig()
    try:
        max_s = _stage_table.max_stage(plugin_root)
        cycles = _stage_table.cycles(plugin_root)
    except Exception:  # noqa: BLE001 — table read must not crash the planner
        max_s, cycles = 12, {}
    cyc = cycles.get(cycle) or {}
    entry = cyc.get("entry", 1)
    exit_ = cyc.get("exit", max_s)

    if not isinstance(current_stage, int) or current_stage < 1:
        start = 1
    else:
        start = current_stage
    start = max(start, entry)

    if to is not None:
        end = to
    elif stages_count is not None:
        end = start + stages_count - 1
    else:  # default + until_gate both run to the cycle exit; the loop stops on a blocker
        end = exit_

    end = min(end, exit_, max_s)
    if cfg.stop_before is not None:
        end = min(end, cfg.stop_before - 1)
    if cfg.max_stages is not None:
        end = min(end, start + cfg.max_stages - 1)

    if end < start:
        return []
    return list(range(start, end + 1))


def _completed_stages(forge_dir: Path) -> set[int]:
    """Stage numbers marked done in the run-log (for --resume). Never raises."""
    done: set[int] = set()
    path = Path(forge_dir) / _RUNLOG_NAME
    try:
        text = path.read_text()
    except OSError:
        return done
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and str(row.get("status", "")).lower() in _DONE_STATUSES:
            n = _coerce_int(row.get("stage"))
            if n is not None:
                done.add(n)
    return done


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record_run(
    forge_dir, stage: int, status: str, *, mode: str = "in-session", note: str = ""
) -> bool:
    """Append a run-log row to `.forge/autopilot-runs.jsonl` (size-bounded, rotated).

    The in-session loop calls this after each stage so `--resume` can skip completed
    work. Never raises (delegates to `_error_log.append_jsonl`).
    """
    entry = {"ts": _now_iso(), "stage": stage, "status": status, "mode": mode}
    if note:
        entry["note"] = note
    return _error_log.append_jsonl(Path(forge_dir) / _RUNLOG_NAME, entry)


def record_assumption(forge_dir, stage: int, assumption: str, *, mode: str = "in-session") -> bool:
    """Record a reasonable default taken for an unanswered interactive prompt during an
    unattended run (REQ-AUTO-004) — an explicit assumption in the run-log, never a silent
    guess. Status `assumption` is NOT a done-status, so it does not mark the stage complete
    for `--resume`. Never raises.
    """
    return record_run(forge_dir, stage, "assumption", mode=mode, note=assumption)


# Answers file for unattended interactive stages (REQ-AUTO-004), tried in order.
_ANSWERS_NAMES = ("autopilot-answers.json", "autopilot-answers.yaml", "autopilot-answers.yml")


def read_answers(forge_dir) -> dict:
    """Load `.forge/autopilot-answers.{json,yaml,yml}` — pre-supplied answers for the
    CLARIFY/CONFIRM prompts of interactive stages in an unattended run (REQ-AUTO-004).
    Returns {} when absent/unreadable/malformed (the loop then records assumptions instead).
    Never raises.
    """
    forge = Path(forge_dir)
    for name in _ANSWERS_NAMES:
        path = forge / name
        try:
            if not path.exists():
                continue
            text = path.read_text()
        except OSError:
            continue
        if name.endswith(".json"):
            try:
                data = json.loads(text)
            except (ValueError, TypeError):
                continue
        else:
            data = _safe_yaml_load(text)
        if isinstance(data, dict):
            return data
    return {}


def answers_for_stage(answers: dict, stage: int) -> Optional[str]:
    """Return the supplied answer for a stage (numeric or string key), or None. Non-string
    values are JSON-encoded so the loop can hand them to the stage. Never raises.
    """
    if not isinstance(answers, dict):
        return None
    for key in (stage, str(stage)):
        if key in answers:
            v = answers[key]
            return v if isinstance(v, str) else json.dumps(v)
    return None


def read_session(forge_dir) -> dict:
    """Read `.forge/autopilot-session.json` ({} if absent/unreadable). Never raises."""
    path = Path(forge_dir) / _SESSION_NAME
    try:
        if not path.exists():
            return {}
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_session(forge_dir, data: dict) -> bool:
    forge = Path(forge_dir)
    try:
        forge.mkdir(parents=True, exist_ok=True)
        tmp = forge / (_SESSION_NAME + ".tmp")
        tmp.write_text(json.dumps(data))
        os.replace(tmp, forge / _SESSION_NAME)
        return True
    except OSError:
        return False


def start_session(forge_dir) -> dict:
    """Mark an autopilot run active. Idempotent: warns if already running (REQ-AP-007)."""
    cur = read_session(forge_dir)
    if cur.get("status") == "running":
        return {"status": "already_running", "started_at": cur.get("started_at")}
    now = _now_iso()
    _write_session(forge_dir, {"status": "running", "started_at": now,
                               "stop_requested": False, "updated_at": now})
    return {"status": "started", "started_at": now}


def request_stop(forge_dir) -> dict:
    """Set the stop flag the loop checks between stages (REQ-AP-007)."""
    data = dict(read_session(forge_dir))
    data["stop_requested"] = True
    data["status"] = "stopping"
    data["updated_at"] = _now_iso()
    _write_session(forge_dir, data)
    return {"status": "stop_requested"}


def stop_requested(forge_dir) -> bool:
    return bool(read_session(forge_dir).get("stop_requested"))


def finish_session(forge_dir) -> dict:
    """Mark the run idle and clear the stop flag (call at run end)."""
    started = read_session(forge_dir).get("started_at")
    _write_session(forge_dir, {"status": "idle", "stop_requested": False,
                               "started_at": started, "updated_at": _now_iso()})
    return {"status": "idle"}


# --------------------------------------------------------------------------- #
# Checkpoint (REQ-CTX-004..008, v0.3.6) — a durable, schema-versioned snapshot
# of "where the run is / what's next", written BEFORE a context boundary (a
# background session rotation, or a native in-session compaction via the
# PreCompact hook) so the run resumes cleanly. Stage-level idempotency stays in
# the run-log (`autopilot-runs.jsonl` + `--resume`); the checkpoint adds the
# next-action pointer. `.forge`-only, atomic, never raises.
# --------------------------------------------------------------------------- #
_CHECKPOINT_NAME = "autopilot-checkpoint.json"
_CHECKPOINT_SCHEMA_VERSION = 1


def read_checkpoint(forge_dir) -> dict:
    """Read `.forge/autopilot-checkpoint.json` ({} if absent/unreadable/malformed). Never raises."""
    path = Path(forge_dir) / _CHECKPOINT_NAME
    try:
        if not path.exists():
            return {}
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_checkpoint(forge_dir, fields: dict) -> bool:
    """Atomically write/refresh the checkpoint, stamping `schema_version` + `ts` and
    preserving `run_started_at` across updates (existing checkpoint → session start → now).
    `.forge`-only; mirrors `_write_session`'s temp-then-rename. Never raises.
    """
    forge = Path(forge_dir)
    fields = dict(fields) if isinstance(fields, dict) else {}
    existing = read_checkpoint(forge)
    run_started = (existing.get("run_started_at")
                   or read_session(forge).get("started_at")
                   or _now_iso())
    payload = {"schema_version": _CHECKPOINT_SCHEMA_VERSION, "run_started_at": run_started}
    payload.update(fields)
    payload["ts"] = _now_iso()
    try:
        forge.mkdir(parents=True, exist_ok=True)
        tmp = forge / (_CHECKPOINT_NAME + ".tmp")
        tmp.write_text(json.dumps(payload))
        os.replace(tmp, forge / _CHECKPOINT_NAME)
        return True
    except OSError:
        return False


def build_and_write_checkpoint(
    cwd,
    *,
    dispatch_count: int = 0,
    last_input_tokens: Optional[int] = None,
    last_session_id: Optional[str] = None,
    next_action: str = "",
) -> bool:
    """Derive the checkpoint fields from the deterministic planner (current stage +
    remaining stages, skipping completed work via `--resume`) and write it. Used by both
    the `checkpoint` CLI subcommand and the PreCompact hook. Never raises.
    """
    plan = plan_stages(cwd, resume=True)
    remaining = [p["stage"] for p in plan] if plan else []
    current = remaining[0] if remaining else None
    if not next_action:
        next_action = (f"resume at stage {current} via {plan[0]['skill']}"
                       if plan else "autopilot run complete — nothing remaining")
    return write_checkpoint(Path(cwd) / ".forge", {
        "current_stage": current,
        "remaining_stages": remaining,
        "dispatch_count": dispatch_count,
        "last_input_tokens": _coerce_int(last_input_tokens),
        "last_session_id": last_session_id,
        "next_action": next_action,
    })


def _background_available(forge_dir) -> tuple[bool, str]:
    """Is the background substrate usable? Honors the kill switch + capability cache."""
    if os.environ.get("FORGE_NO_BACKGROUND") == "1":
        return False, "kill switch (FORGE_NO_BACKGROUND=1)"
    caps = _background_agent.read_capabilities(Path(forge_dir))
    if not caps or not caps.get("forge_background_available"):
        return False, "background agents unavailable"
    return True, "available"


def _stage_prompt(stage: int, skill: str, label: str) -> str:
    return (
        f"You are Forge autopilot executing pipeline stage {stage} ({label}). Run the "
        f"work for {skill} in this project — produce the stage's canonical artifact — "
        f"then stop. Do NOT advance the stage pointer; the foreground loop checks the "
        f"gate and advances."
    )


def _heal_prompt(stage: int, skill: str, label: str, blockers: str = "") -> str:
    base = (
        f"You are Forge autopilot self-healing pipeline stage {stage} ({label}). The "
        f"stage gate FAILED with blocking issues. Run the work for {skill} to fix the "
        f"blockers and repair the stage's canonical artifact, then stop. Do NOT advance "
        f"the stage pointer; the foreground loop re-checks the gate."
    )
    if blockers:
        base += f"\n\nBlocking gate criteria to resolve:\n{blockers}"
    return base


def _verify_prompt(stage: int, skill: str, label: str) -> str:
    return (
        f"You are an INDEPENDENT Forge verifier for pipeline stage {stage} ({label}), "
        f"running in fresh context. The stage's mechanical gate has already passed. "
        f"Critically assess whether the stage's canonical artifact (produced by {skill}) "
        f"genuinely satisfies the stage's intent and the upstream requirements — beyond "
        f"the mechanical checks. Do NOT modify anything. Return a verdict of \"pass\" or "
        f"\"fail\" with concise reasons."
    )


def _dispatch_background(
    cwd,
    stage: int,
    prompt: str,
    *,
    feature: str,
    session_id: Optional[str],
    rotate: bool,
    model: Optional[str],
    max_budget_usd: Optional[float],
    claude_bin: Optional[str],
    output_schema: Optional[dict] = None,
) -> dict:
    """Shared cost/capability-gated `claude -p` dispatch for stage runs, self-heals, and
    verifiers.

    Returns a clean `unavailable` no-op when the kill switch is set or no background
    capability is present; an `error` dict if dispatch unexpectedly raises. Never raises.
    """
    forge = Path(cwd) / ".forge"
    ok, reason = _background_available(forge)
    if not ok:
        return {"status": "unavailable", "reason": reason, "stage": stage}
    kwargs = dict(
        forge_dir=forge,
        feature=feature,
        resume=(None if rotate else session_id),
        model=model,
        max_budget_usd=max_budget_usd,
        claude_bin=claude_bin,
        cwd=str(cwd),
    )
    if output_schema is not None:
        kwargs["output_schema"] = output_schema
    try:
        res = _background_agent.dispatch(prompt, **kwargs)
    except Exception as exc:  # noqa: BLE001 — dispatch shouldn't raise, but never crash
        return {"status": "error", "reason": str(exc), "stage": stage}
    return {
        "status": getattr(res, "status", "error"),
        "reason": getattr(res, "reason", ""),
        "session_id": getattr(res, "session_id", None) or session_id,
        "cost_usd": getattr(res, "cost_usd", None),
        "result": getattr(res, "result", None),
        "input_tokens": _dispatch_input_tokens(res),  # context-pressure signal (REQ-CTX-002)
        "stage": stage,
    }


def _dispatch_input_tokens(res) -> Optional[int]:
    """Pull `usage.input_tokens` from a dispatch result's raw envelope (REQ-CTX-002).
    For a resumed session this approximates current context size. None when absent. Never raises.
    """
    raw = getattr(res, "raw", None)
    if not isinstance(raw, dict):
        return None
    usage = raw.get("usage")
    if not isinstance(usage, dict):
        return None
    return _coerce_int(usage.get("input_tokens"))


def run_stage(
    cwd,
    stage: int,
    skill: str,
    label: str = "",
    *,
    mode: str = "in-session",
    session_id: Optional[str] = None,
    rotate: bool = False,
    model: Optional[str] = None,
    max_budget_usd: Optional[float] = None,
    claude_bin: Optional[str] = None,
) -> dict:
    """Execute one stage in the selected substrate (REQ-AP-006). Never raises.

    `in-session` is a no-op marker — the skill runs the stage in the user's session.
    `background` dispatches one cost/capability-gated `claude -p` run (session reused via
    `session_id`); a clean `unavailable` no-op when the kill switch is set or no
    background capability is present.
    """
    if mode != "background":
        return {"status": "in-session", "stage": stage}
    return _dispatch_background(
        cwd, stage, _stage_prompt(stage, skill, label),
        feature="autopilot-stage", session_id=session_id, rotate=rotate,
        model=model, max_budget_usd=max_budget_usd, claude_bin=claude_bin,
    )


def run_heal(
    cwd,
    stage: int,
    skill: str = "/forge:resolve",
    label: str = "",
    *,
    mode: str = "in-session",
    session_id: Optional[str] = None,
    rotate: bool = False,
    model: Optional[str] = None,
    max_budget_usd: Optional[float] = None,
    blockers: str = "",
    claude_bin: Optional[str] = None,
) -> dict:
    """Dispatch one bounded self-heal for a blocked stage (REQ-AUTO-001). Never raises.

    Routes through the Stage-11 resolver (`/forge:resolve`) to fix the gate blockers, then
    returns so the foreground loop can re-check the gate. `in-session` is a no-op marker
    (the skill runs the resolve in the user's session). `background` is the same
    cost/capability-gated substrate as `run_stage`, tagged `autopilot-heal` in the ledger.
    """
    if mode != "background":
        return {"status": "in-session", "stage": stage}
    return _dispatch_background(
        cwd, stage, _heal_prompt(stage, skill, label, blockers),
        feature="autopilot-heal", session_id=session_id, rotate=rotate,
        model=model, max_budget_usd=max_budget_usd, claude_bin=claude_bin,
    )


def run_verify(
    cwd,
    stage: int,
    skill: str,
    label: str = "",
    *,
    mode: str = "in-session",
    model: Optional[str] = None,
    max_budget_usd: Optional[float] = None,
    claude_bin: Optional[str] = None,
) -> dict:
    """Run an independent verifier over a stage whose gate just passed (REQ-AUTO-003).

    Always **fresh context** (never reuses the stage session) so the verdict is
    independent. `in-session` is a no-op marker — the skill spawns a verifier subagent in
    the user's session. `background` dispatches a schema-constrained verdict
    (`VERIFY_SCHEMA`) headlessly, tagged `autopilot-verify` in the ledger. The returned
    dict's `result` carries the verdict JSON for `verdict_failed`. Never raises.
    """
    if mode != "background":
        return {"status": "in-session", "stage": stage}
    return _dispatch_background(
        cwd, stage, _verify_prompt(stage, skill, label),
        feature="autopilot-verify", session_id=None, rotate=False,
        model=model, max_budget_usd=max_budget_usd, claude_bin=claude_bin,
        output_schema=VERIFY_SCHEMA,
    )


def plan_stages(
    cwd,
    *,
    to: Optional[int] = None,
    stages_count: Optional[int] = None,
    until_gate: bool = False,
    cycle: str = "full",
    resume: bool = False,
    plugin_root: Optional[Path] = None,
) -> list[dict]:
    """Read state + config and return [{stage, skill, label}] for the run. Never raises.

    Returns [] when there is no readable pipeline state (lesson 2026-05-10: check that
    state.md exists before `read_state`, which sys.exit()s when it is missing).
    """
    cwd = Path(cwd)
    if not (cwd / "pipeline" / "state.md").exists():
        return []
    try:
        state = _state_lib.read_state(str(cwd))
    except BaseException:  # noqa: BLE001 — read_state may sys.exit (SystemExit) on bad state
        return []
    # No default: a malformed/empty state.md yields {} (no current_stage) -> no plan.
    current = state.get("current_stage")
    if not isinstance(current, int):
        return []

    cfg = load_config(cwd / ".forge")
    nums = resolve_plan(
        current, to=to, stages_count=stages_count, until_gate=until_gate,
        cycle=cycle, config=cfg, plugin_root=plugin_root,
    )
    if resume:
        done = _completed_stages(cwd / ".forge")
        nums = [n for n in nums if n not in done]

    plan: list[dict] = []
    for n in nums:
        entry = _stage_table.stage(n, plugin_root) or {}
        plan.append({
            "stage": n,
            "skill": entry.get("skill", ""),
            "label": entry.get("label", ""),
        })
    return plan


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="autopilot.py",
        description="Deterministic autopilot stage planner (the /forge:autopilot skill "
                    "walks this plan in-session).",
    )
    parser.add_argument("command", nargs="?", default="plan",
                        choices=("plan", "record", "dispatch", "heal", "verify", "answers",
                                 "start", "stop", "status", "finish", "checkpoint"),
                        help="plan (default) | record a stage | dispatch (background) | "
                             "heal a blocked stage (background) | verify a passed stage "
                             "(background) | answers (echo unattended answers file) | "
                             "start/stop/status/finish the autopilot session")
    parser.add_argument("--cwd", default=os.getcwd(), help="project root (default: cwd)")
    parser.add_argument("--stage", type=int, default=None, metavar="N",
                        help="(record/dispatch) the target stage")
    parser.add_argument("--status", default="done", help="(record) stage outcome")
    parser.add_argument("--note", default="", help="(record) optional note")
    parser.add_argument("--skill", default="", help="(dispatch) the stage's /forge:* command")
    parser.add_argument("--label", default="", help="(dispatch) human stage label")
    parser.add_argument("--session", default=None, help="(dispatch) reuse this session id")
    parser.add_argument("--model", default=None, help="(dispatch) background model override")
    parser.add_argument("--dispatch-count", type=int, default=0,
                        help="(dispatch/heal) prior dispatches on this session — triggers rotation")
    parser.add_argument("--last-input-tokens", type=int, default=None, metavar="N",
                        help="(dispatch/heal) input_tokens reported by the prior dispatch on "
                             "this session — triggers context-pressure rotation (REQ-CTX-003)")
    parser.add_argument("--blockers", default="",
                        help="(heal) blocking gate criteria summary to thread into the resolve prompt")
    parser.add_argument("--to", type=int, default=None, metavar="N",
                        help="run through stage N (inclusive)")
    parser.add_argument("--stages", type=int, default=None, metavar="K",
                        help="run K stages from the current one")
    parser.add_argument("--until-gate", action="store_true",
                        help="run to the cycle end; the loop stops at the first blocking gate")
    parser.add_argument("--cycle", default="full",
                        help="cycle type (full|iteration|hotfix|tech-debt; default: full)")
    parser.add_argument("--mode", default="in-session", choices=VALID_MODES,
                        help="execution substrate the skill uses (default: in-session)")
    parser.add_argument("--resume", action="store_true",
                        help="skip stages already completed in .forge/autopilot-runs.jsonl")
    parser.add_argument("--unattended", action="store_true",
                        help="no per-stage checkpoints; interactive stages use the answers "
                             "file or record assumptions (the loop honors the full safety "
                             "envelope — budget, cost cap, max_heal, stop flag, kill switch)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the plan only (this script never mutates state regardless)")
    parser.add_argument("--json", action="store_true", help="emit the plan as JSON")
    args = parser.parse_args(argv)

    if args.command == "record":
        if args.stage is None:
            print("error: record requires --stage N", file=sys.stderr)
            return 2
        ok = record_run(Path(args.cwd) / ".forge", args.stage, args.status,
                        mode=args.mode, note=args.note)
        print(f"recorded stage {args.stage} status={args.status}" if ok
              else "warning: run-log write failed", file=sys.stderr)
        return 0

    if args.command == "dispatch":
        if args.stage is None:
            print("error: dispatch requires --stage N", file=sys.stderr)
            return 2
        cfg = load_config(Path(args.cwd) / ".forge")
        model = args.model or model_for_stage(cfg, args.stage)
        rotate = (should_rotate_session(args.dispatch_count, cfg)
                  or should_rotate_for_context(args.last_input_tokens, cfg))
        result = run_stage(args.cwd, args.stage, args.skill, args.label,
                           mode="background", session_id=args.session, rotate=rotate,
                           model=model, max_budget_usd=cfg.max_budget_usd)
        print(json.dumps(result))
        return 0

    if args.command == "heal":
        if args.stage is None:
            print("error: heal requires --stage N", file=sys.stderr)
            return 2
        cfg = load_config(Path(args.cwd) / ".forge")
        model = args.model or model_for_stage(cfg, args.stage)
        rotate = (should_rotate_session(args.dispatch_count, cfg)
                  or should_rotate_for_context(args.last_input_tokens, cfg))
        result = run_heal(args.cwd, args.stage, args.skill or "/forge:resolve", args.label,
                          mode="background", session_id=args.session, rotate=rotate,
                          model=model, max_budget_usd=cfg.max_budget_usd,
                          blockers=args.blockers)
        print(json.dumps(result))
        return 0

    if args.command == "verify":
        if args.stage is None:
            print("error: verify requires --stage N", file=sys.stderr)
            return 2
        cfg = load_config(Path(args.cwd) / ".forge")
        model = args.model or model_for_stage(cfg, args.stage)
        result = run_verify(args.cwd, args.stage, args.skill, args.label,
                            mode="background", model=model,
                            max_budget_usd=cfg.max_budget_usd)
        print(json.dumps(result))
        return 0

    if args.command == "answers":
        print(json.dumps(read_answers(Path(args.cwd) / ".forge")))
        return 0

    if args.command == "checkpoint":
        ok = build_and_write_checkpoint(
            args.cwd, dispatch_count=args.dispatch_count,
            last_input_tokens=args.last_input_tokens, last_session_id=args.session,
        )
        if not ok:
            print("warning: checkpoint write failed", file=sys.stderr)
        print(json.dumps(read_checkpoint(Path(args.cwd) / ".forge")))
        return 0  # never fail the loop on a checkpoint write

    if args.command in ("start", "stop", "status", "finish"):
        forge = Path(args.cwd) / ".forge"
        if args.command == "start":
            print(json.dumps(start_session(forge)))
        elif args.command == "stop":
            print(json.dumps(request_stop(forge)))
        elif args.command == "finish":
            print(json.dumps(finish_session(forge)))
        else:
            print(json.dumps(read_session(forge)))
        return 0

    plan = plan_stages(
        args.cwd, to=args.to, stages_count=args.stages, until_gate=args.until_gate,
        cycle=args.cycle, resume=args.resume,
    )

    if args.json:
        print(json.dumps(plan))
        return 0

    prefix = "(dry-run) " if args.dry_run else ""
    if not plan:
        print(f"{prefix}autopilot: nothing to run "
              "(no pipeline state, or already at the target).", file=sys.stderr)
        return 0
    stages_str = " -> ".join(str(p["stage"]) for p in plan)
    unattended = " unattended" if args.unattended else ""
    print(f"[Forge] {prefix}autopilot plan ({args.mode}{unattended}): stages {stages_str}",
          file=sys.stderr)
    for p in plan:
        # stdout: one machine-readable "N\t/forge:skill" per line (build-batch idiom).
        print(f"{p['stage']}\t{p['skill']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
