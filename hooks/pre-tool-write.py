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
# v0.1.5.1: fail soft when PyYAML is missing — a hook must never crash-spam the
# session with an import traceback (_state_lib and others require PyYAML).
try:
    import yaml  # noqa: F401
except ImportError:
    print(
        "[Forge] PyYAML is not installed — Forge hooks are inactive. "
        "Fix: pip install pyyaml (then run /forge:doctor).",
        file=sys.stderr,
    )
    raise SystemExit(0)

sys.path.insert(0, str(_PLUGIN_DIR / "scripts"))
sys.path.insert(0, str(_PLUGIN_DIR / "hooks"))
import _state_lib as lib
import _state_read
import rules as user_rules  # user-authored rules surface — REQ-RULES-010
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


def _enforcing_block_message(cwd: Path, file_path: str) -> str:
    """Return a denial message when an enforcing `glob` rule matches the write
    (REQ-AUTO-006) — the governance guardrail that makes unattended autonomy safe.

    Fail-soft: '' when no enforcing rule matches, there is no `.forge/rules/`, or anything
    goes wrong. A bug in rule handling must NEVER wrongly block legitimate work, so any
    exception degrades to "allow" (advisory behavior).
    """
    if not file_path:
        return ""
    try:
        matched = user_rules.enforcing_for_file(
            user_rules.load_rules(cwd / ".forge"), file_path
        )
        if not matched:
            return ""
        names = ", ".join(f"{r.name} ({r.severity})" for r in matched)
        details = "\n".join(
            f"  • {r.name}: {r.description or (r.body.splitlines()[0] if r.body else r.scope)}"
            for r in matched
        )
        return (
            f"[Forge] BLOCKED write to {Path(file_path).name} by enforcing rule(s): {names}.\n"
            f"{details}\n"
            "This path is governed by an enforcing rule. Change the target, or relax the "
            "rule in .forge/rules/ to advisory (remove `enforce: true`)."
        )
    except Exception:  # noqa: BLE001 — enforcement must fail-soft, never wrongly block on a bug
        return ""


def _glob_rules_message(cwd: Path, file_path: str) -> str:
    """Render user `glob` rules matching the written file (REQ-RULES-010).

    Advisory only — surfaced as additionalContext, NEVER blocks the write. Read-only,
    applies to any file type, and never raises; '' when there is no match or no
    `.forge/rules/` directory.
    """
    if not file_path:
        return ""
    try:
        selected = user_rules.select(
            user_rules.load_rules(cwd / ".forge"), file_path=file_path, scope="glob"
        )
        body = user_rules.render(selected, max_chars=600)
        if not body:
            return ""
        return f"[Forge] Rules for {Path(file_path).name}:\n{body}"
    except Exception:  # noqa: BLE001 — rule injection must never block a write
        return ""


def _design_violations_message(
    cwd: Path, tool_name: str, tool_input: dict, file_path: str, session_id: str
) -> str:
    """Design-system feedback for UI writes after Stage 6 (existing behavior).

    Returns '' when not applicable. Prints a state-read warning if one occurs
    (REQ-SILENTSTATE-001).
    """
    if not _is_ui_file(file_path):
        return ""
    if not (cwd / "pipeline" / "state.md").exists():
        return ""
    state, warning = _state_read.read_state_safe(str(cwd), session_id)
    if warning:
        print(warning)
    if state.get("current_stage", 0) < 6:
        return ""
    design_system = cwd / "pipeline" / "02-product-ux" / "design-system.md"
    if not design_system.exists():
        return ""
    content = _extract_content(tool_name, tool_input)
    if not content:
        return ""
    violations = _scan_violations(content)
    if not violations:
        return ""
    # T-114: record the violation so the repeated-block / heredoc-bypass producers
    # can see a pattern of fighting the design-system check on the same files.
    _state_read.log_event(cwd / ".forge", "pretool_violation", file_path, session_id)
    capped = violations[:10]
    suffix = (
        f"\n  ... and {len(violations) - 10} more violation(s)"
        if len(violations) > 10
        else ""
    )
    return (
        f"[Forge] Design system violations in {Path(file_path).name}:\n"
        + "\n".join(f"  • {v}" for v in capped)
        + suffix
        + "\n\nSee pipeline/02-product-ux/design-system.md for token reference."
    )


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
    cwd = Path(payload.get("cwd", os.getcwd()))
    session_id = payload.get("session_id", "")

    # (0) Enforcing rules — a matching enforcing `glob` rule BLOCKS the write (exit 2).
    # pre-tool-write is a registered blocking hook, so this exit propagates (T-100).
    denial = _enforcing_block_message(cwd, file_path)
    if denial:
        print(denial, file=sys.stderr)
        sys.exit(2)

    blocks: list[str] = []
    # (1) User glob rules — any file type, independent of stage/design-system.
    rule_block = _glob_rules_message(cwd, file_path)
    if rule_block:
        blocks.append(rule_block)
    # (2) Design-system enforcement — UI files after Stage 6 (existing behavior).
    ds_block = _design_violations_message(cwd, tool_name, tool_input, file_path, session_id)
    if ds_block:
        blocks.append(ds_block)

    if not blocks:
        sys.exit(0)
    print(json.dumps({"hookSpecificOutput": {"additionalContext": "\n\n".join(blocks)}}))
    sys.exit(0)


if __name__ == "__main__":
    run_hook(main, hook_name="pre-tool-write")
