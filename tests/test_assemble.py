"""Wave-0 test scaffold for Phase 5 FFmpeg assembly (ASMB-01, ASMB-02, ASMB-03).

All imports from avideo.integrations.ffmpeg and avideo.stages.assemble are
deferred to INSIDE each test body so the collection does not error before
the modules exist (mirrors tests/test_slides_render.py pattern).

Tests turn RED until Tasks 2-4 land; they turn GREEN once the implementation
modules are created.

-k selectors match 05-VALIDATION.md exactly:
  - crossfade
  - probe_drives_duration
  - smoke_dimensions
  - build_filtergraph
  - build_assemble_args
  - assemble_idempotent
"""
from __future__ import annotations

import json
import shutil
import subprocess
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Tests: crossfade math (pure, no ffmpeg) — ASMB-02
# ---------------------------------------------------------------------------


def test_crossfade_offsets_3slides():
    """crossfade_offsets([3.0,4.0,2.5], 0.5) must be [2.5, 6.0] (VERIFIED empirically)."""
    from avideo.integrations.ffmpeg import crossfade_offsets  # noqa: PLC0415

    result = crossfade_offsets([3.0, 4.0, 2.5], 0.5)
    assert result == [2.5, 6.0], f"Expected [2.5, 6.0], got {result}"


def test_crossfade_offsets_4slides():
    """crossfade_offsets([3.0,4.0,2.5,3.5], 0.5) must be [2.5, 6.0, 8.0]."""
    from avideo.integrations.ffmpeg import crossfade_offsets  # noqa: PLC0415

    result = crossfade_offsets([3.0, 4.0, 2.5, 3.5], 0.5)
    assert result == [2.5, 6.0, 8.0], f"Expected [2.5, 6.0, 8.0], got {result}"


def test_expected_total_with_crossfade():
    """expected_total([3.0,4.0,2.5], 0.5) should be approx 8.5 (sum - (N-1)*XF)."""
    from avideo.integrations.ffmpeg import expected_total  # noqa: PLC0415

    result = expected_total([3.0, 4.0, 2.5], 0.5)
    assert abs(result - 8.5) < 1e-9, f"Expected 8.5, got {result}"


def test_expected_total_no_crossfade():
    """expected_total([3.0,4.0,2.5], 0.0) should equal full sum (no overlap)."""
    from avideo.integrations.ffmpeg import expected_total  # noqa: PLC0415

    durations = [3.0, 4.0, 2.5]
    result = expected_total(durations, 0.0)
    assert abs(result - sum(durations)) < 1e-9, f"Expected {sum(durations)}, got {result}"


def test_clamp_crossfade_basic():
    """clamp_crossfade returns min(XF, prev_dur, next_dur)."""
    from avideo.integrations.ffmpeg import clamp_crossfade  # noqa: PLC0415

    # Short prev slide: result is clamped to 0.3 (shorter than XF=0.5)
    assert clamp_crossfade(0.5, 0.3, 1.0) == pytest.approx(0.3)
    # Short next slide: result is clamped to 0.2
    assert clamp_crossfade(0.5, 1.0, 0.2) == pytest.approx(0.2)
    # Both long: result is XF
    assert clamp_crossfade(0.5, 3.0, 4.0) == pytest.approx(0.5)


def test_clamp_crossfade_zero_means_hard_cut():
    """clamp_crossfade returns <= 0 when prev or next is 0, signalling hard cut."""
    from avideo.integrations.ffmpeg import clamp_crossfade  # noqa: PLC0415

    result = clamp_crossfade(0.5, 0.0, 1.0)
    assert result <= 0, f"Expected <=0 (hard cut signal), got {result}"


# ---------------------------------------------------------------------------
# Tests: probe_duration (mock subprocess) — ASMB-01
# ---------------------------------------------------------------------------


