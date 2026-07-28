#!/usr/bin/env python3
"""Gate G7-MONO-001: internal package dependency graph is acyclic.

Discovers internal workspace packages by reading every `package.json` under
`packages/` and `apps/` and collecting their `"name"` values as the internal
set. Builds a directed graph where package A -> B when B's name appears in A's
`dependencies` or `devDependencies`, then DFS-checks for a cycle.

Exit 0 when the graph is acyclic (or there is no workspace / no packages).
Exit 1 when a cycle is found, naming the cycle. Robust to missing/garbled JSON.

Ref: T-131 / REQ-PROFILE-MONOREPO-001
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_WORKSPACE_DIRS = ("packages", "apps")
_DEP_KEYS = ("dependencies", "devDependencies")


def _iter_package_jsons(cwd: str) -> list[str]:
    """Return paths to every package.json under packages/ and apps/."""
    found: list[str] = []
    for group in _WORKSPACE_DIRS:
        base = os.path.join(cwd, group)
        if not os.path.isdir(base):
            continue
        for root, _dirs, files in os.walk(base):
            if "package.json" in files:
                found.append(os.path.join(root, "package.json"))
    return found


def _load_json(path: str) -> dict | None:
    """Load a JSON object, returning None on any read/parse error."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _build_graph(cwd: str) -> dict[str, set[str]]:
    """Build the internal package dependency graph (name -> set of internal deps)."""
    manifests: dict[str, dict] = {}
    for path in _iter_package_jsons(cwd):
        data = _load_json(path)
        if data is None:
            continue
        name = data.get("name")
        if isinstance(name, str) and name:
            manifests[name] = data

    internal = set(manifests)
    graph: dict[str, set[str]] = {name: set() for name in internal}
    for name, data in manifests.items():
        for key in _DEP_KEYS:
            deps = data.get(key)
            if not isinstance(deps, dict):
                continue
            for dep_name in deps:
                if dep_name in internal and dep_name != name:
                    graph[name].add(dep_name)
    return graph


def _find_cycle(graph: dict[str, set[str]]) -> list[str] | None:
    """Return a cycle as an ordered list of nodes, or None if the graph is acyclic."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {node: WHITE for node in graph}

    def dfs(node: str, stack: list[str]) -> list[str] | None:
        color[node] = GRAY
        stack.append(node)
        for nxt in sorted(graph[node]):
            if color[nxt] == GRAY:
                # Found a back-edge; slice the stack from the start of the cycle.
                idx = stack.index(nxt)
                return stack[idx:] + [nxt]
            if color[nxt] == WHITE:
                cycle = dfs(nxt, stack)
                if cycle is not None:
                    return cycle
        stack.pop()
        color[node] = BLACK
        return None

    for node in sorted(graph):
        if color[node] == WHITE:
            cycle = dfs(node, [])
            if cycle is not None:
                return cycle
    return None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", default=".", help="workspace root to inspect (default: .)")
    args = parser.parse_args(argv)

    cwd = os.path.abspath(args.cwd)
    graph = _build_graph(cwd)
    if not graph:
        # No workspace / no internal packages — nothing to validate.
        return 0

    cycle = _find_cycle(graph)
    if cycle is not None:
        print("G7-MONO-001 FAIL: circular internal dependency detected:")
        print("  " + " -> ".join(cycle))
        return 1

    print(f"G7-MONO-001 PASS: {len(graph)} internal package(s), dependency graph acyclic.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
