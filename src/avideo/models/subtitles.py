"""SubtitlesOutput — output contract for the subtitle generation stage (SUB-01)."""
from __future__ import annotations

from pydantic import BaseModel


class SubtitlesOutput(BaseModel):
    """Output model for the subtitles stage (SubtitlesStage).

    Attributes:
        srt_path: Relative path from workdir root to the generated SRT file.
            e.g. ``"subs/output.srt"``
        vtt_path: Relative path from workdir root to the generated VTT file.
            e.g. ``"subs/output.vtt"``
        cue_count: Total number of subtitle cues generated (for logging/QA).
    """

    srt_path: str
    vtt_path: str
    cue_count: int = 0
