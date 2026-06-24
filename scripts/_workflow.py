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

import datetime as _dt
import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

_PLUGIN_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PLUGIN_DIR / "scripts"))
sys.path.insert(0, str(_PLUGIN_DIR / "hooks"))
import _background_agent  # noqa: E402  (the sole `claude -p` wrapper)
import _error_log  # noqa: E402  (rotation-aware atomic JSONL append — T-146, the audit writer)
import _verify  # noqa: E402  (shared verify/heal primitives — REQ-WF-002)

_LOG = logging.getLogger(__name__)

DEFAULT_MAX_PARALLEL = 4
DEFAULT_MAX_TOTAL = 64

# Per-node admission cost estimate (REQ-NF-029): each DAG node is a *fresh* dispatch and pays
# the fresh-session cache-creation tax, so budget-aware admission charges one fresh floor per
# node. Sourced from the single dispatch adapter so the estimate can never drift from the real
# cost gate (`_background_agent.dispatch` charges the same floor in `_cost_cap.precheck`).
FRESH_FLOOR_USD = _background_agent.FRESH_FLOOR_USD


# --------------------------------------------------------------------------- #
# Live run narration (REQ-WF-011 / T-202) — stderr-only, never touches stdout.
# --------------------------------------------------------------------------- #
# The v0.1.6 NARRATE precedent (REQ-INTERACTIVE-NARRATE-001): `[Forge]` progress on stderr,
# stdout reserved for the structured contract. Turning narration on/off must not change a
# single stdout byte (AC-WF-012). All narration routes through `_Narrator._line`, which writes
# to stderr and swallows any error — narration is best-effort and never raises into the engine.


def narration_enabled(forge_dir, *, env=None) -> bool:
    """Whether stderr narration is on for this run. OFF when `FORGE_WF_QUIET` is set to a
    non-empty value or `orchestration.narrate` is `false`; ON by default. Never raises — any
    failure degrades to silence (off), so a broken config can never make the engine throw."""
    try:
        environ = os.environ if env is None else env
        if (environ.get("FORGE_WF_QUIET") or "").strip():
            return False
        import _workflow_config  # local import: keeps the engine importable without it
        cfg = _workflow_config.load_orchestration_config(forge_dir)
        return getattr(cfg, "narrate", True) is not False
    except Exception:  # noqa: BLE001 — narration gating must never raise
        return False


class _Narrator:
    """Stderr-only run narration (REQ-WF-011). Every line is `[Forge] <text>`; when `enabled`
    is False every method is a no-op. `_line` swallows any write error so narration can never
    raise into `run_workflow` / `parallel_build` nor leak a byte onto stdout."""

    def __init__(self, name: str, enabled: bool) -> None:
        self.name = name
        self.enabled = bool(enabled)

    def _line(self, text: str) -> None:
        if not self.enabled:
            return
        try:
            sys.stderr.write(f"[Forge] {text}\n")
            sys.stderr.flush()
        except Exception:  # noqa: BLE001 — a broken stderr degrades to silence, never raises
            pass

    def wave(self, k: int, n: int, count: int) -> None:
        self._line(f"workflow {self.name!r}: wave {k}/{n} — {count} node(s)")

    def start(self, nid: str) -> None:
        self._line(f"  node {nid!r}: start")

    def done(self, nid: str, cost: float) -> None:
        self._line(f"  node {nid!r}: done (${cost:.4f})")

    def drop(self, nid: str, reason: str, cost: float = 0.0) -> None:
        self._line(f"  node {nid!r}: dropped: {reason} (${cost:.4f})")

    def summary(self, completed: list, dropped: list, total: float) -> None:
        """Final, deterministic, id-ordered summary block (the *testable* artifact — live
        per-node lines may interleave under parallelism, this does not)."""
        comp = ", ".join(sorted(completed))
        drops = ", ".join(
            f"{{{d['id']}: {d['reason']}}}" for d in sorted(dropped, key=lambda d: d["id"])
        )
        self._line(f"summary: completed:[{comp}] dropped:[{drops}] total ${total:.4f}")


# --------------------------------------------------------------------------- #
# `events.jsonl` audit record (REQ-WF-012 / T-203) — one structured line per run.
# --------------------------------------------------------------------------- #
# Every other Forge subsystem (cost-cap, observer, health, skill-miner) leaves a structured
# record; a workflow run left none. On every top-level `run_workflow` / `parallel_build`
# completion we append exactly one schema-versioned, PII-free JSON line to `.forge/events.jsonl`
# via the rotation-aware atomic writer (T-146). Deterministic, id-ordered fields — independent
# of thread scheduling (REQ-NF-032). Fail-soft: an unwritable `.forge` degrades silently; an
# over-cap or invalid-spec run still writes a record carrying its drops. Never raises.

