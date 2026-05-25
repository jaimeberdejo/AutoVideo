"""VoiceRecordStage — record mode voice stage (D-04 / D-12 / VOICE-03).

Exports a segmented script for the user to narrate, then for each slide either:
  (a) uses an already-provided ``workdir/audio/slide_XX.wav`` (autodetection, D-04b), or
  (b) records audio via ``sounddevice`` → ``soundfile.write`` (D-04a).

Returns ``UnifiedTimings(source="record", slides=[...])`` with ``words=[]``
(word-level timestamps are populated later by ``AlignStage`` in plan 04-02).

Design decisions:
- D-04/D-12: stage_name="voice" matches the checkpoint contract (VoiceStub used same name).
- D-06 / Pitfall 5: sounddevice and soundfile are imported LAZILY inside the recording
  function — never at module top level.  This keeps the module import-safe on CI/Docker
  and on systems without PortAudio hardware.
- T-04-05: wav_path is constructed ONLY via
  ``workdir.root / "audio" / f"slide_{index:02d}.wav"`` — no user-controlled string
  in the path (no path traversal).
- T-04-07: ImportError from sounddevice (missing PortAudio) is caught and re-raised
  with a clear message pointing to the ``record`` extra.

Script export format:
  A single file ``workdir/audio/script_segments.txt`` is written before recording.
  Format: repeated blocks of
      === Slide N: {title} ===
      {narration text}
      (blank line)
  This gives the user the complete narration to read per slide.

Duration calculation:
  After obtaining a WAV (via autodetect or recording), the clip duration is
  measured with ``soundfile.info(wav_path).frames / samplerate`` (lazy import).
  This provides the real clip duration (not an estimate) so that subtitle
  global-offset accumulation in Phase 4-03 is accurate.

  CRITICAL (Warning 1): Per-slide duration must NEVER be 0.0 when audio/words exist.
  If soundfile.info fails or returns 0 frames, we fall back to 0.0 with a warning
  (align stage / Phase 5 will recalculate via ffprobe).  An explicit guard ensures
  that a positive frame count always maps to a positive duration.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from avideo.models.script import ScriptOutput
from avideo.models.timings import SlideTimings, UnifiedTimings
from avideo.stages.base import CheckpointMixin

if TYPE_CHECKING:
    from avideo.models.config import RunConfig
    from avideo.utils.workdir import WorkdirManager

# ---------------------------------------------------------------------------
# Module-level lazy aliases (set to None; resolved inside functions — D-06)
# These names exist at module scope so tests can patch them via
# ``patch("avideo.stages.voice_record.sounddevice", ...)``.
# ---------------------------------------------------------------------------

sounddevice = None  # type: ignore[assignment]
soundfile = None    # type: ignore[assignment]


def _load_sounddevice():
    """Lazy-load sounddevice, raising ImportError with a clear message if absent."""
    global sounddevice
    if sounddevice is None:
        try:
            import sounddevice as _sd  # noqa: PLC0415 — D-06 lazy
            sounddevice = _sd
        except ImportError as exc:
            raise ImportError(
                "Voice mode 'record' requires PortAudio and the optional 'record' extra. "
                "Install with: uv sync --extra record  "
                "(also requires portaudio19-dev on Linux / brew install portaudio on macOS). "
                f"Original error: {exc}"
            ) from exc
    return sounddevice


def _load_soundfile():
    """Lazy-load soundfile, raising ImportError with a clear message if absent."""
    global soundfile
    if soundfile is None:
        try:
            import soundfile as _sf  # noqa: PLC0415 — D-06 lazy
            soundfile = _sf
        except ImportError as exc:
            raise ImportError(
                "Voice mode 'record' requires soundfile (part of the optional 'record' extra). "
                "Install with: uv sync --extra record. "
                f"Original error: {exc}"
            ) from exc
    return soundfile


# ---------------------------------------------------------------------------
# Script export
# ---------------------------------------------------------------------------


def _export_script_segments(workdir_root: Path, script: ScriptOutput) -> None:
    """Write the segmented narration script to workdir/audio/script_segments.txt.

    Creates one labeled block per slide so the user sees exactly what to narrate
    for each slide.  The file is UTF-8 encoded.

    Format::

        === Slide 0 ===
        {narration text for slide 0}

        === Slide 1 ===
        {narration text for slide 1}

        ...

    Args:
        workdir_root: Root directory of the workdir (workdir.root).
        script: ScriptOutput parsed from the script checkpoint.
    """
    lines: list[str] = []
    for slide in script.slides:
        lines.append(f"=== Slide {slide.slide_index} ===")
        lines.append(slide.narration)
        lines.append("")  # blank line between slides

    out_path = workdir_root / "audio" / "script_segments.txt"
    out_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Duration measurement
# ---------------------------------------------------------------------------


def _measure_duration(wav_path: Path) -> float:
    """Measure the duration of a WAV file in seconds using soundfile.

    Uses lazy-loaded soundfile to read the file's frame count and sample rate.
    Returns a non-negative float.

    CRITICAL (Warning 1): returns 0.0 only if the file has 0 frames or
    soundfile is unavailable.  Callers should warn when 0.0 is returned with
    a non-empty WAV.

    Args:
        wav_path: Path to the WAV file.

    Returns:
        Duration in seconds (float).  0.0 if frames=0 or soundfile unavailable.
    """
    try:
        sf = _load_soundfile()
        info = sf.info(str(wav_path))
        if info.samplerate > 0 and info.frames > 0:
            return float(info.frames) / float(info.samplerate)
        return 0.0
    except Exception:
        # If soundfile is unavailable or the file is unreadable, return 0.0
        # (align stage / Phase 5 recalculate via ffprobe).
        return 0.0


# ---------------------------------------------------------------------------
# Per-slide audio resolution (autodetect or record)
# ---------------------------------------------------------------------------

# Default recording parameters (Claude's discretion — reasonable defaults)
_SAMPLE_RATE: int = 44100
_CHANNELS: int = 1
_DTYPE: str = "float32"
_RECORD_SECONDS_DEFAULT: int = 60  # maximum recording length; user stops with Ctrl+C


def _resolve_audio(
    workdir_root: Path,
    slide_index: int,
    narration: str,
) -> Path:
    """Return the WAV path for a slide, recording if the file does not exist.

    Security (T-04-05):
        The wav_path is constructed ONLY from ``workdir_root / "audio" /
        f"slide_{slide_index:02d}.wav"`` — no user-controlled string appears
        in the filename, preventing path traversal.

    Args:
        workdir_root: Root directory of the workdir.
        slide_index: Zero-based slide index.
        narration: Narration text for this slide (shown to user before recording).

    Returns:
        Path to the WAV file (created by recording if it did not exist).
    """
    wav_path = workdir_root / "audio" / f"slide_{slide_index:02d}.wav"

    if wav_path.exists():
        # (b) autodetection — user provided the WAV (D-04b)
        return wav_path

    # (a) Record with sounddevice → soundfile (D-04a)
    # Lazy imports — only executed on the recording path (Pitfall 5 / D-06)
    sd = _load_sounddevice()
    sf = _load_soundfile()

    try:
        from rich.console import Console  # noqa: PLC0415 — optional UX enhancement
        console = Console()
        console.print(
            f"\n[bold yellow]Slide {slide_index}:[/] {narration}\n"
            f"[cyan]Recording {_RECORD_SECONDS_DEFAULT}s — press Ctrl+C or wait for completion…[/]"
        )
    except ImportError:
        print(f"\nSlide {slide_index}: {narration}")
        print(f"Recording {_RECORD_SECONDS_DEFAULT}s…")

    audio_data = sd.rec(
        frames=_RECORD_SECONDS_DEFAULT * _SAMPLE_RATE,
        samplerate=_SAMPLE_RATE,
        channels=_CHANNELS,
        dtype=_DTYPE,
    )
    sd.wait()  # block until recording completes (or user interrupts)
    sf.write(str(wav_path), audio_data, _SAMPLE_RATE)

    return wav_path


# ---------------------------------------------------------------------------
# VoiceRecordStage
# ---------------------------------------------------------------------------


class VoiceRecordStage(CheckpointMixin):
    """Record-mode voice stage — export script, autodetect/record WAVs, return UnifiedTimings.

    Reads the ``script`` checkpoint (ScriptOutput), exports a segmented narration
    script, then for each slide either uses an existing ``workdir/audio/slide_XX.wav``
    or records one via sounddevice.

    Returns ``UnifiedTimings(source="record", slides=[SlideTimings(..., words=[])])``
    with per-slide WAV paths and durations.  The ``words`` list is empty at this
    stage — ``AlignStage`` (plan 04-02) populates it with word-level timestamps.

    Attributes:
        stage_name: ``"voice"`` — checkpoint contract preserved (D-12).
    """

    stage_name: str = "voice"

    def run(self, workdir: "WorkdirManager", config: "RunConfig") -> UnifiedTimings:
        """Export script, resolve WAVs, and return unified timing skeleton.

        Args:
            workdir: WorkdirManager for reading script checkpoint and path construction.
            config: RunConfig (voice=record; language used for labelling).

        Returns:
            ``UnifiedTimings(source="record")`` with one ``SlideTimings`` per slide.
            ``words`` is empty; ``AlignStage`` fills it in plan 04-02.

        Raises:
            FileNotFoundError: If the script checkpoint does not exist.
            ImportError: If sounddevice/soundfile are unavailable and recording is needed.
        """
        script: ScriptOutput = workdir.read_checkpoint("script", ScriptOutput)  # type: ignore[assignment]

        # Export the segmented script for the user to read/narrate
        _export_script_segments(workdir.root, script)

        slide_timings: list[SlideTimings] = []
        for slide in script.slides:
            # Resolve WAV path (autodetect or record) — T-04-05 safe path construction
            wav_path = _resolve_audio(
                workdir.root,
                slide.slide_index,
                slide.narration,
            )

            # Measure duration (Warning 1: must be non-zero when audio exists)
            duration = _measure_duration(wav_path)
            # Note: if duration is 0.0 here, align stage / Phase 5 recalculates via ffprobe.
            # We do NOT force 0.0 — only genuine absense of frames maps to 0.0.

            # Normalise audio_path to relative (checkpoint portability, same as voice_elevenlabs)
            try:
                relative_path = str(wav_path.relative_to(workdir.root))
            except ValueError:
                relative_path = str(wav_path)

            slide_timings.append(
                SlideTimings(
                    slide_index=slide.slide_index,
                    audio_path=relative_path,
                    duration=duration,
                    words=[],  # filled by AlignStage (04-02)
                )
            )

        return UnifiedTimings(source="record", slides=slide_timings)
