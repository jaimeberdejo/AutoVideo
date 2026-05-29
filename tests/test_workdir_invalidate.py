"""RED tests for WorkdirManager.invalidate_downstream.

These tests FAIL with AttributeError until Plan 02 adds invalidate_downstream
to WorkdirManager.  They are intentionally written before the implementation
exists — they define the contract that Plan 02 must satisfy.

Pipeline stage order (canonical):
    context → storyboard → timing → scriptwriter → slides → verify →
    voice → align → subs → assemble
"""
import pytest
from pathlib import Path


# ---- STAGE_ORDER expected by these tests (mirrors the Plan 02 contract) -----

_STAGE_ORDER = [
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


def test_invalidate_downstream_deletes_later_markers(tmp_workdir: Path) -> None:
    """Invalidate from 'storyboard' deletes only stages strictly after it.

    Setup:  context=done, storyboard=done, timing=done
    Call:   wm.invalidate_downstream("storyboard")
    Expect: context=done, storyboard=done, timing=NOT done
    """
    from avideo.utils.workdir import WorkdirManager

    wm = WorkdirManager(tmp_workdir)
    wm.mark_done("context")
    wm.mark_done("storyboard")
    wm.mark_done("timing")

    wm.invalidate_downstream("storyboard")

    assert wm.is_done("context"), "context (before boundary) must remain done"
    assert wm.is_done("storyboard"), "storyboard (boundary) must remain done"
    assert not wm.is_done("timing"), "timing (after boundary) must be invalidated"


def test_invalidate_downstream_from_first_stage(tmp_workdir: Path) -> None:
    """Invalidate from 'context' removes all stages after it (9 stages total).

    Setup:  all 10 stages done
    Call:   wm.invalidate_downstream("context")
    Expect: context=done, all 9 others NOT done
    """
    from avideo.utils.workdir import WorkdirManager

    wm = WorkdirManager(tmp_workdir)
    for stage in _STAGE_ORDER:
        wm.mark_done(stage)

    wm.invalidate_downstream("context")

    assert wm.is_done("context"), "context (boundary) must remain done"
    for stage in _STAGE_ORDER[1:]:
        assert not wm.is_done(stage), f"{stage} must be invalidated"


def test_invalidate_downstream_from_last_stage(tmp_workdir: Path) -> None:
    """Invalidate from 'assemble' is a no-op (nothing comes after it).

    Setup:  all 10 stages done
    Call:   wm.invalidate_downstream("assemble")
    Expect: all 10 stages still done
    """
    from avideo.utils.workdir import WorkdirManager

    wm = WorkdirManager(tmp_workdir)
    for stage in _STAGE_ORDER:
        wm.mark_done(stage)

    wm.invalidate_downstream("assemble")

    for stage in _STAGE_ORDER:
        assert wm.is_done(stage), f"{stage} must remain done (assemble is last)"


def test_invalidate_downstream_returns_deleted_names(tmp_workdir: Path) -> None:
    """invalidate_downstream returns the list of stage names whose markers were deleted.

    Setup:  storyboard=done, timing=done (context and others are NOT done)
    Call:   wm.invalidate_downstream("storyboard")
    Expect: return value == ["timing"]
    """
    from avideo.utils.workdir import WorkdirManager

    wm = WorkdirManager(tmp_workdir)
    wm.mark_done("storyboard")
    wm.mark_done("timing")

    deleted = wm.invalidate_downstream("storyboard")

    assert deleted == ["timing"], (
        "only stages that had a marker AND were after the boundary should be returned"
    )


def test_invalidate_downstream_unknown_stage_raises(tmp_workdir: Path) -> None:
    """invalidate_downstream raises ValueError for an unknown stage name."""
    from avideo.utils.workdir import WorkdirManager

    wm = WorkdirManager(tmp_workdir)

    with pytest.raises(ValueError):
        wm.invalidate_downstream("nonexistent_stage")
