"""Tests for scripts/bump-version.py.

bump-version.py is the single command that advances the plugin version: it
rewrites the `"version"` key in both manifests (asserting they matched first)
and inserts a dated CHANGELOG skeleton directly under `## [Unreleased]` — newest
section on top, fixing the manual-reorder gotcha hit during the v0.1.5 release.

Loaded by path because the hyphen in the filename blocks import-by-name.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_script = Path(__file__).parent.parent.parent / "scripts" / "bump-version.py"
_spec = importlib.util.spec_from_file_location("bump_version", _script)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


PLUGIN_JSON = json.dumps(
    {"name": "forge", "version": "0.1.5", "description": "x"}, indent=2
)
MARKETPLACE_JSON = json.dumps(
    {"name": "forge-plugins", "plugins": [{"name": "forge", "version": "0.1.5"}]},
    indent=2,
)
CHANGELOG = """# Changelog

---

## [Unreleased]

### Planned
- something later

---

## [0.1.5] — 2026-06-09

### Fixed
- a thing
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    cp = tmp_path / ".claude-plugin"
    cp.mkdir()
    (cp / "plugin.json").write_text(PLUGIN_JSON + "\n")
    (cp / "marketplace.json").write_text(MARKETPLACE_JSON + "\n")
    (tmp_path / "CHANGELOG.md").write_text(CHANGELOG)
    return tmp_path


def _version(path: Path) -> str:
    return json.loads(path.read_text())["version"] if "plugin.json" in path.name \
        else json.loads(path.read_text())["plugins"][0]["version"]


def test_both_manifests_bumped(repo: Path) -> None:
    rc = _mod.main(["0.1.6", "--repo-root", str(repo), "--date", "2026-06-10"])
    assert rc == 0
    assert _version(repo / ".claude-plugin" / "plugin.json") == "0.1.6"
    assert _version(repo / ".claude-plugin" / "marketplace.json") == "0.1.6"


def test_manifests_stay_valid_json(repo: Path) -> None:
    _mod.main(["0.1.6", "--repo-root", str(repo), "--date", "2026-06-10"])
    # Parses without error and preserves sibling keys.
    plugin = json.loads((repo / ".claude-plugin" / "plugin.json").read_text())
    assert plugin["name"] == "forge"
    assert plugin["description"] == "x"


def test_changelog_section_inserted_on_top(repo: Path) -> None:
    _mod.main(["0.1.6", "--repo-root", str(repo), "--date", "2026-06-10"])
    text = (repo / "CHANGELOG.md").read_text()
    assert "## [0.1.6] — 2026-06-10" in text
    # Newest release section must sit ABOVE the previous one.
    assert text.index("## [0.1.6]") < text.index("## [0.1.5]")
    # ...and below the Unreleased block.
    assert text.index("## [Unreleased]") < text.index("## [0.1.6]")


def test_mismatched_manifests_aborts(repo: Path) -> None:
    bad = json.dumps(
        {"name": "forge-plugins",
         "plugins": [{"name": "forge", "version": "0.1.4"}]},
        indent=2,
    )
    (repo / ".claude-plugin" / "marketplace.json").write_text(bad + "\n")
    rc = _mod.main(["0.1.6", "--repo-root", str(repo), "--date", "2026-06-10"])
    assert rc != 0
    # Nothing written on abort — plugin.json keeps its original version.
    assert _version(repo / ".claude-plugin" / "plugin.json") == "0.1.5"


def test_duplicate_version_aborts(repo: Path) -> None:
    # 0.1.5 section already exists — refuse to insert a second one.
    rc = _mod.main(["0.1.5", "--repo-root", str(repo), "--date", "2026-06-10"])
    assert rc != 0


def test_idempotent_safe_on_rerun(repo: Path) -> None:
    assert _mod.main(["0.1.6", "--repo-root", str(repo), "--date", "2026-06-10"]) == 0
    # Re-running the same bump must not double-insert; it aborts cleanly.
    assert _mod.main(["0.1.6", "--repo-root", str(repo), "--date", "2026-06-10"]) != 0
    text = (repo / "CHANGELOG.md").read_text()
    assert text.count("## [0.1.6]") == 1


def test_default_date_used_when_omitted(repo: Path) -> None:
    rc = _mod.main(["0.1.6", "--repo-root", str(repo)])
    assert rc == 0
    text = (repo / "CHANGELOG.md").read_text()
    # A YYYY-MM-DD stamp lands in the new section even without --date.
    import re
    assert re.search(r"## \[0\.1\.6\] — \d{4}-\d{2}-\d{2}", text)
