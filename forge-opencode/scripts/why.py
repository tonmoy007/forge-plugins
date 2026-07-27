#!/usr/bin/env python3
"""Explain a gate criterion, lesson tag, stage, or current blockers.

Pure read-only deterministic lookup. No LLM calls; v0.2 may add an LLM
fallback for unknown IDs.

Usage:
    python scripts/why.py G1-001              # explain a gate criterion
    python scripts/why.py force-advance        # show recent lessons with this tag
    python scripts/why.py stage-3              # explain a pipeline stage
    python scripts/why.py 3                    # same, terse form
    python scripts/why.py                      # explain current blocker(s)

    python scripts/why.py G1-001 --json        # structured output

Exit codes:
    0 — target found and explained
    1 — target type recognized but not found (e.g., G99-001 doesn't exist)
    2 — input malformed or environment broken

Ref: T-106
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _state_lib as lib  # noqa: E402

import yaml  # noqa: E402


STAGE_NAMES: dict[int, dict[str, Any]] = {
    1:  {"name": "srs",
         "purpose": "Capture functional and non-functional requirements with REQ-NNN IDs.",
         "artifacts": ["pipeline/01-srs/srs.md", "pipeline/01-srs/stakeholder-map.md"]},
    2:  {"name": "product / UX",
         "purpose": "Translate requirements into design — wireframes, design tokens, component specs.",
         "artifacts": ["pipeline/02-product-ux/design-system.md",
                       "pipeline/02-product-ux/wireframes/"]},
    3:  {"name": "architecture",
         "purpose": "Define system structure, components, data flows, ADRs.",
         "artifacts": ["pipeline/03-architecture/architecture.md",
                       "pipeline/03-architecture/adr/"]},
    4:  {"name": "spec",
         "purpose": "Technical specifications per component, traceable to REQ-IDs.",
         "artifacts": ["pipeline/04-spec/*.md"]},
    5:  {"name": "plan",
         "purpose": "Task DAG with T-NNN IDs, dependencies, REQ mappings.",
         "artifacts": ["pipeline/05-plan/tasks.yaml", "pipeline/05-plan/task-dag.md"]},
    6:  {"name": "build / implementation",
         "purpose": "Implement tasks from the plan; track progress.",
         "artifacts": ["pipeline/06-implementation/progress.md",
                       "pipeline/06-implementation/decisions.md"]},
    7:  {"name": "evaluation",
         "purpose": "Test against NFRs; verify acceptance criteria; profile-specific checks.",
         "artifacts": ["pipeline/07-evaluation/eval-report.md"]},
    8:  {"name": "deploy",
         "purpose": "Plan and execute deployment (or package publish for cli/library).",
         "artifacts": ["pipeline/08-deploy/deploy-plan.md"]},
    9:  {"name": "monitor",
         "purpose": "Configure runtime observability — metrics, alerts, dashboards.",
         "artifacts": ["pipeline/09-monitor/observability-config.md"]},
    10: {"name": "feedback",
         "purpose": "Collect and categorize feedback from users and metrics.",
         "artifacts": ["pipeline/10-feedback/feedback-log.md"]},
    11: {"name": "resolve",
         "purpose": "Triage and resolve issues from feedback.",
         "artifacts": ["pipeline/11-resolve/resolution-log.md"]},
    12: {"name": "release",
         "purpose": "Tag, changelog, publish; close the cycle.",
         "artifacts": ["CHANGELOG.md", "pipeline/12-release/release-notes.md"]},
}


def _import_format_gate_result(plugin_dir: Path):
    """Dynamic-import format-gate-result.py to reuse its fix-hint lookup."""
    path = plugin_dir / "scripts" / "format-gate-result.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("format_gate_result", path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        return None
    return mod


def _load_all_criteria(plugin_dir: Path) -> dict[str, dict]:
    """Return {criterion_id: criterion_dict} across all stages.

    Each value gets an added `_stage` field for cross-referencing.
    """
    gate_file = plugin_dir / "references" / "gate-criteria.md"
    if not gate_file.exists():
        return {}
    text = gate_file.read_text()
    blocks = re.findall(r"```yaml\n(.*?)```", text, re.DOTALL)
    result: dict[str, dict] = {}
    for block in blocks:
        try:
            data = yaml.safe_load(block)
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict):
            continue
        stage = data.get("stage")
        for c in data.get("criteria", []) or []:
            cid = c.get("id")
            if cid:
                c2 = dict(c)
                c2["_stage"] = stage
                result[cid] = c2
    return result


def _load_lessons(cwd: Path) -> list[dict]:
    """Load lessons from .forge/lessons.yaml, returning [] on absence/error."""
    path = cwd / ".forge" / "lessons.yaml"
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError:
        return []
    if not isinstance(data, dict):
        return []
    lessons = data.get("lessons", [])
    return lessons if isinstance(lessons, list) else []


# ---------- explainers ----------

def _explain_gate(target: str, plugin_dir: Path) -> dict | None:
    """Look up a gate criterion across all stages."""
    all_criteria = _load_all_criteria(plugin_dir)
    crit = all_criteria.get(target)
    if not crit:
        return None
    fgr = _import_format_gate_result(plugin_dir)
    fix_hint = ""
    if fgr is not None:
        try:
            fix_hint = fgr._lookup_fix_hint(crit)  # type: ignore[attr-defined]
        except Exception:
            fix_hint = ""
    return {
        "kind": "gate",
        "id": target,
        "stage": crit.get("_stage"),
        "description": crit.get("description", ""),
        "check": crit.get("check", ""),
        "args": crit.get("args", {}),
        "severity": crit.get("severity", "blocker"),
        "fix_hint": fix_hint,
    }


def _explain_lesson_tag(tag: str, cwd: Path, limit: int = 5) -> dict | None:
    """Return up to `limit` most-recent lessons matching the tag."""
    all_lessons = _load_lessons(cwd)
    matched = [
        l for l in all_lessons
        if isinstance(l, dict) and tag in (l.get("tags") or [])
    ]
    if not matched:
        return None
    # Sort by date desc (best-effort; missing dates sort last)
    matched.sort(key=lambda l: l.get("date") or "", reverse=True)
    return {
        "kind": "lesson_tag",
        "tag": tag,
        "match_count": len(matched),
        "lessons": matched[:limit],
    }


def _explain_stage(stage: int, plugin_dir: Path) -> dict | None:
    """Explain a pipeline stage including its blocker gate count."""
    if stage not in STAGE_NAMES:
        return None
    info = STAGE_NAMES[stage]
    all_criteria = _load_all_criteria(plugin_dir)
    stage_crits = [c for c in all_criteria.values() if c.get("_stage") == stage]
    blocker_count = sum(1 for c in stage_crits if c.get("severity") == "blocker")
    warning_count = sum(1 for c in stage_crits if c.get("severity") != "blocker")
    return {
        "kind": "stage",
        "stage": stage,
        "name": info["name"],
        "purpose": info["purpose"],
        "artifacts": info["artifacts"],
        "gate_blockers": blocker_count,
        "gate_warnings": warning_count,
        "gate_criterion_ids": [c["id"] for c in stage_crits],
    }


def _explain_current_blockers(cwd: Path, plugin_dir: Path) -> dict:
    """Explain the current stage's blockers (if any)."""
    state = lib.read_state(str(cwd))
    current_stage = state.get("current_stage", 0)
    check_gate = plugin_dir / "scripts" / "check-gate.py"
    if not check_gate.exists() or current_stage == 0:
        return {
            "kind": "current_blockers",
            "stage": current_stage,
            "blockers": [],
            "note": "No active stage or check-gate.py missing.",
        }
    proc = subprocess.run(
        [sys.executable, str(check_gate),
         "--stage", str(current_stage),
         "--cwd", str(cwd),
         "--plugin-dir", str(plugin_dir)],
        capture_output=True, text=True, check=False,
    )
    out = proc.stdout.strip()
    if not out.startswith("{"):
        return {
            "kind": "current_blockers",
            "stage": current_stage,
            "blockers": [],
            "note": "check-gate.py did not return JSON; cannot diagnose current blockers.",
        }
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {
            "kind": "current_blockers",
            "stage": current_stage,
            "blockers": [],
            "note": "check-gate.py output was not valid JSON.",
        }
    blockers = [
        c for c in data.get("details", [])
        if not c.get("passed") and c.get("severity") == "blocker"
    ]
    fgr = _import_format_gate_result(plugin_dir)
    enriched = []
    for b in blockers:
        b2 = dict(b)
        if fgr is not None:
            try:
                b2["fix_hint"] = fgr._lookup_fix_hint(b)  # type: ignore[attr-defined]
            except Exception:
                b2["fix_hint"] = ""
        enriched.append(b2)
    return {
        "kind": "current_blockers",
        "stage": current_stage,
        "blockers": enriched,
    }


