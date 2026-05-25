"""RunConfig — single source of truth for all pipeline configuration.

Priority: CLI kwargs (init_settings) > config.yaml > env > Pydantic defaults.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


class VoiceMode(str, Enum):
    """TTS source selection."""

    elevenlabs = "elevenlabs"
    record = "record"


class SlidesMode(str, Enum):
    """Slide generation mode."""

    auto = "auto"
    hybrid = "hybrid"
    manual = "manual"


class RunConfig(BaseSettings):
    """All pipeline parameters, merged from CLI flags, config.yaml, and defaults."""

    # Required inputs
    bullets: Path
    duration: int = Field(gt=0, description="Target duration in seconds")

    # Optional inputs
    context: Optional[Path] = None

    # Voice settings
    voice: VoiceMode = VoiceMode.elevenlabs
    # voice_id default is Rachel (21m00Tcm4TlvDq8ikWAM) — a placeholder; move to config.yaml
    # for production use (supports eleven_multilingual_v2 for Spanish).
    voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    # whisperx_model: size for WhisperX forced-alignment (D-05).
    # "small" balances CPU speed vs. precision; use "large-v3" for GPU runs.
    # Configurable via AVIDEO_WHISPERX_MODEL env var or config.yaml whisperx_model key.
    whisperx_model: str = "small"

    # Slide settings
    slides_mode: SlidesMode = SlidesMode.auto

    # Pipeline control
    level: int = Field(default=4, ge=1, le=4, description="Automation level 1-4")
    wpm: int = Field(default=150, gt=0, description="Words per minute for timing")
    language: str = "es"

    # Assembly / QA settings (Phase 5)
    crossfade_seconds: float = Field(
        default=0.5,
        ge=0,
        description="Crossfade duration between slides in seconds; 0 = hard cuts (D-03)",
    )
    target_lufs: float = Field(
        default=-16.0,
        description="EBU R128 loudness target for two-pass loudnorm in LUFS (D-06)",
    )

    # Flags
    dry_run: bool = False
    burn_subs: bool = False
    verbose: bool = False

    # Filesystem
    workdir: Path = Path("workdir")

    model_config = SettingsConfigDict(
        yaml_file="config.yaml",
        yaml_file_encoding="utf-8",
        extra="ignore",
        env_prefix="AVIDEO_",  # Avoid collisions with common OS vars (LANGUAGE, LEVEL, etc.)
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Priority: CLI kwargs > config.yaml > env > defaults."""
        return (
            init_settings,
            YamlConfigSettingsSource(settings_cls),
            env_settings,
        )
