"""Wave 0 test scaffold for Phase 8 background music FFmpeg builder and
AssembleStage music integration (EXT-02, EXT-03).

All avideo imports deferred to inside test bodies (# noqa: PLC0415).

Pure builder tests (TestBuildMusicMixArgs) need no mock — build_music_mix_args()
is a pure list[str] builder with no I/O.

Stage-level tests (TestAssembleMusicPath) mock run_ffmpeg and probe_duration.

Tests are RED until:
  - Wave 1 (RunConfig fields: bg_music_path, bg_music_volume) lands
  - Wave 3 (integrations/ffmpeg.py: build_music_mix_args + assemble.py music path) lands

Covers EXT-02:
  - build_music_mix_args() emits amix=inputs=2:normalize=0 (never normalize=1)
  - Explicit volume= before amix for level control
  - sidechaincompress for music ducking under narration
  - afade for in/out fades
  - All args are a flat list[str] (shell=False invariant)
  - -c:v copy (no video re-encode)
  - -movflags +faststart

Covers EXT-03:
  - When bg_music_path is set, AssembleStage runs exactly ONE loudnorm pass
    on the mixed output (not per-narration + on mix = double normalization)
  - When bg_music_path is NOT set, existing loudnorm behavior is preserved
"""
from __future__ import annotations

import json
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Pure builder tests — TestBuildMusicMixArgs (no mock needed)
# ---------------------------------------------------------------------------


class TestBuildMusicMixArgs:
    """build_music_mix_args() returns a list[str] ffmpeg arg list for music mixing.

    These are pure builder tests: no I/O, no mocks, no ffmpeg binary required.
    """

    def _build_args(self):
        """Call build_music_mix_args with canonical test parameters."""
        from avideo.integrations.ffmpeg import build_music_mix_args  # noqa: PLC0415

        return build_music_mix_args(
            "/tmp/assembled.mp4",
            "/tmp/music.mp3",
            "/tmp/output_with_music.mp4",
            music_volume=0.12,
            fade_in_s=2.0,
            fade_out_start=40.0,
            fade_out_s=3.0,
        )

    def test_normalize_0(self):
        """amix must use normalize=0 (never default normalize=1 which drops -6 dB)."""
        args = self._build_args()
        args_str = " ".join(args)
        assert "amix=inputs=2:normalize=0" in args_str, (
            f"Expected 'amix=inputs=2:normalize=0' in music mix args; got: {args_str}"
        )

    def test_volume_before_amix(self):
        """Explicit volume= filter must appear BEFORE amix in the filter_complex string."""
        args = self._build_args()
        args_str = " ".join(args)
        assert "volume=0.12" in args_str, (
            f"Expected 'volume=0.12' in music mix args; got: {args_str}"
        )
        vol_idx = args_str.index("volume=0.12")
        amix_idx = args_str.index("amix=inputs=2:normalize=0")
        assert vol_idx < amix_idx, (
            "volume= filter must appear BEFORE amix in filter_complex (levels set before mix)"
        )

    def test_sidechaincompress_present(self):
        """sidechaincompress must be present for music ducking under narration."""
        args = self._build_args()
        args_str = " ".join(args)
        assert "sidechaincompress" in args_str, (
            f"Expected 'sidechaincompress' in music mix args for ducking; got: {args_str}"
        )

    def test_afade_present(self):
        """afade filter must be present for music fade-in and fade-out."""
        args = self._build_args()
        args_str = " ".join(args)
        assert "afade" in args_str, (
            f"Expected 'afade' in music mix args for fade in/out; got: {args_str}"
        )

    def test_no_shell_true(self):
        """build_music_mix_args must return a list[str] — never a single shell string."""
        args = self._build_args()
        assert isinstance(args, list), (
            f"build_music_mix_args must return list[str], got {type(args).__name__}"
        )
        assert all(isinstance(a, str) for a in args), (
            "All elements in the returned list must be str (no None, Path, or int)"
        )

    def test_video_stream_copied(self):
        """-c:v copy must be present (no video re-encode in music mix pass)."""
        args = self._build_args()
        assert "-c:v" in args, "Args must contain '-c:v'"
        idx = args.index("-c:v")
        assert args[idx + 1] == "copy", (
            f"'-c:v' must be followed by 'copy' (no video re-encode); "
            f"got '{args[idx + 1]}'"
        )

    def test_movflags_faststart(self):
        """+faststart must be present for streaming-friendly MP4 output."""
        args = self._build_args()
        args_str = " ".join(args)
        assert "+faststart" in args_str, (
            f"Expected '+faststart' in music mix args; got: {args_str}"
        )


# ---------------------------------------------------------------------------
# Stage-level tests — TestAssembleMusicPath (mocked run_ffmpeg + probe_duration)
# ---------------------------------------------------------------------------


