#!/usr/bin/env python3
"""Per-stage parallel build fan-out (v0.4.0, REQ-WF-007 / T-196).

The build stage today walks ready task-DAG nodes one at a time (`build-batch.py` emits the order,
`autopilot.py` sequences). This module fans the *ready* nodes — those whose `depends_on` are all
already done — out across the dynamic-workflow engine: when the `parallel_build` toggle is on they
run in bounded parallel; when off they run sequentially (`max_parallel=1`), preserving today's
behavior. The engine is always available (no toggle); the toggle only chooses the width.

Each ready node becomes a `WorkflowNode` with **no edges** (ready nodes are independent by
definition — their deps are satisfied) and an optional per-node `cwd` (T-196), supplied by the
caller via `cwd_for` so T-197 can hand each node its own git worktree. Data passing is not used
here — a build task produces a file mutation, judged at the join, not an upstream value.

Design rules (REQ-NF-024/027/028):
  - Stdlib only; **never raises** — every path returns a `WorkflowResult`. Delegates dispatch
    to the engine, which routes through the single cost-gated `_background_agent` adapter.
  - Opt-in: with `parallel_build` off (default), the result is byte-identical to the parallel
    run given identical dispatch outcomes (REQ-NF-026a) — the engine result is id-ordered.
  - `claude -p` dispatches only, never the in-session Agent tool (ADR-006).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

_PLUGIN_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PLUGIN_DIR / "scripts"))
import _workflow as _wf  # noqa: E402  (the dynamic-workflow engine — T-191/192/196)
import _worktree as _wt  # noqa: E402  (git-worktree isolation lifecycle — T-197)


@dataclass
class TaskNode:
    """One task-DAG node for the build stage: an id and its dependency ids.

    Mirrors `build-batch.py`'s `(task_id, {dep_ids})` view of the project task DAG, but as a
    structured value the fan-out can map to a `WorkflowNode`.
    """

    id: str
    depends_on: list = field(default_factory=list)


def ready_nodes(tasks: list, done: set) -> list:
    """Return the ids of tasks ready to build now: not already done, with every `depends_on`
    already done. Sorted for determinism (topological ties broken by id). Never raises."""
    done = set(done or ())
    ready = [
        t.id for t in (tasks or [])
        if t.id not in done and set(t.depends_on or []) <= done
    ]
    return sorted(ready)


def _default_build_prompt(task_id: str) -> str:
    """Prompt for a single build task when the caller supplies no custom builder. Embeds the task
    id so the dispatched builder knows which task-DAG node to implement."""
    return (
        f"Implement task {task_id} from the project's task DAG: build the code for this task per "
        f"the technical spec and plan, then return a JSON summary of the files changed."
    )


def run_parallel_build(
    tasks: list,
    done: set,
    *,
    config,
    forge_dir: Path,
    feature: str,
    dispatch_fn=None,
    build_prompt: Optional[Callable[[str], str]] = None,
    cwd_for: Optional[Callable[[str], Optional[str]]] = None,
    cwd: Optional[str] = None,
    claude_bin: Optional[str] = None,
    resume: Optional[str] = None,
    repo: Optional[Path] = None,
) -> "object":
    """Fan the ready task-DAG nodes out through the engine and return its `WorkflowResult`.

    `config` is an `OrchestrationConfig` (`_workflow_config`): `parallel_build` chooses width
    (on ⇒ `config.max_parallel`; off ⇒ 1, sequential), and `max_total`/`max_budget_usd` bound the
    run. `build_prompt(task_id)` overrides the default per-task prompt; `cwd_for(task_id)` assigns
    each node its own working directory and falls back to the scalar `cwd`.

    When `config.worktree_isolation` is on AND `repo` is a git work tree, each ready node runs in
    its **own git worktree** (branch-per-node), commits, and merges at a join where git surfaces
    conflicts (T-197). When worktrees are unavailable it **degrades to a sequential single
    worktree** — the plain path with `max_parallel=1`. Never raises (the engine never raises)."""
    ids = ready_nodes(tasks, done)
    if not ids:
        return _wf.WorkflowResult(results={}, completed=0, dropped=0, total_cost_usd=0.0)

    if getattr(config, "worktree_isolation", False):
        if repo is not None and _wt.worktrees_available(repo):
            return _run_isolated(
                ids, config=config, forge_dir=forge_dir, feature=feature,
                dispatch_fn=dispatch_fn, build_prompt=build_prompt,
                claude_bin=claude_bin, resume=resume, repo=Path(repo),
            )
        # Worktrees unavailable ⇒ degrade to a sequential single-worktree run (REQ-WF-008).
        return _run_plain(
            ids, config=config, forge_dir=forge_dir, feature=feature, dispatch_fn=dispatch_fn,
            build_prompt=build_prompt, cwd_for=cwd_for, cwd=cwd, claude_bin=claude_bin,
            resume=resume, force_sequential=True,
        )

    return _run_plain(
        ids, config=config, forge_dir=forge_dir, feature=feature, dispatch_fn=dispatch_fn,
        build_prompt=build_prompt, cwd_for=cwd_for, cwd=cwd, claude_bin=claude_bin, resume=resume,
    )


def _build_nodes(ids, builder, cwd_for):
    """Map ready ids to independent `WorkflowNode`s (no edges — ready nodes' deps are satisfied)."""
    return [
        _wf.WorkflowNode(
            id=tid,
            # Bind tid per-iteration (default arg) so each node builds its OWN prompt.
            build_prompt=(lambda _up, _tid=tid: builder(_tid)),
            cwd=(cwd_for(tid) if cwd_for is not None else None),
        )
        for tid in ids
    ]


def _run_plain(
    ids, *, config, forge_dir, feature, dispatch_fn, build_prompt, cwd_for, cwd,
    claude_bin, resume, force_sequential: bool = False,
) -> "object":
    """Run ready nodes through the engine in one wave (no worktree isolation). `force_sequential`
    pins `max_parallel=1` for the degraded single-worktree path."""
    builder = build_prompt or _default_build_prompt
    nodes = _build_nodes(ids, builder, cwd_for)
    parallel_on = getattr(config, "parallel_build", False) and not force_sequential
    max_parallel = config.max_parallel if parallel_on else 1
    return _wf.run_workflow(
        _wf.WorkflowSpec(nodes=nodes),
        forge_dir=forge_dir,
        feature=feature,
        max_parallel=max_parallel,
        max_total=getattr(config, "max_total", _wf.DEFAULT_MAX_TOTAL),
        max_budget_usd=getattr(config, "max_budget_usd", None),
        resume=resume,
        dispatch_fn=dispatch_fn,
        claude_bin=claude_bin,
        cwd=cwd,
    )


def _run_isolated(
    ids, *, config, forge_dir, feature, dispatch_fn, build_prompt, claude_bin, resume, repo,
) -> "object":
    """Worktree-isolated parallel build (REQ-WF-008). Create one worktree+branch per ready node,
    fan the nodes out through the engine (each dispatching in its own worktree), then **at the
    join** — sequentially, in deterministic id order (git cannot merge two branches into one tree
    concurrently) — commit each completed node and merge its branch back; a conflicting merge
    EXCLUDES that node with a reason (never silent clobber). Every worktree is torn down in a
    `finally`, so teardown happens on success AND on any drop/crash. Never raises."""
    builder = build_prompt or _default_build_prompt

    # Phase 1: create a worktree+branch per node. A node whose worktree can't be created is
    # dropped (degrade) and never dispatched.
    handles: dict = {}          # id -> WorktreeHandle (only successfully-added)
    setup_drops: list = []
    for tid in ids:
        h = _wt.add(repo, tid)
        if h.ok:
            handles[tid] = h
        else:
            setup_drops.append(f"node {tid!r}: worktree add failed: {h.reason}")

    try:
        # Phase 2: fan out — each node dispatches IN ITS OWN worktree (per-node cwd).
        nodes = _build_nodes(
            list(handles), builder, cwd_for=lambda tid: handles[tid].path)
        run = _wf.run_workflow(
            _wf.WorkflowSpec(nodes=nodes),
            forge_dir=forge_dir, feature=feature,
            max_parallel=config.max_parallel,
            max_total=getattr(config, "max_total", _wf.DEFAULT_MAX_TOTAL),
            max_budget_usd=getattr(config, "max_budget_usd", None),
            resume=resume, dispatch_fn=dispatch_fn, claude_bin=claude_bin,
        )

        # Phase 3: join — sequential, deterministic id order. Commit each completed node then
        # merge its branch; a conflict (or commit/merge failure) excludes the node with a reason.
        merged: dict = {}
        join_drops: list = []
        for tid in sorted(run.results):
            h = handles[tid]
            c = _wt.commit(h, message=f"feat({tid}): parallel build")
            if not c.ok:
                join_drops.append(f"node {tid!r}: commit failed: {c.reason}")
                continue
            m = _wt.merge(repo, h)
            if not m.ok:
                kind = "merge conflict" if m.conflict else "merge failed"
                join_drops.append(f"node {tid!r}: {kind}: {m.reason}")
                continue
            merged[tid] = run.results[tid]

        ordered = {tid: merged[tid] for tid in sorted(merged)}
        reasons = list(run.dropped_reasons) + setup_drops + join_drops
        # `dropped` is everything that did not merge: setup drops + engine drops + join drops.
        dropped = len(ids) - len(ordered)
        return _wf.WorkflowResult(
            results=ordered,
            completed=len(ordered),
            dropped=dropped,
            total_cost_usd=run.total_cost_usd,
            dropped_reasons=reasons,
        )
    finally:
        # Lifecycle: tear down EVERY worktree — on success and on any drop/crash (no orphans).
        for h in handles.values():
            _wt.remove(repo, h)
