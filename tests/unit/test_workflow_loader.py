"""Tests for scripts/workflow_loader.py (v0.4.0, REQ-WF-005).

The loader parses a declarative `.forge/workflows/*.yaml` file into the in-memory
`WorkflowSpec` that `_workflow.run_workflow` executes: each node's `prompt` /
`prompt_template` compiles to a `build_prompt`, `{{upstream_id}}` interpolation
threads validated upstream results into downstream prompts, and the assembled spec
is run through `validate_spec`. The contract under test is fail-soft (REQ-NF-024):
a missing file, malformed YAML, or an invalid structure yields a structured
`LoadResult(spec=None, errors=[...])` and the loader **never raises**.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_root = Path(__file__).resolve().parent.parent.parent

# The loader imports `_workflow`, which itself imports `_verify` and
# `_background_agent`; loading the loader as a named module is enough — its own
# `sys.path.insert` resolves the engine. Register under the file's stem.
_spec = importlib.util.spec_from_file_location(
    "workflow_loader", _root / "scripts" / "workflow_loader.py"
)
_loader = importlib.util.module_from_spec(_spec)
sys.modules["workflow_loader"] = _loader
_spec.loader.exec_module(_loader)

_wf = _loader._workflow


SAMPLE_YAML = """\
name: sample-flow
description: A two-stage research-then-write flow for the loader test.
nodes:
  - id: research
    prompt: "Research the topic and return JSON {\\"findings\\": []}"
  - id: write
    depends_on: [research]
    prompt_template: "Draft a summary from these findings: {{research}}"
    schema: {type: object}
    model: claude-haiku-4-5
"""


def _write(tmp_path: Path, text: str, name: str = "flow.yaml") -> Path:
    p = tmp_path / name
    p.write_text(text)
    return p


# --- happy path: a sample YAML loads into a spec validate_spec accepts ----------

def test_sample_yaml_loads_into_valid_spec(tmp_path):
    res = _loader.load_workflow_file(_write(tmp_path, SAMPLE_YAML))
    assert res.ok, res.errors
    assert res.name == "sample-flow"
    assert res.description.startswith("A two-stage")
    assert isinstance(res.spec, _wf.WorkflowSpec)
    assert [n.id for n in res.spec.nodes] == ["research", "write"]
    # validate_spec independently accepts the assembled spec.
    assert _wf.validate_spec(res.spec) == []
    # plan_waves reflects the declared dependency.
    assert _wf.plan_waves(res.spec) == [["research"], ["write"]]


def test_node_attributes_compiled(tmp_path):
    res = _loader.load_workflow_file(_write(tmp_path, SAMPLE_YAML))
    write = {n.id: n for n in res.spec.nodes}["write"]
    assert write.depends_on == ["research"]
    assert write.output_schema == {"type": "object"}
    assert write.model == "claude-haiku-4-5"


# --- prompt_template {{upstream}} interpolation ---------------------------------

def test_prompt_template_interpolates_upstream(tmp_path):
    res = _loader.load_workflow_file(_write(tmp_path, SAMPLE_YAML))
    write = {n.id: n for n in res.spec.nodes}["write"]
    out = write.build_prompt({"research": {"findings": ["x"]}})
    assert "Draft a summary from these findings:" in out
    assert "findings" in out and "x" in out


def test_literal_prompt_is_constant(tmp_path):
    res = _loader.load_workflow_file(_write(tmp_path, SAMPLE_YAML))
    research = {n.id: n for n in res.spec.nodes}["research"]
    # No upstream, no template tokens → identical regardless of input.
    assert research.build_prompt({}) == research.build_prompt({"ignored": 1})
    assert "Research the topic" in research.build_prompt({})


def test_unknown_token_left_verbatim(tmp_path):
    text = """\
name: t
nodes:
  - id: a
    prompt_template: "value is {{missing}} end"
"""
    res = _loader.load_workflow_file(_write(tmp_path, text))
    assert res.ok, res.errors
    a = res.spec.nodes[0]
    # An unresolved token is left untouched (no KeyError), visible to the agent.
    assert a.build_prompt({}) == "value is {{missing}} end"


def test_untrusted_upstream_with_braces_does_not_break(tmp_path):
    text = """\
