#!/usr/bin/env python3
"""Semantic, success-gated, anti-unification skill miner (T-178, REQ-SM-003/004).

This is the v2 miner that conceptually replaces the n-gram tool-name miner
(`mine-skills.py`). It is a **stdlib-only, deterministic, never-raises LIBRARY**
that operates over the **semantic episodes** produced by `_trace_semantics`
(verb sequences), not over raw tool names.

Pipeline (`mine_candidates`):
  1. **Success gate (REQ-SM-004).** Keep only episodes that ended in SUCCESS.
     A motif recurring only in failed/incomplete episodes is never promoted —
     bare frequency is never sufficient.
  2. **Recurrence over distinct episodes (REQ-SM-003).** Group the successful
     episodes by their ordered *verb sequence* (the motif). A motif qualifies
     only when it recurs across **>=`MIN_DISTINCT_EPISODES` distinct episodes**.
  3. **Anti-unification coherence gate (REQ-SM-003).** Anti-unify the grouped
     instances via `_antiunify.antiunify`. Promote the motif to a candidate
     **only if** anti-unification yields a coherent parameterized skeleton.
     Coincidental co-occurrence (Bash/Read/Write with no shared parameterizable
     shape) fails this gate and produces nothing.

`MIN_DISTINCT_EPISODES` is the success+coherence gate's `k` (default 3 distinct
successful episodes, per AC-SM-001/003/004).

Induction (`induce`, T-179, REQ-SM-005)
---------------------------------------
For each deterministic `Candidate`, `induce` attempts ONE cheap-model (`haiku`)
background dispatch via `_background_agent.dispatch` using the structured-output
(`--json-schema`) path, cost- and capability-gated. The agent de-specializes the
anti-unified skeleton into a NAMED parameterized procedure with a one-line
THIRD-PERSON description and citations to the source trace lines, returned as an
`InducedSkill`.

**Graceful degradation (REQ-NF-017, CRITICAL):** when background/LLM is
unavailable, `FORGE_NO_BACKGROUND=1`, the capability gate is false, or the
dispatch fails for any reason, `induce` emits the deterministic anti-unified
skeleton as the proposal (`source="deterministic"`) — never a hard failure,
never an exception. LLM induction is an enhancement, not a dependency. The
dispatch boundary is injected (`dispatch_fn`) so it is fully mockable and the
hot path never raises.

REQ-IDs: REQ-SM-003, REQ-SM-004, REQ-SM-005. NF: REQ-NF-016 (stdlib,
never-raises, deterministic), REQ-NF-017 (graceful degradation),
REQ-NF-018 (bounded & gated).
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

# ---------------------------------------------------------------------------
# Sibling library import (hyphen-free names, loaded via importlib so the module
# works regardless of how the package is laid out; matches repo convention).
# ---------------------------------------------------------------------------


def _load_sibling(mod_name: str):
    """Load a sibling scripts/ module by name, registering it in sys.modules.

    Registration is required so @dataclass under `from __future__ import
    annotations` in the sibling can resolve its own module. Never raises here;
    a missing sibling is a programmer error surfaced at import time only.
    """
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    path = Path(__file__).resolve().parent / f"{mod_name}.py"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


_antiunify = _load_sibling("_antiunify")
Skeleton = _antiunify.Skeleton

# The background adapter lives under hooks/, not scripts/. Import it the same way
# the other miner workers do (dreamer.py, skill_miner_bg.py) — fail-soft, so a
# layout where hooks/ is absent never blocks the deterministic path (REQ-NF-017).
_PLUGIN_DIR = Path(__file__).resolve().parent.parent
if str(_PLUGIN_DIR / "hooks") not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR / "hooks"))
try:
    import _background_agent  # type: ignore  # noqa: E402 (the single background adapter)
except Exception:  # noqa: BLE001 — induction degrades to deterministic if absent
    _background_agent = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# k — the minimum number of DISTINCT SUCCESSFUL episodes a motif must recur
# across before it can be promoted (REQ-SM-004; AC-SM-001/003/004).
MIN_DISTINCT_EPISODES = 3

# The outcome string _trace_semantics.segment stamps on a resolved episode.
_SUCCESS_OUTCOME = "success"

# Induction is a cheap, mechanical de-specialization task — pin the cheap model
# (REQ-NF-018; matches DREAMER_MODEL / MINER_MODEL). Override via induce(model=).
INDUCTION_MODEL = "haiku"

# Per-dispatch hard $ ceiling for one induction call, complementing the daily
# _cost_cap ledger gate (REQ-NF-018, --max-budget-usd). Generous for one cheap
# structured-output call; the real bound is the cost cap.
INDUCTION_MAX_BUDGET_USD = 0.05


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Candidate:
    """A promoted skill candidate.

    `skeleton` is the anti-unified parameterized procedure. `support` is the
    number of distinct successful episodes that anti-unified into it. `motif` is
    the shared verb sequence (provenance / stable identity for the candidate).
    """

    skeleton: "Skeleton"
    support: int
    motif: tuple[str, ...]


@dataclass
class InducedSkill:
    """A de-specialized, named proposal derived from a `Candidate` (REQ-SM-005).

    `name` is a kebab-case identifier; `description` is a one-line THIRD-PERSON
    statement of what the procedure does + when to use it; `procedure` is the
    ordered, parameterized steps; `citations` point back to the source trace
    lines / parameter bindings that justify it. `source` is "llm" when the
    cheap-model induction succeeded, or "deterministic" when it degraded to the
    anti-unified skeleton (REQ-NF-017). `candidate` is the originating candidate
    (provenance: skeleton, support, motif).
    """

    name: str
    description: str
    procedure: list[str]
    citations: list[str]
    source: str
    candidate: "Candidate"


# ---------------------------------------------------------------------------
# Mining
# ---------------------------------------------------------------------------


def _episode_verbs(episode: object) -> tuple[str, ...]:
    """Return an episode's ordered verb sequence, or () if malformed."""
    calls = getattr(episode, "calls", None)
    if not isinstance(calls, (list, tuple)):
        return ()
    verbs: list[str] = []
    for call in calls:
        verb = getattr(call, "verb", None)
        if not isinstance(verb, str) or not verb:
            return ()
        verbs.append(verb)
    return tuple(verbs)


