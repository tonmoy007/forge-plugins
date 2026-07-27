"""Helper for invoking Claude subagents from hook contexts.

v0.1: Attempts to spawn `claude --print <prompt>` as a subprocess.
Falls back to empty string on any failure (binary absent, timeout, error).

Full LLM-backed reflection is deferred to T-016 (agents/reflector.md).
Decision recorded in build/05-implementation/decisions.md.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


def invoke_agent(
    name: str,
    context: dict[str, Any],
    *,
    timeout: int = 8,
) -> str:
    """Invoke a named Forge agent and return its text output.

    Falls back to '' on any failure — callers must handle '' gracefully.
    """
    claude_bin = shutil.which("claude")
    if not claude_bin:
        logger.debug("claude binary not found; skipping agent %s", name)
        return ""

    lines = [f"[Forge Agent: {name}]"]
    for k, v in context.items():
        lines.append(f"{k}: {v if isinstance(v, str) else json.dumps(v)}")
    prompt = "\n".join(lines)

    try:
        result = subprocess.run(
            [claude_bin, "--print", prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        logger.debug(
            "agent %s exited %d: %s", name, result.returncode, result.stderr[:200]
        )
    except subprocess.TimeoutExpired:
        logger.debug("agent %s timed out after %ds", name, timeout)
    except Exception as e:  # noqa: BLE001
        logger.debug("agent %s failed: %s", name, e)

    return ""
