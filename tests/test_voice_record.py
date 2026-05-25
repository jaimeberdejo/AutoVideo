"""Tests for stages/voice_record.py — VOICE-03.

Covers:
  - VOICE-03a: Autodetection — if workdir/audio/slide_XX.wav exists, use it (no sounddevice call).
  - VOICE-03b: Recording — if no WAV present, mock sounddevice.rec+wait+soundfile.write.
  - VOICE-03c: Segmented script export — a file with narration text is written under workdir/audio/.
  - VOICE-03d: stage_name == "voice".

No real audio/models are used.  sounddevice and soundfile are mocked where recording would occur.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from avideo.models.config import RunConfig, VoiceMode
from avideo.models.script import ScriptOutput, SlideScript
from avideo.models.timings import SlideTimings, UnifiedTimings
from avideo.utils.workdir import WorkdirManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _build_script(slide_texts: list[str]) -> ScriptOutput:
    """Build a ScriptOutput with given narration texts."""
    return ScriptOutput(
        slides=[
            SlideScript(slide_index=i, narration=text)
            for i, text in enumerate(slide_texts)
        ],
        language="es",
    )


def _build_config(tmp_path: Path, voice: VoiceMode = VoiceMode.record) -> RunConfig:
    bullets = tmp_path / "bullets.yaml"
    bullets.write_text("title: Test\nbullets:\n  - Point 1\n", encoding="utf-8")
    return RunConfig(
        bullets=bullets,
        duration=60,
        voice=voice,
        voice_id="test-voice-id",
        workdir=tmp_path / "workdir",
    )


# ---------------------------------------------------------------------------
# VOICE-03d: stage_name == "voice"
# ---------------------------------------------------------------------------


def test_voice_record_stage_name():
    """VoiceRecordStage must have stage_name='voice' (D-12 checkpoint contract)."""
    from avideo.stages.voice_record import VoiceRecordStage

    stage = VoiceRecordStage()
    assert stage.stage_name == "voice"


# ---------------------------------------------------------------------------
# VOICE-03a: Autodetection — existing WAVs are used, sounddevice NOT called
# ---------------------------------------------------------------------------


def test_autodetect_existing_wavs(tmp_path: Path):
    """If workdir/audio/slide_XX.wav exists, use it without calling sounddevice."""
    workdir = WorkdirManager(tmp_path / "workdir")

    # Write script checkpoint with 2 slides
    script = _build_script(["Hola mundo.", "Segundo slide."])
    workdir.write_checkpoint("script", script)

    # Pre-populate the WAV files (minimal valid WAV bytes — real content not needed)
    for i in range(2):
        wav_path = workdir.root / "audio" / f"slide_{i:02d}.wav"
        wav_path.write_bytes(b"\x00" * 44)  # minimal placeholder

    config = _build_config(tmp_path)

    from avideo.stages.voice_record import VoiceRecordStage

    # sounddevice must NOT be called — patch to detect accidental calls
    with patch("avideo.stages.voice_record.sounddevice") as mock_sd:
        # sounddevice should never be reached in autodetect path
        # We also mock soundfile.info to return a sane duration
        with patch("avideo.stages.voice_record.soundfile") as mock_sf:
            mock_info = MagicMock()
            mock_info.frames = 22050  # 0.5 s at 44100 Hz
            mock_info.samplerate = 44100
            mock_sf.info.return_value = mock_info

            stage = VoiceRecordStage()
            result = stage.run(workdir, config)

    # sounddevice.rec should NOT have been called (autodetect)
    mock_sd.rec.assert_not_called()

    # Result should be UnifiedTimings(source="record") with 2 slides
    assert isinstance(result, UnifiedTimings)
    assert result.source == "record"
    assert len(result.slides) == 2

    # Check slides are populated
    for i, slide_timing in enumerate(result.slides):
        assert isinstance(slide_timing, SlideTimings)
        assert slide_timing.slide_index == i
        assert "audio" in slide_timing.audio_path
        assert f"slide_{i:02d}" in slide_timing.audio_path
        assert slide_timing.words == []  # words filled by align stage


def test_autodetect_duration_non_zero(tmp_path: Path):
    """Duration must be non-zero when the WAV exists and soundfile.info returns valid data.

    Critical guidance Warning 1: per-slide duration must NEVER be 0.0 when audio exists.
    """
    workdir = WorkdirManager(tmp_path / "workdir")
    script = _build_script(["Un slide con duración real."])
    workdir.write_checkpoint("script", script)

    wav_path = workdir.root / "audio" / "slide_00.wav"
    wav_path.write_bytes(b"\x00" * 44)

    config = _build_config(tmp_path)

    from avideo.stages.voice_record import VoiceRecordStage

    with patch("avideo.stages.voice_record.sounddevice"):
        with patch("avideo.stages.voice_record.soundfile") as mock_sf:
            mock_info = MagicMock()
            mock_info.frames = 44100  # exactly 1.0 s at 44100 Hz
            mock_info.samplerate = 44100
            mock_sf.info.return_value = mock_info

            stage = VoiceRecordStage()
            result = stage.run(workdir, config)

    assert result.slides[0].duration > 0.0, (
        "Slide duration must be > 0.0 when WAV exists — subtitle offset calculation "
        "collapses if duration is 0.0 (critical guidance Warning 1)"
    )
    assert abs(result.slides[0].duration - 1.0) < 0.01


# ---------------------------------------------------------------------------
# VOICE-03b: Recording — sounddevice.rec+wait invoked when no WAV present
# ---------------------------------------------------------------------------


def test_recording_invoked_when_no_wav(tmp_path: Path):
    """If workdir/audio/slide_XX.wav does NOT exist, recording is invoked."""
    workdir = WorkdirManager(tmp_path / "workdir")
    script = _build_script(["Slide a grabar.", "Segundo slide a grabar."])
    workdir.write_checkpoint("script", script)

    config = _build_config(tmp_path)

    from avideo.stages.voice_record import VoiceRecordStage

    # Simulate sounddevice and soundfile available (mock them)
    # Use a plain list to avoid numpy dependency in tests
    fake_audio_data = [[0.0]] * 44100  # 1s of silence (mock return)

    with patch("avideo.stages.voice_record.sounddevice") as mock_sd, \
         patch("avideo.stages.voice_record.soundfile") as mock_sf:

        mock_sd.rec.return_value = fake_audio_data
        mock_sd.wait.return_value = None
        mock_sf.write.return_value = None
        # soundfile.info is called for duration after writing
        mock_info = MagicMock()
        mock_info.frames = 22050
        mock_info.samplerate = 44100
        mock_sf.info.return_value = mock_info

        stage = VoiceRecordStage()
        result = stage.run(workdir, config)

    # sounddevice.rec should have been called once per slide (2 slides)
    assert mock_sd.rec.call_count == 2, (
        f"Expected sounddevice.rec called 2 times (one per slide), "
        f"got {mock_sd.rec.call_count}"
    )
    assert mock_sd.wait.call_count == 2

    # Result should still be UnifiedTimings(source="record")
    assert isinstance(result, UnifiedTimings)
    assert result.source == "record"
    assert len(result.slides) == 2


# ---------------------------------------------------------------------------
# VOICE-03c: Segmented script export — file with narration text is written
# ---------------------------------------------------------------------------


def test_script_export_file_created(tmp_path: Path):
    """VoiceRecordStage must write a readable script export file to workdir/audio/."""
    workdir = WorkdirManager(tmp_path / "workdir")
    narrations = ["Primera narración para el slide cero.", "Segunda narración para el slide uno."]
    script = _build_script(narrations)
    workdir.write_checkpoint("script", script)

    # Pre-populate WAVs so recording is skipped
    for i in range(2):
        wav_path = workdir.root / "audio" / f"slide_{i:02d}.wav"
        wav_path.write_bytes(b"\x00" * 44)

    config = _build_config(tmp_path)

    from avideo.stages.voice_record import VoiceRecordStage

    with patch("avideo.stages.voice_record.sounddevice"):
        with patch("avideo.stages.voice_record.soundfile") as mock_sf:
            mock_info = MagicMock()
            mock_info.frames = 22050
            mock_info.samplerate = 44100
            mock_sf.info.return_value = mock_info
            stage = VoiceRecordStage()
            result = stage.run(workdir, config)

    # A script export file should exist under workdir/audio/
    audio_dir = workdir.root / "audio"
    script_files = list(audio_dir.glob("*script*")) + list(audio_dir.glob("script_*"))
    # Also accept per-slide text files
    slide_txt_files = list(audio_dir.glob("slide_*.txt"))
    all_export_files = script_files + slide_txt_files
    assert len(all_export_files) > 0, (
        "Expected at least one script export file under workdir/audio/ "
        "(e.g. script_segments.txt or slide_XX.txt)"
    )

    # The narration text should appear in at least one of those files
    combined_text = "".join(f.read_text(encoding="utf-8") for f in all_export_files)
    for narration in narrations:
        assert narration in combined_text or narration[:20] in combined_text, (
            f"Narration text not found in script export: {narration[:30]!r}"
        )


# ---------------------------------------------------------------------------
# VOICE-03e: audio_path is relative (checkpoint portability)
# ---------------------------------------------------------------------------


def test_audio_path_relative_in_result(tmp_path: Path):
    """audio_path in SlideTimings must be relative to workdir.root (portability)."""
    workdir = WorkdirManager(tmp_path / "workdir")
    script = _build_script(["Texto del slide."])
    workdir.write_checkpoint("script", script)

    wav_path = workdir.root / "audio" / "slide_00.wav"
    wav_path.write_bytes(b"\x00" * 44)

    config = _build_config(tmp_path)

    from avideo.stages.voice_record import VoiceRecordStage

    with patch("avideo.stages.voice_record.sounddevice"):
        with patch("avideo.stages.voice_record.soundfile") as mock_sf:
            mock_info = MagicMock()
            mock_info.frames = 22050
            mock_info.samplerate = 44100
            mock_sf.info.return_value = mock_info
            stage = VoiceRecordStage()
            result = stage.run(workdir, config)

    audio_path = result.slides[0].audio_path
    # Must be a relative path (not absolute starting with /)
    assert not audio_path.startswith("/"), (
        f"audio_path must be relative for checkpoint portability, got: {audio_path!r}"
    )
    assert "audio/slide_00.wav" in audio_path or "audio\\slide_00.wav" in audio_path
