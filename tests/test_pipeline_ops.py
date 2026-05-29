"""RED tests for avideo.ui.pipeline_ops glue functions.

These tests FAIL with ImportError/ModuleNotFoundError until Plan 02 creates
src/avideo/ui/pipeline_ops.py. They define the exact contracts that
rerun_scriptwriter(), persist_edited_script(), write_uploaded_slide(), and
badge_for_verdict() must satisfy.

Coverage:
  TestSingleStageRerun:
    - rerun_scriptwriter calls invalidate_downstream("scriptwriter") then run_stage
    - invalidate_downstream is called with exactly "scriptwriter"

  TestScriptPersistence:
    - persist_edited_script writes checkpoint with name "script"
    - persist_edited_script calls invalidate_downstream("scriptwriter")

  TestUploadToWorkdir:
    - write_uploaded_slide writes bytes to workdir/slides_user/<filename>
    - write_uploaded_slide raises ValueError on path traversal ("../evil.png")

  TestBadgeMapping:
    - badge_for_verdict with status "ok"      returns "✅"
    - badge_for_verdict with status "warning" returns "⚠️"
    - badge_for_verdict with status "fail"    returns "❌"

All imports of avideo.ui.pipeline_ops are DEFERRED inside each test body
(same pattern as tests/test_bullets_gen.py), so this file collects cleanly
even before pipeline_ops.py exists (RED phase).
"""
from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Model imports (modules already exist — top-level import is fine)
# ---------------------------------------------------------------------------
from avideo.models.config import RunConfig
from avideo.models.script import ScriptOutput, SlideScript
from avideo.models.verification import SlideVerdict
from avideo.utils.workdir import WorkdirManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_config(tmp_path: Path) -> RunConfig:
    """Construct a RunConfig via model_construct to avoid env/file validation."""
    bullets = tmp_path / "b.yaml"
    bullets.write_text("title: T\nbullets:\n  - B\n", encoding="utf-8")
    return RunConfig.model_construct(bullets=bullets, duration=60)


def _minimal_script() -> ScriptOutput:
    """Return a minimal ScriptOutput for persistence tests."""
    return ScriptOutput(
        slides=[SlideScript(slide_index=0, narration="Hola mundo.")],
        language="es",
    )


# ---------------------------------------------------------------------------
# Class 1: TestSingleStageRerun
# ---------------------------------------------------------------------------


class TestSingleStageRerun:
    """Tests for rerun_scriptwriter() — single-stage re-run wrapper."""

    def test_rerun_scriptwriter_deletes_done_marker_and_launches_stage(
        self,
        tmp_path: Path,
        mocker,
    ) -> None:
        """rerun_scriptwriter() calls invalidate_downstream("scriptwriter")
        and then calls run_stage with a ScriptwriterStage instance.

        Both calls must happen exactly once.
        """
        from avideo.ui.pipeline_ops import rerun_scriptwriter  # noqa: PLC0415

        wm = WorkdirManager(tmp_path / "workdir")
        config = _minimal_config(tmp_path)

        mock_run_stage = mocker.patch("avideo.ui.pipeline_ops.run_stage")
        mock_invalidate = mocker.patch.object(wm, "invalidate_downstream")

        rerun_scriptwriter(wm, config)

        mock_invalidate.assert_called_once()
        mock_run_stage.assert_called_once()

    def test_rerun_scriptwriter_invalidates_only_from_scriptwriter(
        self,
        tmp_path: Path,
        mocker,
    ) -> None:
        """invalidate_downstream must be called with exactly "scriptwriter"
        — not "storyboard", not "slides", not any other stage.
        """
        from avideo.ui.pipeline_ops import rerun_scriptwriter  # noqa: PLC0415

        wm = WorkdirManager(tmp_path / "workdir")
        config = _minimal_config(tmp_path)

        mocker.patch("avideo.ui.pipeline_ops.run_stage")
        mock_invalidate = mocker.patch.object(wm, "invalidate_downstream")

        rerun_scriptwriter(wm, config)

        mock_invalidate.assert_called_once_with("scriptwriter")


# ---------------------------------------------------------------------------
# Class 2: TestScriptPersistence
# ---------------------------------------------------------------------------


