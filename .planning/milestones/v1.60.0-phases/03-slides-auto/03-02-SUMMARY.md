---
phase: 03-slides-auto
plan: "02"
subsystem: slides-auto-stage
tags: [slides, playwright, jinja2, python-lucide, theme, cost-estimator, pipeline-swap]
dependency_graph:
  requires:
    - plan 03-01: SlideRenderer, ThemeConfig, templates, embed_font_face, icon() contract
    - plan 02-xx: storyboard.json checkpoint (StoryboardOutput) written by StoryboardStage
  provides:
    - SlidesAutoStage (stages/slides_auto.py) — orchestrates theme→Jinja2→Playwright→PNG
    - PIPELINE_STAGES with SlidesAutoStage replacing SlidesStub (stubs.py)
    - estimate_theme_tokens() (cost_estimator.py) — closes Pitfall 6 dry-run gap
  affects:
    - orchestrator: slides stage now renders real PNGs; done-marker still written by orchestrator
    - cost_estimator: dry-run TOTAL now includes slides/theme LLM estimate
    - All orchestrator tests: updated to mock SlideRenderer + slides_auto.call_structured
tech_stack:
  added: []
  patterns:
    - Module-scope call_structured import (mockable, mirrors storyboard.py pattern)
    - theme.yaml idempotency: load-if-exists > AI-generate-and-write > DEFAULT_THEME fallback
    - Jinja2 PackageLoader with autoescape=True + icon() Lucide global
    - estimate_theme_tokens pure arithmetic heuristic (no network, offline dry-run)
key_files:
  created:
    - src/avideo/stages/slides_auto.py
    - tests/test_slides_auto.py
  modified:
    - src/avideo/stages/stubs.py (SlidesAutoStage swap in PIPELINE_STAGES)
    - src/avideo/utils/cost_estimator.py (estimate_theme_tokens + slides row)
    - tests/test_cost_estimator.py (+5 theme-token tests)
    - tests/test_orchestrator.py (SlideRenderer + slides_auto mocks added)
decisions:
  - "theme.yaml location: project root (persistent/editable); precedence: user > AI > DEFAULT_THEME"
  - "chart_slide with no numeric data: renders icon+bullets layout (no invented data; from 03-01)"
  - "estimate_theme_tokens heuristic: in_tok = 300 + est_slides*40; out_tok = 250 (compact ThemeConfig JSON)"
  - "templates+fonts must be packaged via importlib.resources / MANIFEST.in in Phase 7 (PKG-01)"
  - "SlidesAutoStage.__init__ accepts theme_path kwarg so tests inject a tmp path (no real repo theme.yaml touched)"
metrics:
  duration_minutes: 25
  completed_date: "2026-05-25"
  tasks_completed: 2
  tests_added: 23
  tests_total: 147
---

# Phase 3 Plan 2: SlidesAutoStage Summary

SlidesAutoStage wiring layer: reads storyboard.json → resolves theme (idempotent AI call via call_structured + theme.yaml + DEFAULT_THEME fallback) → renders each SlideSpec to workdir/slides/slide_XX.png via Jinja2+Playwright → returns SlidesOutput; cost estimator now includes slides/theme LLM call in dry-run total.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 RED | Failing tests for SlidesAutoStage | 910325f | tests/test_slides_auto.py |
| 1 GREEN | SlidesAutoStage — theme resolution + render orchestration | 21c3f86 | stages/slides_auto.py |
| 2 | PIPELINE_STAGES swap + cost_estimator theme-token gap | 4cd4ef0 | stubs.py, cost_estimator.py, test_cost_estimator.py, test_orchestrator.py |

## Architecture

### theme.yaml Resolution (D-01, D-03)

```
theme_path (project root / overridable in tests)
    │
    ├── EXISTS? → ThemeConfig.model_validate(yaml.safe_load(...)) → DONE (idempotent, D-03)
    │
    └── ABSENT → call_structured(emit_theme, ThemeConfig, max_tokens=2048)
                    ├── SUCCESS → write theme.yaml + return ThemeConfig
                    └── ANY EXCEPTION → return DEFAULT_THEME (D-01, never abort)
```

### theme.yaml Location Decision

**Location:** project root (`Path("theme.yaml")` by default; overridable via `SlidesAutoStage(theme_path=...)` for tests).

**Rationale:** Project-root placement makes it persistent across runs and easy for the user to edit. A workdir-scoped path would be deleted on workdir reset; a hardcoded internal path would prevent user editing.

