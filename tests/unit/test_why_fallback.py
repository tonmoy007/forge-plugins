"""Tests for the /forge:why LLM fallback (v0.2 P2 — T-151, REQ-F-050).

When deterministic ID lookup misses AND background capability is available, why.py
dispatches a single explainer via the orchestration primitive and returns a clearly
marked best-effort answer. Gated by capability + the FORGE_NO_BACKGROUND kill switch.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

_root = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location("why", _root / "scripts" / "why.py")
_why = importlib.util.module_from_spec(_spec)
sys.modules["why"] = _why
_spec.loader.exec_module(_why)


def _ok(explanation: str):
    return SimpleNamespace(status="ok", result=json.dumps({"explanation": explanation}),
                           cost_usd=0.01, raw={"is_error": False})


def test_llm_fallback_returns_marked_explanation(tmp_path: Path) -> None:
    disp = lambda prompt, **kw: _ok("G42-001 looks like a custom gate criterion.")
    text = _why._llm_fallback("G42-001", forge_dir=tmp_path / ".forge", dispatch_fn=disp)
    assert text is not None
    assert "custom gate criterion" in text
    # clearly marked as not authoritative
    assert "not a recognized" in text.lower() or "inferred" in text.lower() or "best-effort" in text.lower()


def test_llm_fallback_none_when_dropped(tmp_path: Path) -> None:
    disp = lambda prompt, **kw: SimpleNamespace(status="ok", result="not json", cost_usd=0.0, raw={})
    assert _why._llm_fallback("ZZZ", forge_dir=tmp_path / ".forge", dispatch_fn=disp) is None


def test_should_try_fallback_gating(tmp_path: Path, monkeypatch) -> None:
    forge = tmp_path / ".forge"
    forge.mkdir()
    # no capabilities.json → no fallback
    monkeypatch.delenv("FORGE_NO_BACKGROUND", raising=False)
    assert _why._should_try_fallback(forge) is False
    # available → yes
    (forge / "capabilities.json").write_text(json.dumps({"forge_background_available": True}))
    assert _why._should_try_fallback(forge) is True
    # kill switch overrides
    monkeypatch.setenv("FORGE_NO_BACKGROUND", "1")
    assert _why._should_try_fallback(forge) is False
