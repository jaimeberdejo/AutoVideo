"""StoryboardOutput — output contract for the storyboard generation stage."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class VisualType(str, Enum):
    """Closed enum of allowed visual layouts for a slide (D-02).

    Phase 3 renderer receives predictable values — no free-form strings.
    Values correspond to HTML/CSS templates in the slides stage.

    Migration note: Phase-1 stub used visual_type="text" which is NOT in this
    enum.  Delete any stale workdir/storyboard.json (+ .storyboard.done) before
    running over an old workdir created with the Phase-1 stub.
    """

    title = "title"
    bullets = "bullets"
    chart = "chart"
    diagram = "diagram"
    quote = "quote"
    comparison = "comparison"
    image_icon = "image_icon"


class SlideSpec(BaseModel):
    """Specification for a single slide in the storyboard."""

    title: str
    bullets: list[str]
    visual_type: VisualType = VisualType.bullets  # default changed from "text" (D-02)


class StoryboardOutput(BaseModel):
    """Full storyboard produced by the LLM storyboard stage."""

    slides: list[SlideSpec]
    language: str = "es"