AUDIT_SCHEMA_VERSION = 1
_EVENTS_NAME = "events.jsonl"


def _audit_ts(ts: Optional[str]) -> str:
    """The record timestamp: the injected `ts` when given, else the wall clock (UTC, Z-suffix)."""
    if ts is not None:
        return ts
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_audit_record(
    forge_dir,
    *,
    name: str,
    nodes: int,
    waves: int,
    completed: list,
    dropped: list,
    total_cost_usd: float,
    admitted: list,
    verdicts: Optional[dict] = None,
    ts: Optional[str] = None,
) -> None:
    """Append one `workflow_run` audit line to `<forge_dir>/events.jsonl` (REQ-WF-012).

    All list fields are id-sorted so the record is deterministic regardless of thread
    scheduling. Delegates the write to `_error_log.append_jsonl` (rotation + atomic single line),
    which is itself fail-soft — and the whole call is additionally guarded, so it never raises."""
    try:
        record = {
            "schema_version": AUDIT_SCHEMA_VERSION,
            "ts": _audit_ts(ts),
            "event": "workflow_run",
            "name": name,
            "nodes": int(nodes),
            "waves": int(waves),
            "completed": sorted(completed),
            "dropped": sorted(
                ({"id": d.get("id", ""), "reason": d.get("reason", "")} for d in (dropped or [])),
                key=lambda d: (d["id"], d["reason"]),
            ),
            "total_cost_usd": round(float(total_cost_usd or 0.0), 6),
            "verdicts": verdicts or {},
            "admitted": sorted(admitted),
        }
        _error_log.append_jsonl(Path(forge_dir) / _EVENTS_NAME, record)
    except Exception:  # noqa: BLE001 — the audit write must never raise into the engine
        pass


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
class DecomposeSpec:
    """Declarative request to *generate* a bounded, pre-validated sub-DAG (REQ-WF-010).

    A node carrying a `DecomposeSpec` is a `decompose` node: its own `build_prompt` is the
    cheap-model, schema-constrained *generation* prompt, whose reply is a sub-DAG (a JSON
    node/edge list). `parse_subdag` turns that parsed JSON into the child `WorkflowNode`s.

    Generation NEVER escapes a validated slot (§1.4 "Validate before dispatch"): before ANY
    child dispatches, the candidate sub-DAG is run through `validate_spec` (acyclicity + dup-id
    + unknown-dep) PLUS a node-count cap (`max_nodes`) PLUS a deterministic token-budget proxy
    (`max_chars`, measured as `len(json) // 4` — there is no stdlib tokenizer). Any violation —
    or garbage/failed generation — drops the generated set with a reason and runs `fallback`, a
    *deterministic* author-supplied sub-DAG (or `[]` for a pure no-op). The whole admission is a
    pure function of the generated JSON: same JSON ⇒ same accept/reject + same dropped set.

    Gated by `run_workflow(allow_generated_subdags=...)` (off by default); with it off the
    decompose node is inert and behaves as a plain node (no generation, no children).
    """

    # Parse the validated sub-DAG JSON (a dict) into child WorkflowNodes. Called only AFTER the
    # JSON parses; may raise — a raising parser is caught and treated as a generation failure.
    parse_subdag: Callable[[dict], list]
    # Deterministic fallback child nodes when generation is rejected/unavailable ([] ⇒ no-op).
    fallback: list = field(default_factory=list)  # list[WorkflowNode]
    max_nodes: int = 8  # node-count cap on the generated sub-DAG (REQ-WF-010)
    # Token-budget proxy ceiling, in *characters* of the generated JSON; the proxy itself is
    # `len(json) // 4` (≈ tokens), compared against `max_chars // 4`. Default ≈ 1024 tokens.
    max_chars: int = 4096
    schema: Optional[dict] = None  # constrains the generation reply (cheap, schema-constrained)
    model: Optional[str] = None  # cheap generation model (else inherits the node's `model`)


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
    # Per-node working directory (T-196, REQ-WF-007): lets a node run in its own directory or
    # git worktree (parallel build). `None` ⇒ inherit `run_workflow`'s scalar `cwd`, so every
    # existing caller — which sets only the scalar — is unaffected.
    cwd: Optional[str] = None
    # Validated sub-DAG generation (T-199, REQ-WF-010): when set AND
    # `run_workflow(allow_generated_subdags=True)`, this node generates a bounded, pre-validated
    # sub-DAG instead of producing a leaf result. `None` ⇒ a plain node (default).
    decompose: Optional[DecomposeSpec] = None


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
    # Additive structured views (v0.4.1) for the audit record (T-203) and the cost pre-flight
    # estimator's run-equality check (T-204). `admitted` is the deterministic topological
    # admission set; `drops` is the id/reason structured form of `dropped_reasons`. Both default
    # empty so every existing caller — which serializes only the original fields — is unaffected.
    admitted: list = field(default_factory=list)
    drops: list = field(default_factory=list)  # list[{"id", "reason"}]


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
    """One dispatch + parse + validate for a node. Returns (obj_or_None, reason, cost, session_id).

    The 4th member (REQ-WF-016) surfaces `res.session_id` so a later same-node re-dispatch can
    `--resume` it. It is the dispatch's session id whenever the dispatch *returned* one
    (`status="ok"` ⇒ a real resumable session exists, including the non-JSON / validation-failed
    paths), and `None` on every no-session path (dispatch raised, non-`ok` status — `skipped`/
    `error`/`unavailable` — or an agent-reported `is_error`). Behavior-preserving: the obj/reason/
    cost members and `_run_node`'s use of them are unchanged; the captured id is not consumed yet.
    """
    cost = 0.0
    try:
        res = dispatch_fn(prompt, **kwargs)
    except Exception as exc:  # noqa: BLE001 — a worker must never raise
        return None, f"dispatch raised: {exc}", cost, None
    cost += float(getattr(res, "cost_usd", 0.0) or 0.0)

    if getattr(res, "status", None) != "ok":
        return None, f"dispatch {getattr(res, 'status', 'error')}", cost, None
    if (getattr(res, "raw", None) or {}).get("is_error"):
        return None, "agent reported is_error", cost, None
    # Past the `ok` + non-`is_error` gates the dispatch returned a resumable session; surface its
    # id on every subsequent path (success, non-JSON, validation-failed) so a retry/heal can reuse it.
    session_id = getattr(res, "session_id", None)
    try:
        parsed = json.loads(res.result or "")
    except (ValueError, TypeError):
        return None, "non-JSON result", cost, session_id
    if node.validate is not None:
        try:
            parsed = node.validate(parsed)
        except Exception as exc:  # noqa: BLE001 — validation failure → drop, not crash
            return None, f"validation failed: {exc}", cost, session_id
    return parsed, None, cost, session_id


