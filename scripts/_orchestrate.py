#!/usr/bin/env python3
"""Orchestration primitive — deterministic, bounded, in-session fan-out (T-148,
REQ-F-031/032/033/035, ADR-006; retrofit onto the workflow engine T-194, REQ-WF-004).

`fan_out` runs a work-list across bounded parallel agent dispatches and returns the
results **ordered by input index** (not completion order), so the parallel and
sequential paths are byte-identical (REQ-NF-009/026). Each result is parsed + validated;
malformed output is retried once, then dropped with a logged reason — never silently
truncated. Every dispatch is cost-gated through `_cost_cap` (via the single
`_background_agent.dispatch` wrapper, REQ-NF-010).

`fan_out` is now the **single-wave special case of `run_workflow`** (REQ-WF-004): a flat
list of independent `WorkflowNode`s — no `depends_on`, one shared prompt + schema mapped
over the items — delegated to the engine. Index ordering is preserved by giving each node
a zero-padded id (so `sorted(ids)` == input order); `dedup_key` (which the engine has no
notion of) is applied here, after the engine returns, in that same index order. The result
EQUALS the pre-retrofit output (AC-WF-005): same ordering, same retry/drop/dedup semantics.

A Python `scripts/` primitive cannot drive Claude's in-session Agent tool, so each
single dispatch delegates (via the engine) to `_background_agent.dispatch` (`claude -p`).
Orchestration is **synchronous** (it awaits + validates every result), which is why it
stays decoupled from the daemon spike gate — see ADR-006.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

_PLUGIN_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PLUGIN_DIR / "scripts"))
sys.path.insert(0, str(_PLUGIN_DIR / "hooks"))
import _background_agent  # noqa: E402  (the sole `claude -p` wrapper)
import _workflow  # noqa: E402  (the DAG engine; fan_out is its single-wave special case)

_LOG = logging.getLogger(__name__)

DEFAULT_MAX_PARALLEL = _workflow.DEFAULT_MAX_PARALLEL
DEFAULT_MAX_TOTAL = _workflow.DEFAULT_MAX_TOTAL


@dataclass
class FanOutResult:
    results: list
    completed: int
    dropped: int
    total_cost_usd: float
    dropped_reasons: list = field(default_factory=list)


def _legacy_dispatch_adapter(dispatch_fn, *, want_output_schema: bool):
    """Wrap the engine's dispatch call so the kwargs a custom `dispatch_fn` sees are
    byte-identical to the pre-retrofit `fan_out` contract. The engine always threads
    `model`/`max_budget_usd`/`resume`/`output_schema` (some as ``None``) into every
    dispatch; legacy `fan_out` never sent those, and only sent `output_schema` when the
    caller requested one. Strip the engine-only keys (and `output_schema` when unwanted)
    so behavior — and kwarg-asserting tests — are preserved (REQ-WF-004 / AC-WF-005)."""
    def adapted(prompt, **kw):
        kw.pop("model", None)
        kw.pop("max_budget_usd", None)
        kw.pop("resume", None)
        if not want_output_schema:
            kw.pop("output_schema", None)
        return dispatch_fn(prompt, **kw)
    return adapted


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
    output_schema: Optional[dict] = None,
    session_reuse: bool = False,
    caveman: Optional[str] = None,
) -> FanOutResult:
    """Fan `work_items` out across bounded parallel dispatches; return index-ordered,
    validated, deduplicated results. Never raises.

    Implemented as the single-wave special case of `run_workflow` (REQ-WF-004): one
    independent `WorkflowNode` per item with a zero-padded id (so id order == input
    index order), the shared `build_prompt`/`validate`/`output_schema`, and no edges.
    The engine handles bounded parallel dispatch, retry-once-then-drop, the `max_total`
    cap, and cost summing; `dedup_key` is applied here afterward (the engine has no
    dedup notion), in index order, so the first occurrence wins exactly as before."""
    dispatch_fn = dispatch_fn or _background_agent.dispatch
    items = list(work_items)

    # One node per item; zero-padded id keeps `sorted(ids)` == input index order, so the
    # engine's id-ordered result projects straight back to fan_out's index-ordered list.
    width = max(1, len(str(len(items) - 1))) if items else 1
    nodes = [
        _workflow.WorkflowNode(
            id=f"{i:0{width}d}",
            build_prompt=(lambda _upstream, item=item: build_prompt(item)),
            output_schema=output_schema,
            validate=validate,
        )
        for i, item in enumerate(items)
    ]

    adapter = _legacy_dispatch_adapter(dispatch_fn, want_output_schema=output_schema is not None)
    wf = _workflow.run_workflow(
        _workflow.WorkflowSpec(nodes=nodes),
        forge_dir=forge_dir,
        feature=feature,
        max_parallel=max_parallel,
        max_total=max_total,
        dispatch_fn=adapter,
        claude_bin=claude_bin,
        cwd=cwd,
        # Threaded for plumbing parity (v0.6.0, REQ-WF-019); inert this task (T-214).
        session_reuse=session_reuse,
        # Caveman level (v0.6.1, REQ-CM-003): threaded through to the chokepoint; reaches dispatch
        # only when set, so a free-prose fan-out can opt into terse output. None ⇒ byte-identical.
        caveman=caveman,
    )

    dropped_reasons = list(wf.dropped_reasons)

    # Project the engine's id-ordered dict back to an index-ordered list, applying
    # `dedup_key` (first-by-index wins) — the one fan_out semantic the engine lacks.
    results: list = []
    seen: set = set()
    for nid in sorted(wf.results):
        obj = wf.results[nid]
        if dedup_key is not None:
            try:
                key = dedup_key(obj)
            except Exception:  # noqa: BLE001 — a bad key must not sink the fan-out
                key = None
            if key in seen:
                dropped_reasons.append("duplicate (dedup_key)")
                continue
            seen.add(key)
        results.append(obj)

    return FanOutResult(
        results=results,
        completed=len(results),
        dropped=len(items) - len(results),
        total_cost_usd=wf.total_cost_usd,
        dropped_reasons=dropped_reasons,
    )
