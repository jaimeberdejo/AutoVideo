"""Wave 0 test scaffold for Phase 8 audio enhancement (VOZ-03).

All avideo imports deferred to inside test bodies (# noqa: PLC0415).
Tests are RED until utils/audio_enhance.py lands (Wave 2b).

Covers VOZ-03:
  - enhance_audio() calls run_ffmpeg with the correct filter chain
    (afftdn=nr=6:nf=-25 + loudnorm=I=-16:TP=-1.5:LRA=11, comma-joined)
  - Non-destructive: in_path is never modified; out_path is written by ffmpeg
  - shell=True is NEVER used (subprocess security invariant)
  - Filter order is fixed: afftdn before loudnorm (denoise before normalize)

Mock seam: patch("avideo.utils.audio_enhance.run_ffmpeg")
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import call, patch

import pytest


class TestEnhanceAudio:
    """enhance_audio(in_path, out_path) wraps run_ffmpeg with denoise+loudnorm filter."""

    def test_enhance_calls_run_ffmpeg(self, tmp_path):
        """enhance_audio must call run_ffmpeg once with the correct filter string."""
        with patch("avideo.utils.audio_enhance.run_ffmpeg") as mock_run:
            from avideo.utils.audio_enhance import enhance_audio  # noqa: PLC0415

            enhance_audio(Path("/tmp/in.wav"), Path("/tmp/out.wav"))

        mock_run.assert_called_once()
        args_str = " ".join(mock_run.call_args[0][0])
        assert "afftdn=nr=6:nf=-25" in args_str, (
            f"Expected 'afftdn=nr=6:nf=-25' in ffmpeg args; got: {args_str}"
        )
        assert "loudnorm=I=-16:TP=-1.5:LRA=11" in args_str, (
            f"Expected 'loudnorm=I=-16:TP=-1.5:LRA=11' in ffmpeg args; got: {args_str}"
        )

    def test_nondestructive(self, tmp_path):
        """enhance_audio must NOT modify the original in_path file."""
        in_path = tmp_path / "in.wav"
        out_path = tmp_path / "out.wav"
        in_path.write_bytes(b"fake audio content")

        with patch("avideo.utils.audio_enhance.run_ffmpeg"):
            from avideo.utils.audio_enhance import enhance_audio  # noqa: PLC0415

            enhance_audio(in_path, out_path)

        # run_ffmpeg is mocked — it does NOT write out_path
        assert not out_path.exists(), (
            "out_path must not exist when run_ffmpeg is mocked (it writes the file)"
        )
        # Original in_path must be untouched
        assert in_path.read_bytes() == b"fake audio content", (
            "in_path must not be modified by enhance_audio (non-destructive)"
        )

    def test_filter_chain_order(self, tmp_path):
        """Filter chain must be 'afftdn=nr=6:nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11' in that order."""
        with patch("avideo.utils.audio_enhance.run_ffmpeg") as mock_run:
            from avideo.utils.audio_enhance import enhance_audio  # noqa: PLC0415

            enhance_audio(Path("/tmp/in.wav"), Path("/tmp/out.wav"))

        call_args_list = mock_run.call_args[0][0]
        args_str = " ".join(call_args_list)
        expected_filter = "afftdn=nr=6:nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11"
        assert expected_filter in args_str, (
            f"Expected combined filter '{expected_filter}' as a single -af value; "
            f"got: {args_str}"
        )

    def test_no_shell_true(self, tmp_path):
        """enhance_audio must pass a list to run_ffmpeg (never a string with shell=True)."""
        with patch("avideo.utils.audio_enhance.run_ffmpeg") as mock_run:
            from avideo.utils.audio_enhance import enhance_audio  # noqa: PLC0415

            enhance_audio(Path("/tmp/in.wav"), Path("/tmp/out.wav"))

        actual_args = mock_run.call_args[0][0]
        assert isinstance(actual_args, list), (
            f"run_ffmpeg must be called with a list[str], not a string (shell=True risk); "
            f"got: {type(actual_args).__name__}"
        )
