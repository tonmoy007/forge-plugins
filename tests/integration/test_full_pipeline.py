"""Pytest wrapper for tests/integration/full-pipeline.sh.

Runs the shell script and asserts exit 0 so the e2e test is included in the
standard `pytest tests/` suite without requiring a separate invocation.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parent / "full-pipeline.sh"
PLUGIN_DIR = Path(__file__).parent.parent.parent


def test_full_pipeline_exits_zero():
    """Full pipeline integration test: all artifacts present, traceability intact."""
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(PLUGIN_DIR),
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, (
        f"full-pipeline.sh exited {result.returncode}\n{output}"
    )
    assert "PASS: full-pipeline integration test" in result.stdout
