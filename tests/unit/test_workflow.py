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

_vspec = importlib.util.spec_from_file_location("_verify", _root / "scripts" / "_verify.py")
_verify = importlib.util.module_from_spec(_vspec)
sys.modules["_verify"] = _verify
_vspec.loader.exec_module(_verify)

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


# --------------------------------------------------------------------------- #
# AC-WF-002 — budget/resume plumbed; deterministic budget-aware admission
# --------------------------------------------------------------------------- #


def _spy_dispatch(recorded: list):
    """A dispatch_fn that records the exact kwargs it was called with (for AC-WF-002)."""

    def dispatch(prompt, **kwargs):
        recorded.append({"prompt": prompt, **kwargs})
        return _ok({"prompt": prompt})

    return dispatch


def test_max_budget_usd_and_resume_reach_dispatch() -> None:
    """REQ-NF-027: the budget ceiling and resume token are threaded into every dispatch."""
    recorded: list = []
    res = _wf.run_workflow(
        _diamond(), forge_dir=FORGE, feature="t",
        max_budget_usd=2.5, resume="sess-123",
        dispatch_fn=_spy_dispatch(recorded),
    )
    assert res.completed == 4
    assert len(recorded) == 4  # one dispatch per node, no retries (all succeed)
    for call in recorded:
        assert call["max_budget_usd"] == 2.5
        assert call["resume"] == "sess-123"


def test_budget_defaults_none_when_unset() -> None:
    """Backward-compat: with no budget/resume given, both reach dispatch as None."""
    recorded: list = []
    _wf.run_workflow(_diamond(), forge_dir=FORGE, feature="t",
                     dispatch_fn=_spy_dispatch(recorded))
    assert recorded  # nodes ran
    for call in recorded:
        assert call["max_budget_usd"] is None
        assert call["resume"] is None


def test_budget_exhausted_fanout_drops_deterministic_set() -> None:
    """REQ-NF-029: when max_budget_usd admits only k of N fan-out nodes, the SAME k
    (lowest ids in topological order) are admitted on every run — independent of thread
    scheduling. Per-node admission cost is the fresh-session floor (~$0.06)."""
    floor = _wf.FRESH_FLOOR_USD
    # 10 independent nodes; a budget that affords exactly 3 floors.
    spec = lambda: _wf.WorkflowSpec(  # noqa: E731 — tiny factory for repeated fresh runs
        nodes=[_node(f"n{i:02d}", lambda up: "x") for i in range(10)])
    budget = floor * 3 + floor / 2  # affords 3 nodes, not 4
    runs = [
        _wf.run_workflow(spec(), forge_dir=FORGE, feature="t",
                         max_parallel=8, max_budget_usd=budget, dispatch_fn=_echo_dispatch)
        for _ in range(5)
    ]
    first = set(runs[0].results)
    assert len(first) == 3                      # budget admits exactly 3
    assert first == {"n00", "n01", "n02"}       # deterministic topo-order admission
    for r in runs[1:]:
        assert set(r.results) == first          # identical across repeated runs
    assert any("max_budget_usd" in reason for reason in runs[0].dropped_reasons)


def test_budget_admission_is_independent_of_thread_scheduling() -> None:
    """The deterministic-drop set is identical for parallel and sequential execution."""
    floor = _wf.FRESH_FLOOR_USD
    spec = lambda: _wf.WorkflowSpec(  # noqa: E731
        nodes=[_node(f"n{i:02d}", lambda up: "x") for i in range(8)])
    budget = floor * 2 + floor / 2  # affords exactly 2
    par = _wf.run_workflow(spec(), forge_dir=FORGE, feature="t",
                           max_parallel=8, max_budget_usd=budget, dispatch_fn=_echo_dispatch)
    seq = _wf.run_workflow(spec(), forge_dir=FORGE, feature="t",
                           max_parallel=1, max_budget_usd=budget, dispatch_fn=_echo_dispatch)
    assert set(par.results) == set(seq.results) == {"n00", "n01"}


# --------------------------------------------------------------------------- #
# REQ-WF-001 — WorkflowNode.verify is now Optional[VerifySpec] (wiring lands in T-192)
# --------------------------------------------------------------------------- #


