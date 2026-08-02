#!/usr/bin/env python3
"""Gate G7-DC-001: schema hygiene + compatibility policy (data-contract profile).

IMPORTANT — this is *hygiene + policy*, NOT a semantic cross-version diff. True
backward-compatibility checking needs the PRIOR version of each schema to diff
against, which a stdlib gate running on a single checkout cannot fetch. What this
gate enforces deterministically on the schemas as they stand:

  - Protobuf: within any `message` (or `enum`) scope, no DUPLICATE field numbers
    — the single most common wire-incompatible mistake. (Numbering *gaps* are NOT
    flagged; gaps are normal and only a warning at best.)
  - buf: if a `buf.yaml` is present, it must declare a `breaking:` change policy,
    so CI actually runs buf's real cross-version breaking-change detection.

Exit 0 when schemas are clean (or there are none to check); exit 1 listing the
issues found. Robust to malformed/unreadable files (skipped). Stdlib only.

Ref: T-133 / REQ-PROFILE-DATACONTRACT-001
"""

from __future__ import annotations

import argparse
import os
import re
import sys

_IGNORE_DIRS = frozenset({
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "env",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".forge", "pipeline",
    "build", "dist", ".idea", ".vscode",
})

# A protobuf field line: optional label, a type (incl. map<...>), a name,
# `= <number>`, optional `[options]`, then `;`.
_FIELD_RE = re.compile(
    r"^\s*(?:(?:repeated|optional|required)\s+)?"
    r"[A-Za-z_][\w.]*(?:\s*<[^>]*>)?\s+"
    r"[A-Za-z_]\w*\s*=\s*(\d+)\s*(?:\[[^\]]*\])?\s*;"
)
# An enum value: `NAME = <number>;`
_ENUM_RE = re.compile(r"^\s*[A-Za-z_]\w*\s*=\s*(\d+)\s*(?:\[[^\]]*\])?\s*;")
_OPEN_RE = re.compile(r"\b(message|enum|oneof|service)\s+(\w+)")


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except OSError:
        return ""


def _walk(cwd: str, suffix: str) -> list[str]:
    found: list[str] = []
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]
        found.extend(os.path.join(root, f) for f in files if f.endswith(suffix))
    return found


def _proto_issues(text: str, label: str) -> list[str]:
    """Return duplicate-field-number issues for one .proto file's text."""
    issues: list[str] = []
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)  # strip block comments
    # stack frames: [kind, name, {seen numbers}]
    stack: list[list] = []

    for raw in text.splitlines():
        line = raw.split("//", 1)[0]  # strip line comment
        stripped = line.strip()
        if not stripped:
            continue

        opened = False
        m = _OPEN_RE.match(stripped)
        if m and "{" in line:
            stack.append([m.group(1), m.group(2), set()])
            opened = True

        if not opened:
            # Field numbers count toward the nearest enclosing message/enum
            # (a `oneof`'s fields belong to its parent message's number space).
            target = next(
                (fr for fr in reversed(stack) if fr[0] in ("message", "enum")),
                None,
            )
            if target is not None:
                mm = (_ENUM_RE if target[0] == "enum" else _FIELD_RE).match(stripped)
                if mm:
                    num = int(mm.group(1))
                    if num in target[2]:
                        issues.append(
                            f"{label}: duplicate field number {num} in "
                            f"{target[0]} {target[1]}"
                        )
                    else:
                        target[2].add(num)

        for _ in range(line.count("}")):
            if stack:
                stack.pop()

    return issues


def check(cwd: str) -> list[str]:
    issues: list[str] = []

    for proto in _walk(cwd, ".proto"):
        issues.extend(_proto_issues(_read(proto), os.path.relpath(proto, cwd)))

    buf = os.path.join(cwd, "buf.yaml")
    if os.path.isfile(buf) and "breaking:" not in _read(buf):
        issues.append(
            "buf.yaml present but declares no `breaking:` change policy — add one "
            "so CI runs buf's cross-version breaking-change detection"
        )

    return issues


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", default=".", help="project root to inspect (default: .)")
    args = parser.parse_args(argv)

    issues = check(os.path.abspath(args.cwd))
    if issues:
        print("G7-DC-001 FAIL: schema hygiene/policy issues:")
        for item in issues:
            print(f"  - {item}")
        return 1

    print("G7-DC-001 PASS: schema hygiene clean (no duplicate field numbers; "
          "buf breaking policy present if buf.yaml used).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
