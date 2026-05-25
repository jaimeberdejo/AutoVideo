"""Playwright-based HTML → PNG renderer for the slides-auto pipeline.

This module is the ONLY place in the codebase that touches the Playwright API
directly.  The slides stage (``stages/slides_auto.py``) calls ``SlideRenderer``
and ``embed_font_face``; it never imports from ``playwright`` itself — mirroring
how ``stages/storyboard.py`` only calls ``call_structured`` and never imports
``anthropic`` directly.

Design decisions implemented here:

- D-05: ONE browser instance per run.  ``SlideRenderer`` is a context manager;
  ``__enter__`` starts ``sync_playwright`` and launches Chromium once.
  ``__exit__`` closes the browser and stops Playwright.  NEVER open/close a
  browser per slide — that is 10× slower (Anti-Pattern).

- D-06: Output PNG is exactly 1920×1080 pixels.  Enforced by:
  ``new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)``
  DSF=1 → physical pixels == CSS pixels (RESEARCH Pitfall 3/Anti-Pattern).

- D-08 / T-03-01: Offline render — nothing leaves the machine.  Fonts must be
  embedded as base64 data-URIs (see ``embed_font_face``). ``set_content`` has
  no base URL, so relative font paths would silently 404 (RESEARCH Pitfall 2).
  No ``goto("http://...")`` is ever called here.

RESEARCH Pitfall 1 — fonts.ready pitfall:
  ``document.fonts.ready`` resolves immediately if no font has been *requested*
  yet.  We call ``f.load()`` on every declared face BEFORE ``fonts.ready`` to
  force the load.  Verified empirically in the Phase-3 research session.

RESEARCH Pitfall 3 — exact 1920×1080:
  ``device_scale_factor=1``, ``full_page`` stays ``False`` (default),
  CSS must set ``html,body { width:1920px; height:1080px; overflow:hidden }``.

Security — T-03-01:
  ``set_content`` is used (not ``goto``), so no network request is made.
  ``embed_font_face`` converts a local .ttf file to a base64 data-URI — the
  font bytes never leave the machine.  ANTHROPIC_API_KEY is irrelevant here.
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Union


# ---------------------------------------------------------------------------
# SlideRenderer — context manager, ONE browser per run (D-05)
# ---------------------------------------------------------------------------


class SlideRenderer:
    """Context manager that owns one Chromium browser for the entire run.

    Usage::

        with SlideRenderer() as renderer:
            renderer.render_to_png(html_string, Path("slide_00.png"))
            renderer.render_to_png(html_string_2, Path("slide_01.png"))

    ``__enter__``: starts ``sync_playwright`` and launches Chromium headless.
    ``__exit__``: closes the browser and stops Playwright (guards for None so
    a failed ``__enter__`` does not raise a secondary exception).

    Raises:
        playwright.sync_api.Error: If Chromium is not installed (run
            ``uv run playwright install chromium``).  The smoke test catches
            this and skips gracefully.
    """

    def __init__(self) -> None:
        self._pw = None
        self._browser = None

    def __enter__(self) -> "SlideRenderer":
        """Start sync_playwright and launch Chromium (once per run, D-05)."""
        from playwright.sync_api import sync_playwright  # noqa: PLC0415 — lazy

        self._pw = sync_playwright().start()
        # headless=True is the default; explicit to make intent clear.
        self._browser = self._pw.chromium.launch(headless=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close the browser and stop Playwright; guards for None."""
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._pw is not None:
            self._pw.stop()
            self._pw = None

    def render_to_png(
        self,
        html: str,
        out_path: Union[str, Path],
    ) -> None:
        """Render an HTML string to a PNG file at exactly 1920×1080 pixels.

        Args:
            html: Complete HTML document string.  Must embed all fonts as
                base64 data-URIs (``embed_font_face``); ``set_content`` has
                no base URL so relative font paths silently 404 (Pitfall 2).
            out_path: Destination path for the PNG file.  Parent directory
                must exist.

        Raises:
            playwright.sync_api.Error: On any Playwright/Chromium error.
        """
        assert self._browser is not None, (
            "SlideRenderer must be used as a context manager "
            "(call __enter__ before render_to_png)"
        )

        page = self._browser.new_page(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,  # DSF=1 → PNG is exactly 1920×1080 (Pitfall 3)
        )
        try:
            page.set_content(html, wait_until="load")

            # CRITICAL — RESEARCH Pitfall 1:
            # Request every @font-face explicitly (.load()) BEFORE fonts.ready.
            # fonts.ready resolves immediately if no font was yet requested,
            # yielding a screenshot with fallback/system fonts.
            # Verified empirically: with this pattern, fonts.check() → True offline.
            page.evaluate(
                """async () => {
                    const faces = [...document.fonts];
                    await Promise.all(faces.map(f => f.load().catch(() => {})));
                    await document.fonts.ready;
                }"""
            )

            page.screenshot(
                path=str(out_path),
                type="png",
                # animations="disabled" freezes CSS/JS animations so the
                # screenshot is deterministic (no mid-animation frames).
                animations="disabled",
                # full_page=False (default) — captures the viewport only.
                # full_page=True would follow scrollable content and break
                # the 1920×1080 guarantee if content overflows (Pitfall 3).
            )
        finally:
            page.close()


# ---------------------------------------------------------------------------
# embed_font_face — build a base64 @font-face CSS string (offline, D-08)
# ---------------------------------------------------------------------------


def embed_font_face(font_path: Union[str, Path], family: str) -> str:
    """Read a .ttf font file and return a base64 @font-face CSS declaration.

    The returned string can be injected into the ``font_face_css`` template
    slot in ``base.html.j2`` so that Chromium can load the font without any
    network access (D-08, RESEARCH Pitfall 2).

    Args:
        font_path: Absolute or relative path to a ``.ttf`` font file.
        family: The ``font-family`` name to declare (e.g. ``"Inter"``).
            Must match the value used in ``theme.typography.heading/body``.

    Returns:
        A complete ``@font-face`` CSS rule string, e.g.::

            @font-face {
              font-family: 'Inter';
              src: url(data:font/ttf;base64,AAAA...) format('truetype');
            }

    Raises:
        FileNotFoundError: If ``font_path`` does not exist.
    """
    font_bytes = Path(font_path).read_bytes()
    b64 = base64.b64encode(font_bytes).decode("ascii")
    return (
        f"@font-face {{\n"
        f"  font-family: '{family}';\n"
        f"  src: url(data:font/ttf;base64,{b64}) format('truetype');\n"
        f"}}\n"
    )
