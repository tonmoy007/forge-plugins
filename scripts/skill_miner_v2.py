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

REQ-IDs: REQ-SM-003, REQ-SM-004. NF: REQ-NF-016 (stdlib, never-raises,
deterministic).
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# k — the minimum number of DISTINCT SUCCESSFUL episodes a motif must recur
# across before it can be promoted (REQ-SM-004; AC-SM-001/003/004).
MIN_DISTINCT_EPISODES = 3

# The outcome string _trace_semantics.segment stamps on a resolved episode.
_SUCCESS_OUTCOME = "success"


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