def _write_stage_checkpoints(workdir, tmp_path):
    """Write minimal slides.json and voice.json checkpoints for AssembleStage."""
    from avideo.models.slides import SlidesOutput  # noqa: PLC0415
    from avideo.models.timings import UnifiedTimings, SlideTimings, WordTiming  # noqa: PLC0415

    slide_path = workdir.root / "slides" / "slide_00.png"
    slide_path.parent.mkdir(parents=True, exist_ok=True)
    slide_path.write_bytes(b"\x89PNG\r\n\x1a\n")

    audio_path = workdir.root / "audio" / "audio_00.mp3"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"\xff\xe3")

    slides_out = SlidesOutput(png_paths=[str(slide_path)], mode="auto")
    workdir.write_checkpoint("slides", slides_out)

    voice_out = UnifiedTimings(
        source="elevenlabs",
        slides=[SlideTimings(
            slide_index=0,
            audio_path=str(audio_path),
            duration=10.0,
            words=[WordTiming(text="test", start=0.0, end=0.5)],
        )],
    )
    workdir.write_checkpoint("voice", voice_out)

    return slide_path, audio_path


def _fake_ffmpeg_factory(loudnorm_pass1_stderr, write_output=True):
    """Return a fake run_ffmpeg side_effect and a call-tracker list."""
    call_args_log = []

    pass1_proc = types.SimpleNamespace(
        returncode=0,
        stdout="",
        stderr=loudnorm_pass1_stderr,
    )
    pass2_proc = types.SimpleNamespace(
        returncode=0,
        stdout="",
        stderr=(
            '{\n'
            '    "input_i" : "-16.09",\n'
            '    "input_tp" : "-1.50",\n'
            '    "input_lra" : "0.50",\n'
            '    "input_thresh" : "-26.09",\n'
            '    "output_i" : "-16.01",\n'
            '    "output_tp" : "-1.50",\n'
            '    "output_lra" : "0.50",\n'
            '    "output_thresh" : "-26.01",\n'
            '    "normalization_type" : "linear",\n'
            '    "target_offset" : "0.09"\n'
            '}\n'
        ),
    )

    call_count = [0]

    def fake_run_ffmpeg(args):
        n = call_count[0]
        call_count[0] += 1
        call_args_log.append(list(args))
        # call 0: main assembly encode — write fake output file
        if n == 0 and write_output:
            out_arg = args[-1]
            Path(out_arg).write_bytes(b"fake mp4")
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")
        # call 1: loudnorm pass-1 measure
        elif n == 1:
            return pass1_proc
        # call 2: loudnorm pass-2 apply — write normalized file
        elif n == 2:
            out_arg = args[-1]
            Path(out_arg).write_bytes(b"fake normalized mp4")
            return pass2_proc
        # call 3: music mix pass — write music-mixed file
        elif n == 3 and write_output:
            out_arg = args[-1]
            Path(out_arg).write_bytes(b"fake music mp4")
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    return fake_run_ffmpeg, call_args_log


_LOUDNORM_PASS1_STDERR = (
    "ffmpeg version 8.0.1\n"
    "[Parsed_loudnorm_0 @ 0x...]\n"
    "{\n"
    '    "input_i" : "-22.01",\n'
    '    "input_tp" : "-20.91",\n'
    '    "input_lra" : "0.70",\n'
    '    "input_thresh" : "-32.01",\n'
    '    "output_i" : "-15.74",\n'
    '    "output_tp" : "-14.60",\n'
    '    "output_lra" : "0.50",\n'
    '    "output_thresh" : "-25.74",\n'
    '    "normalization_type" : "dynamic",\n'
    '    "target_offset" : "-0.26"\n'
    "}\n"
)


