"""FFmpeg integration — arg-list builder, crossfade math, ffprobe, subprocess wrapper.

Decision references (from 05-CONTEXT.md):
    D-01  Single filtergraph: per-slide PNG looped to audio duration; chained with
          xfade (video) + acrossfade (audio); 1920x1080 H.264 yuv420p +faststart.
    D-02  Segment durations measured with ffprobe on real audio files (NOT timings.json).
    D-03  Crossfade default 0.5s, configurable; 0 → hard cuts via concat filter.
    D-04  ffmpeg/ffprobe invoked by subprocess with a list[str], NEVER shell=True;
          captures stderr; raises RuntimeError with tail on nonzero exit.

Pitfall references (from 05-RESEARCH.md):
    Pitfall 1  Negative xfade offset → clamp per-boundary to min(XF, prev, next).
    Pitfall 2  -c:v copy drops +faststart → re-add -movflags +faststart on every output.
    Pitfall 3  Mixed pix_fmt / SAR / fps across xfade inputs → normalize every input.
    Pitfall 4  loudnorm JSON embedded in noisy stderr → extract last {...} block.
    Pitfall 6  filter_complex must be ONE list element (no shell quoting).

Sections:
    PURE MATH     — crossfade_offsets, expected_total, clamp_crossfade
    PURE BUILDERS — _input_normalize, build_filtergraph, build_assemble_args,
                    probe_duration_args, loudnorm_pass1_args, loudnorm_pass2_args,
                    parse_loudnorm_json
    SUBPROCESS    — run_ffmpeg, probe_duration, ffmpeg_available
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from typing import Optional

# ---------------------------------------------------------------------------
# PURE MATH (no I/O — fully unit-testable)
# ---------------------------------------------------------------------------


def crossfade_offsets(durations: list[float], xfade: float) -> list[float]:
    """Return the xfade ``offset=`` value for each join between slides (len = N-1).

    Algorithm (VERIFIED empirically for N=2,3,4, ffmpeg 8.0.1, 05-RESEARCH.md Pattern 1):
        merged_dur after first segment = durations[0]
        for each subsequent duration d:
            offset = round(merged_dur - xfade, 6)   # where the transition begins
            merged_dur = merged_dur + d - xfade

    Final total duration = sum(durations) - (N-1)*xfade  (verified ±1 frame @30fps).

    Verified example — 3 slides [3.0, 4.0, 2.5], XF=0.5:
        join 1: merged=3.0 → offset=2.5;  merged becomes 3.0+4.0-0.5=6.5
        join 2: merged=6.5 → offset=6.0;  merged becomes 6.5+2.5-0.5=8.5
        offsets = [2.5, 6.0]

    Args:
        durations: Per-slide audio durations in seconds (from ffprobe — D-02).
        xfade: Crossfade duration in seconds (0 → use concat instead, not this function).

    Returns:
        List of offset values, length = len(durations) - 1.
    """
    offsets: list[float] = []
    merged = durations[0]
    for d in durations[1:]:
        offsets.append(round(merged - xfade, 6))
        merged = merged + d - xfade
    return offsets


def expected_total(durations: list[float], xfade: float) -> float:
    """Return the expected total video duration with crossfade.

    Formula: sum(durations) - max(0, N-1) * xfade
    With xfade=0: equals the full sum (no overlap).

    Args:
        durations: Per-slide audio durations in seconds.
        xfade: Crossfade duration in seconds.

    Returns:
        Expected total duration in seconds.
    """
    n = len(durations)
    return sum(durations) - max(0, n - 1) * xfade


def clamp_crossfade(xfade: float, prev_dur: float, next_dur: float) -> float:
    """Clamp a crossfade to min(xfade, prev_dur, next_dur) per-boundary.

    If the result is <= 0, the caller must treat that boundary as a hard cut
    (no xfade/acrossfade for this join) to avoid negative offsets which corrupt
    the output silently (Pitfall 1 mitigation, VERIFIED in 05-RESEARCH.md).

    Args:
        xfade: Desired crossfade duration in seconds.
        prev_dur: Duration of the preceding slide's audio.
        next_dur: Duration of the following slide's audio.

    Returns:
        Effective crossfade duration; <= 0 signals hard cut for this boundary.
    """
    return min(xfade, prev_dur, next_dur)


# ---------------------------------------------------------------------------
# PURE BUILDERS (return strings / list[str] — no I/O, no subprocess)
# ---------------------------------------------------------------------------

# Verified per-input normalization chain (05-RESEARCH Pattern 1 + Pitfall 3):
#   scale to 1920x1080 preserving aspect ratio → pad to fill → setsar=1 → fps → format
_NORMALIZE_TMPL = (
    "[{label_in}]scale=1920:1080:force_original_aspect_ratio=decrease,"
    "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p[{label_out}]"
)


def _input_normalize(label_in: str, label_out: str, fps: int = 30) -> str:
    """Return the per-input normalization filter chain as a filtergraph segment.

    Verified: produces exactly 1920×1080, SAR 1:1, yuv420p output for any
    input resolution (including odd dimensions like 1280×720 — Pitfall 3).

    Args:
        label_in:  Input stream label, e.g. ``"0:v"``.
        label_out: Output label, e.g. ``"v0"``.
        fps:       Target frame rate (default 30).

    Returns:
        Filter chain segment string without trailing semicolon.
    """
    return _NORMALIZE_TMPL.format(label_in=label_in, label_out=label_out, fps=fps)


def build_filtergraph(
    durations: list[float],
    xfade: float,
    *,
    fps: int = 30,
) -> str:
    """Build the -filter_complex string for N slides with configurable crossfade.

    Three dispatch paths (D-03, 05-RESEARCH Patterns 1/3/4):

    N == 1 (single slide):
        One normalized video segment [vout] + [1:a]aresample=48000[aout].
        No xfade, no concat — caller adds -shortest.

    xfade == 0 AND N >= 2 (hard cuts):
        Each input normalized; then interleaved [v0][a0][v1][a1]...
        concat=n=N:v=1:a=1[vout][aout].
        (Do NOT use xfade with offset=0 — Pitfall 6 / Anti-Pattern.)

    xfade > 0 AND N >= 2 (crossfade):
        Each input normalized; then per-boundary xfade(video) + acrossfade(audio)
        with computed offsets.  Each boundary crossfade is clamped to
        min(xfade, prev_dur, next_dur) via clamp_crossfade (Pitfall 1).
        If a clamped eff_XF <= 0, that boundary becomes a concat (hard cut for
        that single join) to avoid negative offset corruption.

    Args:
        durations: Per-slide audio durations in seconds; determines slide lengths.
        xfade: Global crossfade duration in seconds (0 → concat path).
        fps: Output frame rate (default 30).

    Returns:
        Complete filter_complex string to be passed as ONE list element to ffmpeg.
    """
    n = len(durations)

    # --- Path 1: single slide ---
    if n == 1:
        v_norm = _input_normalize("0:v", "vout", fps=fps)
        a_norm = "[1:a]aresample=48000[aout]"
        return f"{v_norm};{a_norm}"

    # Normalize all video inputs (audio inputs use aresample only)
    v_norms = [_input_normalize(f"{i}:v", f"v{i}", fps=fps) for i in range(n)]
    a_norms = [f"[{n + i}:a]aresample=48000[a{i}]" for i in range(n)]
    parts: list[str] = v_norms + a_norms

    # --- Path 2: hard cuts (concat filter) ---
    if xfade == 0.0:
        # Interleaved input order: [v0][a0][v1][a1]...
        interleaved = "".join(f"[v{i}][a{i}]" for i in range(n))
        concat = f"{interleaved}concat=n={n}:v=1:a=1[vout][aout]"
        parts.append(concat)
        return ";".join(parts)

    # --- Path 3: xfade + acrossfade (crossfade path) ---
    # Build per-boundary effective crossfades (clamp to avoid negative offsets)
    eff_xf: list[float] = [
        clamp_crossfade(xfade, durations[i], durations[i + 1])
        for i in range(n - 1)
    ]

    # Build offset chain with per-boundary eff_XF
    offsets: list[float] = []
    merged = durations[0]
    for i, eff in enumerate(eff_xf):
        offsets.append(round(merged - eff, 6))
        merged = merged + durations[i + 1] - eff

    # Chain xfade (video) + acrossfade (audio) transitions
    # Start with v0/a0, then apply each join
    v_label = "v0"
    a_label = "a0"

    for i, (eff, offset) in enumerate(zip(eff_xf, offsets)):
        next_v = f"v{i + 1}"
        next_a = f"a{i + 1}"
        out_v = "vout" if i == n - 2 else f"vx{i}"
        out_a = "aout" if i == n - 2 else f"ax{i}"

        if eff <= 0:
            # Hard cut for this boundary (clamped to zero/negative)
            # Use concat for this one pair and continue
            concat_v = f"[{v_label}][{next_v}]concat=n=2:v=1:a=0[{out_v}]"
            concat_a = f"[{a_label}][{next_a}]concat=n=2:v=0:a=1[{out_a}]"
            parts.append(concat_v)
            parts.append(concat_a)
        else:
            xf_filter = (
                f"[{v_label}][{next_v}]xfade=transition=fade:duration={eff}:offset={offset}[{out_v}]"
            )
            acf_filter = (
                f"[{a_label}][{next_a}]acrossfade=d={eff}[{out_a}]"
            )
            parts.append(xf_filter)
            parts.append(acf_filter)

        v_label = out_v
        a_label = out_a

    return ";".join(parts)


def build_assemble_args(
    image_paths: list[str],
    audio_paths: list[str],
    durations: list[float],
    *,
    output_path: str,
    xfade: float,
    fps: int = 30,
    crf: int = 20,
    preset: str = "medium",
    burn_subs_path: Optional[str] = None,
) -> list[str]:
    """Build the complete ffmpeg arg list for video assembly (arg-list, NEVER shell=True).

    Assembles per-slide PNG loops + audio into a single 1080p 16:9 H.264 MP4.
    The -filter_complex value is ONE list element (Pitfall 6 — no shell quoting needed).

    Args:
        image_paths:    Paths to per-slide PNG files (index-aligned with audio_paths).
        audio_paths:    Paths to per-slide audio files (mp3 or wav).
        durations:      Per-slide audio durations in seconds (from probe_duration — D-02).
        output_path:    Destination file path (should be a .tmp path for atomic rename).
        xfade:          Crossfade duration (0 → hard cuts via concat; >0 → xfade path).
        fps:            Output frame rate (default 30 — Assumption A3).
        crf:            libx264 CRF quality (default 20 — Assumption A2).
        preset:         libx264 preset (default "medium" — Assumption A2).
        burn_subs_path: If set, add libass subtitle burn-in filter (D-05, Pattern 6).
                        Must be the fixed workdir/subs/output.srt path (no user component).

    Returns:
        A ``list[str]`` ready for ``subprocess.run(args, shell=False)``.
        Never contains ``"shell=True"`` (T-05-01 enforcement).

    Security (T-05-01/T-05-02):
        - All paths come from WorkdirManager (fixed layout) or prior-phase checkpoints.
        - filter_complex is ONE list element — no shell interpretation.
        - No element is ever "shell=True".
    """
    n = len(image_paths)
    args: list[str] = ["ffmpeg", "-hide_banner", "-y"]

    # Per-image inputs (looped to audio duration)
    for i, (img, dur) in enumerate(zip(image_paths, durations)):
        args.extend(["-loop", "1", "-t", str(dur), "-i", img])

    # Per-audio inputs
    for audio in audio_paths:
        args.extend(["-i", audio])

    # Build filtergraph
    filtergraph = build_filtergraph(durations, xfade, fps=fps)

    # If burn_subs, append the subtitle filter to the vout chain
    # (Pattern 6: subtitles=filename='...', libass)
    if burn_subs_path is not None:
        # Replace [vout] output label with intermediate, then add subtitle filter
        # The subtitle filter must be appended after the vout chain
        filtergraph = filtergraph.replace("[vout]", "[vpre]")
        safe_path = burn_subs_path.replace("'", "\\'")
        filtergraph += f";[vpre]subtitles=filename='{safe_path}'[vout]"

    args.extend(["-filter_complex", filtergraph])

    # Map outputs
    args.extend(["-map", "[vout]", "-map", "[aout]"])

    # Encode options (D-01, Assumption A2/A5)
    args.extend([
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",  # Pitfall 2: always re-add +faststart
    ])

    # Single-slide path needs -shortest to end the loop with the audio
    if n == 1:
        args.append("-shortest")

    args.append(output_path)
    return args


def probe_duration_args(path: str) -> list[str]:
    """Return the ffprobe arg list to measure a file's container duration.

    Verified: ``format.duration`` is reliable for both mp3 (VBR) and wav
    (05-RESEARCH Pattern 2).

    Args:
        path: Path to the audio (or video) file to measure.

    Returns:
        A ``list[str]`` ready for ``subprocess.run``.
    """
    return [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        path,
    ]


def loudnorm_pass1_args(input_path: str, target_lufs: float = -16.0) -> list[str]:
    """Return the ffmpeg arg list for loudnorm pass-1 (measure, EBU R128).

    Output is ``-f null -`` (no output file — measure only).  The JSON block
    containing measured values is printed to stderr (05-RESEARCH Pattern 5).

    Args:
        input_path:  Path to the audio/video file to measure.
        target_lufs: EBU R128 integrated loudness target in LUFS (default -16.0).

    Returns:
        A ``list[str]`` for ``subprocess.run``.
    """
    af = f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11:print_format=json"
    return [
        "ffmpeg", "-hide_banner",
        "-i", input_path,
        "-af", af,
        "-f", "null", "-",
    ]


def loudnorm_pass2_args(
    input_path: str,
    output_path: str,
    *,
    measured_I: float,
    measured_TP: float,
    measured_LRA: float,
    measured_thresh: float,
    offset: float,
    target_lufs: float = -16.0,
) -> list[str]:
    """Return the ffmpeg arg list for loudnorm pass-2 (apply measured values).

    Copies video (-c:v copy), re-encodes audio with measured normalization params.
    Always includes -movflags +faststart (Pitfall 2: copy drops faststart).

    Args:
        input_path:      Path to the assembled MP4.
        output_path:     Path for the normalized output MP4 (use .tmp for atomic rename).
        measured_I:      Measured integrated loudness (from pass-1 ``input_i``).
        measured_TP:     Measured true peak (from pass-1 ``input_tp``).
        measured_LRA:    Measured loudness range (from pass-1 ``input_lra``).
        measured_thresh: Measured threshold (from pass-1 ``input_thresh``).
        offset:          Target offset (from pass-1 ``target_offset``).
        target_lufs:     EBU R128 target loudness (default -16.0).

    Returns:
        A ``list[str]`` for ``subprocess.run``.
    """
    af = (
        f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11"
        f":measured_I={measured_I}"
        f":measured_TP={measured_TP}"
        f":measured_LRA={measured_LRA}"
        f":measured_thresh={measured_thresh}"
        f":offset={offset}"
        f":linear=true:print_format=json"
    )
    return [
        "ffmpeg", "-hide_banner", "-y",
        "-i", input_path,
        "-af", af,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-movflags", "+faststart",  # Pitfall 2: MUST re-add under -c:v copy
        output_path,
    ]


def parse_loudnorm_json(stderr: str) -> dict[str, float]:
    """Extract and parse the loudnorm measurement JSON block from ffmpeg stderr.

    loudnorm prints a JSON block to stderr after other log lines.  We extract
    the last ``{...}`` block (Pitfall 4) and parse the known string fields as
    floats (verified field names from ffmpeg 8.0.1, 05-RESEARCH Pattern 5).

    Args:
        stderr: The captured stderr string from a loudnorm pass-1 ffmpeg run.

    Returns:
        Dict with float values for:
            ``measured_I``, ``measured_TP``, ``measured_LRA``, ``measured_thresh``,
            ``offset`` — suitable for passing to ``loudnorm_pass2_args``.

    Raises:
        ValueError: If no ``{...}`` block is found in stderr.
        KeyError: If expected loudnorm fields are absent from the JSON.
    """
    blocks = re.findall(r"\{[^{}]*\}", stderr, re.DOTALL)
    if not blocks:
        raise ValueError("No loudnorm JSON block found in ffmpeg stderr")
    raw = json.loads(blocks[-1])
    return {
        "measured_I": float(raw["input_i"]),
        "measured_TP": float(raw["input_tp"]),
        "measured_LRA": float(raw["input_lra"]),
        "measured_thresh": float(raw["input_thresh"]),
        "offset": float(raw["target_offset"]),
    }


# ---------------------------------------------------------------------------
# SUBPROCESS PLUMBING (mockable — the ONLY place that shells out)
# ---------------------------------------------------------------------------


def run_ffmpeg(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run an ffmpeg or ffprobe command with a list of args (NEVER shell=True).

    Captures stdout and stderr.  On nonzero exit, raises a ``RuntimeError``
    with the last ~8 stderr lines so the orchestrator surfaces a clean Rich
    message (D-04) rather than a raw traceback.

    Args:
        args: Arg list, e.g. ``["ffmpeg", "-hide_banner", "-i", ...]``.
              Must be a ``list[str]`` — never a shell string (T-05-01, CLAUDE.md).

    Returns:
        ``subprocess.CompletedProcess[str]`` on success (returncode == 0).

    Raises:
        RuntimeError: If ffmpeg exits with a nonzero return code.
    """
    proc = subprocess.run(args, capture_output=True, text=True)  # shell=False is implicit default
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-8:])
        raise RuntimeError(f"ffmpeg failed (exit {proc.returncode}):\n{tail}")
    return proc


def probe_duration(path: str) -> float:
    """Measure the container duration of an audio or video file using ffprobe.

    Uses ``format.duration`` (container-level) which is reliable for both mp3
    (VBR) and wav files (ASMB-01 / D-02 / 05-RESEARCH Pattern 2).

    Args:
        path: Path to the media file.

    Returns:
        Duration in seconds as a float.

    Raises:
        RuntimeError: If ffprobe exits with a nonzero return code.
        ValueError: If the duration field is missing or unparseable.
    """
    proc = run_ffmpeg(probe_duration_args(path))
    return float(json.loads(proc.stdout)["format"]["duration"])


def ffmpeg_available() -> bool:
    """Return True if both ffmpeg and ffprobe binaries are on PATH.

    Used by test skip guards and optional feature detection.
    ``shutil.which`` is used so tests can monkeypatch as needed.

    Returns:
        True if both ``ffmpeg`` and ``ffprobe`` are accessible; False otherwise.
    """
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