def test_verify_spec_type_and_default() -> None:
    """`verify` defaults to None and accepts a VerifySpec (skill/model/schema)."""
    plain = _wf.WorkflowNode(id="A", build_prompt=lambda up: "A")
    assert plain.verify is None

    vspec = _wf.VerifySpec(skill="/forge:review", model="claude-haiku-4-5-20251001",
                           schema={"type": "object"})
    node = _wf.WorkflowNode(id="B", build_prompt=lambda up: "B", verify=vspec)
    assert node.verify is vspec
    assert node.verify.skill == "/forge:review"
    assert node.verify.model == "claude-haiku-4-5-20251001"
    assert node.verify.schema == {"type": "object"}


def test_verify_spec_defaults() -> None:
    """A VerifySpec needs only a skill; model/schema default to None."""
    vspec = _wf.VerifySpec(skill="/forge:review")
    assert vspec.skill == "/forge:review"
    assert vspec.model is None
    assert vspec.schema is None


# --------------------------------------------------------------------------- #
# REQ-WF-002 / AC-WF-003 — per-node verify wiring (fresh-session verdict; fail ⇒ drop/heal)
# --------------------------------------------------------------------------- #


def _verdict(verdict: str) -> SimpleNamespace:
    """A verifier dispatch envelope carrying a structured verdict JSON in `result`."""
    return SimpleNamespace(status="ok", reason="dispatched",
                           result=json.dumps({"verdict": verdict}), cost_usd=0.003)


def _routing_dispatch(recorded: list, *, verdict: str, verdicts=None):
    """Spy dispatch_fn that routes by prompt: a verifier prompt (contains 'INDEPENDENT
    verifier') returns a verdict envelope; any other prompt is a node dispatch echoing its
    prompt. `verdicts` (a list) supplies successive verdicts (for heal re-verification);
    otherwise every verdict is `verdict`."""
    seq = list(verdicts or [])

    def dispatch(prompt, **kwargs):
        recorded.append({"prompt": prompt, **kwargs})
        if "INDEPENDENT verifier" in prompt:
            v = seq.pop(0) if seq else verdict
            return _verdict(v)
        return _ok({"prompt": prompt})

    return dispatch


def _verify_spec(spec_obj=None) -> "object":
    vspec = spec_obj or _wf.VerifySpec(skill="/forge:review", schema={"type": "object"})
    return _wf.WorkflowSpec(nodes=[
        _wf.WorkflowNode(id="A", build_prompt=lambda up: "do-A", verify=vspec),
    ])


def test_verify_node_dispatches_fresh_session_with_schema() -> None:
    """AC-WF-003: a node with a VerifySpec gets a fresh-session, schema-constrained verdict."""
    recorded: list = []
    res = _wf.run_workflow(
        _verify_spec(), forge_dir=FORGE, feature="t", resume="STAGE-SESSION",
        dispatch_fn=_routing_dispatch(recorded, verdict="pass"),
    )
    assert res.completed == 1
    assert res.results["A"]["prompt"] == "do-A"

    verifier_calls = [c for c in recorded if "INDEPENDENT verifier" in c["prompt"]]
    assert len(verifier_calls) == 1
    vc = verifier_calls[0]
    assert vc["resume"] is None                       # fresh session — independence
    assert vc["output_schema"] == {"type": "object"}  # VerifySpec.schema honored
    # The produced node result is embedded for the verifier to judge.
    assert "do-A" in vc["prompt"]


def test_verify_spec_model_overrides_verifier_model() -> None:
    recorded: list = []
    vspec = _wf.VerifySpec(skill="/forge:review", model="claude-haiku-4-5", schema=None)
    _wf.run_workflow(
        _verify_spec(vspec), forge_dir=FORGE, feature="t",
        dispatch_fn=_routing_dispatch(recorded, verdict="pass"),
    )
    vc = [c for c in recorded if "INDEPENDENT verifier" in c["prompt"]][0]
    assert vc["model"] == "claude-haiku-4-5"
    # VerifySpec.schema is None ⇒ verifier falls back to the shared VERIFY_SCHEMA.
    assert vc["output_schema"] == _verify.VERIFY_SCHEMA


def test_verify_failing_verdict_heals_then_passes() -> None:
    """A failing verdict triggers ONE heal (node re-dispatch + re-verify); a passing re-verify
    keeps the result."""
    recorded: list = []
    res = _wf.run_workflow(
        _verify_spec(), forge_dir=FORGE, feature="t",
        dispatch_fn=_routing_dispatch(recorded, verdict="pass", verdicts=["fail", "pass"]),
    )
    assert res.completed == 1
    assert res.dropped == 0
    node_dispatches = [c for c in recorded if "INDEPENDENT verifier" not in c["prompt"]]
    verifier_calls = [c for c in recorded if "INDEPENDENT verifier" in c["prompt"]]
    assert len(node_dispatches) == 2   # initial + one heal re-dispatch
    assert len(verifier_calls) == 2    # initial verdict + re-verify after heal


