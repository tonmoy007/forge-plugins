"""T-237 / REQ-BUILDGATE-001: Quality Gate Runner sub-agent.

AC-BUILDGATE-001a: persona runs all four checks (compile, lint, test, static
                    analysis) and reports pass/fail per check, not a single
                    aggregate boolean.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
AGENTS = ROOT / "agents"
AGENT_FILE = AGENTS / "quality-gate-runner.md"


def _frontmatter_and_body() -> tuple[dict, str]:
    text = AGENT_FILE.read_text()
    parts = text.split("---", 2)
    assert len(parts) == 3, "expected `---` delimited frontmatter"
    frontmatter = yaml.safe_load(parts[1])
    body = parts[2]
    return frontmatter, body


def _frontmatter_tools() -> list[str]:
    text = AGENT_FILE.read_text()
    m = re.search(r"^allowed-tools:\s*\[(.*?)\]", text, re.MULTILINE)
    assert m, "quality-gate-runner has no allowed-tools"
    return [t.strip() for t in m.group(1).split(",") if t.strip()]


def test_agent_file_exists() -> None:
    assert AGENT_FILE.exists()


def test_frontmatter_parses() -> None:
    frontmatter, _ = _frontmatter_and_body()
    assert isinstance(frontmatter, dict)


def test_frontmatter_name_is_quality_gate_runner() -> None:
    frontmatter, _ = _frontmatter_and_body()
    assert frontmatter.get("name") == "quality-gate-runner"


def test_allowed_tools_includes_bash_and_read() -> None:
    tools = _frontmatter_tools()
    assert "Bash" in tools
    assert "Read" in tools


def test_body_documents_all_four_checks_by_name() -> None:
    _, body = _frontmatter_and_body()
    lower = body.lower()
    assert "compile" in lower
    assert "lint" in lower
    assert "test" in lower
    assert "static analysis" in lower


def test_body_states_per_check_reporting_not_aggregate_boolean() -> None:
    _, body = _frontmatter_and_body()
    lower = body.lower()
    assert "pass/fail" in lower or "pass or fail" in lower
    assert "aggregate boolean" in lower or "single boolean" in lower


def test_body_states_one_agent_not_four() -> None:
    _, body = _frontmatter_and_body()
    lower = body.lower()
    assert "one agent" in lower or "single agent" in lower


def test_no_separate_linter_persona_created() -> None:
    assert not (AGENTS / "linter.md").exists()


def test_no_separate_static_analyzer_persona_created() -> None:
    assert not (AGENTS / "static-analyzer.md").exists()


def test_no_separate_build_runner_persona_created() -> None:
    assert not (AGENTS / "build-runner.md").exists()
