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


# ---------------------------------------------------------------------------
# Tests: parse_loudnorm_json (pure, uses fixture) — QA-02
# ---------------------------------------------------------------------------


def test_parse_loudnorm_json_returns_floats(loudnorm_pass1_stderr):
    """parse_loudnorm_json must return float values for all expected keys."""
    from avideo.integrations.ffmpeg import parse_loudnorm_json  # noqa: PLC0415

    result = parse_loudnorm_json(loudnorm_pass1_stderr)

    assert isinstance(result, dict)
    assert "measured_I" in result
    assert "measured_TP" in result
    assert "measured_LRA" in result
    assert "measured_thresh" in result
    assert "offset" in result
    for key, val in result.items():
        assert isinstance(val, float), f"Key '{key}' must be float, got {type(val)}"


def test_parse_loudnorm_json_measured_i_value(loudnorm_pass1_stderr):
    """parse_loudnorm_json measured_I must equal -22.01 from the fixture."""
    from avideo.integrations.ffmpeg import parse_loudnorm_json  # noqa: PLC0415

    result = parse_loudnorm_json(loudnorm_pass1_stderr)

    assert result["measured_I"] == pytest.approx(-22.01), (
        f"Expected measured_I ≈ -22.01, got {result['measured_I']}"
    )


def test_parse_loudnorm_json_raises_on_garbage():
    """parse_loudnorm_json must raise ValueError when no JSON block is found."""
    from avideo.integrations.ffmpeg import parse_loudnorm_json  # noqa: PLC0415

    with pytest.raises(ValueError, match="No loudnorm JSON block"):
        parse_loudnorm_json("garbage no braces here")


def test_parse_loudnorm_json_raises_on_missing_fields():
    """parse_loudnorm_json must raise KeyError/ValueError when required fields are absent."""
    from avideo.integrations.ffmpeg import parse_loudnorm_json  # noqa: PLC0415

    # JSON block with wrong/missing field names
    stderr_with_bad_json = 'some log line\n{"oops": 1}\n'
    with pytest.raises((KeyError, ValueError)):
        parse_loudnorm_json(stderr_with_bad_json)


def test_parse_loudnorm_json_uses_last_block():
    """parse_loudnorm_json must parse the LAST {...} block (Pitfall 4)."""
    from avideo.integrations.ffmpeg import parse_loudnorm_json  # noqa: PLC0415

    # Multiple blocks — last one has correct fields
    stderr = (
        '{"oops": 1}\n'
        '{\n'
        '    "input_i" : "-18.50",\n'
        '    "input_tp" : "-10.00",\n'
        '    "input_lra" : "5.00",\n'
        '    "input_thresh" : "-28.50",\n'
        '    "output_i" : "-16.00",\n'
        '    "output_tp" : "-1.50",\n'
        '    "output_lra" : "4.50",\n'
        '    "output_thresh" : "-26.00",\n'
        '    "normalization_type" : "linear",\n'
        '    "target_offset" : "-0.50"\n'
        '}\n'
    )
    result = parse_loudnorm_json(stderr)
    assert result["measured_I"] == pytest.approx(-18.50)


# ---------------------------------------------------------------------------
# Tests: loudnorm pass-2 args — QA-02 (Pitfall 2: faststart + linear=true)
# ---------------------------------------------------------------------------


def test_loudnorm_pass2_args_has_faststart():
    """loudnorm_pass2_args must include +faststart AND -c:v copy AND linear=true (Pitfall 2)."""
    from avideo.integrations.ffmpeg import loudnorm_pass2_args  # noqa: PLC0415

    measured = {
        "measured_I": -22.01,
        "measured_TP": -20.91,
        "measured_LRA": 0.70,
        "measured_thresh": -32.01,
        "offset": -0.26,
    }
    args = loudnorm_pass2_args(
        "/tmp/input.mp4",
        "/tmp/output.mp4",
        **measured,
        target_lufs=-16.0,
    )

    assert isinstance(args, list), "loudnorm_pass2_args must return a list"
    args_str = " ".join(args)

    # Pitfall 2: faststart must be re-added
    assert "+faststart" in args_str, f"+faststart missing in args: {args_str}"
    assert "-c:v" in args and "copy" in args, f"-c:v copy missing in args: {args}"
    assert "linear=true" in args_str, f"linear=true missing in args: {args_str}"


# ---------------------------------------------------------------------------
# Tests: duration_deviation (pure) — QA-01
# ---------------------------------------------------------------------------


