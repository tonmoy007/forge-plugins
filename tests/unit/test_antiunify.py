"""Tests for scripts/_antiunify.py (T-178 — REQ-SM-003, section 1.4).

Plotkin-style anti-unification over ordered verb fragments. Given >=2 instances
of an ordered verb fragment (each instance is a list of EnrichedCall-like steps),
produce a parameterized skeleton:
  - the shared verb sequence is preserved,
  - differing literals (file/test/error names) are lifted to named parameters,
  - identical diverging values ACROSS instances map to the SAME variable,
  - constants that agree across all instances stay constant.

A clear "not coherent" signal (None) is returned when the instances cannot
anti-unify into a coherent parameterized procedure (different verb sequences,
different lengths, or incompatible argument shapes) — THIS is the filter that
replaces n-gram counting.

Stdlib only; deterministic; never raises.

The module is `_`-prefixed; we load it via importlib.util and register it in
sys.modules so @dataclass under `from __future__ import annotations` resolves.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_scripts = Path(__file__).resolve().parent.parent.parent / "scripts"

# _trace_semantics provides the EnrichedCall dataclass we anti-unify over.
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

EnrichedCall = ts_mod.EnrichedCall


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _step(verb: str, **args: str) -> "EnrichedCall":
    return EnrichedCall(verb=verb, args=dict(args), outcome="neutral", tool="")


def _fix_fragment(src: str, test_file: str) -> list:
    """A canonical fix fragment parameterized over a source + test file name."""
    return [
        _step("run-tests", command="pytest"),
        _step("inspect", file=src),
        _step("patch", file=src),
        _step("run-tests", command="pytest"),
        _step("add-regression-test", file=test_file),
    ]


def _skeleton_verbs(skel) -> list[str]:
    return [s.verb for s in skel.steps]


# ---------------------------------------------------------------------------
# Edge cases — never raises, clear signals
# ---------------------------------------------------------------------------


def test_fewer_than_two_instances_is_not_coherent() -> None:
    assert au_mod.antiunify([]) is None
    assert au_mod.antiunify([_fix_fragment("a.py", "test_a.py")]) is None


def test_different_verb_sequences_do_not_anti_unify() -> None:
    a = [_step("run-tests"), _step("patch", file="a.py")]
    b = [_step("inspect", file="b.py"), _step("patch", file="b.py")]
    assert au_mod.antiunify([a, b]) is None


def test_different_lengths_do_not_anti_unify() -> None:
    a = [_step("run-tests"), _step("patch", file="a.py")]
    b = [_step("run-tests"), _step("patch", file="b.py"), _step("inspect", file="b.py")]
    assert au_mod.antiunify([a, b]) is None


def test_garbage_input_never_raises() -> None:
    assert au_mod.antiunify(None) is None  # type: ignore[arg-type]
    assert au_mod.antiunify("not a list") is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Core anti-unification (REQ-SM-003)
# ---------------------------------------------------------------------------


def test_identical_instances_keep_constants() -> None:
    """When two instances are byte-identical, agreeing literals stay constant —
    no parameters are introduced."""
    a = _fix_fragment("src/foo.py", "tests/test_foo.py")
    b = _fix_fragment("src/foo.py", "tests/test_foo.py")
    skel = au_mod.antiunify([a, b])
    assert skel is not None
    assert _skeleton_verbs(skel) == [
        "run-tests",
        "inspect",
        "patch",
        "run-tests",
        "add-regression-test",
    ]
    assert skel.parameters == []  # nothing differed -> nothing lifted


def test_differing_literals_are_lifted_to_parameters() -> None:
    a = _fix_fragment("src/foo.py", "tests/test_foo.py")
    b = _fix_fragment("src/bar.py", "tests/test_bar.py")
    skel = au_mod.antiunify([a, b])
    assert skel is not None
    # the two distinct differing literals -> two named parameters
    assert len(skel.parameters) == 2


def test_same_diverging_value_maps_to_same_variable() -> None:
    """`inspect(src)` and `patch(src)` use the SAME src literal within an
    instance; across instances the literal differs. Anti-unification must give
    both positions the SAME variable, not two."""
    a = _fix_fragment("src/foo.py", "tests/test_foo.py")
    b = _fix_fragment("src/bar.py", "tests/test_bar.py")
    skel = au_mod.antiunify([a, b])
    assert skel is not None
    inspect_param = skel.steps[1].args["file"]
    patch_param = skel.steps[2].args["file"]
    # both are variables (not literals) and they are the SAME variable
    assert inspect_param in skel.parameters
    assert inspect_param == patch_param
    # and it is distinct from the regression-test-file variable
    regtest_param = skel.steps[4].args["file"]
    assert regtest_param in skel.parameters
    assert regtest_param != inspect_param


def test_constant_arg_stays_literal() -> None:
    """`run-tests(command="pytest")` agrees across all instances -> stays a
    literal, not a parameter."""
    a = _fix_fragment("src/foo.py", "tests/test_foo.py")
    b = _fix_fragment("src/bar.py", "tests/test_bar.py")
    skel = au_mod.antiunify([a, b])
    assert skel is not None
    assert skel.steps[0].args["command"] == "pytest"
    assert "pytest" not in skel.parameters


def test_three_instances_anti_unify() -> None:
    insts = [
        _fix_fragment("src/a.py", "tests/test_a.py"),
        _fix_fragment("src/b.py", "tests/test_b.py"),
        _fix_fragment("src/c.py", "tests/test_c.py"),
    ]
    skel = au_mod.antiunify(insts)
    assert skel is not None
    assert len(skel.parameters) == 2


def test_incompatible_arg_keys_not_coherent() -> None:
    """Same verb sequence but the args carry different KEYS in a position
    (one has `file`, the other has `command`) — not a coherent procedure."""
    a = [_step("act", file="a.py")]
    b = [_step("act", file="b.py")]
    # make them >=2 long and verb-aligned but key-divergent at a position
    a = [_step("run-tests", command="pytest"), _step("act", file="a.py")]
    b = [_step("run-tests", command="pytest"), _step("act", command="ls")]
    assert au_mod.antiunify([a, b]) is None


def test_skeleton_is_deterministic() -> None:
    a = _fix_fragment("src/foo.py", "tests/test_foo.py")
    b = _fix_fragment("src/bar.py", "tests/test_bar.py")
    s1 = au_mod.antiunify([a, b])
    s2 = au_mod.antiunify([a, b])
    assert s1 is not None and s2 is not None
    assert _skeleton_verbs(s1) == _skeleton_verbs(s2)
    assert s1.parameters == s2.parameters
    assert [st.args for st in s1.steps] == [st.args for st in s2.steps]
