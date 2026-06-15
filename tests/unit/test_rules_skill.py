"""Structural tests for the /forge:rules skill + rules-format reference (T-158).

Guards the user-facing contract: the skill registers as a command, documents its
subcommands, and the reference documents every scope.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
_SKILL = _ROOT / "skills" / "forge-rules" / "SKILL.md"
_REF = _ROOT / "references" / "rules-format.md"

_SCOPES = ("always", "stage", "glob", "manual")


def _frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, "SKILL.md must start with a YAML frontmatter block"
    fm: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def test_skill_exists_with_valid_frontmatter() -> None:
    assert _SKILL.exists()
    fm = _frontmatter(_SKILL.read_text())
    # plugin name `forge` + `name: forge-rules` resolves to /forge:rules (set-profile idiom)
    assert fm.get("name") == "forge-rules"
    assert fm.get("description"), "skill needs a description for routing"


def test_skill_documents_subcommands() -> None:
    body = _SKILL.read_text()
    for sub in ("init", "add", "list", "validate"):
        assert re.search(rf"\b{sub}\b", body), f"skill should document `{sub}`"
    assert "scripts/rules.py" in body


def test_skill_states_advisory_no_op() -> None:
    body = _SKILL.read_text().lower()
    assert "advisory" in body
    assert "no-op" in body or "no op" in body  # absent dir = clean no-op


def test_reference_documents_all_scopes() -> None:
    assert _REF.exists()
    text = _REF.read_text()
    for scope in _SCOPES:
        assert scope in text, f"rules-format.md must document scope `{scope}`"
    assert ".forge/rules" in text
