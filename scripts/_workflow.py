#!/usr/bin/env python3
"""Dynamic workflow engine — deterministic, bounded, topological DAG execution (v0.4.0 spike).

Generalizes `_orchestrate.fan_out` from a flat *homogeneous* parallel map to an arbitrary
**DAG of heterogeneous agent steps**: each node carries its own prompt builder, optional
output schema, model, and validator; nodes declare `depends_on` edges; downstream nodes
receive their upstream results for data passing. Nodes are scheduled in dependency *waves*
(Kahn's algorithm) and each wave fans out across bounded parallel `claude -p` dispatches via
the single `_background_agent.dispatch` wrapper (cost-gated, never-raises).

Determinism (REQ-NF-009 lineage): results are keyed by node id and assembled in sorted
order, so a parallel run and a sequential (`max_parallel=1`) run are byte-identical. A node
whose dispatch fails is retried once, then dropped with a logged reason — never silently
truncated; any node with a dropped/missing dependency is skipped (no orphan dispatch).
Never raises: every failure becomes a structured `dropped_reasons` entry.

A Python `scripts/` primitive cannot drive Claude's in-session Agent tool (ADR-006), so each
node delegates to `_background_agent.dispatch`. This is the reusable core the v0.4.0 modes
(general engine / user-defined flows / per-stage parallel build) build on; `fan_out` becomes
the single-wave special case.
"""

from __future__ import annotations

import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

_PLUGIN_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PLUGIN_DIR / "hooks"))
import _background_agent  # noqa: E402  (the sole `claude -p` wrapper)

_LOG = logging.getLogger(__name__)

DEFAULT_MAX_PARALLEL = 4
DEFAULT_MAX_TOTAL = 64

# Per-node admission cost estimate (REQ-NF-029): each DAG node is a *fresh* dispatch and pays
# the fresh-session cache-creation tax, so budget-aware admission charges one fresh floor per
# node. Sourced from the single dispatch adapter so the estimate can never drift from the real
# cost gate (`_background_agent.dispatch` charges the same floor in `_cost_cap.precheck`).
FRESH_FLOOR_USD = _background_agent.FRESH_FLOOR_USD


@dataclass
class VerifySpec:
    """Declarative per-node verification request (REQ-WF-001/002).

    When a node carries a `VerifySpec`, an independent fresh-session verifier runs after the
    node's own dispatch and gates its result (`verdict_failed` ⇒ drop-with-reason or one heal
    attempt). The verifier runs `skill` under `model`, constraining its verdict to `schema`.
    T-191 only introduces the type; the engine *wiring* of verification lands in T-192 via the
    shared `scripts/_verify.py` primitive.
    """

    skill: str
    model: Optional[str] = None
    schema: Optional[dict] = None


@dataclass
class WorkflowNode:
    """One step in a workflow DAG.

    `build_prompt` receives a dict `{dep_id: validated_result}` of this node's completed
    upstream dependencies and returns the prompt string for this node's dispatch — this is
    the inter-step data-passing channel.
    """

    id: str
    build_prompt: Callable[[dict], str]
    depends_on: list = field(default_factory=list)
    output_schema: Optional[dict] = None
    model: Optional[str] = None
    validate: Optional[Callable[[dict], Any]] = None
    verify: Optional[VerifySpec] = None  # per-node verification request (wired in T-192)


@dataclass
class WorkflowSpec:
    nodes: list  # list[WorkflowNode]


@dataclass
class WorkflowResult:
    results: dict  # {node_id: validated_output}, ordered by node id
    completed: int
    dropped: int
    total_cost_usd: float
    dropped_reasons: list = field(default_factory=list)


