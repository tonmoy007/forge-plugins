"""T-122 / REQ-INTERACTIVE-001: decomposed into >=2 concrete REQs.

AC-INTERACTIVE-001a: REQ-INTERACTIVE-001 is replaced in srs-v0.1.5.md by >=2
specific REQs (or explicitly dropped). Here it is replaced by three.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRS = ROOT / "build" / "01-srs" / "srs-v0.1.5.md"

CHILD_REQS = [
    "REQ-INTERACTIVE-CLARIFY-001",
    "REQ-INTERACTIVE-CONFIRM-001",
    "REQ-INTERACTIVE-NARRATE-001",
]


def test_replaced_by_at_least_two_concrete_reqs() -> None:
    text = SRS.read_text()
    present = [r for r in CHILD_REQS if r in text]
    assert len(present) >= 2, f"expected >=2 concrete interactive REQs, found {present}"


def test_each_child_has_acceptance_criterion() -> None:
    text = SRS.read_text()
    for req in CHILD_REQS:
        token = "AC-" + req[len("REQ-"):] + "a"  # e.g. AC-INTERACTIVE-CLARIFY-001a
        assert token in text, f"{req} missing its acceptance criterion {token}"


def test_parent_marked_decomposed_not_implemented() -> None:
    text = SRS.read_text()
    assert "REQ-INTERACTIVE-001 — DECOMPOSED" in text
    # parent acceptance explicitly satisfied
    assert re.search(r"AC-INTERACTIVE-001a.*satisfied", text)
