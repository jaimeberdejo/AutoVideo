"""AlignStage — forced-alignment stage (ALIGN-01 / ALIGN-02 / D-10 / D-12).

Two modes of operation selected by ``config.voice``:

ALIGN-01 (record mode):
    Reads the ``voice`` checkpoint (``UnifiedTimings(source="record")``) produced by
    ``VoiceRecordStage``.  For each slide's WAV, calls ``align_wav()`` from
    ``integrations/whisperx.py`` to run WhisperX forced-alignment.  Converts the
    resulting ``word_segments`` to ``WordTiming`` objects and updates the
    ``SlideTimings.words`` list.  Returns ``UnifiedTimings(source="whisperx")``.

ALIGN-02 (elevenlabs / openai mode):
    The ``voice`` checkpoint already contains word-level timestamps from
    ``VoiceElevenlabsStage`` or ``VoiceOpenAIStage``.  ``AlignStage`` is a
    **no-op idempotent passthrough** — it reads the voice checkpoint and
    returns it unchanged, without calling ``align_wav`` or loading any model.
    This keeps ``subtitles.py`` source-agnostic (D-11).

Design decisions:
- stage_name = "align" matches AlignStub checkpoint contract (D-12).
- ``align_wav`` is imported at **module scope** (not lazy) so that tests can
  patch ``avideo.stages.align.align_wav`` without touching the integration layer
  (mirrors storyboard.py / anthropic.py mock-point pattern).  The lazy import of
  whisperx/torch lives INSIDE ``integrations/whisperx.align_wav``, not here.
- Duration update: when align_wav returns word segments, the slide duration is
  updated to ``last_word.end`` (or the existing duration if the align result is
  empty) — guarantees non-zero duration when words exist (Warning 1).

Security (T-04-05):
  The WAV path for each slide is reconstructed from ``workdir.root / audio_path``
  where ``audio_path`` is the relative path stored in the voice checkpoint.  The
  voice checkpoint is produced by ``VoiceRecordStage`` which already enforces
  safe path construction — so no additional path traversal risk here.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from avideo.integrations.whisperx import align_wav  # module-scope: mock point for tests
from avideo.integrations.whisperx import word_segments_to_words
from avideo.models.config import VoiceMode
from avideo.models.timings import SlideTimings, UnifiedTimings
from avideo.stages.base import CheckpointMixin

if TYPE_CHECKING:
    from avideo.models.config import RunConfig
    from avideo.utils.workdir import WorkdirManager


class AlignStage(CheckpointMixin):
    """Word-level forced-alignment stage (ALIGN-01) or no-op passthrough (ALIGN-02).

    In ``record`` mode (ALIGN-01):
        Reads the ``voice`` checkpoint and for each slide runs WhisperX forced
        alignment on the slide's WAV to produce word-level timestamps.  Returns
        ``UnifiedTimings(source="whisperx")`` with populated ``words`` lists.

    In ``elevenlabs`` or ``openai`` mode (ALIGN-02):
        Returns the ``voice`` checkpoint unchanged.  Both TTS providers produce
        ``UnifiedTimings`` with word timestamps — no alignment step is needed.

    The stage does **NOT** write checkpoints — the orchestrator calls
    ``workdir.write_checkpoint("align", result)`` after ``run()`` returns.

    Attributes:
        stage_name: ``"align"`` — checkpoint contract (D-12).
    """

    stage_name: str = "align"

    def run(self, workdir: "WorkdirManager", config: "RunConfig") -> UnifiedTimings:
        """Run alignment or return voice timings unchanged.

        Args:
            workdir: WorkdirManager for reading the voice checkpoint and
                constructing WAV paths.
            config: RunConfig; ``config.voice`` selects the mode.

        Returns:
            ``UnifiedTimings(source="whisperx")`` in record mode, or the
            original ``UnifiedTimings`` unchanged in elevenlabs/openai mode.

        Raises:
            FileNotFoundError: If the voice checkpoint does not exist.
            ImportError: If whisperx is not installed and mode is record.
        """
        voice_timings: UnifiedTimings = workdir.read_checkpoint("voice", UnifiedTimings)  # type: ignore[assignment]

        if config.voice in (VoiceMode.elevenlabs, VoiceMode.openai):
            # ALIGN-02: no-op idempotent passthrough.
            # ElevenLabs and OpenAI TTS already produce word-level UnifiedTimings;
            # return as-is without calling align_wav or loading any model.
            # whisperx is NOT imported/called on this path (D-06 preserved via integration layer).
            return voice_timings

        # ALIGN-01: record mode — run WhisperX forced-alignment per slide
        aligned_slides: list[SlideTimings] = []
        for slide_timing in voice_timings.slides:
            # Reconstruct absolute WAV path from relative audio_path in checkpoint
            # (T-04-05: audio_path is stored relative by VoiceRecordStage)
            wav_path = workdir.root / slide_timing.audio_path
            wav_path_str = str(wav_path)

            # Call align_wav — module-scope import enables test patching
            word_segs = align_wav(
                wav_path_str,
                language=config.language,
                model_size=config.whisperx_model,
            )

            # Convert raw word_segments dicts → WordTiming list
            words = word_segments_to_words(word_segs)

            # Duration update: use last word's end time when words are present.
            # CRITICAL (Warning 1): must NEVER be 0.0 when words/audio exist.
            if words:
                duration = words[-1].end
                if duration <= 0.0:
                    # Guard: if last word.end is somehow 0, keep existing duration
                    duration = slide_timing.duration if slide_timing.duration > 0.0 else 0.0
            else:
                # No words returned — keep the original duration from voice stage
                duration = slide_timing.duration

            aligned_slides.append(
                SlideTimings(
                    slide_index=slide_timing.slide_index,
                    audio_path=slide_timing.audio_path,
                    duration=duration,
                    words=words,
                )
            )

        return UnifiedTimings(source="whisperx", slides=aligned_slides)
