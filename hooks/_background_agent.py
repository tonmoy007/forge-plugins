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

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
import _cost_cap  # noqa: E402  (sibling hooks/ module — the spend gate)
import _caveman  # noqa: E402  (sibling hooks/ module — the v0.6.1 terse-output preamble)

# Caveman intensities recognised at the chokepoint (REQ-CM-002). Anything else (a typo, the
# unsupported `ultra`/`wenyan`, an env `off`/garbage) resolves to *off* — caveman stays inert.
_CAVEMAN_LEVELS = ("lite", "full")

# Conservative pre-dispatch floor estimates used only to gate spend *before* the
# run (spike O-2): a fresh session pays the ~42k-token cache-creation tax (~$0.05);
# a `--resume` poll is a cache read (~$0.005). Actuals come back in the envelope.
FRESH_FLOOR_USD = 0.06
RESUME_FLOOR_USD = 0.01


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


@dataclass
class DispatchResult:
    """Outcome of a `claude -p` dispatch (REQ-F-002)."""

    status: str  # "ok" | "skipped" | "unavailable" | "error"
    reason: str
    session_id: Optional[str] = None
    cost_usd: Optional[float] = None
    result: Optional[str] = None
    raw: Optional[dict] = None


def dispatch(
    prompt: str,
    *,
    forge_dir: Path,
    feature: str,
    resume: Optional[str] = None,
    model: Optional[str] = None,
    output_schema: Optional[dict] = None,
    max_budget_usd: Optional[float] = None,
    floor_usd: Optional[float] = None,
    caveman: Optional[str] = None,
    claude_bin: Optional[str] = None,
    cwd: Optional[str] = None,
    timeout: float = 120.0,
) -> DispatchResult:
    """Dispatch a headless agent run via `claude -p --output-format json`
    (ADR-005; spike O-1). Synchronous — runs the agent, captures the JSON
    envelope (`session_id`, `total_cost_usd`, `usage`, `result`), and records the
    **actual** cost to the ledger. The caller is responsible for offloading this
    into a detached subprocess so the foreground hook never waits (ADR-004).

    Cost-gated: `_cost_cap.precheck` runs *before* spawning; over-cap → no spawn,
    a skip event, and `status="skipped"`. Pass `resume=<session_id>` to reuse a
    session (`--resume`) — mandatory for cost (fresh ~$0.05 vs resumed ~$0.005).

    Never raises (REQ-F-003): every failure mode yields a structured non-"ok"
    result. The correlation key is the **returned `session_id`**, not
    `claude agents --json` (a `-p` run does not appear there).
    """
    try:
        bin_ = _resolve_bin(claude_bin)
        if not bin_:
            return DispatchResult("unavailable", "claude CLI not found on PATH")

        floor = floor_usd if floor_usd is not None else (
            RESUME_FLOOR_USD if resume else FRESH_FLOOR_USD
        )
        decision = _cost_cap.precheck(forge_dir, floor)
        if not decision.allowed:
            _cost_cap.note_skip(forge_dir, feature=feature, session_id=resume or "", reason=decision.reason)
            return DispatchResult("skipped", decision.reason)

        # Caveman mode (v0.6.1, REQ-CM-002): prepend a terse-output preamble to FREE-PROSE
        # prompts only. The level resolves from the threaded `caveman` arg, else the
        # FORGE_CAVEMAN env var, else off; a schema-constrained dispatch (`output_schema` set)
        # is skipped structurally, so verify/skeptic/gate/miner output is never altered. With no
        # level resolved this is the identity ⇒ byte-identical to v0.6.0 (REQ-NF-041).
        _level = caveman if caveman is not None else os.environ.get("FORGE_CAVEMAN")
        prompt = _caveman.apply(
            prompt,
            enabled=_level in _CAVEMAN_LEVELS,
            has_schema=output_schema is not None,
            level=_level if _level in _CAVEMAN_LEVELS else "lite",
        )

        cmd = [bin_, "-p", prompt, "--output-format", "json"]
        if resume:
            cmd += ["--resume", resume]
        if model:
            cmd += ["--model", model]
        if output_schema:
            # Structured outputs (REQ-HARNESS-001): constrain the agent's result to a
            # JSON Schema via the CLI's `--print`-only `--json-schema` flag. A CLI too
            # old for the flag exits non-zero → a structured "error" result (never
            # raises); the orchestration layer then drops the item with a reason.
            cmd += ["--json-schema", json.dumps(output_schema)]
        if max_budget_usd is not None:
            # Per-dispatch hard $ ceiling enforced by the CLI itself (REQ-HARNESS-002);
            # complements _cost_cap's daily/monthly ledger gate. A CLI too old for the
            # flag exits non-zero → structured "error" result (never raises).
            cmd += ["--max-budget-usd", str(max_budget_usd)]

        try:
            proc = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )
        except subprocess.TimeoutExpired:
            return DispatchResult("error", f"dispatch timeout after {timeout}s")
        except OSError as exc:  # noqa: BLE001 — missing/unexecutable binary
            return DispatchResult("error", f"dispatch failed: {exc}")

        if proc.returncode != 0:
            detail = (proc.stderr or "").strip().splitlines()
            return DispatchResult("error", f"dispatch exit {proc.returncode}: {detail[0] if detail else ''}")

        try:
            data = json.loads(proc.stdout or "")
        except (ValueError, TypeError):
            return DispatchResult("error", "dispatch returned non-JSON output")
        if not isinstance(data, dict):
            return DispatchResult("error", "dispatch envelope was not a JSON object")

        session_id = data.get("session_id")
        cost = data.get("total_cost_usd")
        usage = data.get("usage") or {}
        _cost_cap.record(
            forge_dir,
            feature=feature,
            session_id=session_id or "",
            input_tokens=int(usage.get("input_tokens", 0) or 0),
            output_tokens=int(usage.get("output_tokens", 0) or 0),
            estimated_usd=floor,
            actual_usd=cost,
        )
        return DispatchResult(
            "ok",
            "dispatched",
            session_id=session_id,
            cost_usd=cost,
            result=data.get("result"),
            raw=data,
        )
    except Exception as exc:  # noqa: BLE001 — adapter must never raise (REQ-F-003)
        return DispatchResult("error", f"unexpected dispatch error: {exc}")


