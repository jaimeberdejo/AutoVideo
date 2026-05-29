---
phase: 03-slides-auto
plan: "01"
subsystem: slides-rendering-primitives
tags: [playwright, jinja2, python-lucide, theming, fonts, rendering, offline]
dependency_graph:
  requires: []
  provides:
    - SlideRenderer (integrations/playwright.py) — one browser/run, exact 1920x1080 PNG
    - ThemeConfig + DEFAULT_THEME (models/theme.py) — Pydantic v2 theme model
    - base.html.j2 + macros.html.j2 (templates/) — 7-macro Jinja2 layout system
    - embed_font_face() — base64 @font-face CSS helper
    - fake_storyboard fixture (conftest.py) — 7 VisualType slides for plan 03-02 tests
  affects:
    - plan 03-02: SlideRenderer + templates are wired together in SlidesAutoStage
    - Phase 7: playwright install chromium required in CI/Dockerfile; font OFL license OK
tech_stack:
  added:
    - playwright==1.60.0 (runtime)
    - jinja2==3.1.6 (runtime)
    - python-lucide==0.2.24 (runtime)
    - pillow>=12.2.0 (dev, PNG dimension assertions)
  patterns:
    - Pydantic v2 model with nested default_factory fields
    - Jinja2 PackageLoader with autoescape=True
    - sync_playwright context manager (one browser per run)
    - base64 data-URI @font-face embedding (offline fonts)
    - inline SVG code-drawn charts/diagrams (no external chart libs)
key_files:
  created:
    - src/avideo/integrations/playwright.py
    - src/avideo/models/theme.py
    - src/avideo/models/__init__.py (ThemeConfig/DEFAULT_THEME added)
    - src/avideo/templates/__init__.py
    - src/avideo/templates/base.html.j2
    - src/avideo/templates/macros.html.j2
    - src/avideo/assets/fonts/Inter-Regular.ttf
    - src/avideo/assets/fonts/.gitkeep
    - tests/test_slides_render.py
    - tests/test_theme.py
  modified:
    - pyproject.toml (3 runtime deps + pillow dev dep)
    - tests/conftest.py (fake_storyboard fixture)
    - uv.lock
decisions:
  - "chart_slide parses numeric values from bullets (regex-free character scan); if no numbers found, renders icon+bullets layout (no invented data)"
  - "ThemeConfig nested models use default_factory=Palette/Typography (Pydantic v2)"
  - "macros.html.j2 maps keyword patterns in bullet text to Lucide icon names (ICON_MAP dict)"
  - "Inter variable font (OFL) bundled at src/avideo/assets/fonts/Inter-Regular.ttf"
metrics:
  duration_minutes: 35
  completed_date: "2026-05-25"
  tasks_completed: 3
  tests_added: 11
  tests_total: 124
---

# Phase 3 Plan 1: Slides Rendering Primitives Summary

Playwright renderer (SlideRenderer), ThemeConfig Pydantic model with DEFAULT_THEME fallback, Jinja2 base template + 7 per-visual_type macros with inline SVG charts and offline Lucide icons, Inter OFL font bundle, and Wave-0 test scaffolding covering all 7 VisualType dispatch paths.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Add deps + bundle OFL font + Wave-0 test scaffolding | 07600e3 | pyproject.toml, conftest.py, test_slides_render.py, Inter-Regular.ttf |
| 2 RED | ThemeConfig tests (failing) | 79d2836 | tests/test_theme.py |
| 2 GREEN | ThemeConfig + DEFAULT_THEME + Jinja2 templates | 5e6645e | models/theme.py, templates/base.html.j2, templates/macros.html.j2 |
| 3 GREEN | SlideRenderer — one browser/run, base64 fonts | 0005a63 | integrations/playwright.py |

## Dependencies Added

### Runtime
| Package | Version | Purpose |
|---------|---------|---------|
| `playwright` | `>=1.60.0` | Chromium headless render HTML → PNG |
| `jinja2` | `>=3.1.6` | Template engine for slide HTML |
| `python-lucide` | `>=0.2.24` | Lucide SVG icons offline (SQLite, 1694 icons) |

