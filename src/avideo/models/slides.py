"""SlidesOutput — output contract for the slide generation/render stage."""
from __future__ import annotations

from pydantic import BaseModel


class SlidesOutput(BaseModel):
    """Paths to rendered slide PNG files."""

    png_paths: list[str]
    mode: str = "auto"
