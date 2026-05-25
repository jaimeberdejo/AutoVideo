"""BulletsInput — input contract for a bullets.yaml file.

A bullets.yaml file has exactly two required keys:
    title: str              -- short title for the overall presentation
    bullets: list[str]      -- ordered list of talking points / slide bullets
"""
from __future__ import annotations

from pydantic import BaseModel


class BulletsInput(BaseModel):
    """Parsed representation of a bullets.yaml input file.

    Attributes:
        title: Short title for the overall presentation.
        bullets: Ordered list of talking points / slide bullets.
    """

    title: str
    bullets: list[str]
