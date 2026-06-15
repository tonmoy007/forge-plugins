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
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_PLUGIN_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PLUGIN_DIR / "scripts"))
sys.path.insert(0, str(_PLUGIN_DIR / "hooks"))
import _stage_table  # noqa: E402
import _state_lib  # noqa: E402
import _error_log  # noqa: E402  (shared rotation for the run-log)

VALID_MODES = ("in-session", "background")
_RUNLOG_NAME = "autopilot-runs.jsonl"
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
    return cfg


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
    parser.add_argument("command", nargs="?", default="plan", choices=("plan", "record"),
                        help="plan the run (default) or record a completed stage")
    parser.add_argument("--cwd", default=os.getcwd(), help="project root (default: cwd)")
    parser.add_argument("--stage", type=int, default=None, metavar="N",
                        help="(record) the stage just completed")
    parser.add_argument("--status", default="done", help="(record) stage outcome")
    parser.add_argument("--note", default="", help="(record) optional note")
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
    print(f"[Forge] {prefix}autopilot plan ({args.mode}): stages {stages_str}", file=sys.stderr)
    for p in plan:
        # stdout: one machine-readable "N\t/forge:skill" per line (build-batch idiom).
        print(f"{p['stage']}\t{p['skill']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