def test_verify_persistent_failure_drops_with_reason() -> None:
    """A verdict that fails even after the bounded heal ⇒ node dropped with a reason, never raised."""
    recorded: list = []
    res = _wf.run_workflow(
        _verify_spec(), forge_dir=FORGE, feature="t",
        dispatch_fn=_routing_dispatch(recorded, verdict="fail"),  # always fails
    )
    assert res.completed == 0
    assert res.dropped == 1
    assert "A" not in res.results
    assert any("A" in r and "verify" in r.lower() for r in res.dropped_reasons)


def test_verify_garbage_verdict_degrades_to_pass_never_raises() -> None:
    """A garbage (non-JSON) verdict body must NOT block the node (verifier degrades) — and never
    raises."""
    recorded: list = []

    def dispatch(prompt, **kwargs):
        recorded.append({"prompt": prompt, **kwargs})
        if "INDEPENDENT verifier" in prompt:
            return SimpleNamespace(status="ok", reason="", result="not json at all",
                                   cost_usd=0.001)
        return _ok({"prompt": prompt})

    res = _wf.run_workflow(_verify_spec(), forge_dir=FORGE, feature="t", dispatch_fn=dispatch)
    assert res.completed == 1            # garbage verdict ⇒ not-failed ⇒ node kept
    assert res.results["A"]["prompt"] == "do-A"


def test_unverified_node_never_dispatches_verifier() -> None:
    """No VerifySpec ⇒ no verifier dispatch (opt-in, zero-change default)."""
    recorded: list = []
    _wf.run_workflow(_diamond(), forge_dir=FORGE, feature="t",
                     dispatch_fn=_routing_dispatch(recorded, verdict="fail"))
    assert not any("INDEPENDENT verifier" in c["prompt"] for c in recorded)


# --------------------------------------------------------------------------- #
# REQ-WF-007 / T-196 — per-node `cwd` (each node may run in its own directory/worktree)
# --------------------------------------------------------------------------- #


def test_per_node_cwd_overrides_scalar_cwd() -> None:
    """Each node's dispatch receives its OWN `cwd` when `WorkflowNode.cwd` is set; the scalar
    `run_workflow(cwd=...)` is only the fallback for nodes that don't set one."""
    recorded: list = []
    spec = _wf.WorkflowSpec(nodes=[
        _wf.WorkflowNode(id="A", build_prompt=lambda up: "A", cwd="/wt/A"),
        _wf.WorkflowNode(id="B", build_prompt=lambda up: "B", cwd="/wt/B"),
    ])
    _wf.run_workflow(spec, forge_dir=FORGE, feature="t", cwd="/scalar",
                     dispatch_fn=_spy_dispatch(recorded))
    by_prompt = {c["prompt"]: c for c in recorded}
    assert by_prompt["A"]["cwd"] == "/wt/A"
    assert by_prompt["B"]["cwd"] == "/wt/B"


def test_unset_node_cwd_falls_back_to_scalar() -> None:
    """A node with no `cwd` inherits the scalar `run_workflow(cwd=...)` — backward compatible
    with every existing caller (which passes only the scalar)."""
    recorded: list = []
    spec = _wf.WorkflowSpec(nodes=[
        _wf.WorkflowNode(id="A", build_prompt=lambda up: "A"),               # unset
        _wf.WorkflowNode(id="B", build_prompt=lambda up: "B", cwd="/wt/B"),  # set
    ])
    _wf.run_workflow(spec, forge_dir=FORGE, feature="t", cwd="/scalar",
                     dispatch_fn=_spy_dispatch(recorded))
    by_prompt = {c["prompt"]: c for c in recorded}
    assert by_prompt["A"]["cwd"] == "/scalar"   # fell back to the scalar
    assert by_prompt["B"]["cwd"] == "/wt/B"


