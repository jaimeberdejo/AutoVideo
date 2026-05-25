"""VoiceElevenlabsStage — per-slide TTS synthesis using ElevenLabs.

Reads the script checkpoint (ScriptOutput), calls synthesize_slide once per
slide, and returns a UnifiedTimings(source="elevenlabs") containing per-slide
audio paths, durations, and word-level timestamps.

Design decisions:
- D-01/D-03: Uses MODEL_ID=eleven_multilingual_v2; ELEVENLABS_API_KEY from env.
- D-10/D-12: stage_name="voice" preserves the checkpoint contract (VoiceStub used
  the same name); the orchestrator writes the checkpoint and marks done.
- Mock point: synthesize_slide is imported at module scope so tests can patch
  ``avideo.stages.voice_elevenlabs.synthesize_slide`` without touching the
  integration layer (mirrors the storyboard.py / anthropic.py pattern).

Security:
- out_path is constructed from workdir.root / "audio" / f"slide_{index:02d}.mp3"
  — no user-controlled string in the filename (T-04-03: no path traversal).
- The stage does NOT write checkpoints — that is the orchestrator's responsibility.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from avideo.integrations.elevenlabs import synthesize_slide  # module-scope mock point
from avideo.models.script import ScriptOutput
from avideo.models.timings import UnifiedTimings
from avideo.stages.base import CheckpointMixin

if TYPE_CHECKING:
    from avideo.models.config import RunConfig
    from avideo.utils.workdir import WorkdirManager


class VoiceElevenlabsStage(CheckpointMixin):
    """Per-slide ElevenLabs TTS stage producing UnifiedTimings.

    For each slide in the script checkpoint, calls ``synthesize_slide()`` to:
      - synthesize the narration via ElevenLabs ``convert_with_timestamps``
      - validate that timestamps are strictly increasing (retry ≤3 in integration)
      - write the decoded MP3 to ``workdir/audio/slide_XX.mp3``

    Returns ``UnifiedTimings(source="elevenlabs", slides=[...])`` with one
    ``SlideTimings`` per slide.  Words are populated from per-character timestamps
    (never empty when characters exist — required for subtitle generation).

    The stage does NOT write checkpoints; the orchestrator calls
    ``workdir.write_checkpoint("voice", result)`` after this method returns.

    Attributes:
        stage_name: ``"voice"`` — preserves workdir checkpoint contract (D-12).
    """

    stage_name: str = "voice"

    def run(self, workdir: "WorkdirManager", config: "RunConfig") -> UnifiedTimings:
        """Synthesize narration for all slides and return unified timing data.

        Args:
            workdir: WorkdirManager for reading the script checkpoint and
                constructing audio output paths.
            config: RunConfig with voice_id and other pipeline parameters.

        Returns:
            ``UnifiedTimings(source="elevenlabs")`` with one ``SlideTimings``
            per slide.

        Raises:
            FileNotFoundError: If the script checkpoint does not exist.
            VoiceTimestampError: If ElevenLabs returns degenerate timestamps
                after 3 attempts for any slide.
        """
        script: ScriptOutput = workdir.read_checkpoint("script", ScriptOutput)  # type: ignore[assignment]

        slide_timings = []
        for slide in script.slides:
            # T-04-03: out_path constructed solely from workdir root + fixed template
            # — no user-controlled string in the filename.
            out_path = (
                workdir.root / "audio" / f"slide_{slide.slide_index:02d}.mp3"
            )
            timing = synthesize_slide(
                text=slide.narration,
                slide_index=slide.slide_index,
                voice_id=config.voice_id,
                out_path=out_path,
            )
            # Normalise audio_path to be relative to workdir.root for portability
            # (checkpoint may be moved/shared across machines).
            try:
                relative = str(out_path.relative_to(workdir.root))
            except ValueError:
                relative = str(out_path)  # fallback if out_path is not under root
            timing = timing.model_copy(update={"audio_path": relative})

            slide_timings.append(timing)

        return UnifiedTimings(source="elevenlabs", slides=slide_timings)
