"""T-227 / REQ-TR-001/002: scripts/tool_preflight.py, the declarative tool registry
+ detection + cache.

Covers AC-TR-001: registry parses; presence/version via monkeypatched shutil.which
+ version_probe; required per required_when (Docker-artifact fixture marks docker
required, bare dir does not); TTL cache reused; missing/unreadable registry or
cache -> no-op, never raises; install returns the string and runs nothing.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import tool_preflight as tp  # noqa: E402


REGISTRY_TEXT = """\
# Tool Registry

```yaml
tools:
  - name: docker
    which: docker
    version_probe: ["docker", "--version"]
    workflows: [build, deploy]
    stages: [8]
    required_when: docker_artifacts_present
    install:
      darwin: "brew install --cask docker"
      linux: "curl -fsSL https://get.docker.com | sh"
      win32: "winget install Docker.DockerDesktop"

  - name: gh
    which: gh
    version_probe: ["gh", "--version"]
    workflows: [release]
    stages: [12]
    required_when: release_stage
    install:
      darwin: "brew install gh"
      linux: "sudo apt-get install gh"
      win32: "winget install GitHub.cli"
```
"""


def _write_registry(tmp_path: Path) -> Path:
    path = tmp_path / "tool-registry.md"
    path.write_text(REGISTRY_TEXT)
    return path


# --------------------------------------------------------------------------- #
# load_registry
# --------------------------------------------------------------------------- #


def test_load_registry_parses_seeded_tools(tmp_path: Path) -> None:
    entries = tp.load_registry(_write_registry(tmp_path))
    names = [e.name for e in entries]
    assert "docker" in names
    assert "gh" in names


def test_load_registry_missing_file_returns_empty_not_raise(tmp_path: Path) -> None:
    assert tp.load_registry(tmp_path / "does-not-exist.md") == []


def test_load_registry_malformed_yaml_returns_empty_not_raise(tmp_path: Path) -> None:
    path = tmp_path / "tool-registry.md"
    path.write_text("```yaml\ntools: [this is not: valid: yaml: at all\n```\n")
    assert tp.load_registry(path) == []


def test_load_registry_skips_malformed_entry_keeps_valid_ones(tmp_path: Path) -> None:
    path = tmp_path / "tool-registry.md"
    path.write_text(
        "```yaml\ntools:\n  - description: missing name and which\n"
        "  - name: docker\n    which: docker\n```\n"
    )
    entries = tp.load_registry(path)
    assert [e.name for e in entries] == ["docker"]


# --------------------------------------------------------------------------- #
# detect_tool — presence/version via monkeypatched shutil.which + version_probe
# --------------------------------------------------------------------------- #


def test_detect_tool_present_when_which_and_probe_succeed(tmp_path: Path, monkeypatch) -> None:
    entry = tp.ToolEntry(name="docker", which="docker", version_probe=["docker", "--version"])
    monkeypatch.setattr(tp.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(
        tp.subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="Docker version 27.0.0\n", stderr=""),
    )
    status = tp.detect_tool(entry, tmp_path)
    assert status.present is True
    assert "27.0.0" in status.version


def test_detect_tool_absent_when_which_finds_nothing(tmp_path: Path, monkeypatch) -> None:
    entry = tp.ToolEntry(name="docker", which="docker")
    monkeypatch.setattr(tp.shutil, "which", lambda name: None)
    status = tp.detect_tool(entry, tmp_path)
    assert status.present is False
    assert status.install_cmd is None or isinstance(status.install_cmd, str)


def test_detect_tool_absent_when_binary_present_but_probe_fails(tmp_path: Path, monkeypatch) -> None:
    """docker present but the compose plugin isn't -- probe failure means absent,
    even though `which` found the docker binary."""
    entry = tp.ToolEntry(name="docker compose", which="docker", version_probe=["docker", "compose", "version"])
    monkeypatch.setattr(tp.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(
        tp.subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 1, stdout="", stderr="unknown command"),
    )
    status = tp.detect_tool(entry, tmp_path)
    assert status.present is False


# --------------------------------------------------------------------------- #
# resolve_required — required_when
# --------------------------------------------------------------------------- #


def test_required_always_is_always_true(tmp_path: Path) -> None:
    entry = tp.ToolEntry(name="x", which="x", required_when="always")
    required, _ = tp.resolve_required(entry, tmp_path)
    assert required is True


def test_docker_artifacts_present_required_when_dockerfile_exists(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_text("FROM python:3.12\n")
    entry = tp.ToolEntry(name="docker", which="docker", required_when="docker_artifacts_present")
    required, reason = tp.resolve_required(entry, tmp_path)
    assert required is True
    assert "docker" in reason.lower()


def test_docker_artifacts_present_not_required_on_bare_dir(tmp_path: Path) -> None:
    entry = tp.ToolEntry(name="docker", which="docker", required_when="docker_artifacts_present")
    required, _ = tp.resolve_required(entry, tmp_path)
    assert required is False


def test_release_stage_required_only_at_stage_12(tmp_path: Path) -> None:
    (tmp_path / "pipeline").mkdir()
    (tmp_path / "pipeline" / "state.md").write_text(
        "---\nschema_version: 1\ncurrent_stage: 12\n---\n\n# Pipeline State\n"
    )
    entry = tp.ToolEntry(name="gh", which="gh", required_when="release_stage")
    required, _ = tp.resolve_required(entry, tmp_path)
    assert required is True


def test_release_stage_not_required_at_other_stages(tmp_path: Path) -> None:
    (tmp_path / "pipeline").mkdir()
    (tmp_path / "pipeline" / "state.md").write_text(
        "---\nschema_version: 1\ncurrent_stage: 3\n---\n\n# Pipeline State\n"
    )
    entry = tp.ToolEntry(name="gh", which="gh", required_when="release_stage")
    required, _ = tp.resolve_required(entry, tmp_path)
    assert required is False


# --------------------------------------------------------------------------- #
# TTL cache — write_status_cache / read_status_cache
# --------------------------------------------------------------------------- #


def test_write_and_read_status_cache_roundtrip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(tp.shutil, "which", lambda name: None)
    forge_dir = tmp_path / ".forge"
    tp.write_status_cache(forge_dir, tmp_path, registry_path=_write_registry(tmp_path))
    cached = tp.read_status_cache(forge_dir)
    assert cached is not None
    assert "docker" in cached


def test_read_status_cache_missing_returns_none(tmp_path: Path) -> None:
    assert tp.read_status_cache(tmp_path / ".forge") is None


def test_read_status_cache_unreadable_json_returns_none(tmp_path: Path) -> None:
    forge_dir = tmp_path / ".forge"
    forge_dir.mkdir()
    (forge_dir / "tool-status.json").write_text("{not valid json")
    assert tp.read_status_cache(forge_dir) is None


def test_write_status_cache_never_raises_on_unwritable_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(tp.shutil, "which", lambda name: None)
    # Point forge_dir at a path that can't be created (a file, not a directory).
    blocker = tmp_path / "blocker"
    blocker.write_text("x")
    tp.write_status_cache(blocker / "sub", tmp_path, registry_path=_write_registry(tmp_path))
    # Must not raise -- reaching this line is the assertion.


# --------------------------------------------------------------------------- #
# install_command — string only, never runs anything
# --------------------------------------------------------------------------- #


def test_install_command_returns_string_for_known_tool(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(tp.platform, "system", lambda: "Linux")
    cmd = tp.install_command("docker", tmp_path, registry_path=_write_registry(tmp_path))
    assert isinstance(cmd, str) and cmd


def test_install_command_none_for_unknown_tool(tmp_path: Path) -> None:
    assert tp.install_command("not-a-real-tool", tmp_path, registry_path=_write_registry(tmp_path)) is None


def test_install_command_never_executes_anything(tmp_path: Path, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(tp.subprocess, "run", lambda *a, **k: calls.append(a) or (_ for _ in ()).throw(
        AssertionError("install_command must never run a subprocess")
    ))
    tp.install_command("docker", tmp_path, registry_path=_write_registry(tmp_path))
    assert calls == []


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def test_cli_check_emits_json(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(tp, "_PLUGIN_DIR", tmp_path)
    monkeypatch.setattr(tp, "_DEFAULT_REGISTRY_REL", "tool-registry.md")
    _write_registry(tmp_path)
    monkeypatch.setattr(tp.shutil, "which", lambda name: None)
    rc = tp.main(["check", "--cwd", str(tmp_path)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert "docker" in out


def test_cli_refresh_writes_cache(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(tp, "_PLUGIN_DIR", tmp_path)
    monkeypatch.setattr(tp, "_DEFAULT_REGISTRY_REL", "tool-registry.md")
    _write_registry(tmp_path)
    monkeypatch.setattr(tp.shutil, "which", lambda name: None)
    forge_dir = tmp_path / ".forge"
    rc = tp.main(["refresh", "--forge-dir", str(forge_dir), "--cwd", str(tmp_path)])
    assert rc == 0
    assert tp.read_status_cache(forge_dir) is not None