def test_node_cwd_defaults_none_and_inherits_none_scalar() -> None:
    """With neither a node cwd nor a scalar cwd, dispatch still gets `cwd=None` (today's default)."""
    plain = _wf.WorkflowNode(id="A", build_prompt=lambda up: "A")
    assert plain.cwd is None
    recorded: list = []
    _wf.run_workflow(_diamond(), forge_dir=FORGE, feature="t",
                     dispatch_fn=_spy_dispatch(recorded))
    assert all(c["cwd"] is None for c in recorded)


# --------------------------------------------------------------------------- #
# REQ-WF-010 / T-199 / AC-WF-010 — validated sub-DAG generation (`decompose` node)
#
# A `decompose` node's dispatch is a cheap-model, schema-constrained LLM call that emits a
# sub-DAG (a JSON node/edge list). Before ANY generated child node dispatches, the sub-DAG is
# run through `validate_spec` (cycle/dup/unknown) PLUS a node-count cap PLUS a deterministic
# token-budget proxy (`len(json) // 4`). Any violation ⇒ drop-with-reason + deterministic
# fallback; generation never escapes this validated slot. Gated by `allow_generated_subdags`
# (off by default) — when off the decompose node behaves as a plain node (no generation).
# --------------------------------------------------------------------------- #


def _subdag_json(node_ids, edges=None) -> str:
    """Render a sub-DAG the shape a `decompose` generation call would emit: a JSON object
    with a `nodes` list (each `{id, prompt, depends_on}`)."""
    edges = edges or {}
    return json.dumps({"nodes": [
        {"id": nid, "prompt": f"do-{nid}", "depends_on": edges.get(nid, [])}
        for nid in node_ids
    ]})


def _decompose_dispatch(recorded: list, *, subdag: str):
    """Spy dispatch_fn that routes by prompt: the decompose generation prompt (contains
    'DECOMPOSE') returns the supplied sub-DAG JSON; child/plain prompts echo themselves.
    Records every call so we can assert which (if any) children dispatched."""

    def dispatch(prompt, **kwargs):
        recorded.append({"prompt": prompt, **kwargs})
        if "DECOMPOSE" in prompt:
            return SimpleNamespace(status="ok", reason="dispatched", result=subdag,
                                   cost_usd=0.005, raw={"is_error": False})
        return _ok({"prompt": prompt})

    return dispatch


def _child_prompts(recorded: list) -> list:
    """The prompts of generated-child dispatches (everything that isn't the generation call)."""
    return [c["prompt"] for c in recorded if "DECOMPOSE" not in c["prompt"]]


def _decompose_spec(dspec) -> "object":
    return _wf.WorkflowSpec(nodes=[
        _wf.WorkflowNode(id="root", build_prompt=lambda up: "DECOMPOSE: split the work",
                         decompose=dspec),
    ])


def _dspec(*, max_nodes=8, max_chars=4096, schema=None, model=None):
    """A DecomposeSpec wiring a sub-DAG JSON into child WorkflowNodes, with a deterministic
    fallback that records that it ran (a single 'fallback' node)."""
    def parse(subdag: dict) -> list:
        return [
            _wf.WorkflowNode(id=n["id"], build_prompt=(lambda p: lambda up: p)(n["prompt"]),
                             depends_on=list(n.get("depends_on") or []))
            for n in (subdag.get("nodes") or [])
        ]

    fallback = [_wf.WorkflowNode(id="fallback", build_prompt=lambda up: "fallback")]
    return _wf.DecomposeSpec(parse_subdag=parse, fallback=fallback,
                             max_nodes=max_nodes, max_chars=max_chars,
                             schema=schema, model=model)


def test_decompose_spec_type_and_defaults() -> None:
    """`decompose` defaults to None; a DecomposeSpec needs a parser + fallback; caps default."""
    plain = _wf.WorkflowNode(id="A", build_prompt=lambda up: "A")
    assert plain.decompose is None

    dspec = _dspec()
    node = _wf.WorkflowNode(id="root", build_prompt=lambda up: "x", decompose=dspec)
    assert node.decompose is dspec
    assert dspec.max_nodes == 8
    assert dspec.max_chars == 4096