### Dev
| Package | Version | Purpose |
|---------|---------|---------|
| `pillow` | `>=12.2.0` | PNG dimension assertions in smoke test only |

### CI / Dockerfile requirement
After `pip install playwright` (or `uv sync`), run:
```bash
uv run playwright install chromium
```
For Phase 7 Docker, use the base image `mcr.microsoft.com/playwright/python:v1.60.0-noble` which includes Chromium pre-installed.

## Bundled Font

**Font:** Inter variable font (Google Fonts static)
**File:** `src/avideo/assets/fonts/Inter-Regular.ttf` (876 KB)
**License:** SIL Open Font License v1.1 (OFL) — redistribution permitted in source and binary forms.
**Source URL:** `https://github.com/google/fonts/raw/refs/heads/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf`
**License compliance:** OFL permits embedding in wheels and Docker images. No copyright attribution required in the UI, but SIL OFL copyright notice should be included in Phase 7 NOTICE/LICENSE file.

## Injection Contract for Plan 03-02

Plan 03-02 (`stages/slides_auto.py`) must satisfy the following injection contract when rendering slides:

### `font_face_css` slot
```python
from avideo.integrations.playwright import embed_font_face
from pathlib import Path
import importlib.resources as pkg

# Locate the bundled font at runtime
font_path = Path(__file__).parent.parent / "assets" / "fonts" / "Inter-Regular.ttf"
font_face_css = embed_font_face(font_path, family="Inter")
# Inject into template render context:
html = template.render(slide=slide, theme=theme, font_face_css=font_face_css)
```

### `icon()` global
```python
from lucide import lucide_icon

def icon(name: str, size: int = 48, stroke: str = "currentColor") -> str:
    return lucide_icon(name, width=size, height=size, stroke=stroke)

env.globals["icon"] = icon
# Templates call: {{ icon('chart-bar', size=64, stroke=theme.palette.accent)|safe }}
# The |safe is correct: SVG is generated by python-lucide (our code), not user text.
```

### Jinja2 Environment setup
```python
from jinja2 import Environment, PackageLoader

env = Environment(
    loader=PackageLoader("avideo.templates", package_path=""),
    autoescape=True,  # REQUIRED for T-03-02 (XSS mitigation on user/LLM text)
)
env.globals["icon"] = icon
template = env.get_template("base.html.j2")
```

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (test) | 79d2836 | test(03-01): add failing tests for ThemeConfig and Jinja2 base template |
| GREEN (feat) | 5e6645e | feat(03-01): ThemeConfig model, DEFAULT_THEME, Jinja2 templates |
| GREEN (feat) | 0005a63 | feat(03-01): SlideRenderer — smoke test passes |

## Deviations from Plan

None — plan executed exactly as written.

Chart data extraction (Open Q #2 decision): implemented character-scan approach in Jinja2 macro to parse numeric values from bullets without regex; falls back to icon+bullets layout when no numbers found (no invented data).

## Known Stubs

None — this plan creates primitives only; no data wiring exists yet. Plan 03-02 wires SlideRenderer + templates into SlidesAutoStage.

## Threat Flags

None — no new network endpoints or auth paths introduced. All rendering is offline (set_content + base64 fonts, no goto(http://...), no external chart libs). Templates use autoescape=True.

## Self-Check: PASSED

Verified:
- `src/avideo/integrations/playwright.py` — FOUND
- `src/avideo/models/theme.py` — FOUND
- `src/avideo/templates/base.html.j2` — FOUND
- `src/avideo/templates/macros.html.j2` — FOUND
- `src/avideo/assets/fonts/Inter-Regular.ttf` — FOUND
- `tests/test_slides_render.py` — FOUND
- `tests/test_theme.py` — FOUND
- Commit 07600e3 — FOUND (feat: deps + font + scaffolding)
- Commit 79d2836 — FOUND (test: RED ThemeConfig)
- Commit 5e6645e — FOUND (feat: ThemeConfig + templates GREEN)
- Commit 0005a63 — FOUND (feat: SlideRenderer GREEN)
- `uv run pytest -q` → 124 passed, 5 warnings