class TestAssembleMusicPath:
    """AssembleStage routes to build_music_mix_args when config.bg_music_path is set."""

    def test_assemble_triggers_music_mix(self, tmp_path):
        """AssembleStage must call build_music_mix_args (or run_ffmpeg with amix) when bg_music_path is set."""
        from avideo.models.config import RunConfig  # noqa: PLC0415
        from avideo.stages.assemble import AssembleStage  # noqa: PLC0415
        from avideo.utils.workdir import WorkdirManager  # noqa: PLC0415

        workdir = WorkdirManager(tmp_path / "workdir")
        _write_stage_checkpoints(workdir, tmp_path)

        # Create a fake music file
        music_path = tmp_path / "music.mp3"
        music_path.write_bytes(b"\xff\xe3")

        bullets = tmp_path / "bullets.yaml"
        bullets.write_text("title: T\nbullets:\n  - B\n", encoding="utf-8")
        config = RunConfig(
            bullets=bullets,
            duration=10,
            workdir=workdir.root,
            bg_music_path=music_path,
            bg_music_volume=0.12,
        )

        fake_run_ffmpeg, call_args_log = _fake_ffmpeg_factory(_LOUDNORM_PASS1_STDERR)

        with patch("avideo.integrations.ffmpeg.subprocess.run") as mock_subproc, \
             patch("avideo.stages.assemble.run_ffmpeg", side_effect=fake_run_ffmpeg), \
             patch("avideo.stages.assemble.probe_duration", return_value=10.0):
            mock_subproc.return_value = types.SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"format": {"duration": "10.0"}}),
                stderr="",
            )
            AssembleStage().run(workdir, config)

        # Check that at least one run_ffmpeg call contained "amix" (music mix was triggered)
        all_args_flat = [" ".join(args) for args in call_args_log]
        assert any("amix" in a for a in all_args_flat), (
            "When bg_music_path is set, AssembleStage must call run_ffmpeg with amix "
            f"(music mix pass). Calls recorded: {all_args_flat}"
        )

    def test_single_loudnorm_with_music(self, tmp_path):
        """AssembleStage must apply loudnorm exactly ONCE on final mixed output (not twice)."""
        from avideo.models.config import RunConfig  # noqa: PLC0415
        from avideo.stages.assemble import AssembleStage  # noqa: PLC0415
        from avideo.utils.workdir import WorkdirManager  # noqa: PLC0415

        workdir = WorkdirManager(tmp_path / "workdir")
        _write_stage_checkpoints(workdir, tmp_path)

        music_path = tmp_path / "music.mp3"
        music_path.write_bytes(b"\xff\xe3")

        bullets = tmp_path / "bullets.yaml"
        bullets.write_text("title: T\nbullets:\n  - B\n", encoding="utf-8")
        config = RunConfig(
            bullets=bullets,
            duration=10,
            workdir=workdir.root,
            bg_music_path=music_path,
            bg_music_volume=0.12,
        )

        fake_run_ffmpeg, call_args_log = _fake_ffmpeg_factory(_LOUDNORM_PASS1_STDERR)

        with patch("avideo.integrations.ffmpeg.subprocess.run") as mock_subproc, \
             patch("avideo.stages.assemble.run_ffmpeg", side_effect=fake_run_ffmpeg), \
             patch("avideo.stages.assemble.probe_duration", return_value=10.0):
            mock_subproc.return_value = types.SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"format": {"duration": "10.0"}}),
                stderr="",
            )
            AssembleStage().run(workdir, config)

        # Count how many run_ffmpeg calls contained "loudnorm"
        loudnorm_calls = [
            args for args in call_args_log
            if "loudnorm" in " ".join(args)
        ]
        assert len(loudnorm_calls) == 1, (
            f"With bg_music_path set, loudnorm must run exactly ONCE (single pass on "
            f"final mix); found {len(loudnorm_calls)} loudnorm calls. "
            f"Double normalization causes pumping artifacts. Calls: {loudnorm_calls}"
        )

    def test_loudnorm_without_music(self, tmp_path, loudnorm_pass1_stderr):
        """Without bg_music_path, existing loudnorm behavior must be preserved."""
        from avideo.models.config import RunConfig  # noqa: PLC0415
        from avideo.stages.assemble import AssembleStage  # noqa: PLC0415
        from avideo.utils.workdir import WorkdirManager  # noqa: PLC0415

        workdir = WorkdirManager(tmp_path / "workdir")
        _write_stage_checkpoints(workdir, tmp_path)

        bullets = tmp_path / "bullets.yaml"
        bullets.write_text("title: T\nbullets:\n  - B\n", encoding="utf-8")
        config = RunConfig(bullets=bullets, duration=10, workdir=workdir.root)

        fake_run_ffmpeg, call_args_log = _fake_ffmpeg_factory(loudnorm_pass1_stderr)

        with patch("avideo.integrations.ffmpeg.subprocess.run") as mock_subproc, \
             patch("avideo.stages.assemble.run_ffmpeg", side_effect=fake_run_ffmpeg), \
             patch("avideo.stages.assemble.probe_duration", return_value=10.0):
            mock_subproc.return_value = types.SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"format": {"duration": "10.0"}}),
                stderr="",
            )
            AssembleStage().run(workdir, config)

        # Without music, loudnorm must still run (existing behavior preserved)
        loudnorm_calls = [
            args for args in call_args_log
            if "loudnorm" in " ".join(args)
        ]
        assert len(loudnorm_calls) >= 1, (
            "Without bg_music_path, loudnorm must still run at least once "
            "(existing EBU R128 normalization behavior must not be broken)"
        )