def _is_successful(episode: object) -> bool:
    """True iff the episode ended in success (REQ-SM-004 gate)."""
    return getattr(episode, "outcome", None) == _SUCCESS_OUTCOME


def mine_candidates(episodes: object) -> list[Candidate]:
    """Mine skill candidates from segmented episodes. Never raises.

    Returns a deterministic, motif-sorted list of `Candidate`s. Empty when no
    motif clears the success + distinct-recurrence + anti-unification gates.
    """
    if not isinstance(episodes, (list, tuple)):
        return []

    # Gate 1: success only. Group surviving episodes by their verb-sequence motif.
    motif_to_episodes: dict[tuple[str, ...], list] = {}
    for episode in episodes:
        if not _is_successful(episode):
            continue
        verbs = _episode_verbs(episode)
        if not verbs:
            continue
        motif_to_episodes.setdefault(verbs, []).append(episode)

    candidates: list[Candidate] = []
    # Deterministic order: by motif (lexicographic on the verb tuple).
    for motif in sorted(motif_to_episodes):
        group = motif_to_episodes[motif]
        # Gate 2: >=k distinct successful episodes.
        if len(group) < MIN_DISTINCT_EPISODES:
            continue
        instances = [list(getattr(ep, "calls", [])) for ep in group]
        # Gate 3: anti-unification must yield a coherent skeleton.
        skeleton = _antiunify.antiunify(instances)
        if skeleton is None:
            continue
        candidates.append(
            Candidate(skeleton=skeleton, support=len(group), motif=motif)
        )

    return candidates


# ---------------------------------------------------------------------------
# Induction (REQ-SM-005) — de-specialize each candidate into a named procedure
# ---------------------------------------------------------------------------

