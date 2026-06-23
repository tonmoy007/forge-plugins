"""Tests for scripts/_workflow_config.py (v0.4.0, REQ-WF-003 / AC-WF-004).

The `orchestration:` block in `.forge/config.yaml` carries independent capability toggles
(all default false) plus engine tunables, loaded fail-soft exactly like
`autopilot.load_config`: missing file → defaults; malformed YAML → defaults; an invalid
individual value → that key defaults while valid sibling keys survive. Never raises.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent

_spec = importlib.util.spec_from_file_location(
    "_workflow_config", _root / "scripts" / "_workflow_config.py"
)
_wfc = importlib.util.module_from_spec(_spec)
sys.modules["_workflow_config"] = _wfc
_spec.loader.exec_module(_wfc)

TOGGLES = ("flows_enabled", "parallel_build", "worktree_isolation", "allow_generated_subdags")


def _write_config(tmp_path: Path, text: str) -> Path:
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True, exist_ok=True)
    (forge / "config.yaml").write_text(text)
    return forge


def _assert_all_defaults(cfg) -> None:
    for name in TOGGLES:
        assert getattr(cfg, name) is False, f"{name} should default False"
    assert cfg.max_parallel == 4
    assert cfg.max_total == 64
    assert cfg.max_budget_usd is None


# --------------------------------------------------------------------------- #
# Defaults / fail-soft
# --------------------------------------------------------------------------- #
def test_defaults_when_config_absent(tmp_path):
    cfg = _wfc.load_orchestration_config(tmp_path / ".forge")
    _assert_all_defaults(cfg)


def test_defaults_when_no_orchestration_block(tmp_path):
    forge = _write_config(tmp_path, "autopilot:\n  max_stages: 3\n")
    cfg = _wfc.load_orchestration_config(forge)
    _assert_all_defaults(cfg)


def test_malformed_yaml_falls_back_to_defaults(tmp_path):
    forge = _write_config(tmp_path, "orchestration: : : [[\n  bad\n")
    cfg = _wfc.load_orchestration_config(forge)  # must not raise
    _assert_all_defaults(cfg)


def test_orchestration_not_a_mapping_falls_back(tmp_path):
    forge = _write_config(tmp_path, "orchestration: just-a-string\n")
    cfg = _wfc.load_orchestration_config(forge)
    _assert_all_defaults(cfg)


# --------------------------------------------------------------------------- #
# Happy path round-trip
# --------------------------------------------------------------------------- #
def test_full_valid_block_round_trips(tmp_path):
    forge = _write_config(
        tmp_path,
        "orchestration:\n"
        "  flows_enabled: true\n"
        "  parallel_build: true\n"
        "  worktree_isolation: true\n"
        "  allow_generated_subdags: true\n"
        "  max_parallel: 8\n"
        "  max_total: 128\n"
        "  max_budget_usd: 5.5\n",
    )
    cfg = _wfc.load_orchestration_config(forge)
    assert cfg.flows_enabled is True
    assert cfg.parallel_build is True
    assert cfg.worktree_isolation is True
    assert cfg.allow_generated_subdags is True
    assert cfg.max_parallel == 8
    assert cfg.max_total == 128
    assert cfg.max_budget_usd == 5.5


def test_each_toggle_independently_settable(tmp_path):
    for name in TOGGLES:
        forge = _write_config(tmp_path, f"orchestration:\n  {name}: true\n")
        cfg = _wfc.load_orchestration_config(forge)
        assert getattr(cfg, name) is True, f"{name} should be True when set"
        for other in TOGGLES:
            if other != name:
                assert getattr(cfg, other) is False, (
                    f"{other} should stay False when only {name} is set"
                )


# --------------------------------------------------------------------------- #
# Per-key coercion / invalid-value isolation
# --------------------------------------------------------------------------- #
def test_invalid_int_tunable_defaults_while_others_survive(tmp_path):
    forge = _write_config(
        tmp_path,
        "orchestration:\n"
        "  max_parallel: banana\n"   # invalid → default 4
        "  max_total: 100\n"          # valid → survives
        "  flows_enabled: true\n",    # valid → survives
    )
    cfg = _wfc.load_orchestration_config(forge)
    assert cfg.max_parallel == 4
    assert cfg.max_total == 100
    assert cfg.flows_enabled is True


def test_invalid_budget_defaults_to_none(tmp_path):
    forge = _write_config(tmp_path, "orchestration:\n  max_budget_usd: free\n")
    cfg = _wfc.load_orchestration_config(forge)
    assert cfg.max_budget_usd is None


def test_truthy_nonbool_does_not_enable_toggle(tmp_path):
    # Mirror autopilot's strict `is True` semantics: only a real bool true enables a toggle.
    forge = _write_config(tmp_path, "orchestration:\n  flows_enabled: 1\n")
    cfg = _wfc.load_orchestration_config(forge)
    assert cfg.flows_enabled is False


def test_numeric_budget_int_coerces_to_float(tmp_path):
    forge = _write_config(tmp_path, "orchestration:\n  max_budget_usd: 3\n")
    cfg = _wfc.load_orchestration_config(forge)
    assert cfg.max_budget_usd == 3.0


def test_zero_and_negative_tunables_ignored(tmp_path):
    # Tunables that bound parallelism must be positive; a non-positive value is invalid and
    # falls back to the default rather than disabling the engine.
    forge = _write_config(
        tmp_path, "orchestration:\n  max_parallel: 0\n  max_total: -5\n"
    )
    cfg = _wfc.load_orchestration_config(forge)
    assert cfg.max_parallel == 4
    assert cfg.max_total == 64


# --------------------------------------------------------------------------- #
# T-202 (REQ-WF-011) — narration knob: default ON, only an explicit bool False disables
# --------------------------------------------------------------------------- #


def test_narrate_defaults_on(tmp_path):
    forge = _write_config(tmp_path, "orchestration:\n  parallel_build: true\n")
    cfg = _wfc.load_orchestration_config(forge)
    assert cfg.narrate is True


def test_narrate_defaults_on_when_no_config(tmp_path):
    cfg = _wfc.load_orchestration_config(tmp_path / ".forge")
    assert cfg.narrate is True


def test_narrate_false_disables(tmp_path):
    forge = _write_config(tmp_path, "orchestration:\n  narrate: false\n")
    cfg = _wfc.load_orchestration_config(forge)
    assert cfg.narrate is False


def test_narrate_truthy_nonbool_does_not_disable(tmp_path):
    # Only an explicit bool False silences; a stray 0/"" never flips the product default off.
    forge = _write_config(tmp_path, "orchestration:\n  narrate: 0\n")
    cfg = _wfc.load_orchestration_config(forge)
    assert cfg.narrate is True


# --------------------------------------------------------------------------- #
# T-214 (REQ-WF-019) — session_reuse capability toggle: default OFF, strict `is True`,
# fail-soft; mirrors the v0.4.0 capability toggles (flows_enabled & siblings).
# --------------------------------------------------------------------------- #


def test_session_reuse_defaults_off(tmp_path):
    forge = _write_config(tmp_path, "orchestration:\n  parallel_build: true\n")
    cfg = _wfc.load_orchestration_config(forge)
    assert cfg.session_reuse is False


def test_session_reuse_defaults_off_when_no_config(tmp_path):
    cfg = _wfc.load_orchestration_config(tmp_path / ".forge")
    assert cfg.session_reuse is False


def test_session_reuse_true_enables(tmp_path):
    forge = _write_config(tmp_path, "orchestration:\n  session_reuse: true\n")
    cfg = _wfc.load_orchestration_config(forge)
    assert cfg.session_reuse is True


def test_session_reuse_truthy_nonbool_does_not_enable(tmp_path):
    # Strict `is True`: a stray `1` / `"yes"` never silently enables the capability.
    for stray in ("1", '"yes"'):
        forge = _write_config(tmp_path, f"orchestration:\n  session_reuse: {stray}\n")
        cfg = _wfc.load_orchestration_config(forge)
        assert cfg.session_reuse is False


def test_session_reuse_in_toggles_tuple(tmp_path):
    # session_reuse is a real capability toggle — it must live in `_TOGGLES` so the strict
    # `is True` parse loop covers it (not a bespoke branch).
    assert "session_reuse" in _wfc._TOGGLES


def test_session_reuse_independent_of_other_toggles(tmp_path):
    # Enabling session_reuse alone leaves every other capability toggle off.
    forge = _write_config(tmp_path, "orchestration:\n  session_reuse: true\n")
    cfg = _wfc.load_orchestration_config(forge)
    assert cfg.session_reuse is True
    for other in TOGGLES:
        assert getattr(cfg, other) is False, f"{other} should stay False"
