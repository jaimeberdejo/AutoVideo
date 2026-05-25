"""avideo.templates — Jinja2 template package for slides-auto rendering.

This package contains the HTML/CSS templates used by the slides-auto stage
to render each SlideSpec into a 1920×1080 PNG via Playwright/Chromium.

Package contents:
- ``base.html.j2``: full 1920×1080 HTML document with CSS custom properties
  from ThemeConfig, @font-face slot, and per-visual_type macro dispatch.
- ``macros.html.j2``: one Jinja2 macro per VisualType (title, bullets, chart,
  diagram, quote, comparison, image_icon) with code-drawn SVG for data visuals.

Usage (from the slides_auto stage):
    from importlib.resources import files
    from jinja2 import Environment, BaseLoader

    templates_dir = files("avideo.templates")
    # Load template content and pass to Jinja2 Environment

Design decisions: D-04 (base + macros), D-07 (offline SVG only), D-08 (no
external resources). Package-data inclusion configured in Phase 7 (PKG-01).
"""
