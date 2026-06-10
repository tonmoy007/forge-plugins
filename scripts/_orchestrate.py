#!/usr/bin/env python3
"""Orchestration primitive — deterministic, bounded, in-session fan-out (T-148,
REQ-F-031/032/033/035, ADR-006).

`fan_out` runs a work-list across bounded parallel agent dispatches and returns the
results **ordered by input index** (not completion order), so the parallel and
sequential paths are byte-identical (REQ-NF-009). Each result is parsed + validated;
malformed output is retried once, then dropped with a logged reason — never silently
truncated. Every dispatch is cost-gated through `_cost_cap` (via the single
`_background_agent.dispatch` wrapper, REQ-NF-010).

A Python `scripts/` primitive cannot drive Claude's in-session Agent tool, so each
single call delegates to `_background_agent.dispatch` (`claude -p`). Orchestration is
**synchronous** (it awaits + validates every result), which is why it stays decoupled
from the daemon spike gate — see ADR-006.
"""

from __future__ import annotations

import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

_PLUGIN_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PLUGIN_DIR / "hooks"))
import _background_agent  # noqa: E402  (the sole `claude -p` wrapper)

_LOG = logging.getLogger(__name__)

DEFAULT_MAX_PARALLEL = 4
DEFAULT_MAX_TOTAL = 64


@dataclass
class FanOutResult:
    results: list
    completed: int
    dropped: int
    total_cost_usd: float
    dropped_reasons: list = field(default_factory=list)


def _attempt(prompt: str, dispatch_fn, validate, kwargs) -> tuple[object, Optional[str], float]:
    """One dispatch + parse + validate. Returns (obj_or_None, reason_or_None, cost)."""
    cost = 0.0
    try:
        res = dispatch_fn(prompt, **kwargs)
    except Exception as exc:  # noqa: BLE001 — a worker must never raise
        return None, f"dispatch raised: {exc}", cost
    cost += float(getattr(res, "cost_usd", 0.0) or 0.0)

    if getattr(res, "status", None) != "ok":
        return None, f"dispatch {getattr(res, 'status', 'error')}", cost
    if (getattr(res, "raw", None) or {}).get("is_error"):
        return None, "agent reported is_error", cost
    try:
        parsed = json.loads(res.result or "")
    except (ValueError, TypeError):
        return None, "non-JSON result", cost
    if validate is not None:
        try:
            parsed = validate(parsed)
        except Exception as exc:  # noqa: BLE001 — validation failure → drop, not crash
            return None, f"validation failed: {exc}", cost
    return parsed, None, cost


def _worker(prompt: str, dispatch_fn, validate, kwargs) -> tuple[object, Optional[str], float]:
    """Dispatch with one retry on failure. Returns (obj_or_None, reason, total_cost)."""
    obj, reason, cost = _attempt(prompt, dispatch_fn, validate, kwargs)
    if obj is not None:
        return obj, None, cost
    obj2, reason2, cost2 = _attempt(prompt, dispatch_fn, validate, kwargs)  # retry once
    if obj2 is not None:
        return obj2, None, cost + cost2
    return None, reason2 or reason, cost + cost2


def fan_out(
    work_items: list,
    build_prompt: Callable[[object], str],
    *,
    forge_dir: Path,
    feature: str,
    validate: Optional[Callable[[dict], object]] = None,
    max_parallel: int = DEFAULT_MAX_PARALLEL,
    max_total: int = DEFAULT_MAX_TOTAL,
    dedup_key: Optional[Callable[[object], object]] = None,
    dispatch_fn=None,
    claude_bin: Optional[str] = None,
    cwd: Optional[str] = None,
) -> FanOutResult:
    """Fan `work_items` out across bounded parallel dispatches; return index-ordered,
    validated, deduplicated results. Never raises."""
    dispatch_fn = dispatch_fn or _background_agent.dispatch
    kwargs = {"forge_dir": forge_dir, "feature": feature, "claude_bin": claude_bin, "cwd": cwd}

    dropped_reasons: list[str] = []
    dispatched = list(work_items[:max_total])
    overflow = len(work_items) - len(dispatched)
    if overflow > 0:
        msg = f"exceeds max_total cap: dropped {overflow} item(s)"
        dropped_reasons.append(msg)
        _LOG.warning("fan_out: %s", msg)

    # Dispatch each item; collect by index so ordering is deterministic.
    slots: list[tuple[object, Optional[str], float]] = [(None, "not run", 0.0)] * len(dispatched)
    workers = max(1, min(max_parallel, len(dispatched) or 1))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_worker, build_prompt(item), dispatch_fn, validate, kwargs): i
            for i, item in enumerate(dispatched)
        }
        for fut in futures:
            i = futures[fut]
            try:
                slots[i] = fut.result()
            except Exception as exc:  # noqa: BLE001 — defensive; workers already guard
                slots[i] = (None, f"worker error: {exc}", 0.0)

    total_cost = sum(c for _, _, c in slots)

    results: list = []
    seen: set = set()
    for obj, reason, _cost in slots:
        if obj is None:
            if reason:
                dropped_reasons.append(reason)
                _LOG.warning("fan_out: dropped item — %s", reason)
            continue
        if dedup_key is not None:
            try:
                key = dedup_key(obj)
            except Exception:  # noqa: BLE001
                key = None
            if key in seen:
                dropped_reasons.append("duplicate (dedup_key)")
                continue
            seen.add(key)
        results.append(obj)

    return FanOutResult(
        results=results,
        completed=len(results),
        dropped=len(work_items) - len(results),
        total_cost_usd=total_cost,
        dropped_reasons=dropped_reasons,
    )
