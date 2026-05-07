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
        "name": "sdlc-orchestrator",
        "version": "0.1.0",
        "claude_code_version": ">=2.1.0",
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
        "claude_code_version": ">=2.1.0",
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
        "name": "sdlc-orchestrator",
        "version": "0.1.0",
        "claude_code_version": ">=2.1.0",
        "hooks": {
            "UnknownEvent": [{"hooks": []}]
        }
    }))
    assert validate(path) is False
