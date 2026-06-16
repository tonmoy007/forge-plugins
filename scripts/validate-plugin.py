#!/usr/bin/env python3
"""Validates .claude-plugin/plugin.json against the Forge plugin schema."""

import json
import os
import sys
from pathlib import Path

KNOWN_HOOK_EVENTS = {
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "Stop",
    "SubagentStop",
    "SessionEnd",
    "PreCompact",
}

# Per the official Claude Code plugin manifest schema
# (https://json.schemastore.org/claude-code-plugin-manifest.json) `name` is the
# ONLY schema-required field. There is no `claude_code_version`/`engines`
# manifest field — a minimum Claude Code version cannot be expressed in the
# manifest at all; it is enforced at runtime by scripts/doctor.py instead.
# Forge additionally requires `version` as a release-discipline rule: every
# release must pin an explicit semver for traceability (stricter than the
# schema, intentionally).
REQUIRED_FIELDS = ["name", "version"]


def validate(plugin_path: Path) -> bool:
    try:
        with open(plugin_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {plugin_path}: {e}", file=sys.stderr)
        return False
    except FileNotFoundError:
        print(f"ERROR: {plugin_path} not found", file=sys.stderr)
        return False

    ok = True

    for field in REQUIRED_FIELDS:
        if field not in data:
            print(f"ERROR: Missing required field: {field}", file=sys.stderr)
            ok = False

    hooks = data.get("hooks", {})
    for event_name in hooks:
        if event_name not in KNOWN_HOOK_EVENTS:
            print(f"ERROR: Unknown hook event: {event_name}", file=sys.stderr)
            ok = False

    plugin_dir = plugin_path.parent.parent
    for event_name, matchers in hooks.items():
        for matcher_block in matchers:
            for hook in matcher_block.get("hooks", []):
                cmd = hook.get("command", "")
                # Extract script path from command (strip env var prefix)
                parts = cmd.replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_dir)).split()
                for part in parts:
                    if part.endswith(".py"):
                        script_path = Path(part)
                        if not script_path.exists():
                            print(f"WARN: Hook script not found: {part} (expected — will be created in T-007+)")

    if ok:
        print(f"OK: {plugin_path} is valid")
    return ok


def main() -> None:
    repo_root = Path(__file__).parent.parent
    plugin_path = repo_root / ".claude-plugin" / "plugin.json"
    success = validate(plugin_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
