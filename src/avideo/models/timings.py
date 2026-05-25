"""Unified timing model — shared contract for voice and subtitle stages.

Both voice backends (ElevenLabs and WhisperX) produce a ``UnifiedTimings``
instance so that ``stages/subtitles.py`` is fully agnostic of the voice source.

Coordinate system:
    All ``start``/``end`` values in ``WordTiming`` are in **SECONDS**, measured
    RELATIVE to the beginning of the individual slide's audio clip.  They are
    NOT global (accumulated) timestamps.

    When assembling subtitles for the final video, ``stages/subtitles.py``
    accumulates a running offset (``offset += slide.duration`` after each slide)
    to convert per-slide relative timestamps into global video timestamps.
    This design is documented here (Open Question 1 of 04-RESEARCH.md) so
    Phase 5 consumes it correctly.

    Example (3-slide video, durations 5s / 3s / 4s):
        slide 0 word "hello": start=0.1, end=0.5  → global start = 0.1
        slide 1 word "world": start=0.2, end=0.6  → global start = 5.2 (offset = 5.0)
        slide 2 word "bye":   start=0.0, end=0.3  → global start = 8.0 (offset = 8.0)
"""
from __future__ import annotations

from pydantic import BaseModel


class WordTiming(BaseModel):
    """Timing for a single word within a slide.

    Attributes:
        text: The word text (may include punctuation).
        start: Word start in **seconds**, RELATIVE to the start of this slide's
            audio clip.  NOT a global timeline timestamp.
        end: Word end in **seconds**, RELATIVE to the start of this slide's
            audio clip.
    """

    text: str
    start: float  # SECONDS, relative to the start of this slide's audio clip
    end: float    # SECONDS, relative to the start of this slide's audio clip


class SlideTimings(BaseModel):
    """Timing data for a single slide's audio.

    Attributes:
        slide_index: Zero-based slide position (matches ScriptOutput.slides index).
        audio_path: Relative path from workdir root, e.g. ``"audio/slide_00.mp3"``
            (stored relative for checkpoint portability — workdir may be moved).
        duration: Total duration of the slide's audio clip in seconds.
            For ElevenLabs: set to the last ``character_end_times_seconds`` value.
            For WhisperX: set from the last word's end time or ffprobe (Phase 5).
        words: Word-level timings.  ElevenLabs synthesize path populates this by
            grouping per-character timestamps into words (split on whitespace).
            WhisperX path populates this directly from ``word_segments``.
            Empty list only if no characters/words were returned by the backend.
    """

    slide_index: int
    audio_path: str    # relative path: "audio/slide_00.mp3" or "audio/slide_00.wav"
    duration: float    # seconds (last character_end_times_seconds or ffprobe in Phase 5)
    words: list[WordTiming] = []


class UnifiedTimings(BaseModel):
    """Unified timing contract consumed by stages/subtitles.py (D-11).

    Both voice backends must produce this model so the subtitle stage is
    fully source-agnostic.

    Attributes:
        source: The backend that produced these timings.
            ``"elevenlabs"`` — from convert_with_timestamps (D-03).
            ``"whisperx"`` — from WhisperX forced-alignment (D-05/D-06).
        slides: One ``SlideTimings`` per slide, in slide_index order.
    """

    source: str           # "elevenlabs" | "whisperx"
    slides: list[SlideTimings]