# One bounded heal attempt per verified node (REQ-WF-002), mirroring autopilot's default
# `max_heal_attempts = 1`: a failing verdict triggers a single node re-dispatch, then a
# re-verify; still-failing ⇒ drop-with-reason. 0 would make verify drop-only (no heal).
_NODE_HEAL_ATTEMPTS = 1


def _verify_prompt(node: WorkflowNode, obj) -> str:
    """Prompt for an INDEPENDENT verifier judging a produced node result (REQ-WF-002).

    Fresh context, read-only critique: assess whether the result genuinely satisfies the node's
    intent. The verdict is schema-constrained (`VerifySpec.schema` / `VERIFY_SCHEMA`) so the
    reply parses to pass/fail. The produced result is embedded for the verifier to judge.
    """
    spec = node.verify
    try:
        rendered = json.dumps(obj, sort_keys=True)
    except (TypeError, ValueError):
        rendered = repr(obj)
    return (
        f"You are an INDEPENDENT verifier for workflow node {node.id!r}, running in fresh "
        f"context via {spec.skill}. Critically assess whether the produced result genuinely "
        f"satisfies the node's intent — beyond surface checks. Do NOT modify anything. Return a "
        f"verdict of \"pass\" or \"fail\" with concise reasons.\n\nProduced result:\n{rendered}"
    )


def _run_verify(node: WorkflowNode, obj, dispatch_fn, kwargs) -> tuple:
    """Run the node's `VerifySpec` over a produced result `obj` (REQ-WF-002). Returns
    (passed: bool, cost: float). A fresh-session, schema-constrained pass/fail verdict gates
    the result; an unavailable/garbage verdict degrades to *passed* (the verifier is an extra
    check — REQ-NF-013). Never raises (delegates to `_verify.run_verify`, which never raises).
    """
    spec = node.verify
    vkwargs = dict(kwargs)
    if spec.model is not None:
        vkwargs["model"] = spec.model  # verifier model override (else inherits node's)
    res = _verify.run_verify(
        _verify_prompt(node, obj), dispatch_fn, vkwargs, schema=spec.schema,
    )
    cost = float((res.get("cost_usd") if isinstance(res, dict) else None) or 0.0)
    return (not _verify.verdict_failed(res)), cost


