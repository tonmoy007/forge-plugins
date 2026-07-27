#!/usr/bin/env python3
"""Replay verification before admit (T-181, REQ-SM-008).

Before a mined proposal is admitted/installed, it is **replayed** against the
source episodes it was induced from; it is admitted **only if** replay reproduces
the successful outcome. For coding, the oracle is the test suite: a source episode
must reproduce the **red->green** transition (a failing `run-tests` recovered to a
passing one — the failure->fix delta `_trace_semantics` already flags as
`has_fix_boundary`). When no runnable oracle exists in the source episodes, we
fall back to a **critic** check (one cheap-model background dispatch), which is
budget- and capability-gated and degrades gracefully.

This is the verify gate from SRS section 1.4 ("Verify before admit") and the
admit/install boundary that precedes `scripts/skill-approval.py`. It is a
**stdlib-only LIBRARY** on the never-raises discipline (REQ-NF-016): malformed,
missing, or empty input yields a conservative *not-admitted* result, never an
exception. The replay oracle is deterministic; the critic is an enhancement, not
a dependency (REQ-NF-017).

Why "replay" is an episode re-check, not a live re-run: the source evidence Forge
holds for a mined candidate is the segmented episode trace. Re-executing arbitrary
historical shell commands is neither safe nor reproducible on the background path,
so the oracle is whether the episodes the candidate was generalized from genuinely
demonstrate the successful outcome (red->green). A motif that only ever recurred in
episodes that never reached green is not admitted (AC-SM-008), exactly as the
success gate in `skill_miner_v2.mine_candidates` already rejects all-failed motifs
at mine time — this is the second, per-proposal line of defence before install.

REQ-IDs: REQ-SM-008. NF: REQ-NF-016 (stdlib, never-raises), REQ-NF-017 (graceful
degradation), REQ-NF-018 (bounded & gated), REQ-NF-019 (human-in-the-loop: never
auto-admit an unverified proposal).
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

# ---------------------------------------------------------------------------
# Sibling imports (hyphen-free names loaded via importlib so @dataclass under
# `from __future__ import annotations` can resolve; matches repo convention).
# ---------------------------------------------------------------------------


def _load_sibling(mod_name: str):
    """Load a sibling scripts/ module by name, registering it in sys.modules."""
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    path = Path(__file__).resolve().parent / f"{mod_name}.py"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


_ts = _load_sibling("_trace_semantics")
OUTCOME_PASS = _ts.OUTCOME_PASS
OUTCOME_FAIL = _ts.OUTCOME_FAIL

# The background adapter lives under hooks/, imported the same way skill_miner_v2
# does — fail-soft so a layout where hooks/ is absent never blocks the oracle path.
_PLUGIN_DIR = Path(__file__).resolve().parent.parent
if str(_PLUGIN_DIR / "hooks") not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR / "hooks"))
try:
    import _background_agent  # type: ignore  # noqa: E402
except Exception:  # noqa: BLE001 — critic degrades to unverified if absent
    _background_agent = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The verb _trace_semantics stamps on a test-suite run (the runnable oracle).
_RUN_TESTS_VERB = "run-tests"

# The critic is a cheap, mechanical "is this a coherent reusable workflow" check —
# pin the cheap model (REQ-NF-018; matches INDUCTION_MODEL / DREAMER_MODEL).
CRITIC_MODEL = "haiku"

# Per-dispatch hard $ ceiling for one critic call, complementing the daily
# _cost_cap ledger gate (REQ-NF-018, --max-budget-usd).
CRITIC_MAX_BUDGET_USD = 0.05

# Verification methods, recorded on the result for observability.
METHOD_REPLAY = "replay"
METHOD_CRITIC = "critic"
METHOD_UNVERIFIED = "unverified"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class VerifyResult:
    """Outcome of verifying one proposal before admit (REQ-SM-008).

    `admitted` is the gate decision. `method` is how it was decided:
    "replay" (the test-suite oracle was runnable and reproduced red->green),
    "critic" (no oracle; a critic pass decided), or "unverified" (no oracle and
    no critic capability — conservatively not admitted). `reason` is a
    human-readable explanation for inspection.
    """

    admitted: bool
    method: str
    reason: str


# ---------------------------------------------------------------------------
# Replay oracle (deterministic)
# ---------------------------------------------------------------------------


def _episode_has_test_oracle(episode: object) -> bool:
    """True iff the episode contains a runnable test-suite signal (a `run-tests`
    verb), i.e. a coding oracle exists to replay against."""
    calls = getattr(episode, "calls", None)
    if not isinstance(calls, (list, tuple)):
        return False
    return any(getattr(c, "verb", None) == _RUN_TESTS_VERB for c in calls)


def _episode_reproduces_red_green(episode: object) -> bool:
    """True iff the episode reproduces the red->green transition.

    `_trace_semantics.segment` already computes `has_fix_boundary` (a failing
    `run-tests` recovered to a passing one) and stamps `outcome="success"` on an
    episode that ended green. Both must hold: the oracle is the test suite going
    red then green.
    """
    if getattr(episode, "outcome", None) != "success":
        return False
    return bool(getattr(episode, "has_fix_boundary", False))


def _replay(episodes: object) -> Optional[bool]:
    """Run the deterministic test-suite oracle over the source episodes.

    Returns:
      - True  — a runnable oracle exists AND at least one source episode
                reproduces red->green (admit on replay),
      - False — a runnable oracle exists but NO source episode reproduces
                red->green (reject on replay; the critic must not rescue it),
      - None  — no runnable oracle exists in any source episode (defer to the
                critic fallback).
    Never raises.
    """
    if not isinstance(episodes, (list, tuple)) or not episodes:
        return False
    saw_oracle = False
    for episode in episodes:
        if not _episode_has_test_oracle(episode):
            continue
        saw_oracle = True
        if _episode_reproduces_red_green(episode):
            return True
    return False if saw_oracle else None


# ---------------------------------------------------------------------------
# Critic fallback (REQ-SM-008 "when no runnable oracle exists, fall back to a
# critic check") — one cheap-model, structured-output, gated background dispatch.
# ---------------------------------------------------------------------------

# Structured-output contract handed to the critic via `--json-schema`. A malformed
# reply simply fails validation and degrades to not-admitted.
CRITIC_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "admit": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["admit", "reason"],
    "additionalProperties": False,
}


def _critic_prompt(skill: object) -> str:
    """Build the critic prompt for one proposal whose source episodes have no
    runnable test oracle. The critic judges whether the procedure is a coherent,
    reusable workflow worth admitting (a conservative second opinion)."""
    name = str(getattr(skill, "name", "") or "(unnamed)")
    description = str(getattr(skill, "description", "") or "")
    procedure = getattr(skill, "procedure", None) or []
    steps = "\n".join(
        f"  {i}. {str(s).strip()}" for i, s in enumerate(procedure, start=1)
    ) or "  (no steps recorded)"
    return (
        "You are Forge's skill-verification critic. A workflow was mined from "
        "repeated successful episodes, but those episodes have NO runnable test "
        "oracle to replay, so judge it directly. Admit it ONLY if it is a coherent, "
        "genuinely reusable problem-solving procedure (not a coincidental sequence "
        "of generic actions). Return ONLY the structured object.\n\n"
        f"Name: {name}\n"
        f"Description: {description}\n"
        "Procedure:\n" + steps
    )


def _parse_critic_result(result: object) -> Optional[bool]:
    """Parse a critic dispatch's structured `result` into a bool admit decision,
    or None if unusable (so the caller degrades to not-admitted). Never raises."""
    if not isinstance(result, str) or not result.strip():
        return None
    try:
        data = json.loads(result)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    admit = data.get("admit")
    if not isinstance(admit, bool):
        return None
    return admit


def _resolve_dispatch(dispatch_fn: Optional[Callable]) -> Optional[Callable]:
    """Resolve the dispatch function: the injected one, else the background
    adapter's `dispatch`, else None."""
    if dispatch_fn is not None:
        return dispatch_fn
    if _background_agent is not None:
        return getattr(_background_agent, "dispatch", None)
    return None