# ---------- text rendering ----------

def _render(answer: dict) -> str:
    kind = answer.get("kind")
    if kind == "gate":
        return _render_gate(answer)
    if kind == "lesson_tag":
        return _render_lesson_tag(answer)
    if kind == "stage":
        return _render_stage(answer)
    if kind == "current_blockers":
        return _render_current_blockers(answer)
    return json.dumps(answer, indent=2)


def _render_gate(a: dict) -> str:
    lines = [
        f"Gate criterion: {a['id']}",
        f"  Stage:       {a['stage']}",
        f"  Severity:    {a['severity']}",
        f"  Check type:  {a['check']}",
        f"  Description: {a['description']}",
    ]
    if a.get("args"):
        lines.append(f"  Check args:  {json.dumps(a['args'])}")
    if a.get("fix_hint"):
        lines.append("")
        lines.append("  Fix hint:")
        for line in str(a["fix_hint"]).splitlines() or [a["fix_hint"]]:
            lines.append(f"    {line}")
    return "\n".join(lines)


def _render_lesson_tag(a: dict) -> str:
    lines = [
        f"Lesson tag: {a['tag']}",
        f"  Total matches: {a['match_count']} "
        f"(showing {len(a['lessons'])} most recent)",
        "",
    ]
    for i, l in enumerate(a["lessons"], 1):
        lines.append(f"  [{i}] {l.get('date', '?date')} — Stage "
                     f"{','.join(str(s) for s in l.get('stage', []))}")
        if l.get("trigger"):
            lines.append(f"      trigger: {l['trigger']}")
        if l.get("rule"):
            lines.append(f"      rule:    {l['rule']}")
        if l.get("reason") and l.get("reason") != l.get("rule"):
            lines.append(f"      reason:  {l['reason']}")
        if l.get("blockers"):
            lines.append(f"      blockers: {', '.join(l['blockers'])}")
        lines.append("")
    return "\n".join(lines)


