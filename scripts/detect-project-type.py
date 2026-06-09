#!/usr/bin/env python3
"""Detect Forge project type from file structure. Outputs JSON to stdout.

Detects: ml-pipeline, fullstack, api, cli, library, unknown.

For small repos that don't match any of those (< 500 LOC, no package manifest),
also emits a `suggested_profile: "script"` hint so /forge:init can prompt the
user to opt into the streamlined `script` profile. The `script` profile is
NEVER auto-assigned; the suggestion is informational.

Ref: T-107
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_ML_LIBS = ("torch", "transformers", "tensorflow", "sklearn", "scikit-learn", "keras", "jax", "xgboost", "lightgbm")
_API_LIBS = ("fastapi", "flask", "django", "falcon", "aiohttp", "express", "koa", "hapi", "fastify")

# ---------- T-107 additions ----------

# Package manifests that disqualify a project from the `script` profile.
# A project with any of these is "something a person decided to package" —
# even if it's small, it shouldn't get the script profile suggested.
_PACKAGE_MANIFESTS = (
    "package.json", "setup.py", "pyproject.toml", "Cargo.toml",
    "go.mod", "Gemfile", "composer.json",
)

# Languages we consider "scriptable" — interpreted, single-file-friendly.
_SCRIPT_EXTENSIONS = frozenset({
    ".py", ".sh", ".bash", ".zsh", ".fish", ".js", ".mjs",
})

# Directories to skip when measuring project size.
_IGNORE_DIRS = frozenset({
    ".git", ".hg", ".svn",
    "node_modules", ".venv", "venv", "env",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".forge", "pipeline", "tasks", "build", "dist",
    ".idea", ".vscode",
})

_SCRIPT_LOC_THRESHOLD = 500
_SCRIPT_FILE_COUNT_THRESHOLD = 20
_SCRIPT_CONFIDENCE = 0.85


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


# ---------- T-131: monorepo detection ----------

# Workspace marker files: presence of any one signals a monorepo.
_MONOREPO_MARKERS = ("pnpm-workspace.yaml", "lerna.json", "turbo.json", "nx.json")


def _detect_monorepo(cwd: str, files: set) -> dict | None:
    """Return a monorepo classification if any workspace signal is present, else None.

    Signals (ANY): a workspace marker file (pnpm-workspace.yaml, lerna.json,
    turbo.json, nx.json), a `"workspaces"` field in package.json, a `[workspace]`
    table in Cargo.toml, or BOTH `packages/` and `apps/` directories present.
    """
    indicators: list[str] = []

    for marker in _MONOREPO_MARKERS:
        if marker in files:
            indicators.append(f"{marker} present")

    if "package.json" in files:
        content = _read(os.path.join(cwd, "package.json"))
        if '"workspaces"' in content:
            indicators.append('package.json declares "workspaces"')

    if "Cargo.toml" in files:
        content = _read(os.path.join(cwd, "Cargo.toml"))
        if "[workspace]" in content:
            indicators.append("Cargo.toml declares [workspace]")

    if _has_dir(cwd, "packages") and _has_dir(cwd, "apps"):
        indicators.append("packages/ and apps/ directories present")

    if not indicators:
        return None

    return {"type": "monorepo", "confidence": 0.90, "indicators": indicators}


def detect(cwd: str) -> dict:
    try:
        files = set(os.listdir(cwd))
    except OSError:
        return {"type": "unknown", "confidence": 0.0, "indicators": ["cannot read directory"]}

    indicators: list[str] = []

    # ------------------------------------------------------------- Monorepo
    # Checked FIRST: a monorepo wraps single-package signals (a Next.js app,
    # an API, a library) inside workspaces, so it must win before those
    # branches fire. Detected via ANY workspace manifest or the packages/+apps/
    # convention. Deliberately specific so plain fullstack/api/library projects
    # don't match.
    mono = _detect_monorepo(cwd, files)
    if mono is not None:
        return mono

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


# ---------- T-107: script-profile suggestion ----------

def _walk_source_files(cwd: str):
    """Yield (abs_path, lowercase_ext) for non-hidden files under cwd, skipping ignore dirs."""
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [
            d for d in dirs
            if d not in _IGNORE_DIRS and not d.startswith(".")
        ]
        for f in files:
            if f.startswith("."):
                continue
            ext = os.path.splitext(f)[1].lower()
            yield os.path.join(root, f), ext


def _count_loc(cwd: str, extensions: frozenset) -> int:
    """Count non-blank, non-comment lines across files with given extensions."""
    total = 0
    for path, ext in _walk_source_files(cwd):
        if ext not in extensions:
            continue
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    if stripped.startswith("#") or stripped.startswith("//"):
                        continue
                    total += 1
        except OSError:
            continue
    return total


def _count_files(cwd: str) -> int:
    """Count regular files, excluding ignored dirs and hidden files."""
    return sum(1 for _ in _walk_source_files(cwd))


def _is_language_subset(cwd: str, allowed: frozenset) -> bool:
    """Return True if every source file (with a recognized extension) is in allowed.

    Files without an extension (READMEs, Makefiles, etc.) are not counted against
    the subset. Returns False if no source files at all are found.
    """
    found_any_source = False
    for _path, ext in _walk_source_files(cwd):
        if not ext:
            continue  # extensionless files don't disqualify
        found_any_source = True
        if ext not in allowed:
            return False
    return found_any_source


def _has_package_manifest(files: set) -> bool:
    return any(m in files for m in _PACKAGE_MANIFESTS)


def _detect_script(cwd: str, files: set) -> dict | None:
    """Return script-profile match info if the project looks tiny enough, else None.

    Conservative — only suggests `script` when ALL of:
      - No package manifest (the user hasn't decided to package this)
      - File count < 20 (excluding ignored dirs)
      - All source files are in the script-language subset
      - LOC < 500 (and > 0)
    """
    if _has_package_manifest(files):
        return None
    if _count_files(cwd) >= _SCRIPT_FILE_COUNT_THRESHOLD:
        return None
    if not _is_language_subset(cwd, _SCRIPT_EXTENSIONS):
        return None
    loc = _count_loc(cwd, _SCRIPT_EXTENSIONS)
    if loc == 0 or loc >= _SCRIPT_LOC_THRESHOLD:
        return None
    return {
        "loc": loc,
        "indicators": [
            f"{loc} LOC across script files (< {_SCRIPT_LOC_THRESHOLD})",
            "no package manifest present",
            "language subset: Python / shell / JS only",
        ],
    }


def _finalize(result: dict, cwd: str) -> dict:
    """Post-process detect() output.

    Adds:
      - `project_type` alias (mirrors `type` — matches state.md field name).
      - `suggested_profile: "script"` (and related fields) when nothing else
        matched and the project looks tiny enough.
    """
    result = dict(result)

    # Alias `type` -> `project_type` for downstream consistency with state.md.
    if "type" in result and "project_type" not in result:
        result["project_type"] = result["type"]

    # Only suggest `script` when nothing else matched.
    if result.get("type") == "unknown":
        try:
            files = set(os.listdir(cwd))
        except OSError:
            return result
        script_match = _detect_script(cwd, files)
        if script_match is not None:
            result["suggested_profile"] = "script"
            result["suggested_profile_confidence"] = _SCRIPT_CONFIDENCE
            result["suggested_profile_indicators"] = script_match["indicators"]
            result["suggested_profile_metadata"] = {"loc": script_match["loc"]}

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", default=".", help="directory to inspect (default: .)")
    args = parser.parse_args()

    cwd = os.path.abspath(args.cwd)
    if not os.path.isdir(cwd):
        print(json.dumps({"error": f"directory not found: {cwd}"}))
        sys.exit(1)

    print(json.dumps(_finalize(detect(cwd), cwd)))


if __name__ == "__main__":
    main()