"""SlidesManualStage — count validation + ingest for user-supplied slides (SLIDE-05).

Reads the storyboard checkpoint, validates that the number of user-supplied
slides in ``workdir/slides_user/`` matches the storyboard count (hard-fails on
mismatch), warns (but does NOT fail) on slides with non-1920×1080 dimensions,
ingests via the shared ``ingest_slide`` helper, and returns
``SlidesOutput(mode="manual")``.

Design decisions:
- D-10: stage_name = "slides" — preserves the dispatcher contract.
- Count mismatch → RuntimeError listing missing indices (SLIDE-05).
- Wrong dimensions → logger.warning only (SLIDE-05; warns, not hard-fail).
- Stages MUST NOT call workdir.mark_done or workdir.write_checkpoint.

Security (T-06-01):
- All path lookups are scoped to ``workdir.root / "slides_user"`` via glob.
- Suffix validation delegated to ingest_slide (SUPPORTED_EXTS check).

Mock point (Pitfall 6):
- ``ingest_slide`` imported at module scope → patch at
  ``avideo.stages.slides_manual.ingest_slide`` in tests.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from avideo.models.slides import SlidesOutput
from avideo.models.storyboard import StoryboardOutput
from avideo.stages.base import CheckpointMixin
from avideo.stages.slides_hybrid import _ingest_user_slides
from avideo.stages.slides_ingest import ingest_slide  # noqa: F401 — module-scope for patching

if TYPE_CHECKING:
    from avideo.models.config import RunConfig
    from avideo.utils.workdir import WorkdirManager

logger = logging.getLogger(__name__)

_TARGET_DIMS: tuple[int, int] = (1920, 1080)
"""Expected PNG dimensions. Warn if output PNG differs from this."""


class SlidesManualStage(CheckpointMixin):
    """Manual slide mode: validate user-supplied slides then ingest to SlidesOutput.

    Run sequence:
    1. Read storyboard checkpoint.
    2. Collect slides_user/ files for each storyboard index.
    3. Hard-fail (RuntimeError) if any index is missing.
    4. Ingest each file to slides/slide_XX.png via ingest_slide helper.
    5. Warn (logger.warning) if any output PNG is not exactly 1920×1080.
    6. Return SlidesOutput(mode="manual").
    """

    stage_name: str = "slides"

    def run(self, workdir: "WorkdirManager", config: "RunConfig") -> SlidesOutput:
        """Validate user slide count, ingest, check dims, return SlidesOutput.

        Args:
            workdir: WorkdirManager providing path resolution and checkpoint helpers.
            config: RunConfig (slides_mode must be SlidesMode.manual for this stage).

        Returns:
            SlidesOutput with mode="manual" and one png_path per storyboard slide.

        Raises:
            RuntimeError: If slide count in slides_user/ != storyboard slide count.
        """
        storyboard: StoryboardOutput = workdir.read_checkpoint(
            "storyboard", StoryboardOutput
        )

        # Ingest (raises RuntimeError on missing indices — count validation)
        png_paths = _ingest_user_slides(workdir, storyboard, mode="manual")

        # Dimension check: warn on non-1920×1080 (SLIDE-05: warn, not fail)
        _warn_wrong_dims(png_paths)

        return SlidesOutput(png_paths=png_paths, mode="manual")


def _warn_wrong_dims(png_paths: list[str]) -> None:
    """Log a WARNING for any PNG in *png_paths* whose dimensions != 1920×1080.

    Uses Pillow (PIL) to read image dimensions without fully decoding the file.
    Skips the check gracefully if Pillow is unavailable (should not happen in
    the project venv, but avoids a hard import error for robustness).

    Args:
        png_paths: Ordered list of PNG file paths to check.
    """
    try:
        from PIL import Image
    except ImportError:
        logger.debug("Pillow not available — skipping dimension check")
        return

    for path_str in png_paths:
        path = Path(path_str)
        if not path.exists():
            continue
        try:
            with Image.open(path) as img:
                w, h = img.size
            if (w, h) != _TARGET_DIMS:
                logger.warning(
                    "Slide %s has dimensions %dx%d — expected %dx%d. "
                    "The video may have borders or scaling artifacts. "
                    "Consider resizing to 1920×1080 before re-running.",
                    path.name,
                    w,
                    h,
                    _TARGET_DIMS[0],
                    _TARGET_DIMS[1],
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not read dimensions for %s: %s", path.name, exc)
