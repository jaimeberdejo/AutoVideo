"""Tests for avideo.stages.verify_slides — VerifyStage.

Covers VERIFY-01/02:
  - auto mode: no vision call; returns trivial all-ok VerificationReport.
  - hybrid/manual mode: one call_structured_with_images per slide.
  - verification_report.json written atomically (no leftover .tmp files).
  - fail/warning verdict propagation.

No real Anthropic API calls — call_structured_with_images is patched at the
module boundary: avideo.stages.verify_slides.call_structured_with_images.

Wave-0 RED scaffold: tests fail until verify_slides.py is implemented.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Tiny-PNG helper
# ---------------------------------------------------------------------------


def _write_png(path: Path, size: tuple[int, int] = (100, 60)) -> None:
    """Write a minimal valid PNG at the given path using Pillow."""
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (10, 20, 30)).save(path, format="PNG")


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_config(tmp_path: Path, slides_mode: str = "auto", level: int = 4):
    """Build a RunConfig with the given slides_mode."""
    from avideo.models import RunConfig

    bullets_file = tmp_path / "bullets.yaml"
    bullets_file.write_text(
        "title: Test\nbullets:\n  - Bullet 1\n  - Bullet 2\n",
        encoding="utf-8",
    )
    return RunConfig(
        bullets=bullets_file,
        duration=120,
        workdir=tmp_path / "workdir",
        level=level,
        slides_mode=slides_mode,
    )


def _write_storyboard(workdir, n_slides: int = 2):
    """Pre-write a storyboard checkpoint with n_slides slides."""
    from avideo.models.storyboard import SlideSpec, StoryboardOutput, VisualType
    from avideo.utils.workdir import WorkdirManager

    wd = WorkdirManager(workdir)
    storyboard = StoryboardOutput(
        slides=[
            SlideSpec(
                title=f"Slide {i}",
                bullets=[f"Bullet {i}"],
                visual_type=VisualType.bullets,
            )
            for i in range(n_slides)
        ],
        language="es",
    )
    wd.write_checkpoint("storyboard", storyboard)
    return wd, storyboard


def _write_script(wd, n_slides: int = 2):
    """Pre-write a script checkpoint with n_slides slides."""
    from avideo.models.script import ScriptOutput, SlideScript

    script = ScriptOutput(
        slides=[
            SlideScript(slide_index=i, narration=f"Narration for slide {i}.")
            for i in range(n_slides)
        ],
        language="es",
    )
    wd.write_checkpoint("script", script)
    return script


def _write_slides_checkpoint(wd, png_paths: list[str]):
    """Pre-write a slides checkpoint pointing at given PNG paths."""
    from avideo.models.slides import SlidesOutput

    slides_out = SlidesOutput(png_paths=png_paths, mode="hybrid")
    wd.write_checkpoint("slides", slides_out)
    return slides_out


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVerifyAutoMode:
    """auto mode: verifier must NOT call the vision API."""

    def test_verify_auto_mode_skips(self, tmp_path):
        """VerifyStage in auto mode returns all-ok report without vision calls."""
        from avideo.stages.verify_slides import VerifyStage

        config = _make_config(tmp_path, slides_mode="auto")
        wd, _ = _write_storyboard(config.workdir, n_slides=2)

        mock_vision = MagicMock()
        with patch("avideo.stages.verify_slides.call_structured_with_images", mock_vision):
            stage = VerifyStage()
            report = stage.run(wd, config)

        # Vision call must NOT have been made
        mock_vision.assert_not_called()
        # Report has 2 slides, all ok
        assert len(report.slides) == 2
        assert all(v.status == "ok" for v in report.slides)


class TestVerifyHybridMode:
    """hybrid/manual mode: one call per slide."""

    def test_verify_calls_per_slide(self, tmp_path):
        """VerifyStage in hybrid mode calls call_structured_with_images once per slide."""
        from avideo.models.verification import SlideVerdict
        from avideo.stages.verify_slides import VerifyStage

        config = _make_config(tmp_path, slides_mode="hybrid")
        wd, _ = _write_storyboard(config.workdir, n_slides=2)
        _write_script(wd, n_slides=2)

        # Create fake slide PNGs
        slides_dir = config.workdir / "slides"
        slides_dir.mkdir(parents=True, exist_ok=True)
        png_paths = []
        for i in range(2):
            p = slides_dir / f"slide_{i:02d}.png"
            _write_png(p)
            png_paths.append(str(p))
        _write_slides_checkpoint(wd, png_paths)

        # Return ok verdict (slide_index will be overwritten by stage)
        mock_vision = MagicMock(
            return_value=SlideVerdict(slide_index=0, status="ok")
        )
        with patch("avideo.stages.verify_slides.call_structured_with_images", mock_vision):
            stage = VerifyStage()
            report = stage.run(wd, config)

        assert mock_vision.call_count == 2, (
            f"Expected 2 vision calls, got {mock_vision.call_count}"
        )
        assert len(report.slides) == 2

    def test_verify_writes_report_json(self, tmp_path):
        """VerifyStage writes verification_report.json to workdir root after run."""
        from avideo.models.verification import SlideVerdict, VerificationReport
        from avideo.stages.verify_slides import VerifyStage

        config = _make_config(tmp_path, slides_mode="hybrid")
        wd, _ = _write_storyboard(config.workdir, n_slides=2)
        _write_script(wd, n_slides=2)

        slides_dir = config.workdir / "slides"
        slides_dir.mkdir(parents=True, exist_ok=True)
        png_paths = []
        for i in range(2):
            p = slides_dir / f"slide_{i:02d}.png"
            _write_png(p)
            png_paths.append(str(p))
        _write_slides_checkpoint(wd, png_paths)

        mock_vision = MagicMock(
            return_value=SlideVerdict(slide_index=0, status="ok")
        )
        with patch("avideo.stages.verify_slides.call_structured_with_images", mock_vision):
            stage = VerifyStage()
            stage.run(wd, config)

        report_path = config.workdir / "verification_report.json"
        assert report_path.exists(), "verification_report.json must exist after run"

        # Must be valid VerificationReport JSON
        data = json.loads(report_path.read_text(encoding="utf-8"))
        report = VerificationReport.model_validate(data)
        assert len(report.slides) == 2

    def test_verify_report_json_atomic_no_tmp(self, tmp_path):
        """No verification_report.json.tmp file remains after a successful run."""
        from avideo.models.verification import SlideVerdict
        from avideo.stages.verify_slides import VerifyStage

        config = _make_config(tmp_path, slides_mode="hybrid")
        wd, _ = _write_storyboard(config.workdir, n_slides=2)
        _write_script(wd, n_slides=2)

        slides_dir = config.workdir / "slides"
        slides_dir.mkdir(parents=True, exist_ok=True)
        png_paths = []
        for i in range(2):
            p = slides_dir / f"slide_{i:02d}.png"
            _write_png(p)
            png_paths.append(str(p))
        _write_slides_checkpoint(wd, png_paths)

        mock_vision = MagicMock(
            return_value=SlideVerdict(slide_index=0, status="ok")
        )
        with patch("avideo.stages.verify_slides.call_structured_with_images", mock_vision):
            stage = VerifyStage()
            stage.run(wd, config)

        tmp_path_check = config.workdir / "verification_report.json.tmp"
        assert not tmp_path_check.exists(), (
            ".tmp file must be cleaned up after successful atomic write"
        )

    def test_verify_propagates_fail_status(self, tmp_path):
        """VerifyStage propagates fail verdict from the vision call into the report."""
        from avideo.models.verification import SlideVerdict
        from avideo.stages.verify_slides import VerifyStage

        config = _make_config(tmp_path, slides_mode="hybrid")
        wd, _ = _write_storyboard(config.workdir, n_slides=2)
        _write_script(wd, n_slides=2)

        slides_dir = config.workdir / "slides"
        slides_dir.mkdir(parents=True, exist_ok=True)
        png_paths = []
        for i in range(2):
            p = slides_dir / f"slide_{i:02d}.png"
            _write_png(p)
            png_paths.append(str(p))
        _write_slides_checkpoint(wd, png_paths)

        # First slide ok, second slide fail
        verdicts = [
            SlideVerdict(slide_index=0, status="ok"),
            SlideVerdict(slide_index=1, status="fail", issues=["Missing title"]),
        ]
        mock_vision = MagicMock(side_effect=verdicts)
        with patch("avideo.stages.verify_slides.call_structured_with_images", mock_vision):
            stage = VerifyStage()
            report = stage.run(wd, config)

        statuses = [v.status for v in report.slides]
        assert "fail" in statuses, f"Expected fail verdict in report, got: {statuses}"
