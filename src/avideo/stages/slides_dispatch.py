"""SlidesDispatchStage — thin dispatcher routing by config.slides_mode (SLIDE-04/05).

Instantiates SlidesAutoStage, SlidesHybridStage, and SlidesManualStage on init,
then routes to the appropriate stage in ``run()`` based on
``config.slides_mode.value``.

Preserves the pipeline contract:
- ``stage_name = "slides"`` (D-10)
- Returns ``SlidesOutput`` from whichever sub-stage is chosen.

Design decisions:
- Each sub-stage is independently testable with no Chromium/API/network in tests.
- SlidesAutoStage is imported at module scope so the dispatch test can patch
  ``avideo.stages.slides_dispatch.SlidesAutoStage`` without touching the
  integration layer (Pitfall 6).
- PIPELINE_STAGES replaces SlidesAutoStage() with SlidesDispatchStage() (stubs.py).

Mock point (Pitfall 6):
- Import SlidesAutoStage at module scope → patch at
  ``avideo.stages.slides_dispatch.SlidesAutoStage``.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from avideo.models.slides import SlidesOutput
from avideo.stages.base import CheckpointMixin

# Imported at module scope so tests can patch avideo.stages.slides_dispatch.SlidesAutoStage
from avideo.stages.slides_auto import SlidesAutoStage
from avideo.stages.slides_hybrid import SlidesHybridStage
from avideo.stages.slides_manual import SlidesManualStage

if TYPE_CHECKING:
    from avideo.models.config import RunConfig
    from avideo.utils.workdir import WorkdirManager


class SlidesDispatchStage(CheckpointMixin):
    """Thin dispatcher stage that routes slide generation by config.slides_mode.

    Preserves ``stage_name="slides"`` and the ``SlidesOutput`` contract so all
    downstream stages (voice, assemble) are unaffected by the mode choice.

    Sub-stages instantiated at construction time:
    - auto   → SlidesAutoStage (Phase 3 real renderer, unchanged)
    - hybrid → SlidesHybridStage (design proposals + pause + ingest)
    - manual → SlidesManualStage (count validation + ingest)
    """

    stage_name: str = "slides"

    def __init__(self, theme_path: Path | None = None) -> None:
        """Initialise the dispatcher and its three sub-stages.

        Args:
            theme_path: Optional path to an existing theme.yaml, forwarded to
                SlidesAutoStage (ignored in hybrid/manual modes).
        """
        self._auto = SlidesAutoStage(theme_path=theme_path)
        self._hybrid = SlidesHybridStage()
        self._manual = SlidesManualStage()

    def run(self, workdir: "WorkdirManager", config: "RunConfig") -> SlidesOutput:
        """Route to the correct sub-stage based on config.slides_mode.

        Args:
            workdir: WorkdirManager providing path resolution and checkpoint helpers.
            config: RunConfig; ``slides_mode`` selects the sub-stage.

        Returns:
            SlidesOutput from whichever sub-stage is selected.

        Raises:
            ValueError: If config.slides_mode.value is not one of
                "auto", "hybrid", "manual".
        """
        mode = config.slides_mode.value
        if mode == "auto":
            return self._auto.run(workdir, config)
        if mode == "hybrid":
            return self._hybrid.run(workdir, config)
        if mode == "manual":
            return self._manual.run(workdir, config)
        raise ValueError(f"Unknown slides_mode: {mode!r}")
