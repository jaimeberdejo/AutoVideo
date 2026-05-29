"""RED tests for voice helpers in avideo.ui.pipeline_ops.

These tests FAIL with ImportError/AttributeError until Plan 02 adds
rerun_voice(), write_uploaded_audio(), and audio_gate_ready() to
src/avideo/ui/pipeline_ops.py.  They define the exact contracts those
helpers must satisfy before any implementation is written.

Coverage:
  TestRerunVoice:
    - rerun_voice calls invalidate_downstream("voice") exactly once
    - rerun_voice calls run_stage exactly once with a VoiceStage instance
    - rerun_voice deletes the voice done-marker before calling run_stage

  TestWriteUploadedAudio:
    - write_uploaded_audio writes bytes to workdir/audio/<filename>
    - write_uploaded_audio rejects path-traversal filenames with ".."
    - write_uploaded_audio rejects filenames containing "/"
    - write_uploaded_audio rejects filenames containing "\\"

  TestAudioGateReady:
    - audio_gate_ready returns False when audio files are missing
    - audio_gate_ready returns False when voice.json is missing
    - audio_gate_ready returns False when every SlideTimings.words is empty
    - audio_gate_ready returns True when all conditions are met

All imports of avideo.ui.pipeline_ops are DEFERRED inside each test body
(same pattern as tests/test_pipeline_ops.py), so this file collects cleanly
even before pipeline_ops.py has the new helpers (RED phase).

Threat model compliance:
    T-12-01-01 (Tampering): write_uploaded_audio must raise ValueError on
    "../evil.wav", "sub/evil.wav", "sub\\evil.wav" — tests enforce this.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Model imports (modules already exist — top-level import is fine)
# ---------------------------------------------------------------------------
from avideo.models.config import RunConfig, VoiceMode
from avideo.models.timings import SlideTimings, UnifiedTimings, WordTiming
from avideo.utils.workdir import WorkdirManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_config(tmp_path: Path) -> RunConfig:
    """Construct a RunConfig via model_construct to avoid env/file validation."""
    bullets = tmp_path / "b.yaml"
    bullets.write_text("title: T\nbullets:\n  - B\n", encoding="utf-8")
    return RunConfig.model_construct(bullets=bullets, duration=60)


def _unified_timings_with_words(n_slides: int) -> UnifiedTimings:
    """Return a UnifiedTimings with valid word-level data for n_slides."""
    return UnifiedTimings(
        source="elevenlabs",
        slides=[
            SlideTimings(
                slide_index=i,
                audio_path=f"audio/slide_{i:02d}.mp3",
                duration=2.5,
                words=[WordTiming(text="hola", start=0.0, end=0.5)],
            )
            for i in range(n_slides)
        ],
    )


def _unified_timings_empty_words(n_slides: int) -> UnifiedTimings:
    """Return a UnifiedTimings where every SlideTimings.words is empty."""
    return UnifiedTimings(
        source="elevenlabs",
        slides=[
            SlideTimings(
                slide_index=i,
                audio_path=f"audio/slide_{i:02d}.mp3",
                duration=2.5,
                words=[],
            )
            for i in range(n_slides)
        ],
    )


# ---------------------------------------------------------------------------
# Class 1: TestRerunVoice
# ---------------------------------------------------------------------------


class TestRerunVoice:
    """Tests for rerun_voice() — single-stage re-run wrapper for voice."""

    def test_rerun_voice_calls_invalidate_downstream_voice(
        self,
        tmp_path: Path,
        mocker,
    ) -> None:
        """rerun_voice(wm, config) calls wm.invalidate_downstream("voice") exactly once.

        Patch run_stage at avideo.ui.pipeline_ops.run_stage and
        wm.invalidate_downstream via mocker.patch.object.
        """
        from avideo.ui.pipeline_ops import rerun_voice  # noqa: PLC0415

        wm = WorkdirManager(tmp_path / "workdir")
        config = _minimal_config(tmp_path)

        mocker.patch("avideo.ui.pipeline_ops.run_stage")
        mock_invalidate = mocker.patch.object(wm, "invalidate_downstream")

        rerun_voice(wm, config)

        mock_invalidate.assert_called_once_with("voice")

    def test_rerun_voice_launches_voice_stage(
        self,
        tmp_path: Path,
        mocker,
    ) -> None:
        """rerun_voice(wm, config) calls run_stage exactly once with a VoiceStage instance."""
        from avideo.stages.voice import VoiceStage  # noqa: PLC0415
        from avideo.ui.pipeline_ops import rerun_voice  # noqa: PLC0415

        wm = WorkdirManager(tmp_path / "workdir")
        config = _minimal_config(tmp_path)

        mock_run_stage = mocker.patch("avideo.ui.pipeline_ops.run_stage")
        mocker.patch.object(wm, "invalidate_downstream")

        rerun_voice(wm, config)

        mock_run_stage.assert_called_once()
        call_args = mock_run_stage.call_args[0]
        assert isinstance(call_args[0], VoiceStage), (
            f"Expected run_stage first arg to be a VoiceStage, got {type(call_args[0])}"
        )

    def test_rerun_voice_deletes_voice_done_marker(
        self,
        tmp_path: Path,
        mocker,
    ) -> None:
        """rerun_voice deletes the voice done-marker before run_stage is invoked.

        Touch workdir/.voice.done before calling rerun_voice (with run_stage
        mocked).  After the call the marker file must NOT exist.
        """
        from avideo.ui.pipeline_ops import rerun_voice  # noqa: PLC0415

        wm = WorkdirManager(tmp_path / "workdir")
        config = _minimal_config(tmp_path)

        # Pre-condition: marker exists
        wm.done_marker("voice").touch()
        assert wm.done_marker("voice").exists(), "Pre-condition: marker must exist"

        mocker.patch("avideo.ui.pipeline_ops.run_stage")
        mocker.patch.object(wm, "invalidate_downstream")

        rerun_voice(wm, config)

        assert not wm.done_marker("voice").exists(), (
            "Voice done-marker must be deleted by rerun_voice"
        )


# ---------------------------------------------------------------------------
# Class 2: TestWriteUploadedAudio
# ---------------------------------------------------------------------------


class TestWriteUploadedAudio:
    """Tests for write_uploaded_audio() — path-traversal-safe audio upload."""

    def test_write_uploaded_audio_creates_file_in_audio_dir(
        self,
        tmp_path: Path,
    ) -> None:
        """write_uploaded_audio(wm, "slide_00.mp3", b"AUDIO") writes bytes to
        workdir/audio/slide_00.mp3 and returns that Path.

        No mocking needed — real filesystem write.
        """
        from avideo.ui.pipeline_ops import write_uploaded_audio  # noqa: PLC0415

        wm = WorkdirManager(tmp_path / "workdir")
        data = b"AUDIO\x00data"

        result = write_uploaded_audio(wm, "slide_00.mp3", data)

        expected = wm.root / "audio" / "slide_00.mp3"
        assert result == expected, (
            f"Expected returned path {expected}, got {result}"
        )
        assert expected.read_bytes() == data, (
            "File contents must match the uploaded bytes"
        )

    def test_write_uploaded_audio_rejects_path_traversal_dotdot(
        self,
        tmp_path: Path,
    ) -> None:
        """write_uploaded_audio(wm, '../evil.wav', b'') raises ValueError.

        Path traversal via '..' must be rejected (T-12-01-01).
        """
        from avideo.ui.pipeline_ops import write_uploaded_audio  # noqa: PLC0415

        wm = WorkdirManager(tmp_path / "workdir")

        with pytest.raises(ValueError):
            write_uploaded_audio(wm, "../evil.wav", b"")

    def test_write_uploaded_audio_rejects_path_traversal_slash(
        self,
        tmp_path: Path,
    ) -> None:
        """write_uploaded_audio(wm, 'sub/evil.wav', b'') raises ValueError.

        Filenames containing '/' must be rejected (T-12-01-01).
        """
        from avideo.ui.pipeline_ops import write_uploaded_audio  # noqa: PLC0415

        wm = WorkdirManager(tmp_path / "workdir")

        with pytest.raises(ValueError):
            write_uploaded_audio(wm, "sub/evil.wav", b"")

    def test_write_uploaded_audio_rejects_backslash(
        self,
        tmp_path: Path,
    ) -> None:
        """write_uploaded_audio(wm, 'sub\\\\evil.wav', b'') raises ValueError.

        Filenames containing '\\\\' must be rejected (T-12-01-01).
        """
        from avideo.ui.pipeline_ops import write_uploaded_audio  # noqa: PLC0415

        wm = WorkdirManager(tmp_path / "workdir")

        with pytest.raises(ValueError):
            write_uploaded_audio(wm, "sub\\evil.wav", b"")


# ---------------------------------------------------------------------------
# Class 3: TestAudioGateReady
# ---------------------------------------------------------------------------


class TestAudioGateReady:
    """Tests for audio_gate_ready() — gate that checks audio + timings validity."""

    def test_audio_gate_ready_false_when_audio_missing(
        self,
        tmp_path: Path,
    ) -> None:
        """With n_slides=2 and no audio files on disk, audio_gate_ready(wm, 2) returns False."""
        from avideo.ui.pipeline_ops import audio_gate_ready  # noqa: PLC0415

        wm = WorkdirManager(tmp_path / "workdir")

        result = audio_gate_ready(wm, 2)

        assert result is False, "Gate must be False when no audio files exist"

    def test_audio_gate_ready_false_when_timings_missing(
        self,
        tmp_path: Path,
    ) -> None:
        """Gate is False when audio files exist but voice.json is absent."""
        from avideo.ui.pipeline_ops import audio_gate_ready  # noqa: PLC0415

        wm = WorkdirManager(tmp_path / "workdir")
        # Create audio files but no timings
        (wm.root / "audio" / "slide_00.mp3").write_bytes(b"MP3")
        (wm.root / "audio" / "slide_01.mp3").write_bytes(b"MP3")

        result = audio_gate_ready(wm, 2)

        assert result is False, "Gate must be False when voice.json is missing"

    def test_audio_gate_ready_false_when_words_empty(
        self,
        tmp_path: Path,
    ) -> None:
        """Gate is False when voice.json exists but every SlideTimings.words is empty."""
        from avideo.ui.pipeline_ops import audio_gate_ready  # noqa: PLC0415

        wm = WorkdirManager(tmp_path / "workdir")
        # Create audio files
        (wm.root / "audio" / "slide_00.mp3").write_bytes(b"MP3")
        (wm.root / "audio" / "slide_01.mp3").write_bytes(b"MP3")
        # Write timings with empty words
        timings = _unified_timings_empty_words(2)
        wm.write_checkpoint("voice", timings)

        result = audio_gate_ready(wm, 2)

        assert result is False, (
            "Gate must be False when SlideTimings.words is empty for any slide"
        )

    def test_audio_gate_ready_true_when_all_conditions_met(
        self,
        tmp_path: Path,
    ) -> None:
        """Gate is True when all audio files exist AND voice.json has valid word-level data."""
        from avideo.ui.pipeline_ops import audio_gate_ready  # noqa: PLC0415

        wm = WorkdirManager(tmp_path / "workdir")
        # Create audio files
        (wm.root / "audio" / "slide_00.mp3").write_bytes(b"MP3")
        (wm.root / "audio" / "slide_01.mp3").write_bytes(b"MP3")
        # Write timings with valid word data
        timings = _unified_timings_with_words(2)
        wm.write_checkpoint("voice", timings)

        result = audio_gate_ready(wm, 2)

        assert result is True, (
            "Gate must be True when all audio files exist and timings has word-level data"
        )
