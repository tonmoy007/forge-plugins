"""Tests for scripts/skill_verify.py (T-181 — REQ-SM-008, AC-SM-008).

Before a mined proposal is admitted/installed, it is REPLAYED against the source
episodes it was induced from. A candidate is admitted ONLY IF replay reproduces
the successful outcome — for coding, the oracle is the test suite (red->green).
When no runnable oracle exists in the source episodes, verification falls back to
a CRITIC check (an LLM pass), which is budget/capability gated and fully mockable.

Acceptance (AC-SM-008):
  - a candidate that FAILS replay (its source episodes do not reproduce red->green)
    is NOT admitted,
  - a candidate that PASSES replay (its source episodes do reproduce red->green)
    IS admitted.

Stdlib only; deterministic on the oracle path; never raises; no network (the
critic dispatch boundary is injected and mocked).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_scripts = Path(__file__).resolve().parent.parent.parent / "scripts"


def _load(mod_name: str):
    path = _scripts / f"{mod_name}.py"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


ts_mod = _load("_trace_semantics")
au_mod = _load("_antiunify")
sm_mod = _load("skill_miner_v2")
sv_mod = _load("skill_verify")


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
    """A successful failure->fix->regression episode (red then green)."""
    return [
        _call("Bash", success=False, session=session, command=test_cmd),
        _call("Read", file=src, session=session),
        _call("Edit", file=src, session=session),
        _call("Bash", success=True, session=session, command=test_cmd),
        _call("Write", file=test_file, session=session),
    ]


def _no_oracle_episode(src: str, session: str) -> list[dict]:
    """A successful episode with NO test-suite signal (no red->green oracle):
    just inspect + edit that never runs tests. Ends 'incomplete' (no passing
    test), so it is not even a mining candidate — used to drive the critic
    fallback directly through `verify`."""
    return [
        _call("Read", file=src, session=session),
        _call("Edit", file=src, session=session),
    ]


def _episodes(records: list[dict]):
    return ts_mod.segment(ts_mod.enrich(records))


def _candidate_and_episodes():
    """One coherent candidate from 3 distinct successful red->green episodes,
    plus the segmented source episodes it was mined from."""
    records = (
        _fix_episode("src/a.py", "pytest a", "tests/test_a.py", "s1")
        + _fix_episode("src/b.py", "pytest b", "tests/test_b.py", "s2")
        + _fix_episode("src/c.py", "pytest c", "tests/test_c.py", "s3")
    )
    eps = _episodes(records)
    cands = sm_mod.mine_candidates(eps)
    assert len(cands) == 1
    induced = sm_mod.induce(cands, forge_dir=Path("/nonexistent"), available=False)
    return induced[0], eps


class _Dispatched:
    """Duck-typed stand-in for _background_agent.DispatchResult."""

    def __init__(self, status: str, result: str = "", reason: str = ""):
        self.status = status
        self.result = result
        self.reason = reason
        self.session_id = "sess-x"
        self.cost_usd = None
        self.raw = None


# ---------------------------------------------------------------------------
# Edge cases — never raises (REQ-NF-016).
# ---------------------------------------------------------------------------


def test_verify_garbage_inputs_never_raise() -> None:
    res = sv_mod.verify(None, None, forge_dir=None, available=False)  # type: ignore[arg-type]
    assert res.admitted is False


def test_verify_no_source_episodes_is_not_admitted() -> None:
    skill, _eps = _candidate_and_episodes()
    res = sv_mod.verify(skill, [], forge_dir=None, available=False)
    assert res.admitted is False


# ---------------------------------------------------------------------------
# AC-SM-008 — replay oracle (test suite red->green).
# ---------------------------------------------------------------------------


def test_passing_replay_is_admitted() -> None:
    """A candidate whose source episodes reproduce red->green IS admitted, with
    no critic needed (the oracle is runnable)."""
    skill, eps = _candidate_and_episodes()

    def must_not_dispatch(*_a, **_k):
        raise AssertionError("critic must not run when a test oracle exists")

    res = sv_mod.verify(
        skill, eps, forge_dir=Path("/tmp"), available=True, dispatch_fn=must_not_dispatch
    )
    assert res.admitted is True
    assert res.method == "replay"


def test_failing_replay_is_not_admitted() -> None:
    """The source episodes have a test oracle but it does NOT reproduce
    red->green (every run is a failure) -> NOT admitted, and the critic is NOT
    used to rescue a present-but-failing oracle."""
    records = (
        [
            _call("Bash", success=False, session="s1", command="pytest a"),
            _call("Read", file="src/a.py", session="s1"),
            _call("Edit", file="src/a.py", session="s1"),
            _call("Bash", success=False, session="s1", command="pytest a"),
        ]
        + [
            _call("Bash", success=False, session="s2", command="pytest b"),
            _call("Read", file="src/b.py", session="s2"),
            _call("Edit", file="src/b.py", session="s2"),
            _call("Bash", success=False, session="s2", command="pytest b"),
        ]
    )
    eps = _episodes(records)
    skill, _ = _candidate_and_episodes()

    def must_not_dispatch(*_a, **_k):
        raise AssertionError("critic must not rescue a failing oracle")

    res = sv_mod.verify(
        skill, eps, forge_dir=Path("/tmp"), available=True, dispatch_fn=must_not_dispatch
    )
    assert res.admitted is False
    assert res.method == "replay"


# ---------------------------------------------------------------------------
# Critic fallback — no runnable oracle in the source episodes.
# ---------------------------------------------------------------------------


def test_critic_admits_when_no_oracle_and_critic_approves(tmp_path) -> None:
    """No test oracle in the episodes -> fall back to the critic. A positive
    critic verdict admits."""
    skill, _ = _candidate_and_episodes()
    no_oracle = _episodes(
        _no_oracle_episode("src/a.py", "s1") + _no_oracle_episode("src/b.py", "s2")
    )
    captured: dict = {}

    def fake_dispatch(prompt, **kwargs):
        captured["kwargs"] = kwargs
        import json as _json

        return _Dispatched("ok", result=_json.dumps({"admit": True, "reason": "coherent"}))

    res = sv_mod.verify(
        skill, no_oracle, forge_dir=tmp_path, available=True, dispatch_fn=fake_dispatch
    )
    assert res.admitted is True
    assert res.method == "critic"
    # The critic ran on the cheap-model, structured-output, gated path.
    kw = captured["kwargs"]
    assert kw.get("output_schema")
    assert kw.get("model") == sv_mod.CRITIC_MODEL
    assert kw.get("feature") == "skill_verify"
    assert kw.get("max_budget_usd") is not None
    assert kw.get("forge_dir") == tmp_path


def test_critic_rejects_when_no_oracle_and_critic_disapproves(tmp_path) -> None:
    skill, _ = _candidate_and_episodes()
    no_oracle = _episodes(
        _no_oracle_episode("src/a.py", "s1") + _no_oracle_episode("src/b.py", "s2")
    )

    def fake_dispatch(prompt, **kwargs):
        import json as _json

        return _Dispatched("ok", result=_json.dumps({"admit": False, "reason": "noise"}))

    res = sv_mod.verify(
        skill, no_oracle, forge_dir=tmp_path, available=True, dispatch_fn=fake_dispatch
    )
    assert res.admitted is False
    assert res.method == "critic"


# ---------------------------------------------------------------------------
# Graceful degradation of the critic (REQ-NF-017) — no network, never raises.
# ---------------------------------------------------------------------------


def test_no_oracle_and_critic_unavailable_is_not_admitted() -> None:
    """No runnable oracle AND no critic capability -> conservatively NOT
    admitted (human-in-the-loop: never auto-admit unverified)."""
    skill, _ = _candidate_and_episodes()
    no_oracle = _episodes(
        _no_oracle_episode("src/a.py", "s1") + _no_oracle_episode("src/b.py", "s2")
    )

    def boom(*_a, **_k):
        raise AssertionError("critic must not run when capability is off")

    res = sv_mod.verify(
        skill, no_oracle, forge_dir=Path("/nonexistent"), available=False, dispatch_fn=boom
    )
    assert res.admitted is False
    assert res.method == "unverified"


def test_no_oracle_and_critic_raises_degrades_not_admitted(tmp_path) -> None:
    skill, _ = _candidate_and_episodes()
    no_oracle = _episodes(
        _no_oracle_episode("src/a.py", "s1") + _no_oracle_episode("src/b.py", "s2")
    )

    def raiser(*_a, **_k):
        raise RuntimeError("network exploded")

    res = sv_mod.verify(
        skill, no_oracle, forge_dir=tmp_path, available=True, dispatch_fn=raiser
    )
    assert res.admitted is False
    assert res.method == "critic"


def test_no_oracle_and_critic_returns_garbage_not_admitted(tmp_path) -> None:
    skill, _ = _candidate_and_episodes()
    no_oracle = _episodes(
        _no_oracle_episode("src/a.py", "s1") + _no_oracle_episode("src/b.py", "s2")
    )

    def garbage(*_a, **_k):
        return _Dispatched("ok", result="not json {")

    res = sv_mod.verify(
        skill, no_oracle, forge_dir=tmp_path, available=True, dispatch_fn=garbage
    )
    assert res.admitted is False
    assert res.method == "critic"


def test_critic_model_is_cheap() -> None:
    assert sv_mod.CRITIC_MODEL == "haiku"


# ---------------------------------------------------------------------------
# Batch admit helper — filter a list of induced skills to the admitted ones.
# ---------------------------------------------------------------------------


def test_admit_filters_to_verified(tmp_path) -> None:
    """admit() pairs each induced skill with its source episodes and returns
    only those that pass verification (AC-SM-008)."""
    good_skill, good_eps = _candidate_and_episodes()

    # A second skill whose source episodes fail replay (never green).
    bad_records = (
        [
            _call("Bash", success=False, session="b1", command="pytest x"),
            _call("Edit", file="src/x.py", session="b1"),
            _call("Bash", success=False, session="b1", command="pytest x"),
        ]
    )
    bad_eps = _episodes(bad_records)

    admitted = sv_mod.admit(
        [(good_skill, good_eps), (good_skill, bad_eps)],
        forge_dir=tmp_path,
        available=False,
    )
    assert good_skill in admitted
    assert len(admitted) == 1


def test_admit_garbage_never_raises(tmp_path) -> None:
    assert sv_mod.admit(None, forge_dir=tmp_path, available=False) == []  # type: ignore[arg-type]
    assert sv_mod.admit([], forge_dir=tmp_path, available=False) == []
