"""T-236 / REQ-BUILDGEN-001: Code Generator sub-agent.

AC-BUILDGEN-001a: persona's Output Contract lists only code + test files as
                   output — no commit step, no progress.md write, no
                   gate-running, no context resolution of its own.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
AGENTS = ROOT / "agents"
AGENT_FILE = AGENTS / "code-generator.md"


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
    assert m, "code-generator has no allowed-tools"
    return [t.strip() for t in m.group(1).split(",") if t.strip()]


def _section(body: str, heading: str) -> str:
    pattern = rf"^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)"
    m = re.search(pattern, body, re.MULTILINE | re.DOTALL)
    assert m, f"'## {heading}' section not found"
    return m.group(1)


def _split_output_contract(body: str) -> tuple[str, str]:
    """Split Output Contract into (produces list, must-not list)."""
    section = _section(body, "Output Contract")
    parts = re.split(r"You MUST NOT:", section, maxsplit=1)
    assert len(parts) == 2, "Output Contract must have a 'You MUST NOT' list"
    return parts[0], parts[1]


def test_agent_file_exists() -> None:
    assert AGENT_FILE.exists()


def test_frontmatter_parses() -> None:
    frontmatter, _ = _frontmatter_and_body()
    assert isinstance(frontmatter, dict)


def test_frontmatter_name_is_code_generator() -> None:
    frontmatter, _ = _frontmatter_and_body()
    assert frontmatter.get("name") == "code-generator"


def test_allowed_tools_includes_required_set() -> None:
    tools = _frontmatter_tools()
    for tool in ("Read", "Write", "Edit", "Bash", "Grep", "Glob"):
        assert tool in tools


def test_output_contract_produces_only_code_and_tests() -> None:
    _, body = _frontmatter_and_body()
    produces, _ = _split_output_contract(body)
    lower = produces.lower()
    assert "code" in lower
    assert "test" in lower
    # commit / progress.md must not appear as things it does
    assert "commit" not in lower
    assert "progress.md" not in lower


def test_output_contract_states_no_commit() -> None:
    _, body = _frontmatter_and_body()
    _, must_not = _split_output_contract(body)
    assert "commit" in must_not.lower()


def test_output_contract_states_no_progress_md_write() -> None:
    _, body = _frontmatter_and_body()
    _, must_not = _split_output_contract(body)
    assert "progress.md" in must_not.lower()


def test_output_contract_states_no_gate_running() -> None:
    _, body = _frontmatter_and_body()
    _, must_not = _split_output_contract(body)
    lower = must_not.lower()
    assert "gate" in lower or ("lint" in lower and "compile" in lower)


def test_body_states_does_not_resolve_context_itself() -> None:
    _, body = _frontmatter_and_body()
    lower = body.lower()
    assert "context bundle" in lower
    assert "does not resolve context" in lower or "do not resolve context" in lower


def test_body_never_instructs_committing_as_a_step() -> None:
    _, body = _frontmatter_and_body()
    # builder.md's own phrasing for its commit step — must not carry over
    assert "commit with message" not in body.lower()
