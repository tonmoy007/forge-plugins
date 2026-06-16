"""Tests for scripts/skill_miner_v2.py (T-178 — REQ-SM-003, REQ-SM-004).

The v2 miner replaces the n-gram tool-name miner (mine-skills.py). It operates
over the SEMANTIC episodes produced by _trace_semantics (verb sequences), finds
ordered verb fragments recurring across >=k DISTINCT episodes, anti-unifies
their instances, and promotes a fragment to a candidate ONLY IF:
  (a) anti-unification yields a coherent parameterized skeleton (REQ-SM-003),
  (b) the source episodes are >=k distinct, AND
  (c) those episodes ended in SUCCESS (REQ-SM-004).

Acceptance (AC-SM-001/003/004):
  - a parameterized candidate from 3 distinct SUCCESSFUL episodes w/ differing
    names,
  - NOTHING from a control stream where Bash/Read/Write merely co-occur with no
    coherent shape,
  - a motif recurring 3x but in all-FAILED episodes is NOT promoted.

Stdlib only; deterministic; never raises.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_scripts = Path(__file__).resolve().parent.parent.parent / "scripts"

_ts_path = _scripts / "_trace_semantics.py"
_ts_spec = importlib.util.spec_from_file_location("_trace_semantics", _ts_path)
assert _ts_spec and _ts_spec.loader
ts_mod = importlib.util.module_from_spec(_ts_spec)
sys.modules["_trace_semantics"] = ts_mod
_ts_spec.loader.exec_module(ts_mod)

_au_path = _scripts / "_antiunify.py"
_au_spec = importlib.util.spec_from_file_location("_antiunify", _au_path)
assert _au_spec and _au_spec.loader
au_mod = importlib.util.module_from_spec(_au_spec)
sys.modules["_antiunify"] = au_mod
_au_spec.loader.exec_module(au_mod)

_sm_path = _scripts / "skill_miner_v2.py"
_sm_spec = importlib.util.spec_from_file_location("skill_miner_v2", _sm_path)
assert _sm_spec and _sm_spec.loader
sm_mod = importlib.util.module_from_spec(_sm_spec)
sys.modules["skill_miner_v2"] = sm_mod
_sm_spec.loader.exec_module(sm_mod)


# ---------------------------------------------------------------------------
# Helpers — build raw session-log records, run them through the real pipeline.
# ---------------------------------------------------------------------------


def _call(
    tool: str,
    file: str = "",
    success: bool = True,
    session: str = "s1",
    command: str = "",
) -> dict:
    rec: dict = {
        "ts": "2026-06-16T12:00:00Z",
        "session": session,
        "tool": tool,
        "file": file,
        "success": success,
        "stage": 6,
    }
    if command:
        rec["command"] = command
    return rec


def _fix_episode(src: str, test_cmd: str, test_file: str, session: str) -> list[dict]:
    """A successful failure->fix->regression episode (ends green)."""
    return [
        _call("Bash", success=False, session=session, command=test_cmd),
        _call("Read", file=src, session=session),
        _call("Edit", file=src, session=session),
        _call("Bash", success=True, session=session, command=test_cmd),
        _call("Write", file=test_file, session=session),
    ]


def _failed_episode(src: str, test_cmd: str, session: str) -> list[dict]:
    """A failure->patch episode that never goes green (incomplete / failed)."""
    return [
        _call("Bash", success=False, session=session, command=test_cmd),
        _call("Read", file=src, session=session),
        _call("Edit", file=src, session=session),
        _call("Bash", success=False, session=session, command=test_cmd),
    ]


def _episodes(records: list[dict]):
    return ts_mod.segment(ts_mod.enrich(records))


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_no_episodes_yields_no_candidates() -> None:
    assert sm_mod.mine_candidates([]) == []


def test_garbage_never_raises() -> None:
    assert sm_mod.mine_candidates(None) == []  # type: ignore[arg-type]


def test_single_episode_below_k_not_promoted() -> None:
    eps = _episodes(_fix_episode("src/a.py", "pytest a", "tests/test_a.py", "s1"))
    assert sm_mod.mine_candidates(eps) == []


# ---------------------------------------------------------------------------
# AC-SM-001/003 — a parameterized candidate from 3 distinct SUCCESS episodes
# ---------------------------------------------------------------------------


def test_three_distinct_successful_episodes_promote_one_candidate() -> None:
    records = (
        _fix_episode("src/a.py", "pytest a", "tests/test_a.py", "s1")
        + _fix_episode("src/b.py", "pytest b", "tests/test_b.py", "s2")
        + _fix_episode("src/c.py", "pytest c", "tests/test_c.py", "s3")
    )
    candidates = sm_mod.mine_candidates(_episodes(records))
    assert len(candidates) == 1
    cand = candidates[0]
    # the recurring failure->fix->regression shape
    assert [s.verb for s in cand.skeleton.steps] == [
        "run-tests",
        "inspect",
        "patch",
        "run-tests",
        "add-regression-test",
    ]
    # parameterized over the differing names
    assert len(cand.skeleton.parameters) >= 1
    assert cand.support >= sm_mod.MIN_DISTINCT_EPISODES


def test_candidate_records_distinct_episode_support() -> None:
    records = (
        _fix_episode("src/a.py", "pytest a", "tests/test_a.py", "s1")
        + _fix_episode("src/b.py", "pytest b", "tests/test_b.py", "s2")
        + _fix_episode("src/c.py", "pytest c", "tests/test_c.py", "s3")
    )
    candidates = sm_mod.mine_candidates(_episodes(records))
    assert candidates[0].support == 3


# ---------------------------------------------------------------------------
# AC-SM-001 — NOTHING from a control stream with no coherent shape
# ---------------------------------------------------------------------------


def test_control_stream_no_coherent_shape_yields_nothing() -> None:
    """Bash/Read/Write merely co-occur, in shuffled orders, no failure->fix
    shape, never reaching a coherent repeated procedure. Must emit nothing."""
    records = (
        [
            _call("Bash", command="ls", session="c1"),
            _call("Read", file="notes.txt", session="c1"),
            _call("Write", file="out.txt", session="c1"),
        ]
        + [
            _call("Read", file="a.txt", session="c2"),
            _call("Write", file="b.txt", session="c2"),
            _call("Bash", command="echo hi", session="c2"),
        ]
        + [
            _call("Write", file="z.txt", session="c3"),
            _call("Bash", command="pwd", session="c3"),
            _call("Read", file="y.txt", session="c3"),
        ]
    )
    candidates = sm_mod.mine_candidates(_episodes(records))
    assert candidates == []


# ---------------------------------------------------------------------------
# AC-SM-004 — a motif recurring 3x but in all-FAILED episodes is NOT promoted
# ---------------------------------------------------------------------------


def test_failed_episodes_are_not_promoted() -> None:
    records = (
        _failed_episode("src/a.py", "pytest a", "s1")
        + _failed_episode("src/b.py", "pytest b", "s2")
        + _failed_episode("src/c.py", "pytest c", "s3")
    )
    eps = _episodes(records)
    # sanity: the motif really does recur 3x (same verb shape, distinct episodes)
    assert len(eps) >= 3
    candidates = sm_mod.mine_candidates(eps)
    assert candidates == []


def test_mixed_two_success_one_fail_below_k_not_promoted() -> None:
    """Only 2 successful episodes share the shape (3rd failed) -> below k=3
    distinct SUCCESSFUL episodes -> not promoted."""
    records = (
        _fix_episode("src/a.py", "pytest a", "tests/test_a.py", "s1")
        + _fix_episode("src/b.py", "pytest b", "tests/test_b.py", "s2")
        + _failed_episode("src/c.py", "pytest c", "s3")
    )
    candidates = sm_mod.mine_candidates(_episodes(records))
    assert candidates == []


def test_default_k_is_three() -> None:
    assert sm_mod.MIN_DISTINCT_EPISODES == 3
