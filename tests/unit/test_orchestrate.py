"""Tests for scripts/_orchestrate.py (v0.2 P2 — T-148, REQ-F-031/032/033/035, ADR-006).

The orchestration primitive fans a work-list out across bounded parallel agent
dispatches, validates each structured result, retries once on malformed output,
drops (never silently truncates) on repeated failure, dedups, and returns results
**index-ordered** so the parallel and sequential paths are byte-identical (NF-009).
A fake dispatch_fn is injected — no real claude / subprocess is touched.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

_root = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location("_orchestrate", _root / "scripts" / "_orchestrate.py")
_orch = importlib.util.module_from_spec(_spec)
sys.modules["_orchestrate"] = _orch
_spec.loader.exec_module(_orch)


def _ok(result_obj: dict, cost: float = 0.01) -> SimpleNamespace:
    return SimpleNamespace(status="ok", result=json.dumps(result_obj),
                           cost_usd=cost, raw={"is_error": False})


def _echo_dispatch(prompt, *, forge_dir, feature, resume=None, model=None,
                   claude_bin=None, cwd=None, **kw):
    """Fake: returns {item: prompt, n: len}, finishing OUT of index order
    (shorter prompts sleep less) to prove ordering is by index, not completion."""
    time.sleep(max(0, (6 - len(prompt))) * 0.01)
    return _ok({"item": prompt, "n": len(prompt)})


FORGE = Path("/tmp/does-not-matter")  # fake dispatch ignores it


def test_parallel_equals_sequential_and_input_ordered() -> None:
    items = ["a", "bb", "ccc", "dddd"]
    par = _orch.fan_out(items, lambda x: x, forge_dir=FORGE, feature="t",
                        max_parallel=4, dispatch_fn=_echo_dispatch)
    seq = _orch.fan_out(items, lambda x: x, forge_dir=FORGE, feature="t",
                        max_parallel=1, dispatch_fn=_echo_dispatch)
    assert par.results == seq.results                      # determinism (NF-009)
    assert [r["item"] for r in par.results] == items       # input index order


def test_malformed_dropped_after_retry_not_silent() -> None:
    calls: dict[str, int] = {}

    def flaky(prompt, **kw):
        calls[prompt] = calls.get(prompt, 0) + 1
        if prompt == "bad":
            return SimpleNamespace(status="ok", result="not json",
                                   cost_usd=0.01, raw={"is_error": False})
        return _ok({"item": prompt})

    res = _orch.fan_out(["good1", "bad", "good2"], lambda x: x, forge_dir=FORGE,
                        feature="t", max_parallel=3, dispatch_fn=flaky)
    assert [r["item"] for r in res.results] == ["good1", "good2"]  # bad excluded
    assert res.dropped == 1
    assert res.dropped_reasons  # logged, not silent
    assert calls["bad"] == 2  # retried once


def test_retry_then_succeeds() -> None:
    state: dict[str, int] = {}

    def recover(prompt, **kw):
        state[prompt] = state.get(prompt, 0) + 1
        if state[prompt] == 1:
            return SimpleNamespace(status="error", result=None, cost_usd=0.0, raw=None)
        return _ok({"item": prompt})

    res = _orch.fan_out(["x"], lambda p: p, forge_dir=FORGE, feature="t",
                        dispatch_fn=recover)
    assert res.results == [{"item": "x"}]
    assert res.dropped == 0


def test_validate_rejects_then_drops() -> None:
    def validate(d):
        if "keep" not in d:
            raise ValueError("missing keep")
        return d

    def disp(prompt, **kw):
        return _ok({"keep": 1} if prompt == "ok" else {"nope": 1})

    res = _orch.fan_out(["ok", "no"], lambda p: p, forge_dir=FORGE, feature="t",
                        validate=validate, dispatch_fn=disp)
    assert res.results == [{"keep": 1}]
    assert res.dropped == 1


def test_dedup_keeps_first_by_index() -> None:
    def disp(prompt, **kw):
        return _ok({"k": prompt[0], "p": prompt})  # "ax","ay" share key "a"

    res = _orch.fan_out(["ax", "ay", "bz"], lambda p: p, forge_dir=FORGE, feature="t",
                        dedup_key=lambda o: o["k"], dispatch_fn=disp)
    assert [r["p"] for r in res.results] == ["ax", "bz"]  # first "a" kept, "ay" dropped


def test_skipped_dispatch_dropped_never_raises() -> None:
    def capped(prompt, **kw):
        return SimpleNamespace(status="skipped", result=None, cost_usd=0.0, raw=None)

    res = _orch.fan_out(["a", "b"], lambda p: p, forge_dir=FORGE, feature="t",
                        dispatch_fn=capped)
    assert res.results == []
    assert res.dropped == 2


def test_total_cap_bounds_and_logs() -> None:
    items = [str(i) for i in range(10)]
    res = _orch.fan_out(items, lambda p: p, forge_dir=FORGE, feature="t",
                        max_total=4, dispatch_fn=lambda p, **kw: _ok({"item": p}))
    assert len(res.results) == 4
    assert any("max_total" in r or "cap" in r.lower() for r in res.dropped_reasons)


def test_cost_summed() -> None:
    res = _orch.fan_out(["a", "b", "c"], lambda p: p, forge_dir=FORGE, feature="t",
                        dispatch_fn=lambda p, **kw: _ok({"item": p}, cost=0.02))
    assert abs(res.total_cost_usd - 0.06) < 1e-9
