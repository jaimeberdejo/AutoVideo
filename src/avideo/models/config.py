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
    voice_id: str = "21m00Tcm4TlvDq8ikWAM"

    # Slide settings
    slides_mode: SlidesMode = SlidesMode.auto

    # Pipeline control
    level: int = Field(default=4, ge=1, le=4, description="Automation level 1-4")
    wpm: int = Field(default=150, gt=0, description="Words per minute for timing")
    language: str = "es"

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
