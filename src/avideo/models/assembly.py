"""AssemblyOutput — output contract for the FFmpeg assembly and QA stage."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class QAReport(BaseModel):
    """Quality metrics for the assembled video.

    Carries duration deviation (QA-01) and loudness measurements (QA-02).

    Attributes:
        target_seconds:     Target video duration in seconds (from RunConfig.duration).
        actual_seconds:     Actual video duration measured by ffprobe on output.mp4.
        duration_deviation: actual_seconds - target_seconds (negative = short, positive = long).
        lufs:               Legacy single loudness field (kept for back-compat; prefer
                            measured_lufs / normalized_lufs).
        measured_lufs:      Pre-normalization integrated loudness (loudnorm pass-1 input_i).
        normalized_lufs:    Post-normalization integrated loudness (loudnorm pass-2 output_i
                            or a re-measured pass-1 on the normalized file).
    """

    target_seconds: float
    actual_seconds: float
    duration_deviation: float
    lufs: Optional[float] = None
    measured_lufs: Optional[float] = None
    normalized_lufs: Optional[float] = None


class AssemblyOutput(BaseModel):
    """Result of the final video assembly stage."""

    output_path: str
    qa: Optional[QAReport] = None
