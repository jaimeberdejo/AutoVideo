"""VoiceOutput — output contract for the TTS / voice recording stage."""
from __future__ import annotations

from pydantic import BaseModel


class VoiceOutput(BaseModel):
    """Paths to generated or recorded audio files, one per slide."""

    audio_paths: list[str]
    voice_mode: str = "elevenlabs"