# --------------------------------------------------------------------------- #
# Capability cache (REQ-F-001) — written by a detached refresh, read by
# session-start. The probe shells to `claude agents` (~0.3s), too slow for the
# session-start latency budget (NF-004), so the result is cached and refreshed
# out-of-band; session-start only ever reads the cached file.
# --------------------------------------------------------------------------- #
_CAPABILITIES_NAME = "capabilities.json"


def write_capabilities(
    forge_dir: Path,
    cwd: Optional[str] = None,
    claude_bin: Optional[str] = None,
    timeout: float = 10.0,
) -> dict:
    """Probe and atomically write `<forge_dir>/capabilities.json`. Never raises."""
    cap = detect_capability(claude_bin=claude_bin, cwd=cwd, timeout=timeout)
    data = {
        "forge_background_available": cap.available,
        "reason": cap.reason,
        "active_sessions": cap.active_sessions,
        "checked_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    try:
        forge_dir.mkdir(parents=True, exist_ok=True)
        tmp = forge_dir / (_CAPABILITIES_NAME + ".tmp")
        tmp.write_text(json.dumps(data))
        os.replace(tmp, forge_dir / _CAPABILITIES_NAME)
    except OSError:
        pass  # advisory cache — never crash the caller
    return data


def read_capabilities(forge_dir: Path) -> Optional[dict]:
    """Return the cached capabilities dict, or None if absent/unreadable."""
    path = forge_dir / _CAPABILITIES_NAME
    try:
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _main(argv: list) -> int:
    """CLI entry so session-start can spawn a detached capability refresh."""
    import argparse

    parser = argparse.ArgumentParser(prog="_background_agent")
    parser.add_argument("--write-capabilities", action="store_true")
    parser.add_argument("--forge-dir", required=True)
    parser.add_argument("--cwd", default=None)
    args = parser.parse_args(argv)
    if args.write_capabilities:
        write_capabilities(Path(args.forge_dir), cwd=args.cwd)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
