"""T-121 / REQ-WEBSEARCH-001: WebSearch on research/spec agents, planner excluded.

AC-WEBSEARCH-001a: each affected agent lists WebSearch in its tools and contains
                   the cite-or-skip rule; the planner does not get WebSearch.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
AGENTS = ROOT / "agents"

WEB_AGENTS = ["requirements-analyst", "product-designer", "system-architect", "spec-writer"]
EXCLUDED = ["planner"]


def _frontmatter_tools(slug: str) -> list[str]:
    text = (AGENTS / f"{slug}.md").read_text()
    m = re.search(r"^allowed-tools:\s*\[(.*?)\]", text, re.MULTILINE)
    assert m, f"{slug} has no allowed-tools"
    return [t.strip() for t in m.group(1).split(",") if t.strip()]


@pytest.mark.parametrize("slug", WEB_AGENTS)
def test_research_agent_has_websearch(slug: str) -> None:
    assert "WebSearch" in _frontmatter_tools(slug)


@pytest.mark.parametrize("slug", WEB_AGENTS)
def test_research_agent_has_cite_or_skip_rule(slug: str) -> None:
    text = (AGENTS / f"{slug}.md").read_text()
    assert "REQ-WEBSEARCH-001" in text
    assert "Cite or skip" in text
    assert "cite" in text.lower()


@pytest.mark.parametrize("slug", EXCLUDED)
def test_planner_excluded_from_websearch(slug: str) -> None:
    tools = _frontmatter_tools(slug)
    assert "WebSearch" not in tools
    assert "REQ-WEBSEARCH-001" not in (AGENTS / f"{slug}.md").read_text()
