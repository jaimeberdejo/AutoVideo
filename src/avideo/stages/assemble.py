"""AssembleStage — FFmpeg video assembly: slides + audio → output.mp4 (1080p 16:9 H.264).

Replaces AssembleStub from stubs.py (plan 05-02 performs the PIPELINE_STAGES swap
once QA loudnorm is also wired — this plan deliberately leaves PIPELINE_STAGES
unchanged so both assemble + qa land in a single idempotence boundary).

Stage contract (StageProtocol / CheckpointMixin):
    stage_name      = "assemble"      — done-marker path: .assemble.done
    checkpoint_name = "assembly"      — checkpoint JSON: assembly.json

Idempotence (D-10):
    If output.mp4 AND assembly.json already exist, run() reads the existing
    AssemblyOutput checkpoint and returns immediately WITHOUT calling run_ffmpeg.
    This handles re-runs where the done-marker is absent but artifacts exist.
    The orchestrator's done-marker check (.assemble.done) handles the common resume
    path; this guards the rarer "marker gone, files present" case.

Atomic write (D-10):
    ffmpeg writes to output.mp4.tmp; os.replace renames to output.mp4 (same
    filesystem — POSIX atomic). No partial MP4 ever lands at the final path.

Real durations (ASMB-01 / D-02):
    Each slide's duration equals its audio file's container duration as measured
    by ffprobe — NOT estimated from timings.json / WPM. Pitfall 5 mitigation.

Security (T-05-02):
    Output paths are built from workdir.root / fixed names only (output.mp4,
    output.mp4.tmp, subs/output.srt — no user-controlled path components).

Note on QAReport (plan 05-02):
    This stage returns AssemblyOutput with qa=None.  The QA sub-step (two-pass
    loudnorm + deviation report) is layered on top in plan 05-02 and will enrich
    the returned AssemblyOutput with a QAReport.  Leaving qa=None here keeps the
    idempotence boundary clean.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from avideo.models.assembly import AssemblyOutput
from avideo.models.slides import SlidesOutput
from avideo.models.voice import VoiceOutput
from avideo.stages.base import CheckpointMixin
from avideo.integrations.ffmpeg import (
    build_assemble_args,
    probe_duration,
    run_ffmpeg,
)

if TYPE_CHECKING:
    from avideo.models.config import RunConfig
    from avideo.utils.workdir import WorkdirManager


class AssembleStage(CheckpointMixin):
    """FFmpeg assembly stage — stitches per-slide PNGs + audio into output.mp4.

    Reads:
        slides checkpoint (SlidesOutput.png_paths)
        voice  checkpoint (VoiceOutput.audio_paths)
        subs checkpoint (optional, only when config.burn_subs)

    Writes:
        workdir/output.mp4  (1080p 16:9 H.264 yuv420p, atomic tmp→rename)
        Returns AssemblyOutput — the ORCHESTRATOR writes assembly.json.

    Attributes:
        stage_name: ``"assemble"`` — matches AssembleStub and existing done-markers.
    """

    stage_name: str = "assemble"

    @property
    def checkpoint_name(self) -> str:
        """Checkpoint name is "assembly" (differs from stage_name "assemble")."""
        return "assembly"

    def run(self, workdir: "WorkdirManager", config: "RunConfig") -> AssemblyOutput:
        """Assemble per-slide PNGs and audio into a single 1080p 16:9 H.264 MP4.

        Steps:
        1. Idempotence check (D-10): return early if output.mp4 + assembly.json exist.
        2. Read slides + voice checkpoints.
        3. Validate slide count == audio count (Assumption A1).
        4. Measure real audio durations via ffprobe (ASMB-01 / D-02).
        5. Optionally resolve subtitle path for burn-in (D-05).
        6. Build ffmpeg arg list (build_assemble_args).
        7. Run ffmpeg (writes to output.mp4.tmp).
        8. Atomic rename tmp → output.mp4 (D-10).
        9. Return AssemblyOutput (qa=None; QA is plan 05-02's responsibility).

        Args:
            workdir: WorkdirManager providing root path and checkpoint access.
            config: RunConfig with crossfade_seconds, burn_subs, etc.

        Returns:
            AssemblyOutput with the absolute output_path.

        Raises:
            RuntimeError: If slide / audio count mismatch, or if ffmpeg fails.
        """
        output_mp4 = workdir.root / "output.mp4"
        assembly_json = workdir.checkpoint_path("assembly")

        # --- Step 1: Idempotence (D-10) ---
        if output_mp4.exists() and assembly_json.exists():
            # Artifacts already exist — read and return the existing output
            existing: AssemblyOutput = workdir.read_checkpoint(  # type: ignore[assignment]
                "assembly", AssemblyOutput
            )
            return existing

        # --- Step 2: Read input checkpoints ---
        slides_out: SlidesOutput = workdir.read_checkpoint(  # type: ignore[assignment]
            "slides", SlidesOutput
        )
        voice_out: VoiceOutput = workdir.read_checkpoint(  # type: ignore[assignment]
            "voice", VoiceOutput
        )

        png_paths_raw = slides_out.png_paths
        audio_paths_raw = voice_out.audio_paths

        # --- Step 3: Validate counts ---
        if not png_paths_raw:
            raise RuntimeError(
                "AssembleStage: slides checkpoint has no PNG paths. "
                "Check that the slides stage completed successfully."
            )
        if not audio_paths_raw:
            raise RuntimeError(
                "AssembleStage: voice checkpoint has no audio paths. "
                "Check that the voice stage completed successfully."
            )
        if len(png_paths_raw) != len(audio_paths_raw):
            raise RuntimeError(
                f"AssembleStage: slide count ({len(png_paths_raw)}) does not match "
                f"audio count ({len(audio_paths_raw)}). Each slide must have exactly "
                "one corresponding audio file (Assumption A1)."
            )

        # Resolve relative paths against workdir.root
        def _resolve(p: str) -> str:
            path = Path(p)
            if not path.is_absolute():
                return str(workdir.root / p)
            return str(path)

        png_paths = [_resolve(p) for p in png_paths_raw]
        audio_paths = [_resolve(p) for p in audio_paths_raw]

        # --- Step 4: Measure real audio durations (ASMB-01 / D-02) ---
        # NEVER use timings.json / WPM estimates — Pitfall 5
        durations = [probe_duration(a) for a in audio_paths]

        # --- Step 5: Subtitle burn-in path (D-05, T-05-02) ---
        subs_path: Optional[str] = None
        if config.burn_subs:
            # Fixed path — no user-controlled component (T-05-02)
            subs_path = str(workdir.root / "subs" / "output.srt")

        # --- Step 6: Build ffmpeg args ---
        tmp_mp4 = workdir.root / "output.mp4.tmp"
        args = build_assemble_args(
            png_paths,
            audio_paths,
            durations,
            output_path=str(tmp_mp4),
            xfade=config.crossfade_seconds,
            burn_subs_path=subs_path,
        )

        # --- Step 7: Run ffmpeg (D-04 — list[str], never shell=True) ---
        run_ffmpeg(args)

        # --- Step 8: Atomic publish (D-10 — tmp → rename) ---
        os.replace(str(tmp_mp4), str(output_mp4))

        # --- Step 9: Return output (QA is plan 05-02's responsibility) ---
        return AssemblyOutput(output_path=str(output_mp4))
