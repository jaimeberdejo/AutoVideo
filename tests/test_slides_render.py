"""Real-Chromium smoke test: HTML → Playwright → PNG must be exactly 1920×1080.

This test exercises the actual SlideRenderer (Task 3) against a real headless
Chromium browser.  It SKIPS gracefully in two scenarios:

1. ``playwright`` package not available: ``pytest.importorskip("playwright")``
   marks the whole module as skipped before any import of SlideRenderer.

2. Chromium browser executable missing (e.g. CI without ``playwright install
   chromium``): the ``playwright.sync_api.Error`` raised by ``browser.launch()``
   is caught inside the test and causes a ``pytest.skip``.

Wave-0 status: the test is RED until Task 3 creates
``src/avideo/integrations/playwright.py``.  Importing SlideRenderer here is
deferred to inside the test body so the import error becomes a clean failure
(not a collection error) before Task 3 lands.
"""

from __future__ import annotations

import pytest

# Guard: skip entire module if playwright package is not installed.
pytest.importorskip("playwright")

# ---------------------------------------------------------------------------
# Minimal HTML for the smoke test — no fonts, no external resources,
# inline background so the render is visually non-trivial.
# ---------------------------------------------------------------------------

_MINIMAL_HTML = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
html, body {
  width: 1920px;
  height: 1080px;
  margin: 0;
  overflow: hidden;
  background: #0f172a;
}
h1 {
  color: #38bdf8;
  font-family: sans-serif;
  font-size: 80px;
  padding: 200px 120px;
}
</style>
</head>
<body>
  <h1>Smoke Test Slide</h1>
</body>
</html>
"""


def test_render_png_is_1920x1080(tmp_path):
    """Render a minimal HTML string and assert the PNG is exactly 1920×1080.

    Skips if:
    - playwright not installed (module-level importorskip)
    - Chromium binary is missing (Error caught inside body)
    """
    from playwright.sync_api import Error as PWError  # noqa: PLC0415 — lazy

    # Defer SlideRenderer import so the test is a clean failure (not a
    # collection error) before Task 3 creates integrations/playwright.py.
    from avideo.integrations.playwright import SlideRenderer  # noqa: PLC0415

    out_png = tmp_path / "slide_smoke.png"

    try:
        with SlideRenderer() as renderer:
            renderer.render_to_png(_MINIMAL_HTML, out_png)
    except PWError as exc:
        pytest.skip(f"Chromium browser not available: {exc}")

    assert out_png.exists(), "PNG file was not created"

    from PIL import Image  # noqa: PLC0415 — dev dependency

    img = Image.open(out_png)
    assert img.size == (1920, 1080), (
        f"Expected PNG size (1920, 1080), got {img.size}"
    )
