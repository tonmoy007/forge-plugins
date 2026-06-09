"""Tests for T-107 additions:

  - scripts/detect-project-type.py — _finalize() aliasing + script suggestion
  - scripts/check-script-runnable.py
  - scripts/check-script-has-tests.py

Existing detect() behavior is not retested here — its tests should live in
tests/unit/test_detect_project_type.py alongside the original v0.1.0 cases.
This file is additive and intentionally narrow to the T-107 scope.

Run with: python -m pytest tests/unit/test_detect_project_type_script.py -q
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts"


def _import(name: str):
    """Import a hyphenated script by absolute path."""
    path = SCRIPTS / f"{name}.py"
    module_name = name.replace("-", "_")
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


detect_mod = _import("detect-project-type")
runnable_mod = _import("check-script-runnable")
tests_mod = _import("check-script-has-tests")


# ---------- _finalize: alias ----------

class TestFinalizeAlias:
    def test_project_type_mirrors_type(self, tmp_path):
        r = detect_mod._finalize({"type": "api", "confidence": 0.9, "indicators": []}, str(tmp_path))
        assert r["type"] == "api"
        assert r["project_type"] == "api"

    def test_does_not_overwrite_existing_project_type(self, tmp_path):
        r = detect_mod._finalize(
            {"type": "api", "project_type": "library", "confidence": 0.9, "indicators": []},
            str(tmp_path),
        )
        assert r["project_type"] == "library"  # caller's explicit value wins

    def test_no_type_field_does_not_crash(self, tmp_path):
        r = detect_mod._finalize({"confidence": 0.0}, str(tmp_path))
        assert "project_type" not in r  # nothing to alias


# ---------- _finalize: script suggestion ----------

def _make_tiny_script_project(root: Path, *, loc: int = 100) -> Path:
    """Create a small project with a single Python file of `loc` non-blank lines."""
    proj = root / "tiny"
    proj.mkdir()
    lines = ["print('hello')"] * loc
    (proj / "tool.py").write_text("\n".join(lines) + "\n")
    return proj


class TestScriptSuggestion:
    def test_tiny_project_gets_script_suggestion(self, tmp_path):
        proj = _make_tiny_script_project(tmp_path, loc=50)
        # detect() will return unknown (no manifests, no signals)
        result = detect_mod._finalize(detect_mod.detect(str(proj)), str(proj))
        assert result["type"] == "unknown"
        assert result.get("suggested_profile") == "script"
        assert result["suggested_profile_confidence"] == detect_mod._SCRIPT_CONFIDENCE
        assert result["suggested_profile_metadata"]["loc"] == 50
        # Indicators are populated
        assert any("LOC" in s for s in result["suggested_profile_indicators"])

    def test_project_with_setup_py_no_suggestion(self, tmp_path):
        proj = _make_tiny_script_project(tmp_path, loc=50)
        (proj / "setup.py").write_text("from setuptools import setup\nsetup()\n")
        # Existing detect() will return library; even if it returned unknown, the
        # presence of setup.py disqualifies the script suggestion.
        result = detect_mod._finalize(
            {"type": "unknown", "confidence": 0.0, "indicators": []},
            str(proj),
        )
        assert "suggested_profile" not in result

    def test_project_with_package_json_no_suggestion(self, tmp_path):
        proj = _make_tiny_script_project(tmp_path, loc=50)
        (proj / "package.json").write_text("{}")
        result = detect_mod._finalize(
            {"type": "unknown", "confidence": 0.0, "indicators": []},
            str(proj),
        )
        assert "suggested_profile" not in result

    def test_large_project_no_suggestion(self, tmp_path):
        # Over 500 LOC → no suggestion even with no manifest.
        proj = _make_tiny_script_project(tmp_path, loc=600)
        result = detect_mod._finalize(
            {"type": "unknown", "confidence": 0.0, "indicators": []},
            str(proj),
        )
        assert "suggested_profile" not in result

    def test_too_many_files_no_suggestion(self, tmp_path):
        proj = tmp_path / "many"
        proj.mkdir()
        for i in range(25):
            (proj / f"f{i}.py").write_text("print(1)\n")
        result = detect_mod._finalize(
            {"type": "unknown", "confidence": 0.0, "indicators": []},
            str(proj),
        )
        assert "suggested_profile" not in result

    def test_mixed_language_no_suggestion(self, tmp_path):
        # Has a Go file → fails the language-subset check.
        proj = _make_tiny_script_project(tmp_path, loc=50)
        (proj / "main.go").write_text("package main\nfunc main() {}\n")
        result = detect_mod._finalize(
            {"type": "unknown", "confidence": 0.0, "indicators": []},
            str(proj),
        )
        assert "suggested_profile" not in result

    def test_empty_project_no_suggestion(self, tmp_path):
        # No source files at all → no suggestion.
        proj = tmp_path / "empty"
        proj.mkdir()
        result = detect_mod._finalize(
            {"type": "unknown", "confidence": 0.0, "indicators": []},
            str(proj),
        )
        assert "suggested_profile" not in result

    def test_already_classified_no_suggestion(self, tmp_path):
        # If detect() found something non-unknown, don't suggest script.
        proj = _make_tiny_script_project(tmp_path, loc=50)
        result = detect_mod._finalize(
            {"type": "api", "confidence": 0.9, "indicators": []},
            str(proj),
        )
        assert "suggested_profile" not in result

    def test_forge_dirs_excluded_from_count(self, tmp_path):
        proj = _make_tiny_script_project(tmp_path, loc=50)
        # Add a fake .forge/ and pipeline/ that would push file count over threshold
        # if not ignored.
        (proj / ".forge").mkdir()
        for i in range(30):
            (proj / ".forge" / f"x{i}.json").write_text("{}")
        (proj / "pipeline").mkdir()
        for i in range(15):
            (proj / "pipeline" / f"f{i}.md").write_text("x")
        result = detect_mod._finalize(
            {"type": "unknown", "confidence": 0.0, "indicators": []},
            str(proj),
        )
        # Should still suggest script — the Forge dirs are ignored.
        assert result.get("suggested_profile") == "script"


# ---------- _count_loc / _is_language_subset helpers ----------

class TestHelpers:
    def test_count_loc_skips_blank_and_comments(self, tmp_path):
        (tmp_path / "x.py").write_text(
            "# comment\n"
            "\n"
            "print(1)\n"
            "  # indented comment\n"
            "print(2)\n"
        )
        assert detect_mod._count_loc(str(tmp_path), detect_mod._SCRIPT_EXTENSIONS) == 2

    def test_count_files_excludes_hidden(self, tmp_path):
        (tmp_path / "visible.py").write_text("x")
        (tmp_path / ".hidden").write_text("x")
        (tmp_path / ".dotdir").mkdir()
        (tmp_path / ".dotdir" / "y.py").write_text("x")
        assert detect_mod._count_files(str(tmp_path)) == 1

    def test_language_subset_passes(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        (tmp_path / "b.sh").write_text("#!/bin/sh\n")
        assert detect_mod._is_language_subset(
            str(tmp_path), detect_mod._SCRIPT_EXTENSIONS,
        )

    def test_language_subset_fails_on_disallowed_ext(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        (tmp_path / "b.go").write_text("package main")
        assert not detect_mod._is_language_subset(
            str(tmp_path), detect_mod._SCRIPT_EXTENSIONS,
        )

    def test_language_subset_ignores_extensionless(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        (tmp_path / "Makefile").write_text("all:\n\techo hi\n")  # no extension
        assert detect_mod._is_language_subset(
            str(tmp_path), detect_mod._SCRIPT_EXTENSIONS,
        )

    def test_language_subset_empty_returns_false(self, tmp_path):
        assert not detect_mod._is_language_subset(
            str(tmp_path), detect_mod._SCRIPT_EXTENSIONS,
        )


# ---------- check-script-runnable.py ----------

class TestRunnable:
    def test_python_parses(self, tmp_path):
        (tmp_path / "tool.py").write_text("print('hi')\n")
        found, msg = runnable_mod.find_runnable(tmp_path)
        assert found
        assert "tool.py" in msg

    def test_python_with_syntax_error_not_runnable(self, tmp_path):
        (tmp_path / "tool.py").write_text("def broken(\n")
        found, _ = runnable_mod.find_runnable(tmp_path)
        assert not found

    def test_shell_with_shebang(self, tmp_path):
        (tmp_path / "tool.sh").write_text("#!/bin/bash\necho hi\n")
        found, msg = runnable_mod.find_runnable(tmp_path)
        assert found
        assert "tool.sh" in msg

    def test_shell_without_shebang_not_runnable(self, tmp_path):
        (tmp_path / "tool.sh").write_text("echo hi\n")
        found, _ = runnable_mod.find_runnable(tmp_path)
        assert not found

    def test_extensionless_with_shebang(self, tmp_path):
        f = tmp_path / "mytool"
        f.write_text("#!/usr/bin/env python3\nprint('hi')\n")
        found, msg = runnable_mod.find_runnable(tmp_path)
        assert found
        assert "mytool" in msg

    def test_ignored_dirs_skipped(self, tmp_path):
        # Only runnable file is under .venv/ — should be ignored.
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "tool.py").write_text("print('hi')\n")
        found, _ = runnable_mod.find_runnable(tmp_path)
        assert not found

    def test_pipeline_dir_skipped(self, tmp_path):
        # Files inside pipeline/ should be ignored (Forge artifacts, not user code)
        (tmp_path / "pipeline").mkdir()
        (tmp_path / "pipeline" / "tool.py").write_text("print('hi')\n")
        found, _ = runnable_mod.find_runnable(tmp_path)
        assert not found

    def test_cli_exit_codes(self, tmp_path, capsys):
        # Failure case
        rc = runnable_mod.main(["--cwd", str(tmp_path)])
        assert rc == 1
        # Success case
        (tmp_path / "ok.py").write_text("print('x')\n")
        rc = runnable_mod.main(["--cwd", str(tmp_path)])
        assert rc == 0


# ---------- check-script-has-tests.py ----------

class TestHasTests:
    def test_pytest_style_file(self, tmp_path):
        (tmp_path / "test_thing.py").write_text("def test_x(): pass\n")
        found, msg = tests_mod.find_tests(tmp_path)
        assert found
        assert "test_thing.py" in msg

    def test_suffix_style_file(self, tmp_path):
        (tmp_path / "thing_test.py").write_text("def test_x(): pass\n")
        found, _ = tests_mod.find_tests(tmp_path)
        assert found

    def test_shell_test_file(self, tmp_path):
        (tmp_path / "tool.test.sh").write_text("#!/bin/bash\necho ok\n")
        found, _ = tests_mod.find_tests(tmp_path)
        assert found

    def test_tests_dir_with_runnable(self, tmp_path):
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "smoke.py").write_text("print('ok')\n")
        found, msg = tests_mod.find_tests(tmp_path)
        assert found
        assert "tests/" in msg

    def test_examples_dir_with_runnable(self, tmp_path):
        (tmp_path / "examples").mkdir()
        (tmp_path / "examples" / "demo.py").write_text("print('demo')\n")
        found, msg = tests_mod.find_tests(tmp_path)
        assert found
        assert "examples/" in msg

    def test_no_tests_anywhere(self, tmp_path):
        (tmp_path / "tool.py").write_text("print('hi')\n")
        (tmp_path / "README.md").write_text("# hi")
        found, msg = tests_mod.find_tests(tmp_path)
        assert not found
        assert "no tests found" in msg.lower()

    def test_ignored_dirs_not_counted(self, tmp_path):
        # Test inside .venv/ doesn't count
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "test_thing.py").write_text("def test_x(): pass\n")
        found, _ = tests_mod.find_tests(tmp_path)
        assert not found

    def test_hidden_files_ignored(self, tmp_path):
        (tmp_path / ".test_hidden.py").write_text("def test_x(): pass\n")
        found, _ = tests_mod.find_tests(tmp_path)
        assert not found

    def test_cli_exit_codes(self, tmp_path):
        rc = tests_mod.main(["--cwd", str(tmp_path)])
        assert rc == 1
        (tmp_path / "test_x.py").write_text("def test_x(): pass\n")
        rc = tests_mod.main(["--cwd", str(tmp_path)])
        assert rc == 0


# ---------- end-to-end via CLI ----------

class TestDetectCLI:
    def test_outputs_valid_json_with_project_type(self, tmp_path, capsys, monkeypatch):
        proj = _make_tiny_script_project(tmp_path, loc=50)
        monkeypatch.setattr(sys, "argv", ["detect-project-type.py", "--cwd", str(proj)])
        try:
            detect_mod.main()
        except SystemExit:
            pass
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "project_type" in data
        assert data["project_type"] == "unknown"
        assert data.get("suggested_profile") == "script"


# ---------- detect: monorepo (T-131 / REQ-PROFILE-MONOREPO-001) ----------

class TestMonorepoDetection:
    def test_pnpm_workspace_classifies_monorepo(self, tmp_path):
        (tmp_path / "pnpm-workspace.yaml").write_text("packages:\n  - 'packages/*'\n")
        result = detect_mod.detect(str(tmp_path))
        assert result["type"] == "monorepo"
        assert result["confidence"] >= 0.85

    def test_workspaces_field_in_package_json_classifies_monorepo(self, tmp_path):
        (tmp_path / "package.json").write_text(
            '{"name": "root", "private": true, "workspaces": ["packages/*"]}'
        )
        result = detect_mod.detect(str(tmp_path))
        assert result["type"] == "monorepo"

    def test_turbo_json_classifies_monorepo(self, tmp_path):
        (tmp_path / "turbo.json").write_text('{"pipeline": {}}')
        assert detect_mod.detect(str(tmp_path))["type"] == "monorepo"

    def test_cargo_workspace_classifies_monorepo(self, tmp_path):
        (tmp_path / "Cargo.toml").write_text("[workspace]\nmembers = [\"crates/*\"]\n")
        assert detect_mod.detect(str(tmp_path))["type"] == "monorepo"

    def test_packages_and_apps_dirs_classify_monorepo(self, tmp_path):
        (tmp_path / "packages").mkdir()
        (tmp_path / "apps").mkdir()
        assert detect_mod.detect(str(tmp_path))["type"] == "monorepo"

    def test_monorepo_with_nextjs_app_wins_over_fullstack(self, tmp_path):
        # A monorepo that contains a Next.js app at the root must still be
        # classified `monorepo` — the wrapper signal takes precedence.
        (tmp_path / "pnpm-workspace.yaml").write_text("packages:\n  - 'apps/*'\n")
        (tmp_path / "package.json").write_text(
            '{"name": "root", "workspaces": ["apps/*"], "dependencies": {"next": "14.0.0"}}'
        )
        (tmp_path / "next.config.js").write_text("module.exports = {}\n")
        result = detect_mod.detect(str(tmp_path))
        assert result["type"] == "monorepo"

    def test_plain_fullstack_not_monorepo(self, tmp_path):
        # Single-package Next.js app must NOT be mistaken for a monorepo.
        (tmp_path / "package.json").write_text(
            '{"name": "app", "dependencies": {"next": "14.0.0"}}'
        )
        (tmp_path / "next.config.js").write_text("module.exports = {}\n")
        assert detect_mod.detect(str(tmp_path))["type"] == "fullstack"

    def test_plain_api_not_monorepo(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("fastapi\n")
        assert detect_mod.detect(str(tmp_path))["type"] == "api"

    def test_only_packages_dir_not_monorepo(self, tmp_path):
        # packages/ alone (without apps/ or a workspace manifest) is not enough.
        (tmp_path / "packages").mkdir()
        assert detect_mod.detect(str(tmp_path))["type"] != "monorepo"


# ---------- detect: mobile (T-132 / REQ-PROFILE-MOBILE-001) ----------

class TestMobileDetection:
    def test_flutter_with_lib_dir_classifies_mobile(self, tmp_path):
        (tmp_path / "pubspec.yaml").write_text("name: myapp\nflutter:\n  uses-material-design: true\n")
        (tmp_path / "lib").mkdir()
        result = detect_mod.detect(str(tmp_path))
        assert result["type"] == "mobile"
        assert result["confidence"] >= 0.85

    def test_ios_podfile_classifies_mobile(self, tmp_path):
        (tmp_path / "Podfile").write_text("platform :ios, '13.0'\n")
        assert detect_mod.detect(str(tmp_path))["type"] == "mobile"

    def test_ios_xcodeproj_classifies_mobile(self, tmp_path):
        (tmp_path / "MyApp.xcodeproj").mkdir()
        assert detect_mod.detect(str(tmp_path))["type"] == "mobile"

    def test_android_dir_with_build_gradle_classifies_mobile(self, tmp_path):
        (tmp_path / "android").mkdir()
        (tmp_path / "build.gradle").write_text("apply plugin: 'com.android.application'\n")
        assert detect_mod.detect(str(tmp_path))["type"] == "mobile"

    def test_react_native_classifies_mobile(self, tmp_path):
        (tmp_path / "package.json").write_text(
            '{"name": "app", "dependencies": {"react-native": "0.73.0", "react": "18.2.0"}}'
        )
        assert detect_mod.detect(str(tmp_path))["type"] == "mobile"

    def test_react_native_is_mobile_not_fullstack(self, tmp_path):
        # A React Native repo has package.json but must NOT fall through to fullstack.
        (tmp_path / "package.json").write_text(
            '{"name": "app", "dependencies": {"react-native": "0.73.0"}}'
        )
        result = detect_mod.detect(str(tmp_path))
        assert result["type"] == "mobile"
        assert result["type"] != "fullstack"

    def test_plain_fullstack_not_mobile(self, tmp_path):
        # Sanity: a Next.js app with no mobile signal stays fullstack.
        (tmp_path / "package.json").write_text(
            '{"name": "app", "dependencies": {"next": "14.0.0"}}'
        )
        (tmp_path / "next.config.js").write_text("module.exports = {}\n")
        assert detect_mod.detect(str(tmp_path))["type"] == "fullstack"


# ---------- detect: data-contract (T-133 / REQ-PROFILE-DATACONTRACT-001) ----------

class TestDataContractDetection:
    def test_root_proto_file_classifies_data_contract(self, tmp_path):
        (tmp_path / "user.proto").write_text(
            'syntax = "proto3";\nmessage User { string id = 1; }\n'
        )
        result = detect_mod.detect(str(tmp_path))
        assert result["type"] == "data-contract"
        assert result["confidence"] >= 0.8

    def test_schemas_dir_classifies_data_contract(self, tmp_path):
        schemas = tmp_path / "schemas"
        schemas.mkdir()
        (schemas / "event.avsc").write_text('{"type": "record", "name": "Event"}')
        assert detect_mod.detect(str(tmp_path))["type"] == "data-contract"

    def test_buf_yaml_classifies_data_contract(self, tmp_path):
        (tmp_path / "buf.yaml").write_text("version: v1\nbreaking:\n  use: [FILE]\n")
        assert detect_mod.detect(str(tmp_path))["type"] == "data-contract"

    def test_proto_is_not_api_or_library(self, tmp_path):
        (tmp_path / "schema.proto").write_text("message M { int32 x = 1; }\n")
        t = detect_mod.detect(str(tmp_path))["type"]
        assert t == "data-contract"
        assert t not in ("api", "library")

    def test_grpc_service_with_server_dep_stays_api(self, tmp_path):
        # A real service that also ships .proto has an API framework dep — it
        # must fall through to `api`, not be stolen by data-contract.
        (tmp_path / "api.proto").write_text("message Req { int32 x = 1; }\n")
        (tmp_path / "requirements.txt").write_text("fastapi\ngrpcio\n")
        assert detect_mod.detect(str(tmp_path))["type"] == "api"

    def test_plain_library_not_data_contract(self, tmp_path):
        # Sanity: a Python library with no schema files stays library.
        (tmp_path / "setup.py").write_text("from setuptools import setup\nsetup()\n")
        assert detect_mod.detect(str(tmp_path))["type"] != "data-contract"