"""Tests for stages/align.py + integrations/whisperx.py align_wav — ALIGN-01 + ALIGN-02.

Covers:
  - ALIGN-01: record mode — AlignStage calls align_wav per wav → UnifiedTimings(source=whisperx)
    with words populated.
  - ALIGN-02 (elevenlabs_skip): elevenlabs mode — AlignStage is a no-op; align_wav NOT called;
    result is the unchanged voice checkpoint.
  - stage_name == "align"
  - mock point: align_wav patched at avideo.stages.align.align_wav (module-scope import)

No real models are loaded.  align_wav is always mocked.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from avideo.models.config import RunConfig, VoiceMode
from avideo.models.timings import SlideTimings, UnifiedTimings, WordTiming
from avideo.utils.workdir import WorkdirManager


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _build_config(
    tmp_path: Path,
    voice: VoiceMode = VoiceMode.record,
    whisperx_model: str = "small",
) -> RunConfig:
    bullets = tmp_path / "bullets.yaml"
    bullets.write_text("title: Test\nbullets:\n  - Point 1\n", encoding="utf-8")
    return RunConfig(
        bullets=bullets,
        duration=60,
        voice=voice,
        voice_id="test-voice-id",
        whisperx_model=whisperx_model,
        workdir=tmp_path / "workdir",
    )


def _write_voice_checkpoint(
    workdir: WorkdirManager,
    source: str = "record",
    n_slides: int = 2,
) -> UnifiedTimings:
    """Write a minimal voice checkpoint and return the UnifiedTimings written."""
    slides = [
        SlideTimings(
            slide_index=i,
            audio_path=f"audio/slide_{i:02d}.wav",
            duration=2.5,
            words=[],
        )
        for i in range(n_slides)
    ]
    timings = UnifiedTimings(source=source, slides=slides)
    workdir.write_checkpoint("voice", timings)
    return timings


# ---------------------------------------------------------------------------
# stage_name
# ---------------------------------------------------------------------------


def test_align_stage_name():
    """AlignStage must have stage_name='align'."""
    from avideo.stages.align import AlignStage

    stage = AlignStage()
    assert stage.stage_name == "align"


# ---------------------------------------------------------------------------
# ALIGN-01: record mode — whisperx aligns per slide
# ---------------------------------------------------------------------------


def test_align_record_calls_align_wav_per_slide(tmp_path: Path, fake_word_segments):
    """In record mode, align_wav is called once per slide with the correct wav path."""
    workdir = WorkdirManager(tmp_path / "workdir")

    # Create placeholder WAV files so the align stage can find them
    for i in range(2):
        wav_path = workdir.root / "audio" / f"slide_{i:02d}.wav"
        wav_path.write_bytes(b"\x00" * 44)

    _write_voice_checkpoint(workdir, source="record", n_slides=2)

    config = _build_config(tmp_path, voice=VoiceMode.record)

    from avideo.stages.align import AlignStage

    with patch("avideo.stages.align.align_wav", return_value=fake_word_segments) as mock_align:
        stage = AlignStage()
        result = stage.run(workdir, config)

    # align_wav called once per slide
    assert mock_align.call_count == 2, (
        f"Expected align_wav called 2 times, got {mock_align.call_count}"
    )

    # Check that each call included the correct wav path (as string ending with the expected filename)
    expected_paths = [
        str(workdir.root / "audio" / "slide_00.wav"),
        str(workdir.root / "audio" / "slide_01.wav"),
    ]
    actual_paths = [c.args[0] for c in mock_align.call_args_list]
    for expected, actual in zip(expected_paths, actual_paths):
        assert expected == actual, f"Expected wav path {expected!r}, got {actual!r}"


def test_align_record_returns_whisperx_source(tmp_path: Path, fake_word_segments):
    """In record mode, result.source must be 'whisperx' (ALIGN-01)."""
    workdir = WorkdirManager(tmp_path / "workdir")

    for i in range(2):
        (workdir.root / "audio" / f"slide_{i:02d}.wav").write_bytes(b"\x00" * 44)

    _write_voice_checkpoint(workdir, source="record", n_slides=2)
    config = _build_config(tmp_path, voice=VoiceMode.record)

    from avideo.stages.align import AlignStage

    with patch("avideo.stages.align.align_wav", return_value=fake_word_segments):
        stage = AlignStage()
        result = stage.run(workdir, config)

    assert isinstance(result, UnifiedTimings)
    assert result.source == "whisperx"


def test_align_record_populates_words(tmp_path: Path, fake_word_segments):
    """In record mode, SlideTimings.words must be populated from align_wav result."""
    workdir = WorkdirManager(tmp_path / "workdir")

    for i in range(2):
        (workdir.root / "audio" / f"slide_{i:02d}.wav").write_bytes(b"\x00" * 44)

    _write_voice_checkpoint(workdir, source="record", n_slides=2)
    config = _build_config(tmp_path, voice=VoiceMode.record)

    from avideo.stages.align import AlignStage

    with patch("avideo.stages.align.align_wav", return_value=fake_word_segments):
        stage = AlignStage()
        result = stage.run(workdir, config)

    for slide_timing in result.slides:
        assert len(slide_timing.words) > 0, (
            f"Slide {slide_timing.slide_index} words must not be empty after ALIGN-01"
        )
        assert all(isinstance(w, WordTiming) for w in slide_timing.words)

    # Check specific word content from fake_word_segments fixture
    # fake_word_segments = [{"word": "hola", "start": 0.0, "end": 0.4}, ...]
    assert result.slides[0].words[0].text == "hola"
    assert result.slides[0].words[0].start == 0.0
    assert result.slides[0].words[0].end == 0.4


def test_align_record_duration_from_last_word_end(tmp_path: Path, fake_word_segments):
    """In record mode, slide duration must reflect last word.end when words are populated.

    Critical guidance Warning 1: duration must NEVER be 0.0 when words exist.
    """
    workdir = WorkdirManager(tmp_path / "workdir")

    for i in range(1):
        (workdir.root / "audio" / "slide_00.wav").write_bytes(b"\x00" * 44)

    # Voice checkpoint has duration=0.0 (initial stub — align must fix it)
    slides = [SlideTimings(slide_index=0, audio_path="audio/slide_00.wav", duration=0.0, words=[])]
    timings = UnifiedTimings(source="record", slides=slides)
    workdir.write_checkpoint("voice", timings)

    config = _build_config(tmp_path, voice=VoiceMode.record)

    from avideo.stages.align import AlignStage

    # fake_word_segments last end is 0.9
    with patch("avideo.stages.align.align_wav", return_value=fake_word_segments):
        stage = AlignStage()
        result = stage.run(workdir, config)

    assert result.slides[0].duration > 0.0, (
        "Duration must be > 0.0 when words exist (Warning 1)"
    )
    # Duration should be updated to last word end (0.9 from fake_word_segments)
    assert abs(result.slides[0].duration - 0.9) < 0.01


def test_align_record_uses_config_language_and_model(tmp_path: Path, fake_word_segments):
    """align_wav must be called with config.language and config.whisperx_model."""
    workdir = WorkdirManager(tmp_path / "workdir")
    (workdir.root / "audio" / "slide_00.wav").write_bytes(b"\x00" * 44)
    _write_voice_checkpoint(workdir, source="record", n_slides=1)

    config = _build_config(tmp_path, voice=VoiceMode.record, whisperx_model="base")
    config = RunConfig(
        bullets=config.bullets,
        duration=60,
        voice=VoiceMode.record,
        voice_id="test-voice-id",
        whisperx_model="base",
        language="en",
        workdir=tmp_path / "workdir",
    )

    from avideo.stages.align import AlignStage

    with patch("avideo.stages.align.align_wav", return_value=fake_word_segments) as mock_align:
        stage = AlignStage()
        result = stage.run(workdir, config)

    # Must pass language and model_size from config
    call_kwargs = mock_align.call_args
    assert call_kwargs.kwargs.get("language", None) == "en" or \
           (len(call_kwargs.args) > 1 and call_kwargs.args[1] == "en"), (
        "align_wav must be called with language from config"
    )
    assert call_kwargs.kwargs.get("model_size", None) == "base" or \
           (len(call_kwargs.args) > 2 and call_kwargs.args[2] == "base"), (
        "align_wav must be called with model_size from config.whisperx_model"
    )


# ---------------------------------------------------------------------------
# ALIGN-02: elevenlabs mode — no-op idempotent (elevenlabs_skip)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("elevenlabs_skip", [True])
def test_align_elevenlabs_noop(tmp_path: Path, fake_word_segments, elevenlabs_skip):
    """In elevenlabs mode, align_wav must NOT be called (ALIGN-02 no-op)."""
    workdir = WorkdirManager(tmp_path / "workdir")

    # Write voice checkpoint with elevenlabs source + populated words
    el_slides = [
        SlideTimings(
            slide_index=0,
            audio_path="audio/slide_00.mp3",
            duration=2.1,
            words=[
                WordTiming(text="hola", start=0.0, end=0.4),
                WordTiming(text="mundo", start=0.5, end=0.9),
            ],
        )
    ]
    el_timings = UnifiedTimings(source="elevenlabs", slides=el_slides)
    workdir.write_checkpoint("voice", el_timings)

    config = _build_config(tmp_path, voice=VoiceMode.elevenlabs)

    from avideo.stages.align import AlignStage

    mock_align_fn = MagicMock()
    with patch("avideo.stages.align.align_wav", mock_align_fn):
        stage = AlignStage()
        result = stage.run(workdir, config)

    # align_wav must NOT be called in elevenlabs mode
    assert not mock_align_fn.called, (
        "align_wav must NOT be called in elevenlabs mode (ALIGN-02 no-op idempotent)"
    )

    # Result must be identical to the voice checkpoint (pass-through)
    assert result.source == "elevenlabs"
    assert len(result.slides) == 1
    assert result.slides[0].audio_path == "audio/slide_00.mp3"
    assert result.slides[0].duration == pytest.approx(2.1)
    assert result.slides[0].words[0].text == "hola"


def test_align_elevenlabs_noop_direct(tmp_path: Path):
    """Directly test the -k elevenlabs_skip scenario without parametrize."""
    workdir = WorkdirManager(tmp_path / "workdir")

    el_timings = UnifiedTimings(
        source="elevenlabs",
        slides=[
            SlideTimings(
                slide_index=0,
                audio_path="audio/slide_00.mp3",
                duration=3.5,
                words=[WordTiming(text="test", start=0.0, end=0.3)],
            )
        ],
    )
    workdir.write_checkpoint("voice", el_timings)

    config = _build_config(tmp_path, voice=VoiceMode.elevenlabs)

    from avideo.stages.align import AlignStage

    mock_fn = MagicMock()
    with patch("avideo.stages.align.align_wav", mock_fn):
        stage = AlignStage()
        result = stage.run(workdir, config)

    assert not mock_fn.called, "align_wav must NOT be called for elevenlabs"
    assert result.source == "elevenlabs"
    assert result.slides[0].duration == pytest.approx(3.5)


# ---------------------------------------------------------------------------
# Mock point: tests can patch avideo.stages.align.align_wav
# ---------------------------------------------------------------------------


def test_align_wav_is_module_scope_import():
    """align_wav must be importable from avideo.stages.align at module scope.

    This ensures the mock point is at avideo.stages.align.align_wav.
    """
    import avideo.stages.align as align_mod
    assert hasattr(align_mod, "align_wav"), (
        "align_wav must be imported at module scope in align.py for test patching"
    )