def test_decompose_off_by_default_is_inert_no_generation() -> None:
    """`allow_generated_subdags` defaults OFF: the decompose node never runs the generation slot
    and never spawns children — it behaves as a plain node (its raw build_prompt is dispatched
    once, with NO schema-hint suffix, and the reply is treated as a leaf result)."""
    recorded: list = []
    spec = _decompose_spec(_dspec())
    res = _wf.run_workflow(spec, forge_dir=FORGE, feature="t",
                           dispatch_fn=_decompose_dispatch(recorded, subdag=_subdag_json(["x"])))
    # Exactly one dispatch — the plain node — with the raw prompt (no generation schema hint).
    assert len(recorded) == 1
    assert recorded[0]["prompt"] == "DECOMPOSE: split the work"
    assert _wf._DECOMPOSE_SCHEMA_HINT not in recorded[0]["prompt"]
    # No children/fallback ran; the root's result is the echoed leaf, not a {"children": ...} dict.
    assert "root" in res.results
    assert "children" not in res.results["root"]


def test_decompose_admits_valid_subdag_and_runs_children() -> None:
    """With the toggle ON and a valid sub-DAG, children are generated, validated, and run; the
    generation call uses the cheap model + schema."""
    recorded: list = []
    schema = {"type": "object"}
    spec = _decompose_spec(_dspec(model="claude-haiku-4-5", schema=schema))
    subdag = _subdag_json(["c1", "c2"], edges={"c2": ["c1"]})
    res = _wf.run_workflow(
        spec, forge_dir=FORGE, feature="t", allow_generated_subdags=True,
        dispatch_fn=_decompose_dispatch(recorded, subdag=subdag),
    )
    # The generation call used the DecomposeSpec model + schema (cheap, schema-constrained).
    gen = [c for c in recorded if "DECOMPOSE" in c["prompt"]][0]
    assert gen["model"] == "claude-haiku-4-5"
    assert gen["output_schema"] == schema
    # Both validated children dispatched and produced results.
    assert set(_child_prompts(recorded)) == {"do-c1", "do-c2"}
    assert res.results["root"]["children"] == {"c1": {"prompt": "do-c1"},
                                               "c2": {"prompt": "do-c2"}}
    # The deterministic fallback did NOT run (valid sub-DAG admitted).
    assert "fallback" not in _child_prompts(recorded)


def test_decompose_cyclic_subdag_rejected_before_any_child_dispatch() -> None:
    """AC-WF-010: a generated sub-DAG containing a CYCLE is rejected before any child dispatches;
    the deterministic fallback runs instead."""
    recorded: list = []
    spec = _decompose_spec(_dspec())
    cyclic = _subdag_json(["a", "b"], edges={"a": ["b"], "b": ["a"]})
    res = _wf.run_workflow(
        spec, forge_dir=FORGE, feature="t", allow_generated_subdags=True,
        dispatch_fn=_decompose_dispatch(recorded, subdag=cyclic),
    )
    # ZERO generated children dispatched — only the fallback ran.
    assert "do-a" not in _child_prompts(recorded)
    assert "do-b" not in _child_prompts(recorded)
    assert "fallback" in _child_prompts(recorded)
    assert any("root" in r and "cycle" in r.lower() for r in res.dropped_reasons)


def test_decompose_malformed_parser_output_runs_fallback_never_raises() -> None:
    """REQ-WF-010 robustness: if the author's `parse_subdag` returns malformed nodes (objects
    lacking `.id`), admission (`validate_spec`) raises while dereferencing `n.id`. That must be
    caught inside the generation slot and routed to the deterministic fallback — NOT escape to
    the worker guard with no fallback (which would drop the node to `{}`). Zero generated
    children dispatch; the fallback runs; nothing raises."""
    recorded: list = []

    def bad_parse(subdag: dict) -> list:
        # Returns objects WITHOUT an `.id` attribute → validate_spec dereferences n.id and raises.
        return [SimpleNamespace(build_prompt=lambda up: "x", depends_on=[])]

    fallback = [_wf.WorkflowNode(id="fallback", build_prompt=lambda up: "fallback")]
    dspec = _wf.DecomposeSpec(parse_subdag=bad_parse, fallback=fallback,
                              max_nodes=8, max_chars=4096)
    spec = _decompose_spec(dspec)
    res = _wf.run_workflow(
        spec, forge_dir=FORGE, feature="t", allow_generated_subdags=True,
        dispatch_fn=_decompose_dispatch(recorded, subdag=_subdag_json(["a", "b"])),
    )
    # The malformed generated set never dispatched; the deterministic fallback ran instead.
    assert "do-a" not in _child_prompts(recorded)
    assert "fallback" in _child_prompts(recorded)
    assert any("root" in r and "parse failed" in r.lower() for r in res.dropped_reasons)


