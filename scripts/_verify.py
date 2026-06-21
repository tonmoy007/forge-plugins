#!/usr/bin/env python3
"""Shared verification + self-heal primitives (REQ-WF-002).

The structured-verdict schema, the lenient verdict interpreter, and the bounded self-heal
decision were born inside `scripts/autopilot.py` (REQ-AUTO-002/003). v0.4.0 extracts them here
so the workflow engine (`scripts/_workflow.py`) and autopilot share ONE copy: a node carrying a
`VerifySpec` gets the same fresh-session, schema-constrained pass/fail verdict that gates an
autopilot stage. autopilot keeps its public names by re-importing from this module, so its
behavior — and its tests — are unchanged.

Design rules (mirrors the autopilot originals):
  - Stdlib only. No PyYAML, no external deps.
  - NEVER raises. Garbage verdict output ⇒ a structured non-failed result, not an exception.
  - The verifier is an *extra* check on an already-produced node result; a broken or unavailable
    verifier degrades to "not-failed" (does not block) — REQ-NF-013.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

_LOG = logging.getLogger(__name__)

# Structured verdict an independent verifier returns (REQ-AUTO-003 / REQ-WF-002); constrained
# via the CLI structured-outputs flag (`--json-schema`). A CLI/model without structured outputs
# degrades to free-form text, which `verdict_failed` parses leniently (and treats as pass on
# failure to parse).
VERIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["pass", "fail"]},
        "reasons": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["verdict"],
    "additionalProperties": False,
}


def verdict_failed(result: dict) -> bool:
    """Interpret a verifier dispatch result (REQ-AUTO-003 / REQ-WF-002): True only when the
    verifier returned a clean `fail` verdict. A missing/unparseable/unavailable verdict is
    treated as NOT-failed — the verifier is an extra check on an already-passing result, so a
    broken or unavailable verifier degrades gracefully rather than blocking (REQ-NF-013).
    Never raises.
    """
    if not isinstance(result, dict):
        return False
    payload = result.get("result")
    if not isinstance(payload, str) or not payload.strip():
        return False
    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        return False
    return isinstance(data, dict) and str(data.get("verdict", "")).lower() == "fail"


def should_heal(attempts_used: int, max_heal_attempts: int) -> bool:
    """True when another bounded self-heal may be attempted (REQ-AUTO-001/002 / REQ-WF-002).

    Capped by `max_heal_attempts` (autopilot default 1; 0 = stop-on-gate). `attempts_used` is
    the number of heals already tried. This is the config-agnostic primitive; autopilot's
    `should_heal(attempts_used, config)` delegates here with `config.max_heal_attempts`, and the
    workflow engine passes its own cap. Never raises.
    """
    return isinstance(max_heal_attempts, int) and attempts_used < max_heal_attempts


def run_verify(
    prompt: str,
    dispatch_fn,
    kwargs: dict,
    *,
    schema: Optional[dict] = None,
) -> dict:
    """Run one independent, fresh-session, schema-constrained verifier dispatch and return a
    result dict whose `result` field carries the verdict JSON for `verdict_failed` (REQ-WF-002).

    This is the engine-facing primitive: the caller supplies the verifier `prompt`, the same
    `dispatch_fn` the engine uses for node dispatch, and the per-dispatch `kwargs` (forge_dir,
    feature, model, budget, cwd, ...). Independence is enforced here — `resume` is forced to
    `None` (fresh session, never reusing the produced node's session) and `output_schema` to the
    given `schema` (default `VERIFY_SCHEMA`). Never raises: any dispatch failure degrades to a
    result that `verdict_failed` reads as not-failed (an unavailable verifier must not block).
    """
    call = dict(kwargs)
    call["resume"] = None  # fresh context — independence (REQ-AUTO-003)
    call["output_schema"] = schema if schema is not None else VERIFY_SCHEMA
    try:
        res = dispatch_fn(prompt, **call)
    except Exception as exc:  # noqa: BLE001 — a broken verifier must degrade, never raise
        _LOG.warning("run_verify: dispatch raised: %s", exc)
        return {"status": "error", "reason": str(exc), "result": None, "cost_usd": 0.0}
    return {
        "status": getattr(res, "status", "error"),
        "reason": getattr(res, "reason", ""),
        "result": getattr(res, "result", None),
        "cost_usd": float(getattr(res, "cost_usd", 0.0) or 0.0),
    }
