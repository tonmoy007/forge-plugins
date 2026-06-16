"""Tests for scripts/_trace_semantics.py (T-177 — REQ-SM-001, REQ-SM-002).

This module is the deterministic FOUNDATION the rest of the v0.3.5 semantic
miner imports. It must:
  - read .forge/session-log.jsonl fail-soft (missing/empty/malformed -> [] or
    skip line, never raise),
  - canonicalize each tool call into (verb, args, outcome) via a small explicit
    rule table mapping (tool, arg-pattern, exit/result, stage) -> intent verb,
  - segment the enriched stream into outcome-bounded episodes, splitting at
    outcome transitions (the failure->fix delta being the key boundary).

Stdlib only; never raises on the hot/background path.

The module name is `_`-prefixed so it imports cleanly, but we load it via
importlib.util and register it in sys.modules so @dataclass under
`from __future__ import annotations` can resolve its own module.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_mod_path = Path(__file__).resolve().parent.parent.parent / "scripts" / "_trace_semantics.py"
_spec = importlib.util.spec_from_file_location("_trace_semantics", _mod_path)
assert _spec and _spec.loader
ts_mod = importlib.util.module_from_spec(_spec)
sys.modules["_trace_semantics"] = ts_mod  # @dataclass needs the module registered
_spec.loader.exec_module(ts_mod)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_log(tmp_path: Path, records: list[dict]) -> Path:
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True, exist_ok=True)
    p = forge / "session-log.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    return p


def _call(
    tool: str,
    file: str = "",
    success: bool = True,
    stage: int = 6,
    session: str = "s1",
    command: str = "",
) -> dict:
    """A session-log record, matching hooks/post-tool-use.py's shape."""
    rec: dict = {
        "ts": "2026-06-16T12:00:00Z",
        "session": session,
        "tool": tool,
        "file": file,
        "success": success,
        "stage": stage,
    }
    if command:
        rec["command"] = command
    return rec


def _verbs(enriched) -> list[str]:
    return [e.verb for e in enriched]


# A canonical failure->fix->regression episode, parameterized over names.
def _fix_episode(src: str, test_cmd: str, test_file: str, session: str) -> list[dict]:
    return [
        _call("Bash", success=False, session=session, command=test_cmd),  # run-tests(fail)
        _call("Read", file=src, session=session),                          # inspect
        _call("Edit", file=src, session=session),                          # patch
        _call("Bash", success=True, session=session, command=test_cmd),    # run-tests(pass)
        _call("Write", file=test_file, session=session),                   # add-regression-test
    ]


# ---------------------------------------------------------------------------
# Fail-soft reader
# ---------------------------------------------------------------------------


def test_read_missing_log_returns_empty(tmp_path: Path) -> None:
    missing = tmp_path / ".forge" / "session-log.jsonl"
    assert ts_mod.read_session_log(missing) == []


def test_read_empty_log_returns_empty(tmp_path: Path) -> None:
    p = _write_log(tmp_path, [])
    assert ts_mod.read_session_log(p) == []


