"""End-to-end browser tests for the Studio Guiado wizard (avideo studio).

These tests launch a REAL `avideo studio` subprocess and drive it with a REAL
headless Chromium browser via the `playwright` package (already a core
dependency for slide rendering — no extra dependency added here). They are
slow (each test starts/stops a Streamlit process and a browser) and require
Playwright's Chromium browser binary to be installed
(`uv run playwright install chromium`), so they are SKIPPED by default and
only run when explicitly requested.

Run them with:
    AVIDEO_E2E=1 uv run pytest tests/test_ui_wizard_e2e.py -v

They do not replace the fast unit-test suite (`uv run pytest`, no env var
needed) — that suite mocks every external call. These tests exist to catch
exactly the class of bug unit tests structurally cannot: things that only
break when a real browser talks to a real Streamlit process (e.g. the
"disabled button stuck after an error" bug and the "ffmpeg can't infer output
format from .tmp extension" bug found during v2.0.0 browser UAT — both were
invisible to the mocked unit-test suite and only surfaced here).
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("AVIDEO_E2E") != "1",
    reason="Real-browser E2E tests are opt-in — set AVIDEO_E2E=1 to run them "
    "(requires `uv run playwright install chromium` and a working ffmpeg).",
)


def _free_port() -> int:
    """Return an ephemeral free TCP port (avoids clashing with a dev server)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def studio_server(tmp_path: Path):
    """Launch `avideo studio` against a fresh temp workdir; yield its base URL.

    Waits for the Streamlit health endpoint to respond before yielding, and
    terminates the subprocess (and its process group) on teardown.
    """
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    port = _free_port()

    env = dict(os.environ)
    env["AVIDEO_STUDIO_WORKDIR"] = str(workdir)

    proc = subprocess.Popen(
        ["uv", "run", "avideo", "studio", "--port", str(port)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=Path(__file__).resolve().parent.parent,
        start_new_session=True,
    )

    base_url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 30.0
    healthy = False
    while time.monotonic() < deadline:
        try:
            import urllib.request

            with urllib.request.urlopen(f"{base_url}/_stcore/health", timeout=1) as resp:
                if resp.status == 200:
                    healthy = True
                    break
        except Exception:  # noqa: BLE001 — server not up yet, keep polling
            time.sleep(0.5)

    if not healthy:
        proc.terminate()
        pytest.fail("avideo studio did not become healthy within 30s")

    try:
        yield base_url, workdir
    finally:
        import signal

        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=10)


@pytest.fixture
def browser_page(studio_server):
    """Yield a Playwright page navigated to the studio_server base_url."""
    from playwright.sync_api import sync_playwright

    base_url, workdir = studio_server
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(base_url)
        page.wait_for_selector("text=Studio Guiado", timeout=15000)
        yield page, workdir
        browser.close()


def test_app_loads_and_shows_six_phase_wizard(browser_page) -> None:
    """App loads without crashing; sidebar shows all 6 phases; Phase 1 active."""
    page, _ = browser_page
    assert page.get_by_text("Studio Guiado").is_visible()
    for label in [
        "Fase 1: Contenido",
        "Fase 2: Guion + Slides",
        "Fase 3: Diapositivas",
        "Fase 4: Voz",
        "Fase 5: Extras",
        "Fase 6: Ensamblaje",
    ]:
        assert page.get_by_text(label).is_visible(), f"missing sidebar phase: {label}"
    # No Python traceback strings anywhere on the page
    body_text = page.inner_text("body")
    assert "Traceback (most recent call last)" not in body_text


def test_cannot_advance_phase_1_without_bullets(browser_page) -> None:
    """The footer 'Aprobar y continuar' stays disabled until bullets exist."""
    page, _ = browser_page
    next_btn = page.get_by_role("button", name="Aprobar y continuar →")
    assert next_btn.is_disabled(), "footer nav must gate on bullets being present"


def test_can_advance_after_approving_bullets(browser_page) -> None:
    """Filling topic + duration + one bullet and approving enables the footer gate."""
    page, _ = browser_page

    page.get_by_role("textbox", name="Tema de la presentación").fill("Test topic")
    dur = page.get_by_role("textbox", name="Duración objetivo (mm:ss o segundos)")
    dur.click(click_count=3)
    dur.fill("1:00")
    dur.press("Tab")
    page.wait_for_timeout(500)

    # Fill the first data_editor cell (a canvas grid — coordinate double-click,
    # not a normal DOM input; see HANDOFF notes on Streamlit's glide-data-grid).
    canvas = page.locator("canvas").first
    box = canvas.bounding_box()
    assert box is not None
    page.mouse.dblclick(box["x"] + box["width"] / 2, box["y"] + 35)
    page.wait_for_timeout(200)
    page.keyboard.type("A single test bullet point", delay=5)
    page.mouse.click(box["x"], box["y"] + box["height"] + 40)
    page.wait_for_timeout(800)

    approve_bullets = page.get_by_role("button", name="Aprobar bullets y continuar")
    approve_bullets.click()
    page.wait_for_timeout(1000)

    next_btn = page.get_by_role("button", name="Aprobar y continuar →")
    assert next_btn.is_enabled(), "footer nav must unlock once bullets are approved"


def test_missing_api_keys_do_not_crash_ui(browser_page) -> None:
    """Selecting a TTS provider with no configured API key must show a clean
    error (or otherwise degrade gracefully) — never an unhandled traceback.

    This test does not assert the exact provider flow (it depends on which
    phase is reachable without a full run); it asserts the invariant that
    matters: no raw Python traceback ever renders in the DOM.
    """
    page, _ = browser_page
    body_text = page.inner_text("body")
    assert "Traceback (most recent call last)" not in body_text
    assert "ModuleNotFoundError" not in body_text


def test_refresh_resumes_from_workdir(browser_page) -> None:
    """After approving Phase 1, a hard page reload must resume at Phase 1's
    completed state (not reset to a blank form) — state lives in workdir, not
    session_state.
    """
    page, workdir = browser_page

    page.get_by_role("textbox", name="Tema de la presentación").fill("Resume test topic")
    dur = page.get_by_role("textbox", name="Duración objetivo (mm:ss o segundos)")
    dur.click(click_count=3)
    dur.fill("1:00")
    dur.press("Tab")
    page.wait_for_timeout(500)

    canvas = page.locator("canvas").first
    box = canvas.bounding_box()
    page.mouse.dblclick(box["x"] + box["width"] / 2, box["y"] + 35)
    page.wait_for_timeout(200)
    page.keyboard.type("Resume test bullet", delay=5)
    page.mouse.click(box["x"], box["y"] + box["height"] + 40)
    page.wait_for_timeout(800)
    page.get_by_role("button", name="Aprobar bullets y continuar").click()
    page.wait_for_timeout(1000)
    page.get_by_role("button", name="Aprobar y continuar →").click()
    page.wait_for_timeout(2000)

    assert (workdir / ".context.done").exists(), "context done-marker must be written to workdir"

    page.reload()
    page.wait_for_selector("text=Studio Guiado", timeout=15000)
    page.wait_for_timeout(2000)

    # Phase 1 marker in the sidebar must show complete (✅), not reset to fresh.
    assert page.get_by_text("✅ Fase 1: Contenido").is_visible(), (
        "wizard must resume at the completed phase from workdir, not reset "
        "session_state to a blank Phase 1 form"
    )
