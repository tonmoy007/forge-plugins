#!/usr/bin/env python3
"""Detect Forge project type from file structure. Outputs JSON to stdout.

Detects: ml-pipeline, fullstack, api, cli, library, unknown.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_ML_LIBS = ("torch", "transformers", "tensorflow", "sklearn", "scikit-learn", "keras", "jax", "xgboost", "lightgbm")
_API_LIBS = ("fastapi", "flask", "django", "falcon", "aiohttp", "express", "koa", "hapi", "fastify")


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read().lower()
    except OSError:
        return ""


def _has_dir(cwd: str, name: str) -> bool:
    return os.path.isdir(os.path.join(cwd, name))


def _req_content(cwd: str, files: set) -> str:
    """Return lowercased content of the first requirements file found."""
    for fname in ("requirements.txt", "pyproject.toml", "setup.py", "package.json"):
        if fname in files:
            content = _read(os.path.join(cwd, fname))
            if content:
                return content
    return ""


def detect(cwd: str) -> dict:
    try:
        files = set(os.listdir(cwd))
    except OSError:
        return {"type": "unknown", "confidence": 0.0, "indicators": ["cannot read directory"]}

    indicators: list[str] = []

    # ------------------------------------------------------------------ ML
    # Signals: ML library in requirements, train.py, *.ipynb, models/
    ml_lib: str = ""
    for req_file in ("requirements.txt", "pyproject.toml", "setup.py"):
        if req_file in files:
            content = _read(os.path.join(cwd, req_file))
            for lib in _ML_LIBS:
                if lib in content:
                    ml_lib = lib
                    indicators.append(f"{req_file} contains {lib}")
                    break
        if ml_lib:
            break

    has_train_py = "train.py" in files
    has_notebooks = any(f.endswith(".ipynb") for f in files)
    has_models_dir = _has_dir(cwd, "models")

    if has_train_py:
        indicators.append("train.py present")
    if has_notebooks:
        count = sum(1 for f in files if f.endswith(".ipynb"))
        indicators.append(f"{count} Jupyter notebook(s) present")
    if has_models_dir:
        indicators.append("models/ directory present")

    ml_signal_count = sum([bool(ml_lib), has_train_py, has_notebooks])
    if ml_signal_count >= 1:
        if ml_signal_count >= 2:
            confidence = 0.95
        elif ml_lib:
            confidence = 0.90
        else:
            confidence = 0.80  # train.py or notebooks alone
        return {"type": "ml-pipeline", "confidence": confidence, "indicators": list(indicators)}

    # Reset indicators for subsequent checks
    indicators = []

    # -------------------------------------------------------------- Fullstack
    next_configs = [f for f in files if f.startswith("next.config")]
    if "package.json" in files and next_configs:
        indicators.append("package.json present")
        indicators.append(f"{next_configs[0]} present (Next.js)")
        return {"type": "fullstack", "confidence": 0.95, "indicators": indicators}

    # -------------------------------------------------------------------  API
    # Signals: API framework in requirements/package.json, routes/ or api/ dir
    api_lib: str = ""
    for req_file in ("requirements.txt", "pyproject.toml", "package.json"):
        if req_file in files:
            content = _read(os.path.join(cwd, req_file))
            for lib in _API_LIBS:
                if lib in content:
                    api_lib = lib
                    indicators.append(f"{req_file} contains {lib}")
                    break
        if api_lib:
            break

    has_routes = _has_dir(cwd, "routes") or _has_dir(cwd, "routers") or _has_dir(cwd, "api")
    if has_routes:
        indicators.append("routes/ or api/ directory present")

    if api_lib or (has_routes and "app.py" in files):
        confidence = 0.90 if api_lib else 0.80
        return {"type": "api", "confidence": confidence, "indicators": indicators}

    indicators = []

    # ------------------------------------------------------------------- CLI
    # Rust: Cargo.toml with [[bin]]
    if "Cargo.toml" in files:
        indicators.append("Cargo.toml present")
        content = _read(os.path.join(cwd, "Cargo.toml"))
        if "[[bin]]" in content:
            indicators.append("[[bin]] target declared")
            return {"type": "cli", "confidence": 0.85, "indicators": indicators}
        indicators.append("no [[bin]] target — library crate")
        return {"type": "library", "confidence": 0.75, "indicators": indicators}

    # Go: go.mod + cmd/
    if "go.mod" in files:
        indicators.append("go.mod present")
        if _has_dir(cwd, "cmd"):
            indicators.append("cmd/ directory present")
            return {"type": "cli", "confidence": 0.85, "indicators": indicators}
        return {"type": "api", "confidence": 0.60, "indicators": indicators}

    # -------------------------------------------------------------- Library
    if "setup.py" in files or "pyproject.toml" in files:
        indicators.append("Python package config present")
        content = _read(os.path.join(cwd, "pyproject.toml")) or _read(os.path.join(cwd, "setup.py"))
        has_entry = any(k in content for k in ("scripts", "entry_points", "console_scripts"))
        if not has_entry:
            indicators.append("no entry points defined")
            return {"type": "library", "confidence": 0.75, "indicators": indicators}

    # --------------------------------------------------------- Fullstack (low)
    if "package.json" in files:
        indicators.append("package.json present (no Next.js config)")
        return {"type": "fullstack", "confidence": 0.70, "indicators": indicators}

    return {
        "type": "unknown",
        "confidence": 0.0,
        "indicators": ["no recognizable project files found"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", default=".", help="directory to inspect (default: .)")
    args = parser.parse_args()

    cwd = os.path.abspath(args.cwd)
    if not os.path.isdir(cwd):
        print(json.dumps({"error": f"directory not found: {cwd}"}))
        sys.exit(1)

    print(json.dumps(detect(cwd)))


if __name__ == "__main__":
    main()
