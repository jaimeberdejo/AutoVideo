"""Tests for Pydantic I/O contracts: RunConfig and all stage output models."""
import pytest
from pathlib import Path
from pydantic import ValidationError


def test_runconfig_defaults(minimal_bullets: Path) -> None:
    """RunConfig defaults: voice=elevenlabs, slides_mode=auto, level=4, wpm=150, language=es."""
    from avideo.models import RunConfig, VoiceMode, SlidesMode
    cfg = RunConfig(bullets=minimal_bullets, duration=120)
    assert cfg.voice is VoiceMode.elevenlabs
    assert cfg.slides_mode is SlidesMode.auto
    assert cfg.level == 4
    assert cfg.wpm == 150
    assert cfg.language == "es"
    assert cfg.dry_run is False
    assert cfg.burn_subs is False


def test_runconfig_duration_zero_raises(minimal_bullets: Path) -> None:
    """duration=0 must raise ValidationError."""
    from avideo.models import RunConfig
    with pytest.raises(ValidationError):
        RunConfig(bullets=minimal_bullets, duration=0)


def test_runconfig_level_too_high_raises(minimal_bullets: Path) -> None:
    """level=5 must raise ValidationError."""
    from avideo.models import RunConfig
    with pytest.raises(ValidationError):
        RunConfig(bullets=minimal_bullets, duration=120, level=5)


def test_runconfig_level_too_low_raises(minimal_bullets: Path) -> None:
    """level=0 must raise ValidationError."""
    from avideo.models import RunConfig
    with pytest.raises(ValidationError):
        RunConfig(bullets=minimal_bullets, duration=120, level=0)


def test_runconfig_voice_string_coercion(minimal_bullets: Path) -> None:
    """voice='record' as string coerces to VoiceMode.record."""
    from avideo.models import RunConfig, VoiceMode
    cfg = RunConfig(bullets=minimal_bullets, duration=120, voice="record")
    assert cfg.voice is VoiceMode.record


def test_runconfig_slides_mode_string_coercion(minimal_bullets: Path) -> None:
    """slides_mode='hybrid' as string coerces to SlidesMode.hybrid."""
    from avideo.models import RunConfig, SlidesMode
    cfg = RunConfig(bullets=minimal_bullets, duration=120, slides_mode="hybrid")
    assert cfg.slides_mode is SlidesMode.hybrid


def test_storyboard_output_roundtrip() -> None:
    """StoryboardOutput round-trips through model_dump_json/model_validate_json."""
    from avideo.models import StoryboardOutput, SlideSpec, VisualType
    sb = StoryboardOutput(
        slides=[SlideSpec(title="Slide 1", bullets=["A", "B"], visual_type=VisualType.bullets)],
        language="es",
    )
    reloaded = StoryboardOutput.model_validate_json(sb.model_dump_json())
    assert reloaded == sb


def test_all_stage_outputs_instantiate_and_roundtrip() -> None:
    """All stage output models instantiate with minimal required fields and round-trip."""
    from avideo.models import (
        ContextOutput,
        TimingOutput, SlideTiming,
        ScriptOutput, SlideScript,
        SlidesOutput,
        VerificationReport, SlideVerdict,
        VoiceOutput,
        AssemblyOutput,
    )

    models = [
        ContextOutput(),
        TimingOutput(
            slides=[SlideTiming(slide_index=0, seconds=10.0, word_budget=25)],
            total_seconds=10.0,
        ),
        ScriptOutput(
            slides=[SlideScript(slide_index=0, narration="Hello")],
        ),
        SlidesOutput(png_paths=["slide_0.png"]),
        VerificationReport(
            slides=[SlideVerdict(slide_index=0)],
        ),
        VoiceOutput(audio_paths=["audio_0.mp3"]),
        AssemblyOutput(output_path="output.mp4"),
    ]

    for model in models:
        cls = type(model)
        reloaded = cls.model_validate_json(model.model_dump_json())
        assert reloaded == model
