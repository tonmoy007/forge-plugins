#!/usr/bin/env python3
"""Background-agent adapter — the single wrapper around Claude Code's background
agent surface (REQ-F-002).

v0.2 P0 foundation. Every Forge call that touches background agents goes through
this module, so a host-API change touches exactly one file. Built and validated
against the **real** API in Claude Code v2.1.169:

  - `claude agents --json [--cwd <path>]` lists active background sessions as a
    JSON array, headlessly (no TTY) — this is what the probe and the Observer
    monitor use.
  - `claude -p` provides headless dispatch.

Note: the original 2026-05-14 v0.2 draft assumed `claude --bg` / `/bg` / `/tasks`.
That surface no longer exists; the shipped surface is `claude agents`. See
`build/06-evaluation/spike-background-agents.md`.

Design rules:
  - REQ-F-003: every call degrades to a structured no-op when the capability is
    absent — it NEVER raises. Hooks must not crash on a missing/old CLI.
  - Stdlib only (subprocess, json, shutil). No PyYAML, no external deps.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Capability:
    """Result of a background-capability probe (REQ-F-001)."""

    available: bool
    reason: str
    claude_bin: Optional[str] = None
    active_sessions: int = 0
    sessions: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "forge_background_available": self.available,
            "reason": self.reason,
            "active_sessions": self.active_sessions,
        }


def _resolve_bin(claude_bin: Optional[str]) -> Optional[str]:
    return claude_bin or shutil.which("claude")


def _run_agents_json(claude_bin: str, cwd: Optional[str], timeout: float) -> tuple[int, str, str]:
    """Run `claude agents --json [--cwd]`. Returns (returncode, stdout, stderr).

    Never raises — a timeout or OS error is reported as a non-zero return.
    """
    cmd = [claude_bin, "agents", "--json"]
    if cwd:
        cmd += ["--cwd", cwd]
    try:
        proc = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except OSError as exc:  # noqa: BLE001 — missing/unexecutable binary, etc.
        return 127, "", str(exc)


def detect_capability(
    claude_bin: Optional[str] = None,
    cwd: Optional[str] = None,
    timeout: float = 10.0,
) -> Capability:
    """Probe for background-agent capability (REQ-F-001).

    Returns a Capability with `available=True` only when the `claude` CLI is
    present AND `claude agents --json` returns a JSON array. Any failure mode
    (no CLI, non-zero exit, timeout, unparseable output) yields `available=False`
    with a human-readable reason — and never raises (REQ-F-003).
    """
    bin_ = _resolve_bin(claude_bin)
    if not bin_:
        return Capability(False, "claude CLI not found on PATH")

    rc, out, err = _run_agents_json(bin_, cwd, timeout)
    if rc != 0:
        detail = (err or "").strip().splitlines()[0] if err else f"exit {rc}"
        return Capability(False, f"`claude agents --json` failed: {detail}", claude_bin=bin_)

    try:
        data = json.loads(out or "[]")
    except (ValueError, TypeError):
        return Capability(False, "`claude agents --json` returned non-JSON output", claude_bin=bin_)

    if not isinstance(data, list):
        return Capability(False, "`claude agents --json` did not return a JSON array", claude_bin=bin_)

    return Capability(
        True,
        "background agents available via `claude agents`",
        claude_bin=bin_,
        active_sessions=len(data),
        sessions=data,
    )


def list_sessions(
    claude_bin: Optional[str] = None,
    cwd: Optional[str] = None,
    timeout: float = 10.0,
) -> list:
    """Return the list of active background sessions, or [] when unavailable.

    Degraded no-op (REQ-F-003): any failure returns an empty list, never raises.
    The Observer monitor and `/forge:status` build on this.
    """
    cap = detect_capability(claude_bin=claude_bin, cwd=cwd, timeout=timeout)
    return cap.sessions if cap.available else []
