"""T-112 / REQ-GATESTUB-001: gate-criteria audit — no dangling script references.

AC-GATESTUB-001b: every `script_returns_zero` criterion in gate-criteria.md
references a script that exists in the plugin. This is the CI guard that fails if
a future criterion points at a missing script (the bug class T-108..T-111 closed).

Uses check-gate's own loader so it audits exactly what check-gate would run — the
`### script_returns_zero` *format example* (no `stage:` block) is not a real
criterion and is therefore not audited.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"


def _load_check_gate():
    spec = importlib.util.spec_from_file_location("check_gate", SCRIPTS / "check-gate.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_gate"] = mod
    spec.loader.exec_module(mod)
    return mod


cg = _load_check_gate()


def _all_script_criteria():
    """Yield (stage, criterion) for every script_returns_zero criterion, all stages."""
    for stage in range(1, 13):
        for c in cg._load_stage_criteria(ROOT, stage):
            if c.get("check") == "script_returns_zero":
                yield stage, c


def test_every_gate_script_reference_exists():
    missing = []
    for stage, c in _all_script_criteria():
        script_rel = c.get("args", {}).get("script", "")
        if not script_rel or not (ROOT / script_rel).exists():
            missing.append(f"stage {stage} {c.get('id')} -> {script_rel!r}")
    assert missing == [], f"gate criteria reference missing scripts: {missing}"


def test_audit_found_some_script_criteria():
    """Guard against a vacuous pass if parsing silently returns nothing."""
    assert list(_all_script_criteria()), "no script_returns_zero criteria parsed"


def test_some_check_not_a_real_criterion():
    """some_check.py is only in the format-example block, never a real criterion."""
    refs = [c.get("args", {}).get("script", "") for _, c in _all_script_criteria()]
    assert not any("some_check.py" in r for r in refs)
