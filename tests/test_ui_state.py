"""RED tests for avideo.ui.state — phase reconstruction from done-markers.

These tests FAIL with ModuleNotFoundError until Plan 03 creates
src/avideo/ui/state.py.  They define the contract Plan 03 must satisfy.

No Streamlit APIs are called or imported in this file.
"""
import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Module-level import — fails with ModuleNotFoundError until state.py exists
# ---------------------------------------------------------------------------
from avideo.ui.state import workdir_phase_from_done_markers, PHASES, PHASE_COMPLETION_STAGE  # noqa: E402


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_phase_from_done_markers_fresh_workdir(tmp_workdir: Path) -> None:
    """Fresh workdir (no done-markers) returns phase 1."""
    from avideo.utils.workdir import WorkdirManager

    wm = WorkdirManager(tmp_workdir)
    assert workdir_phase_from_done_markers(wm) == 1


def test_phase_from_done_markers_phase1_complete(tmp_workdir: Path) -> None:
    """'context' done-marker present → return phase 2 (next incomplete phase)."""
    from avideo.utils.workdir import WorkdirManager

    wm = WorkdirManager(tmp_workdir)
    wm.mark_done("context")

    assert workdir_phase_from_done_markers(wm) == 2


def test_phase_from_done_markers_phase2_complete(tmp_workdir: Path) -> None:
    """Phases 1 and 2 complete (context + scriptwriter done) → return phase 3."""
    from avideo.utils.workdir import WorkdirManager

    wm = WorkdirManager(tmp_workdir)
    # Phase 2 completion stage is 'scriptwriter'; all earlier stages are also done
    for stage in ("context", "storyboard", "timing", "scriptwriter"):
        wm.mark_done(stage)

    assert workdir_phase_from_done_markers(wm) == 3


def test_phase_from_done_markers_all_complete(tmp_workdir: Path) -> None:
    """All 10 pipeline stages done → return 6 (max phase; never increments past 6)."""
    from avideo.utils.workdir import WorkdirManager

    all_stages = [
        "context",
        "storyboard",
        "timing",
        "scriptwriter",
        "slides",
        "verify",
        "voice",
        "align",
        "subs",
        "assemble",
    ]

    wm = WorkdirManager(tmp_workdir)
    for stage in all_stages:
        wm.mark_done(stage)

    result = workdir_phase_from_done_markers(wm)
    assert result == 6, f"expected phase 6 when all stages done, got {result}"


def test_phases_constant_has_six_entries() -> None:
    """PHASES has exactly 6 entries; first is (1, 'Contenido'); last starts with 6."""
    assert len(PHASES) == 6
    assert PHASES[0] == (1, "Contenido"), f"first entry must be (1, 'Contenido'), got {PHASES[0]}"
    assert PHASES[5][0] == 6, f"last entry must start with phase number 6, got {PHASES[5][0]}"


def test_phase_completion_stage_covers_all_phases() -> None:
    """PHASE_COMPLETION_STAGE maps all 6 wizard phases (1-6)."""
    assert set(PHASE_COMPLETION_STAGE.keys()) == {1, 2, 3, 4, 5, 6}, (
        f"expected keys {{1,2,3,4,5,6}}, got {set(PHASE_COMPLETION_STAGE.keys())}"
    )