def plan_waves(spec: WorkflowSpec) -> list:
    """Group nodes into dependency waves (Kahn's algorithm); node ids are sorted within
    each wave for determinism. Returns ``[]`` if the graph has a cycle (no valid ordering).
    Unknown dependencies are ignored here (they are reported by `validate_spec`)."""
    nodes = list(getattr(spec, "nodes", []) or [])
    id_set = {n.id for n in nodes}
    pending = {n.id: {d for d in (n.depends_on or []) if d in id_set} for n in nodes}
    done: set = set()
    waves: list[list[str]] = []
    while pending:
        ready = sorted(nid for nid, deps in pending.items() if deps <= done)
        if not ready:
            return []  # no progress possible → cycle
        waves.append(ready)
        for nid in ready:
            done.add(nid)
            del pending[nid]
    return waves


def validate_spec(spec: WorkflowSpec) -> list:
    """Return structural errors (``[]`` == valid): duplicate ids, unknown dependencies,
    and cycles. Never raises."""
    errors: list[str] = []
    nodes = list(getattr(spec, "nodes", []) or [])
    ids = [n.id for n in nodes]

    seen: set = set()
    for nid in ids:
        if nid in seen:
            errors.append(f"duplicate node id: {nid!r}")
        seen.add(nid)
    id_set = set(ids)

    for n in nodes:
        for dep in (n.depends_on or []):
            if dep not in id_set:
                errors.append(f"node {n.id!r} depends on unknown node {dep!r}")

    if nodes and not plan_waves(spec):
        errors.append("cycle detected in workflow graph")

    return errors


def _attempt(node: WorkflowNode, prompt: str, dispatch_fn, kwargs) -> tuple:
    """One dispatch + parse + validate for a node. Returns (obj_or_None, reason, cost)."""
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
    if node.validate is not None:
        try:
            parsed = node.validate(parsed)
        except Exception as exc:  # noqa: BLE001 — validation failure → drop, not crash
            return None, f"validation failed: {exc}", cost
    return parsed, None, cost


def _run_node(node: WorkflowNode, prompt: str, dispatch_fn, kwargs) -> tuple:
    """Dispatch a node with one retry on failure. Returns (obj_or_None, reason, total_cost)."""
    obj, reason, cost = _attempt(node, prompt, dispatch_fn, kwargs)
    if obj is not None:
        return obj, None, cost
    obj2, reason2, cost2 = _attempt(node, prompt, dispatch_fn, kwargs)  # retry once
    if obj2 is not None:
        return obj2, None, cost + cost2
    return None, reason2 or reason, cost + cost2


