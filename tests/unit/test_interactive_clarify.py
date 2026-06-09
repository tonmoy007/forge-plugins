"""T-126 / REQ-INTERACTIVE-CLARIFY-001: bounded clarifying-question round in /forge:srs.

AC-CLARIFY-001a: skills/forge-srs/SKILL.md AND agents/requirements-analyst.md both
                 direct a single bounded clarifying-question round BEFORE srs.md is
                 written, with the bound explicit (one batch / not a drip / max cap).
AC-CLARIFY-001b: the same instructions require recording explicit assumptions for
                 unanswered items in the SRS.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SKILL = ROOT / "skills" / "forge-srs" / "SKILL.md"
AGENT = ROOT / "agents" / "requirements-analyst.md"


def test_agent_directs_bounded_single_round() -> None:
    text = AGENT.read_text()
    assert "REQ-INTERACTIVE-CLARIFY-001" in text
    # The bound must be explicit: one batch / single round / not a drip.
    assert re.search(r"single\s+(bounded\s+)?(batch|round)", text, re.IGNORECASE)
    assert re.search(r"not\s+a\s+drip", text, re.IGNORECASE)


def test_agent_orders_clarify_before_srs_written() -> None:
    text = AGENT.read_text()
    # Clarifying round must be tied to happening BEFORE srs.md is written.
    assert re.search(r"before\s+writing\s+`?(pipeline/01-srs/)?srs\.md`?", text, re.IGNORECASE)


def test_agent_records_assumptions_for_unanswered() -> None:
    text = AGENT.read_text()
    assert re.search(r"assumption", text, re.IGNORECASE)
    # Unanswered items become recorded assumptions in the SRS.
    assert re.search(r"unanswered", text, re.IGNORECASE)


def test_skill_directs_bounded_single_round_before_srs() -> None:
    text = SKILL.read_text()
    assert "REQ-INTERACTIVE-CLARIFY-001" in text
    assert re.search(r"single\s+(bounded\s+)?(batch|round)", text, re.IGNORECASE)
    assert re.search(r"not\s+a\s+drip", text, re.IGNORECASE)
    assert re.search(r"before\s+writing\s+`?(pipeline/01-srs/)?srs\.md`?", text, re.IGNORECASE)


def test_skill_records_assumptions_for_unanswered() -> None:
    text = SKILL.read_text()
    assert re.search(r"assumption", text, re.IGNORECASE)
    assert re.search(r"unanswered", text, re.IGNORECASE)