def _render_stage(a: dict) -> str:
    lines = [
        f"Stage {a['stage']} — {a['name']}",
        f"  Purpose: {a['purpose']}",
        f"  Gate criteria: {a['gate_blockers']} blocker(s), "
        f"{a['gate_warnings']} warning(s)",
        f"  Artifacts:",
    ]
    for art in a["artifacts"]:
        lines.append(f"    - {art}")
    if a["gate_criterion_ids"]:
        lines.append(f"  Criterion IDs: {', '.join(a['gate_criterion_ids'])}")
    return "\n".join(lines)


def _render_current_blockers(a: dict) -> str:
    if a.get("note"):
        return f"Stage {a['stage']}: {a['note']}"
    if not a["blockers"]:
        return f"Stage {a['stage']}: no blockers. You can advance with `/forge:advance`."
    lines = [f"Stage {a['stage']}: {len(a['blockers'])} blocker(s):", ""]
    for b in a["blockers"]:
        lines.append(f"  ✗ {b['id']} — {b.get('description', '')}")
        if b.get("message"):
            lines.append(f"      detail: {b['message']}")
        if b.get("fix_hint"):
            lines.append(f"      fix:    {b['fix_hint']}")
        lines.append("")
    lines.append("To override: /forge:force-advance --reason '<why>'  "
                 "(records a lesson)")
    return "\n".join(lines)


# ---------- driver ----------

_STAGE_PATTERN = re.compile(r"^(?:stage-)?([1-9]|1[0-2])$", re.IGNORECASE)
# REQ-WHYCI-001: gate IDs are matched case-insensitively (sibling _STAGE_PATTERN
# already is); the target is upper-cased before the gate-criteria lookup.
_GATE_PATTERN = re.compile(r"^G\d+", re.IGNORECASE)


def _classify(target: str) -> str:
    """Return 'gate', 'stage', or 'tag' based on input shape."""
    if _GATE_PATTERN.match(target):
        return "gate"
    if _STAGE_PATTERN.match(target):
        return "stage"
    return "tag"