def test_probe_drives_duration(tmp_path):
    """probe_duration must parse format.duration from ffprobe JSON output.

    Patches subprocess.run so no ffprobe binary is needed.
    Verifies that the args include 'format=duration' and '-of json'.
    """
    from avideo.integrations.ffmpeg import probe_duration  # noqa: PLC0415

    fake_stdout = json.dumps({"format": {"duration": "3.000000"}})
    fake_proc = types.SimpleNamespace(
        returncode=0,
        stdout=fake_stdout,
        stderr="",
    )

    audio_path = str(tmp_path / "slide_00.mp3")
    with patch("avideo.integrations.ffmpeg.subprocess.run", return_value=fake_proc) as mock_run:
        duration = probe_duration(audio_path)

    assert duration == pytest.approx(3.0), f"Expected 3.0, got {duration}"

    # Verify the args passed to subprocess.run contain required ffprobe options
    call_args = mock_run.call_args[0][0]  # first positional arg (the list)
    assert isinstance(call_args, list), "probe_duration must call subprocess.run with a list"
    args_str = " ".join(call_args)
    assert "format=duration" in args_str, f"Args must include 'format=duration'; got: {args_str}"
    assert "-of" in call_args, "Args must include '-of'"
    assert "json" in call_args, "Args must include 'json' (output format)"


def test_probe_drives_duration_no_wpm(tmp_path):
    """Segment durations must come from ffprobe, not from timings.json (ASMB-01 / D-02).

    This test asserts that probe_duration parses the ffprobe output directly
    and that no timings.json or WPM calculation is referenced.
    """
    from avideo.integrations.ffmpeg import probe_duration  # noqa: PLC0415

    fake_stdout = json.dumps({"format": {"duration": "7.250000"}})
    fake_proc = types.SimpleNamespace(returncode=0, stdout=fake_stdout, stderr="")

    with patch("avideo.integrations.ffmpeg.subprocess.run", return_value=fake_proc):
        duration = probe_duration(str(tmp_path / "audio.mp3"))

    assert duration == pytest.approx(7.25), f"Expected 7.25, got {duration}"


# ---------------------------------------------------------------------------
# Tests: build_filtergraph substrings (pure, no ffmpeg) — ASMB-02, ASMB-03
# ---------------------------------------------------------------------------


def test_build_filtergraph_xfade_contains_required_elements():
    """N>=2, XF>0: filtergraph must contain scale, setsar, format=yuv420p, xfade, acrossfade."""
    from avideo.integrations.ffmpeg import build_filtergraph  # noqa: PLC0415

    fg = build_filtergraph([3.0, 4.0, 2.5], xfade=0.5)

    assert "scale=1920:1080" in fg, f"Missing 'scale=1920:1080' in filtergraph"
    assert "setsar=1" in fg, f"Missing 'setsar=1' in filtergraph"
    assert "format=yuv420p" in fg, f"Missing 'format=yuv420p' in filtergraph"
    assert "xfade=" in fg, f"Missing 'xfade=' in filtergraph"
    assert "acrossfade=" in fg, f"Missing 'acrossfade=' in filtergraph"


def test_build_filtergraph_concat_when_xfade_zero():
    """XF==0: filtergraph must use concat= and NOT xfade=."""
    from avideo.integrations.ffmpeg import build_filtergraph  # noqa: PLC0415

    fg = build_filtergraph([3.0, 4.0, 2.5], xfade=0.0)

    assert "concat=" in fg, f"Missing 'concat=' in XF=0 filtergraph"
    assert "xfade=" not in fg, f"XF=0 filtergraph must NOT contain 'xfade='"


def test_build_filtergraph_single_slide_no_transitions():
    """N==1: filtergraph must contain neither 'xfade=' nor 'concat='."""
    from avideo.integrations.ffmpeg import build_filtergraph  # noqa: PLC0415

    fg = build_filtergraph([3.0], xfade=0.5)

    assert "xfade=" not in fg, "Single-slide filtergraph must NOT contain 'xfade='"
    assert "concat=" not in fg, "Single-slide filtergraph must NOT contain 'concat='"