class TestScriptPersistence:
    """Tests for persist_edited_script() — checkpoint write + downstream invalidation."""

    def test_persist_edited_script_writes_checkpoint(
        self,
        tmp_path: Path,
        mocker,
    ) -> None:
        """persist_edited_script(workdir, script_output) calls
        workdir.write_checkpoint("script", script_output) exactly once.
        """
        from avideo.ui.pipeline_ops import persist_edited_script  # noqa: PLC0415

        wm = WorkdirManager(tmp_path / "workdir")
        script = _minimal_script()

        mock_write = mocker.patch.object(wm, "write_checkpoint")
        mocker.patch.object(wm, "invalidate_downstream")

        persist_edited_script(wm, script)

        mock_write.assert_called_once_with("script", script)

    def test_persist_edited_script_calls_invalidate_downstream(
        self,
        tmp_path: Path,
        mocker,
    ) -> None:
        """persist_edited_script calls workdir.invalidate_downstream("scriptwriter")
        so that voice/align/subs/assemble are cleared after editing the script.
        """
        from avideo.ui.pipeline_ops import persist_edited_script  # noqa: PLC0415

        wm = WorkdirManager(tmp_path / "workdir")
        script = _minimal_script()

        mocker.patch.object(wm, "write_checkpoint")
        mock_invalidate = mocker.patch.object(wm, "invalidate_downstream")

        persist_edited_script(wm, script)

        mock_invalidate.assert_called_once_with("scriptwriter")


# ---------------------------------------------------------------------------
# Class 3: TestUploadToWorkdir
# ---------------------------------------------------------------------------


class TestUploadToWorkdir:
    """Tests for write_uploaded_slide() — safe file-upload path."""

    def test_write_uploaded_slide_creates_file_in_slides_user(
        self,
        tmp_path: Path,
    ) -> None:
        """write_uploaded_slide(workdir, "slide_00.png", data) writes bytes to
        workdir/slides_user/slide_00.png and returns that Path.

        No mocking needed — real filesystem write.
        """
        from avideo.ui.pipeline_ops import write_uploaded_slide  # noqa: PLC0415

        wm = WorkdirManager(tmp_path / "workdir")
        data = b"PNG\x00data"

        result = write_uploaded_slide(wm, "slide_00.png", data)

        expected = wm.root / "slides_user" / "slide_00.png"
        assert result == expected, (
            f"Expected returned path {expected}, got {result}"
        )
        assert expected.read_bytes() == data, (
            "File contents must match the uploaded bytes"
        )

    def test_write_uploaded_slide_rejects_path_traversal(
        self,
        tmp_path: Path,
    ) -> None:
        """write_uploaded_slide(workdir, '../evil.png', b'') raises ValueError.

        Path traversal filenames must be rejected to prevent writing outside
        the slides_user/ directory (T-11-01-01).
        """
        from avideo.ui.pipeline_ops import write_uploaded_slide  # noqa: PLC0415

        wm = WorkdirManager(tmp_path / "workdir")

        with pytest.raises(ValueError):
            write_uploaded_slide(wm, "../evil.png", b"")


# ---------------------------------------------------------------------------
# Class 4: TestBadgeMapping
# ---------------------------------------------------------------------------


class TestBadgeMapping:
    """Tests for badge_for_verdict() — pure emoji mapping from SlideVerdict."""

    def test_badge_ok(self) -> None:
        """badge_for_verdict with status 'ok' returns '✅'."""
        from avideo.ui.pipeline_ops import badge_for_verdict  # noqa: PLC0415

        verdict = SlideVerdict(slide_index=0, status="ok")
        assert badge_for_verdict(verdict) == "✅"

    def test_badge_warning(self) -> None:
        """badge_for_verdict with status 'warning' returns '⚠️'."""
        from avideo.ui.pipeline_ops import badge_for_verdict  # noqa: PLC0415

        verdict = SlideVerdict(slide_index=0, status="warning")
        assert badge_for_verdict(verdict) == "⚠️"

    def test_badge_fail(self) -> None:
        """badge_for_verdict with status 'fail' returns '❌'."""
        from avideo.ui.pipeline_ops import badge_for_verdict  # noqa: PLC0415

        verdict = SlideVerdict(slide_index=0, status="fail")
        assert badge_for_verdict(verdict) == "❌"
