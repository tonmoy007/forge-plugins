"""Proposal schemas for the Stop hook pipeline (FR-DET-001, v4.1).

All writes to long-term memory originate as proposal objects validated before
execution. LessonProposal enforces trust="ephemeral" at the type level — no
LLM-extracted lesson can be promoted at creation time.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ReflectionProposal(BaseModel):
    stage: int
    score: int = Field(ge=1, le=10)
    gaps: list[str] = Field(max_length=10)
    prose: str = Field(max_length=4000)
    model: str
    prompt_hash: str
    temperature: float
    created_at: datetime


class LessonProposal(BaseModel):
    trigger: str = Field(max_length=200)
    rule: str = Field(max_length=500)
    why: str = Field(max_length=500)
    stage_tags: list[int]
    trust: Literal["ephemeral"] = "ephemeral"  # cannot be elevated on creation
    source_session: str
    source_corrections: list[str]
    model: str
    prompt_hash: str
    temperature: float
    created_at: datetime


class GateProposal(BaseModel):
    stage: int
    passed: bool
    blockers: list[str]
    advance_to: int | None
    checked_at: datetime


class StageAdvanceProposal(BaseModel):
    from_stage: int
    to_stage: int
    triggered_by: Literal["done_signal_with_passing_gate"]
    created_at: datetime