def run_workflow(
    spec: WorkflowSpec,
    *,
    forge_dir: Path,
    feature: str,
    max_parallel: int = DEFAULT_MAX_PARALLEL,
    max_total: int = DEFAULT_MAX_TOTAL,
    max_budget_usd: Optional[float] = None,
    resume: Optional[str] = None,
    dispatch_fn=None,
    claude_bin: Optional[str] = None,
    cwd: Optional[str] = None,
) -> WorkflowResult:
    """Execute a workflow DAG wave-by-wave with bounded parallel fan-out per wave.

    Validates the spec first (invalid → nothing dispatched). Within each wave, ready nodes
    fan out across at most `max_parallel` threads; results pass to downstream nodes via
    `build_prompt`. Index/id-ordered + retry-once-then-drop discipline mirrors
    `_orchestrate.fan_out`, so parallel and sequential runs are byte-identical. Never raises.

    Bounding (REQ-NF-027/029): `max_total` caps the node count and `max_budget_usd` caps total
    spend; both are pre-allocated in topological order (wave, then id) so cap pressure drops a
    *fixed* set independent of thread scheduling. `max_budget_usd` and `resume` are threaded
    into every node's `dispatch` call — the CLI enforces the per-dispatch ceiling and reuses
    the given session (cheaper than a fresh one).
    """
    dispatch_fn = dispatch_fn or _background_agent.dispatch
    nodes = list(getattr(spec, "nodes", []) or [])
    dropped_reasons: list[str] = []

    errors = validate_spec(spec)
    if errors:
        for e in errors:
            dropped_reasons.append(f"invalid spec: {e}")
            _LOG.warning("run_workflow: %s", e)
        return WorkflowResult(results={}, completed=0, dropped=len(nodes),
                              total_cost_usd=0.0, dropped_reasons=dropped_reasons)

    by_id = {n.id: n for n in nodes}
    waves = plan_waves(spec)

    # Deterministic budget-aware admission (REQ-NF-029): walk nodes in topological order
    # (wave, then sorted id) and admit each while it fits *both* the count cap (`max_total`)
    # and the spend cap (`max_budget_usd`, charged one fresh-session floor per node). Because
    # admission is a single-threaded topological pass — never a thread race — cap pressure
    # drops a *fixed* set, identical across parallel and sequential runs (REQ-NF-026b).
    allowed: set = set()
    count_budget = max_total
    spend_budget = max_budget_usd  # None ⇒ no spend cap
    capped_by_total = False
    capped_by_budget = False
    for wave in waves:
        for nid in wave:  # sorted within wave
            if count_budget <= 0:
                capped_by_total = True
                continue
            if spend_budget is not None and spend_budget < FRESH_FLOOR_USD:
                capped_by_budget = True
                continue
            allowed.add(nid)
            count_budget -= 1
            if spend_budget is not None:
                spend_budget -= FRESH_FLOOR_USD
    overflow = len(nodes) - len(allowed)
    if overflow > 0:
        caps = []
        if capped_by_total:
            caps.append("max_total")
        if capped_by_budget:
            caps.append(f"max_budget_usd (${max_budget_usd:.2f}, ${FRESH_FLOOR_USD:.2f}/node)")
        msg = f"exceeds {' and '.join(caps)} cap: dropped {overflow} node(s)"
        dropped_reasons.append(msg)
        _LOG.warning("run_workflow: %s", msg)

    results: dict = {}
    total_cost = 0.0

    for wave in waves:
        prepared: list[tuple[WorkflowNode, str]] = []  # (node, prompt) ready to dispatch
        for nid in wave:
            if nid not in allowed:
                continue  # capped — reason already logged once above
            node = by_id[nid]
            missing = [d for d in (node.depends_on or []) if d not in results]
            if missing:
                reason = f"node {nid!r} skipped: dependency dropped/missing {missing}"
                dropped_reasons.append(reason)
                _LOG.warning("run_workflow: %s", reason)
                continue
            upstream = {d: results[d] for d in (node.depends_on or [])}
            try:
                prompt = node.build_prompt(upstream)
            except Exception as exc:  # noqa: BLE001 — build failure → drop, not crash
                reason = f"node {nid!r} build_prompt failed: {exc}"
                dropped_reasons.append(reason)
                _LOG.warning("run_workflow: %s", reason)
                continue
            prepared.append((node, prompt))

        if not prepared:
            continue

        workers = max(1, min(max_parallel, len(prepared)))
        wave_out: dict = {}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    _run_node, node, prompt, dispatch_fn,
                    {"forge_dir": forge_dir, "feature": feature, "model": node.model,
                     "output_schema": node.output_schema, "max_budget_usd": max_budget_usd,
                     "resume": resume, "claude_bin": claude_bin, "cwd": cwd},
                ): node.id
                for node, prompt in prepared
            }
            for fut in futures:
                nid = futures[fut]
                try:
                    wave_out[nid] = fut.result()
                except Exception as exc:  # noqa: BLE001 — defensive; _run_node already guards
                    wave_out[nid] = (None, f"worker error: {exc}", 0.0)

        # Collect this wave's results in sorted id order so accumulation is deterministic.
        for nid in sorted(wave_out):
            obj, reason, cost = wave_out[nid]
            total_cost += cost
            if obj is None:
                dropped_reasons.append(f"node {nid!r}: {reason}")
                _LOG.warning("run_workflow: dropped %s — %s", nid, reason)
                continue
            results[nid] = obj

    ordered = {nid: results[nid] for nid in sorted(results)}
    completed = len(ordered)
    return WorkflowResult(
        results=ordered,
        completed=completed,
        dropped=len(nodes) - completed,
        total_cost_usd=total_cost,
        dropped_reasons=dropped_reasons,
    )
