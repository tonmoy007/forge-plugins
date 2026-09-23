#!/usr/bin/env python3
"""Evaluate exit criteria for a pipeline stage, output JSON pass/fail report."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _state_lib as lib  # noqa: E402


def _state_readable(cwd: Path) -> bool:
    """REQ-SILENTSTATE-001: a gate cannot pass against unreadable state.

    Returns True when state.md is absent (a different, separately-reported
    condition) or readable; False when it exists but cannot be parsed.
    """
    state_path = cwd / "pipeline" / "state.md"
    if not state_path.exists():
        return True
    try:
        lib.read_state(str(cwd))
        return True
    except (Exception, SystemExit):  # noqa: BLE001 - unreadable state is the signal
        return False


# Project-level override: a project may ship its own criteria for any stage in
# this file (same YAML-block format as references/gate-criteria.md). A stage it
# defines replaces the plugin's criteria for that stage wholesale; stages it
# does not define fall back to the plugin.
PROJECT_GATE_FILE = Path("pipeline") / "gate-criteria.md"


def _find_stage_block(gate_file: Path, stage: int) -> list[dict] | None:
    text = gate_file.read_text()
    blocks = re.findall(r"```yaml\n(.*?)```", text, re.DOTALL)

    for block in blocks:
        try:
            data = yaml.safe_load(block)
            if isinstance(data, dict) and data.get("stage") == stage:
                return data.get("criteria", []) or []
        except yaml.YAMLError:
            continue
    return None


def _resolve_stage_criteria(plugin_dir: Path, stage: int, cwd: Path) -> tuple[list[dict], str]:
    """Return (criteria, source) where source is "project" or "plugin"."""
    project_file = cwd / PROJECT_GATE_FILE
    if project_file.exists():
        criteria = _find_stage_block(project_file, stage)
        if criteria is not None:
            return criteria, "project"
    return _load_stage_criteria(plugin_dir, stage), "plugin"


def _load_stage_criteria(plugin_dir: Path, stage: int) -> list[dict]:
    gate_file = plugin_dir / "references" / "gate-criteria.md"
    if not gate_file.exists():
        print(f"error: gate-criteria.md not found at {gate_file}", file=sys.stderr)
        sys.exit(1)

    criteria = _find_stage_block(gate_file, stage)
    if criteria is not None:
        return criteria

    print(f"error: no gate criteria found for stage {stage}", file=sys.stderr)
    sys.exit(1)


def _resolve_script(script_rel: str, cwd: Path, plugin_dir: Path, source: str) -> Path:
    """Project criteria may name a project-local script; plugin scripts are the fallback."""
    if source == "project":
        local = cwd / script_rel
        if local.exists():
            return local
    return plugin_dir / script_rel


def _check_file_exists(args: dict, cwd: Path) -> tuple[bool, str]:
    p = cwd / args["path"]
    if not p.exists():
        return False, f"{args['path']}: file does not exist"
    if p.stat().st_size == 0:
        return False, f"{args['path']}: file is empty"
    return True, "OK"


def _check_file_contains(args: dict, cwd: Path) -> tuple[bool, str]:
    p = cwd / args["path"]
    if not p.exists():
        return False, f"{args['path']}: file does not exist"
    pattern = args["pattern"]
    min_matches = int(args.get("min_matches", 1))
    try:
        content = p.read_text()
        matches = re.findall(pattern, content, re.MULTILINE)
        if len(matches) >= min_matches:
            return True, f"{len(matches)} match(es) found"
        return False, f"{len(matches)} match(es) for {pattern!r} (need {min_matches})"
    except re.error as exc:
        return False, f"invalid regex {pattern!r}: {exc}"


def _check_script_returns_zero(args: dict, cwd: Path, script: Path) -> tuple[bool, str]:
    script_rel = args["script"]
    if not script.exists():
        return False, f"check script not yet implemented: {script_rel}"
    argv = [sys.executable, str(script)] + [str(a) for a in args.get("argv", [])]
    result = subprocess.run(argv, capture_output=True, text=True, cwd=str(cwd))
    if result.returncode == 0:
        return True, "OK"
    detail = (result.stderr.strip() or result.stdout.strip() or "exited non-zero")[:300]
    return False, detail


def _check_all_tests_pass(args: dict, cwd: Path) -> tuple[bool, str]:
    cmd = args.get("test_command", "pytest")
    argv = shlex.split(cmd)
    if argv[0] == "pytest":
        argv = [sys.executable, "-m", "pytest"] + argv[1:]
    result = subprocess.run(argv, capture_output=True, text=True, cwd=str(cwd))
    if result.returncode == 0:
        return True, "OK"
    lines = result.stdout.splitlines() + result.stderr.splitlines()
    last = next((l for l in reversed(lines) if l.strip()), "tests failed")
    return False, last[:300]


def _evaluate(criterion: dict, cwd: Path, plugin_dir: Path, source: str = "plugin") -> dict:
    cid = criterion["id"]
    check = criterion["check"]
    args = criterion.get("args", {})
    severity = criterion.get("severity", "blocker")
    inconclusive = False

    try:
        if check == "file_exists":
            passed, msg = _check_file_exists(args, cwd)
        elif check == "file_contains":
            passed, msg = _check_file_contains(args, cwd)
        elif check == "script_returns_zero":
            # REQ-GATESTUB-001: a missing check script is a config bug, not a soft
            # pass. Report inconclusive and promote severity to blocker regardless
            # of the declared severity — a stub gate must not read as "warnings only".
            script_rel = args.get("script", "")
            script = _resolve_script(script_rel, cwd, plugin_dir, source)
            if not script.exists():
                passed, msg = False, f"check script not implemented: {script_rel}"
                inconclusive = True
                severity = "blocker"
            else:
                passed, msg = _check_script_returns_zero(args, cwd, script)
        elif check == "all_tests_pass":
            passed, msg = _check_all_tests_pass(args, cwd)
        else:
            passed, msg = False, f"unknown check type: {check!r}"
    except Exception as exc:  # noqa: BLE001
        passed, msg = False, f"internal error: {exc}"

    return {
        "id": cid,
        "inconclusive": inconclusive,
        "description": criterion.get("description", ""),
        "check": check,
        "severity": severity,
        "passed": passed,
        "message": msg,
        "source": source,
    }


def evaluate_stage(stage: int, cwd: Path, plugin_dir: Path) -> dict:
    criteria, source = _resolve_stage_criteria(plugin_dir, stage, cwd)
    details = [_evaluate(c, cwd, plugin_dir, source) for c in criteria]

    # REQ-SILENTSTATE-001: if state.md exists but is unreadable, the whole gate is
    # inconclusive — it must not read as a clean pass against missing data.
    state_readable = _state_readable(cwd)
    if not state_readable:
        details.insert(0, {
            "id": "STATE-READ",
            "description": "pipeline/state.md is readable",
            "check": "state_readable",
            "severity": "blocker",
            "passed": False,
            "message": "pipeline/state.md exists but could not be read — gate result is inconclusive",
        })

    # REQ-GATESTUB-001: criteria whose check script is missing are unimplemented.
    unimplemented = sum(1 for d in details if d.get("inconclusive"))
    passed = sum(1 for d in details if d["passed"])
    failed = len(details) - passed
    return {
        "stage": stage,
        "criteria_source": source,
        "total": len(details),
        "passed": passed,
        "failed": failed,
        "unimplemented": unimplemented,
        "inconclusive": (not state_readable) or unimplemented > 0,
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="check-gate.py",
        description="Evaluate pipeline stage exit criteria",
    )
    parser.add_argument("--stage", required=True, type=int, metavar="N")
    parser.add_argument("--cwd", default=os.getcwd(), metavar="PATH")
    parser.add_argument(
        "--plugin-dir",
        default=str(Path(__file__).parent.parent),
        metavar="PATH",
        help="plugin root (default: parent of scripts/)",
    )
    args = parser.parse_args()

    result = evaluate_stage(
        stage=args.stage,
        cwd=Path(args.cwd),
        plugin_dir=Path(args.plugin_dir),
    )
    print(json.dumps(result, indent=2))
    # REQ-SILENTSTATE-001: a gate run against unreadable state exits non-zero so
    # callers can't treat an inconclusive result as a pass.
    if result.get("inconclusive"):
        sys.exit(2)


if __name__ == "__main__":
    main()
