"""Image utilities for the Anthropic vision API.

Provides helpers for downscaling PNG files to the Anthropic API's size limits
before base64 encoding. These utilities are used by the vision-capable call
helper in ``avideo.integrations.anthropic``.

Design decisions:
- MAX_LONG_SIDE = 1568 px: Anthropic non-Opus model limit (e.g. claude-sonnet-4-6).
  Pre-downscaling client-side reduces payload from ~8 MB to ~6 KB for 1920×1080 slides.
- MAX_BYTES = 20 MB: Anthropic hard limit on the total encoded payload per image.
- MEDIA_TYPE = "image/png": Exact string required by the API (lowercase, no alternatives).
  Stored as a module constant so it is never hand-rolled as a string literal elsewhere.
- base64.standard_b64encode: The Anthropic API requires standard base64 (not URL-safe)
  with no line breaks. ``standard_b64encode`` guarantees this on all Python versions.

Security:
- T-06-02: MAX_BYTES guard raises ``ValueError`` if the downscaled PNG still exceeds 20 MB,
  preventing silent oversized payloads.
- T-06-03: MEDIA_TYPE is a module constant — single source of truth prevents typos like
  ``"image/PNG"`` (uppercase) which the API rejects.
"""
from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Maximum pixels on the longest side before downscaling (Anthropic non-Opus limit).
#: Source: https://platform.claude.com/docs/en/docs/build-with-claude/vision (VERIFIED 2026-05-26)
MAX_LONG_SIDE: int = 1568

#: Maximum encoded payload size in bytes (Anthropic hard limit).
MAX_BYTES: int = 20 * 1024 * 1024  # 20 MB

#: Exact ``media_type`` string required by the Anthropic image content block API.
#: Must be lowercase; the API is case-sensitive (T-06-03 / Pitfall 3).
MEDIA_TYPE: str = "image/png"


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------


def downscale_png_for_api(png_path: Path) -> str:
    """Return a standard base64-encoded PNG, downscaled so the longest side ≤ 1568 px.

    Opens the PNG at *png_path*, preserving its alpha channel (transparency is
    NOT flattened to black), downscales with Lanczos resampling if the longest
    side exceeds ``MAX_LONG_SIDE``, saves to an in-memory buffer, and encodes as
    standard base64 with no line breaks.

    Small images (longest side ≤ 1568 px) are returned unchanged — no upscaling.

    Args:
        png_path: Path to the source PNG file.

    Returns:
        A standard base64 string (no newlines) representing the downscaled PNG.

    Raises:
        ValueError: If the encoded PNG payload exceeds ``MAX_BYTES`` (20 MB)
            even after downscaling, which would be rejected by the API (T-06-02).
        FileNotFoundError: If *png_path* does not exist (propagated from Pillow).
        OSError: If the file cannot be opened or read (propagated from Pillow).

    Example::

        b64 = downscale_png_for_api(Path("workdir/slides/slide_00.png"))
        # b64 is a clean base64 string ready for an Anthropic image content block.
    """
    img = Image.open(png_path)
    # Preserve the alpha channel — converting to RGB fills transparent regions with
    # black, which would corrupt the pixels Claude sees and produce misleading verdicts.
    # Only normalise exotic modes (e.g. "P" palette, "CMYK") that PNG can't round-trip
    # cleanly: palette images expand to RGBA, everything else to RGB.
    if img.mode in ("P", "PA"):
        img = img.convert("RGBA")
    elif img.mode not in ("RGB", "RGBA", "L", "LA"):
        img = img.convert("RGB")
    w, h = img.size

    if max(w, h) > MAX_LONG_SIDE:
        scale = MAX_LONG_SIDE / max(w, h)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        img = img.resize((new_w, new_h), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw = buf.getvalue()

    if len(raw) > MAX_BYTES:
        raise ValueError(
            f"Image {png_path!r} is {len(raw) / 1e6:.1f} MB after downscale; "
            f"the Anthropic API requires ≤ {MAX_BYTES / 1e6:.0f} MB per image (T-06-02)."
        )

    return base64.standard_b64encode(raw).decode("utf-8")
