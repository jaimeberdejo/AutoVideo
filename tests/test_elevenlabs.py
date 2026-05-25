"""Tests for integrations/elevenlabs.py — VOICE-02.

Covers:
  - is_strictly_increasing: pure function, all edge cases
  - synthesize_slide: success on first try with increasing timestamps
  - synthesize_slide: retry logic — fails after 3 attempts, raises VoiceTimestampError
  - synthesize_slide: succeeds on 2nd attempt (flat then increasing)
  - Import safety: importing the module must NOT require ELEVENLABS_API_KEY
"""
from __future__ import annotations

import base64
import types
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# is_strictly_increasing — pure unit tests (no mocks needed)
# ---------------------------------------------------------------------------


class TestIsStrictlyIncreasing:
    """Pure function: all(b > a for a, b in zip(xs, xs[1:]))."""

    def test_increasing_returns_true(self):
        from avideo.integrations.elevenlabs import is_strictly_increasing

        assert is_strictly_increasing([0.0, 0.1, 0.25]) is True

    def test_equal_returns_false(self):
        from avideo.integrations.elevenlabs import is_strictly_increasing

        assert is_strictly_increasing([0.0, 0.1, 0.1]) is False

    def test_decreasing_returns_false(self):
        from avideo.integrations.elevenlabs import is_strictly_increasing

        assert is_strictly_increasing([0.2, 0.1]) is False

    def test_empty_returns_true(self):
        """Empty list: vacuously true (no pair to violate)."""
        from avideo.integrations.elevenlabs import is_strictly_increasing

        assert is_strictly_increasing([]) is True

    def test_single_element_returns_true(self):
        """Single element: no pair to violate."""
        from avideo.integrations.elevenlabs import is_strictly_increasing

        assert is_strictly_increasing([0.0]) is True

    def test_large_increasing_sequence(self):
        from avideo.integrations.elevenlabs import is_strictly_increasing

        xs = [i * 0.1 for i in range(100)]
        assert is_strictly_increasing(xs) is True

    def test_two_elements_equal(self):
        from avideo.integrations.elevenlabs import is_strictly_increasing

        assert is_strictly_increasing([1.0, 1.0]) is False


# ---------------------------------------------------------------------------
# VoiceTimestampError existence
# ---------------------------------------------------------------------------


def test_voice_timestamp_error_exists():
    from avideo.integrations.elevenlabs import VoiceTimestampError

    exc = VoiceTimestampError("test message")
    assert isinstance(exc, Exception)
    assert "test message" in str(exc)


# ---------------------------------------------------------------------------
# Import safety — no API key required
# ---------------------------------------------------------------------------


def test_import_does_not_require_api_key(monkeypatch):
    """Importing the module must NOT require ELEVENLABS_API_KEY."""
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    import importlib

    import avideo.integrations.elevenlabs as mod

    importlib.reload(mod)  # force re-evaluation with key removed from env
    # If we got here without error, the lazy client contract is satisfied.


# ---------------------------------------------------------------------------
# synthesize_slide helpers
# ---------------------------------------------------------------------------


def _make_response(starts, ends, characters, audio_bytes=b"\xff\xe3\x10\x00"):
    """Build a fake ElevenLabs response namespace."""
    alignment = types.SimpleNamespace(
        character_start_times_seconds=starts,
        character_end_times_seconds=ends,
        characters=characters,
    )
    return types.SimpleNamespace(
        audio_base64=base64.b64encode(audio_bytes).decode("utf-8"),
        alignment=alignment,
    )


# ---------------------------------------------------------------------------
# synthesize_slide — success path
# ---------------------------------------------------------------------------


class TestSynthesizeSlideSuccess:
    """synthesize_slide writes mp3 and returns SlideTimings on success."""

    def test_writes_mp3_and_returns_slide_timings(self, tmp_path, mocker):
        from avideo.integrations.elevenlabs import synthesize_slide
        from avideo.models.timings import SlideTimings

        resp = _make_response(
            starts=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9],
            ends=  [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
            characters=list("hola mundo"),
        )
        mock_client = mocker.MagicMock()
        mock_client.text_to_speech.convert_with_timestamps.return_value = resp
        mocker.patch("avideo.integrations.elevenlabs._get_client", return_value=mock_client)

        out_path = tmp_path / "slide_00.mp3"
        result = synthesize_slide(
            text="hola mundo",
            slide_index=0,
            voice_id="test-voice",
            out_path=out_path,
        )

        assert out_path.exists(), "mp3 file must be written"
        assert isinstance(result, SlideTimings)
        assert result.slide_index == 0
        assert result.duration == pytest.approx(1.0)
        # words must be populated (critical guidance: not empty on elevenlabs path)
        assert len(result.words) > 0, "words must be populated from char timestamps"

    def test_sdk_called_once_on_success(self, tmp_path, mocker):
        from avideo.integrations.elevenlabs import synthesize_slide

        resp = _make_response(
            starts=[0.0, 0.05, 0.10],
            ends=  [0.05, 0.10, 0.15],
            characters=["a", "b", "c"],
        )
        mock_client = mocker.MagicMock()
        mock_client.text_to_speech.convert_with_timestamps.return_value = resp
        mocker.patch("avideo.integrations.elevenlabs._get_client", return_value=mock_client)

        out_path = tmp_path / "slide_00.mp3"
        synthesize_slide(text="abc", slide_index=0, voice_id="v", out_path=out_path)

        assert mock_client.text_to_speech.convert_with_timestamps.call_count == 1

    def test_duration_is_last_end_time(self, tmp_path, mocker):
        from avideo.integrations.elevenlabs import synthesize_slide

        resp = _make_response(
            starts=[0.0, 0.5],
            ends=  [0.5, 2.3],
            characters=["x", "y"],
        )
        mock_client = mocker.MagicMock()
        mock_client.text_to_speech.convert_with_timestamps.return_value = resp
        mocker.patch("avideo.integrations.elevenlabs._get_client", return_value=mock_client)

        result = synthesize_slide(
            text="xy", slide_index=1, voice_id="v", out_path=tmp_path / "s.mp3"
        )
        assert result.duration == pytest.approx(2.3)

    def test_audio_path_is_relative(self, tmp_path, mocker):
        """audio_path stored as string (relative or absolute — whichever the impl chooses)."""
        from avideo.integrations.elevenlabs import synthesize_slide

        resp = _make_response(starts=[0.0, 0.1], ends=[0.1, 0.2], characters=["a", "b"])
        mock_client = mocker.MagicMock()
        mock_client.text_to_speech.convert_with_timestamps.return_value = resp
        mocker.patch("avideo.integrations.elevenlabs._get_client", return_value=mock_client)

        out_path = tmp_path / "slide_00.mp3"
        result = synthesize_slide(text="ab", slide_index=0, voice_id="v", out_path=out_path)
        assert result.audio_path == str(out_path)


