"""Tests for scripts/check_monorepo_graph.py — T-131 / REQ-PROFILE-MONOREPO-001.

The gate discovers internal workspace packages (every package.json under
`packages/` and `apps/`), builds an internal dependency graph, and fails if the
graph contains a cycle.

Run with: python3 -m pytest tests/unit/test_check_monorepo_graph.py -q
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts"


def _import(name: str):
    """Import a (possibly hyphenated) script by absolute path."""
    path = SCRIPTS / f"{name}.py"
    module_name = name.replace("-", "_")
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


graph_mod = _import("check_monorepo_graph")


def _pkg(root: Path, group: str, dir_name: str, name: str, deps: dict | None = None) -> None:
    """Write packages/<dir_name>/package.json with name + dependencies."""
    pkg_dir = root / group / dir_name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    data: dict = {"name": name}
    if deps:
        data["dependencies"] = deps
    (pkg_dir / "package.json").write_text(json.dumps(data))


class TestAcyclic:
    def test_acyclic_workspace_passes(self, tmp_path):
        # app -> ui -> core (a DAG, no cycle)
        _pkg(tmp_path, "packages", "core", "@acme/core")
        _pkg(tmp_path, "packages", "ui", "@acme/ui", {"@acme/core": "1.0.0"})
        _pkg(tmp_path, "apps", "web", "@acme/web", {"@acme/ui": "1.0.0"})
        assert graph_mod.main(["--cwd", str(tmp_path)]) == 0

    def test_external_deps_ignored(self, tmp_path):
        # Only external deps (react) — not internal, so no cycle possible.
        _pkg(tmp_path, "packages", "core", "@acme/core", {"react": "18.0.0"})
        _pkg(tmp_path, "apps", "web", "@acme/web", {"react": "18.0.0"})
        assert graph_mod.main(["--cwd", str(tmp_path)]) == 0


class TestCyclic:
    def test_internal_cycle_fails(self, tmp_path, capsys):
        # A depends on B, B depends on A — a 2-node cycle.
        _pkg(tmp_path, "packages", "a", "@acme/a", {"@acme/b": "1.0.0"})
        _pkg(tmp_path, "packages", "b", "@acme/b", {"@acme/a": "1.0.0"})
        rc = graph_mod.main(["--cwd", str(tmp_path)])
        assert rc == 1
        out = capsys.readouterr().out
        assert "@acme/a" in out and "@acme/b" in out

    def test_cycle_via_dev_dependencies(self, tmp_path):
        # devDependencies also count toward the graph.
        (tmp_path / "packages" / "a").mkdir(parents=True)
        (tmp_path / "packages" / "b").mkdir(parents=True)
        (tmp_path / "packages" / "a" / "package.json").write_text(
            json.dumps({"name": "@acme/a", "devDependencies": {"@acme/b": "1.0.0"}})
        )
        (tmp_path / "packages" / "b" / "package.json").write_text(
            json.dumps({"name": "@acme/b", "devDependencies": {"@acme/a": "1.0.0"}})
        )
        assert graph_mod.main(["--cwd", str(tmp_path)]) == 1


class TestEdgeCases:
    def test_empty_workspace_passes(self, tmp_path):
        # No packages/ or apps/ at all → nothing to check → exit 0.
        assert graph_mod.main(["--cwd", str(tmp_path)]) == 0

    def test_no_packages_passes(self, tmp_path):
        # packages/ exists but contains no package.json files.
        (tmp_path / "packages").mkdir()
        (tmp_path / "apps").mkdir()
        assert graph_mod.main(["--cwd", str(tmp_path)]) == 0

    def test_garbled_json_skipped(self, tmp_path):
        # One broken package.json must not crash; the rest is acyclic → exit 0.
        _pkg(tmp_path, "packages", "core", "@acme/core")
        bad = tmp_path / "packages" / "bad"
        bad.mkdir(parents=True)
        (bad / "package.json").write_text("{ this is not json ")
        assert graph_mod.main(["--cwd", str(tmp_path)]) == 0