# The structured-output contract handed to the cheap model via `--json-schema`.
# Constrains the agent's result to exactly the fields `induce` consumes, so a
# malformed reply is impossible to misread (it would simply fail validation and
# fall back to the deterministic skeleton).
INDUCTION_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "procedure": {"type": "array", "items": {"type": "string"}},
        "citations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["name", "description", "procedure", "citations"],
    "additionalProperties": False,
}


def _skeleton_citations(candidate: "Candidate") -> list[str]:
    """Deterministic provenance for a candidate: the per-instance parameter
    bindings that justify the generalization, formatted `param=value`.

    Always non-empty for a real candidate (the motif itself is cited even when a
    skeleton has no diverging parameters)."""
    skeleton = getattr(candidate, "skeleton", None)
    bindings = getattr(skeleton, "bindings", None) if skeleton is not None else None
    cites: list[str] = []
    if isinstance(bindings, dict):
        for name in sorted(bindings):
            for value in bindings[name]:
                cites.append(f"{name}={value}")
    if not cites:
        # No diverging parameters — cite the motif itself as provenance.
        cites.append("motif=" + "->".join(getattr(candidate, "motif", ()) or ()))
    return cites


def _deterministic_skill(candidate: "Candidate") -> InducedSkill:
    """The anti-unified skeleton AS the proposal — the graceful-degradation
    output (REQ-NF-017). Named from the motif, third-person description, the
    skeleton verbs as the procedure, deterministic bindings as citations."""
    motif = tuple(getattr(candidate, "motif", ()) or ())
    name = "-".join(motif) if motif else "recurring-procedure"
    description = (
        "Performs the recurring "
        + (" then ".join(motif) if motif else "procedure")
        + f" workflow observed across {getattr(candidate, 'support', 0)} successful episodes."
    )
    skeleton = getattr(candidate, "skeleton", None)
    steps = getattr(skeleton, "steps", []) if skeleton is not None else []
    procedure = [getattr(s, "verb", "") for s in steps]
    return InducedSkill(
        name=name,
        description=description,
        procedure=procedure,
        citations=_skeleton_citations(candidate),
        source="deterministic",
        candidate=candidate,
    )


def _induction_prompt(candidate: "Candidate") -> str:
    """Build the de-specialization prompt for one candidate. The skeleton +
    bindings are the evidence the agent generalizes and cites."""
    skeleton = getattr(candidate, "skeleton", None)
    steps = getattr(skeleton, "steps", []) if skeleton is not None else []
    lines = []
    for i, step in enumerate(steps, start=1):
        args = getattr(step, "args", {}) or {}
        arg_str = ", ".join(f"{k}={v}" for k, v in sorted(args.items()))
        lines.append(f"  {i}. {getattr(step, 'verb', '')}({arg_str})")
    bindings = getattr(skeleton, "bindings", {}) if skeleton is not None else {}
    binding_lines = [
        f"  {name}: {bindings[name]}" for name in sorted(bindings)
    ] or ["  (no diverging parameters)"]
    return (
        "You are Forge's skill-inducer. Below is an anti-unified procedure mined from "
        f"{getattr(candidate, 'support', 0)} distinct SUCCESSFUL episodes (the differing "
        "literals are already lifted to parameters P1, P2, ...). De-specialize it into a "
        "reusable skill: give it a short kebab-case NAME, a one-line THIRD-PERSON "
        "description (what it does AND when to use it), restate the PROCEDURE as clear "
        "imperative steps that reference the parameters, and list CITATIONS back to the "
        "source bindings that justify the generalization. Return ONLY the structured "
        "object.\n\n"
        "Parameterized steps:\n" + "\n".join(lines) + "\n\n"
        "Parameter bindings (per-episode source values):\n" + "\n".join(binding_lines)
    )


