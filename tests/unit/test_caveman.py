"""Tests for hooks/_caveman.py (v0.6.1 — REQ-CM-001 / NF-041).

The caveman core is a pure, never-raising stdlib module: `terse_preamble(level)` returns a
per-level instruction string (unknown ⇒ lite), and `apply(prompt, *, enabled, has_schema, level)`
prepends that preamble to a free-prose prompt — but is the **identity** when disabled OR when the
dispatch is schema-constrained, and degrades to the original prompt on any internal error. We test
it directly with no CLI / network.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_mod_path = Path(__file__).resolve().parent.parent.parent / "hooks" / "_caveman.py"
_spec = importlib.util.spec_from_file_location("_caveman", _mod_path)
_cm = importlib.util.module_from_spec(_spec)
sys.modules["_caveman"] = _cm
_spec.loader.exec_module(_cm)


# --- terse_preamble ---------------------------------------------------------

def test_terse_preamble_lite_nonempty():
    assert isinstance(_cm.terse_preamble("lite"), str)
    assert _cm.terse_preamble("lite").strip() != ""


def test_terse_preamble_full_nonempty_and_differs_from_lite():
    full = _cm.terse_preamble("full")
    assert isinstance(full, str) and full.strip() != ""
    assert full != _cm.terse_preamble("lite")


def test_terse_preamble_unknown_level_coerces_to_lite():
    for bad in ("ultra", "wenyan", "LITE", "", "garbage"):
        assert _cm.terse_preamble(bad) == _cm.terse_preamble("lite")


def test_terse_preamble_none_level_is_lite():
    # A None level must not raise — it coerces to the lite preamble.
    assert _cm.terse_preamble(None) == _cm.terse_preamble("lite")


# --- apply: prepend / identity ----------------------------------------------

def test_apply_prepends_preamble_when_enabled_and_no_schema():
    out = _cm.apply("Summarise the run.", enabled=True, has_schema=False, level="lite")
    assert out.endswith("Summarise the run.")
    assert out.startswith(_cm.terse_preamble("lite"))
    assert len(out) > len("Summarise the run.")


def test_apply_is_identity_when_disabled():
    prompt = "Summarise the run."
    assert _cm.apply(prompt, enabled=False, has_schema=False, level="lite") == prompt


def test_apply_is_identity_when_has_schema_even_if_enabled():
    # Schema-constrained dispatches are NEVER altered (REQ-NF-041), regardless of `enabled`.
    prompt = "Return ONLY a JSON array."
    assert _cm.apply(prompt, enabled=True, has_schema=True, level="full") == prompt


def test_apply_is_identity_when_disabled_and_schema():
    prompt = "x"
    assert _cm.apply(prompt, enabled=False, has_schema=True, level="lite") == prompt


def test_apply_exact_composition_is_preamble_plus_prompt():
    prompt = "Consolidate lessons."
    out = _cm.apply(prompt, enabled=True, has_schema=False, level="full")
    assert out == _cm.terse_preamble("full") + prompt


def test_apply_unknown_level_uses_lite_preamble():
    prompt = "go"
    out = _cm.apply(prompt, enabled=True, has_schema=False, level="ultra")
    assert out == _cm.terse_preamble("lite") + prompt


def test_apply_empty_prompt_returns_just_preamble():
    out = _cm.apply("", enabled=True, has_schema=False, level="lite")
    assert out == _cm.terse_preamble("lite")


# --- never-raises (REQ-NF-041) ----------------------------------------------

def test_apply_never_raises_when_preamble_raises(monkeypatch):
    # If the preamble builder blows up, apply must degrade to the original prompt, never raise.
    def _boom(_level):
        raise RuntimeError("preamble exploded")

    monkeypatch.setattr(_cm, "terse_preamble", _boom)
    prompt = "untouched"
    assert _cm.apply(prompt, enabled=True, has_schema=False, level="lite") == prompt


def test_apply_never_raises_on_nonstring_prompt():
    # A non-str prompt makes `preamble + prompt` raise TypeError internally → original returned.
    sentinel = None
    assert _cm.apply(sentinel, enabled=True, has_schema=False, level="lite") is sentinel


def test_apply_keyword_only_enforced():
    # enabled / has_schema / level are keyword-only (no positional foot-guns at the call site).
    with pytest.raises(TypeError):
        _cm.apply("p", True, False, "lite")  # type: ignore[misc]
