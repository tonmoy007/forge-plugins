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


# ---------------------------------------------------------------------------
# T-179 (REQ-SM-005, REQ-NF-017, AC-SM-005) — LLM induction with graceful
# degradation. The induction step turns each deterministic Candidate into an
# InducedSkill: a NAMED, parameterized procedure with a one-line third-person
# description and citations to the source trace lines. ONE cheap-model (haiku)
# background dispatch via the structured-output (--json-schema) path, cost- and
# capability-gated. When background/LLM is unavailable OR FORGE_NO_BACKGROUND=1
# OR the dispatch fails, the deterministic anti-unified skeleton (REQ-SM-003) is
# the proposal — never a hard failure, never raises.
#
# Tests MUST NOT touch the network: the dispatch boundary is injected
# (dispatch_fn) and the capability/kill-switch gate is parameterised so neither
# path shells out to `claude`.
# ---------------------------------------------------------------------------


def _three_episode_candidates():
    """A single coherent candidate from 3 distinct successful fix episodes."""
    records = (
        _fix_episode("src/a.py", "pytest a", "tests/test_a.py", "s1")
        + _fix_episode("src/b.py", "pytest b", "tests/test_b.py", "s2")
        + _fix_episode("src/c.py", "pytest c", "tests/test_c.py", "s3")
    )
    cands = sm_mod.mine_candidates(_episodes(records))
    assert len(cands) == 1
    return cands


class _Dispatched:
    """A stand-in DispatchResult — duck-typed like _background_agent.DispatchResult."""

    def __init__(self, status: str, result: str = "", reason: str = "", cost_usd=None):
        self.status = status
        self.result = result
        self.reason = reason
        self.cost_usd = cost_usd
        self.session_id = "sess-x"
        self.raw = None


def test_induce_empty_candidates_is_empty() -> None:
    assert sm_mod.induce([], forge_dir=Path("/nonexistent"), available=True) == []


def test_induce_garbage_never_raises() -> None:
    # None / wrong types degrade to [] rather than raising (REQ-NF-017).
    assert sm_mod.induce(None, forge_dir=None, available=True) == []  # type: ignore[arg-type]


def test_induce_uses_llm_procedure_when_dispatch_available(tmp_path) -> None:
    cands = _three_episode_candidates()
    captured: dict = {}

    def fake_dispatch(prompt, **kwargs):
        captured["prompt"] = prompt
        captured["kwargs"] = kwargs
        import json as _json

        payload = {
            "name": "red-green-regression-fix",
            "description": (
                "Drives a failing test to green by inspecting, patching the source, "
                "and adding a regression test."
            ),
            "procedure": [
                "Run the failing test to confirm red",
                "Inspect the implicated source file",
                "Patch the source file",
                "Re-run the test to confirm green",
                "Add a regression test",
            ],
            "citations": ["src/a.py:run-tests", "src/b.py:patch"],
        }
        return _Dispatched("ok", result=_json.dumps(payload))

    induced = sm_mod.induce(
        cands,
        forge_dir=tmp_path,
        available=True,
        dispatch_fn=fake_dispatch,
    )
    assert len(induced) == 1
    skill = induced[0]
    assert skill.source == "llm"
    assert skill.name == "red-green-regression-fix"
    assert "regression" in skill.description.lower()
    assert len(skill.procedure) == 5
    assert skill.citations  # non-empty provenance
    # the candidate's skeleton/motif is preserved as provenance
    assert skill.candidate is cands[0]

    # The dispatch went through the structured-output, cheap-model, gated path.
    kw = captured["kwargs"]
    assert kw.get("output_schema")  # --json-schema path
    assert kw.get("model") == sm_mod.INDUCTION_MODEL
    assert kw.get("feature") == "skill_induction"
    assert kw.get("max_budget_usd") is not None
    assert kw.get("forge_dir") == tmp_path


def test_induce_falls_back_to_skeleton_when_background_off() -> None:
    cands = _three_episode_candidates()

    def boom(*_a, **_k):  # must NEVER be called when capability is absent
        raise AssertionError("dispatch must not be called when background is off")

    induced = sm_mod.induce(
        cands,
        forge_dir=Path("/nonexistent"),
        available=False,
        dispatch_fn=boom,
    )
    assert len(induced) == 1
    skill = induced[0]
    assert skill.source == "deterministic"
    # the deterministic proposal still carries a name, third-person description,
    # a procedure derived from the skeleton verbs, and citations — never empty.
    assert skill.name
    assert skill.description
    assert skill.procedure == [s.verb for s in cands[0].skeleton.steps]
    assert skill.citations
    assert skill.candidate is cands[0]


def test_induce_falls_back_when_dispatch_returns_non_ok(tmp_path) -> None:
    cands = _three_episode_candidates()

    def skipped(*_a, **_k):
        return _Dispatched("skipped", reason="daily cap reached")

    induced = sm_mod.induce(
        cands, forge_dir=tmp_path, available=True, dispatch_fn=skipped
    )
    assert len(induced) == 1
    assert induced[0].source == "deterministic"


def test_induce_falls_back_when_dispatch_returns_garbage_json(tmp_path) -> None:
    cands = _three_episode_candidates()

    def garbage(*_a, **_k):
        return _Dispatched("ok", result="not json at all {")

    induced = sm_mod.induce(
        cands, forge_dir=tmp_path, available=True, dispatch_fn=garbage
    )
    assert len(induced) == 1
    assert induced[0].source == "deterministic"


def test_induce_falls_back_when_dispatch_raises(tmp_path) -> None:
    cands = _three_episode_candidates()

    def raiser(*_a, **_k):
        raise RuntimeError("network exploded")

    # induce must absorb a raising dispatch and degrade — never propagate.
    induced = sm_mod.induce(
        cands, forge_dir=tmp_path, available=True, dispatch_fn=raiser
    )
    assert len(induced) == 1
    assert induced[0].source == "deterministic"


def test_induction_model_is_cheap() -> None:
    assert sm_mod.INDUCTION_MODEL == "haiku"
