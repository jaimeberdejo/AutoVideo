"""ElevenLabs TTS integration — client lazy singleton + convert_with_timestamps.

Design decisions implemented here:
- D-01: MODEL_ID constant — single source of truth for model selection.
- D-02: Retry ≤3 for degenerate/non-increasing timestamps (general safeguard,
  NOT a fix for bug #607 which is a speech-to-text diarisation issue, not TTS).
  The SDK already handles network retries (429/5xx) — do NOT add a network
  retry loop on top.
- D-03: Client is lazy — importing this module NEVER requires ELEVENLABS_API_KEY.
  The SDK reads the key from the environment only when the first call is made.

Security (T-04-01):
- ELEVENLABS_API_KEY is ONLY read from the environment by the SDK.
  NEVER log the key or embed it in any output/checkpoint.
  NEVER log audio_base64 in full (it may be large and contains the TTS audio).
- out_path is constructed exclusively from WorkdirManager paths (T-04-03:
  no path traversal possible because caller uses workdir.root / 'audio' /
  f'slide_{index:02d}.mp3' — no user-controlled string in the filename).
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from avideo.models.timings import SlideTimings

# ---------------------------------------------------------------------------
# Constants (D-01)
# ---------------------------------------------------------------------------

#: TTS model ID — eleven_multilingual_v2 supports Spanish and other languages.
MODEL_ID: str = "eleven_multilingual_v2"

#: Audio output format: 44.1 kHz stereo MP3 at 128 kbps.
OUTPUT_FORMAT: str = "mp3_44100_128"

# ---------------------------------------------------------------------------
# Lazy client singleton (D-03 / T-04-01)
# ---------------------------------------------------------------------------

_client = None  # type: ignore[assignment]


def _get_client():
    """Return the lazily-instantiated ElevenLabs client.

    The client is created on first call, then cached.  Importing this module
    does NOT instantiate the client and therefore does NOT require
    ELEVENLABS_API_KEY to be set — keeping --dry-run and tests import-safe.

    Security note (T-04-01): the SDK reads ELEVENLABS_API_KEY from the
    environment automatically.  NEVER log the key or pass it explicitly here.
    The SDK handles network retries (429/5xx) internally — do NOT add a
    hand-rolled retry loop for network errors on top (see RESEARCH Anti-patterns).

    Returns:
        A shared ``ElevenLabs`` SDK client instance.
    """
    global _client
    if _client is None:
        from elevenlabs import ElevenLabs  # lazy import: SDK key read from env here (D-03)

        _client = ElevenLabs()
    return _client


# ---------------------------------------------------------------------------
# Domain error
# ---------------------------------------------------------------------------


class VoiceTimestampError(Exception):
    """Raised when ElevenLabs returns degenerate timestamps after all retries.

    This is a general safeguard against non-increasing/frozen character
    timestamps, NOT a specific fix for bug #607 (which is a speech-to-text
    diarisation issue, unrelated to TTS).  See RESEARCH Pitfall 3.
    """


# ---------------------------------------------------------------------------
# Pure helper: strictly-increasing check (D-02 / T-04-02)
# ---------------------------------------------------------------------------


def is_strictly_increasing(xs: list[float]) -> bool:
    """Return True if *xs* is a strictly increasing sequence.

    Empty lists and single-element lists are vacuously increasing.

    Args:
        xs: Sequence of floats (e.g. character_start_times_seconds).

    Returns:
        True if every consecutive pair satisfies ``b > a``, else False.

    Examples:
        >>> is_strictly_increasing([0.0, 0.1, 0.25])
        True
        >>> is_strictly_increasing([0.0, 0.1, 0.1])
        False
        >>> is_strictly_increasing([])
        True
    """
    return all(b > a for a, b in zip(xs, xs[1:]))


# ---------------------------------------------------------------------------
# Word grouping helper
# ---------------------------------------------------------------------------


def _group_chars_to_words(
    characters: list[str],
    starts: list[float],
    ends: list[float],
) -> list["SlideTimings"]:  # actually list[WordTiming]
    """Group per-character timestamps into word-level timings.

    Words are delimited by whitespace characters.  The word start is the start
    of its first character; the word end is the end of its last character.

    This populates ``SlideTimings.words`` on the ElevenLabs path so that
    subtitle generation has real word-level timings (critical: must NOT be
    empty, see PLAN checklist Warning 2).

    Args:
        characters: List of characters from ``alignment.characters``.
        starts: ``alignment.character_start_times_seconds`` (SECONDS, NOT ms).
        ends: ``alignment.character_end_times_seconds`` (SECONDS, NOT ms).

    Returns:
        List of ``WordTiming`` instances, one per whitespace-delimited token.
    """
    from avideo.models.timings import WordTiming  # local import: avoids circular

    words: list[WordTiming] = []
    current_chars: list[str] = []
    current_starts: list[float] = []
    current_ends: list[float] = []

    def _flush() -> None:
        if current_chars:
            words.append(
                WordTiming(
                    text="".join(current_chars),
                    start=current_starts[0],
                    end=current_ends[-1],
                )
            )
            current_chars.clear()
            current_starts.clear()
            current_ends.clear()

    for char, start, end in zip(characters, starts, ends):
        if char == " " or char == "\t":
            _flush()
        else:
            current_chars.append(char)
            current_starts.append(start)
            current_ends.append(end)

    _flush()
    return words


# ---------------------------------------------------------------------------
# Core function: synthesize_slide
# ---------------------------------------------------------------------------


def synthesize_slide(
    *,
    text: str,
    slide_index: int,
    voice_id: str,
    out_path: Path,
    model_id: str = MODEL_ID,
    output_format: str = OUTPUT_FORMAT,
) -> "SlideTimings":
    """Synthesize narration for one slide and return its timing data.

    Calls ``client.text_to_speech.convert_with_timestamps()`` and validates
    that the returned character timestamps are strictly increasing (T-04-02).
    If not, retries up to 3 times total.  If all attempts produce degenerate
    timestamps, raises ``VoiceTimestampError`` with a clear message.

    The retry loop is ONLY for timestamp validation failures — it does NOT
    wrap network errors (the SDK already handles 429/5xx retries, D-02 /
    RESEARCH Anti-patterns).

    Args:
        text: Narration text for this slide (from ScriptOutput.slides[i].narration).
        slide_index: Zero-based slide index; stored in the returned SlideTimings.
        voice_id: ElevenLabs voice ID (from RunConfig.voice_id).
        out_path: Absolute path where the MP3 file is written.
            Must be constructed by the caller via WorkdirManager to avoid
            path traversal (T-04-03).
        model_id: TTS model.  Defaults to ``eleven_multilingual_v2`` (D-01).
        output_format: Audio encoding.  Defaults to ``mp3_44100_128``.

    Returns:
        A ``SlideTimings`` with:
        - ``slide_index`` set to *slide_index*.
        - ``audio_path`` set to ``str(out_path)``.
        - ``duration`` set to the last ``character_end_times_seconds`` value
          (or 0.0 if no characters returned).
        - ``words`` populated by grouping per-character timestamps into words
          (split on whitespace).  Never empty when characters exist.

    Raises:
        VoiceTimestampError: If all 3 synthesis attempts return non-increasing
            character timestamps.  This is a general safeguard against
            degenerate/frozen timestamps — see RESEARCH Pitfall 3.
        Any exception raised by the SDK (e.g. network errors) propagates
            immediately without retry (the SDK retries internally).
    """
    from avideo.models.timings import SlideTimings  # local import: avoids circular

    for attempt in range(3):  # D-02: retry ≤3, timestamp validation only
        resp = _get_client().text_to_speech.convert_with_timestamps(
            voice_id=voice_id,
            text=text,
            model_id=model_id,
            output_format=output_format,
        )

        # Read SECONDS fields — NOT the obsolete _ms fields (SDK 1.x). Pitfall 1.
        starts: list[float] = resp.alignment.character_start_times_seconds
        ends: list[float] = resp.alignment.character_end_times_seconds
        characters: list[str] = resp.alignment.characters

        if is_strictly_increasing(starts):
            # Write audio to filesystem (T-04-03: out_path is caller-controlled)
            out_path.write_bytes(base64.b64decode(resp.audio_base64))

            # Duration = last character end time (or 0.0 if no characters)
            duration = ends[-1] if ends else 0.0

            # Group per-character timestamps into words (Warning 2: must not be empty)
            words = _group_chars_to_words(characters, starts, ends)

            return SlideTimings(
                slide_index=slide_index,
                audio_path=str(out_path),
                duration=duration,
                words=words,
            )

        # Non-increasing timestamps — retry (D-02 safeguard)

    # All 3 attempts exhausted — raise domain error with clear message
    raise VoiceTimestampError(
        f"ElevenLabs returned degenerate/frozen timestamps for slide {slide_index} "
        f"after 3 synthesis attempts.  This is a general timestamp safeguard "
        f"(not a specific bug fix).  character_start_times_seconds was not strictly "
        f"increasing across all retry attempts.  Check ElevenLabs API status or "
        f"try a different voice_id / model_id."
    )
