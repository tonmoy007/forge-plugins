#!/usr/bin/env python3
"""Tool preflight — declarative registry detection + cache (T-227, REQ-TR-001/002).

Pure detection (shutil.which + optional version probe) for each tool declared in
references/tool-registry.md, cached to .forge/tool-status.json with a 24h TTL and
detached refresh — mirrors hooks/_background_agent.py's capability-probe pattern
(T-138: shutil.which + Capability dataclass + cache file + never raises). This
module never installs anything — install_command() only ever returns a string.

required_when is resolved against project state: `docker_artifacts_present` walks
the tree for Docker artifacts; `release_stage` reads pipeline/state.md's
current_stage. Never raises: a missing binary is "not present"; an unreadable
registry or cache degrades to an empty/needs-refresh result, never crashes the
caller.

CLI:
    tool_preflight.py check --cwd .                    -> JSON {tool: {...}}
    tool_preflight.py install <tool> --cwd .            -> the OS install command
                                                             (string only, never runs it)
    tool_preflight.py refresh --forge-dir DIR --cwd .   -> probe + write cache
                                                             (for the detached refresh)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:  # fail-soft — PyYAML is declared but must degrade cleanly if absent
    yaml = None

_PLUGIN_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_REGISTRY_REL = "references/tool-registry.md"
_STATUS_NAME = "tool-status.json"
_TTL_SECONDS = 86400  # re-probe tools at most once/day, same TTL as the capability probe

_DOCKER_ARTIFACT_NAMES = frozenset({
    "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml",
})
_IGNORE_DIRS = frozenset({
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".forge", "pipeline",
    "build", "dist",
})
_OS_KEYS = {"Darwin": "darwin", "Linux": "linux", "Windows": "win32"}


@dataclass
class ToolEntry:
    name: str
    which: str
    version_probe: Optional[list] = None
    workflows: list = field(default_factory=list)
    stages: list = field(default_factory=list)
    required_when: str = "always"
    install: dict = field(default_factory=dict)


@dataclass
class ToolStatus:
    present: bool
    version: Optional[str]
    required: bool
    reason: str
    install_cmd: Optional[str]


# --------------------------------------------------------------------------- #
# Registry parsing — malformed/missing degrades to [], never raises
# --------------------------------------------------------------------------- #


def load_registry(path: Optional[Path] = None) -> list:
    registry_path = path or (_PLUGIN_DIR / _DEFAULT_REGISTRY_REL)
    if yaml is None or not registry_path.exists():
        return []
    try:
        text = registry_path.read_text()
    except OSError:
        return []
    m = re.search(r"```yaml\n(.*?)\n```", text, re.DOTALL)
    if not m:
        return []
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return []
    if not isinstance(data, dict):
        return []
    entries = []
    for raw in data.get("tools", []) or []:
        if not isinstance(raw, dict) or "name" not in raw or "which" not in raw:
            continue  # malformed entry — skipped, not fatal
        entries.append(ToolEntry(
            name=raw["name"],
            which=raw["which"],
            version_probe=raw.get("version_probe"),
            workflows=raw.get("workflows") or [],
            stages=raw.get("stages") or [],
            required_when=raw.get("required_when", "always"),
            install=raw.get("install") or {},
        ))
    return entries


# --------------------------------------------------------------------------- #
# required_when resolution against project state
# --------------------------------------------------------------------------- #


def _has_docker_artifacts(cwd: Path) -> bool:
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]
        if any(f.startswith("Dockerfile") or f in _DOCKER_ARTIFACT_NAMES for f in files):
            return True
    return False


def _current_stage(cwd: Path) -> Optional[int]:
    try:
        sys.path.insert(0, str(_PLUGIN_DIR / "scripts"))
        import _state_lib as lib  # noqa: PLC0415
        state = lib.read_state(str(cwd))
    except SystemExit:  # _state_lib.read_state exits 1 when pipeline/state.md is missing
        return None
    except Exception:  # noqa: BLE001 — never raises (bad value, unreadable file, etc.)
        return None
    stage = state.get("current_stage") if isinstance(state, dict) else None
    try:
        return int(stage) if stage is not None else None
    except (TypeError, ValueError):
        return None


def resolve_required(entry: ToolEntry, cwd: Path) -> tuple:
    if entry.required_when == "always":
        return True, "always required"
    if entry.required_when == "docker_artifacts_present":
        present = _has_docker_artifacts(cwd)
        return present, ("Docker artifacts present" if present else "no Docker artifacts")
    if entry.required_when == "release_stage":
        stage = _current_stage(cwd)
        at_release = stage == 12
        return at_release, (f"current stage is {stage}" if at_release else "not at the release stage")
    return False, f"unknown required_when: {entry.required_when!r}"


# --------------------------------------------------------------------------- #
# Detection — shutil.which + optional version_probe; never raises
# --------------------------------------------------------------------------- #


def _install_cmd_for_entry(entry: ToolEntry) -> Optional[str]:
    os_key = _OS_KEYS.get(platform.system())
    return entry.install.get(os_key) if os_key else None


def detect_tool(entry: ToolEntry, cwd: Path) -> ToolStatus:
    required, reason = resolve_required(entry, cwd)
    path = shutil.which(entry.which)
    present = path is not None
    version = None
    if present and entry.version_probe:
        try:
            result = subprocess.run(entry.version_probe, capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            present = False
        else:
            present = result.returncode == 0
            if present:
                first_line = (result.stdout or result.stderr).strip().splitlines()
                version = first_line[0] if first_line else None
    install_cmd = None if present else _install_cmd_for_entry(entry)
    return ToolStatus(present=present, version=version, required=required, reason=reason, install_cmd=install_cmd)


def check_all(cwd: Path, *, registry_path: Optional[Path] = None) -> dict:
    entries = load_registry(registry_path)
    return {e.name: detect_tool(e, cwd) for e in entries}


# --------------------------------------------------------------------------- #
# TTL cache — mirrors hooks/_background_agent.py's write_capabilities/
# read_capabilities pattern
# --------------------------------------------------------------------------- #


def write_status_cache(forge_dir: Path, cwd: Path, *, registry_path: Optional[Path] = None) -> dict:
    """Probe every registry tool and atomically write the cache. Never raises."""
    statuses = check_all(cwd, registry_path=registry_path)
    data = {
        name: {
            "present": s.present, "version": s.version, "required": s.required,
            "reason": s.reason, "install_cmd": s.install_cmd,
        }
        for name, s in statuses.items()
    }
    data["_checked_at"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        forge_dir.mkdir(parents=True, exist_ok=True)
        tmp = forge_dir / (_STATUS_NAME + ".tmp")
        tmp.write_text(json.dumps(data))
        os.replace(tmp, forge_dir / _STATUS_NAME)
    except OSError:
        pass  # advisory cache — never crash the caller
    return data


def read_status_cache(forge_dir: Path) -> Optional[dict]:
    path = forge_dir / _STATUS_NAME
    try:
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def cache_is_fresh(forge_dir: Path) -> bool:
    path = forge_dir / _STATUS_NAME
    try:
        return path.exists() and (dt.datetime.now().timestamp() - path.stat().st_mtime) < _TTL_SECONDS
    except OSError:
        return False


# --------------------------------------------------------------------------- #
# install_command — string only, never executes anything
# --------------------------------------------------------------------------- #


def install_command(tool_name: str, cwd: Path, *, registry_path: Optional[Path] = None) -> Optional[str]:
    for entry in load_registry(registry_path):
        if entry.name == tool_name:
            return _install_cmd_for_entry(entry)
    return None


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="tool_preflight")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="detect every registry tool, print JSON")
    p_check.add_argument("--cwd", default=".")

    p_install = sub.add_parser("install", help="print the install command for one tool")
    p_install.add_argument("tool")
    p_install.add_argument("--cwd", default=".")

    p_refresh = sub.add_parser("refresh", help="probe + write the status cache")
    p_refresh.add_argument("--forge-dir", required=True)
    p_refresh.add_argument("--cwd", default=".")

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    cwd = Path(args.cwd)

    if args.command == "check":
        statuses = check_all(cwd)
        print(json.dumps({name: vars(s) for name, s in statuses.items()}, indent=2))
        return 0

    if args.command == "install":
        cmd = install_command(args.tool, cwd)
        if cmd is None:
            print(f"no install command for {args.tool!r} on this platform", file=sys.stderr)
            return 1
        print(cmd)
        return 0

    if args.command == "refresh":
        write_status_cache(Path(args.forge_dir), cwd)
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