def _parse_induction_result(result: object, candidate: "Candidate") -> Optional[InducedSkill]:
    """Parse a dispatch's structured `result` into an InducedSkill, or None if it
    is unusable (so the caller degrades). Never raises."""
    if not isinstance(result, str) or not result.strip():
        return None
    try:
        data = json.loads(result)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    name = data.get("name")
    description = data.get("description")
    procedure = data.get("procedure")
    citations = data.get("citations")
    if not isinstance(name, str) or not name.strip():
        return None
    if not isinstance(description, str) or not description.strip():
        return None
    if not isinstance(procedure, list) or not procedure:
        return None
    proc = [str(s) for s in procedure]
    cites = [str(c) for c in citations] if isinstance(citations, list) else []
    if not cites:
        cites = _skeleton_citations(candidate)
    return InducedSkill(
        name=name.strip(),
        description=description.strip(),
        procedure=proc,
        citations=cites,
        source="llm",
        candidate=candidate,
    )


def induce(
    candidates: object,
    *,
    forge_dir: object,
    available: bool,
    dispatch_fn: Optional[Callable] = None,
    model: str = INDUCTION_MODEL,
    max_budget_usd: Optional[float] = INDUCTION_MAX_BUDGET_USD,
    cwd: Optional[str] = None,
    claude_bin: Optional[str] = None,
) -> list[InducedSkill]:
    """De-specialize each candidate into a named `InducedSkill` (REQ-SM-005). Never raises.

    For each candidate, ONE cheap-model background dispatch via `dispatch_fn`
    (default `_background_agent.dispatch`) on the structured-output (`--json-schema`)
    path, cost- and capability-gated. Returns one `InducedSkill` per candidate, in
    candidate order.

    Graceful degradation (REQ-NF-017): the deterministic anti-unified skeleton is
    emitted (`source="deterministic"`) when:
      - `available` is False (caller's capability gate / kill switch), OR
      - `FORGE_NO_BACKGROUND=1`, OR
      - no dispatch function is resolvable, OR
      - the dispatch returns non-"ok", malformed output, or raises.
    LLM induction is an enhancement, never a hard dependency.
    """
    if not isinstance(candidates, (list, tuple)):
        return []
    cands = [c for c in candidates if c is not None]
    if not cands:
        return []

    # Capability / kill-switch gate (REQ-NF-017, REQ-NF-018). When the substrate
    # is off, never even attempt a dispatch — degrade every candidate.
    fn = dispatch_fn
    if fn is None and _background_agent is not None:
        fn = getattr(_background_agent, "dispatch", None)
    gate_open = (
        bool(available)
        and os.environ.get("FORGE_NO_BACKGROUND") != "1"
        and fn is not None
        and forge_dir is not None
    )
    if not gate_open:
        return [_deterministic_skill(c) for c in cands]

    induced: list[InducedSkill] = []
    for candidate in cands:
        induced.append(
            _induce_one(
                candidate,
                fn=fn,
                forge_dir=forge_dir,
                model=model,
                max_budget_usd=max_budget_usd,
                cwd=cwd,
                claude_bin=claude_bin,
            )
        )
    return induced


def _induce_one(
    candidate: "Candidate",
    *,
    fn: Callable,
    forge_dir: object,
    model: str,
    max_budget_usd: Optional[float],
    cwd: Optional[str],
    claude_bin: Optional[str],
) -> InducedSkill:
    """One cost/capability-gated induction dispatch for a single candidate. Any
    failure mode degrades to the deterministic skeleton. Never raises."""
    try:
        res = fn(
            _induction_prompt(candidate),
            forge_dir=forge_dir,
            feature="skill_induction",
            model=model,
            output_schema=INDUCTION_SCHEMA,
            max_budget_usd=max_budget_usd,
            cwd=cwd,
            claude_bin=claude_bin,
        )
    except Exception:  # noqa: BLE001 — induction must never raise (REQ-NF-017)
        return _deterministic_skill(candidate)

    if getattr(res, "status", None) != "ok":
        return _deterministic_skill(candidate)
    parsed = _parse_induction_result(getattr(res, "result", None), candidate)
    return parsed if parsed is not None else _deterministic_skill(candidate)
