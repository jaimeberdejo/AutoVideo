"""Tests for Phase 8 model layer additions: VoiceMode.openai + new RunConfig fields.

TDD RED phase — these tests FAIL until Task 1 edits config.py.
"""
import pytest
from pathlib import Path
from pydantic import ValidationError


def test_voice_mode_openai_value(minimal_bullets: Path) -> None:
    """VoiceMode.openai exists and has string value 'openai'."""
    from avideo.models.config import VoiceMode
    assert VoiceMode("openai") is VoiceMode.openai
    assert VoiceMode.openai.value == "openai"


def test_voice_mode_openai_coercion(minimal_bullets: Path) -> None:
    """RunConfig accepts voice='openai' and coerces to VoiceMode.openai."""
    from avideo.models.config import RunConfig, VoiceMode
    cfg = RunConfig(bullets=minimal_bullets, duration=60, voice="openai")
    assert cfg.voice is VoiceMode.openai


def test_runconfig_openai_tts_defaults(minimal_bullets: Path) -> None:
    """New openai_tts_model and openai_tts_voice fields have correct defaults."""
    from avideo.models.config import RunConfig
    cfg = RunConfig(bullets=minimal_bullets, duration=60)
    assert cfg.openai_tts_model == "tts-1"
    assert cfg.openai_tts_voice == "nova"


def test_runconfig_bg_music_defaults(minimal_bullets: Path) -> None:
    """New bg_music_* fields have correct defaults: path=None, volume=0.12, fade=3.0."""
    from avideo.models.config import RunConfig
    cfg = RunConfig(bullets=minimal_bullets, duration=60)
    assert cfg.bg_music_path is None
    assert cfg.bg_music_volume == 0.12
    assert cfg.bg_music_fade_out_s == 3.0


def test_runconfig_bg_music_volume_too_high_raises(minimal_bullets: Path) -> None:
    """bg_music_volume > 1.0 must raise ValidationError (le=1.0 constraint)."""
    from avideo.models.config import RunConfig
    with pytest.raises(ValidationError):
        RunConfig(bullets=minimal_bullets, duration=60, bg_music_volume=1.5)


def test_runconfig_bg_music_volume_negative_raises(minimal_bullets: Path) -> None:
    """bg_music_volume < 0.0 must raise ValidationError (ge=0.0 constraint)."""
    from avideo.models.config import RunConfig
    with pytest.raises(ValidationError):
        RunConfig(bullets=minimal_bullets, duration=60, bg_music_volume=-0.1)


def test_runconfig_bg_music_fade_negative_raises(minimal_bullets: Path) -> None:
    """bg_music_fade_out_s < 0.0 must raise ValidationError (ge=0.0 constraint)."""
    from avideo.models.config import RunConfig
    with pytest.raises(ValidationError):
        RunConfig(bullets=minimal_bullets, duration=60, bg_music_fade_out_s=-1.0)


def test_runconfig_existing_fields_unchanged(minimal_bullets: Path) -> None:
    """Adding new fields must not break any existing RunConfig fields or defaults."""
    from avideo.models.config import RunConfig, VoiceMode, SlidesMode
    cfg = RunConfig(bullets=minimal_bullets, duration=120)
    # All existing defaults must be unchanged
    assert cfg.voice is VoiceMode.elevenlabs
    assert cfg.slides_mode is SlidesMode.auto
    assert cfg.level == 4
    assert cfg.wpm == 150
    assert cfg.language == "es"
    assert cfg.dry_run is False
    assert cfg.burn_subs is False
    assert cfg.verbose is False
    assert cfg.crossfade_seconds == 0.5
    assert cfg.target_lufs == -16.0
    assert cfg.workdir == Path("workdir")