def _reuse_attempt(
    node: WorkflowNode, prompt: str, dispatch_fn, kwargs, *, session_reuse: bool, sid,
) -> tuple:
    """One same-node re-dispatch (retry or heal) with within-node session reuse (REQ-WF-017/018).

    Returns the `_attempt` 4-tuple `(obj, reason, cost, session_id)` plus the realized cost.
    When `session_reuse` is on and a prior same-node `sid` exists, the re-dispatch resumes it via
    a **per-attempt copy** `{**kwargs, "resume": sid}` — the shared `kwargs` dict is never mutated
    (it still flows to the fresh verifier). A resumed re-dispatch that returns a non-`ok` status
    (stale/invalid session ⇒ no parsed obj AND no new session) **falls back to one fresh
    re-dispatch within the same attempt budget** (REQ-WF-018), so reuse can never turn a
    would-succeed node into a drop. With reuse off (or no `sid`), the original `kwargs` flow
    through unchanged — byte-identical to v0.4.x (the run-level `resume` token is preserved).
    Never raises.
    """
    if not (session_reuse and sid):
        obj, reason, cost, new_sid = _attempt(node, prompt, dispatch_fn, kwargs)
        return obj, reason, cost, new_sid

    resumed = {**kwargs, "resume": sid}  # per-attempt copy — never mutate the shared dict (R-1)
    obj, reason, cost, new_sid = _attempt(node, prompt, dispatch_fn, resumed)
    # A stale/invalid resumed session surfaces as a no-session failure (the dispatch returned a
    # non-`ok` status, so `_attempt` yields obj=None AND new_sid=None). Fall back to a single fresh
    # re-dispatch within the same attempt budget; an ok-but-unparseable/validation-failed result
    # (new_sid set) is a genuine retry case, not a stale session, so it does not fall back.
    if obj is None and new_sid is None:
        f_obj, f_reason, f_cost, f_sid = _attempt(node, prompt, dispatch_fn, kwargs)
        return f_obj, f_reason, cost + f_cost, f_sid
    return obj, reason, cost, new_sid


def _run_node(node: WorkflowNode, prompt: str, dispatch_fn, kwargs,
              session_reuse: bool = False) -> tuple:
    """Dispatch a node with one retry on failure, then (if `node.verify` is set) gate the result
    with a fresh-session verdict and one bounded heal attempt. Returns (obj_or_None, reason,
    total_cost). Never raises.

    Within-node session reuse (REQ-WF-017, T-216): when `session_reuse` is on, the node's own
    retry and heal re-dispatches `--resume` the **most-recent captured `session_id`** (lowering
    their realized floor from `FRESH_FLOOR_USD` to `RESUME_FLOOR_USD`) via a per-attempt kwargs
    copy that never mutates the shared dict — so the independent verifier (which reads the same
    `kwargs` through `_run_verify`/`_verify.run_verify`) still dispatches fresh (REQ-WF-002). With
    reuse off the param is inert and every re-dispatch is fresh — byte-identical to v0.4.x.
    """
    # `_attempt` returns a 4-tuple `(obj, reason, cost, session_id)` (REQ-WF-016). Track the newest
    # non-None same-node session so each re-dispatch resumes the most recent context.
    obj, reason, cost, session_id = _attempt(node, prompt, dispatch_fn, kwargs)
    if obj is None:
        obj, reason, cost2, retry_sid = _reuse_attempt(  # retry once
            node, prompt, dispatch_fn, kwargs, session_reuse=session_reuse, sid=session_id)
        cost += cost2
        session_id = retry_sid or session_id
        if obj is None:
            return None, reason, cost

    if node.verify is None:
        return obj, None, cost

    # Per-node verification (REQ-WF-002): fresh-session verdict; on a clean `fail`, make one
    # bounded heal (re-dispatch + re-verify) before dropping. The heal re-dispatch reuses the
    # node's session under `session_reuse`; the verifier is always fresh.
    passed, vcost = _run_verify(node, obj, dispatch_fn, kwargs)
    cost += vcost
    if passed:
        return obj, None, cost

    attempts = 0
    while _verify.should_heal(attempts, _NODE_HEAL_ATTEMPTS):
        attempts += 1
        healed, hreason, hcost, heal_sid = _reuse_attempt(
            node, prompt, dispatch_fn, kwargs, session_reuse=session_reuse, sid=session_id)
        cost += hcost
        session_id = heal_sid or session_id
        if healed is None:
            return None, f"verify failed; heal dispatch failed: {hreason}", cost
        passed, vcost = _run_verify(node, healed, dispatch_fn, kwargs)
        cost += vcost
        if passed:
            return healed, None, cost
        obj = healed  # carry the latest result for the drop reason / next attempt
    return None, "verify verdict failed after heal", cost


# Generation prompt marker: the decompose node's reply is the *whole* sub-DAG, so the generation
# call asks for a JSON node/edge list. The DecomposeSpec.schema (if any) constrains the shape.
_DECOMPOSE_SCHEMA_HINT = (
    "Reply ONLY with a JSON object {\"nodes\": [{\"id\": str, \"prompt\": str, "
    "\"depends_on\": [str]}]} describing a sub-DAG of steps. No prose."
)


