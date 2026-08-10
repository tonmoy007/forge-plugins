#!/usr/bin/env python3
"""Advisory Docker hygiene check (T-228, REQ-DK-001).

Mirrors check_store_readiness.py's no-op-when-absent template, but this one is
**purely advisory**: it exits 0 whether or not it finds Docker artifacts, and
exits 0 even when it reports findings. Findings are printed as `WARN:` lines —
never a blocking gate.

Checks, per Dockerfile found:
  - base image pinned (no `:latest`, no untagged `FROM`; a digest pin or a
    reference to an earlier build stage both count as pinned)
  - `HEALTHCHECK` present
  - the last `USER` directive is not root (`root` or `0`); no `USER` at all
    also flags (the image runs as root by default)
Project-level:
  - `.dockerignore` exists when any Docker artifact is present
  - each compose file parses and has a top-level `services:` key

Robust to unreadable files (skipped, not fatal) and to PyYAML being absent
(compose parse check degrades to skipped, not a crash).

Ref: T-228 / REQ-DK-001
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field

try:
    import yaml
except ImportError:  # fail-soft — compose parse check degrades to skipped
    yaml = None

_IGNORE_DIRS = frozenset({
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".forge", "pipeline",
    "build", "dist",
})
_COMPOSE_NAMES = frozenset({"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"})

_FROM_RE = re.compile(r"(?im)^\s*FROM\s+(?:--platform=\S+\s+)?(\S+)")
_STAGE_NAME_RE = re.compile(r"(?im)\bAS\s+(\S+)\s*$")
_HEALTHCHECK_RE = re.compile(r"(?im)^\s*HEALTHCHECK\b")
_USER_RE = re.compile(r"(?im)^\s*USER\s+(\S+)")


@dataclass
class DockerFindings:
    has_artifacts: bool
    warnings: list = field(default_factory=list)


def _read(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except OSError:
        return None


def _walk_files(cwd: str, matches) -> list:
    found = []
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]
        for name in files:
            if matches(name):
                found.append(os.path.join(root, name))
    return found


def _check_dockerfile(path: str, warnings: list) -> None:
    text = _read(path)
    if text is None:
        return  # unreadable — skip, don't crash

    stage_names = {m.group(1) for m in _STAGE_NAME_RE.finditer(text)}
    for image in _FROM_RE.findall(text):
        base = image.split("@")[0]
        if "@sha256:" in image:
            continue  # digest-pinned
        if base in stage_names:
            continue  # refers to an earlier build stage, not a registry image
        if ":" not in base or base.rsplit(":", 1)[1] == "latest":
            warnings.append(f"{path}: base image not pinned ({image!r}) — pin to a specific tag or digest")

    if not _HEALTHCHECK_RE.search(text):
        warnings.append(f"{path}: no HEALTHCHECK instruction")

    users = _USER_RE.findall(text)
    last_user = users[-1] if users else None
    if last_user is None:
        warnings.append(f"{path}: no USER directive — image runs as root by default")
    elif last_user in ("root", "0"):
        warnings.append(f"{path}: USER is {last_user!r} — runs as root")


def _check_compose(path: str, warnings: list) -> None:
    text = _read(path)
    if text is None:
        return
    if yaml is None:
        return  # fail-soft — cannot verify without PyYAML, not a crash
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        warnings.append(f"{path}: does not parse as valid YAML")
        return
    if not isinstance(data, dict) or "services" not in data:
        warnings.append(f"{path}: missing top-level 'services:' key")


def check_docker_readiness(cwd) -> DockerFindings:
    cwd = str(cwd)
    dockerfiles = _walk_files(cwd, lambda n: n == "Dockerfile" or n.startswith("Dockerfile."))
    compose_files = _walk_files(cwd, lambda n: n in _COMPOSE_NAMES)
    has_artifacts = bool(dockerfiles or compose_files)
    if not has_artifacts:
        return DockerFindings(has_artifacts=False, warnings=[])

    warnings: list = []
    for path in dockerfiles:
        _check_dockerfile(path, warnings)
    for path in compose_files:
        _check_compose(path, warnings)

    if not os.path.isfile(os.path.join(cwd, ".dockerignore")):
        warnings.append(".dockerignore not found at project root")

    return DockerFindings(has_artifacts=True, warnings=warnings)


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", default=".", help="project root to inspect (default: .)")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    findings = check_docker_readiness(args.cwd)

    if not findings.has_artifacts:
        print("check_docker_readiness: no Docker artifacts found — nothing to check.")
        return 0

    if not findings.warnings:
        print("check_docker_readiness PASS: no hygiene findings.")
        return 0

    print("check_docker_readiness: advisory findings (never blocking):")
    for w in findings.warnings:
        print(f"  WARN: {w}")
    return 0  # always 0 — this check can never block a stage


if __name__ == "__main__":
    sys.exit(main())
