#!/usr/bin/env python3
"""PreToolUse hook: enforce design system in UI file writes.

Fires on Write/Edit/MultiEdit tool calls to UI files. Scans content for raw
design values and injects feedback as additionalContext if violations are found.
Only active after Stage 6 and when pipeline/02-product-ux/design-system.md exists.
Never blocks writes (always exits 0).
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

_PLUGIN_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(_PLUGIN_DIR / "scripts"))
sys.path.insert(0, str(_PLUGIN_DIR / "hooks"))
import _state_lib as lib
import _state_read
from _hook_runner import run_hook

_UI_EXTENSIONS = {".tsx", ".jsx", ".ts", ".js", ".vue", ".svelte", ".css", ".scss", ".html"}

# px values allowed without a token (Tailwind-compatible spacing scale)
_SPACING_SCALE = {0, 1, 2, 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96, 128}

_HEX_COLOR_RE = re.compile(r"#([0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
_RAW_PX_RE = re.compile(r"\b(\d+)px\b")
_FONT_FAMILY_RE = re.compile(r"font-family\s*:")
_Z_INDEX_RE = re.compile(r"z-index\s*:")
_IMPORTANT_RE = re.compile(r"!important")


def _is_ui_file(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in _UI_EXTENSIONS


def _extract_content(tool_name: str, tool_input: dict) -> str:
    """Get the text being written from Write, Edit, or MultiEdit input."""
    if "content" in tool_input:
        return tool_input["content"]
    if "new_string" in tool_input:
        return tool_input["new_string"]
    # MultiEdit: list of {old_string, new_string}
    edits = tool_input.get("edits", [])
    if isinstance(edits, list):
        return "\n".join(
            e.get("new_string", "") for e in edits if isinstance(e, dict)
        )
    return ""


def _is_comment_line(line: str) -> bool:
    s = line.strip()
    return s.startswith("//") or s.startswith("*") or s.startswith("/*")


def _scan_violations(content: str) -> list[str]:
    violations: list[str] = []
    for i, line in enumerate(content.splitlines(), 1):
        if _is_comment_line(line):
            continue

        # Hex colors not wrapped in var(--color-*)
        if _HEX_COLOR_RE.search(line) and "var(--color" not in line:
            for m in list(_HEX_COLOR_RE.finditer(line))[:2]:
                violations.append(
                    f"Line {i}: raw hex `#{m.group(1)}` — use `var(--color-*)`"
                )

        # Raw px values outside spacing scale
        for m in _RAW_PX_RE.finditer(line):
            val = int(m.group(1))
            if val not in _SPACING_SCALE:
                violations.append(
                    f"Line {i}: `{val}px` not on spacing scale"
                    " — use a design token or scale value"
                )

        # font-family not using a CSS variable
        if _FONT_FAMILY_RE.search(line) and "var(--font" not in line:
            violations.append(f"Line {i}: `font-family` raw value — use `var(--font-*)`")

        # z-index not using a CSS variable
        if _Z_INDEX_RE.search(line) and "var(--z" not in line:
            violations.append(f"Line {i}: `z-index` raw value — use `var(--z-*)`")

        # !important usage
        if _IMPORTANT_RE.search(line):
            violations.append(f"Line {i}: `!important` — avoid; prefer specificity")

    return violations


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}

    tool_name = payload.get("tool_name", "")
    if tool_name not in {"Write", "Edit", "MultiEdit"}:
        sys.exit(0)

    tool_input_raw = payload.get("tool_input", {})
    tool_input: dict = tool_input_raw if isinstance(tool_input_raw, dict) else {}
    file_path = tool_input.get("file_path", "")

    if not _is_ui_file(file_path):
        sys.exit(0)

    cwd = Path(payload.get("cwd", os.getcwd()))

    # Only enforce after Stage 6
    if not (cwd / "pipeline" / "state.md").exists():
        sys.exit(0)
    state, warning = _state_read.read_state_safe(str(cwd), payload.get("session_id", ""))
    if warning:
        print(warning)
    if state.get("current_stage", 0) < 6:
        sys.exit(0)

    # Only enforce when a design system has been authored
    design_system = cwd / "pipeline" / "02-product-ux" / "design-system.md"
    if not design_system.exists():
        sys.exit(0)

    content = _extract_content(tool_name, tool_input)
    if not content:
        sys.exit(0)

    violations = _scan_violations(content)
    if not violations:
        sys.exit(0)

    capped = violations[:10]
    suffix = (
        f"\n  ... and {len(violations) - 10} more violation(s)"
        if len(violations) > 10
        else ""
    )
    msg = (
        f"[Forge] Design system violations in {Path(file_path).name}:\n"
        + "\n".join(f"  • {v}" for v in capped)
        + suffix
        + "\n\nSee pipeline/02-product-ux/design-system.md for token reference."
    )
    print(json.dumps({"hookSpecificOutput": {"additionalContext": msg}}))
    sys.exit(0)


if __name__ == "__main__":
    run_hook(main, hook_name="pre-tool-write")