name: t
nodes:
  - id: up
    prompt: "produce"
  - id: down
    depends_on: [up]
    prompt_template: "got: {{up}}"
"""
    res = _loader.load_workflow_file(_write(tmp_path, text))
    down = {n.id: n for n in res.spec.nodes}["down"]
    # Upstream output containing format-spec-looking braces is spliced literally.
    hostile = "{0} {name} {{nested}}"
    assert down.build_prompt({"up": hostile}) == f"got: {hostile}"


# --- fail-soft: missing / malformed YAML ---------------------------------------

def test_missing_file_fails_soft(tmp_path):
    res = _loader.load_workflow_file(tmp_path / "nope.yaml")
    assert res.spec is None
    assert res.errors
    assert any("not found" in e for e in res.errors)


def test_malformed_yaml_fails_soft(tmp_path):
    # Unclosed bracket → YAML parse error → reported, not raised.
    res = _loader.load_workflow_file(_write(tmp_path, "name: x\nnodes: [oops\n"))
    assert res.spec is None
    assert res.errors


def test_non_mapping_document_fails_soft(tmp_path):
    res = _loader.load_workflow_file(_write(tmp_path, "- just\n- a\n- list\n"))
    assert res.spec is None
    assert any("mapping" in e for e in res.errors)


def test_no_nodes_fails_soft(tmp_path):
    res = _loader.load_workflow_file(_write(tmp_path, "name: x\ndescription: y\n"))
    assert res.spec is None
    assert any("nodes" in e for e in res.errors)


def test_node_without_prompt_fails_soft(tmp_path):
    text = "name: x\nnodes:\n  - id: a\n"
    res = _loader.load_workflow_file(_write(tmp_path, text))
    assert res.spec is None
    assert any("prompt" in e for e in res.errors)


def test_node_without_id_fails_soft(tmp_path):
    text = "name: x\nnodes:\n  - prompt: hi\n"
    res = _loader.load_workflow_file(_write(tmp_path, text))
    assert res.spec is None
    assert any("id" in e for e in res.errors)


# --- invalid spec surfaced by validate_spec ------------------------------------

def test_duplicate_id_reported(tmp_path):
    text = """\
name: x
nodes:
  - id: a
    prompt: one
  - id: a
    prompt: two
"""
    res = _loader.load_workflow_file(_write(tmp_path, text))
    assert res.spec is None
    assert any("duplicate" in e for e in res.errors)


def test_cycle_reported(tmp_path):
    text = """\
name: x
nodes:
  - id: a
    depends_on: [b]
    prompt: a
  - id: b
    depends_on: [a]
    prompt: b
"""
    res = _loader.load_workflow_file(_write(tmp_path, text))
    assert res.spec is None
    assert any("cycle" in e for e in res.errors)


def test_unknown_dependency_reported(tmp_path):
    text = """\
name: x
nodes:
  - id: a
    depends_on: [ghost]
    prompt: a
