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


def _load_stage_criteria(plugin_dir: Path, stage: int) -> list[dict]:
    gate_file = plugin_dir / "references" / "gate-criteria.md"
    if not gate_file.exists():
        print(f"error: gate-criteria.md not found at {gate_file}", file=sys.stderr)
        sys.exit(1)

    text = gate_file.read_text()
    blocks = re.findall(r"```yaml\n(.*?)```", text, re.DOTALL)

    for block in blocks:
        try:
            data = yaml.safe_load(block)
            if isinstance(data, dict) and data.get("stage") == stage:
                return data.get("criteria", [])
        except yaml.YAMLError:
            continue

    print(f"error: no gate criteria found for stage {stage}", file=sys.stderr)
    sys.exit(1)


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


def _check_script_returns_zero(
    args: dict, cwd: Path, plugin_dir: Path
) -> tuple[bool, str]:
    script_rel = args["script"]
    script = plugin_dir / script_rel
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


def _evaluate(criterion: dict, cwd: Path, plugin_dir: Path) -> dict:
    cid = criterion["id"]
    check = criterion["check"]
    args = criterion.get("args", {})
    severity = criterion.get("severity", "blocker")

    try:
        if check == "file_exists":
            passed, msg = _check_file_exists(args, cwd)
        elif check == "file_contains":
            passed, msg = _check_file_contains(args, cwd)
        elif check == "script_returns_zero":
            passed, msg = _check_script_returns_zero(args, cwd, plugin_dir)
        elif check == "all_tests_pass":
            passed, msg = _check_all_tests_pass(args, cwd)
        else:
            passed, msg = False, f"unknown check type: {check!r}"
    except Exception as exc:  # noqa: BLE001
        passed, msg = False, f"internal error: {exc}"

    return {
        "id": cid,
        "description": criterion.get("description", ""),
        "check": check,
        "severity": severity,
        "passed": passed,
        "message": msg,
    }


def evaluate_stage(stage: int, cwd: Path, plugin_dir: Path) -> dict:
    criteria = _load_stage_criteria(plugin_dir, stage)
    details = [_evaluate(c, cwd, plugin_dir) for c in criteria]
    passed = sum(1 for d in details if d["passed"])
    failed = len(details) - passed
    return {
        "stage": stage,
        "total": len(details),
        "passed": passed,
        "failed": failed,
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


if __name__ == "__main__":
    main()
