#!/usr/bin/env python3
"""Implicit lesson-signal producers (REQ-LESSON-SOURCES-001 / T-114).

Today `prompt-submit.py` is the only thing that writes `.forge/correction-flags.jsonl`,
and only when the user types an explicit correction. This module adds five *implicit*
producers that watch a session's event trail (`.forge/errors.log`, rows shaped
`{ts, kind, detail, session}`) and emit correction-flag rows with pattern-match-friendly
prompt text the existing `extract-lessons.py` rule engine already understands — so
observable session pathologies become lessons without an explicit user prompt.

Producers + thresholds (OQ-6, 2026-06-01):
  1. hook-error cluster      — any single hook error kind fires >= 5x this session
  2. repeated design block   — >= 2 design-system violations on similar paths
  3. heredoc bypass          — a bash-heredoc write to a UI file after a block (binary)
  4. gate pass -> wedge      — a gate that passed then wedged within the session (binary)
  5. state-read regression   — a state-read failure this session (binary)

Note on (2)/(3): forge's own pre-tool-write hook never *blocks* (it injects
design-system feedback and exits 0), so a repeated violation injection is the
observable analog of "repeated PreToolUse block," and a heredoc write following a
violation is the EF-003 bypass pattern. Producers read events the hooks log; the
extractor is reused unchanged.

stdlib only — safe to import from hooks.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Optional

ERRORS_LOG_RELPATH = ".forge/errors.log"
FLAGS_RELPATH = ".forge/correction-flags.jsonl"

HOOK_ERROR_CLUSTER_N = 5
REPEATED_BLOCK_M = 2

# Synthetic event kinds the hooks emit for producers 2-4 (not "errors").
KIND_VIOLATION = "pretool_violation"
KIND_HEREDOC_BYPASS = "heredoc_bypass"
KIND_GATE_OUTCOME = "gate_outcome"
KIND_STATE_READ_FAILED = "state_read_failed"


# --------------------------------------------------------------------------- IO

def read_events(forge_dir: Path, session_id: str) -> list[dict]:
    """Return this session's events from .forge/errors.log (oldest first)."""
    log = forge_dir / "errors.log"
    if not log.exists():
        return []
    events: list[dict] = []
    try:
        for line in log.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            if session_id and row.get("session", "") != session_id:
                continue
            events.append(row)
    except OSError:
        return events
    return events


def _is_hook_error(kind: str) -> bool:
    return kind.endswith("_failed")


# ------------------------------------------------------------------ producers

def producer_hook_error_cluster(events: list[dict]) -> Optional[dict]:
    counts: dict[str, int] = {}
    for e in events:
        kind = e.get("kind", "")
        if _is_hook_error(kind):
            counts[kind] = counts.get(kind, 0) + 1
    worst = max(counts.items(), key=lambda kv: kv[1], default=None)
    if worst and worst[1] >= HOOK_ERROR_CLUSTER_N:
        kind, n = worst
        return {
            "signal": "hook_error_cluster",
            "prompt": (
                f"never ignore a recurring hook failure: '{kind}' fired {n} times "
                f"this session — fix the failing hook before continuing"
            ),
        }
    return None


def _path_group(detail: str) -> str:
    """Group key for a violated path: parent dir, else file extension."""
    p = Path(detail)
    parent = str(p.parent)
    return parent if parent not in ("", ".") else p.suffix


def producer_repeated_block(events: list[dict]) -> Optional[dict]:
    groups: dict[str, int] = {}
    for e in events:
        if e.get("kind") == KIND_VIOLATION:
            groups[_path_group(e.get("detail", ""))] = groups.get(_path_group(e.get("detail", "")), 0) + 1
    if any(n >= REPEATED_BLOCK_M for n in groups.values()):
        return {
            "signal": "repeated_design_block",
            "prompt": (
                "don't repeatedly fight the design-system check on the same files — "
                "use design tokens (var(--*)) instead of raw values"
            ),
        }
    return None


def producer_heredoc_bypass(events: list[dict]) -> Optional[dict]:
    if any(e.get("kind") == KIND_HEREDOC_BYPASS for e in events):
        return {
            "signal": "heredoc_bypass",
            "prompt": (
                "don't bypass a blocked Write with a bash heredoc — address the hook's "
                "reason instead of routing around it"
            ),
        }
    return None


def producer_gate_pass_to_wedge(events: list[dict]) -> Optional[dict]:
    """Fire if a stage's gate reported pass (0 blockers) then wedge (>0) this session."""
    seen_pass: set[str] = set()
    for e in events:
        if e.get("kind") != KIND_GATE_OUTCOME:
            continue
        detail = e.get("detail", "")
        stage = _kv(detail, "stage")
        blockers = _kv(detail, "blockers")
        if stage is None or blockers is None:
            continue
        if blockers == "0":
            seen_pass.add(stage)
        elif stage in seen_pass:
            return {
                "signal": "gate_pass_to_wedge",
                "prompt": (
                    f"never advance stage {stage} when its gate hasn't really passed — "
                    f"the gate went from passing to wedged this session"
                ),
            }
    return None


def producer_state_read_regression(events: list[dict]) -> Optional[dict]:
    if any(e.get("kind") == KIND_STATE_READ_FAILED for e in events):
        return {
            "signal": "state_read_regression",
            "prompt": (
                "never proceed on unreadable pipeline state — fix pipeline/state.md "
                "before continuing; gates evaluated against missing data are meaningless"
            ),
        }
    return None


PRODUCERS = [
    producer_hook_error_cluster,
    producer_repeated_block,
    producer_heredoc_bypass,
    producer_gate_pass_to_wedge,
    producer_state_read_regression,
]


def _kv(detail: str, key: str) -> Optional[str]:
    """Parse `key=value` tokens from a 'stage=4 blockers=2' detail string."""
    for tok in detail.split():
        if tok.startswith(key + "="):
            return tok.split("=", 1)[1]
    return None


# ------------------------------------------------------------------- driver

def _existing_signals(flags_path: Path, session_id: str) -> set[str]:
    if not flags_path.exists():
        return set()
    out: set[str] = set()
    try:
        for line in flags_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("session", "") == session_id and row.get("signal"):
                out.add(row["signal"])
    except OSError:
        return out
    return out


def run(forge_dir: Path, session_id: str, *, now: Optional[str] = None) -> list[dict]:
    """Evaluate all producers for the session; append new flags; return them.

    Dedup is per (session, signal) so re-running a session never double-flags.
    """
    events = read_events(forge_dir, session_id)
    if not events:
        return []
    already = _existing_signals(forge_dir / "correction-flags.jsonl", session_id)
    ts = now or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    emitted: list[dict] = []
    flags_path = forge_dir / "correction-flags.jsonl"
    for producer in PRODUCERS:
        result = producer(events)
        if result is None or result["signal"] in already:
            continue
        flag = {"ts": ts, "session": session_id, "prompt": result["prompt"],
                "signal": result["signal"]}
        try:
            forge_dir.mkdir(parents=True, exist_ok=True)
            with flags_path.open("a") as f:
                f.write(json.dumps(flag) + "\n")
        except OSError:
            continue
        already.add(result["signal"])
        emitted.append(flag)
    return emitted
