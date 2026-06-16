#!/usr/bin/env python3
"""Background skill-miner — drives the v2 semantic pipeline (T-183, REQ-SM-010).

This is the detached worker the Stop hook (`hooks/stop-reflect.py`) spawns. It
**drives the v0.3.5 semantic miner** (`scripts/skill_miner_v2.py`) end-to-end,
having retired the v1 tool-name-n-gram path (`mine-skills.py` + the free-text
sliding-tool-window LLM prompt this module used to dispatch):

    read_session_log(.forge/session-log.jsonl)   # _trace_semantics
        -> enrich -> segment                       # semantic verb episodes
        -> mine_candidates                         # success + anti-unification gate
        -> induce                                  # cheap-model de-specialization,
                                                   #   degrades to deterministic skeleton
        -> write_proposals                         # .forge/proposed-skills/<slug>/SKILL.md

The canonical artifact is unchanged — `.forge/proposed-skills/<slug>/SKILL.md` —
so both paths still feed the identical approval flow (`stop-reflect` surfaces them,
`scripts/skill-approval.py` approves/rejects). The legacy `proposed-skills/` dirs
and `skill-blacklist.txt` are honored by `write_proposals` (it skips existing
slugs and blacklisted motif signatures), so migration is clean.

The only LLM call is the induction dispatch, which lives **inside**
`skill_miner_v2.induce` — cost- and capability-gated, and degrading to the
deterministic anti-unified skeleton when background/LLM is unavailable,
`FORGE_NO_BACKGROUND=1`, or the dispatch fails (REQ-NF-017). When no background
capability is present, `run()` still drives the deterministic pipeline and emits
skeleton proposals; it never becomes a no-op and never raises.

Each `run()` appends one completion marker + cost to `.forge/skill-miner-runs.jsonl`
(the spike's O-2 data source); `completion_stats()` reports the completion rate.

Never raises: a failed run is recorded as a failed run, not an exception.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Optional

_PLUGIN_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PLUGIN_DIR / "hooks"))


def _load_sibling(mod_name: str):
    """Load a sibling scripts/ module by name, registering it in sys.modules.

    Registration is required so @dataclass under `from __future__ import
    annotations` in the sibling can resolve its own module (repo lesson). Fail-soft
    at the call site — a missing sibling degrades the run to a recorded failure,
    never a crash (this worker runs detached).
    """
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    path = Path(__file__).resolve().parent / f"{mod_name}.py"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


# The background adapter lives under hooks/. Import it fail-soft so a layout where
# hooks/ is absent never blocks the deterministic pipeline (REQ-NF-017).
try:
    import _background_agent  # type: ignore  # noqa: E402 (the single background adapter)
except Exception:  # noqa: BLE001 — induction degrades to deterministic if absent
    _background_agent = None  # type: ignore[assignment]

_RUNS_NAME = "skill-miner-runs.jsonl"
_SESSION_LOG_NAME = "session-log.jsonl"
_TS_FMT = "%Y-%m-%dT%H:%M:%SZ"


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


# --- capability gate --------------------------------------------------------

def _background_available(forge_dir: Path) -> bool:
    """True iff the background capability is advertised AND not killed. Mirrors the
    Stop hook's gate so `induce` only attempts an LLM dispatch when the substrate
    is on. Deterministic skeleton mining runs regardless. Never raises."""
    if _background_agent is None:
        return False
    if os.environ.get("FORGE_NO_BACKGROUND") == "1":
        return False
    try:
        caps = _background_agent.read_capabilities(forge_dir) or {}
        return caps.get("forge_background_available") is True
    except Exception:  # noqa: BLE001 — gate read must never raise
        return False


# --- the v2 pipeline driver -------------------------------------------------

def run(
    forge_dir: Path,
    session_id: str,
    cwd: Optional[str] = None,
    claude_bin: Optional[str] = None,
    model: Optional[str] = None,
    now: Optional[dt.datetime] = None,
) -> str:
    """Drive one semantic skill-mining run over `.forge/session-log.jsonl` and
    record the outcome. Returns the recorded status. Never raises.

    The pipeline (read -> enrich -> segment -> mine -> induce -> emit) is the v2
    semantic miner (`skill_miner_v2`). Induction is the only LLM call and is
    capability/cost-gated inside `induce`, degrading to deterministic skeletons.

    Status:
      - "completed": the pipeline ran to emission (zero or more proposals written);
      - "skipped":   the cost-cap blocked every induction dispatch (no LLM spend);
      - "failed":    a library import or unexpected error (recorded, never raised).
    """
    try:
        sm = _load_sibling("skill_miner_v2")
        ts = _load_sibling("_trace_semantics")
    except Exception:  # noqa: BLE001 — missing library degrades to a recorded failure
        record_run(forge_dir, session_id, "failed", 0.0, now=now)
        return "failed"

    try:
        records = ts.read_session_log(forge_dir / _SESSION_LOG_NAME)
        episodes = ts.segment(ts.enrich(records))
        candidates = sm.mine_candidates(episodes)

        available = _background_available(forge_dir)
        induce_kwargs = {
            "forge_dir": forge_dir,
            "available": available,
            "cwd": cwd,
            "claude_bin": claude_bin,
        }
        if model is not None:
            induce_kwargs["model"] = model
        induced = sm.induce(candidates, **induce_kwargs)

        sm.write_proposals(induced, forge_dir=forge_dir)

        # Cost: induction may have spent on the ledger; mining itself is free. The
        # per-dispatch spend is captured by _cost_cap; we record 0.0 here when no
        # LLM ran (deterministic degrade) and otherwise leave precise accounting to
        # the ledger — the run marker tracks completion, not exact $.
        record_run(forge_dir, session_id, "completed", 0.0, now=now)
        return "completed"
    except Exception:  # noqa: BLE001 — worker must never raise (it runs detached)
        record_run(forge_dir, session_id, "failed", 0.0, now=now)
        return "failed"


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="skill_miner_bg")
    parser.add_argument("--forge-dir", required=True)
    parser.add_argument("--session", default="")
    parser.add_argument("--cwd", default=None)
    parser.add_argument("--claude-bin", default=None)
    parser.add_argument("--model", default=None, help="induction model alias (default: cheap)")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    run(Path(args.forge_dir), args.session, cwd=args.cwd, claude_bin=args.claude_bin, model=args.model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
