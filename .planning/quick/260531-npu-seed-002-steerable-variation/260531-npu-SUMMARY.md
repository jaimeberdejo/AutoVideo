---
quick_id: 260531-npu
phase: quick
plan: 260531-npu
subsystem: feedback-transport, stages, pipeline_ops, ui
tags: [seed-002, steerable-variation, tdd, feedback, prompt-injection]
dependency_graph:
  requires: []
  provides:
    - FeedbackCheckpoint pydantic model (src/avideo/models/feedback.py)
    - WorkdirManager.write_feedback / read_feedback / clear_feedback helpers
    - storyboard._build_prompts with feedback param
    - scriptwriter._build_prompts with feedback param
    - slides_auto.resolve_theme with feedback param + consumed-once lifecycle
    - pipeline_ops.rerun_with_feedback dispatcher
    - Phase 2 Guion variation widget (text_area + radio)
    - Phase 3 Diapositivas variation widget (text_area + radio + disabled pexels stub)
  affects:
    - src/avideo/stages/storyboard.py
    - src/avideo/stages/scriptwriter.py
    - src/avideo/stages/slides_auto.py
    - src/avideo/ui/pipeline_ops.py
    - src/avideo/ui/pages/phase_2_guion.py
    - src/avideo/ui/pages/phase_3_slides.py
tech_stack:
  added: []
  patterns:
    - consumed-once lifecycle via workdir feedback.json
    - feedback block delimiter appended to user prompt at end
    - dispatcher pattern in pipeline_ops (rerun_with_feedback)
key_files:
  created:
    - src/avideo/models/feedback.py
    - tests/test_seed002_feedback.py
  modified:
    - src/avideo/utils/workdir.py
    - src/avideo/stages/storyboard.py
    - src/avideo/stages/scriptwriter.py
    - src/avideo/stages/slides_auto.py
    - src/avideo/ui/pipeline_ops.py
    - src/avideo/ui/pages/phase_2_guion.py
    - src/avideo/ui/pages/phase_3_slides.py
decisions:
  - feedback transport via workdir/feedback.json (not RunConfig) — ephemeral, no config pollution
  - consumed-once: stage clears its feedback entry after successful call_structured
  - empty-string feedback skips write_feedback to preserve rerun_scriptwriter backward compat
  - slides feedback bypasses theme idempotency by unlinking theme.yaml before resolve_theme
metrics:
  duration_min: ~20
  completed: 2026-05-31
  tasks_completed: 4
  tasks_total: 4
  files_created: 2
  files_modified: 7
---

# Quick Task 260531-npu: SEED-002 Steerable Variation — Summary

**One-liner:** Free-text feedback injection into storyboard/scriptwriter/slides prompts via workdir/feedback.json transport, with st.radio stage selector in Fase 2 and Fase 3 variation widgets.

## What Was Built

### Task 1: FeedbackCheckpoint model + WorkdirManager helpers (3ae493e)
- `src/avideo/models/feedback.py`: `FeedbackCheckpoint` pydantic model with `entries: dict[str, str] = {}`
- `src/avideo/utils/workdir.py`: three new methods after `read_checkpoint`:
  - `write_feedback(stage, text)` — creates/merges feedback.json
  - `read_feedback(stage) -> str | None` — returns None on missing file/key (never raises)
  - `clear_feedback(stage)` — removes stage key; silent no-op if absent
- All three use lazy imports of `FeedbackCheckpoint` to avoid circular imports

### Task 2: Stage prompt injection + consumed-once lifecycle (e9bab7e)
- `storyboard.py`: extracted `_build_prompts(bullets_input, context_text, title, duration, language, feedback=None)` from inline code in `run()`; appends `_FEEDBACK_BLOCK` when feedback is non-empty; `StoryboardStage.run()` reads + clears feedback
- `scriptwriter.py`: `_build_prompts` gains `feedback=None`; feedback block appended; `ScriptwriterStage.run()` reads + clears after first `call_structured` (before calibration retry)
- `slides_auto.py`: `resolve_theme` gains `feedback=None`; `SlidesAutoStage.run()` reads feedback, unlinks `theme.yaml` when feedback present (bypasses idempotency), passes feedback to `resolve_theme`, clears after resolution

### Task 3: pipeline_ops.rerun_with_feedback dispatcher (ec336ff)
- Added `rerun_with_feedback(workdir, config, target_stage, feedback)` handling `"storyboard"`, `"scriptwriter"`, `"slides"`; raises `ValueError` for unknown stages
- `rerun_scriptwriter` now delegates to `rerun_with_feedback(..., feedback="")` (preserved as public API)
- `rerun_slides` keeps its body unchanged (theme_path support needed for non-feedback callers)

