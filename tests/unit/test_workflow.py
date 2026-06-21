"""Tests for scripts/_workflow.py (v0.4.0 spike — dynamic workflow DAG engine).

The workflow engine generalizes `_orchestrate.fan_out` from a flat homogeneous parallel
map to an arbitrary DAG of heterogeneous agent steps: per-node prompt/schema/model,
`depends_on` edges, inter-step data passing, dependency-wave scheduling, bounded parallel
fan-out per wave, retry-once-then-drop, and byte-identical parallel/sequential output.
A fake dispatch_fn is injected — no real claude / subprocess is touched.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

_root = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location("_workflow", _root / "scripts" / "_workflow.py")
_wf = importlib.util.module_from_spec(_spec)
sys.modules["_workflow"] = _wf
_spec.loader.exec_module(_wf)

FORGE = Path("/tmp/does-not-matter")  # fake dispatch ignores it


def _ok(result_obj: dict, cost: float = 0.01) -> SimpleNamespace:
    return SimpleNamespace(status="ok", result=json.dumps(result_obj),
                           cost_usd=cost, raw={"is_error": False})


def _echo_dispatch(prompt, *, forge_dir, feature, model=None, output_schema=None,
                   resume=None, claude_bin=None, cwd=None, **kw):
    """Fake: echoes the prompt back so data-flow through the DAG is observable."""
    return _ok({"prompt": prompt})


def _node(nid, build_prompt, depends_on=None):
    return _wf.WorkflowNode(id=nid, build_prompt=build_prompt, depends_on=depends_on or [])


def _diamond() -> "object":
    """A -> (B, C) -> D. Each node's prompt encodes its upstream, so the echoed
    result lets us assert exact data-flow."""
    return _wf.WorkflowSpec(nodes=[
        _node("A", lambda up: "A"),
        _node("B", lambda up: f"B(from {up['A']['prompt']})", ["A"]),
        _node("C", lambda up: f"C(from {up['A']['prompt']})", ["A"]),
        _node("D", lambda up: f"D(from {up['B']['prompt']}+{up['C']['prompt']})", ["B", "C"]),
    ])


def test_diamond_dag_waves_and_data_passing() -> None:
    spec = _diamond()
    # Wave grouping is deterministic: A alone, then B+C together, then D.
    assert _wf.plan_waves(spec) == [["A"], ["B", "C"], ["D"]]

    res = _wf.run_workflow(spec, forge_dir=FORGE, feature="t",
                           max_parallel=4, dispatch_fn=_echo_dispatch)
    assert res.completed == 4
    assert res.dropped == 0
    assert set(res.results) == {"A", "B", "C", "D"}
    # Data passed along every edge: A -> B/C -> D.
    assert res.results["B"]["prompt"] == "B(from A)"
    assert res.results["D"]["prompt"] == "D(from B(from A)+C(from A))"


def test_parallel_equals_sequential_byte_identical() -> None:
    par = _wf.run_workflow(_diamond(), forge_dir=FORGE, feature="t",
                           max_parallel=8, dispatch_fn=_echo_dispatch)
    seq = _wf.run_workflow(_diamond(), forge_dir=FORGE, feature="t",
                           max_parallel=1, dispatch_fn=_echo_dispatch)
    assert par == seq  # dataclass equality
    assert json.dumps(par.results, sort_keys=False) == json.dumps(seq.results, sort_keys=False)


def test_cycle_and_unknown_dep_rejected_no_dispatch() -> None:
    calls: list[str] = []

    def recording(prompt, **kw):
        calls.append(prompt)
        return _ok({"prompt": prompt})

    cyclic = _wf.WorkflowSpec(nodes=[
        _node("A", lambda up: "A", ["B"]),
        _node("B", lambda up: "B", ["A"]),
    ])
    errs = _wf.validate_spec(cyclic)
    assert any("cycle" in e.lower() for e in errs)
    res = _wf.run_workflow(cyclic, forge_dir=FORGE, feature="t", dispatch_fn=recording)
    assert res.completed == 0
    assert calls == []                      # invalid spec dispatches nothing
    assert res.dropped_reasons             # not silent

    unknown = _wf.WorkflowSpec(nodes=[_node("A", lambda up: "A", ["Z"])])
    errs2 = _wf.validate_spec(unknown)
    assert any("unknown" in e.lower() and "Z" in e for e in errs2)


def test_failure_isolation_drops_dependents_never_raises() -> None:
    def flaky(prompt, **kw):
        if prompt == "A":
            raise RuntimeError("boom")          # A always fails
        return _ok({"prompt": prompt})

    spec = _wf.WorkflowSpec(nodes=[
        _node("A", lambda up: "A"),
        _node("B", lambda up: "B", ["A"]),      # depends on failing A
        _node("C", lambda up: "C"),             # independent
    ])
    res = _wf.run_workflow(spec, forge_dir=FORGE, feature="t", dispatch_fn=flaky)
    assert set(res.results) == {"C"}            # only the independent branch survives
    assert res.completed == 1
    assert res.dropped == 2
    assert any("A" in r for r in res.dropped_reasons)   # A dropped (dispatch failed)
    assert any("B" in r for r in res.dropped_reasons)   # B skipped (dep dropped)


def test_max_total_cap_drops_overflow_not_silent() -> None:
    spec = _wf.WorkflowSpec(nodes=[_node(f"n{i}", lambda up: "x") for i in range(5)])
    res = _wf.run_workflow(spec, forge_dir=FORGE, feature="t",
                           max_total=3, dispatch_fn=_echo_dispatch)
    assert res.completed == 3
    assert res.dropped == 2
    assert any("max_total" in r for r in res.dropped_reasons)
