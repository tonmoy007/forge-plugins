#!/usr/bin/env python3
"""Workflow engine configuration — the opt-in `orchestration:` block (v0.4.0, REQ-WF-003).

`.forge/config.yaml` gains an `orchestration:` section carrying **independent** capability
toggles (`flows_enabled`, `parallel_build`, `worktree_isolation`, `allow_generated_subdags`)
— **all default false** — plus engine tunables (`max_parallel`, `max_total`, `max_budget_usd`).
The DAG engine in `_workflow.py` is always available (no toggle); the toggles gate the
*features built on top of it* (T-194..T-199 read them). With every toggle off, behavior is
identical to v0.3.6 (REQ-NF-025).

Loading mirrors `autopilot.load_config` exactly in spirit: fail-soft PyYAML (absent library
or malformed file → defaults), per-key coercion where an invalid individual value falls back
to that key's default while valid siblings survive, and strict `is True` toggle semantics so a
stray truthy scalar can never silently enable a capability. Never raises (REQ-NF-024).

Stdlib only (PyYAML guarded). `python3`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Engine tunable defaults — kept in sync with `_workflow.DEFAULT_MAX_PARALLEL` /
# `DEFAULT_MAX_TOTAL`; duplicated here so config loading has no import dependency on the
# engine module (and stays importable even if the engine is unavailable).
DEFAULT_MAX_PARALLEL = 4
DEFAULT_MAX_TOTAL = 64


@dataclass
class OrchestrationConfig:
    """The parsed `orchestration:` block. All capabilities default off (REQ-NF-025)."""

    # Independent capability toggles — all default false.
    flows_enabled: bool = False
    parallel_build: bool = False
    worktree_isolation: bool = False
    allow_generated_subdags: bool = False
    # Per-node session reuse (v0.6.0, REQ-WF-019): when on, a node's own retry/heal
    # re-dispatches `--resume` the first attempt's session (cheaper floor). Default off ⇒
    # the engine is byte-identical to v0.4.x. Strict `is True` like its sibling toggles.
    session_reuse: bool = False
    # Engine tunables threaded into `run_workflow` (REQ-NF-027).
    max_parallel: int = DEFAULT_MAX_PARALLEL
    max_total: int = DEFAULT_MAX_TOTAL
    max_budget_usd: Optional[float] = None  # None ⇒ no per-run spend cap
    # Observability control (REQ-WF-011, v0.4.1): live stderr narration, default ON. This is
    # *not* a capability toggle — it gates no engine behavior, only side-channel stderr output
    # (the engine's stdout result is byte-identical with it on or off). Only an explicit bool
    # `false` silences; a stray truthy/falsy scalar never flips the product default off.
    narrate: bool = True


_TOGGLES = (
    "flows_enabled",
    "parallel_build",
    "worktree_isolation",
    "allow_generated_subdags",
    "session_reuse",
)


def _safe_yaml_load(text: str) -> Optional[dict]:
    """Parse YAML fail-soft: missing PyYAML or a malformed doc → None (mirrors
    `autopilot._safe_yaml_load`). Returns the parsed dict, or None when not a mapping."""
    try:
        import yaml  # noqa: F401
    except ImportError:
        return None
    try:
        data = yaml.safe_load(text)
    except Exception:  # noqa: BLE001 — any parse error is fail-soft, never propagated
        return None
    return data if isinstance(data, dict) else None


def _coerce_positive_int(value: object) -> Optional[int]:
    """Coerce to a positive int, or None when invalid/non-positive. Tunables that bound
    parallelism must be ≥ 1; a non-positive value is invalid (it would disable the engine)."""
    try:
        n = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def load_orchestration_config(forge_dir) -> OrchestrationConfig:
    """Read `<forge_dir>/config.yaml` → `orchestration:`; fail-soft to defaults. Never raises.

    Matches `autopilot.load_config`'s arg convention (the `.forge` directory) and its fail-soft
    discipline: an absent file, malformed YAML, or a non-mapping `orchestration` value all yield
    all-default config; an invalid individual key defaults while valid siblings survive.
    """
    cfg = OrchestrationConfig()
    path = Path(forge_dir) / "config.yaml"
    try:
        if not path.exists():
            return cfg
        data = _safe_yaml_load(path.read_text())
    except OSError:
        return cfg
    section = data.get("orchestration") if data else None
    if not isinstance(section, dict):
        return cfg

    # Strict bool semantics (mirror autopilot's `is True`): a real bool true enables a toggle;
    # a stray `1` / `"yes"` does not silently turn on a capability.
    for name in _TOGGLES:
        if section.get(name) is True:
            setattr(cfg, name, True)

    # Narration defaults ON; only an explicit bool `false` silences it (REQ-WF-011).
    if section.get("narrate") is False:
        cfg.narrate = False

    parallel = _coerce_positive_int(section.get("max_parallel"))
    if parallel is not None:
        cfg.max_parallel = parallel
    total = _coerce_positive_int(section.get("max_total"))
    if total is not None:
        cfg.max_total = total

    budget = section.get("max_budget_usd")
    if budget is not None:
        try:
            cfg.max_budget_usd = float(budget)
        except (TypeError, ValueError):
            pass  # invalid budget → default (None); valid siblings already applied
    return cfg