# ---------------------------------------------------------------------------
# synthesize_slide — retry on non-increasing timestamps
# ---------------------------------------------------------------------------


class TestSynthesizeSlideRetry:
    """Retry behaviour when timestamps are degenerate/non-increasing."""

    def test_always_flat_raises_after_3_attempts(self, tmp_path, mocker):
        """If all 3 attempts return flat timestamps, VoiceTimestampError is raised."""
        from avideo.integrations.elevenlabs import VoiceTimestampError, synthesize_slide

        flat_resp = _make_response(
            starts=[0.0, 0.0, 0.0],
            ends=  [0.1, 0.1, 0.1],
            characters=["a", "b", "c"],
        )
        mock_client = mocker.MagicMock()
        mock_client.text_to_speech.convert_with_timestamps.return_value = flat_resp
        mocker.patch("avideo.integrations.elevenlabs._get_client", return_value=mock_client)

        with pytest.raises(VoiceTimestampError, match=r"(?i)(timestamp|degenerate|retry|attempt)"):
            synthesize_slide(
                text="abc", slide_index=0, voice_id="v", out_path=tmp_path / "s.mp3"
            )

        assert mock_client.text_to_speech.convert_with_timestamps.call_count == 3

    def test_succeeds_on_second_attempt(self, tmp_path, mocker):
        """If first attempt is flat but second is increasing, succeeds in 2 calls."""
        from avideo.integrations.elevenlabs import synthesize_slide

        flat_resp = _make_response(
            starts=[0.0, 0.0, 0.0],
            ends=  [0.1, 0.1, 0.1],
            characters=["a", "b", "c"],
        )
        good_resp = _make_response(
            starts=[0.0, 0.1, 0.2],
            ends=  [0.1, 0.2, 0.3],
            characters=["a", "b", "c"],
        )
        mock_client = mocker.MagicMock()
        mock_client.text_to_speech.convert_with_timestamps.side_effect = [flat_resp, good_resp]
        mocker.patch("avideo.integrations.elevenlabs._get_client", return_value=mock_client)

        result = synthesize_slide(
            text="abc", slide_index=0, voice_id="v", out_path=tmp_path / "s.mp3"
        )

        assert mock_client.text_to_speech.convert_with_timestamps.call_count == 2
        assert result.duration == pytest.approx(0.3)

    def test_retry_is_only_for_timestamps_not_network(self, tmp_path, mocker):
        """Network errors from the SDK should propagate immediately (no retry≤3 wrap)."""
        from avideo.integrations.elevenlabs import synthesize_slide

        mock_client = mocker.MagicMock()
        mock_client.text_to_speech.convert_with_timestamps.side_effect = ConnectionError("network")
        mocker.patch("avideo.integrations.elevenlabs._get_client", return_value=mock_client)

        with pytest.raises(ConnectionError):
            synthesize_slide(
                text="abc", slide_index=0, voice_id="v", out_path=tmp_path / "s.mp3"
            )

        # Must NOT have retried the network error 3 times
        assert mock_client.text_to_speech.convert_with_timestamps.call_count == 1


# ---------------------------------------------------------------------------
# synthesize_slide — uses seconds fields, NOT ms fields (Pitfall 1)
# ---------------------------------------------------------------------------


def test_synthesize_slide_reads_seconds_not_ms(tmp_path, mocker):
    """Ensures the integration reads character_start_times_seconds (not _ms)."""
    import avideo.integrations.elevenlabs as mod

    # Confirm the source code references the correct field name
    import inspect

    source = inspect.getsource(mod)
    assert "character_start_times_seconds" in source, (
        "Integration must read character_start_times_seconds (SECONDS), not _ms fields"
    )
    assert "character_start_times_ms" not in source, (
        "Integration must NOT reference the obsolete _ms field (SDK 1.x)"
    )
    assert "character_durations_ms" not in source, (
        "Integration must NOT reference the obsolete _ms field (SDK 1.x)"
    )