def test_read_skips_malformed_lines(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    p = forge / "session-log.jsonl"
    p.write_text(
        '{"tool": "Read", "file": "a.py", "success": true}\n'
        "this is not json\n"
        "\n"
        '{"tool": "Edit", "file": "a.py", "success": true}\n',
        encoding="utf-8",
    )
    records = ts_mod.read_session_log(p)
    assert [r.get("tool") for r in records] == ["Read", "Edit"]


def test_read_garbage_never_raises(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    p = forge / "session-log.jsonl"
    p.write_bytes(b"\x00\xff\xfe not json at all \x00")
    # Must not raise; returns a list (possibly empty).
    assert isinstance(ts_mod.read_session_log(p), list)


def test_enrich_empty_returns_empty() -> None:
    assert ts_mod.enrich([]) == []


def test_segment_empty_returns_empty() -> None:
    assert ts_mod.segment([]) == []


# ---------------------------------------------------------------------------
# Canonicalization (REQ-SM-001)
# ---------------------------------------------------------------------------


def test_failing_test_command_maps_to_run_tests_fail() -> None:
    enriched = ts_mod.enrich([_call("Bash", success=False, command="pytest -q")])
    assert enriched[0].verb == "run-tests"
    assert enriched[0].outcome == "fail"


def test_passing_test_command_maps_to_run_tests_pass() -> None:
    enriched = ts_mod.enrich([_call("Bash", success=True, command="pytest -q")])
    assert enriched[0].verb == "run-tests"
    assert enriched[0].outcome == "pass"


def test_read_maps_to_inspect() -> None:
    enriched = ts_mod.enrich([_call("Read", file="src/foo.py")])
    assert enriched[0].verb == "inspect"


def test_edit_source_after_failing_test_maps_to_patch() -> None:
    enriched = ts_mod.enrich(
        [
            _call("Bash", success=False, command="pytest -q"),
            _call("Edit", file="src/foo.py"),
        ]
    )
    assert enriched[1].verb == "patch"


def test_write_test_file_after_green_maps_to_add_regression_test() -> None:
    enriched = ts_mod.enrich(
        [
            _call("Bash", success=False, command="pytest -q"),
            _call("Edit", file="src/foo.py"),
            _call("Bash", success=True, command="pytest -q"),
            _call("Write", file="tests/test_foo.py"),
        ]
    )
    assert enriched[-1].verb == "add-regression-test"


def test_unknown_tool_maps_to_generic_verb_not_raise() -> None:
    enriched = ts_mod.enrich([_call("SomeMysteryTool", file="x")])
    assert len(enriched) == 1
    assert enriched[0].verb  # non-empty generic verb
    assert enriched[0].verb != ""


def test_canonical_verb_sequence_for_fix_episode() -> None:
    enriched = ts_mod.enrich(_fix_episode("src/foo.py", "pytest", "tests/test_foo.py", "s1"))
    assert _verbs(enriched) == [
        "run-tests",
        "inspect",
        "patch",
        "run-tests",
        "add-regression-test",
    ]


def test_args_preserve_differing_literals() -> None:
    """Differing file/command literals are preserved in args for later
    anti-unification (T-178)."""
    enriched = ts_mod.enrich([_call("Edit", file="src/payments.py")])
    # the source file literal must be recoverable from args
    assert "src/payments.py" in enriched[0].args.values()


# ---------------------------------------------------------------------------
# Episode segmentation (REQ-SM-002)
# ---------------------------------------------------------------------------


def test_terminal_success_ends_episode() -> None:
    enriched = ts_mod.enrich(_fix_episode("src/foo.py", "pytest", "tests/test_foo.py", "s1"))
    episodes = ts_mod.segment(enriched)
    assert len(episodes) == 1
    assert episodes[0].outcome == "success"


def test_two_back_to_back_fix_episodes_split() -> None:
    calls = (
        _fix_episode("src/a.py", "pytest a", "tests/test_a.py", "s1")
        + _fix_episode("src/b.py", "pytest b", "tests/test_b.py", "s1")
    )
    episodes = ts_mod.segment(ts_mod.enrich(calls))
    assert len(episodes) == 2


def test_new_session_starts_new_episode() -> None:
    calls = (
        _fix_episode("src/a.py", "pytest a", "tests/test_a.py", "s1")[:3]  # incomplete, no success
        + _fix_episode("src/b.py", "pytest b", "tests/test_b.py", "s2")
    )
    episodes = ts_mod.segment(ts_mod.enrich(calls))
    # The session boundary forces a split even though s1's episode never
    # reached a terminal success.
    assert len(episodes) == 2


def test_failure_to_fix_boundary_detected() -> None:
    """The failure->fix delta is the highest-signal boundary: an episode that
    contains a run-tests(fail) followed by a run-tests(pass) is flagged as a
    fix episode."""
    enriched = ts_mod.enrich(_fix_episode("src/foo.py", "pytest", "tests/test_foo.py", "s1"))
    ep = ts_mod.segment(enriched)[0]
    assert ep.has_fix_boundary is True


def test_no_fix_boundary_when_only_passing() -> None:
    calls = [
        _call("Read", file="src/foo.py"),
        _call("Bash", success=True, command="pytest"),
    ]
    ep = ts_mod.segment(ts_mod.enrich(calls))[0]
    assert ep.has_fix_boundary is False


def test_episode_carries_its_enriched_calls() -> None:
    enriched = ts_mod.enrich(_fix_episode("src/foo.py", "pytest", "tests/test_foo.py", "s1"))
    ep = ts_mod.segment(enriched)[0]
    assert _verbs(ep.calls) == ["run-tests", "inspect", "patch", "run-tests", "add-regression-test"]


def test_full_pipeline_read_enrich_segment(tmp_path: Path) -> None:
    p = _write_log(
        tmp_path,
        _fix_episode("src/foo.py", "pytest", "tests/test_foo.py", "s1"),
    )
    records = ts_mod.read_session_log(p)
    episodes = ts_mod.segment(ts_mod.enrich(records))
    assert len(episodes) == 1
    assert episodes[0].has_fix_boundary is True
    assert episodes[0].outcome == "success"
