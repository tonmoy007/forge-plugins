"""Tests for scripts/validate-plugin.py."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# Load validate-plugin.py by path since the hyphen makes it non-importable by name
_script = Path(__file__).parent.parent.parent / "scripts" / "validate-plugin.py"
_spec = importlib.util.spec_from_file_location("validate_plugin", _script)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
validate = _mod.validate


@pytest.fixture
def good_plugin(tmp_path: Path) -> Path:
    plugin_dir = tmp_path / ".claude-plugin"
    plugin_dir.mkdir()
    path = plugin_dir / "plugin.json"
    path.write_text(json.dumps({
        "name": "forge",
        "version": "0.1.0",
        "hooks": {
            "SessionStart": [{"hooks": [{"type": "command", "command": "python hooks/session-start.py"}]}]
        }
    }))
    return path


@pytest.fixture
def missing_name_plugin(tmp_path: Path) -> Path:
    plugin_dir = tmp_path / ".claude-plugin"
    plugin_dir.mkdir()
    path = plugin_dir / "plugin.json"
    path.write_text(json.dumps({
        "version": "0.1.0",
    }))
    return path


def test_good_plugin_passes(good_plugin: Path) -> None:
    assert validate(good_plugin) is True


def test_missing_name_fails(missing_name_plugin: Path) -> None:
    assert validate(missing_name_plugin) is False


def test_invalid_json_fails(tmp_path: Path) -> None:
    plugin_dir = tmp_path / ".claude-plugin"
    plugin_dir.mkdir()
    path = plugin_dir / "plugin.json"
    path.write_text("{ not valid json }")
    assert validate(path) is False


def test_missing_file_fails(tmp_path: Path) -> None:
    assert validate(tmp_path / ".claude-plugin" / "plugin.json") is False


def test_unknown_hook_event_fails(tmp_path: Path) -> None:
    plugin_dir = tmp_path / ".claude-plugin"
    plugin_dir.mkdir()
    path = plugin_dir / "plugin.json"
    path.write_text(json.dumps({
        "name": "forge",
        "version": "0.1.0",
        "hooks": {
            "UnknownEvent": [{"hooks": []}]
        }
    }))
    assert validate(path) is False


def test_manifest_without_claude_code_version_passes(tmp_path: Path) -> None:
    """Regression: claude_code_version is NOT a real manifest field (removed in
    v0.1.1). A manifest omitting it must validate — the validator must not
    require a field that does not exist in the official schema."""
    plugin_dir = tmp_path / ".claude-plugin"
    plugin_dir.mkdir()
    path = plugin_dir / "plugin.json"
    path.write_text(json.dumps({"name": "forge", "version": "0.1.3"}))
    assert validate(path) is True


def test_real_repo_manifest_validates() -> None:
    """The actual shipped .claude-plugin/plugin.json must pass its own
    validator. Guards against the validator drifting from the real manifest
    (the exact failure that prompted this fix)."""
    repo_manifest = (
        Path(__file__).parent.parent.parent / ".claude-plugin" / "plugin.json"
    )
    assert validate(repo_manifest) is True
