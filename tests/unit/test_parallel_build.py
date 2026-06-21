"""Tests for scripts/parallel_build.py (v0.4.0 T-196 — per-stage parallel build fan-out).

The parallel-build helper maps *ready* task-DAG nodes (those whose `depends_on` are all already
done) to a `WorkflowSpec` and runs them through the engine: in parallel when the `parallel_build`
toggle is on, sequentially (max_parallel=1) when off. A fake dispatch_fn is injected — no real
claude / subprocess is touched. Per-node `cwd` (T-196) lets each node run in its own directory.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

_root = Path(__file__).resolve().parent.parent.parent

_vspec = importlib.util.spec_from_file_location("_verify", _root / "scripts" / "_verify.py")
_verify = importlib.util.module_from_spec(_vspec)
sys.modules["_verify"] = _verify
_vspec.loader.exec_module(_verify)

_wspec = importlib.util.spec_from_file_location("_workflow", _root / "scripts" / "_workflow.py")
_wf = importlib.util.module_from_spec(_wspec)
sys.modules["_workflow"] = _wf
_wspec.loader.exec_module(_wf)

_cspec = importlib.util.spec_from_file_location(
    "_workflow_config", _root / "scripts" / "_workflow_config.py")
_cfg = importlib.util.module_from_spec(_cspec)
sys.modules["_workflow_config"] = _cfg
_cspec.loader.exec_module(_cfg)

_pspec = importlib.util.spec_from_file_location(
    "parallel_build", _root / "scripts" / "parallel_build.py")
_pb = importlib.util.module_from_spec(_pspec)
sys.modules["parallel_build"] = _pb
_pspec.loader.exec_module(_pb)

FORGE = Path("/tmp/does-not-matter")  # fake dispatch ignores it


def _ok(result_obj: dict, cost: float = 0.01) -> SimpleNamespace:
    return SimpleNamespace(status="ok", result=json.dumps(result_obj),
                           cost_usd=cost, raw={"is_error": False})


def _echo_dispatch(prompt, **kwargs):
    return _ok({"prompt": prompt, "cwd": kwargs.get("cwd")})


def _spy_dispatch(recorded: list):
    def dispatch(prompt, **kwargs):
        recorded.append({"prompt": prompt, **kwargs})
        return _ok({"prompt": prompt})
    return dispatch


def _task(tid, deps=None):
    return _pb.TaskNode(id=tid, depends_on=deps or [])


# --------------------------------------------------------------------------- #
# ready_nodes — only tasks whose deps are all done are ready
# --------------------------------------------------------------------------- #


def test_ready_nodes_filters_by_unmet_deps() -> None:
    tasks = [_task("T1"), _task("T2"), _task("T3", ["T1"]), _task("T4", ["T1", "T2"])]
    assert _pb.ready_nodes(tasks, done=set()) == ["T1", "T2"]
    assert _pb.ready_nodes(tasks, done={"T1"}) == ["T2", "T3"]
    # T1/T2 done ⇒ excluded; T3 (dep T1) and T4 (deps T1,T2) are now ready.
    assert _pb.ready_nodes(tasks, done={"T1", "T2"}) == ["T3", "T4"]


def test_ready_nodes_excludes_already_done() -> None:
    """A task already in `done` is not 'ready to run' — it is finished."""
    tasks = [_task("T1"), _task("T2", ["T1"])]
    assert _pb.ready_nodes(tasks, done={"T1"}) == ["T2"]
    assert _pb.ready_nodes(tasks, done={"T1", "T2"}) == []


def test_ready_nodes_sorted_deterministic() -> None:
    tasks = [_task("T9"), _task("T1"), _task("T5")]
    assert _pb.ready_nodes(tasks, done=set()) == ["T1", "T5", "T9"]


# --------------------------------------------------------------------------- #
# AC-WF-007 — toggle on ⇒ N ready nodes fan out in parallel with per-node cwd
# --------------------------------------------------------------------------- #


def test_parallel_on_fans_out_ready_nodes() -> None:
    cfg = _cfg.OrchestrationConfig(parallel_build=True, max_parallel=4)
    tasks = [_task("T1"), _task("T2"), _task("T3", ["T1"])]  # T3 not ready
    recorded: list = []
    res = _pb.run_parallel_build(
        tasks, done=set(), config=cfg, forge_dir=FORGE, feature="t",
        dispatch_fn=_spy_dispatch(recorded),
    )
    assert res.completed == 2                       # only the two ready nodes ran
    assert set(res.results) == {"T1", "T2"}
    assert "T3" not in res.results                  # unmet dependency ⇒ not dispatched
    assert len(recorded) == 2


def test_parallel_per_node_cwd_applied() -> None:
    """Each fanned-out node dispatches in its OWN cwd via the `cwd_for` mapping (the seam T-197
    uses to hand each node its worktree)."""
    cfg = _cfg.OrchestrationConfig(parallel_build=True, max_parallel=4)
    tasks = [_task("T1"), _task("T2")]
    recorded: list = []
    _pb.run_parallel_build(
        tasks, done=set(), config=cfg, forge_dir=FORGE, feature="t",
        dispatch_fn=_spy_dispatch(recorded),
        cwd_for=lambda tid: f"/wt/{tid}",
    )
    by_prompt = {c["cwd"] for c in recorded}
    assert by_prompt == {"/wt/T1", "/wt/T2"}


def test_parallel_threads_max_parallel_and_budget() -> None:
    """Engine tunables from the config (max_parallel/max_total/max_budget_usd) reach run_workflow;
    the budget ceiling is threaded into every dispatch."""
    cfg = _cfg.OrchestrationConfig(parallel_build=True, max_parallel=2, max_budget_usd=5.0)
    tasks = [_task(f"T{i}") for i in range(3)]
    recorded: list = []
    _pb.run_parallel_build(
        tasks, done=set(), config=cfg, forge_dir=FORGE, feature="t",
        dispatch_fn=_spy_dispatch(recorded),
    )
    assert recorded
    for c in recorded:
        assert c["max_budget_usd"] == 5.0


# --------------------------------------------------------------------------- #
# AC-WF-007 — toggle off ⇒ today's sequential behavior (max_parallel == 1)
# --------------------------------------------------------------------------- #


def test_parallel_off_runs_sequential() -> None:
    """With `parallel_build` off, ready nodes still run (the engine is always on) but the result
    is the SAME as a parallel run — byte-identical engine result (REQ-NF-026a)."""
    tasks = [_task("T1"), _task("T2"), _task("T3")]
    off = _pb.run_parallel_build(
        tasks, done=set(), config=_cfg.OrchestrationConfig(parallel_build=False),
        forge_dir=FORGE, feature="t", dispatch_fn=_echo_dispatch)
    on = _pb.run_parallel_build(
        tasks, done=set(), config=_cfg.OrchestrationConfig(parallel_build=True, max_parallel=8),
        forge_dir=FORGE, feature="t", dispatch_fn=_echo_dispatch)
    assert off.completed == on.completed == 3
    assert json.dumps(off.results, sort_keys=True) == json.dumps(on.results, sort_keys=True)


def test_parallel_off_uses_single_worker() -> None:
    """The off path runs the engine with max_parallel=1 (sequential), the documented degrade."""
    captured: dict = {}
    real_run = _wf.run_workflow

    def spy_run(spec, **kwargs):
        captured["max_parallel"] = kwargs.get("max_parallel")
        return real_run(spec, **kwargs)

    _pb._wf.run_workflow = spy_run
    try:
        _pb.run_parallel_build(
            [_task("T1")], done=set(),
            config=_cfg.OrchestrationConfig(parallel_build=False),
            forge_dir=FORGE, feature="t", dispatch_fn=_echo_dispatch)
        assert captured["max_parallel"] == 1
    finally:
        _pb._wf.run_workflow = real_run


# --------------------------------------------------------------------------- #
# never-raises + empty input
# --------------------------------------------------------------------------- #


def test_no_ready_nodes_is_noop() -> None:
    """No ready nodes (all blocked or all done) ⇒ an empty, non-raising result with no dispatch."""
    recorded: list = []
    res = _pb.run_parallel_build(
        [_task("T2", ["T1"])], done=set(),  # T2 blocked on undone T1
        config=_cfg.OrchestrationConfig(parallel_build=True),
        forge_dir=FORGE, feature="t", dispatch_fn=_spy_dispatch(recorded))
    assert res.completed == 0
    assert recorded == []


def test_default_build_prompt_mentions_task_id() -> None:
    """The default per-task build prompt embeds the task id so the agent knows which task to build."""
    cfg = _cfg.OrchestrationConfig(parallel_build=True)
    recorded: list = []
    _pb.run_parallel_build(
        [_task("T42")], done=set(), config=cfg, forge_dir=FORGE, feature="t",
        dispatch_fn=_spy_dispatch(recorded))
    assert any("T42" in c["prompt"] for c in recorded)