### Task 4: UI variation widgets (32b300f)
- `phase_2_guion.py`: `st.radio` (Afinar tono / Cambiar nº de slides) + `st.text_area` + "Aplicar variación" button → `rerun_with_feedback` with `target_stage = "storyboard" or "scriptwriter"`
- `phase_3_slides.py`: `st.radio` (Estilo visual / Añadir imágenes disabled) + `st.text_area` + "Aplicar variación" button (disabled when pexels option) → `rerun_with_feedback('slides', ...)`

## Test Results

**Full suite (plan verification command):** 415 passed (ignoring 3 integration test files)
**Full suite including integration tests:** 446 passed

New tests added: 27 in `tests/test_seed002_feedback.py`:
- `TestWorkdirFeedback` (13): filesystem round-trip for all helpers
- `TestStoryboardFeedbackPrompt` (3): prompt injection present/absent
- `TestScriptwriterFeedbackPrompt` (2): prompt injection present/absent
- `TestSlidesAutoFeedbackPrompt` (2): resolve_theme user prompt
- `TestFeedbackConsumedOnce` (2): consumed-once lifecycle for scriptwriter + storyboard
- `TestRerunWithFeedback` (5): dispatcher routing x3 stages, ValueError, empty feedback

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Wrong import paths in tests**
- **Found during:** Task 2 — tests used `BulletsInput` from `avideo.utils.bullets` (not exported there) and `SlideTimingSpec` (non-existent name, actual class is `SlideTiming`)
- **Fix:** Corrected imports to `avideo.models.bullets.BulletsInput` and `avideo.models.timing.SlideTiming`; updated `SlideTiming` constructor arg `duration_s` → `seconds`
- **Files modified:** `tests/test_seed002_feedback.py`
- **Commit:** e9bab7e (part of Task 2 commit after fix)

**2. [Rule 1 - Bug] VisualType enum value casing**
- **Found during:** Task 2 — tests used `VisualType.TITLE` but enum member is `VisualType.title`
- **Fix:** Changed all occurrences to `VisualType.title`
- **Files modified:** `tests/test_seed002_feedback.py`
- **Commit:** e9bab7e

**3. [Rule 1 - Bug] RunConfig requires duration field**
- **Found during:** Tasks 2 and 3 — `RunConfig(bullets=...)` without `duration` raises ValidationError
- **Fix:** Added `duration=60` to all `RunConfig` instantiations in tests
- **Files modified:** `tests/test_seed002_feedback.py`
- **Commit:** e9bab7e and ec336ff

### Plan Inaccuracy Handled
The plan's `<interfaces>` block listed `storyboard._build_prompts(storyboard, timings, language)` — that was scriptwriter's signature. Storyboard had no `_build_prompts` (prompts built inline). Correctly handled per the `<critical_execution_notes>`: extracted `_build_prompts` with the actual parameters `(bullets_input, context_text, title, duration, language, feedback=None)` matching the inline code's structure.

## Backward Compatibility

- All 419 original tests continue to pass (verified via `uv run pytest tests/`)
- `feedback=None` in `_build_prompts` (all three stages) produces byte-identical prompts
- CLI pipeline never writes `feedback.json` — so `read_feedback` always returns `None` for CLI runs
- `rerun_scriptwriter` public API preserved; delegates to `rerun_with_feedback` with `feedback=""`
- `rerun_slides` public API and `theme_path` support preserved (body unchanged)

## Known Stubs

- "Añadir imágenes (próximamente — SEED-001)" option in Fase 3 radio is present but disabled. This is an intentional placeholder — the button is disabled and shows an info message. SEED-001 (Pexels image source) will implement this option.

## Threat Surface Scan

No new network endpoints, auth paths, or trust boundary crossings introduced. The feedback flow matches the plan's threat model:
- T-S002-01 (feedback.json in user-controlled workdir): accepted
- T-S002-02 (feedback appended as delimited block in user prompt, not system prompt): mitigated by `_FEEDBACK_BLOCK` template with explicit delimiters
- T-S002-03 (no system prompt override possible): accepted — only user turn modified

## Self-Check: PASSED

Files exist:
- src/avideo/models/feedback.py: FOUND
- src/avideo/utils/workdir.py (modified): FOUND
- tests/test_seed002_feedback.py: FOUND
- src/avideo/stages/storyboard.py (modified): FOUND
- src/avideo/stages/scriptwriter.py (modified): FOUND
- src/avideo/stages/slides_auto.py (modified): FOUND
- src/avideo/ui/pipeline_ops.py (modified): FOUND
- src/avideo/ui/pages/phase_2_guion.py (modified): FOUND
- src/avideo/ui/pages/phase_3_slides.py (modified): FOUND

Commits exist:
- 3ae493e: FOUND (Task 1)
- e9bab7e: FOUND (Task 2)
- ec336ff: FOUND (Task 3)
- 32b300f: FOUND (Task 4)
