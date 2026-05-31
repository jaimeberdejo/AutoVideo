"""avideo.ui.pipeline_ops — Thin UI-layer glue helpers.

Provides single-stage re-run wrappers, script persistence, upload handling,
and badge mapping so that wizard pages (phase_2_guion.py, phase_3_diapositivas.py)
stay simple and don't duplicate these idioms.

Design constraints:
- NO Streamlit import (must be unit-testable without Streamlit installed).
- Lazy imports of heavy stage modules (playwright / anthropic at module level
  in those stages) to keep test import cost low.
- Path-traversal guard on write_uploaded_slide (T-11-02-01).
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from avideo.ui.bridge import run_stage  # noqa: E402 — module-level mock seam for tests

if TYPE_CHECKING:
    from avideo.models.assembly import QAReport
    from avideo.models.config import RunConfig
    from avideo.models.script import ScriptOutput
    from avideo.models.verification import SlideVerdict
    from avideo.utils.workdir import WorkdirManager


# ---------------------------------------------------------------------------
# Single-stage re-run wrappers
# ---------------------------------------------------------------------------


def rerun_scriptwriter(workdir: "WorkdirManager", config: "RunConfig") -> None:
    """Reset the scriptwriter done-marker and launch ONLY the scriptwriter stage.

    Thin wrapper around ``rerun_with_feedback`` with an empty-string feedback so
    that ``write_feedback`` is skipped and the original behaviour is fully preserved.
    Kept as a named public function for backward compatibility with existing callers
    (UI pages and tests that import it directly).

    Args:
        workdir: Active WorkdirManager for the current run.
        config:  RunConfig for the current run.
    """
    rerun_with_feedback(workdir, config, "scriptwriter", feedback="")


def rerun_slides(
    workdir: "WorkdirManager",
    config: "RunConfig",
    theme_path: Path | None = None,
) -> None:
    """Reset the slides done-marker and launch ONLY the slides stage.

    Preserves ``theme_path`` forwarding for non-feedback callers (the feedback
    path handles theme deletion internally inside SlidesAutoStage.run() when
    feedback is present, so theme_path is irrelevant in that path).

    Does NOT touch storyboard, timing, or scriptwriter done-markers.

    Args:
        workdir:    Active WorkdirManager for the current run.
        config:     RunConfig for the current run.
        theme_path: Optional path to a custom ``theme.yaml``; forwarded to
                    ``SlidesDispatchStage``.
    """
    from avideo.stages.slides_dispatch import SlidesDispatchStage  # noqa: PLC0415

    workdir.done_marker("slides").unlink(missing_ok=True)
    workdir.invalidate_downstream("slides")
    run_stage(SlidesDispatchStage(theme_path), workdir, config)


# ---------------------------------------------------------------------------
# SEED-002: Steerable variation dispatcher
# ---------------------------------------------------------------------------

#: Stages that accept free-text feedback via feedback.json transport.
_VALID_FEEDBACK_STAGES: frozenset[str] = frozenset({"storyboard", "scriptwriter", "slides"})


def rerun_with_feedback(
    workdir: "WorkdirManager",
    config: "RunConfig",
    target_stage: str,
    feedback: str,
) -> None:
    """Write feedback.json, invalidate done-markers, and launch the target stage.

    This is the single entry point for all steered re-runs from the UI.  The
    stage reads ``workdir.read_feedback(target_stage)`` at the start of its
    ``run()`` and clears it after a successful ``call_structured`` call
    (consumed-once lifecycle).

    For ``target_stage="storyboard"``: runs ``StoryboardStage``.  Done-marker
    chaining (storyboard → timing → scriptwriter) re-walks automatically via
    the existing mechanism.
    For ``target_stage="scriptwriter"``: runs ``ScriptwriterStage`` only.
    For ``target_stage="slides"``: runs ``SlidesDispatchStage`` only.

    Design:
    - ``write_feedback`` is called BEFORE touching done-markers so that a crash
      between the two calls leaves feedback on disk — the stage will read and
      clear it on the next attempt (idempotent on retry).
    - Empty-string *feedback* skips ``write_feedback`` so that the original
      ``rerun_scriptwriter`` / ``rerun_slides`` behaviour is preserved when they
      delegate here with ``feedback=""``.

    Args:
        workdir:      Active WorkdirManager for the current run.
        config:       RunConfig for the current run.
        target_stage: One of ``"storyboard"``, ``"scriptwriter"``, ``"slides"``.
        feedback:     Free-text instruction from the user (may be empty string).

    Raises:
        ValueError: If *target_stage* is not one of the valid feedback stages.
    """
    if target_stage not in _VALID_FEEDBACK_STAGES:
        raise ValueError(
            f"Unknown feedback stage: {target_stage!r}. "
            f"Expected one of: {sorted(_VALID_FEEDBACK_STAGES)}"
        )

    # Write feedback before touching done-markers (idempotency on crash/retry)
    if feedback:
        workdir.write_feedback(target_stage, feedback)

    if target_stage == "storyboard":
        from avideo.stages.storyboard import StoryboardStage  # noqa: PLC0415

        workdir.done_marker("storyboard").unlink(missing_ok=True)
        workdir.invalidate_downstream("storyboard")
        run_stage(StoryboardStage(), workdir, config)

    elif target_stage == "scriptwriter":
        from avideo.stages.scriptwriter import ScriptwriterStage  # noqa: PLC0415

        workdir.done_marker("scriptwriter").unlink(missing_ok=True)
        workdir.invalidate_downstream("scriptwriter")
        run_stage(ScriptwriterStage(), workdir, config)

    elif target_stage == "slides":
        from avideo.stages.slides_dispatch import SlidesDispatchStage  # noqa: PLC0415

        workdir.done_marker("slides").unlink(missing_ok=True)
        workdir.invalidate_downstream("slides")
        run_stage(SlidesDispatchStage(), workdir, config)


# ---------------------------------------------------------------------------
# Script persistence
# ---------------------------------------------------------------------------


def persist_edited_script(
    workdir: "WorkdirManager",
    edited: "ScriptOutput",
) -> None:
    """Atomically write *edited* to ``workdir/script.json`` and invalidate downstream.

    Ordering (Pitfall-4): checkpoint is written FIRST; then downstream
    done-markers are deleted.  This guarantees that if the process is
    interrupted between the two calls, the new script is already on disk and
    the downstream stages will be re-run on the next resume.

    Args:
        workdir: Active WorkdirManager for the current run.
        edited:  The user-edited ``ScriptOutput`` to persist.
    """
    workdir.write_checkpoint("script", edited)
    workdir.invalidate_downstream("scriptwriter")


# ---------------------------------------------------------------------------
# Upload helper
# ---------------------------------------------------------------------------


def write_uploaded_slide(
    workdir: "WorkdirManager",
    filename: str,
    data: bytes,
) -> Path:
    """Write uploaded slide bytes to ``workdir/slides_user/<filename>``.

    Guards against path traversal: if *filename* contains ``/``, ``\\``,
    or starts with ``..``, a ``ValueError`` is raised before any file is
    written (T-11-02-01).

    Args:
        workdir:  Active WorkdirManager for the current run.
        filename: Bare filename provided by the user (e.g. ``"slide_00.png"``).
        data:     Raw bytes of the uploaded file.

    Returns:
        The ``Path`` of the written file (``workdir.root / "slides_user" / filename``).

    Raises:
        ValueError: If *filename* contains a path separator or starts with
                    ``".."``, indicating a path traversal attempt.
    """
    if "/" in filename or "\\" in filename or filename.startswith(".."):
        raise ValueError(
            f"Unsafe filename rejected (path traversal attempt): {filename!r}"
        )

    dest_dir = workdir.root / "slides_user"
    dest_dir.mkdir(exist_ok=True)
    dest = dest_dir / filename
    dest.write_bytes(data)
    return dest


# ---------------------------------------------------------------------------
# Voice helpers (Phase 12)
# ---------------------------------------------------------------------------


def rerun_voice(workdir: "WorkdirManager", config: "RunConfig") -> None:
    """Reset the voice done-marker and launch ONLY the voice stage.

    Deletes ``workdir/.voice.done`` so that ``bridge.run_stage`` will start a
    fresh thread even if the stage ran before.  Calls
    ``invalidate_downstream("voice")`` so that all downstream stages (align,
    subs, assemble) are also invalidated — their outputs are stale once voice
    changes.

    Does NOT touch storyboard, scriptwriter, or slides done-markers.

    Args:
        workdir: Active WorkdirManager for the current run.
        config:  RunConfig for the current run.
    """
    from avideo.stages.voice import VoiceStage  # noqa: PLC0415

    workdir.done_marker("voice").unlink(missing_ok=True)
    workdir.invalidate_downstream("voice")
    run_stage(VoiceStage(), workdir, config)


def write_uploaded_audio(
    workdir: "WorkdirManager",
    filename: str,
    data: bytes,
) -> Path:
    """Write uploaded audio bytes to ``workdir/audio/<filename>``.

    Guards against path traversal: if *filename* contains ``/``, ``\\``,
    or starts with ``..``, a ``ValueError`` is raised before any file is
    written (T-12-02-01).

    Args:
        workdir:  Active WorkdirManager for the current run.
        filename: Bare filename provided by the user (e.g. ``"slide_00.mp3"``).
        data:     Raw bytes of the uploaded audio file.

    Returns:
        The ``Path`` of the written file (``workdir.root / "audio" / filename``).

    Raises:
        ValueError: If *filename* contains a path separator or starts with
                    ``".."``, indicating a path traversal attempt.
    """
    if "/" in filename or "\\" in filename or filename.startswith(".."):
        raise ValueError(
            f"Unsafe filename rejected (path traversal attempt): {filename!r}"
        )

    dest_dir = workdir.root / "audio"
    dest_dir.mkdir(exist_ok=True)
    dest = dest_dir / filename
    dest.write_bytes(data)
    return dest


def audio_gate_ready(workdir: "WorkdirManager", n_slides: int) -> bool:
    """Return True iff all slides have audio AND timings.json has valid word-level data.

    Checks:
    1. For each slide i in range(n_slides), either ``audio/slide_{i:02d}.mp3``
       or ``audio/slide_{i:02d}.wav`` must exist.
    2. ``voice.json`` must parse successfully as ``UnifiedTimings``.
    3. ``len(timings.slides)`` must equal *n_slides*.
    4. Every ``SlideTimings.words`` list must be non-empty.

    Returns False (never raises) on any missing or malformed state so that the
    UI gate is safe to call at any pipeline stage (T-12-02-02).

    Args:
        workdir:  Active WorkdirManager for the current run.
        n_slides: Expected number of slides (and corresponding audio files).

    Returns:
        ``True`` if all conditions are satisfied; ``False`` otherwise.
    """
    from avideo.models.timings import UnifiedTimings  # noqa: PLC0415

    audio_dir = workdir.root / "audio"
    for i in range(n_slides):
        mp3 = audio_dir / f"slide_{i:02d}.mp3"
        wav = audio_dir / f"slide_{i:02d}.wav"
        if not (mp3.exists() or wav.exists()):
            return False

    try:
        timings: UnifiedTimings = workdir.read_checkpoint("voice", UnifiedTimings)  # type: ignore[assignment]
    except Exception:  # noqa: BLE001
        return False

    if len(timings.slides) != n_slides:
        return False

    return all(len(slide.words) > 0 for slide in timings.slides)


# ---------------------------------------------------------------------------
# Extras helpers (Phase 13)
# ---------------------------------------------------------------------------


def write_uploaded_music(
    workdir: "WorkdirManager",
    filename: str,
    data: bytes,
) -> Path:
    """Write uploaded music bytes to ``workdir/music/<filename>``.

    Guards against path traversal: if *filename* contains ``/``, ``\\``,
    or starts with ``..``, a ``ValueError`` is raised before any file is
    written (T-13-02-01).  Mirrors write_uploaded_audio but targets
    ``workdir/music/`` instead of ``workdir/audio/``.

    Args:
        workdir:  Active WorkdirManager for the current run.
        filename: Bare filename provided by the user (e.g. ``"bg_music.mp3"``).
        data:     Raw bytes of the uploaded music file.

    Returns:
        The ``Path`` of the written file (``workdir.root / "music" / filename``).

    Raises:
        ValueError: If *filename* contains a path separator or starts with
                    ``".."``, indicating a path traversal attempt.
    """
    if "/" in filename or "\\" in filename or filename.startswith(".."):
        raise ValueError(
            f"Unsafe filename rejected (path traversal attempt): {filename!r}"
        )

    dest_dir = workdir.root / "music"
    dest_dir.mkdir(exist_ok=True)
    dest = dest_dir / filename
    dest.write_bytes(data)
    return dest


def extras_to_run_config(
    burn_subs: bool,
    bg_music_path: "Path | None",
    bg_music_volume: float,
    bg_music_fade_out_s: float,
    crossfade_seconds: float,
) -> dict:
    """Map Fase 5 widget values to RunConfig kwargs.

    Returns a dict safe to merge into ``session_state['run_config']``.
    Pure function — no I/O, no Streamlit dependency.

    Args:
        burn_subs:          Whether to burn subtitles into the final video.
        bg_music_path:      Path to background music file, or None.
        bg_music_volume:    Linear volume level 0.0–1.0 (0.12 ~ -18 dBFS).
        bg_music_fade_out_s: Fade-out duration in seconds at end of video.
        crossfade_seconds:  Crossfade duration between slides in seconds.

    Returns:
        Dict with keys matching RunConfig field names.
    """
    return {
        "burn_subs": burn_subs,
        "bg_music_path": bg_music_path,
        "bg_music_volume": bg_music_volume,
        "bg_music_fade_out_s": bg_music_fade_out_s,
        "crossfade_seconds": crossfade_seconds,
    }


def read_qa_report(workdir: "WorkdirManager") -> "QAReport | None":
    """Read qa_report.json from workdir; returns None when absent or invalid.

    Wraps all I/O and parsing in a broad ``except Exception`` so that the
    wizard page is never broken by a corrupt or missing report (T-13-02-02).

    Args:
        workdir: Active WorkdirManager for the current run.

    Returns:
        A parsed ``QAReport`` on success; ``None`` on any error.
    """
    try:
        from avideo.models.assembly import QAReport  # noqa: PLC0415

        qa_path = workdir.root / "qa_report.json"
        return QAReport.model_validate_json(qa_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Badge mapping
# ---------------------------------------------------------------------------

_BADGE_MAP: dict[str, str] = {
    "ok": "✅",       # ✅
    "warning": "⚠️",  # ⚠️
    "fail": "❌",     # ❌
}


def badge_for_verdict(verdict: "SlideVerdict") -> str:
    """Return the emoji badge for a slide verification verdict.

    Args:
        verdict: A ``SlideVerdict`` with a ``status`` field of
                 ``"ok"``, ``"warning"``, or ``"fail"``.

    Returns:
        ``"✅"`` for ok, ``"⚠️"`` for warning, ``"❌"`` for fail.

    Raises:
        ValueError: If ``verdict.status`` is not a recognised status string.
    """
    try:
        return _BADGE_MAP[verdict.status]
    except KeyError:
        raise ValueError(
            f"Unknown verdict status: {verdict.status!r}. "
            f"Expected one of: {list(_BADGE_MAP)}"
        )
