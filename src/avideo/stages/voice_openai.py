"""VoiceOpenAIStage — per-slide TTS synthesis using OpenAI Audio (VOZ-02).

Reads the script checkpoint (ScriptOutput), calls synthesize_slide_openai
and transcribe_slide_openai once per slide, and returns a
UnifiedTimings(source="openai") containing per-slide audio paths, durations,
and word-level timestamps.

The two-call pattern per slide (synthesize → STT round-trip) is required because
OpenAI Audio TTS returns NO timestamps. The mandatory whisper-1 STT round-trip
produces word-level timestamps to fulfil the same UnifiedTimings contract as
VoiceElevenlabsStage and VoiceRecordStage. See RESEARCH Pitfall 17 for why
whisper-1 is hard-coded (gpt-4o-transcribe does not support word timestamps).

Design decisions:
- D-12: stage_name="voice" preserves the checkpoint contract (same as
  VoiceElevenlabsStage); the orchestrator writes the checkpoint and marks done.
- T-08-03-02: out_path constructed solely from workdir.root + fixed template
  "audio/slide_{N:02d}.mp3" — no user-controlled string in the filename.

Mock points (for tests — module-scope imports so patching hits the stage namespace):
  avideo.stages.voice_openai.synthesize_slide_openai
  avideo.stages.voice_openai.transcribe_slide_openai

Security:
- out_path is constructed from workdir.root / "audio" / f"slide_{index:02d}.mp3"
  — no user-controlled string in the filename (T-08-03-02: no path traversal).
- The stage does NOT write checkpoints — that is the orchestrator's responsibility.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from avideo.integrations.openai import (  # module-scope: mock seam for tests
    synthesize_slide_openai,
    transcribe_slide_openai,
)
from avideo.models.script import ScriptOutput
from avideo.models.timings import UnifiedTimings
from avideo.stages.base import CheckpointMixin

if TYPE_CHECKING:
    from avideo.models.config import RunConfig
    from avideo.utils.workdir import WorkdirManager


class VoiceOpenAIStage(CheckpointMixin):
    """Per-slide OpenAI Audio TTS stage producing UnifiedTimings (VOZ-02).

    For each slide in the script checkpoint:
      1. Calls ``synthesize_slide_openai()`` to synthesize narration via OpenAI
         Audio TTS (model=config.openai_tts_model, voice=config.openai_tts_voice)
         and write the MP3 to ``workdir/audio/slide_XX.mp3``.
      2. Calls ``transcribe_slide_openai()`` to perform a whisper-1 STT round-trip
         on the generated audio, producing word-level timestamps.

    Returns ``UnifiedTimings(source="openai", slides=[...])`` with one
    ``SlideTimings`` per slide. Audio paths are stored workdir-relative for
    checkpoint portability.

    The stage does NOT write checkpoints; the orchestrator calls
    ``workdir.write_checkpoint("voice", result)`` after this method returns.

    Attributes:
        stage_name: ``"voice"`` — preserves workdir checkpoint contract (D-12).
            CRITICAL: must match VoiceElevenlabsStage.stage_name exactly.
    """

    stage_name: str = "voice"

    def run(self, workdir: "WorkdirManager", config: "RunConfig") -> UnifiedTimings:
        """Synthesize narration for all slides and return unified timing data.

        Args:
            workdir: WorkdirManager for reading the script checkpoint and
                constructing audio output paths.
            config: RunConfig with openai_tts_model and openai_tts_voice parameters.

        Returns:
            ``UnifiedTimings(source="openai")`` with one ``SlideTimings``
            per slide, word-level timestamps populated from whisper-1.

        Raises:
            FileNotFoundError: If the script checkpoint does not exist.
            ValueError: If any slide's narration exceeds 4096 chars
                (enforced in synthesize_slide_openai).
        """
        script: ScriptOutput = workdir.read_checkpoint("script", ScriptOutput)  # type: ignore[assignment]

        slide_timings = []
        for slide in script.slides:
            # T-08-03-02: out_path constructed solely from workdir root + fixed template
            # — no user-controlled string in the filename.
            out_path = workdir.root / "audio" / f"slide_{slide.slide_index:02d}.mp3"
            out_path.parent.mkdir(parents=True, exist_ok=True)

            # Step 1: Synthesize narration to MP3 via OpenAI Audio TTS
            synthesize_slide_openai(
                text=slide.narration,
                slide_index=slide.slide_index,
                model=config.openai_tts_model,
                voice=config.openai_tts_voice,
                out_path=out_path,
            )

            # Step 2: STT round-trip for word-level timestamps (whisper-1)
            timing = transcribe_slide_openai(
                audio_path=out_path,
                slide_index=slide.slide_index,
            )

            # Normalise audio_path to be relative to workdir.root for portability
            # (checkpoint may be moved/shared across machines — mirrors elevenlabs.py).
            try:
                relative = str(out_path.relative_to(workdir.root))
            except ValueError:
                relative = str(out_path)  # fallback if out_path is not under root
            timing = timing.model_copy(update={"audio_path": relative})

            slide_timings.append(timing)

        return UnifiedTimings(source="openai", slides=slide_timings)