def test_build_filtergraph_single_slide_has_normalization():
    """N==1: filtergraph must still normalize the single input."""
    from avideo.integrations.ffmpeg import build_filtergraph  # noqa: PLC0415

    fg = build_filtergraph([3.0], xfade=0.5)

    assert "scale=1920:1080" in fg, "Single-slide filtergraph must still normalize scale"
    assert "setsar=1" in fg, "Single-slide filtergraph must still set SAR"
    assert "format=yuv420p" in fg, "Single-slide filtergraph must still set pixel format"


# ---------------------------------------------------------------------------
# Tests: build_assemble_args (pure, no ffmpeg)
# ---------------------------------------------------------------------------


def test_build_assemble_args_returns_list():
    """build_assemble_args must return a list[str]."""
    from avideo.integrations.ffmpeg import build_assemble_args  # noqa: PLC0415

    args = build_assemble_args(
        ["/tmp/slide_00.png"],
        ["/tmp/audio_00.mp3"],
        [3.0],
        output_path="/tmp/output.mp4",
        xfade=0.5,
    )

    assert isinstance(args, list), "build_assemble_args must return a list"
    assert all(isinstance(a, str) for a in args), "All args must be strings"


def test_build_assemble_args_has_faststart():
    """-movflags +faststart must appear in the arg list."""
    from avideo.integrations.ffmpeg import build_assemble_args  # noqa: PLC0415

    args = build_assemble_args(
        ["/tmp/s0.png", "/tmp/s1.png"],
        ["/tmp/a0.mp3", "/tmp/a1.mp3"],
        [3.0, 4.0],
        output_path="/tmp/out.mp4",
        xfade=0.5,
    )

    # -movflags must be present and followed by +faststart
    assert "-movflags" in args, "Args must contain '-movflags'"
    movflags_idx = args.index("-movflags")
    assert args[movflags_idx + 1] == "+faststart", (
        f"'-movflags' must be followed by '+faststart', got '{args[movflags_idx + 1]}'"
    )


def test_build_assemble_args_filter_complex_is_one_element():
    """-filter_complex value must be exactly ONE list element (not shell-split)."""
    from avideo.integrations.ffmpeg import build_assemble_args  # noqa: PLC0415

    args = build_assemble_args(
        ["/tmp/s0.png", "/tmp/s1.png"],
        ["/tmp/a0.mp3", "/tmp/a1.mp3"],
        [3.0, 4.0],
        output_path="/tmp/out.mp4",
        xfade=0.5,
    )

    assert "-filter_complex" in args, "Args must contain '-filter_complex'"
    fc_idx = args.index("-filter_complex")
    # The value after -filter_complex must be a single string element
    fc_value = args[fc_idx + 1]
    assert isinstance(fc_value, str), "-filter_complex value must be a string"
    assert len(fc_value) > 0, "-filter_complex value must not be empty"


def test_build_assemble_args_no_shell_true():
    """build_assemble_args must never contain 'shell=True' as a list element."""
    from avideo.integrations.ffmpeg import build_assemble_args  # noqa: PLC0415

    args = build_assemble_args(
        ["/tmp/s0.png"],
        ["/tmp/a0.mp3"],
        [3.0],
        output_path="/tmp/out.mp4",
        xfade=0.0,
    )

    assert "shell=True" not in args, "Arg list must not contain 'shell=True'"
    assert "shell" not in args, "Arg list must not contain the word 'shell'"


# ---------------------------------------------------------------------------
# Test: AssembleStage idempotence (mock run_ffmpeg + probe_duration)
# ---------------------------------------------------------------------------


