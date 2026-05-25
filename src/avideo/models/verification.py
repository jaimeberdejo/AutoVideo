"""VerificationReport — output contract for the Claude vision verifier stage."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SlideVerdict(BaseModel):
    """Verification result for one slide."""

    slide_index: int
    status: str = "ok"  # one of: ok, warning, fail
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class VerificationReport(BaseModel):
    """Full verification report across all slides."""

    slides: list[SlideVerdict]
