"""ThemeConfig — Pydantic v2 model for slide visual theme (D-02/D-03).

A ``ThemeConfig`` encapsulates the full set of visual parameters that the
slides-auto stage injects as CSS custom properties into the Jinja2 base
template:

- ``palette``: hex colour strings for primary/background/text/accent slots.
- ``typography``: heading and body font-family names (must match an @font-face
  declared in the template or a generic CSS family like sans-serif).
- ``base_font_px``: root font size for the 1920×1080 canvas (D-06).
- ``scale``: modular type scale multiplier (heading size = base × scale²).
- ``margin_px``: outer canvas padding (all sides).
- ``gap_px``: gap between layout regions / bullet items.

All fields carry defaults, so ``ThemeConfig()`` is fully valid without any
arguments (D-02).  ``DEFAULT_THEME`` is the built-in fallback used when the AI
generation fails or is skipped (D-01).

Decision reference: D-01 (theme fallback), D-02 (ThemeConfig schema),
D-03 (idempotence — if theme.yaml exists, ThemeConfig.model_validate is used
instead of regenerating).
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Palette(BaseModel):
    """Colour palette for slide themes.

    All fields are CSS-compatible hex colour strings (e.g. ``"#2563eb"``).
    """

    primary: str = "#2563eb"
    """Primary accent colour — used for headings, icons, highlights."""
    background: str = "#0f172a"
    """Slide background colour."""
    text: str = "#f1f5f9"
    """Body/bullet text colour."""
    accent: str = "#38bdf8"
    """Secondary accent — used for decorative elements and chart fills."""


class Typography(BaseModel):
    """Font-family names used in the theme.

    Values must match an ``@font-face`` family name bundled via base64
    embedding *or* a valid CSS generic family (``sans-serif``, etc.).
    The stage injects the ``@font-face`` CSS via the ``font_face_css``
    template slot before rendering (see ``embed_font_face`` in
    ``integrations/playwright.py``).
    """

    heading: str = "Inter"
    """Font family for slide titles / headings."""
    body: str = "Inter"
    """Font family for bullet text and body copy."""


class ThemeConfig(BaseModel):
    """Full visual theme for the slides-auto pipeline stage.

    Encodes all parameters injected as CSS custom properties into
    ``src/avideo/templates/base.html.j2``.  Validated by Pydantic v2.
    Persisted as ``theme.yaml`` (``pyyaml``) in the project root.

    Decision reference: D-02 (schema), D-01 (fallback), D-03 (idempotence).
    """

    palette: Palette = Field(default_factory=Palette)
    """Colour palette (primary/background/text/accent hex strings)."""
    typography: Typography = Field(default_factory=Typography)
    """Font-family names for heading and body text."""
    base_font_px: int = 32
    """Root font size in pixels on the 1920×1080 canvas."""
    scale: float = 1.25
    """Modular type scale multiplier (heading = base × scale², sub = base × scale)."""
    margin_px: int = 120
    """Outer canvas padding applied to all four sides (px)."""
    gap_px: int = 40
    """Gap between major layout regions and between bullet items (px)."""


#: Built-in default theme — used as fallback when AI generation fails/is skipped.
#: Decision reference: D-01.
DEFAULT_THEME: ThemeConfig = ThemeConfig()
