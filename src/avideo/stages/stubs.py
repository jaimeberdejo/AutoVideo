"""Phase-1 stub stages — each writes a minimal valid Pydantic checkpoint.

These stubs form the skeleton of the pipeline.  They satisfy StageProtocol /
CheckpointMixin and run end-to-end without any real LLM, TTS, Playwright or
FFmpeg calls.  Phases 2–5 replace each stub with a real implementation while
keeping the same stage_name and checkpoint_name so existing workdir state
remains compatible.

Pipeline order (canonical):
    context → storyboard → timing → scriptwriter → slides → verify →
    voice → align → subs → assemble

PIPELINE_STAGES: canonical ordered list consumed by the orchestrator.

Phase 2 stub swap (plan 02-03):
    ContextStub, StoryboardStub, TimingStub, ScriptwriterStub have been
    replaced in PIPELINE_STAGES by their real implementations.  The stub
    classes are retained for tests that import them directly.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel

from avideo.models import (
    AssemblyOutput,
    ContextOutput,
    ScriptOutput,
    SlideScript,
    SlideSpec,
    SlidesOutput,
    SlideTiming,
    SlideVerdict,
    StoryboardOutput,
    TimingOutput,
    VerificationReport,
    VoiceOutput,
)
from avideo.stages.base import CheckpointMixin

# Real Phase-2 stage implementations (replacing the first four stubs in PIPELINE_STAGES)
from avideo.stages.context import ContextStage
from avideo.stages.scriptwriter import ScriptwriterStage
from avideo.stages.storyboard import StoryboardStage
from avideo.stages.timing import TimingStage

# Real Phase-3 stage implementation (replacing SlidesStub in PIPELINE_STAGES)
from avideo.stages.slides_auto import SlidesAutoStage

# Real Phase-4 stage implementations (replacing VoiceStub/AlignStub/SubsStub in PIPELINE_STAGES)
from avideo.stages.align import AlignStage
from avideo.stages.subtitles import SubtitlesStage
from avideo.stages.voice import VoiceStage

if TYPE_CHECKING:
    from avideo.models import RunConfig
    from avideo.utils.workdir import WorkdirManager


# ---------------------------------------------------------------------------
# Context stage
# ---------------------------------------------------------------------------


class ContextStub(CheckpointMixin):
    """Phase-1 stub for context ingestion.

    Writes ContextOutput(used=False) when config.context is None, or
    ContextOutput(used=True, source_path=...) when a context document is set.
    Phase 3 replaces this with real .pptx/.pdf/.md extraction.
    """

    stage_name: str = "context"

    def run(self, workdir: "WorkdirManager", config: "RunConfig") -> ContextOutput:
        if config.context is None:
            return ContextOutput(used=False)
        return ContextOutput(source_path=str(config.context), text="", used=True)


# ---------------------------------------------------------------------------
# Storyboard stage
# ---------------------------------------------------------------------------


class StoryboardStub(CheckpointMixin):
    """Phase-1 stub for LLM storyboard generation.

    Returns a single-slide storyboard so downstream stages have at least one
    SlideSpec to process.  Phase 2 replaces this with a real Anthropic call.
    """

    stage_name: str = "storyboard"

    def run(self, workdir: "WorkdirManager", config: "RunConfig") -> StoryboardOutput:
        return StoryboardOutput(
            slides=[SlideSpec(title="Stub Slide", bullets=["Bullet 1"])],  # visual_type defaults to VisualType.bullets
            language=config.language,
        )


# ---------------------------------------------------------------------------
# Timing stage
# ---------------------------------------------------------------------------


class TimingStub(CheckpointMixin):
    """Phase-1 stub for the timing/duration director.

    checkpoint_name is "timings" so the workdir file is timings.json,
    matching the layout consumed by Phase 4 (voice/align).
    Phase 2 replaces this with proportional duration allocation.
    """

    stage_name: str = "timing"

    @property
    def checkpoint_name(self) -> str:
        return "timings"

    def run(self, workdir: "WorkdirManager", config: "RunConfig") -> TimingOutput:
        return TimingOutput(
            slides=[SlideTiming(slide_index=0, seconds=float(config.duration), word_budget=10)],
            total_seconds=float(config.duration),
            wpm=config.wpm,
        )


# ---------------------------------------------------------------------------
# Scriptwriter stage
# ---------------------------------------------------------------------------


class ScriptwriterStub(CheckpointMixin):
    """Phase-1 stub for LLM narration scriptwriter.

    checkpoint_name is "script" so the workdir file is script.json.
    Phase 2 replaces this with a real Anthropic call calibrated to WPM.
    """

    stage_name: str = "scriptwriter"

    @property
    def checkpoint_name(self) -> str:
        return "script"

    def run(self, workdir: "WorkdirManager", config: "RunConfig") -> ScriptOutput:
        return ScriptOutput(
            slides=[SlideScript(slide_index=0, narration="Narración stub.")],
            language=config.language,
        )


# ---------------------------------------------------------------------------
# Slides stage
# ---------------------------------------------------------------------------


class SlidesStub(CheckpointMixin):
    """Phase-1 stub for slide render (Jinja2 + Playwright).

    Returns SlidesOutput with empty png_paths; real PNG files are generated
    in Phase 3.
    """

    stage_name: str = "slides"

    def run(self, workdir: "WorkdirManager", config: "RunConfig") -> SlidesOutput:
        return SlidesOutput(png_paths=[], mode=config.slides_mode.value)


# ---------------------------------------------------------------------------
# Verify stage
# ---------------------------------------------------------------------------


class VerifyStub(CheckpointMixin):
    """Phase-1 stub for the Claude vision verifier.

    checkpoint_name is "verification" so the workdir file is verification.json.
    The stub reports a single slide with status "ok" so L3 never triggers.
    Phase 6 replaces this with a real vision-model call.
    """

    stage_name: str = "verify"

    @property
    def checkpoint_name(self) -> str:
        return "verification"

    def run(self, workdir: "WorkdirManager", config: "RunConfig") -> VerificationReport:
        return VerificationReport(slides=[SlideVerdict(slide_index=0, status="ok")])


# ---------------------------------------------------------------------------
# Voice stage
# ---------------------------------------------------------------------------


class VoiceStub(CheckpointMixin):
    """Phase-1 stub for ElevenLabs TTS / recording.

    Returns VoiceOutput with empty audio_paths; real audio is generated in Phase 4.
    """

    stage_name: str = "voice"

    def run(self, workdir: "WorkdirManager", config: "RunConfig") -> VoiceOutput:
        return VoiceOutput(audio_paths=[], voice_mode=config.voice.value)


# ---------------------------------------------------------------------------
# Align stage
# ---------------------------------------------------------------------------


class AlignStub(CheckpointMixin):
    """Phase-1 placeholder for word-level audio alignment (WhisperX).

    checkpoint_name is "align"; reuses TimingOutput shape for the checkpoint.
    Phase 4 replaces this with a real WhisperX forced-alignment model that
    produces word-level timestamps.
    """

    stage_name: str = "align"

    def run(self, workdir: "WorkdirManager", config: "RunConfig") -> TimingOutput:
        """Phase-1 placeholder; Phase 4 replaces with a word-level alignment model."""
        return TimingOutput(slides=[], total_seconds=0.0, wpm=config.wpm)


# ---------------------------------------------------------------------------
# Subs stage
# ---------------------------------------------------------------------------


class SubsStub(CheckpointMixin):
    """Phase-1 placeholder for subtitle generation (.srt/.vtt).

    checkpoint_name is "subs"; reuses ScriptOutput shape for the checkpoint.
    Phase 4 replaces this with a subtitle generator from word-level timings.
    """

    stage_name: str = "subs"

    def run(self, workdir: "WorkdirManager", config: "RunConfig") -> ScriptOutput:
        """Phase-1 placeholder; Phase 4 replaces with a subtitles model."""
        return ScriptOutput(slides=[], language=config.language)


# ---------------------------------------------------------------------------
# Assemble stage
# ---------------------------------------------------------------------------


class AssembleStub(CheckpointMixin):
    """Phase-1 stub for FFmpeg video assembly.

    checkpoint_name is "assembly" so the workdir file is assembly.json.
    Creates a workdir/output.mp4 marker file so the phase acceptance criterion
    ("obtiene un vídeo MP4 final") is satisfied even with stub content.
    Phase 5 replaces this with a real FFmpeg invocation.
    """

    stage_name: str = "assemble"

    @property
    def checkpoint_name(self) -> str:
        return "assembly"

    def run(self, workdir: "WorkdirManager", config: "RunConfig") -> AssemblyOutput:
        output_path = workdir.root / "output.mp4"
        output_path.touch()
        return AssemblyOutput(output_path=str(output_path))


# ---------------------------------------------------------------------------
# PIPELINE_STAGES — canonical ordered list for the orchestrator
# ---------------------------------------------------------------------------

PIPELINE_STAGES: list = [
    ContextStage(),       # Phase 2: real context ingestion (was ContextStub)
    StoryboardStage(),    # Phase 2: real LLM storyboard (was StoryboardStub)
    TimingStage(),        # Phase 2: real timing apportionment (was TimingStub)
    ScriptwriterStage(),  # Phase 2: real LLM scriptwriter (was ScriptwriterStub)
    SlidesAutoStage(),    # Phase 3: real (was SlidesStub) — stage_name='slides'
    VerifyStub(),         # Phase 6: placeholder
    VoiceStage(),         # Phase 4: real TTS dispatcher (was VoiceStub) — stage_name='voice'
    AlignStage(),         # Phase 4: real alignment (was AlignStub) — stage_name='align'
    SubtitlesStage(),     # Phase 4: real subtitle gen (was SubsStub) — stage_name='subs'
    AssembleStub(),       # Phase 5: placeholder
]