def test_deviation_basic():
    """duration_deviation(actual, target) == actual - target."""
    from avideo.stages.qa import duration_deviation  # noqa: PLC0415

    result = duration_deviation(actual_seconds=8.533, target_seconds=8.5)
    assert result == pytest.approx(0.033, abs=1e-6)


def test_deviation_negative():
    """duration_deviation is negative when actual < target."""
    from avideo.stages.qa import duration_deviation  # noqa: PLC0415

    result = duration_deviation(actual_seconds=7.9, target_seconds=8.5)
    assert result < 0
    assert result == pytest.approx(-0.6, abs=1e-6)


def test_deviation_zero():
    """duration_deviation is zero when actual == target."""
    from avideo.stages.qa import duration_deviation  # noqa: PLC0415

    result = duration_deviation(actual_seconds=8.5, target_seconds=8.5)
    assert result == pytest.approx(0.0)


def test_deviation_within_tolerance():
    """within_tolerance returns True for small deviation and False for large."""
    from avideo.stages.qa import within_tolerance  # noqa: PLC0415

    assert within_tolerance(0.033) is True   # 33ms — within 0.5s default
    assert within_tolerance(0.499) is True   # just under
    assert within_tolerance(1.5) is False    # over 0.5s threshold
    assert within_tolerance(-1.5) is False   # negative large deviation


# ---------------------------------------------------------------------------
# Tests: build_qa_report (pure) — QA-01/02
# ---------------------------------------------------------------------------


def test_build_qa_report_fields():
    """build_qa_report must return QAReport with correct deviation + LUFS fields."""
    from avideo.stages.qa import build_qa_report  # noqa: PLC0415
    from avideo.models.assembly import QAReport  # noqa: PLC0415

    report = build_qa_report(
        target_seconds=8.5,
        actual_seconds=8.533,
        measured_lufs=-22.01,
        normalized_lufs=-16.01,
    )

    assert isinstance(report, QAReport)
    assert report.target_seconds == pytest.approx(8.5)
    assert report.actual_seconds == pytest.approx(8.533)
    assert report.duration_deviation == pytest.approx(0.033, abs=1e-6)
    assert report.measured_lufs == pytest.approx(-22.01)
    assert report.normalized_lufs == pytest.approx(-16.01)


def test_build_qa_report_has_measured_and_normalized_lufs():
    """QAReport must carry both measured_lufs and normalized_lufs fields."""
    from avideo.models.assembly import QAReport  # noqa: PLC0415

    # Direct construction to verify model has both new fields
    report = QAReport(
        target_seconds=10.0,
        actual_seconds=10.5,
        duration_deviation=0.5,
        measured_lufs=-20.0,
        normalized_lufs=-16.0,
    )

    assert report.measured_lufs == pytest.approx(-20.0)
    assert report.normalized_lufs == pytest.approx(-16.0)


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


# ---------------------------------------------------------------------------
# Task 2 tests: QA sub-step wired into AssembleStage + PIPELINE_STAGES swap
# ---------------------------------------------------------------------------