def _token_proxy(json_str: str) -> int:
    """Deterministic stdlib token-budget proxy (REQ-WF-010): ≈ tokens as character count // 4.

    A pure function of the input string — same string ⇒ same number — used to bound a *generated*
    sub-DAG before any child dispatch. There is no stdlib tokenizer, so this is intentionally a
    coarse char-based heuristic, never an import."""
    return len(json_str) // 4


def _admit_subdag(
    sub: WorkflowSpec, raw_json: str, dspec: DecomposeSpec,
) -> tuple[bool, Optional[str]]:
    """Deterministically admit a *generated* sub-DAG (REQ-WF-010). Returns (admitted, reason).

    Three gates, all pure functions of the candidate: `validate_spec` (acyclicity + dup-id +
    unknown-dep), the node-count cap (`max_nodes`), and the token-budget proxy (`max_chars`).
    The first failing gate yields a reason; on success returns (True, None). Never raises."""
    nodes = list(getattr(sub, "nodes", []) or [])
    if len(nodes) > dspec.max_nodes:
        return False, f"generated sub-DAG node count {len(nodes)} exceeds cap {dspec.max_nodes}"
    proxy = _token_proxy(raw_json)
    budget = dspec.max_chars // 4
    if proxy > budget:
        return False, f"generated sub-DAG token proxy {proxy} exceeds budget {budget}"
    errors = validate_spec(sub)
    if errors:
        return False, "; ".join(errors)
    return True, None


def _run_decompose(
    node: WorkflowNode, prompt: str, dispatch_fn, kwargs, run_kwargs,
) -> tuple:
    """Run a `decompose` node (REQ-WF-010): generate → validate → admit → run children, or run
    the deterministic fallback. Returns (result_obj_or_None, reason, total_cost). Never raises.

    The generation call is a cheap-model, schema-constrained dispatch via the same adapter; its
    reply is parsed to a candidate sub-DAG and gated by `_admit_subdag` *before* any child runs.
    Admitted ⇒ the children run via a nested `run_workflow` and the node's result is
    `{"children": {...}}`. Rejected/garbage/failed ⇒ the fallback sub-DAG runs and the node is
    dropped-with-reason (its result is whatever the fallback produced, surfaced as `children`)."""
    dspec = node.decompose
    cost = 0.0

    def _run_children(children: list) -> tuple:
        """Run a child sub-DAG via a nested run_workflow; returns ({id: result}, cost)."""
        if not children:
            return {}, 0.0
        child_spec = WorkflowSpec(nodes=children)
        out = run_workflow(child_spec, dispatch_fn=dispatch_fn, **run_kwargs)
        return out.results, out.total_cost_usd

    def _fallback(reason: str) -> tuple:
        """Drop the generated set with `reason`; run the deterministic fallback (no child of the
        generated set ever dispatched)."""
        fb_results, fb_cost = _run_children(list(dspec.fallback or []))
        result = {"children": fb_results, "generated": False}
        return result, reason, cost + fb_cost

    # Generation dispatch: cheap model + schema-constrained (REQ-WF-010). Reuse the node-dispatch
    # kwargs but override model/schema from the DecomposeSpec; never resume (fresh generation).
    gkwargs = dict(kwargs)
    gkwargs["resume"] = None
    if dspec.model is not None:
        gkwargs["model"] = dspec.model
    gkwargs["output_schema"] = dspec.schema  # None ⇒ unconstrained generation
    gen_prompt = f"{prompt}\n\n{_DECOMPOSE_SCHEMA_HINT}"
    try:
        res = dispatch_fn(gen_prompt, **gkwargs)
    except Exception as exc:  # noqa: BLE001 — a generation dispatch must never raise the worker
        return _fallback(f"decompose generation raised: {exc}")
    cost += float(getattr(res, "cost_usd", 0.0) or 0.0)

    if getattr(res, "status", None) != "ok":
        return _fallback(f"decompose generation {getattr(res, 'status', 'error')}")
    if (getattr(res, "raw", None) or {}).get("is_error"):
        return _fallback("decompose generation reported is_error")
    try:
        parsed = json.loads(res.result or "")
    except (ValueError, TypeError):
        return _fallback("decompose generation returned non-JSON")
    if not isinstance(parsed, dict):
        return _fallback("decompose generation was not a JSON object")

    # Build the candidate sub-DAG via the author's parser, then admit it deterministically.
    # Parse + admission run under one guard: a parser that returns malformed nodes (e.g. objects
    # without `.id`) makes `_admit_subdag`/`validate_spec` raise, which must route to the
    # deterministic fallback (REQ-WF-010) — not escape to the worker guard with no fallback.
    try:
        children = dspec.parse_subdag(parsed)
        sub = WorkflowSpec(nodes=list(children or []))
        admitted, reason = _admit_subdag(sub, res.result or "", dspec)
    except Exception as exc:  # noqa: BLE001 — a raising parser/validator ⇒ generation failure, not a crash
        return _fallback(f"decompose parse failed: {exc}")
    if not admitted:
        return _fallback(f"generated sub-DAG rejected: {reason}")

    child_results, child_cost = _run_children(list(children))
    return {"children": child_results, "generated": True}, None, cost + child_cost