def test_decompose_over_node_count_rejected_before_any_child_dispatch() -> None:
    """AC-WF-010: a generated sub-DAG exceeding the node-count cap is rejected before any child
    dispatch; the fallback runs."""
    recorded: list = []
    spec = _decompose_spec(_dspec(max_nodes=2))
    too_many = _subdag_json(["n0", "n1", "n2"])  # 3 > cap of 2
    res = _wf.run_workflow(
        spec, forge_dir=FORGE, feature="t", allow_generated_subdags=True,
        dispatch_fn=_decompose_dispatch(recorded, subdag=too_many),
    )
    assert not any(p.startswith("do-n") for p in _child_prompts(recorded))
    assert "fallback" in _child_prompts(recorded)
    assert any("root" in r and "node" in r.lower() for r in res.dropped_reasons)


def test_decompose_over_token_proxy_rejected_before_any_child_dispatch() -> None:
    """AC-WF-010: a generated sub-DAG exceeding the token-proxy budget (`len(json)//4`) is
    rejected before any child dispatch; the fallback runs."""
    recorded: list = []
    subdag = _subdag_json(["c1", "c2"])
    tiny_budget = len(subdag) // 4 - 1  # one below the proxy of this exact JSON ⇒ over-budget
    spec = _decompose_spec(_dspec(max_chars=tiny_budget * 4))  # max_chars below len(subdag)
    res = _wf.run_workflow(
        spec, forge_dir=FORGE, feature="t", allow_generated_subdags=True,
        dispatch_fn=_decompose_dispatch(recorded, subdag=subdag),
    )
    assert not any(p.startswith("do-c") for p in _child_prompts(recorded))
    assert "fallback" in _child_prompts(recorded)
    assert any("root" in r and "token" in r.lower() for r in res.dropped_reasons)


def test_decompose_token_proxy_is_deterministic_pure_function() -> None:
    """The token-proxy is a pure function of the JSON string: `len(s)//4`, no imports."""
    s = _subdag_json(["x", "y", "z"])
    assert _wf._token_proxy(s) == len(s) // 4
    assert _wf._token_proxy(s) == _wf._token_proxy(s)  # deterministic
    assert _wf._token_proxy("") == 0


def test_decompose_admission_is_deterministic_same_json_same_outcome() -> None:
    """Same generated JSON ⇒ same accept/reject + same children, every run (determinism)."""
    subdag = _subdag_json(["c1", "c2", "c3"], edges={"c3": ["c1", "c2"]})
    runs = []
    for _ in range(4):
        recorded: list = []
        res = _wf.run_workflow(
            _decompose_spec(_dspec()), forge_dir=FORGE, feature="t",
            allow_generated_subdags=True,
            dispatch_fn=_decompose_dispatch(recorded, subdag=subdag),
        )
        runs.append((sorted(res.results.get("root", {}).get("children", {})),
                     "fallback" in _child_prompts(recorded)))
    assert all(r == runs[0] for r in runs)
    assert runs[0] == (["c1", "c2", "c3"], False)  # all admitted, no fallback


def test_decompose_garbage_generation_falls_back_never_raises() -> None:
    """Garbage / non-JSON generation output ⇒ deterministic fallback, never raises."""
    recorded: list = []

    def dispatch(prompt, **kwargs):
        recorded.append({"prompt": prompt, **kwargs})
        if "DECOMPOSE" in prompt:
            return SimpleNamespace(status="ok", reason="", result="not json at all{{",
                                   cost_usd=0.005, raw={"is_error": False})
        return _ok({"prompt": prompt})

    res = _wf.run_workflow(
        _decompose_spec(_dspec()), forge_dir=FORGE, feature="t",
        allow_generated_subdags=True, dispatch_fn=dispatch,
    )
    assert "fallback" in _child_prompts(recorded)
    assert any("root" in r for r in res.dropped_reasons)
    # Never raised: a structured result came back.
    assert isinstance(res, _wf.WorkflowResult)


def test_decompose_generation_dispatch_failure_falls_back() -> None:
    """A failed generation dispatch (status != ok) ⇒ fallback, no child dispatch, never raises."""
    recorded: list = []

    def dispatch(prompt, **kwargs):
        recorded.append({"prompt": prompt, **kwargs})
        if "DECOMPOSE" in prompt:
            return SimpleNamespace(status="error", reason="boom", result=None, cost_usd=0.0)
        return _ok({"prompt": prompt})

    res = _wf.run_workflow(
        _decompose_spec(_dspec()), forge_dir=FORGE, feature="t",
        allow_generated_subdags=True, dispatch_fn=dispatch,
    )
    assert "fallback" in _child_prompts(recorded)
    assert isinstance(res, _wf.WorkflowResult)


