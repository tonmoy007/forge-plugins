"""T-124 / REQ-DOCS-001 + REQ-FEEDBACK-001: third-party-hook troubleshooting + issue template.

AC-DOCS-001a: a troubleshooting section exists with the diagnostic command and the
              Forge-vs-third-party distinction.
AC-DOCS-001b: it is linked from the README's "If something looks wrong" entry point.
REQ-FEEDBACK-001: the GitHub feedback issue template is present.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FEEDBACK_DOC = ROOT / "docs" / "getting-feedback.md"
README = ROOT / "README.md"
ISSUE_TEMPLATE = ROOT / ".github" / "ISSUE_TEMPLATE" / "forge-feedback.md"


def test_troubleshooting_section_exists() -> None:
    text = FEEDBACK_DOC.read_text()
    assert "Troubleshooting third-party plugin hooks" in text
    assert "/plugin list" in text                       # diagnostic command
    assert "pre-tool-write.py" in text                  # Forge-vs-third-party distinction
    assert "~/.claude/plugins/" in text                 # how to find the owner


def test_readme_links_troubleshooting() -> None:
    text = README.read_text()
    assert "If something looks wrong" in text
    assert "getting-feedback.md#troubleshooting-third-party-plugin-hooks" in text


def test_issue_template_present() -> None:
    assert ISSUE_TEMPLATE.exists()
    text = ISSUE_TEMPLATE.read_text()
    assert text.startswith("---")                       # front matter
    assert "name:" in text and "about:" in text
    assert "forge:doctor" in text.lower()


def test_readme_links_issue_template() -> None:
    assert ".github/ISSUE_TEMPLATE/forge-feedback.md" in README.read_text()
