#!/usr/bin/env python3
"""Background skill-miner — the spike's instrumented dispatch (T-139, REQ-F-027/028).

When background capability is available, `stop-reflect.py` offloads skill-mining to
a real background agent through `_background_agent.dispatch` (reusing one session via
`--resume`), instead of the inline deterministic `mine-skills.py`. This module is the
detached worker: it dispatches the mining agent, then records a completion marker +
cost to `.forge/skill-miner-runs.jsonl`.

Those markers are the data source for the spike's O-2 gate (REQ-F-028): real sessions
accumulate runs, and `completion_stats()` reports the completion rate (≥90% over ≥5
sessions) and per-session cost. Nothing here fabricates a run — each line is one real
dispatch.

Never raises: a failed dispatch is recorded as a failed run, not an exception.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Optional

_PLUGIN_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PLUGIN_DIR / "hooks"))
import _background_agent  # noqa: E402  (the single background adapter)

_RUNS_NAME = "skill-miner-runs.jsonl"
_SESSION_NAME = "skill-miner-session.json"
_TS_FMT = "%Y-%m-%dT%H:%M:%SZ"

# Skill-mining is a cheap, mechanical task — pin a cheap model. Real-usage testing
# showed the session default (Opus-class) costs ~$1/run, ~20× the spike's
# haiku-measured estimate and well over the O-2 budget. (Override via --model.)
MINER_MODEL = "haiku"

_PROMPT = (
    "You are Forge's skill-miner. Read `.forge/patterns.jsonl` in the current "
    "project (it holds sliding tool-usage windows). If any tool-sequence signature "
    "recurs 3 or more times, append one compact JSON object per proposed skill to "
    "`.forge/proposals.jsonl` with fields {signature, suggestion, count}. If nothing "
    "qualifies, write nothing. Be terse. Reply with exactly: done"
)


def _now(now: Optional[dt.datetime]) -> dt.datetime:
    return now if now is not None else dt.datetime.now(dt.timezone.utc)


# --- run markers ------------------------------------------------------------

def record_run(
    forge_dir: Path,
    session_id: str,
    status: str,
    cost_usd: float,
    now: Optional[dt.datetime] = None,
) -> None:
    """Append one completion marker. status ∈ {completed, failed, skipped}. Never raises."""
    entry = {
        "ts": _now(now).strftime(_TS_FMT),
        "session": session_id,
        "status": status,
        "cost_usd": cost_usd,
    }
    try:
        forge_dir.mkdir(parents=True, exist_ok=True)
        with (forge_dir / _RUNS_NAME).open("a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        return


def completion_stats(forge_dir: Path) -> dict:
    """Read the run markers and report the O-2 numbers. Skipped runs (deliberate
    cost-cap no-ops) are excluded from the completion rate. Never raises."""
    completed = failed = skipped = 0
    total_cost = 0.0
    path = forge_dir / _RUNS_NAME
    try:
        lines = path.read_text().splitlines() if path.exists() else []
    except OSError:
        lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        status = row.get("status")
        if status == "completed":
            completed += 1
        elif status == "failed":
            failed += 1
        elif status == "skipped":
            skipped += 1
        try:
            total_cost += float(row.get("cost_usd") or 0.0)
        except (TypeError, ValueError):
            pass
    n = completed + failed + skipped
    denom = completed + failed
    rate = (completed / denom) if denom else None
    avg_cost = (total_cost / n) if n else 0.0
    return {
        "n": n,
        "completed": completed,
        "failed": failed,
        "skipped": skipped,
        "completion_rate": rate,
        "total_cost_usd": total_cost,
        "avg_cost_usd": avg_cost,
    }


# --- session reuse ----------------------------------------------------------

def _load_miner_session(forge_dir: Path) -> Optional[str]:
    try:
        data = json.loads((forge_dir / _SESSION_NAME).read_text())
        sid = data.get("session_id")
        return sid if isinstance(sid, str) and sid else None
    except (OSError, ValueError, AttributeError):
        return None


def _save_miner_session(forge_dir: Path, session_id: str) -> None:
    try:
        forge_dir.mkdir(parents=True, exist_ok=True)
        (forge_dir / _SESSION_NAME).write_text(json.dumps({"session_id": session_id}))
    except OSError:
        return


# --- the dispatch -----------------------------------------------------------

def run(
    forge_dir: Path,
    session_id: str,
    cwd: Optional[str] = None,
    claude_bin: Optional[str] = None,
    model: Optional[str] = MINER_MODEL,
) -> str:
    """Dispatch one background skill-mining run, reusing the miner's session, and
    record the outcome. Returns the recorded status. Never raises."""
    try:
        prior = _load_miner_session(forge_dir)
        res = _background_agent.dispatch(
            _PROMPT,
            forge_dir=forge_dir,
            feature="skill_miner",
            resume=prior,
            model=model,
            cwd=cwd,
            claude_bin=claude_bin,
        )
        if res.status == "skipped":
            status = "skipped"
        elif res.status == "ok" and not (res.raw or {}).get("is_error"):
            status = "completed"
            if res.session_id:
                _save_miner_session(forge_dir, res.session_id)
        else:
            status = "failed"
        record_run(forge_dir, session_id, status, res.cost_usd or 0.0)
        return status
    except Exception:  # noqa: BLE001 — worker must never raise (it runs detached)
        record_run(forge_dir, session_id, "failed", 0.0)
        return "failed"


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="skill_miner_bg")
    parser.add_argument("--forge-dir", required=True)
    parser.add_argument("--session", default="")
    parser.add_argument("--cwd", default=None)
    parser.add_argument("--claude-bin", default=None)
    parser.add_argument("--model", default=MINER_MODEL, help=f"model alias (default: {MINER_MODEL})")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    run(Path(args.forge_dir), args.session, cwd=args.cwd, claude_bin=args.claude_bin, model=args.model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
