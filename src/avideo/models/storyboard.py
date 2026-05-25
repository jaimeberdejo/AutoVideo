"""StoryboardOutput — output contract for the storyboard generation stage."""
from __future__ import annotations

from pydantic import BaseModel


class SlideSpec(BaseModel):
    """Specification for a single slide in the storyboard."""

    title: str
    bullets: list[str]
    visual_type: str = "text"


class StoryboardOutput(BaseModel):
    """Full storyboard produced by the LLM storyboard stage."""

    slides: list[SlideSpec]
    language: str = "es"
