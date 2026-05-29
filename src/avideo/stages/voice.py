"""VoiceStage — dispatcher that selects the voice backend by config.voice.

A single stage with ``stage_name="voice"`` dispatches internally to either
``VoiceElevenlabsStage`` or ``VoiceRecordStage`` based on ``config.voice``.
This design (Option A from RESEARCH Open Question 3) keeps the checkpoint
contract intact and avoids routing logic in the orchestrator.

Design decisions:
- D-12: stage_name="voice" matches VoiceStub — checkpoint file stays "voice.json".
- D-06: VoiceRecordStage is imported lazily (inside the record branch) to avoid
  importing whisperx/torch when using the default elevenlabs mode.
- ALIGN-02: In elevenlabs mode, the voice stage already produces UnifiedTimings —
  the align stage is a no-op (04-02/04-03 implement this).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from avideo.models.config import VoiceMode
from avideo.models.timings import UnifiedTimings
from avideo.stages.base import CheckpointMixin
from avideo.stages.voice_elevenlabs import VoiceElevenlabsStage

if TYPE_CHECKING:
    from avideo.models.config import RunConfig
    from avideo.utils.workdir import WorkdirManager


class VoiceStage(CheckpointMixin):
    """Dispatcher voice stage — selects backend by RunConfig.voice (D-12).

    Always presents ``stage_name="voice"`` to the orchestrator so the
    checkpoint contract is unchanged regardless of the selected backend.

    Attributes:
        stage_name: ``"voice"`` — checkpoint contract; matches VoiceStub.
    """

    stage_name: str = "voice"

    def run(self, workdir: "WorkdirManager", config: "RunConfig") -> UnifiedTimings:
        """Dispatch to the appropriate voice backend and return UnifiedTimings.

        Args:
            workdir: WorkdirManager for filesystem operations.
            config: RunConfig; ``config.voice`` selects the backend.

        Returns:
            UnifiedTimings from the selected backend.

        Raises:
            ImportError: If mode is ``record`` and the record extra is not
                installed.  Install with: ``uv sync --extra record``.
            NotImplementedError: If an unknown VoiceMode value is encountered.
        """
        if config.voice == VoiceMode.elevenlabs:
            return VoiceElevenlabsStage().run(workdir, config)

        if config.voice == VoiceMode.record:
            # D-06: lazy import of whisperx/sounddevice deps; only loaded in record mode.
            # VoiceRecordStage is implemented in plan 04-02.
            try:
                from avideo.stages.voice_record import VoiceRecordStage  # noqa: PLC0415
            except ImportError as exc:
                raise ImportError(
                    "Voice mode 'record' requires the optional 'record' extra. "
                    "Install with: uv sync --extra record  "
                    "(needs torch==2.5.1 pre-installed; see 04-RESEARCH.md Pitfall 2). "
                    f"Original error: {exc}"
                ) from exc
            return VoiceRecordStage().run(workdir, config)

        if config.voice == VoiceMode.openai:
            from avideo.stages.voice_openai import VoiceOpenAIStage  # noqa: PLC0415 — lazy: avoids openai import at module load
            return VoiceOpenAIStage().run(workdir, config)

        raise NotImplementedError(f"Unknown voice mode: {config.voice!r}")
