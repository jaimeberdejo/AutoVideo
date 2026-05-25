"""ContextOutput — output contract for the context ingestion stage."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ContextOutput(BaseModel):
    """Result of ingesting an optional context document (.pptx/.pdf/.md)."""

    source_path: Optional[str] = None
    text: str = ""
    used: bool = False
