"""ScriptOutput — output contract for the scriptwriter (narration) stage."""
from __future__ import annotations

from pydantic import BaseModel


class SlideScript(BaseModel):
    """Narration text for one slide."""

    slide_index: int
    narration: str


class ScriptOutput(BaseModel):
    """Full narration script for all slides."""

    slides: list[SlideScript]
    language: str = "es"
