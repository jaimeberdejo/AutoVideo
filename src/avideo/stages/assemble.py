"""AssembleStage — FFmpeg video assembly: slides + audio → output.mp4 (1080p 16:9 H.264).

Stage contract (StageProtocol / CheckpointMixin):
    stage_name      = "assemble"      — done-marker path: .assemble.done
    checkpoint_name = "assembly"      — checkpoint JSON: assembly.json

Idempotence (D-10):
    If output.mp4 AND assembly.json already exist, run() reads the existing
    AssemblyOutput checkpoint and returns immediately WITHOUT calling run_ffmpeg.
    This handles re-runs where the done-marker is absent but artifacts exist.
    The orchestrator's done-marker check (.assemble.done) handles the common resume
    path; this guards the rarer "marker gone, files present" case.

    QA idempotence sub-boundary: if output.mp4 AND qa_report.json both exist but
    assembly.json is absent (partial run), the QA sub-step is also skipped — the
    normalized output.mp4 and report are already present.

Atomic write (D-10):
    ffmpeg assembly writes to output.tmp.mp4; os.replace renames to output.mp4.
    loudnorm pass-2 writes to output.norm.tmp.mp4; os.replace renames to output.mp4.
    (".mp4" must be the final extension — ffmpeg infers the container format from
    the output filename's extension, and a trailing ".tmp" is not a recognized
    muxer, so it fails with "Unable to choose an output format".)
    qa_report.json written to qa_report.json.tmp; os.replace renames to qa_report.json.
    No partial files ever land at final paths.

Real durations (ASMB-01 / D-02):
    Each slide's duration equals its audio file's container duration as measured
    by ffprobe — NOT estimated from timings.json / WPM.  Pitfall 5 mitigation.

QA sub-step (QA-01/02, per 05-RESEARCH Open Question 1):
    After the assembly encode, AssembleStage runs two-pass EBU R128 loudnorm:
    1. Pass-1 measures integrated loudness (parse_loudnorm_json on stderr).
    2. Pass-2 applies measured values with linear=true, -c:v copy, +faststart.
    3. probe_duration on the normalized output.mp4 → actual duration.
    4. build_qa_report constructs QAReport(target, actual, measured_lufs, normalized_lufs).
    5. qa_report.json written atomically.
    6. Rich table printed to terminal (D-08).
    7. QAReport attached to AssemblyOutput before return.

Security (T-05-02, T-05-06, T-05-07, T-05-08):
    All output paths are workdir.root / fixed names only (output.mp4, output.tmp.mp4,
    output.norm.tmp.mp4, qa_report.json, qa_report.json.tmp, subs/output.srt).
    No user-controlled path components.
    Loudnorm args are a Python list[str], shell=False implicit (T-05-06).
    parse_loudnorm_json isolates the last {...} block (T-05-07).
    Atomic writes prevent partial artifacts on crash (T-05-08).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from rich.table import Table

from avideo.integrations.ffmpeg import (
    build_assemble_args,
    build_music_mix_args,
    loudnorm_pass1_args,
    loudnorm_pass2_args,
    parse_loudnorm_json,
    probe_duration,
    run_ffmpeg,
)
from avideo.models.assembly import AssemblyOutput, QAReport
from avideo.models.slides import SlidesOutput
from avideo.models.timings import UnifiedTimings
from avideo.stages.base import CheckpointMixin
from avideo.stages.qa import build_qa_report, within_tolerance
from avideo.utils.rich_ui import console

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
        workdir/output.mp4      (1080p 16:9 H.264 yuv420p, atomic tmp→rename)
        workdir/qa_report.json  (QAReport with duration deviation + LUFS metrics)
        Returns AssemblyOutput  — the ORCHESTRATOR writes assembly.json.

    Attributes:
        stage_name: ``"assemble"`` — matches AssembleStub and existing done-markers.
    """

    stage_name: str = "assemble"

    @property
    def checkpoint_name(self) -> str:
        """Checkpoint name is "assembly" (differs from stage_name "assemble")."""
        return "assembly"

    def run(self, workdir: "WorkdirManager", config: "RunConfig") -> AssemblyOutput:
        """Assemble per-slide PNGs and audio into a single 1080p 16:9 H.264 MP4 with QA.

        Steps:
        1. Idempotence check (D-10): return early if output.mp4 + assembly.json exist.
        2. Read slides + voice checkpoints.
        3. Validate slide count == audio count (Assumption A1).
        4. Measure real audio durations via ffprobe (ASMB-01 / D-02).
        5. Optionally resolve subtitle path for burn-in (D-05).
        6. Build ffmpeg arg list (build_assemble_args).
        7. Run ffmpeg (writes to output.tmp.mp4).
        8. Atomic rename tmp → output.mp4 (D-10).
        9. QA sub-step (QA-01/02): two-pass loudnorm + duration deviation + report.
           a. If output.mp4 AND qa_report.json already exist, reload and attach.
           b. Pass-1: measure loudness (parse_loudnorm_json on ffmpeg stderr).
           c. Pass-2: apply with linear=true, -c:v copy, +faststart (Pitfall 2).
           d. probe_duration on normalized output.mp4 → actual_seconds.
           e. build_qa_report → QAReport.
           f. Write qa_report.json atomically.
           g. Print Rich table (D-08).
        10. Return AssemblyOutput(output_path=..., qa=report).

        Args:
            workdir: WorkdirManager providing root path and checkpoint access.
            config: RunConfig with crossfade_seconds, burn_subs, duration, target_lufs.

        Returns:
            AssemblyOutput with the absolute output_path and attached QAReport.

        Raises:
            RuntimeError: If slide / audio count mismatch, or if ffmpeg fails.
        """
        output_mp4 = workdir.root / "output.mp4"
        assembly_json = workdir.checkpoint_path("assembly")
        qa_json = workdir.root / "qa_report.json"

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
        # The "voice" checkpoint is written by VoiceStage as UnifiedTimings (not VoiceOutput).
        # UnifiedTimings.slides[i].audio_path is the relative audio path per slide.
        voice_out: UnifiedTimings = workdir.read_checkpoint(  # type: ignore[assignment]
            "voice", UnifiedTimings
        )

        png_paths_raw = slides_out.png_paths
        # Extract audio paths from UnifiedTimings (relative → resolved below with workdir.root)
        audio_paths_raw = [slide.audio_path for slide in voice_out.slides]

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
        tmp_mp4 = workdir.root / "output.tmp.mp4"  # .mp4 ext must be last — see module docstring
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

        # --- Step 8.5: Music mix pass (EXT-02/EXT-03) ---
        # If bg_music_path is configured and the file exists, overlay background music
        # with ducking + fades.  This step replaces output_mp4 with the mixed version
        # BEFORE _run_qa runs, so _run_qa applies loudnorm exactly once on the final mix.
        #
        # IMPORTANT (EXT-03 / Pitfall 20):
        #   When music is present we use a SINGLE-PASS loudnorm on the mixed output
        #   instead of the two-pass approach to avoid double-normalization / pumping.
        #   We pre-write qa_report.json so that _run_qa's idempotence check returns
        #   immediately, skipping the two-pass loudnorm pass entirely.
        #
        # IMPORTANT (Pitfall 21):
        #   fade_out_start uses probe_duration() on the REAL assembled output,
        #   not config.duration (which is the target, not the actual frame count).
        bg_music_path = config.bg_music_path
        if bg_music_path and Path(str(bg_music_path)).exists():
            actual_dur = probe_duration(str(output_mp4))
            fade_out_s: float = config.bg_music_fade_out_s
            target_lufs: float = config.target_lufs
            music_volume: float = config.bg_music_volume
            fade_out_start = max(0.0, actual_dur - fade_out_s)
            music_tmp = workdir.root / "output.music.tmp.mp4"  # .mp4 ext required by ffmpeg
            music_args = build_music_mix_args(
                str(output_mp4),
                str(bg_music_path),
                str(music_tmp),
                music_volume=music_volume,
                fade_out_start=fade_out_start,
                fade_out_s=fade_out_s,
            )
            run_ffmpeg(music_args)
            os.replace(str(music_tmp), str(output_mp4))  # atomic: music mix replaces narration-only

            # Single-pass loudnorm on the final mixed output (EXT-03).
            # Two-pass loudnorm on already-normalized audio causes pumping (Pitfall 20).
            # print_format=json enables parsing actual measured loudness from stderr (CR-01).
            # -ar 48000 ensures consistent sample rate with the two-pass path (WR-02).
            # _run_qa's idempotence check (qa_json.exists()) short-circuits the two-pass
            # path so loudnorm runs exactly ONCE total when music is present.
            norm_tmp = workdir.root / "output.norm.tmp.mp4"  # .mp4 ext must be last — see module docstring
            single_loudnorm_args: list[str] = [
                "ffmpeg", "-hide_banner", "-y",
                "-i", str(output_mp4),
                "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11:print_format=json",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "48000",             # match loudnorm_pass2_args for consistent sample rate
                "-movflags", "+faststart",  # Pitfall 2: re-add under -c:v copy
                str(norm_tmp),
            ]
            single_proc = run_ffmpeg(single_loudnorm_args)
            os.replace(str(norm_tmp), str(output_mp4))

            # Parse actual loudness from the single-pass stderr (CR-01: no fabricated values).
            measured_lufs_music: float
            normalized_lufs_music: float
            try:
                sp_measured = parse_loudnorm_json(single_proc.stderr)
                measured_lufs_music = float(sp_measured.get("input_i", target_lufs))
                # output_i is the actual measured post-normalization loudness —
                # same fix as the two-pass path below (was hardcoded to target_lufs,
                # assuming success rather than measuring the real result).
                normalized_lufs_music = float(sp_measured.get("output_i", target_lufs))
            except (ValueError, KeyError):
                measured_lufs_music = target_lufs
                normalized_lufs_music = target_lufs

            # Build and pre-write qa_report.json so _run_qa's idempotence path fires.
            actual_seconds = probe_duration(str(output_mp4))
            music_qa = build_qa_report(
                target_seconds=float(config.duration),
                actual_seconds=actual_seconds,
                measured_lufs=measured_lufs_music,
                normalized_lufs=normalized_lufs_music,
            )
            qa_tmp = workdir.root / "qa_report.json.tmp"
            qa_tmp.write_text(music_qa.model_dump_json(indent=2), encoding="utf-8")
            os.replace(str(qa_tmp), str(qa_json))

        # --- Step 9: QA sub-step (QA-01/02, per 05-RESEARCH Open Question 1) ---
        # When music is present, qa_report.json was pre-written in Step 8.5, so
        # _run_qa's idempotence check fires immediately (no additional loudnorm passes).
        report = self._run_qa(
            workdir=workdir,
            output_mp4=output_mp4,
            qa_json=qa_json,
            config=config,
        )

        # Print QA table here (outside _run_qa) so it fires unconditionally
        # for both music and non-music paths (CR-02: music path was skipping it).
        self._print_qa_table(report)

        # --- Step 10: Return output with QA report attached ---
        return AssemblyOutput(output_path=str(output_mp4), qa=report)

    def _run_qa(
        self,
        *,
        workdir: "WorkdirManager",
        output_mp4: Path,
        qa_json: Path,
        config: "RunConfig",
    ) -> QAReport:
        """Run the two-pass loudnorm QA sub-step and return the QAReport.

        Idempotent: if qa_report.json already exists (from a prior run that
        completed the QA but not the orchestrator's checkpoint write), reload
        and return the existing report without re-running loudnorm.

        Security (T-05-06): both loudnorm passes use list[str] + run_ffmpeg
        (shell=False implicit).  Paths are fixed workdir names (T-05-08).

        Args:
            workdir:    WorkdirManager instance for path resolution.
            output_mp4: Path to the assembled output.mp4 to normalize.
            qa_json:    Path where qa_report.json should be written.
            config:     RunConfig carrying duration (QA target) and target_lufs.

        Returns:
            QAReport with duration deviation + measured/normalized LUFS.
        """
        # QA idempotence: if qa_report.json already exists, reload it
        if qa_json.exists():
            return QAReport.model_validate_json(qa_json.read_text(encoding="utf-8"))

        target_lufs = config.target_lufs
        norm_tmp = workdir.root / "output.norm.tmp.mp4"  # .mp4 ext must be last — see module docstring

        # --- Pass 1: measure loudness ---
        pass1_args = loudnorm_pass1_args(str(output_mp4), target_lufs=target_lufs)
        pass1_proc = run_ffmpeg(pass1_args)
        measured = parse_loudnorm_json(pass1_proc.stderr)
        measured_lufs: float = measured["input_i"]

        # --- Pass 2: apply with linear=true, -c:v copy, +faststart (Pitfall 2) ---
        pass2_args = loudnorm_pass2_args(
            str(output_mp4),
            str(norm_tmp),
            measured_I=measured["measured_I"],
            measured_TP=measured["measured_TP"],
            measured_LRA=measured["measured_LRA"],
            measured_thresh=measured["measured_thresh"],
            offset=measured["offset"],
            target_lufs=target_lufs,
        )
        pass2_proc = run_ffmpeg(pass2_args)

        # Atomic replace: normalized audio overwrites the assembled output.mp4
        os.replace(str(norm_tmp), str(output_mp4))

        # Determine normalized_lufs from pass-2 stderr's output_i — the ACTUAL
        # resulting loudness after normalization, not input_i (which is always
        # the pre-normalization value, even in the pass-2/apply JSON block).
        # Regression note: this previously read "input_i" here, which silently
        # reported the pre-normalization loudness as if it were the result —
        # observed live during v2.0.0 browser UAT (normalized_lufs == measured_lufs
        # on every real run, giving false confidence that normalization worked).
        normalized_lufs: float = target_lufs  # fallback = target
        try:
            pass2_measured = parse_loudnorm_json(pass2_proc.stderr)
            normalized_lufs = pass2_measured.get("output_i", target_lufs)
        except (ValueError, KeyError):
            # If pass-2 stderr doesn't have parseable block, use target as estimate
            normalized_lufs = target_lufs

        # --- QA-01: duration deviation ---
        actual_seconds = probe_duration(str(output_mp4))
        target_seconds = float(config.duration)

        # --- Build QAReport ---
        qa_report = build_qa_report(
            target_seconds=target_seconds,
            actual_seconds=actual_seconds,
            measured_lufs=measured_lufs,
            normalized_lufs=normalized_lufs,
        )

        # --- Write qa_report.json atomically (T-05-08) ---
        qa_tmp = workdir.root / "qa_report.json.tmp"
        qa_tmp.write_text(qa_report.model_dump_json(indent=2), encoding="utf-8")
        os.replace(str(qa_tmp), str(qa_json))

        return qa_report

    def _print_qa_table(self, report: QAReport) -> None:
        """Print the QA metrics as a Rich table to stderr (D-08).

        Rows: Target Duration, Actual Duration, Deviation, Measured LUFS, Normalized LUFS.
        The deviation row is flagged with a colour hint when outside tolerance (Pitfall 7).

        Args:
            report: Populated QAReport to display.
        """
        if not isinstance(report, QAReport):
            return

        table = Table(
            "Metric",
            "Value",
            "Status",
            title="[bold cyan]QA Report[/bold cyan]",
            border_style="cyan",
        )

        # Duration rows
        table.add_row(
            "Target Duration",
            f"{report.target_seconds:.3f} s",
            "",
        )
        table.add_row(
            "Actual Duration",
            f"{report.actual_seconds:.3f} s",
            "",
        )

        dev = report.duration_deviation
        ok = within_tolerance(dev)
        dev_status = "[green]OK[/green]" if ok else "[yellow]WARNING[/yellow]"
        dev_sign = "+" if dev >= 0 else ""
        table.add_row(
            "Duration Deviation",
            f"{dev_sign}{dev:.3f} s",
            dev_status,
        )

        # Loudness rows
        if report.measured_lufs is not None:
            table.add_row(
                "Measured LUFS",
                f"{report.measured_lufs:.2f} LUFS",
                "",
            )
        if report.normalized_lufs is not None:
            norm_ok = abs(report.normalized_lufs - (-16.0)) < 2.0
            norm_status = "[green]OK[/green]" if norm_ok else "[yellow]CHECK[/yellow]"
            table.add_row(
                "Normalized LUFS",
                f"{report.normalized_lufs:.2f} LUFS",
                norm_status,
            )

        console.print(table)
