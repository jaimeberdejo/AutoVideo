---
phase: 3
slug: slides-auto
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-25
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-mock 3.x (113 existing tests green) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=["tests"], pythonpath=["src"]) |
| **Quick run command** | `uv run pytest tests/test_slides_auto.py -x -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | unit <1s; smoke (real Chromium) ~3-5s |

---

## Sampling Rate

- **After every task commit:** `uv run pytest tests/test_slides_auto.py -x -q` (unit, Playwright + call_structured mocked — fast)
- **After every plan wave:** `uv run pytest -q` (full suite, incl. real-Chromium smoke if browser present)
- **Before `/gsd-verify-work`:** Full suite green
- **Max feedback latency:** <5 seconds

---

## Per-Task Verification Map

| Req | Behavior | Test Type | Automated Command | File Exists | Status |
|-----|----------|-----------|-------------------|-------------|--------|
| SLIDE-01 | 1 slide → PNG exactly 1920×1080 (real Chromium) | smoke | `uv run pytest tests/test_slides_render.py::test_render_png_is_1920x1080 -x -q` | ❌ W0 | ⬜ |
| SLIDE-01 | `SlidesAutoStage.run` → N PNGs, `SlidesOutput(png_paths)` (Playwright mocked) | unit | `uv run pytest tests/test_slides_auto.py -k renders_all -x -q` | ❌ W0 | ⬜ |
| SLIDE-01 | stage_name=="slides" + checkpoint contract preserved | unit | `uv run pytest tests/test_slides_auto.py -k contract -x -q` | ❌ W0 | ⬜ |
| SLIDE-02 | Rendered HTML has inline SVG (Lucide), NO external `<img src>` | unit | `uv run pytest tests/test_slides_auto.py -k offline_only -x -q` | ❌ W0 | ⬜ |
| SLIDE-02 | `lucide_icon('chart-bar')` returns offline SVG (no network) | unit | `uv run pytest tests/test_slides_auto.py -k lucide_offline -x -q` | ❌ W0 | ⬜ |
| SLIDE-03 | Existing theme.yaml NOT regenerated (idempotent; call_structured not called) | unit | `uv run pytest tests/test_slides_auto.py -k theme_idempotent -x -q` | ❌ W0 | ⬜ |
| SLIDE-03 | No theme.yaml → call_structured generates ThemeConfig (mocked) + writes file | unit | `uv run pytest tests/test_slides_auto.py -k theme_generated -x -q` | ❌ W0 | ⬜ |
| SLIDE-03 | call_structured fails → falls back to DEFAULT_THEME | unit | `uv run pytest tests/test_slides_auto.py -k theme_fallback -x -q` | ❌ W0 | ⬜ |
| cross | All 7 visual_types render without KeyError | unit | `uv run pytest tests/test_slides_auto.py -k all_visual_types -x -q` | ❌ W0 | ⬜ |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Smoke test (SLIDE-01) — real vs mock:** Real Chromium render needed for TEST-03 (Phase 7) + 1920×1080 validation; chromium-1217 cached locally, CI runs `playwright install chromium`. Use `pytest.importorskip("playwright")` + skip if executable missing so the suite never breaks on browserless envs. Stage unit tests mock the renderer + call_structured.

---

## Wave 0 Requirements

- [ ] `tests/test_slides_auto.py` — stage unit (theme idempotency, visual_type dispatch, PNG count, offline-only) with Playwright + call_structured mocked — SLIDE-01/02/03
- [ ] `tests/test_slides_render.py` — real smoke: HTML → Chromium → PNG, assert (1920,1080) with Pillow; importorskip/skip if no browser — SLIDE-01 (+ TEST-03 prep)
- [ ] `tests/conftest.py` — `fake_storyboard` fixture (StoryboardOutput with several visual_types)
- [ ] `uv add --dev pillow` (PNG dimension asserts)
- [ ] Document `playwright install chromium` for CI

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Slide visual quality / theme aesthetics | SLIDE-03 | Subjective design judgment | Run full `auto` pipeline; open `workdir/slides/slide_*.png`; confirm legible, on-theme, no overflow |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
