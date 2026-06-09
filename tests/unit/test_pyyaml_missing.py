"""v0.1.5.1 hotfix: Forge hooks fail soft when PyYAML is not installed.

Regression for the tester report where `import yaml` raised
`ModuleNotFoundError` at hook import time and crash-spammed the Stop hook.
Hooks must exit 0 with a single actionable line, never a traceback.

Simulates a missing PyYAML by shadowing `yaml` with an ImportError-raising shim
on PYTHONPATH (same technique as TestNoFrontmatterDependency).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
HOOKS = ROOT / "hooks"
PYTHON = sys.executable

GUARDED_HOOKS = [
    "session-start.py",
    "prompt-submit.py",
    "pre-tool-write.py",
    "post-tool-use.py",
    "stop-reflect.py",
    "session-end.py",
]


def _shim_dir(tmp_path: Path) -> Path:
    d = tmp_path / "shim"
    d.mkdir()
    (d / "yaml.py").write_text('raise ImportError("No module named yaml (test shim)")\n')
    return d


def _run(hook: str, tmp_path: Path, *, shim: bool) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if shim:
        env["PYTHONPATH"] = str(_shim_dir(tmp_path)) + os.pathsep + env.get("PYTHONPATH", "")
    payload = '{"cwd": "%s", "session_id": "s"}' % tmp_path
    return subprocess.run(
        [PYTHON, str(HOOKS / hook)], input=payload,
        capture_output=True, text=True, env=env,
    )


@pytest.mark.parametrize("hook", GUARDED_HOOKS)
def test_hook_fails_soft_without_pyyaml(hook: str, tmp_path: Path) -> None:
    r = _run(hook, tmp_path, shim=True)
    assert r.returncode == 0, f"{hook} did not exit 0: {r.stderr}"
    assert "PyYAML is not installed" in r.stderr
    assert "pip install pyyaml" in r.stderr


@pytest.mark.parametrize("hook", GUARDED_HOOKS)
def test_hook_does_not_traceback_without_pyyaml(hook: str, tmp_path: Path) -> None:
    r = _run(hook, tmp_path, shim=True)
    assert "Traceback (most recent call last)" not in r.stderr
    assert "ModuleNotFoundError" not in r.stderr


@pytest.mark.parametrize("hook", GUARDED_HOOKS)
def test_no_spurious_pyyaml_message_when_present(hook: str, tmp_path: Path) -> None:
    # Without the shim, PyYAML imports normally — the guard stays silent.
    r = _run(hook, tmp_path, shim=False)
    assert "PyYAML is not installed" not in r.stderr
