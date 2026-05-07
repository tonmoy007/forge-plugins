#!/usr/bin/env python3
"""Detects project type from file presence. Outputs JSON to stdout.

Basic detection only — full implementation is T-023.
"""
import argparse
import json
import os
import sys


def _read(path: str) -> str:
    try:
        with open(path) as f:
            return f.read().lower()
    except OSError:
        return ""


def detect(cwd: str) -> dict:
    files = set(os.listdir(cwd))
    indicators: list[str] = []

    # ml-pipeline: requirements.txt or pyproject.toml mentions ML libraries
    for req_file in ("requirements.txt", "pyproject.toml"):
        if req_file in files:
            content = _read(os.path.join(cwd, req_file))
            if any(lib in content for lib in ("torch", "transformers", "tensorflow")):
                indicators.append(f"{req_file} references an ML library")
                return {"type": "ml-pipeline", "confidence": 0.9, "indicators": indicators}

    # fullstack (high confidence): package.json + next.config.*
    next_configs = [f for f in files if f.startswith("next.config")]
    if "package.json" in files and next_configs:
        indicators.append("package.json present")
        indicators.append(f"{next_configs[0]} present (Next.js)")
        return {"type": "fullstack", "confidence": 0.95, "indicators": indicators}

    # cli or library: Cargo.toml
    if "Cargo.toml" in files:
        indicators.append("Cargo.toml present")
        content = _read(os.path.join(cwd, "Cargo.toml"))
        if "[[bin]]" in content:
            indicators.append("[[bin]] target declared")
            return {"type": "cli", "confidence": 0.85, "indicators": indicators}
        indicators.append("no [[bin]] target — library crate")
        return {"type": "library", "confidence": 0.75, "indicators": indicators}

    # cli: go.mod with cmd/ pattern
    if "go.mod" in files:
        indicators.append("go.mod present")
        has_cmd = os.path.isdir(os.path.join(cwd, "cmd"))
        if has_cmd:
            indicators.append("cmd/ directory present")
            return {"type": "cli", "confidence": 0.85, "indicators": indicators}
        return {"type": "fullstack", "confidence": 0.6, "indicators": indicators}

    # library: pyproject.toml or setup.py without ML libs and without entry points
    if "setup.py" in files or "pyproject.toml" in files:
        indicators.append("Python package config present")
        content = _read(os.path.join(cwd, "pyproject.toml")) or _read(os.path.join(cwd, "setup.py"))
        has_entry = any(k in content for k in ("scripts", "entry_points", "console_scripts"))
        if not has_entry:
            indicators.append("no entry points defined")
            return {"type": "library", "confidence": 0.75, "indicators": indicators}

    # fullstack (low confidence): package.json only
    if "package.json" in files:
        indicators.append("package.json present (no Next.js config)")
        return {"type": "fullstack", "confidence": 0.7, "indicators": indicators}

    return {"type": "unknown", "confidence": 0.0, "indicators": ["no recognizable project files found"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect Forge project type")
    parser.add_argument("--cwd", default=".", help="Directory to inspect (default: .)")
    args = parser.parse_args()

    cwd = os.path.abspath(args.cwd)
    if not os.path.isdir(cwd):
        print(json.dumps({"error": f"directory not found: {cwd}"}))
        sys.exit(1)

    print(json.dumps(detect(cwd)))


if __name__ == "__main__":
    main()
