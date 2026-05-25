"""SubtitlesStage — generate SRT and VTT subtitle files from UnifiedTimings (SUB-01/SUB-02).

Reads the ``align`` checkpoint (``UnifiedTimings``) and produces two subtitle files:
    - ``workdir/subs/output.srt``: SubRip format with comma decimal separator.
    - ``workdir/subs/output.vtt``: WebVTT format with WEBVTT header and dot separator.

Offset accumulation (RESEARCH Pattern 4 / Open Question 1):
    ``WordTiming`` objects stored in checkpoints have timestamps that are RELATIVE to
    the start of their slide's audio clip.  To build correct global video subtitles,
    this stage accumulates an offset (``offset += slide.duration``) after processing
    each slide.  Each word's start/end is shifted by the running offset before
    segmentation.  This converts per-slide-relative timestamps into global video
    timestamps for the final assembled video.

Fallback for empty words (elevenlabs path):
    When ``SlideTimings.words`` is empty (e.g. the voice stage produced a slide with
    no recognized characters), the stage creates a single cue spanning the entire
    slide duration with empty text.  The text loss is explicitly acceptable: it only
    occurs when there are no words to display, so there is nothing to lose.  This
    approach avoids a crash and still writes valid SRT/VTT files.

burn_subs (SUB-02 / D-09):
    Phase 4 ONLY writes the ``.srt``/``.vtt`` files.  The actual burn-in (using
    ``ffmpeg`` with the ``subtitles=`` filter) is deferred to Phase 5 (assemble stage).
    Even with ``config.burn_subs=True``, this stage does NOT invoke ffmpeg.

Security (T-04-10):
    Output paths are constructed ONLY from ``workdir.root / "subs"`` with fixed
    filenames ``"output.srt"`` and ``"output.vtt"`` — no user-controlled path
    components.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from avideo.models.subtitles import SubtitlesOutput
from avideo.models.timings import UnifiedTimings
from avideo.stages.base import CheckpointMixin
from avideo.utils.subtitle_format import Cue, segment_words, to_srt, to_vtt

if TYPE_CHECKING:
    from avideo.models.config import RunConfig
    from avideo.utils.workdir import WorkdirManager


class SubtitlesStage(CheckpointMixin):
    """Subtitle generation stage — UnifiedTimings → output.srt + output.vtt.

    Reads the ``align`` checkpoint (the canonical UnifiedTimings produced by
    either ``AlignStage`` on the record path, or the passthrough on the elevenlabs
    path).  Groups word-level timings into subtitle cues using the rules from D-08
    (42 chars/line, ≤2 lines, ≤5s/cue, ≤17 CPS), accumulates a global offset
    across slides, and writes the two subtitle files.

    This stage does NOT call ``workdir.write_checkpoint`` — the orchestrator does
    that after ``run()`` returns (StageProtocol contract).

    Attributes:
        stage_name: ``"subs"`` — checkpoint contract (D-12); matches SubsStub.
    """

    stage_name: str = "subs"

    def run(self, workdir: "WorkdirManager", config: "RunConfig") -> SubtitlesOutput:
        """Generate SRT and VTT subtitle files from the align checkpoint.

        Args:
            workdir: WorkdirManager; provides root path and checkpoint access.
            config: RunConfig; ``config.burn_subs`` is noted but Phase 4 does NOT
                burn — burning is Phase 5's responsibility (D-09).

        Returns:
            ``SubtitlesOutput`` with relative paths to the written files and total
            cue count.  The orchestrator writes this as ``subs.json``.

        Note:
            Even with ``config.burn_subs=True``, this method only writes the
            ``.srt`` and ``.vtt`` files.  Phase 5 (AssembleStage) is responsible
            for the actual burn-in via ``ffmpeg -vf subtitles=...``.
        """
        # SUB-02: Phase 4 does NOT burn subtitles — document the decision point.
        # burn_subs=True is recorded here only for transparency; the actual burn
        # happens in Phase 5.  No ffmpeg call is made in this stage.
        _ = config.burn_subs  # acknowledged; not acted upon (D-09)

        # Read the unified timings from the align checkpoint (ALIGN-02 passthrough
        # for elevenlabs, or whisperx-populated for record mode — D-11).
        timings: UnifiedTimings = workdir.read_checkpoint("align", UnifiedTimings)  # type: ignore[assignment]

        # Accumulate all cues across slides, converting per-slide-relative timestamps
        # to global video timestamps by accumulating an offset per slide.
        # offset = Σ durations of all preceding slides (RESEARCH Pattern 4 / Open Question 1).
        all_cues: list[Cue] = []
        offset: float = 0.0

        for slide in timings.slides:
            if slide.words:
                # Shift each word's timestamps by the accumulated global offset.
                # WordTiming is a Pydantic model; we create shifted copies inline
                # rather than mutating the checkpoint data.
                from avideo.models.timings import WordTiming  # local to avoid circular at top
                shifted_words = [
                    WordTiming(
                        text=w.text,
                        start=w.start + offset,
                        end=w.end + offset,
                    )
                    for w in slide.words
                ]
                slide_cues = segment_words(shifted_words)
            else:
                # Fallback: no words for this slide.  Create a single empty cue
                # spanning the slide duration.  Text is empty because there is no
                # word-level data to display — nothing is lost.
                # This keeps the SRT/VTT files structurally valid without crashing.
                if slide.duration > 0:
                    slide_cues = [Cue(start=offset, end=offset + slide.duration, text="")]
                else:
                    slide_cues = []

            all_cues.extend(slide_cues)
            # Advance the global offset by this slide's full duration.
            offset += slide.duration

        # Serialize to SRT and VTT.
        srt_content = to_srt(all_cues)
        vtt_content = to_vtt(all_cues)

        # Write output files under workdir/subs/ (T-04-10: fixed paths, no traversal).
        subs_dir: Path = workdir.root / "subs"
        subs_dir.mkdir(exist_ok=True)  # already created by WorkdirManager.__init__; guard

        srt_path = subs_dir / "output.srt"
        vtt_path = subs_dir / "output.vtt"
        srt_path.write_text(srt_content, encoding="utf-8")
        vtt_path.write_text(vtt_content, encoding="utf-8")

        # Return paths relative to workdir.root for checkpoint portability.
        return SubtitlesOutput(
            srt_path=str(srt_path.relative_to(workdir.root)),
            vtt_path=str(vtt_path.relative_to(workdir.root)),
            cue_count=len(all_cues),
        )
