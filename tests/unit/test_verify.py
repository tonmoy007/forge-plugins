"""Tests for scripts/_verify.py (v0.4.0 — shared verify/heal primitives, REQ-WF-002).

The verdict schema, the lenient verdict interpreter, the bounded self-heal decision, and the
engine-facing fresh-session verifier runner were extracted from autopilot so the workflow engine
and autopilot share ONE copy. A fake/spy dispatch_fn is injected — no real claude / subprocess.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

_root = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location("_verify", _root / "scripts" / "_verify.py")
_v = importlib.util.module_from_spec(_spec)
sys.modules["_verify"] = _v
_spec.loader.exec_module(_v)

FORGE = Path("/tmp/does-not-matter")


# --- VERIFY_SCHEMA ----------------------------------------------------------

def test_verify_schema_shape() -> None:
    schema = _v.VERIFY_SCHEMA
    assert schema["properties"]["verdict"]["enum"] == ["pass", "fail"]
    assert schema["required"] == ["verdict"]
    assert schema["additionalProperties"] is False


# --- verdict_failed ---------------------------------------------------------

def test_verdict_failed_true_on_fail() -> None:
    assert _v.verdict_failed({"result": '{"verdict": "fail", "reasons": ["x"]}'}) is True


def test_verdict_failed_false_on_pass() -> None:
    assert _v.verdict_failed({"result": '{"verdict": "pass"}'}) is False


def test_verdict_failed_degrades_on_garbage_never_raises() -> None:
    # A broken/empty/unavailable verifier must NOT report failure (degrade, don't block).
    assert _v.verdict_failed({"result": "not json"}) is False
    assert _v.verdict_failed({"result": ""}) is False
    assert _v.verdict_failed({"result": None}) is False
    assert _v.verdict_failed({"status": "unavailable"}) is False
    assert _v.verdict_failed({}) is False
    assert _v.verdict_failed("not a dict") is False  # type: ignore[arg-type]
    assert _v.verdict_failed(None) is False  # type: ignore[arg-type]


# --- should_heal (config-agnostic primitive) --------------------------------

def test_should_heal_default_one_attempt() -> None:
    assert _v.should_heal(0, 1) is True   # first failure → heal
    assert _v.should_heal(1, 1) is False  # after one heal → stop


def test_should_heal_zero_never_heals() -> None:
    assert _v.should_heal(0, 0) is False


def test_should_heal_respects_higher_cap() -> None:
    assert _v.should_heal(2, 3) is True
    assert _v.should_heal(3, 3) is False


def test_should_heal_non_int_cap_never_heals() -> None:
    assert _v.should_heal(0, None) is False  # type: ignore[arg-type]


# --- run_verify (engine-facing fresh-session runner) ------------------------

def _ok(result_payload: str) -> SimpleNamespace:
    return SimpleNamespace(status="ok", reason="dispatched", result=result_payload)


def _spy(recorded: list, res):
    def dispatch(prompt, **kwargs):
        recorded.append({"prompt": prompt, **kwargs})
        return res
    return dispatch


def test_run_verify_happy_path_returns_verdict() -> None:
    recorded: list = []
    out = _v.run_verify(
        "verify this", _spy(recorded, _ok('{"verdict": "pass"}')),
        {"forge_dir": FORGE, "feature": "wf-verify", "model": None, "resume": "S1"},
    )
    assert out["status"] == "ok"
    assert out["result"] == '{"verdict": "pass"}'
    assert _v.verdict_failed(out) is False


def test_run_verify_forces_fresh_session_and_schema() -> None:
    """Independence: resume forced to None, output_schema forced to VERIFY_SCHEMA by default,
    even when the caller's kwargs say otherwise."""
    recorded: list = []
    _v.run_verify(
        "verify this", _spy(recorded, _ok('{"verdict": "fail"}')),
        {"forge_dir": FORGE, "feature": "wf-verify", "resume": "STAGE-SESSION"},
    )
    call = recorded[0]
    assert call["resume"] is None                       # never reuse the produced session
    assert call["output_schema"] == _v.VERIFY_SCHEMA    # schema-constrained verdict
    assert call["prompt"] == "verify this"


def test_run_verify_honors_explicit_schema() -> None:
    recorded: list = []
    custom = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    _v.run_verify(
        "v", _spy(recorded, _ok('{"verdict": "pass"}')),
        {"forge_dir": FORGE, "feature": "f"}, schema=custom,
    )
    assert recorded[0]["output_schema"] == custom


def test_run_verify_fail_verdict_reads_as_failed() -> None:
    out = _v.run_verify(
        "v", _spy([], _ok('{"verdict": "fail", "reasons": ["bad"]}')),
        {"forge_dir": FORGE, "feature": "f"},
    )
    assert _v.verdict_failed(out) is True


def test_run_verify_dispatch_raises_degrades_never_raises() -> None:
    def boom(prompt, **kwargs):
        raise RuntimeError("dispatch exploded")

    out = _v.run_verify("v", boom, {"forge_dir": FORGE, "feature": "f"})
    assert out["status"] == "error"
    assert _v.verdict_failed(out) is False  # broken verifier degrades, does not block


def test_run_verify_garbage_verdict_output_never_raises() -> None:
    out = _v.run_verify(
        "v", _spy([], _ok("this is not json at all")),
        {"forge_dir": FORGE, "feature": "f"},
    )
    # Non-JSON verdict body → not-failed (lenient), no exception.
    assert _v.verdict_failed(out) is False
