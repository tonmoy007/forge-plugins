#!/usr/bin/env python3
"""Forge doctor — diagnostic report on environment, plugin, and project state.

Runs ~13 deterministic checks and prints a status report. Each failing check
includes a specific fix command. Exits 0 if all checks pass (warnings allowed),
1 if any fail.

Usage:
    python scripts/doctor.py
    python scripts/doctor.py --json
    python scripts/doctor.py --quiet   # only failures and warnings
    python scripts/doctor.py --cwd /path/to/project

Design constraints:
- Stdlib-only where possible; PyYAML import is optional and self-reported
- POSIX-only (matches other Forge scripts)
- Total runtime budget < 5s; each check < 1s
- Zero false alarms: every ✗ reflects a real, actionable problem
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

MIN_PYTHON = (3, 11)
MIN_CLAUDE_CODE = (2, 1, 0)
EXPECTED_HOOKS = [
    "session-start.py",
    "prompt-submit.py",
    "pre-tool-write.py",
    "post-tool-use.py",
    "stop-reflect.py",
    "subagent-stop.py",
    "session-end.py",
]
EXPECTED_STAGE_AGENTS = 12
GATE_CRITERIA_PATH = "references/gate-criteria.md"


@dataclass
class CheckResult:
    name: str
    category: str       # "environment" | "plugin" | "project" | "global"
    status: str         # "pass" | "fail" | "warn" | "info"
    detail: str
    fix: Optional[str] = None


# ---------- helpers ----------

def parse_version(s: str) -> Optional[tuple[int, ...]]:
    """Extract (major, minor, patch...) from any string containing 'N.N[.N...]'."""
    m = re.search(r"(\d+(?:\.\d+)+)", s)
    if not m:
        return None
    return tuple(int(p) for p in m.group(1).split("."))


def cmp_version(actual: tuple[int, ...], minimum: tuple[int, ...]) -> bool:
    pad = max(len(actual), len(minimum))
    a = actual + (0,) * (pad - len(actual))
    b = minimum + (0,) * (pad - len(minimum))
    return a >= b


# ---------- environment checks ----------

def check_python_version() -> CheckResult:
    v = sys.version_info[:3]
    ok = v >= MIN_PYTHON
    return CheckResult(
        name="python_version",
        category="environment",
        status="pass" if ok else "fail",
        detail=f"Python {'.'.join(map(str, v))}",
        fix=None if ok else f"Install Python ≥ {'.'.join(map(str, MIN_PYTHON))}",
    )


def check_pyyaml() -> CheckResult:
    try:
        import yaml  # noqa: F401
        v = getattr(yaml, "__version__", "unknown")
        return CheckResult("pyyaml", "environment", "pass", f"PyYAML {v}")
    except ImportError:
        return CheckResult(
            "pyyaml", "environment", "fail",
            "PyYAML not installed",
            fix="pip install pyyaml",
        )


def check_claude_code() -> CheckResult:
    claude = shutil.which("claude")
    if not claude:
        return CheckResult(
            "claude_code", "environment", "fail",
            "`claude` binary not found in PATH",
            fix="Install Claude Code: https://docs.claude.com/claude-code",
        )
    try:
        out = subprocess.run(
            ["claude", "--version"],
            capture_output=True, text=True, timeout=3,
        )
        v_str = (out.stdout or out.stderr or "").strip()
        v = parse_version(v_str)
        if v is None:
            return CheckResult(
                "claude_code", "environment", "warn",
                f"Claude Code found but version not parseable: {v_str!r}",
            )
        ok = cmp_version(v, MIN_CLAUDE_CODE)
        min_str = ".".join(map(str, MIN_CLAUDE_CODE))
        return CheckResult(
            "claude_code", "environment",
            "pass" if ok else "fail",
            f"Claude Code {'.'.join(map(str, v))} (≥ {min_str} required)",
            fix=None if ok else "Upgrade Claude Code via your installer",
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return CheckResult(
            "claude_code", "environment", "warn",
            f"Could not run `claude --version`: {e}",
        )


# ---------- plugin checks ----------

def check_plugin_manifest(forge_root: Path) -> CheckResult:
    path = forge_root / ".claude-plugin" / "plugin.json"
    if not path.exists():
        return CheckResult(
            "plugin_manifest", "plugin", "fail",
            f"{path} not found",
            fix="Re-install Forge: /plugin install forge@forge-plugins",
        )
    try:
        data = json.loads(path.read_text())
        name = data.get("name", "<unnamed>")
        version = data.get("version", "<unversioned>")
        return CheckResult(
            "plugin_manifest", "plugin", "pass",
            f"plugin.json valid (name={name}, version={version})",
        )
    except json.JSONDecodeError as e:
        return CheckResult(
            "plugin_manifest", "plugin", "fail",
            f"plugin.json malformed: {e}",
            fix="Re-install Forge: /plugin install forge@forge-plugins",
        )


def check_hooks(forge_root: Path) -> list[CheckResult]:
    hooks_dir = forge_root / "hooks"
    if not hooks_dir.exists():
        return [CheckResult(
            "hooks", "plugin", "fail",
            f"{hooks_dir} not found",
            fix="Re-install Forge: /plugin install forge@forge-plugins",
        )]
    missing = [h for h in EXPECTED_HOOKS if not (hooks_dir / h).exists()]
    if missing:
        return [CheckResult(
            "hooks", "plugin", "fail",
            f"Missing hooks: {', '.join(missing)}",
            fix="Re-install Forge: /plugin install forge@forge-plugins",
        )]
    return [CheckResult(
        "hooks", "plugin", "pass",
        f"All {len(EXPECTED_HOOKS)} hooks present",
    )]


def check_agents(forge_root: Path) -> CheckResult:
    agents_dir = forge_root / "agents"
    if not agents_dir.exists():
        return CheckResult(
            "agents", "plugin", "fail",
            f"{agents_dir} not found",
            fix="Re-install Forge: /plugin install forge@forge-plugins",
        )
    md_files = list(agents_dir.glob("*.md"))
    ok = len(md_files) >= EXPECTED_STAGE_AGENTS
    return CheckResult(
        "agents", "plugin",
        "pass" if ok else "warn",
        f"{len(md_files)} agent definitions (≥ {EXPECTED_STAGE_AGENTS} expected)",
    )


def check_gate_criteria(forge_root: Path) -> CheckResult:
    path = forge_root / GATE_CRITERIA_PATH
    if not path.exists():
        return CheckResult(
            "gate_criteria", "plugin", "fail",
            f"{path} not found",
            fix="Re-install Forge",
        )
    try:
        import yaml
    except ImportError:
        return CheckResult(
            "gate_criteria", "plugin", "warn",
            "Gate criteria file present; PyYAML missing for full parse check",
        )
    try:
        text = path.read_text()
        blocks = re.findall(r"```yaml\n(.*?)\n```", text, re.DOTALL)
        count = 0
        for b in blocks:
            doc = yaml.safe_load(b)
            if isinstance(doc, dict) and "criteria" in doc:
                count += len(doc["criteria"])
        return CheckResult(
            "gate_criteria", "plugin", "pass",
            f"Gate criteria parsed: {count} criteria across {len(blocks)} stages",
        )
    except Exception as e:
        return CheckResult(
            "gate_criteria", "plugin", "fail",
            f"Could not parse gate criteria: {e}",
            fix="Re-install Forge",
        )


# ---------- project checks ----------

def check_pipeline_dir(cwd: Path) -> CheckResult:
    pipeline = cwd / "pipeline"
    if not pipeline.exists():
        return CheckResult(
            "pipeline_dir", "project", "info",
            "No `pipeline/` directory — Forge not initialized in this project",
            fix="Run `/forge:init` to initialize",
        )
    if not os.access(pipeline, os.W_OK):
        return CheckResult(
            "pipeline_dir", "project", "fail",
            f"{pipeline} not writable",
            fix=f"chmod u+w {pipeline}",
        )
    return CheckResult(
        "pipeline_dir", "project", "pass",
        f"{pipeline} writable",
    )


def check_state(cwd: Path) -> Optional[CheckResult]:
    state = cwd / "pipeline" / "state.md"
    if not state.exists():
        return None
    try:
        text = state.read_text()
        m = re.search(r"stage:\s*(\d+)", text, re.IGNORECASE)
        stage = m.group(1) if m else "unknown"
        return CheckResult(
            "state", "project", "pass",
            f"Currently at Stage {stage}",
        )
    except OSError as e:
        return CheckResult(
            "state", "project", "fail",
            f"Could not read state.md: {e}",
        )


def check_gitignore(cwd: Path) -> Optional[CheckResult]:
    if not (cwd / "pipeline").exists() and not (cwd / ".forge").exists():
        return None
    gi = cwd / ".gitignore"
    if not gi.exists():
        return CheckResult(
            "gitignore", "project", "warn",
            "No .gitignore found",
            fix="echo '.forge/' >> .gitignore",
        )
    # Strip comments and whitespace, look for .forge/ pattern
    lines = [
        ln.strip()
        for ln in gi.read_text().splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    dot_forge_ignored = any(ln in (".forge/", ".forge", "/.forge") for ln in lines)
    if not dot_forge_ignored:
        return CheckResult(
            "gitignore", "project", "warn",
            ".forge/ not in .gitignore (runtime state shouldn't be committed)",
            fix="echo '.forge/' >> .gitignore",
        )
    return CheckResult(
        "gitignore", "project", "pass",
        ".forge/ in .gitignore",
    )


# ---------- global checks ----------

def check_global_forge() -> CheckResult:
    home_forge = Path.home() / ".forge"
    if not home_forge.exists():
        return CheckResult(
            "global_forge", "global", "info",
            f"{home_forge} not yet created (will be on first lesson promotion)",
        )
    if not os.access(home_forge, os.W_OK):
        return CheckResult(
            "global_forge", "global", "fail",
            f"{home_forge} not writable",
            fix=f"chmod u+w {home_forge}",
        )
    return CheckResult(
        "global_forge", "global", "pass",
        f"{home_forge} writable",
    )


def check_disk_space() -> CheckResult:
    home = Path.home()
    try:
        usage = shutil.disk_usage(home)
        free_gb = usage.free / (1024 ** 3)
        ok = free_gb > 0.5
        return CheckResult(
            "disk_space", "global",
            "pass" if ok else "warn",
            f"{free_gb:.1f} GB free in {home}",
            fix=None if ok else "Free up disk space; .forge/ may not function with <500 MB free",
        )
    except OSError as e:
        return CheckResult(
            "disk_space", "global", "warn",
            f"Could not check disk: {e}",
        )


def check_hook_errors(cwd: Path) -> CheckResult:
    log = cwd / ".forge" / "hook-errors.log"
    if not log.exists():
        return CheckResult(
            "hook_errors", "global", "pass",
            "No hook errors recorded",
        )
    try:
        lines = log.read_text().splitlines()
        recent = lines[-5:]
        if not recent:
            return CheckResult(
                "hook_errors", "global", "pass",
                "Hook error log empty",
            )
        return CheckResult(
            "hook_errors", "global", "warn",
            "Last hook errors:\n  " + "\n  ".join(recent),
            fix=f"Investigate {log}",
        )
    except OSError as e:
        return CheckResult(
            "hook_errors", "global", "warn",
            f"Could not read hook error log: {e}",
        )


# ---------- driver ----------

ICONS = {"pass": "✓", "fail": "✗", "warn": "⚠", "info": "·"}


def find_forge_root() -> Path:
    """Locate the installed Forge plugin root.

    Honors FORGE_ROOT, then CLAUDE_PLUGIN_ROOT, then the script's parent's parent.
    """
    for var in ("FORGE_ROOT", "CLAUDE_PLUGIN_ROOT"):
        v = os.environ.get(var)
        if v and Path(v).exists():
            return Path(v)
    # Script is at scripts/doctor.py; root is its parent's parent
    return Path(__file__).resolve().parent.parent


def run_checks(forge_root: Path, cwd: Path) -> list[CheckResult]:
    results: list[CheckResult] = []
    results.append(check_python_version())
    results.append(check_pyyaml())
    results.append(check_claude_code())
    results.append(check_plugin_manifest(forge_root))
    results.extend(check_hooks(forge_root))
    results.append(check_agents(forge_root))
    results.append(check_gate_criteria(forge_root))
    results.append(check_pipeline_dir(cwd))
    state = check_state(cwd)
    if state:
        results.append(state)
    gi = check_gitignore(cwd)
    if gi:
        results.append(gi)
    results.append(check_global_forge())
    results.append(check_disk_space())
    results.append(check_hook_errors(cwd))
    return results


def format_text(results: list[CheckResult], quiet: bool = False) -> str:
    lines: list[str] = ["Forge Doctor — diagnostic report", "=" * 33, ""]
    by_cat: dict[str, list[CheckResult]] = {}
    for r in results:
        by_cat.setdefault(r.category, []).append(r)
    for cat in ("environment", "plugin", "project", "global"):
        rs = by_cat.get(cat, [])
        if not rs:
            continue
        shown = rs if not quiet else [r for r in rs if r.status in ("fail", "warn")]
        if not shown:
            continue
        lines.append(cat.capitalize() + ":")
        for r in shown:
            icon = ICONS.get(r.status, "?")
            lines.append(f"  {icon} {r.detail}")
            if r.fix:
                lines.append(f"    Fix: {r.fix}")
        lines.append("")
    lines.append(summarize(results))
    return "\n".join(lines)


def summarize(results: list[CheckResult]) -> str:
    fails = sum(1 for r in results if r.status == "fail")
    warns = sum(1 for r in results if r.status == "warn")
    if fails == 0 and warns == 0:
        return "Result: all checks passed."
    parts = []
    if fails:
        parts.append(f"{fails} failure{'s' if fails != 1 else ''}")
    if warns:
        parts.append(f"{warns} warning{'s' if warns != 1 else ''}")
    return f"Result: {' • '.join(parts)}."


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Forge environment, plugin, and project diagnostics.",
    )
    parser.add_argument("--json", action="store_true",
                        help="Emit machine-readable JSON report")
    parser.add_argument("--quiet", action="store_true",
                        help="Only show failures and warnings")
    parser.add_argument("--cwd", default=os.getcwd(),
                        help="Project directory for project checks (default: cwd)")
    args = parser.parse_args(argv)

    forge_root = find_forge_root()
    cwd = Path(args.cwd).resolve()
    results = run_checks(forge_root, cwd)

    if args.json:
        print(json.dumps([asdict(r) for r in results], indent=2))
    else:
        print(format_text(results, quiet=args.quiet))

    fails = sum(1 for r in results if r.status == "fail")
    return 1 if fails > 0 else 0


if __name__ == "__main__":
    sys.exit(main())