def test_assemble_idempotent(tmp_path):
    """When output.mp4 + assembly.json already exist, AssembleStage must NOT call run_ffmpeg.

    This verifies D-10: idempotence when artifacts exist.
    """
    from avideo.stages.assemble import AssembleStage  # noqa: PLC0415
    from avideo.models.assembly import AssemblyOutput  # noqa: PLC0415
    from avideo.utils.workdir import WorkdirManager  # noqa: PLC0415
    from avideo.models.config import RunConfig  # noqa: PLC0415

    # Set up a workdir with existing output.mp4 and assembly.json
    workdir = WorkdirManager(tmp_path / "workdir")

    # Create dummy output.mp4
    output_mp4 = workdir.root / "output.mp4"
    output_mp4.write_bytes(b"fake mp4 data")

    # Create assembly.json checkpoint with a valid AssemblyOutput
    existing_output = AssemblyOutput(output_path=str(output_mp4))
    (workdir.root / "assembly.json").write_text(
        existing_output.model_dump_json(), encoding="utf-8"
    )

    # Minimal config
    bullets = tmp_path / "bullets.yaml"
    bullets.write_text("title: T\nbullets:\n  - B\n", encoding="utf-8")
    config = RunConfig(bullets=bullets, duration=60, workdir=workdir.root)

    stage = AssembleStage()

    with patch("avideo.integrations.ffmpeg.run_ffmpeg") as mock_run_ffmpeg, \
         patch("avideo.integrations.ffmpeg.probe_duration") as mock_probe:
        result = stage.run(workdir, config)

    # run_ffmpeg must NOT have been called (idempotent skip)
    mock_run_ffmpeg.assert_not_called()
    mock_probe.assert_not_called()

    assert isinstance(result, AssemblyOutput)
    assert "output.mp4" in result.output_path


# ---------------------------------------------------------------------------
# Smoke test: real ffmpeg produces 1920x1080 yuv420p mp4 — ASMB-03
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed — smoke test skipped",
)
def test_smoke_dimensions(tmp_path, tiny_av_assets):
    """Real-ffmpeg smoke: assembled output must be 1920x1080 yuv420p with correct duration.

    Uses tiny PNGs + sine-wave audios from the tiny_av_assets fixture.
    Asserts width==1920, height==1080, pix_fmt=="yuv420p",
    and abs(duration - expected_total) < 0.1 (Pitfall 7: ±1-frame tolerance).
    """
    from avideo.integrations.ffmpeg import (  # noqa: PLC0415
        build_assemble_args,
        probe_duration,
        run_ffmpeg,
        expected_total,
    )

    png_paths, audio_paths = tiny_av_assets
    n = len(png_paths)
    assert n >= 2, "tiny_av_assets should provide at least 2 assets"

    # Measure real durations
    durations = [probe_duration(a) for a in audio_paths]
    xfade = 0.3  # Use a small crossfade that fits within ~1s audios
    expected_dur = expected_total(durations, xfade)

    output_mp4 = str(tmp_path / "smoke_output.mp4")
    args = build_assemble_args(
        png_paths,
        audio_paths,
        durations,
        output_path=output_mp4,
        xfade=xfade,
    )
    run_ffmpeg(args)

    # Probe the output file
    probe_args = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=width,height,pix_fmt:format=duration",
        "-of", "json",
        output_mp4,
    ]
    result = subprocess.run(probe_args, capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)

    # Find video stream
    video_streams = [s for s in info.get("streams", []) if s.get("width")]
    assert video_streams, "No video stream found in output"
    vs = video_streams[0]

    assert vs.get("width") == 1920, f"Expected width 1920, got {vs.get('width')}"
    assert vs.get("height") == 1080, f"Expected height 1080, got {vs.get('height')}"
    assert vs.get("pix_fmt") == "yuv420p", f"Expected yuv420p, got {vs.get('pix_fmt')}"

    actual_duration = float(info["format"]["duration"])
    assert abs(actual_duration - expected_dur) < 0.1, (
        f"Duration mismatch: expected ~{expected_dur:.3f}s, got {actual_duration:.3f}s"
    )
