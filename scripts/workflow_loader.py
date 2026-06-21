#!/usr/bin/env python3
"""Declarative `.forge/workflows/*.yaml` loader → `WorkflowSpec` (v0.4.0, REQ-WF-005).

Parses a user-authored workflow file into the in-memory `WorkflowSpec` that
`_workflow.run_workflow` executes. A workflow file is a YAML mapping:

```yaml
name: my-flow
description: what this flow does
nodes:
  - id: research
    prompt: "Research the topic and return JSON {findings: [...]}"
  - id: write
    depends_on: [research]
    prompt_template: "Write a draft from these findings: {{research}}"
    schema: {type: object}      # optional → WorkflowNode.output_schema
    model: claude-haiku-4-5     # optional → WorkflowNode.model
```

Each node compiles to a `WorkflowNode`. A literal `prompt` compiles to a *constant*
`build_prompt`; a `prompt_template` compiles to a closure that substitutes
`{{upstream_id}}` tokens with the matching upstream node's validated result at run
time — this is the inter-step data channel. The interpolated upstream output is
**untrusted data**: it was schema-validated at the upstream node boundary, but we
only string-substitute it (never eval/format-spec it), so a node result that happens
to contain `{`/`}` or `{name}` cannot break or hijack the prompt.

Fail-soft (REQ-NF-024): a missing file, absent PyYAML, malformed YAML, a non-mapping
document, or a structurally invalid spec (`validate_spec`) all yield a structured
`LoadResult(spec=None, errors=[...])` — this module **never raises**, mirroring
`_state_lib`'s stdlib + guarded-PyYAML discipline (no `frontmatter` dependency).

Stdlib only (PyYAML guarded). `python3`.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

_PLUGIN_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PLUGIN_DIR / "scripts"))
import _workflow  # noqa: E402  (WorkflowSpec / WorkflowNode / validate_spec)

WorkflowSpec = _workflow.WorkflowSpec
WorkflowNode = _workflow.WorkflowNode

# `{{upstream_id}}` interpolation token. Ids are matched loosely (any run of
# non-brace chars, trimmed) so an unknown/malformed token is left untouched rather
# than crashing — an unresolved token surfaces in the prompt for the agent to see.
_TOKEN = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")


@dataclass
class LoadResult:
    """Outcome of loading one workflow file. `spec is None` ⇔ load failed; `errors`
    then explains why (missing file, malformed YAML, invalid structure). `name` and
    `description` echo the file's metadata when available (for the `/forge:flow`
    listing), even on partial failure."""

    spec: Optional[Any] = None  # WorkflowSpec | None
    errors: list = field(default_factory=list)
    name: Optional[str] = None
    description: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.spec is not None and not self.errors


def _safe_yaml_load(text: str) -> tuple[Optional[object], Optional[str]]:
    """Parse YAML fail-soft (mirrors `_state_lib`'s guarded import). Returns
    (parsed, error): a missing PyYAML or any parse error yields (None, reason)."""
    try:
        import yaml  # noqa: F811
    except ImportError:
        return None, "PyYAML is not available — cannot parse workflow YAML"
    try:
        return yaml.safe_load(text), None
    except Exception as exc:  # noqa: BLE001 — any parse error is fail-soft
        return None, f"malformed YAML: {exc}"


def _interpolate(template: str, upstream: dict) -> str:
    """Substitute `{{id}}` tokens in `template` with the matching upstream result.

    Upstream values are untrusted data, so each is rendered with plain `str()` and
    spliced in literally — no `str.format`, no eval. An unknown token is left as-is
    (visible to the agent) rather than raising a KeyError."""

    def _sub(match: re.Match) -> str:
        key = match.group(1)
        if key in upstream:
            return str(upstream[key])
        return match.group(0)  # leave unresolved token verbatim

    return _TOKEN.sub(_sub, template)


def _make_build_prompt(node_dict: dict) -> tuple[Optional[Callable[[dict], str]], Optional[str]]:
    """Compile a node's `prompt` / `prompt_template` into a `build_prompt(upstream)`.

    A literal `prompt` → a constant builder. A `prompt_template` → an interpolating
    closure. Returns (builder, error); error is non-None when neither key is a
    usable string (the node cannot dispatch without a prompt)."""
    template = node_dict.get("prompt_template")
    literal = node_dict.get("prompt")

    if isinstance(template, str):
        def build_prompt(upstream: dict, _tmpl: str = template) -> str:
            return _interpolate(_tmpl, upstream)
        return build_prompt, None

    if isinstance(literal, str):
        def build_prompt(upstream: dict, _text: str = literal) -> str:  # noqa: ARG001
            return _text
        return build_prompt, None

    return None, "node has neither a string 'prompt' nor 'prompt_template'"


def _build_node(node_dict: dict, index: int) -> tuple[Optional[Any], list]:
    """Compile one node mapping into a `WorkflowNode`. Returns (node, errors)."""
    errors: list = []
    if not isinstance(node_dict, dict):
        return None, [f"node #{index} is not a mapping"]

    nid = node_dict.get("id")
    if not isinstance(nid, str) or not nid.strip():
        return None, [f"node #{index} is missing a string 'id'"]

    depends_on = node_dict.get("depends_on") or []
    if not isinstance(depends_on, list) or not all(isinstance(d, str) for d in depends_on):
        errors.append(f"node {nid!r}: 'depends_on' must be a list of strings")
        depends_on = [d for d in depends_on if isinstance(d, str)] if isinstance(depends_on, list) else []

    build_prompt, prompt_err = _make_build_prompt(node_dict)
    if prompt_err:
        return None, [f"node {nid!r}: {prompt_err}"]

    schema = node_dict.get("schema")
    output_schema = schema if isinstance(schema, dict) else None
    model = node_dict.get("model")
    model = model if isinstance(model, str) else None

    node = WorkflowNode(
        id=nid,
        build_prompt=build_prompt,
        depends_on=depends_on,
        output_schema=output_schema,
        model=model,
    )
    return node, errors


def load_spec(data: object) -> LoadResult:
    """Compile an already-parsed workflow document (a dict) into a `LoadResult`.

    Validates structure: the document must be a mapping with a list `nodes`; each
    node compiles via `_build_node`; the assembled spec is run through
    `validate_spec` (duplicate ids / unknown deps / cycles). Never raises."""
    if not isinstance(data, dict):
        return LoadResult(errors=["workflow file is not a YAML mapping"])

    name = data.get("name") if isinstance(data.get("name"), str) else None
    description = data.get("description") if isinstance(data.get("description"), str) else None

    raw_nodes = data.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        return LoadResult(
            errors=["workflow file has no 'nodes' list"],
            name=name,
            description=description,
        )

    nodes: list = []
    errors: list = []
    for i, nd in enumerate(raw_nodes):
        node, node_errors = _build_node(nd, i)
        errors.extend(node_errors)
        if node is not None:
            nodes.append(node)

    if not nodes:
        return LoadResult(errors=errors or ["no valid nodes"], name=name, description=description)

    spec = WorkflowSpec(nodes=nodes)
    errors.extend(f"invalid spec: {e}" for e in _workflow.validate_spec(spec))
    if errors:
        return LoadResult(errors=errors, name=name, description=description)
    return LoadResult(spec=spec, name=name, description=description)


def load_workflow_file(path) -> LoadResult:
    """Load one `.forge/workflows/<name>.yaml` from disk into a `LoadResult`.

    Fail-soft end to end: a missing/unreadable file, absent PyYAML, or malformed
    YAML each yield `LoadResult(spec=None, errors=[...])`. Never raises."""
    p = Path(path)
    try:
        if not p.exists():
            return LoadResult(errors=[f"workflow file not found: {p}"])
        text = p.read_text()
    except OSError as exc:
        return LoadResult(errors=[f"cannot read workflow file {p}: {exc}"])

    data, yaml_err = _safe_yaml_load(text)
    if yaml_err:
        return LoadResult(errors=[yaml_err])
    return load_spec(data)


def flow_estimate(spec, forge_dir, config, *, now=None):
    """Cost pre-flight estimate for `/forge:flow` (REQ-WF-013 / T-204): read the *single*
    cost-cap source (`_cost_cap` daily/monthly caps + ledger spend) for the remaining headroom,
    take the engine tunables from the `orchestration:` config, and delegate to the pure
    `_workflow.estimate_admission`. Returns an `AdmissionEstimate` (admitted/dropped split +
    spend estimate + headroom). No dispatch; fail-soft — an unreadable cap-state degrades to
    unbounded headroom. Never raises."""
    daily_headroom = None
    monthly_headroom = None
    try:
        import _cost_cap  # hooks/ — on sys.path via _workflow's import above
        import datetime as _dt
        when = now if now is not None else _dt.datetime.now(_dt.timezone.utc)
        caps = _cost_cap.load_caps(Path(forge_dir))
        rows = _cost_cap._read_ledger(Path(forge_dir))
        spent_today, spent_month = _cost_cap._spend(rows, when)
        daily_headroom = caps.daily_usd - spent_today
        if caps.monthly_usd is not None:
            monthly_headroom = caps.monthly_usd - spent_month
    except Exception:  # noqa: BLE001 — cap-state is advisory; degrade to unbounded headroom
        daily_headroom = None
        monthly_headroom = None

    return _workflow.estimate_admission(
        spec,
        max_total=getattr(config, "max_total", _workflow.DEFAULT_MAX_TOTAL),
        max_budget_usd=getattr(config, "max_budget_usd", None),
        daily_headroom_usd=daily_headroom,
        monthly_headroom_usd=monthly_headroom,
    )


def list_workflows(workflows_dir) -> list:
    """Return sorted `.yaml`/`.yml` workflow file paths under `workflows_dir`.

    Returns `[]` when the directory is absent or unreadable (fail-soft). The
    `/forge:flow` skill calls this to enumerate available flows by name."""
    d = Path(workflows_dir)
    try:
        if not d.is_dir():
            return []
        return sorted(
            p for p in d.iterdir()
            if p.is_file() and p.suffix.lower() in (".yaml", ".yml")
        )
    except OSError:
        return []