def test_assemble_end_to_end_writes_qa_report(tmp_path, loudnorm_pass1_stderr):
    """AssembleStage.run must write qa_report.json with QAReport attached to output.

    Mocks run_ffmpeg (canned loudnorm stderr for pass-1) + probe_duration (fixed floats).
    Creates placeholder slide/audio assets + slides.json/voice.json checkpoints.
    Asserts output.mp4, qa_report.json written and QAReport has measured/normalized LUFS.
    """
    import types  # noqa: PLC0415 — already imported at module level but safe to re-import

    from avideo.stages.assemble import AssembleStage  # noqa: PLC0415
    from avideo.models.assembly import AssemblyOutput, QAReport  # noqa: PLC0415
    from avideo.models.slides import SlidesOutput  # noqa: PLC0415
    from avideo.models.voice import VoiceOutput  # noqa: PLC0415
    from avideo.utils.workdir import WorkdirManager  # noqa: PLC0415
    from avideo.models.config import RunConfig  # noqa: PLC0415

    workdir = WorkdirManager(tmp_path / "workdir")

    # Create placeholder PNG and audio files (just touch them — ffmpeg is mocked)
    slide_path = workdir.root / "slides" / "slide_00.png"
    slide_path.write_bytes(b"\x89PNG\r\n\x1a\n")  # PNG magic bytes
    audio_path = workdir.root / "audio" / "audio_00.mp3"
    audio_path.write_bytes(b"\xff\xe3")  # minimal mp3 magic

    # Write slides.json checkpoint
    slides_out = SlidesOutput(
        png_paths=[str(slide_path)],
        mode="auto",
    )
    workdir.write_checkpoint("slides", slides_out)

    # Write voice.json checkpoint
    voice_out = VoiceOutput(
        audio_paths=[str(audio_path)],
        voice_mode="elevenlabs",
    )
    workdir.write_checkpoint("voice", voice_out)

    # Minimal config (duration=10 as target)
    bullets = tmp_path / "bullets.yaml"
    bullets.write_text("title: T\nbullets:\n  - B\n", encoding="utf-8")
    config = RunConfig(bullets=bullets, duration=10, workdir=workdir.root)

    # Fake pass-1 proc (loudnorm JSON in stderr) — used for both pass-1 measure and probe
    pass1_proc = types.SimpleNamespace(
        returncode=0,
        stdout="",
        stderr=loudnorm_pass1_stderr,
    )
    # Fake pass-2 proc (stdout empty, stderr minimal for pass-2 output_i)
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
        count = call_count[0]
        call_count[0] += 1
        # call 0: main assembly encode → create fake output.mp4
        if count == 0:
            # The first call produces output.mp4.tmp; we simulate it by writing the tmp file
            # Find the output path argument (last arg)
            out_arg = args[-1]
            Path(out_arg).write_bytes(b"fake mp4")
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")
        # call 1: loudnorm pass-1 (measure)
        elif count == 1:
            return pass1_proc
        # call 2: loudnorm pass-2 (apply) → create normalized tmp
        elif count == 2:
            out_arg = args[-1]
            Path(out_arg).write_bytes(b"fake normalized mp4")
            return pass2_proc
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    def fake_probe_duration(path):
        # Return 10.5 for the final output.mp4 (target=10 → deviation=0.5)
        return 10.5

    with patch("avideo.integrations.ffmpeg.subprocess.run") as mock_subproc, \
         patch("avideo.stages.assemble.run_ffmpeg", side_effect=fake_run_ffmpeg), \
         patch("avideo.stages.assemble.probe_duration", side_effect=fake_probe_duration):
        # subprocess.run is also patched so the probe_duration_args calls succeed
        mock_subproc.return_value = types.SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"format": {"duration": "10.5"}}),
            stderr="",
        )
        result = AssembleStage().run(workdir, config)

    # output.mp4 must exist
    assert (workdir.root / "output.mp4").exists(), "output.mp4 must be written"

    # qa_report.json must exist
    qa_json_path = workdir.root / "qa_report.json"
    assert qa_json_path.exists(), "qa_report.json must be written"

    # qa_report.json must be valid JSON with QAReport shape
    qa_data = json.loads(qa_json_path.read_text())
    assert "duration_deviation" in qa_data
    assert "measured_lufs" in qa_data
    assert "normalized_lufs" in qa_data

    # AssemblyOutput.qa must be attached
    assert isinstance(result, AssemblyOutput)
    assert result.qa is not None, "AssemblyOutput.qa must be populated"
    assert isinstance(result.qa, QAReport)
    assert result.qa.measured_lufs is not None
    assert result.qa.normalized_lufs is not None


def test_pipeline_stages_has_assemble_stage():
    """PIPELINE_STAGES last entry must be AssembleStage with correct stage_name + checkpoint."""
    from avideo.stages.stubs import PIPELINE_STAGES  # noqa: PLC0415
    from avideo.stages.assemble import AssembleStage  # noqa: PLC0415

    last_stage = PIPELINE_STAGES[-1]
    assert isinstance(last_stage, AssembleStage), (
        f"PIPELINE_STAGES last entry must be AssembleStage, got {type(last_stage).__name__}"
    )
    assert last_stage.stage_name == "assemble", (
        f"stage_name must be 'assemble', got '{last_stage.stage_name}'"
    )
    assert last_stage.checkpoint_name == "assembly", (
        f"checkpoint_name must be 'assembly', got '{last_stage.checkpoint_name}'"
    )


def test_assemble_stub_class_still_exists():
    """AssembleStub class must still be importable (tests import it directly)."""
    from avideo.stages.stubs import AssembleStub  # noqa: PLC0415

    assert hasattr(AssembleStub, "stage_name")
    assert AssembleStub.stage_name == "assemble"
