"""RED test scaffold for ingest_slide helper + SlidesManualStage (SLIDE-05).

Tests are written BEFORE implementation. They define the expected contract for:
  - ingest_slide: normalizes PNG/PDF/PPTX → PNG; rejects unsupported types.
  - SlidesManualStage: validates count == storyboard count; warns (not fails) on dims;
    returns SlidesOutput(mode='manual').

All tests patch at the STAGE import boundary (avideo.stages.slides_ingest.*) — never
the integration module directly (Pitfall 6).
No real PyMuPDF calls, no real rasterization.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, call

import pytest

from avideo.models.config import RunConfig, SlidesMode
from avideo.models.slides import SlidesOutput
from avideo.models.storyboard import SlideSpec, StoryboardOutput, VisualType
from avideo.utils.workdir import WorkdirManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(tmp_path: Path, slides_mode: SlidesMode = SlidesMode.manual) -> Any:
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
            bullets=[f"Bullet {i}a"],
            visual_type=VisualType.bullets,
        )
        for i in range(n_slides)
    ]
    storyboard = StoryboardOutput(slides=slides, language="es")
    workdir.write_checkpoint("storyboard", storyboard)
    return workdir


# ---------------------------------------------------------------------------
# Test: ingest_slide — PNG direct copy
# ---------------------------------------------------------------------------


def test_ingest_png_copies(tmp_path: Path) -> None:
    """PNG input is copied verbatim to the destination path (SLIDE-05)."""
    from avideo.stages.slides_ingest import ingest_slide

    src = tmp_path / "src_slide.png"
    out = tmp_path / "out_slide.png"
    _write_png(src)

    ingest_slide(src, out)

    assert out.exists(), "out_png must exist after ingest_slide for PNG"
    assert out.read_bytes() == src.read_bytes(), (
        "PNG ingest must copy bytes verbatim (no rasterize)"
    )


# ---------------------------------------------------------------------------
# Test: ingest_slide — PDF rasterization via PyMuPDF
# ---------------------------------------------------------------------------


def test_ingest_pdf_rasterizes(tmp_path: Path) -> None:
    """PDF input triggers fitz rasterization to 1920px width (SLIDE-05)."""
    from avideo.stages.slides_ingest import ingest_slide

    src = tmp_path / "deck.pdf"
    src.write_bytes(b"%PDF-1.4 fake")  # not a real PDF — fitz is mocked
    out = tmp_path / "out_slide.png"

    # Build a fitz mock that writes a file on pix.save()
    mock_page = MagicMock()
    mock_page.rect.width = 595.0  # A4 width in points

    def _save_side_effect(path: str) -> None:
        _write_png(Path(path))

    mock_pix = MagicMock()
    mock_pix.save.side_effect = _save_side_effect
    mock_page.get_pixmap.return_value = mock_pix

    mock_doc = MagicMock()
    mock_doc.__getitem__ = MagicMock(return_value=mock_page)

    mock_fitz = MagicMock()
    mock_fitz.open.return_value = mock_doc
    mock_fitz.Matrix = MagicMock(side_effect=lambda a, b: (a, b))

    with patch("avideo.stages.slides_ingest.fitz", mock_fitz):
        ingest_slide(src, out)

    mock_fitz.open.assert_called_once_with(str(src))
    assert out.exists(), "out_png must exist after PDF rasterization"


# ---------------------------------------------------------------------------
# Test: ingest_slide — PPTX raises RuntimeError
# ---------------------------------------------------------------------------


def test_ingest_pptx_raises(tmp_path: Path) -> None:
    """PPTX input raises RuntimeError with export hint (PDF/PNG) (SLIDE-05)."""
    from avideo.stages.slides_ingest import ingest_slide

    src = Path("deck.pptx")
    out = tmp_path / "out_slide.png"

    with pytest.raises(RuntimeError) as exc_info:
        ingest_slide(src, out)

    msg = str(exc_info.value)
    assert "PDF" in msg or "png" in msg.lower(), (
        f"RuntimeError message must mention PDF or PNG export; got: {msg!r}"
    )


# ---------------------------------------------------------------------------
# Test: ingest_slide — unsupported extension raises ValueError
# ---------------------------------------------------------------------------


def test_ingest_unsupported_raises(tmp_path: Path) -> None:
    """Unsupported file type raises ValueError listing supported extensions (SLIDE-05)."""
    from avideo.stages.slides_ingest import ingest_slide

    src = Path("x.txt")
    out = tmp_path / "out.png"

    with pytest.raises(ValueError):
        ingest_slide(src, out)


# ---------------------------------------------------------------------------
# Test: manual stage — count mismatch → RuntimeError
# ---------------------------------------------------------------------------


def test_manual_validates_count(tmp_path: Path) -> None:
    """Manual mode raises RuntimeError listing missing indices when count mismatches (SLIDE-05)."""
    from avideo.stages.slides_manual import SlidesManualStage

    workdir = _make_workdir_with_storyboard(tmp_path, n_slides=3)
    config = _make_config(tmp_path, SlidesMode.manual)

    # Only place 2 slides instead of 3
    for i in range(2):
        _write_png(workdir.root / "slides_user" / f"slide_{i:02d}.png")

    stage = SlidesManualStage()
    with pytest.raises(RuntimeError) as exc_info:
        stage.run(workdir, config)

    msg = str(exc_info.value)
    # Must mention missing index 2
    assert "2" in msg, (
        f"RuntimeError message must list missing index 2; got: {msg!r}"
    )


# ---------------------------------------------------------------------------
# Test: manual stage — wrong dims warns but does NOT raise
# ---------------------------------------------------------------------------


def test_manual_warns_wrong_dims(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Non-1920x1080 PNG triggers a WARNING but does NOT raise (SLIDE-05)."""
    from avideo.stages.slides_manual import SlidesManualStage

    workdir = _make_workdir_with_storyboard(tmp_path, n_slides=3)
    config = _make_config(tmp_path, SlidesMode.manual)

    # Write 2 normal slides and 1 with wrong dimensions
    _write_png(workdir.root / "slides_user" / "slide_00.png", size=(1920, 1080))
    _write_png(workdir.root / "slides_user" / "slide_01.png", size=(1280, 720))  # wrong
    _write_png(workdir.root / "slides_user" / "slide_02.png", size=(1920, 1080))

    stage = SlidesManualStage()
    with caplog.at_level(logging.WARNING):
        result = stage.run(workdir, config)

    # Must not raise — returns SlidesOutput
    assert isinstance(result, SlidesOutput)
    assert len(result.png_paths) == 3


# ---------------------------------------------------------------------------
# Test: manual stage — correct count → SlidesOutput(mode="manual")
# ---------------------------------------------------------------------------


def test_manual_returns_slides_output(tmp_path: Path) -> None:
    """2-slide storyboard + 2 matching PNGs → SlidesOutput(mode='manual', len=2) (SLIDE-05)."""
    from avideo.stages.slides_manual import SlidesManualStage

    workdir = _make_workdir_with_storyboard(tmp_path, n_slides=2)
    config = _make_config(tmp_path, SlidesMode.manual)

    for i in range(2):
        _write_png(workdir.root / "slides_user" / f"slide_{i:02d}.png")

    stage = SlidesManualStage()
    result = stage.run(workdir, config)

    assert isinstance(result, SlidesOutput)
    assert result.mode == "manual", f"Expected mode='manual', got {result.mode!r}"
    assert len(result.png_paths) == 2, (
        f"Expected 2 png_paths, got {len(result.png_paths)}"
    )