def _should_try_fallback(forge_dir: Path) -> bool:
    """True when the background capability is available and not opted out (REQ-F-050)."""
    if os.environ.get("FORGE_NO_BACKGROUND") == "1":
        return False
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
        import _background_agent  # noqa: PLC0415
        caps = _background_agent.read_capabilities(Path(forge_dir)) or {}
        return caps.get("forge_background_available") is True
    except Exception:  # noqa: BLE001 — capability check must never break `why`
        return False


def _llm_fallback(target: str, *, forge_dir: Path, dispatch_fn=None) -> Optional[str]:
    """Best-effort explanation of an unknown ID via one orchestrated subagent
    (REQ-F-050, uses REQ-F-031). Returns clearly-marked text, or None if the agent
    is unavailable / its output was dropped. Never raises."""
    try:
        import _orchestrate  # noqa: PLC0415

        def _validate(d: dict) -> dict:
            if not isinstance(d, dict) or not isinstance(d.get("explanation"), str) \
                    or not d["explanation"].strip():
                raise ValueError("no explanation")
            return d

        prompt = (
            f"A user ran `/forge:why {target}` but it is not a known Forge gate ID, "
            f"lesson tag, or stage (1-12). Briefly explain what it most likely refers to "
            f"in a Forge SDLC pipeline, and state plainly that it is not a recognized "
            f'Forge identifier. Reply with JSON: {{"explanation": "<2-4 sentences>"}}.'
        )
        fan = _orchestrate.fan_out([target], lambda _t: prompt, forge_dir=Path(forge_dir),
                                   feature="why", validate=_validate, max_parallel=1,
                                   dispatch_fn=dispatch_fn)
        if not fan.results:
            return None
        explanation = fan.results[0]["explanation"].strip()
        return (f"⚠️  '{target}' is not a recognized Forge ID — best-effort inference:\n\n"
                f"{explanation}\n\n(Not authoritative — verify against references/.)")
    except Exception:  # noqa: BLE001 — fallback is advisory; never crash `why`
        return None


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="why.py",
        description="Explain a gate criterion, lesson tag, stage, or current blockers.",
    )
    parser.add_argument("target", nargs="?", default=None,
                        help="gate ID (G1-001), lesson tag (force-advance), "
                             "stage (3 or stage-3), or omit for current blockers")
    parser.add_argument("--cwd", default=os.getcwd(), metavar="PATH",
                        help="project root (default: cwd)")
    parser.add_argument("--plugin-dir",
                        default=str(Path(__file__).resolve().parent.parent),
                        metavar="PATH",
                        help="Forge plugin root (default: parent of scripts/)")
    parser.add_argument("--json", action="store_true",
                        help="emit structured JSON instead of text")
    args = parser.parse_args(argv)

    cwd = Path(args.cwd).resolve()
    plugin_dir = Path(args.plugin_dir).resolve()

    # Bare invocation → current blockers
    if not args.target:
        answer: dict | None = _explain_current_blockers(cwd, plugin_dir)
    else:
        target = args.target.strip()
        kind = _classify(target)
        if kind == "gate":
            answer = _explain_gate(target.upper(), plugin_dir)  # REQ-WHYCI-001
        elif kind == "stage":
            m = _STAGE_PATTERN.match(target)
            stage_num = int(m.group(1)) if m else None
            answer = _explain_stage(stage_num, plugin_dir) if stage_num else None
        else:
            answer = _explain_lesson_tag(target, cwd)

    if answer is None:
        # REQ-F-050: when deterministic lookup misses, fall back to a single
        # orchestrated subagent — but only if background capability is available.
        if args.target and _should_try_fallback(cwd / ".forge"):
            inferred = _llm_fallback(args.target.strip(), forge_dir=cwd / ".forge")
            if inferred:
                print(inferred)
                return 0
        msg = f"error: '{args.target}' not found "
        if args.target and _GATE_PATTERN.match(args.target.strip()):
            msg += "(no such gate criterion in references/gate-criteria.md)"
        elif args.target and _STAGE_PATTERN.match(args.target.strip()):
            msg += "(stage must be 1-12)"
        else:
            msg += "(no lessons match this tag)"
        print(msg, file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(answer, indent=2, default=str))
    else:
        print(_render(answer))
    return 0


if __name__ == "__main__":
    sys.exit(main())