# --------------------------------------------------------------------------- #
# Deterministic admission + cost pre-flight estimator (REQ-WF-013 / NF-033 / T-204).
# --------------------------------------------------------------------------- #
# The estimator is a *pure* function of `(spec, cap-state)` that replays the EXACT topological
# pre-allocation `run_workflow` performs (REQ-NF-029) — they share `_preallocate`, so the
# estimate can never become a second cost model that drifts from the run (REQ-NF-033). Zero
# dispatch. Same inputs ⇒ same result.

# The per-node reason used for a pre-allocated cap drop — shared by `run_workflow`'s loud
# narration line and the estimator's split, so the two are byte-identical (AC-WF-014).
_CAP_DROP_REASON = "exceeds cost/total cap (pre-allocated drop)"


def _preallocate(waves: list, max_total: int, max_budget_usd: Optional[float]) -> tuple:
    """Walk nodes in topological order (wave, then sorted id) and admit each while it fits *both*
    the count cap (`max_total`) and the spend cap (`max_budget_usd`, one fresh-session floor per
    node). A single-threaded pass — never a thread race — so cap pressure drops a *fixed* set,
    identical across parallel and sequential runs (REQ-NF-026b). Pure; returns
    `(allowed: set, capped_by_total: bool, capped_by_budget: bool)`."""
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
    return allowed, capped_by_total, capped_by_budget


@dataclass
class AdmissionEstimate:
    """A pre-flight cost estimate over a `WorkflowSpec` against current cap-state (REQ-WF-013).

    `admitted` / `dropped` are the deterministic id-ordered pre-allocation split (identical, by
    construction, to what `run_workflow` admits/drops for the same inputs). `estimate_usd` is the
    floor-based spend estimate (`len(admitted) × FRESH_FLOOR_USD`). The `*_headroom_usd` fields and
    `within_headroom` report whether the estimate fits the remaining daily/monthly cap headroom."""

    admitted: list                              # sorted node ids that will run
    dropped: list                               # [{id, reason}], id-ordered
    estimate_usd: float
    floor_usd: float
    node_count: int
    max_total: int
    max_budget_usd: Optional[float] = None
    daily_headroom_usd: Optional[float] = None
    monthly_headroom_usd: Optional[float] = None
    within_headroom: bool = True


