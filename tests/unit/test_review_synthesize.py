"""Tests for scripts/review_synthesize.py (v0.2 P2 — T-149, REQ-F-034).

The first consumer of the orchestration primitive: fan independent review
dimensions out via _orchestrate.fan_out, then synthesize a single deduplicated,
severity-sorted report. Synthesis is a pure function (tested directly); run_review
is tested with a fake dispatch_fn (no real claude).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

_root = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location("review_synthesize", _root / "scripts" / "review_synthesize.py")
_rev = importlib.util.module_from_spec(_spec)
sys.modules["review_synthesize"] = _rev
_spec.loader.exec_module(_rev)

FORGE = Path("/tmp/nope")


def _f(file, line, severity, title, detail=""):
    return {"file": file, "line": line, "severity": severity, "title": title, "detail": detail}


# --- synthesize (pure) ------------------------------------------------------

def test_synthesize_dedups_across_dimensions() -> None:
    dim_results = [
        {"dimension": "correctness", "findings": [_f("a.py", 10, "high", "Off-by-one")]},
        {"dimension": "security", "findings": [_f("a.py", 10, "high", "off-by-one")]},  # dup (case)
    ]
    report = _rev.synthesize(dim_results)
    assert len(report["findings"]) == 1


def test_synthesize_sorts_by_severity() -> None:
    dim_results = [{"dimension": "d", "findings": [
        _f("a.py", 1, "low", "L"), _f("b.py", 2, "critical", "C"), _f("c.py", 3, "medium", "M"),
    ]}]
    sevs = [f["severity"] for f in _rev.synthesize(dim_results)["findings"]]
    assert sevs == ["critical", "medium", "low"]


def test_synthesize_empty_is_clean() -> None:
    report = _rev.synthesize([{"dimension": "d", "findings": []}])
    assert report["findings"] == []
    assert "no findings" in report["markdown"].lower()


# --- run_review (fan-out, injected dispatch) --------------------------------

def _dispatch_for(mapping):
    """Fake dispatch: prompt contains the dimension key; return its findings."""
    def disp(prompt, **kw):
        for key, findings in mapping.items():
            if key in prompt:
                payload = {"dimension": key, "findings": findings}
                return SimpleNamespace(status="ok", result=json.dumps(payload),
                                       cost_usd=0.01, raw={"is_error": False})
        return SimpleNamespace(status="ok", result=json.dumps({"dimension": "?", "findings": []}),
                               cost_usd=0.01, raw={"is_error": False})
    return disp


def test_run_review_aggregates_dimensions() -> None:
    disp = _dispatch_for({
        "correctness": [_f("x.py", 5, "high", "Bug")],
        "security": [_f("y.py", 9, "critical", "Injection")],
    })
    report = _rev.run_review("some diff", forge_dir=FORGE, dispatch_fn=disp)
    titles = {f["title"] for f in report["findings"]}
    assert {"Bug", "Injection"} <= titles
    assert report["findings"][0]["severity"] == "critical"  # sorted


def test_run_review_tolerates_malformed_dimension() -> None:
    def disp(prompt, **kw):
        if "security" in prompt:
            return SimpleNamespace(status="ok", result="not json", cost_usd=0.0, raw={})
        return SimpleNamespace(status="ok",
                               result=json.dumps({"dimension": "d", "findings": [_f("z.py", 1, "low", "Nit")]}),
                               cost_usd=0.0, raw={"is_error": False})
    report = _rev.run_review("diff", forge_dir=FORGE, dispatch_fn=disp)
    # the malformed dimension is dropped; the report is still produced from the rest
    assert any(f["title"] == "Nit" for f in report["findings"])
    assert report["dropped"] >= 1