"""
    res = _loader.load_workflow_file(_write(tmp_path, text))
    assert res.spec is None
    assert any("unknown" in e for e in res.errors)


# --- loader never raises on garbage --------------------------------------------

@pytest.mark.parametrize(
    "garbage",
    [
        "",                      # empty
        "null\n",                # YAML null
        "42\n",                  # scalar int
        "nodes: not-a-list\n",   # nodes wrong type
        "nodes:\n  - 5\n",       # node not a mapping
        "nodes:\n  - id: a\n    depends_on: notlist\n    prompt: p\n",
        "\t\x00 binary-ish \xff",  # junk bytes (str)
    ],
)
def test_loader_never_raises_on_garbage(tmp_path, garbage):
    res = _loader.load_workflow_file(_write(tmp_path, garbage))
    # Contract: always a LoadResult, spec None, errors populated, no exception.
    assert res.spec is None
    assert res.errors


def test_load_spec_handles_non_dict_directly():
    # The structural entry point also never raises on a non-mapping.
    for bad in (None, 42, "str", [1, 2], object()):
        res = _loader.load_spec(bad)
        assert res.spec is None and res.errors


# --- the shipped sample fixture loads, validates, plans, and runs ---------------

_FIXTURE = _root / "tests" / "fixtures" / "workflows" / "research-brief.yaml"


def test_sample_fixture_loads_and_validates():
    res = _loader.load_workflow_file(_FIXTURE)
    assert res.ok, res.errors
    assert res.name == "research-brief"
    assert [n.id for n in res.spec.nodes] == ["gather", "draft"]
    assert _wf.validate_spec(res.spec) == []
    assert _wf.plan_waves(res.spec) == [["gather"], ["draft"]]


def test_sample_fixture_runs_end_to_end_with_fake_dispatch():
    """AC-WF-006: a sample workflow loads, validates, and *runs*. A fake dispatch
    stands in for `claude -p` so no subprocess is touched; the draft node's prompt
    must carry the interpolated upstream result."""
    import json
    from types import SimpleNamespace

    res = _loader.load_workflow_file(_FIXTURE)
    assert res.ok, res.errors

    seen_prompts: dict = {}

    def fake_dispatch(prompt, *, forge_dir, feature, model=None, output_schema=None,
                      max_budget_usd=None, resume=None, claude_bin=None, cwd=None, **kw):
        # Record each node's compiled prompt by a marker only it contains.
        key = "gather" if "Research the given topic" in prompt else "draft"
        seen_prompts[key] = prompt
        payload = {"sources": [{"title": "t", "url": "u", "summary": "s"}]} \
            if key == "gather" else {"brief": "ok"}
        return SimpleNamespace(status="ok", result=json.dumps(payload),
                               cost_usd=0.01, raw={"is_error": False})

    out = _wf.run_workflow(
        res.spec, forge_dir=Path("/tmp/none"), feature="flow:test",
        dispatch_fn=fake_dispatch,
    )
    assert out.completed == 2, out.dropped_reasons
    assert out.dropped == 0
    assert out.results["draft"] == {"brief": "ok"}
    # The downstream prompt embedded the upstream JSON (data passing through {{gather}}).
    assert "sources" in seen_prompts["draft"]


# --- list_workflows discovery --------------------------------------------------

def test_list_workflows_finds_yaml_files(tmp_path):
    (tmp_path / "b.yaml").write_text("name: b\n")
    (tmp_path / "a.yml").write_text("name: a\n")
    (tmp_path / "ignore.txt").write_text("nope")
    found = _loader.list_workflows(tmp_path)
    assert [p.name for p in found] == ["a.yml", "b.yaml"]  # sorted


def test_list_workflows_missing_dir_returns_empty(tmp_path):
    assert _loader.list_workflows(tmp_path / "absent") == []


# --------------------------------------------------------------------------- #
# T-204 (REQ-WF-013, AC-WF-014) — /forge:flow pre-flight estimate reads cap-state
# --------------------------------------------------------------------------- #
import importlib.util as _ilu  # noqa: E402

_cfgspec = _ilu.spec_from_file_location(
    "_workflow_config", _root / "scripts" / "_workflow_config.py")
_wcfg = _ilu.module_from_spec(_cfgspec)
sys.modules["_workflow_config"] = _wcfg
_cfgspec.loader.exec_module(_wcfg)


def _flow_spec(n):
    return _wf.WorkflowSpec(nodes=[
        _wf.WorkflowNode(id=f"n{i}", build_prompt=lambda up: "x",
                         depends_on=([f"n{i-1}"] if i else []))
        for i in range(n)
    ])


def test_flow_estimate_within_generous_cap(tmp_path):
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    (forge / "config.yaml").write_text("cost_cap:\n  daily_usd: 100\n")
    cfg = _wcfg.OrchestrationConfig()
    est = _loader.flow_estimate(_flow_spec(3), forge, cfg)
    assert est.admitted == ["n0", "n1", "n2"]
    assert est.within_headroom is True
    assert est.daily_headroom_usd == 100.0


def test_flow_estimate_flags_tight_daily_cap(tmp_path):
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    # A daily cap that leaves headroom for only one node.
    daily = 1.5 * _wf.FRESH_FLOOR_USD
    (forge / "config.yaml").write_text(f"cost_cap:\n  daily_usd: {daily}\n")
    cfg = _wcfg.OrchestrationConfig()
    est = _loader.flow_estimate(_flow_spec(5), forge, cfg)
    # All 5 admitted by max_total, but 5×floor exceeds the ~1.5×floor daily headroom.
    assert est.within_headroom is False