def estimate_admission(
    spec: WorkflowSpec,
    *,
    max_total: int = DEFAULT_MAX_TOTAL,
    max_budget_usd: Optional[float] = None,
    daily_headroom_usd: Optional[float] = None,
    monthly_headroom_usd: Optional[float] = None,
) -> AdmissionEstimate:
    """Pure pre-flight estimator (REQ-WF-013, AC-WF-014). Replays `run_workflow`'s `_preallocate`
    pass to return the deterministic admitted/pre-dropped split and a floor-based spend estimate —
    **zero dispatch**. An invalid spec admits nothing (it would dispatch nothing). The estimate is
    compared to the supplied daily/monthly headroom; `within_headroom` is False when it exceeds
    either. Never raises."""
    nodes = list(getattr(spec, "nodes", []) or [])
    floor = FRESH_FLOOR_USD

    errors = validate_spec(spec)
    if errors:
        dropped = [{"id": "", "reason": f"invalid spec: {'; '.join(errors)}"}]
        return AdmissionEstimate(
            admitted=[], dropped=dropped, estimate_usd=0.0, floor_usd=floor,
            node_count=len(nodes), max_total=max_total, max_budget_usd=max_budget_usd,
            daily_headroom_usd=daily_headroom_usd, monthly_headroom_usd=monthly_headroom_usd,
            within_headroom=True,
        )

    waves = plan_waves(spec)
    allowed, _capped_total, _capped_budget = _preallocate(waves, max_total, max_budget_usd)
    admitted = sorted(allowed)
    dropped = sorted(
        ({"id": n.id, "reason": _CAP_DROP_REASON} for n in nodes if n.id not in allowed),
        key=lambda d: d["id"],
    )
    estimate_usd = round(len(admitted) * floor, 6)

    within = True
    if daily_headroom_usd is not None and estimate_usd > daily_headroom_usd:
        within = False
    if monthly_headroom_usd is not None and estimate_usd > monthly_headroom_usd:
        within = False

    return AdmissionEstimate(
        admitted=admitted, dropped=dropped, estimate_usd=estimate_usd, floor_usd=floor,
        node_count=len(nodes), max_total=max_total, max_budget_usd=max_budget_usd,
        daily_headroom_usd=daily_headroom_usd, monthly_headroom_usd=monthly_headroom_usd,
        within_headroom=within,
    )


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
    allow_generated_subdags: bool = False,
    session_reuse: bool = False,
    caveman: Optional[str] = None,
    name: Optional[str] = None,
    narrator: Optional["_Narrator"] = None,
    audit: bool = True,
    audit_ts: Optional[str] = None,
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

    Hybrid generation (REQ-WF-010): when `allow_generated_subdags=True`, a node carrying a
    `DecomposeSpec` generates a bounded, pre-validated sub-DAG (cheap-model, schema-constrained)
    that is admitted via `validate_spec` + node-count cap + token-budget proxy *before* any child
    dispatches; a rejected/garbage/failed generation runs the deterministic fallback. With the
    toggle off (default) such a node behaves as a plain node — no generation, no children.

    Per-node session reuse (v0.6.0, REQ-WF-019): `session_reuse` is accepted and threaded but
    **inert this release-task (T-214)** — no node yet `--resume`s a prior same-node attempt, so
    the engine's output is byte-identical with it on or off. T-216 consumes it. Admission stays
    on `FRESH_FLOOR_USD` regardless (REQ-WF-020), so reuse never alters the admitted/dropped split.

    Caveman mode (v0.6.1, REQ-CM-003): when `caveman` is a level (`lite`|`full`) it threads into
    every node's `dispatch` call, where the chokepoint prepends a terse-output preamble to
    *free-prose* dispatches only (schema-constrained ones are skipped). It is added to the dispatch
    kwargs **only when set**, so with it unset (default) the kwargs are byte-identical to v0.6.0
    (REQ-NF-041). Cost admission is unaffected.
    """
    dispatch_fn = dispatch_fn or _background_agent.dispatch
    nodes = list(getattr(spec, "nodes", []) or [])
    dropped_reasons: list[str] = []
    # Structured (id, reason) drops for the deterministic id-ordered narration summary (T-202)
    # and, later, the events.jsonl audit record (T-203). Parallel to `dropped_reasons` (which is
    # kept byte-identical to v0.4.0 on the result), never replacing it.
    drops: list[dict] = []

    run_name = name if name is not None else feature
    if narrator is None:
        narrator = _Narrator(run_name, narration_enabled(forge_dir))

    errors = validate_spec(spec)
    if errors:
        for e in errors:
            dropped_reasons.append(f"invalid spec: {e}")
            drops.append({"id": "", "reason": f"invalid spec: {e}"})
            narrator.drop("", f"invalid spec: {e}")
            _LOG.warning("run_workflow: %s", e)
        narrator.summary([], drops, 0.0)
        if audit:
            write_audit_record(
                forge_dir, name=run_name, nodes=len(nodes), waves=0, completed=[],
                dropped=drops, total_cost_usd=0.0, admitted=[], ts=audit_ts,
            )
        return WorkflowResult(results={}, completed=0, dropped=len(nodes),
                              total_cost_usd=0.0, dropped_reasons=dropped_reasons,
                              admitted=[], drops=drops)

    by_id = {n.id: n for n in nodes}
    waves = plan_waves(spec)

    # Deterministic budget-aware admission (REQ-NF-029) via the shared `_preallocate` pass —
    # the *same* pure function the pre-flight estimator (`estimate_admission`, T-204) replays,
    # so the estimate can never drift from what the run admits (REQ-NF-033).
    allowed, capped_by_total, capped_by_budget = _preallocate(waves, max_total, max_budget_usd)
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

    n_waves = len(waves)
    for wi, wave in enumerate(waves, 1):
        narrator.wave(wi, n_waves, len(wave))
        prepared: list[tuple[WorkflowNode, str]] = []  # (node, prompt) ready to dispatch
        for nid in wave:
            if nid not in allowed:
                # Pre-allocated cap drop (REQ-NF-029): the aggregate reason was logged once
                # above; here it becomes a loud, per-node line + structured drop (T-202/204).
                # Same reason string the estimator emits ⇒ estimator split == run drops.
                drops.append({"id": nid, "reason": _CAP_DROP_REASON})
                narrator.drop(nid, _CAP_DROP_REASON)
                continue
            node = by_id[nid]
            missing = [d for d in (node.depends_on or []) if d not in results]
            if missing:
                reason = f"node {nid!r} skipped: dependency dropped/missing {missing}"
                dropped_reasons.append(reason)
                drops.append({"id": nid, "reason": reason})
                narrator.drop(nid, reason)
                _LOG.warning("run_workflow: %s", reason)
                continue
            upstream = {d: results[d] for d in (node.depends_on or [])}
            try:
                prompt = node.build_prompt(upstream)
            except Exception as exc:  # noqa: BLE001 — build failure → drop, not crash
                reason = f"node {nid!r} build_prompt failed: {exc}"
                dropped_reasons.append(reason)
                drops.append({"id": nid, "reason": reason})
                narrator.drop(nid, reason)
                _LOG.warning("run_workflow: %s", reason)
                continue
            prepared.append((node, prompt))

        # Live per-node `start` lines (id-ordered here; may interleave with `done` lines under
        # parallelism — accepted, the deterministic artifact is the summary block).
        for node, _prompt in prepared:
            narrator.start(node.id)

        if not prepared:
            continue

        workers = max(1, min(max_parallel, len(prepared)))
        wave_out: dict = {}

        def _submit(pool, node, prompt):
            """Submit one node to the worker pool, routing active `decompose` nodes (REQ-WF-010)
            to the generate→validate→admit path and every other node to the normal dispatch."""
            node_kwargs = {
                "forge_dir": forge_dir, "feature": feature, "model": node.model,
                "output_schema": node.output_schema, "max_budget_usd": max_budget_usd,
                "resume": resume, "claude_bin": claude_bin,
                # Per-node `cwd` (T-196) overrides the scalar; unset ⇒ scalar fallback.
                "cwd": node.cwd if node.cwd is not None else cwd,
            }
            # Caveman level (v0.6.1, REQ-CM-003) threads into the dispatch call ONLY when set, so
            # with it off the kwargs are byte-identical to v0.6.0 (REQ-NF-041). The chokepoint
            # skips schema-constrained dispatches, so verify/skeptic/gate output is never altered.
            if caveman is not None:
                node_kwargs["caveman"] = caveman
            if allow_generated_subdags and node.decompose is not None:
                # Nested run_workflow kwargs for the generated/fallback children: same bounds,
                # same cwd/toggle, fresh sessions (generation never resumes a parent session).
                run_kwargs = {
                    "forge_dir": forge_dir, "feature": feature,
                    "max_parallel": max_parallel, "max_total": max_total,
                    "max_budget_usd": max_budget_usd, "claude_bin": claude_bin,
                    "cwd": node.cwd if node.cwd is not None else cwd,
                    "allow_generated_subdags": allow_generated_subdags,
                    # Inherit the reuse toggle into child sub-DAGs (inert this task, T-214).
                    "session_reuse": session_reuse,
                    # Nested child run is part of THIS run — it must not write its own audit
                    # line (exactly one record per top-level run, REQ-WF-012).
                    "audit": False,
                }
                # Inherit the caveman level into child sub-DAGs only when set (REQ-CM-003).
                if caveman is not None:
                    run_kwargs["caveman"] = caveman
                return pool.submit(_run_decompose, node, prompt, dispatch_fn,
                                   node_kwargs, run_kwargs)
            return pool.submit(_run_node, node, prompt, dispatch_fn, node_kwargs,
                               session_reuse)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {_submit(pool, node, prompt): node.id for node, prompt in prepared}
            for fut in futures:
                nid = futures[fut]
                try:
                    wave_out[nid] = fut.result()
                except Exception as exc:  # noqa: BLE001 — defensive; workers already guard
                    wave_out[nid] = (None, f"worker error: {exc}", 0.0)

        # Collect this wave's results in sorted id order so accumulation is deterministic.
        for nid in sorted(wave_out):
            obj, reason, cost = wave_out[nid]
            total_cost += cost
            if obj is None:
                dropped_reasons.append(f"node {nid!r}: {reason}")
                drops.append({"id": nid, "reason": reason})
                narrator.drop(nid, reason, cost)
                _LOG.warning("run_workflow: dropped %s — %s", nid, reason)
                continue
            # A `decompose` node can complete *with* a reason: the generated sub-DAG was rejected
            # (cycle / over-cap / garbage) so the deterministic fallback ran. The node keeps its
            # (fallback) result, but the rejection is surfaced — drop-with-reason, never silent.
            if reason is not None:
                dropped_reasons.append(f"node {nid!r}: {reason}")
                drops.append({"id": nid, "reason": reason})
                _LOG.warning("run_workflow: %s — %s", nid, reason)
            narrator.done(nid, cost)
            results[nid] = obj

    ordered = {nid: results[nid] for nid in sorted(results)}
    completed = len(ordered)
    narrator.summary(list(ordered.keys()), drops, total_cost)
    admitted_ids = sorted(allowed)
    if audit:
        write_audit_record(
            forge_dir, name=run_name, nodes=len(nodes), waves=len(waves),
            completed=list(ordered.keys()), dropped=drops, total_cost_usd=total_cost,
            admitted=admitted_ids, ts=audit_ts,
        )
    return WorkflowResult(
        results=ordered,
        admitted=admitted_ids,
        drops=drops,
        completed=completed,
        dropped=len(nodes) - completed,
        total_cost_usd=total_cost,
        dropped_reasons=dropped_reasons,
    )
