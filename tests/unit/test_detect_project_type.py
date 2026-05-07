"""Tests for scripts/detect-project-type.py"""
import importlib.util
import os
import tempfile

# Hyphenated filename — must use importlib (see tasks/lessons.md)
_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../scripts/detect-project-type.py"))
_spec = importlib.util.spec_from_file_location("detect_project_type", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
detect = _mod.detect


def test_empty_dir_returns_unknown():
    with tempfile.TemporaryDirectory() as tmpdir:
        result = detect(tmpdir)
        assert result["type"] == "unknown"
        assert result["confidence"] == 0.0


def test_package_json_only_returns_fullstack():
    with tempfile.TemporaryDirectory() as tmpdir:
        open(os.path.join(tmpdir, "package.json"), "w").write('{"name": "app"}')
        result = detect(tmpdir)
        assert result["type"] == "fullstack"
        assert result["confidence"] >= 0.7


def test_next_config_returns_fullstack_high_confidence():
    with tempfile.TemporaryDirectory() as tmpdir:
        open(os.path.join(tmpdir, "package.json"), "w").write('{"name": "app"}')
        open(os.path.join(tmpdir, "next.config.js"), "w").write("module.exports = {};")
        result = detect(tmpdir)
        assert result["type"] == "fullstack"
        assert result["confidence"] >= 0.9


def test_torch_in_requirements_returns_ml_pipeline():
    with tempfile.TemporaryDirectory() as tmpdir:
        open(os.path.join(tmpdir, "requirements.txt"), "w").write("torch==2.0.0\nnumpy\n")
        result = detect(tmpdir)
        assert result["type"] == "ml-pipeline"
        assert result["confidence"] >= 0.85


def test_transformers_in_pyproject_returns_ml_pipeline():
    with tempfile.TemporaryDirectory() as tmpdir:
        open(os.path.join(tmpdir, "pyproject.toml"), "w").write(
            '[project]\nname = "trainer"\ndependencies = ["transformers"]\n'
        )
        result = detect(tmpdir)
        assert result["type"] == "ml-pipeline"


def test_cargo_toml_with_bin_returns_cli():
    with tempfile.TemporaryDirectory() as tmpdir:
        open(os.path.join(tmpdir, "Cargo.toml"), "w").write(
            '[package]\nname = "my-cli"\n\n[[bin]]\nname = "my-cli"\npath = "src/main.rs"\n'
        )
        result = detect(tmpdir)
        assert result["type"] == "cli"
        assert result["confidence"] >= 0.8


def test_cargo_toml_without_bin_returns_library():
    with tempfile.TemporaryDirectory() as tmpdir:
        open(os.path.join(tmpdir, "Cargo.toml"), "w").write(
            '[package]\nname = "mylib"\n\n[lib]\nname = "mylib"\n'
        )
        result = detect(tmpdir)
        assert result["type"] == "library"


def test_pyproject_no_entry_points_returns_library():
    with tempfile.TemporaryDirectory() as tmpdir:
        open(os.path.join(tmpdir, "pyproject.toml"), "w").write(
            '[build-system]\nrequires = ["setuptools"]\n[project]\nname = "mylib"\n'
        )
        result = detect(tmpdir)
        assert result["type"] == "library"


def test_go_mod_with_cmd_dir_returns_cli():
    with tempfile.TemporaryDirectory() as tmpdir:
        open(os.path.join(tmpdir, "go.mod"), "w").write("module example.com/app\n\ngo 1.21\n")
        os.makedirs(os.path.join(tmpdir, "cmd"))
        result = detect(tmpdir)
        assert result["type"] == "cli"
