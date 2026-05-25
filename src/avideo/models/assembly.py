"""AssemblyOutput — output contract for the FFmpeg assembly and QA stage."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class QAReport(BaseModel):
    """Quality metrics for the assembled video."""

    target_seconds: float
    actual_seconds: float
    duration_deviation: float
    lufs: Optional[float] = None


class AssemblyOutput(BaseModel):
    """Result of the final video assembly stage."""

    output_path: str
    qa: Optional[QAReport] = None
