"""WhisperX forced-alignment integration — LAZY import (D-06).

This module provides ``align_wav()`` which runs WhisperX forced alignment on a
single WAV file to produce word-level timestamps.

CRITICAL — Lazy import design (D-06):
    ``import whisperx`` and ``import torch`` are placed INSIDE the function body,
    NOT at module top level.  This guarantees that importing this module does NOT
    require whisperx or torch to be installed.  The default ``elevenlabs`` path
    never touches whisperx — only ``record`` mode triggers the import.

    Importing this module without the ``record`` extra installed is safe:
        >>> import avideo.integrations.whisperx   # always OK
        >>> avideo.integrations.whisperx.align_wav("x.wav")  # fails with clear ImportError

CPU / compute type (D-05):
    The default compute type is ``"int8"`` on CPU, which is portable (no CUDA),
    fast enough for the ``small`` model, and supported by faster-whisper
    (the CTranslate2 backend underlying WhisperX).

torch pin (Pitfall 2):
    torch >=2.6 changes ``torch.load`` to ``weights_only=True`` by default, which
    breaks the pyannote VAD checkpoint loaded by ``whisperx.load_model()``.
    The recommended mitigation is to pre-install ``torch==2.5.1`` before
    ``whisperx`` (see RESEARCH.md Pitfall 2).  Install command:
        pip install torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cpu
    Alternative (verify before using): ``load_model(..., vad_method="silero")``
    avoids pyannote VAD entirely — check that whisperx 3.8.x accepts the parameter
    at runtime (Assumption A2).

No diarization:
    This module does NOT use diarisation (no ``pyannote.audio`` token required).
    ``load_model`` loads pyannote VAD only; with torch 2.5.1 this is safe.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from avideo.models.timings import WordTiming


# ---------------------------------------------------------------------------
# Pure helper: word_segments dict list → WordTiming list
# ---------------------------------------------------------------------------


def word_segments_to_words(segments: list[dict]) -> list["WordTiming"]:
    """Convert a WhisperX ``word_segments`` list to a list of ``WordTiming`` instances.

    Each segment dict contains ``{"word": str, "start": float, "end": float}``
    where ``start``/``end`` are in **seconds relative to the beginning of the WAV
    clip** (NOT global timeline timestamps — see models/timings.py coordinate
    system note).

    This is a **pure** function — no I/O, no external dependencies.

    Args:
        segments: List of word-segment dicts as returned by
            ``whisperx.align()["word_segments"]``.  Each dict must have
            ``"word"`` (str), ``"start"`` (float), ``"end"`` (float).
            Segments with missing ``start``/``end`` are skipped (WhisperX may
            return segments without alignment for very short words).

    Returns:
        List of ``WordTiming`` instances, one per segment that has timing data.
    """
    from avideo.models.timings import WordTiming  # local to avoid circular imports

    words: list[WordTiming] = []
    for seg in segments:
        start = seg.get("start")
        end = seg.get("end")
        if start is None or end is None:
            # WhisperX occasionally returns word_segments without alignment;
            # skip rather than fail (the subtitle stage handles sparse words gracefully).
            continue
        words.append(
            WordTiming(
                text=seg["word"],
                start=float(start),
                end=float(end),
            )
        )
    return words


# ---------------------------------------------------------------------------
# Core function: align_wav (lazy import of whisperx/torch inside function body)
# ---------------------------------------------------------------------------


def align_wav(
    wav_path: str,
    language: str = "es",
    model_size: str = "small",
) -> list[dict]:
    """Align a WAV file using WhisperX forced-alignment and return word segments.

    Runs the full WhisperX pipeline on ``wav_path``:
    1. ``whisperx.load_model`` — loads faster-whisper + VAD (CPU int8).
    2. ``model.transcribe`` — ASR transcription.
    3. ``whisperx.load_align_model`` — loads wav2vec2 alignment model for
       the given language.
    4. ``whisperx.align`` — forced alignment → word-level timestamps.

    **Lazy import:** ``whisperx`` (and ``torch`` if needed) are imported INSIDE
    this function body, never at module top level (D-06).  The module is
    import-safe even without the ``record`` extra installed.

    Args:
        wav_path: Absolute or workdir-relative path to the WAV file.
            Must be constructed via WorkdirManager (T-04-05: no path traversal).
        language: BCP-47 language code for alignment model.  Default ``"es"``
            (Spanish — ``wav2vec2-large-xlsr-53-spanish`` from torchaudio).
        model_size: WhisperX model size passed to ``load_model``.  Default
            ``"small"`` (balances speed vs. accuracy on CPU; use ``"large-v3"``
            on GPU for best results — configurable via ``RunConfig.whisperx_model``).

    Returns:
        List of word-segment dicts as returned by
        ``whisperx.align()["word_segments"]``.  Each dict has at minimum
        ``{"word": str, "start": float, "end": float}`` (start/end in
        **seconds**, relative to the start of the WAV clip).

    Raises:
        ImportError: If ``whisperx`` is not installed.  Message includes the
            install command so the user knows to run
            ``uv sync --extra record`` (with torch 2.5.1 pre-installed).
        Any exception raised by whisperx (e.g. model load errors) propagates
            without wrapping so the caller sees the original error.

    Note on torch compatibility (Pitfall 2):
        With torch >=2.6, ``whisperx.load_model`` may fail with
        ``_pickle.UnpicklingError: Weights only load failed`` when loading the
        pyannote VAD checkpoint.  Pin ``torch==2.5.1`` before ``whisperx``
        (see module docstring).  As a runtime fallback, try
        ``load_model(..., vad_method="silero")`` if available.
    """
    try:
        import whisperx  # noqa: PLC0415 — D-06: lazy import; MUST be inside the function
    except ImportError as exc:
        raise ImportError(
            "Voice mode 'record' requires the optional 'record' extra with whisperx. "
            "Install with: uv sync --extra record  "
            "(pre-install torch==2.5.1 first; see 04-RESEARCH.md Pitfall 2 and module docstring). "
            f"Original error: {exc}"
        ) from exc

    device: str = "cpu"
    compute_type: str = "int8"  # portable / CI; use "float16" for GPU runs

    model = whisperx.load_model(
        model_size,
        device,
        compute_type=compute_type,
        language=language,
    )

    audio = whisperx.load_audio(wav_path)
    result = model.transcribe(audio, batch_size=16)

    model_a, metadata = whisperx.load_align_model(
        language_code=language,
        device=device,
    )
    aligned = whisperx.align(
        result["segments"],
        model_a,
        metadata,
        audio,
        device,
        return_char_alignments=False,
    )

    return aligned["word_segments"]
