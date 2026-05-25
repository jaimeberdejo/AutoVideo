"""TimingOutput — output contract for the timing/duration director stage."""
from __future__ import annotations

from pydantic import BaseModel


class SlideTiming(BaseModel):
    """Timing allocation for one slide."""

    slide_index: int
    seconds: float
    word_budget: int


class TimingOutput(BaseModel):
    """Complete timing plan for the full video."""

    slides: list[SlideTiming]
    total_seconds: float
    wpm: int = 150