# --------------------------------------------------------------------------- #
# T-202 (REQ-WF-011, AC-WF-012) — live stderr narration; stdout byte-identical
# --------------------------------------------------------------------------- #
import io  # noqa: E402
import contextlib  # noqa: E402


def _capture_run(spec, *, dispatch_fn, forge_dir=FORGE, **kw):
    """Run a workflow capturing (stdout, stderr) text. Narration must be stderr-only."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        res = _wf.run_workflow(spec, forge_dir=forge_dir, feature="t",
                               dispatch_fn=dispatch_fn, **kw)
    return res, out.getvalue(), err.getvalue()


def test_narration_emits_waves_nodes_and_summary_on_stderr(monkeypatch):
    monkeypatch.delenv("FORGE_WF_QUIET", raising=False)
    res, out, err = _capture_run(_diamond(), dispatch_fn=_echo_dispatch)
    assert res.completed == 4
    # Per-node start + done lines for each node on stderr.
    for nid in ("A", "B", "C", "D"):
        assert f"node '{nid}': start" in err
        assert f"node '{nid}': done" in err
    # Wave header present.
    assert "wave 1/" in err
    # Final id-ordered summary block.
    assert "completed:[A, B, C, D]" in err
    assert "total $" in err
    # stdout untouched by narration.
    assert out == ""


def test_narration_summary_is_deterministic(monkeypatch):
    monkeypatch.delenv("FORGE_WF_QUIET", raising=False)
    _, _, err1 = _capture_run(_diamond(), dispatch_fn=_echo_dispatch)
    _, _, err2 = _capture_run(_diamond(), dispatch_fn=_echo_dispatch)
    line1 = [l for l in err1.splitlines() if "completed:[" in l]
    line2 = [l for l in err2.splitlines() if "completed:[" in l]
    assert line1 == line2 and line1  # identical summary block across runs


def test_stdout_byte_identical_narration_on_vs_off(monkeypatch):
    monkeypatch.delenv("FORGE_WF_QUIET", raising=False)
    _, out_on, err_on = _capture_run(_diamond(), dispatch_fn=_echo_dispatch)
    monkeypatch.setenv("FORGE_WF_QUIET", "1")
    _, out_off, err_off = _capture_run(_diamond(), dispatch_fn=_echo_dispatch)
    assert out_on == out_off  # stdout byte-identical
    assert err_on != ""       # narration present when on
    assert err_off == ""      # silenced when off


def test_narration_silenced_by_quiet_env(monkeypatch):
    monkeypatch.setenv("FORGE_WF_QUIET", "1")
    _, out, err = _capture_run(_diamond(), dispatch_fn=_echo_dispatch)
    assert err == ""


def test_narration_silenced_by_config_false(tmp_path, monkeypatch):
    monkeypatch.delenv("FORGE_WF_QUIET", raising=False)
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    (forge / "config.yaml").write_text("orchestration:\n  narrate: false\n")
    _, out, err = _capture_run(_diamond(), dispatch_fn=_echo_dispatch, forge_dir=forge)
    assert err == ""


def test_narration_reports_dropped_node_with_reason(monkeypatch):
    monkeypatch.delenv("FORGE_WF_QUIET", raising=False)

    def dispatch(prompt, **kwargs):
        if prompt == "A":
            return SimpleNamespace(status="error", reason="boom", result=None, cost_usd=0.0)
        return _ok({"prompt": prompt})

    spec = _wf.WorkflowSpec(nodes=[_node("A", lambda up: "A")])
    _, out, err = _capture_run(spec, dispatch_fn=dispatch)
    assert "dropped:" in err
    assert "A" in err
    assert out == ""


def test_narration_failure_degrades_to_silence(monkeypatch):
    """A forced narration write error degrades to silence — never raises into the engine."""
    monkeypatch.delenv("FORGE_WF_QUIET", raising=False)

    class _Boom(io.StringIO):
        def write(self, *a, **k):
            raise RuntimeError("stderr is broken")

    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(_Boom()):
        res = _wf.run_workflow(_diamond(), forge_dir=FORGE, feature="t",
                               dispatch_fn=_echo_dispatch)
    # The run still completed and returned a structured result.
    assert res.completed == 4
