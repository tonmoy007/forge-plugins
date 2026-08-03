"""T-235 / REQ-BUILDCTX-001: Context Loader sub-agent.

AC-BUILDCTX-001a: given a task ID, output names only files/sections tied to that
                  task's declared Files — not the entire spec or architecture doc.
AC-BUILDCTX-001b: task resolution (reading the task-dag entry itself) is folded in —
                  no separate Task Resolver agent is created.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
AGENTS = ROOT / "agents"
SLUG = "context-loader"


def _agent_text() -> str:
    path = AGENTS / f"{SLUG}.md"
    assert path.exists(), f"{path} does not exist"
    return path.read_text()


def _frontmatter_block(text: str) -> str:
    parts = text.split("---")
    assert len(parts) >= 3, "agent file must have --- delimited frontmatter"
    return parts[1]


def _frontmatter_tools(text: str) -> list[str]:
    m = re.search(r"^allowed-tools:\s*\[(.*?)\]", text, re.MULTILINE)
    assert m, f"{SLUG} has no allowed-tools"
    return [t.strip() for t in m.group(1).split(",") if t.strip()]


def test_context_loader_agent_exists() -> None:
    assert (AGENTS / f"{SLUG}.md").exists()


def test_frontmatter_parses_as_yaml_mapping() -> None:
    data = yaml.safe_load(_frontmatter_block(_agent_text()))
    assert isinstance(data, dict)


def test_frontmatter_name_is_context_loader() -> None:
    data = yaml.safe_load(_frontmatter_block(_agent_text()))
    assert data.get("name") == SLUG


def test_allowed_tools_is_exactly_read_grep_glob() -> None:
    assert _frontmatter_tools(_agent_text()) == ["Read", "Grep", "Glob"]


@pytest.mark.parametrize("forbidden", ["Write", "Edit", "Bash"])
def test_allowed_tools_excludes_mutating_tools(forbidden: str) -> None:
    assert forbidden not in _frontmatter_tools(_agent_text())


def test_documents_task_relevant_only_contract() -> None:
    """AC-BUILDCTX-001a: only task-relevant docs, not the full spec/architecture."""
    text = _agent_text().lower()
    assert "only" in text
    assert "task-relevant" in text or "relevant" in text
    assert "full spec" in text or "entire spec" in text


def test_documents_folded_in_task_resolution() -> None:
    """AC-BUILDCTX-001b: task resolution is folded in, no separate Task Resolver."""
    text = _agent_text()
    assert re.search(r"task resolver", text, re.IGNORECASE)
    assert re.search(r"folded in|no separate", text, re.IGNORECASE)


def test_references_req_id() -> None:
    assert "REQ-BUILDCTX-001" in _agent_text()


def test_is_read_only_persona() -> None:
    text = _agent_text().lower()
    assert "read-only" in text or "read only" in text