def _critic_gate_open(
    *, available: bool, fn: Optional[Callable], forge_dir: object
) -> bool:
    """Capability / kill-switch gate for the critic (REQ-NF-017, REQ-NF-018)."""
    return (
        bool(available)
        and os.environ.get("FORGE_NO_BACKGROUND") != "1"
        and fn is not None
        and forge_dir is not None
    )


def _run_critic(
    skill: object,
    *,
    fn: Callable,
    forge_dir: object,
    model: str,
    max_budget_usd: Optional[float],
    cwd: Optional[str],
    claude_bin: Optional[str],
) -> VerifyResult:
    """One cost/capability-gated critic dispatch. Any failure mode degrades to a
    not-admitted critic result. Never raises."""
    try:
        res = fn(
            _critic_prompt(skill),
            forge_dir=forge_dir,
            feature="skill_verify",
            model=model,
            output_schema=CRITIC_SCHEMA,
            max_budget_usd=max_budget_usd,
            cwd=cwd,
            claude_bin=claude_bin,
        )
    except Exception:  # noqa: BLE001 — verify must never raise (REQ-NF-017)
        return VerifyResult(False, METHOD_CRITIC, "critic dispatch raised; not admitted")

    if getattr(res, "status", None) != "ok":
        reason = str(getattr(res, "reason", "") or "dispatch not ok")
        return VerifyResult(False, METHOD_CRITIC, f"critic unavailable ({reason}); not admitted")
    admit = _parse_critic_result(getattr(res, "result", None))
    if admit is None:
        return VerifyResult(False, METHOD_CRITIC, "critic returned unusable output; not admitted")
    return VerifyResult(
        admit,
        METHOD_CRITIC,
        "critic admitted" if admit else "critic rejected",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def verify(
    skill: object,
    episodes: object,
    *,
    forge_dir: object,
    available: bool,
    dispatch_fn: Optional[Callable] = None,
    model: str = CRITIC_MODEL,
    max_budget_usd: Optional[float] = CRITIC_MAX_BUDGET_USD,
    cwd: Optional[str] = None,
    claude_bin: Optional[str] = None,
) -> VerifyResult:
    """Verify one proposal against its source episodes before admit (REQ-SM-008).

    Replay first: if any source episode has a runnable test oracle, admit iff at
    least one reproduces red->green; if an oracle exists but none reproduce it,
    reject (the critic does NOT rescue a present-but-failing oracle).

    Critic fallback: when NO source episode has a runnable oracle, run one
    cheap-model, structured-output, budget/capability-gated critic dispatch via
    `dispatch_fn` (default `_background_agent.dispatch`). When the critic gate is
    closed (no capability, `FORGE_NO_BACKGROUND=1`, no dispatch fn, no forge_dir),
    the proposal is conservatively NOT admitted ("unverified") — never auto-admit
    an unverified proposal (REQ-NF-019).

    Never raises (REQ-NF-016/017): malformed/empty input yields not-admitted.
    """
    replayed = _replay(episodes)
    if replayed is True:
        return VerifyResult(True, METHOD_REPLAY, "source episodes reproduce red->green")
    if replayed is False:
        return VerifyResult(False, METHOD_REPLAY, "source episodes do not reproduce red->green")

    # replayed is None — no runnable oracle. Fall back to the critic.
    fn = _resolve_dispatch(dispatch_fn)
    if not _critic_gate_open(available=available, fn=fn, forge_dir=forge_dir):
        return VerifyResult(
            False,
            METHOD_UNVERIFIED,
            "no runnable oracle and no critic capability; not admitted",
        )
    assert fn is not None  # guaranteed by _critic_gate_open
    return _run_critic(
        skill,
        fn=fn,
        forge_dir=forge_dir,
        model=model,
        max_budget_usd=max_budget_usd,
        cwd=cwd,
        claude_bin=claude_bin,
    )


def admit(
    pairs: object,
    *,
    forge_dir: object,
    available: bool,
    dispatch_fn: Optional[Callable] = None,
    model: str = CRITIC_MODEL,
    max_budget_usd: Optional[float] = CRITIC_MAX_BUDGET_USD,
    cwd: Optional[str] = None,
    claude_bin: Optional[str] = None,
) -> list:
    """Verify a batch of `(skill, source_episodes)` pairs; return only the skills
    whose proposal passes verification, in input order (AC-SM-008). Never raises.

    A malformed pair is skipped (treated as not admitted). The shared gate
    arguments are threaded straight through to `verify`.
    """
    if not isinstance(pairs, (list, tuple)) or not pairs:
        return []
    admitted: list = []
    for pair in pairs:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        skill, episodes = pair
        result = verify(
            skill,
            episodes,
            forge_dir=forge_dir,
            available=available,
            dispatch_fn=dispatch_fn,
            model=model,
            max_budget_usd=max_budget_usd,
            cwd=cwd,
            claude_bin=claude_bin,
        )
        if result.admitted:
            admitted.append(skill)
    return admitted
