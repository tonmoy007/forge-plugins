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


# ---------------------------------------------------------------------------
# T-023: ML detection enhancements
# ---------------------------------------------------------------------------

def test_train_py_and_torch_returns_ml_pipeline():
    # done-when criterion: train.py + torch in requirements.txt → ml-pipeline
    with tempfile.TemporaryDirectory() as tmpdir:
        open(os.path.join(tmpdir, "train.py"), "w").write("import torch\n")
        open(os.path.join(tmpdir, "requirements.txt"), "w").write("torch==2.1.0\nnumpy\n")
        result = detect(tmpdir)
        assert result["type"] == "ml-pipeline"
        assert result["confidence"] >= 0.9


def test_train_py_and_torch_high_confidence():
    with tempfile.TemporaryDirectory() as tmpdir:
        open(os.path.join(tmpdir, "train.py"), "w").write("# training script\n")
        open(os.path.join(tmpdir, "requirements.txt"), "w").write("torch>=2.0\n")
        result = detect(tmpdir)
        assert result["confidence"] == 0.95


def test_train_py_alone_returns_ml_pipeline():
    with tempfile.TemporaryDirectory() as tmpdir:
        open(os.path.join(tmpdir, "train.py"), "w").write("# training\n")
        result = detect(tmpdir)
        assert result["type"] == "ml-pipeline"
        assert result["confidence"] >= 0.75


def test_jupyter_notebook_returns_ml_pipeline():
    with tempfile.TemporaryDirectory() as tmpdir:
        open(os.path.join(tmpdir, "analysis.ipynb"), "w").write("{}")
        result = detect(tmpdir)
        assert result["type"] == "ml-pipeline"


def test_sklearn_in_requirements_returns_ml_pipeline():
    with tempfile.TemporaryDirectory() as tmpdir:
        open(os.path.join(tmpdir, "requirements.txt"), "w").write("scikit-learn>=1.0\npandas\n")
        result = detect(tmpdir)
        assert result["type"] == "ml-pipeline"


def test_train_py_indicator_in_result():
    with tempfile.TemporaryDirectory() as tmpdir:
        open(os.path.join(tmpdir, "train.py"), "w").write("")
        open(os.path.join(tmpdir, "requirements.txt"), "w").write("torch\n")
        result = detect(tmpdir)
        combined = " ".join(result["indicators"]).lower()
        assert "train.py" in combined


# ---------------------------------------------------------------------------
# T-023: API type detection
# ---------------------------------------------------------------------------

def test_fastapi_in_requirements_returns_api():
    with tempfile.TemporaryDirectory() as tmpdir:
        open(os.path.join(tmpdir, "requirements.txt"), "w").write("fastapi\nuvicorn\n")
        result = detect(tmpdir)
        assert result["type"] == "api"
        assert result["confidence"] >= 0.85


def test_flask_in_requirements_returns_api():
    with tempfile.TemporaryDirectory() as tmpdir:
        open(os.path.join(tmpdir, "requirements.txt"), "w").write("flask>=2.0\n")
        result = detect(tmpdir)
        assert result["type"] == "api"


def test_django_in_requirements_returns_api():
    with tempfile.TemporaryDirectory() as tmpdir:
        open(os.path.join(tmpdir, "requirements.txt"), "w").write("django>=4.0\n")
        result = detect(tmpdir)
        assert result["type"] == "api"


def test_routes_dir_with_app_py_returns_api():
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "routes"))
        open(os.path.join(tmpdir, "app.py"), "w").write("from flask import Flask\n")
        result = detect(tmpdir)
        assert result["type"] == "api"
