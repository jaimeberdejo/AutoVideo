"""Tests for WorkdirManager: paths, atomic writes, done markers."""
import os
import pytest
from pathlib import Path


def test_workdir_creates_root_and_subdirs(tmp_workdir: Path) -> None:
    """WorkdirManager creates root and all required subdirectories."""
    from avideo.utils.workdir import WorkdirManager
    wm = WorkdirManager(tmp_workdir)
    assert tmp_workdir.exists()
    for subdir in ("slides", "audio", "subs", "design_proposal", "slides_user"):
        assert (tmp_workdir / subdir).is_dir(), f"missing subdir: {subdir}"


def test_write_and_read_checkpoint_roundtrip(tmp_workdir: Path) -> None:
    """write_checkpoint then read_checkpoint returns an equal model."""
    from avideo.utils.workdir import WorkdirManager
    from avideo.models import StoryboardOutput, SlideSpec
    wm = WorkdirManager(tmp_workdir)
    sb = StoryboardOutput(
        slides=[SlideSpec(title="T", bullets=["B"], visual_type="text")],
        language="es",
    )
    wm.write_checkpoint("storyboard", sb)
    loaded = wm.read_checkpoint("storyboard", StoryboardOutput)
    assert loaded == sb


def test_is_done_false_before_mark_done(tmp_workdir: Path) -> None:
    """is_done returns False before mark_done is called."""
    from avideo.utils.workdir import WorkdirManager
    wm = WorkdirManager(tmp_workdir)
    assert wm.is_done("storyboard") is False


def test_is_done_true_after_mark_done(tmp_workdir: Path) -> None:
    """is_done returns True after mark_done is called."""
    from avideo.utils.workdir import WorkdirManager
    wm = WorkdirManager(tmp_workdir)
    wm.mark_done("storyboard")
    assert wm.is_done("storyboard") is True


def test_write_checkpoint_no_tmp_file_left_behind(tmp_workdir: Path) -> None:
    """write_checkpoint leaves no .json.tmp file after success."""
    from avideo.utils.workdir import WorkdirManager
    from avideo.models import ContextOutput
    wm = WorkdirManager(tmp_workdir)
    wm.write_checkpoint("context", ContextOutput())
    tmp_file = wm.checkpoint_path("context").with_suffix(".json.tmp")
    assert not tmp_file.exists(), ".json.tmp should be cleaned up after successful write"


def test_interrupted_write_leaves_no_partial_file(tmp_workdir: Path, monkeypatch) -> None:
    """If os.replace is interrupted, the target JSON does not exist and is_done stays False."""
    from avideo.utils.workdir import WorkdirManager
    from avideo.models import ContextOutput

    def failing_replace(src, dst):
        raise OSError("Simulated interrupt")

    monkeypatch.setattr(os, "replace", failing_replace)
    wm = WorkdirManager(tmp_workdir)
    with pytest.raises(OSError):
        wm.write_checkpoint("context", ContextOutput())
    target = wm.checkpoint_path("context")
    assert not target.exists(), "target JSON must not exist after interrupted write"
    assert wm.is_done("context") is False, "done marker must not exist after interrupted write"


def test_failed_replace_cleans_up_tmp_file(tmp_workdir: Path, monkeypatch) -> None:
    """WR-06: if os.replace fails, the .json.tmp file is removed so no stale tmp accumulates."""
    from avideo.utils.workdir import WorkdirManager
    from avideo.models import ContextOutput

    def failing_replace(src, dst):
        raise OSError("Simulated replace failure")

    monkeypatch.setattr(os, "replace", failing_replace)
    wm = WorkdirManager(tmp_workdir)
    with pytest.raises(OSError):
        wm.write_checkpoint("context", ContextOutput())
    tmp_file = wm.checkpoint_path("context").with_suffix(".json.tmp")
    assert not tmp_file.exists(), ".json.tmp must be cleaned up after a failed os.replace"


def test_mark_done_independent_of_write_checkpoint(tmp_workdir: Path) -> None:
    """mark_done only flips is_done; write_checkpoint is independent."""
    from avideo.utils.workdir import WorkdirManager
    wm = WorkdirManager(tmp_workdir)
    # Touch marker without writing checkpoint
    wm.mark_done("slides")
    assert wm.is_done("slides") is True
    # checkpoint JSON should not exist
    assert not wm.checkpoint_path("slides").exists()
