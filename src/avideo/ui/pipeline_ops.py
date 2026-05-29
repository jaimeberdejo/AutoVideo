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
    from avideo.models.config import RunConfig
    from avideo.models.script import ScriptOutput
    from avideo.models.verification import SlideVerdict
    from avideo.utils.workdir import WorkdirManager


# ---------------------------------------------------------------------------
# Single-stage re-run wrappers
# ---------------------------------------------------------------------------


def rerun_scriptwriter(workdir: "WorkdirManager", config: "RunConfig") -> None:
    """Reset the scriptwriter done-marker and launch ONLY the scriptwriter stage.

    Deletes ``.<workdir>/.scriptwriter.done`` so that ``bridge.run_stage``
    will start a fresh thread even if the stage ran before.  Calls
    ``invalidate_downstream("scriptwriter")`` so that all downstream stages
    (voice, align, subs, assemble) are also invalidated — their outputs are
    stale once the script changes.

    Does NOT touch storyboard or timing done-markers.

    Args:
        workdir: Active WorkdirManager for the current run.
        config:  RunConfig for the current run.
    """
    from avideo.stages.scriptwriter import ScriptwriterStage  # noqa: PLC0415

    workdir.done_marker("scriptwriter").unlink(missing_ok=True)
    workdir.invalidate_downstream("scriptwriter")
    run_stage(ScriptwriterStage(), workdir, config)


def rerun_slides(
    workdir: "WorkdirManager",
    config: "RunConfig",
    theme_path: Path | None = None,
) -> None:
    """Reset the slides done-marker and launch ONLY the slides stage.

    Deletes ``.<workdir>/.slides.done`` so that ``bridge.run_stage`` will
    start a fresh thread even if the stage ran before.  Calls
    ``invalidate_downstream("slides")`` so that downstream stages (verify,
    voice, align, subs, assemble) are also invalidated.

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
