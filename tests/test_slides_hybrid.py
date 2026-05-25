"""RED test scaffold for SlidesHybridStage + SlidesDispatchStage (SLIDE-04).

Tests are written BEFORE implementation. They define the expected contract for:
  - SlidesHybridStage: design proposal generation, pause for approval, ingest, SlidesOutput.
  - SlidesDispatchStage: routes by config.slides_mode to auto/hybrid/manual.

All tests patch at the STAGE import boundary (avideo.stages.slides_hybrid.*,
avideo.stages.slides_dispatch.*) — never the integration module directly (Pitfall 6).
No real Chromium, no real API, no network.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from avideo.models.config import RunConfig, SlidesMode
from avideo.models.slides import SlidesOutput
from avideo.models.storyboard import SlideSpec, StoryboardOutput, VisualType
from avideo.utils.workdir import WorkdirManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(tmp_path: Path, slides_mode: SlidesMode = SlidesMode.hybrid) -> Any:
    """Build a minimal RunConfig with slides_mode set."""
    bullets_path = tmp_path / "bullets.yaml"
    bullets_path.write_text(
        "title: Test\nbullets:\n  - Point 1\n  - Point 2\n", encoding="utf-8"
    )
    return RunConfig(bullets=bullets_path, duration=120, slides_mode=slides_mode)


def _write_png(path: Path, size: tuple[int, int] = (1920, 1080)) -> None:
    """Write a minimal valid PNG file at *path* using Pillow."""
    from PIL import Image

    Image.new("RGB", size, (10, 20, 30)).save(path, format="PNG")


def _make_workdir_with_storyboard(
    tmp_path: Path, n_slides: int = 2
) -> WorkdirManager:
    """Create a WorkdirManager and pre-write an n_slides storyboard checkpoint."""
    workdir = WorkdirManager(tmp_path / "workdir")
    slides = [
        SlideSpec(
            title=f"Slide {i}",
            bullets=[f"Bullet {i}a", f"Bullet {i}b"],
            visual_type=VisualType.bullets,
        )
        for i in range(n_slides)
    ]
    storyboard = StoryboardOutput(slides=slides, language="es")
    workdir.write_checkpoint("storyboard", storyboard)
    return workdir


# ---------------------------------------------------------------------------
# Test: hybrid writes design proposals
# ---------------------------------------------------------------------------


def test_hybrid_writes_design_proposals(tmp_path: Path) -> None:
    """Hybrid stage writes one slide_XX.json brief per storyboard slide (SLIDE-04)."""
    from avideo.models.design_proposal import SlideDesignProposal
    from avideo.stages.slides_hybrid import SlidesHybridStage

    workdir = _make_workdir_with_storyboard(tmp_path, n_slides=2)
    config = _make_config(tmp_path, SlidesMode.hybrid)

    # Place user slides in slides_user/
    for i in range(2):
        _write_png(workdir.root / "slides_user" / f"slide_{i:02d}.png")

    fake_brief = SlideDesignProposal(
        slide_index=0,
        title="Fake Title",
        bullets=["bullet"],
        visual_type="bullets",
        layout_notes="some notes",
    )

    with (
        patch(
            "avideo.stages.slides_hybrid.call_structured", return_value=fake_brief
        ),
        patch("avideo.stages.slides_hybrid.pause_for_approval"),
    ):
        stage = SlidesHybridStage()
        stage.run(workdir, config)

    # Assert design proposal JSON files were written
    dp_dir = workdir.root / "design_proposal"
    for i in range(2):
        json_path = dp_dir / f"slide_{i:02d}.json"
        assert json_path.exists(), f"Expected {json_path} to exist"
        parsed = SlideDesignProposal.model_validate_json(json_path.read_text())
        assert hasattr(parsed, "title")
        assert hasattr(parsed, "bullets")
        assert hasattr(parsed, "visual_type")
        assert hasattr(parsed, "layout_notes")


# ---------------------------------------------------------------------------
# Test: hybrid calls call_structured once per slide
# ---------------------------------------------------------------------------


def test_hybrid_calls_call_structured(tmp_path: Path) -> None:
    """call_structured is called exactly once per storyboard slide (SLIDE-04)."""
    from avideo.models.design_proposal import SlideDesignProposal
    from avideo.stages.slides_hybrid import SlidesHybridStage

    workdir = _make_workdir_with_storyboard(tmp_path, n_slides=2)
    config = _make_config(tmp_path, SlidesMode.hybrid)

    for i in range(2):
        _write_png(workdir.root / "slides_user" / f"slide_{i:02d}.png")

    fake_brief = SlideDesignProposal(
        slide_index=0,
        title="Title",
        bullets=["b"],
        visual_type="bullets",
        layout_notes="notes",
    )

    with (
        patch(
            "avideo.stages.slides_hybrid.call_structured", return_value=fake_brief
        ) as mock_cs,
        patch("avideo.stages.slides_hybrid.pause_for_approval"),
    ):
        stage = SlidesHybridStage()
        stage.run(workdir, config)

    assert mock_cs.call_count == 2, (
        f"Expected call_structured called 2 times, got {mock_cs.call_count}"
    )


# ---------------------------------------------------------------------------
# Test: hybrid pauses exactly once after writing proposals
# ---------------------------------------------------------------------------


def test_hybrid_pauses_after_proposals(tmp_path: Path) -> None:
    """pause_for_approval is called exactly once after all briefs are written (SLIDE-04)."""
    from avideo.models.design_proposal import SlideDesignProposal
    from avideo.stages.slides_hybrid import SlidesHybridStage

    workdir = _make_workdir_with_storyboard(tmp_path, n_slides=2)
    config = _make_config(tmp_path, SlidesMode.hybrid)

    for i in range(2):
        _write_png(workdir.root / "slides_user" / f"slide_{i:02d}.png")

    fake_brief = SlideDesignProposal(
        slide_index=0,
        title="T",
        bullets=["b"],
        visual_type="bullets",
        layout_notes="n",
    )

    with (
        patch("avideo.stages.slides_hybrid.call_structured", return_value=fake_brief),
        patch(
            "avideo.stages.slides_hybrid.pause_for_approval"
        ) as mock_pause,
    ):
        stage = SlidesHybridStage()
        stage.run(workdir, config)

    assert mock_pause.call_count == 1, (
        f"Expected pause_for_approval called once, got {mock_pause.call_count}"
    )


# ---------------------------------------------------------------------------
# Test: hybrid returns SlidesOutput with mode="hybrid"
# ---------------------------------------------------------------------------


def test_hybrid_returns_slides_output(tmp_path: Path) -> None:
    """run() returns SlidesOutput(mode='hybrid', png_paths=[...]) with one path per slide."""
    from avideo.models.design_proposal import SlideDesignProposal
    from avideo.stages.slides_hybrid import SlidesHybridStage

    workdir = _make_workdir_with_storyboard(tmp_path, n_slides=2)
    config = _make_config(tmp_path, SlidesMode.hybrid)

    for i in range(2):
        _write_png(workdir.root / "slides_user" / f"slide_{i:02d}.png")

    fake_brief = SlideDesignProposal(
        slide_index=0,
        title="T",
        bullets=["b"],
        visual_type="bullets",
        layout_notes="n",
    )

    with (
        patch("avideo.stages.slides_hybrid.call_structured", return_value=fake_brief),
        patch("avideo.stages.slides_hybrid.pause_for_approval"),
    ):
        stage = SlidesHybridStage()
        result = stage.run(workdir, config)

    assert isinstance(result, SlidesOutput), (
        f"Expected SlidesOutput, got {type(result)!r}"
    )
    assert result.mode == "hybrid", f"Expected mode='hybrid', got {result.mode!r}"
    assert len(result.png_paths) == 2, (
        f"Expected 2 png_paths, got {len(result.png_paths)}"
    )


# ---------------------------------------------------------------------------
# Test: dispatch auto delegates to SlidesAutoStage only
# ---------------------------------------------------------------------------


def test_dispatch_auto_delegates_to_auto(tmp_path: Path) -> None:
    """In auto mode, SlidesDispatchStage delegates to SlidesAutoStage only (SLIDE-04)."""
    from avideo.stages.slides_dispatch import SlidesDispatchStage

    workdir = _make_workdir_with_storyboard(tmp_path, n_slides=2)
    config = _make_config(tmp_path, SlidesMode.auto)

    expected_output = SlidesOutput(png_paths=["x"], mode="auto")
    mock_auto_instance = MagicMock()
    mock_auto_instance.run.return_value = expected_output
    mock_auto_cls = MagicMock(return_value=mock_auto_instance)

    with patch("avideo.stages.slides_dispatch.SlidesAutoStage", mock_auto_cls):
        stage = SlidesDispatchStage()
        result = stage.run(workdir, config)

    mock_auto_instance.run.assert_called_once()
    assert result.mode == "auto"
