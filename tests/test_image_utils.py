"""Tests for avideo.utils.image_utils — downscale_png_for_api helper.

These tests cover VERIFY-01 (PNG downscale before base64 encoding for the
Anthropic vision API). No real API calls; only Pillow and base64 are used.

Wave-0 RED scaffold: tests fail until src/avideo/utils/image_utils.py exists.
"""
from __future__ import annotations

import base64
import io
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Tiny-PNG helper
# ---------------------------------------------------------------------------


def _write_png(path: Path, size: tuple[int, int] = (1920, 1080)) -> None:
    """Write a minimal valid PNG at the given path using Pillow."""
    from PIL import Image

    Image.new("RGB", size, (10, 20, 30)).save(path, format="PNG")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_downscale_reduces_1920(tmp_path):
    """downscale_png_for_api on a 1920x1080 PNG returns base64 of a PNG <= 1568px longest side."""
    from avideo.utils.image_utils import downscale_png_for_api

    png = tmp_path / "slide.png"
    _write_png(png, size=(1920, 1080))

    b64 = downscale_png_for_api(png)

    # Decode and check resulting image dimensions
    raw = base64.standard_b64decode(b64)
    from PIL import Image

    img = Image.open(io.BytesIO(raw))
    w, h = img.size
    assert max(w, h) <= 1568, f"Longest side {max(w, h)} exceeds 1568px"
    # Should be a valid PNG
    assert img.format == "PNG"


def test_downscale_leaves_small_image(tmp_path):
    """downscale_png_for_api on a small PNG (800x600) does not upscale or corrupt it."""
    from avideo.utils.image_utils import downscale_png_for_api

    png = tmp_path / "small.png"
    _write_png(png, size=(800, 600))

    b64 = downscale_png_for_api(png)

    raw = base64.standard_b64decode(b64)
    from PIL import Image

    img = Image.open(io.BytesIO(raw))
    w, h = img.size
    assert max(w, h) <= 1568, f"Longest side {max(w, h)} exceeds 1568px"
    # Should not have been upscaled
    assert w <= 800 and h <= 600, f"Image was upscaled: {w}x{h}"


def test_downscale_returns_standard_base64(tmp_path):
    """downscale_png_for_api returns a standard-base64 string with no newline characters."""
    from avideo.utils.image_utils import downscale_png_for_api

    png = tmp_path / "slide.png"
    _write_png(png, size=(1920, 1080))

    b64 = downscale_png_for_api(png)

    assert "\n" not in b64, "base64 string must not contain newlines"
    assert "\r" not in b64, "base64 string must not contain carriage returns"
    # Must round-trip without error
    base64.standard_b64decode(b64)  # raises if invalid


def test_downscale_media_type_constant():
    """MEDIA_TYPE constant must be 'image/png' (lowercase, exact match)."""
    import avideo.utils.image_utils as m

    assert m.MEDIA_TYPE == "image/png", (
        f"MEDIA_TYPE must be 'image/png' (lowercase), got {m.MEDIA_TYPE!r}"
    )