**Precedence:** user-edited theme.yaml > AI-generated theme.yaml > DEFAULT_THEME (in-code fallback).

**Idempotency:** The file is written once (on first AI generation) and never regenerated unless deleted manually. This bounds the API cost to one call per project and respects user edits (D-03, T-03-07).

### estimate_theme_tokens Heuristic

```python
est_slides = clamp(round(duration / 25), 3, 20)
in_tok  = 300 + est_slides * 40   # system prompt (~200) + slide-title summary (~40/slide)
out_tok = 250                      # compact ThemeConfig JSON (~200-300 tokens)
```

**Rationale:** The theme prompt summarises storyboard slide titles (one line per slide, ~40 tokens) plus a fixed system prompt (~300 tokens). Output is a compact ThemeConfig JSON (palette + typography + 4 integer fields) — empirically ~200-300 tokens. This is a one-time cost (idempotent after first run, D-03).

**Offline contract:** Pure arithmetic, no network call, no API key read. Preserves `--dry-run` offline guarantee (T-03-06, CLI-06).

### chart_slide Numeric Data Decision (from 03-01)

chart_slide macro parses numeric values from bullets using a character-scan approach in Jinja2. If no numbers are found, it renders an icon+bullets layout instead (no invented data). This means a chart slide with only qualitative bullets degrades gracefully to a visually clean bullets layout.

### Templates + Fonts Packaging Reminder (PKG-01, Phase 7)

`SlidesAutoStage._build_jinja_env` uses `PackageLoader("avideo.templates", package_path="")` and `_bundled_font_path()` uses `__file__`-relative path. For the wheel to include these assets:
- `pyproject.toml` must declare `[tool.setuptools.package-data] avideo = ["templates/*.j2", "assets/fonts/*.ttf"]`
- Or equivalent for the build backend in use.
- Phase 7 (PKG-01) must verify `importlib.resources.files("avideo.templates")` resolves correctly inside the installed wheel.

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

### Deviation: test_unknown_visual_type_falls_back_to_bullets approach

**Found during:** Task 1 test implementation

**Issue:** The plan suggested monkey-patching `storyboard.slides[0].__dict__["visual_type"]` with a fake object to simulate an unknown visual_type, then calling `workdir.write_checkpoint("storyboard", storyboard)` with that patched object. Pydantic v2's `model_dump_json()` cannot serialize the fake object (serialization error before the stage code even runs).

**Fix:** Replaced with direct Jinja2 template rendering test: built a `FakeSlide` object with `visual_type.value = "unknown_legacy_type"` and rendered `base.html.j2` directly. This tests the actual fallback mechanism (the `renderers.get(slide.visual_type.value, bullets_slide)` dispatch in the base template) without serialization issues.

**Classification:** Rule 1 (bug in test design — test never reached RED correctly).

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (test) | 910325f | test(03-02): add failing tests for SlidesAutoStage |
| GREEN (feat) | 21c3f86 | feat(03-02): implement SlidesAutoStage |
| Task 2 (feat) | 4cd4ef0 | feat(03-02): PIPELINE_STAGES swap + cost estimator |

## Known Stubs

None — SlidesAutoStage is the real implementation. SlideRenderer launches Chromium (mocked in unit tests; real Chromium used in smoke test from 03-01).

## Threat Flags

None — no new network endpoints or auth paths. All changes are:
- Offline rendering (Playwright set_content, no goto(http://...))
- theme.yaml at project root (local filesystem write only)
- estimate_theme_tokens is pure arithmetic (no network)
- call_structured for theme uses forced tool-use with ThemeConfig schema (T-03-05 mitigated)

## Self-Check: PASSED

Files verified:
- `src/avideo/stages/slides_auto.py` — FOUND
- `src/avideo/stages/stubs.py` (contains SlidesAutoStage()) — FOUND
- `src/avideo/utils/cost_estimator.py` (contains estimate_theme_tokens) — FOUND
- `tests/test_slides_auto.py` — FOUND
- `tests/test_cost_estimator.py` — FOUND

Commits verified:
- 910325f (RED) — FOUND
- 21c3f86 (GREEN) — FOUND
- 4cd4ef0 (Task 2) — FOUND

Full test suite: `uv run pytest -q` → 147 passed, 5 warnings
Pipeline verification: `SlidesAutoStage` confirmed in PIPELINE_STAGES slides slot
Dry-run verification: `estimate_theme_tokens` present and returns positive ints offline
