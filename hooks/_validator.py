"""Deterministic proposal validator (FR-DET-002).

Checks schema validity (via Pydantic), policy (trust level), and conflicts
against existing trusted lessons. No LLM calls — all logic is deterministic.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Union

sys.path.insert(0, str(Path(__file__).parent))
from _proposals import (
    GateProposal,
    LessonProposal,
    ReflectionProposal,
    StageAdvanceProposal,
)

AnyProposal = Union[ReflectionProposal, LessonProposal, GateProposal, StageAdvanceProposal]


def validate(proposal: AnyProposal, forge_dir: Path) -> tuple[bool, str]:
    """Return (accepted, reason). reason is '' on accept."""
    if isinstance(proposal, ReflectionProposal):
        return _validate_reflection(proposal)
    if isinstance(proposal, LessonProposal):
        return _validate_lesson(proposal, forge_dir)
    if isinstance(proposal, (GateProposal, StageAdvanceProposal)):
        return True, ""
    return False, f"unknown proposal type: {type(proposal).__name__}"


def _validate_reflection(p: ReflectionProposal) -> tuple[bool, str]:
    if not p.prose.strip():
        return False, "prose is empty"
    if not p.prompt_hash:
        return False, "prompt_hash is empty"
    return True, ""


def _validate_lesson(p: LessonProposal, forge_dir: Path) -> tuple[bool, str]:
    if p.trust != "ephemeral":
        return False, "lesson trust must be 'ephemeral' on creation"

    lessons_yaml = forge_dir / "lessons.yaml"
    if not lessons_yaml.exists():
        return True, ""

    try:
        import yaml
        existing: list = yaml.safe_load(lessons_yaml.read_text()) or []
    except Exception:
        return True, ""  # fail open — can't risk blocking on unreadable lessons

    if not isinstance(existing, list):
        return True, ""

    trigger_norm = p.trigger.strip().lower()
    rule_norm = p.rule.strip().lower()

    for ex in existing:
        if not isinstance(ex, dict):
            continue
        ex_trigger = ex.get("trigger", "").strip().lower()

        if ex_trigger == trigger_norm:
            return False, f"duplicate trigger: '{p.trigger}'"

        # Conflict: overlapping trigger + trusted lesson with opposite negation
        if ex.get("trust") == "trusted" and ex_trigger and (
            ex_trigger in trigger_norm or trigger_norm in ex_trigger
        ):
            ex_rule = ex.get("rule", "").strip().lower()
            ex_neg = " not " in ex_rule or ex_rule.startswith("not ")
            new_neg = " not " in rule_norm or rule_norm.startswith("not ")
            if ex_neg != new_neg:
                return False, (
                    f"conflicts with trusted lesson on trigger '{ex.get('trigger')}'"
                )

    return True, ""
