---
phase: 07-empaquetado-tests-docs
plan: "02"
subsystem: tests
tags: [tests, storyboard, timing, slides, playwright, verification]
dependency_graph:
  requires: []
  provides: [TEST-01, TEST-02, TEST-03]
  affects: []
tech_stack:
  added: []
  patterns:
    - mocker.patch at import site (no real API call — TEST-01)
    - largest-remainder apportionment exact-sum invariant (TEST-02)
    - pytest.importorskip + PWError skip for headless Chromium guard (TEST-03)
key_files:
  created: []
  modified: []
decisions:
  - "No code changes made: all three tests already satisfy their requirements; suite is 303/303 green"
metrics:
  duration: "2 minutes"
  completed: "2026-05-26T00:26:01Z"
  tasks_completed: 2
  files_changed: 0
---

# Phase 7 Plan 02: Core Test Verification Summary

**One-liner:** Verified TEST-01/02/03 each cover their Nyquist contract requirement; all 303 tests pass, no gaps found, no code changes needed.

## What Was Done

This plan is verification-only. The three minimal core tests were audited against their requirements and the full suite was confirmed green.

### TEST-01: Storyboard with Anthropic API mocked

File: `tests/test_storyboard.py`

**Requirement:** StoryboardStage must run without a real Anthropic API call or API key.

**Verification result: SATISFIED**

- `mocker.patch("avideo.stages.storyboard.call_structured", return_value=fake)` patches at the correct import site (the module that calls the function, not the definition site).
- `assert mock_cs.called` in `test_prompt_contains_bullet_text` explicitly asserts that the mock was invoked (no real network call made).
- `result is fake` in `test_run_returns_storyboard_from_mock` confirms the stage returns the mocked value, not a real API response.
- 8 passing tests cover: return value from mock, prompt contains bullet text, language honored, visual_type is enum, stage/checkpoint names, no context checkpoint, with context checkpoint, duration in prompt.

**No gap found. No changes made.**

### TEST-02: Timing director — exact-sum apportionment + word budget

File: `tests/test_timing.py`

**Requirement:** Sum of slide seconds == config.duration EXACTLY; word_budget == round(seconds * wpm / 60) for every slide.

**Verification result: SATISFIED**

- `test_exact_sum` (parametrized: 3 duration/slide combinations) asserts `sum(s.seconds for s in output.slides) == duration` exactly.
- `test_exact_sum_clamps_active_still_holds` confirms the invariant holds even when min-clamp forces redistribution.
- `test_word_budget` (parametrized: wpm in [120, 150, 180]) asserts `s.word_budget == round(s.seconds * wpm / 60)` for every slide.
- `test_no_slide_below_min_seconds` / `test_no_slide_above_max_seconds` cover clamp bounds.
- `apportion_seconds` unit tests (6) confirm the pure helper: sums to total, ties, zero weights, single slide, large counts.

**No gap found. No changes made.**

### TEST-03: Slide HTML -> PNG render at 1920x1080

File: `tests/test_slides_render.py`

**Requirement:** SlideRenderer.render_to_png produces a PNG of exactly (1920, 1080) pixels; skips cleanly if Chromium is absent.

**Verification result: SATISFIED**

- `pytest.importorskip("playwright")` at module level skips the entire file if the playwright package is not installed.
- `except PWError as exc: pytest.skip(...)` skips gracefully if the Chromium binary is missing at runtime.
- `assert img.size == (1920, 1080)` directly verifies the dimensional requirement after opening the PNG with Pillow.
- The test ran and PASSED (Chromium is installed in this environment).

**No gap found. No changes made.**

## Full Suite Result

```
303 passed, 5 warnings in 3.08s
```

- 0 failures, 0 errors.
- 5 DeprecationWarnings from `builtins` in PyMuPDF's SwigPy types — pre-existing, not caused by this plan.
- No skips in this run (Chromium available).

## Deviations from Plan

None — plan executed exactly as written. No test files were modified. The three tests already covered their requirements in full.

## Known Stubs

None identified in the three test files.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. This plan is verification-only.

## Self-Check: PASSED

- tests/test_storyboard.py: READ, verified, unchanged
- tests/test_timing.py: READ, verified, unchanged
- tests/test_slides_render.py: READ, verified, unchanged
- Full suite: 303 passed, 0 failed (confirmed via `uv run pytest -q`)
