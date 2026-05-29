"""OpenAI Audio integration — TTS synthesis + whisper-1 STT round-trip (VOZ-02).

Provides:
  - synthesize_slide_openai(): one MP3 per slide via openai.audio.speech.create
  - transcribe_slide_openai(): word-level timestamps via openai.audio.transcriptions.create

Design decisions:
- Lazy client singleton (mirrors elevenlabs.py D-03): importing this module does NOT
  require OPENAI_API_KEY. The SDK reads the key from the environment only when the
  first call is made.
- max_retries=3: explicit retry parameter (the openai SDK does NOT add retries by
  default, unlike the ElevenLabs SDK which handles 429/5xx internally).
- 4096-char guard (T-08-03-03): raises ValueError before the API call; the storyboard
  WPM budget (150 WPM × max 60s = 1500 chars) keeps slides well under this limit,
  but the guard catches misconfiguration.
- whisper-1 hard-coded in transcribe_slide_openai (T-08-03-04): gpt-4o-transcribe
  does NOT support word-level timestamps (Pitfall 17 in PITFALLS.md). Making the model
  configurable would silently break subtitle generation.

Security (T-08-03-01):
- OPENAI_API_KEY is ONLY read from the environment by the SDK.
  NEVER log the key or embed it in any output/checkpoint.
- Client is lazy — importing this module NEVER requires OPENAI_API_KEY.
  The SDK reads the key from the environment only when the first call is made.

Mock point (for tests):
  avideo.integrations.openai._get_client
    — patch this to inject a mock OpenAI client without OPENAI_API_KEY.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from avideo.models.timings import SlideTimings

# ---------------------------------------------------------------------------
# Lazy client singleton (D-03 / T-08-03-01)
# ---------------------------------------------------------------------------

_client = None  # type: ignore[assignment]


def _get_client():
    """Return the lazily-instantiated OpenAI client.

    The client is created on first call, then cached. Importing this module
    does NOT instantiate the client and therefore does NOT require
    OPENAI_API_KEY to be set — keeping dry-run and tests import-safe.

    Security note (T-08-03-01): the SDK reads OPENAI_API_KEY from the
    environment automatically. NEVER log the key or pass it explicitly here.
    max_retries=3 is set explicitly because the openai SDK defaults to 0
    (unlike the ElevenLabs SDK which handles retries internally).

    Returns:
        A shared ``OpenAI`` SDK client instance.
    """
    global _client
    if _client is None:
        from openai import OpenAI  # lazy import — key read from env only here

        _client = OpenAI(max_retries=3)
    return _client


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def synthesize_slide_openai(
    *,
    text: str,
    slide_index: int,
    model: str,
    voice: str,
    out_path: Path,
) -> Path:
    """Synthesize one slide's narration via OpenAI Audio TTS.

    Enforces the 4096-char per-request limit (T-08-03-03). Raises ValueError
    if text exceeds 4096 characters — the storyboard WPM budget keeps slides
    well under this limit in practice, but the guard catches misconfiguration.

    Writes raw MP3 bytes to out_path via response.stream_to_file(). The caller
    is responsible for creating the parent directory (workdir/audio/).

    Args:
        text: Narration text for this slide (<= 4096 chars enforced here).
        slide_index: Slide index (zero-based); used only in the error message.
        model: OpenAI TTS model id (e.g. "tts-1" or "gpt-4o-mini-tts").
        voice: Voice name (e.g. "alloy", "echo", "fable", "onyx", "nova", "shimmer").
        out_path: Destination MP3 path. Must be constructed by the caller via
            WorkdirManager to avoid path traversal (T-08-03-02).

    Returns:
        out_path (written to disk).

    Raises:
        ValueError: If text exceeds 4096 characters.
        Any exception from the OpenAI SDK (network errors, auth errors) propagates
        immediately.
    """
    if len(text) > 4096:
        raise ValueError(
            f"Slide {slide_index} text is {len(text)} chars; OpenAI TTS limit is 4096. "
            "The storyboard WPM budget (150 WPM × max 60s = 1500 chars) should keep slides "
            "well under this limit. Check the script output for unexpectedly long narrations."
        )
    response = _get_client().audio.speech.create(
        model=model,
        voice=voice,
        input=text,
        response_format="mp3",
    )
    response.stream_to_file(str(out_path))
    return out_path


def transcribe_slide_openai(
    *,
    audio_path: Path,
    slide_index: int,
) -> "SlideTimings":
    """STT round-trip on the generated audio to obtain word-level timestamps.

    Uses whisper-1 with verbose_json + word granularity to produce word-level
    timestamps from the synthesized MP3. The model is hard-coded to "whisper-1"
    because gpt-4o-transcribe does NOT support word-level timestamps (T-08-03-04
    / Pitfall 17 in PITFALLS.md) — making it configurable would silently break
    subtitle generation.

    Args:
        audio_path: Path to the synthesized MP3 for this slide (written by
            synthesize_slide_openai).
        slide_index: Slide index (zero-based); stored in the returned SlideTimings.

    Returns:
        SlideTimings with:
        - ``slide_index`` set to *slide_index*.
        - ``audio_path`` set to ``str(audio_path)`` (normalised to relative by caller).
        - ``duration`` set to the last word's end time (or 0.0 if no words returned).
        - ``words`` populated from whisper-1 word objects (``w.word``, ``w.start``,
          ``w.end``).
    """
    from avideo.models.timings import SlideTimings, WordTiming  # noqa: PLC0415

    with open(audio_path, "rb") as f:
        result = _get_client().audio.transcriptions.create(
            file=f,
            model="whisper-1",                         # MUST be whisper-1; not gpt-4o-transcribe (T-08-03-04)
            response_format="verbose_json",
            timestamp_granularities=["word"],
        )
    words = [
        WordTiming(text=w.word, start=w.start, end=w.end)
        for w in (result.words or [])
    ]
    duration = words[-1].end if words else 0.0
    return SlideTimings(
        slide_index=slide_index,
        audio_path=str(audio_path),
        duration=duration,
        words=words,
    )
