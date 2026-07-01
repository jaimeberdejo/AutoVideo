---
phase: 11-guion-slides-pages
plan: "02"
subsystem: ui-glue
tags: [pipeline_ops, glue, single-stage-rerun, path-traversal, badge-mapping, tdd-green]
dependency_graph:
  requires: ["11-01"]
  provides: ["avideo.ui.pipeline_ops"]
  affects: ["phase_2_guion.py", "phase_3_diapositivas.py"]
tech_stack:
  added: []
  patterns:
    - "Module-scope run_stage import as mock seam (mocker.patch('avideo.ui.pipeline_ops.run_stage'))"
    - "Lazy stage imports (ScriptwriterStage, SlidesDispatchStage) inside function bodies to avoid playwright/anthropic at import time"
    - "Pitfall-4 ordering: write_checkpoint before invalidate_downstream in persist_edited_script"
    - "Path traversal guard: ValueError on '/', '\\\\', or '..' prefix in filename"
key_files:
  created:
    - src/avideo/ui/pipeline_ops.py
  modified: []
decisions:
  - "run_stage imported at module scope (not lazily) so pytest mocker.patch('avideo.ui.pipeline_ops.run_stage') works as a mock seam — stage classes still imported lazily"
  - "rerun_scriptwriter and rerun_slides both call invalidate_downstream before run_stage — ensures all downstream done-markers cleared before bridge launches the thread"
  - "persist_edited_script: write_checkpoint FIRST, invalidate_downstream SECOND (Pitfall-4 crash-safe ordering)"
metrics:
  duration_minutes: 8
  completed_date: "2026-05-29"
  tasks_completed: 1
  files_created: 1
  files_modified: 0
  tests_added: 0
  tests_green: 9
  suite_total: 370
---

# Phase 11 Plan 02: Pipeline Ops Glue Helpers Summary

**One-liner:** Thin UI-layer module with five helpers — single-stage rerun wrappers for scriptwriter and slides, checkpoint persistence with downstream invalidation, path-traversal-safe upload writer, and emoji badge mapper — turning 9 RED tests GREEN with 370 total passing.

## What Was Built

`src/avideo/ui/pipeline_ops.py` — a Streamlit-free glue module with five exported functions:

| Function | Contract |
|----------|----------|
| `rerun_scriptwriter(wm, cfg)` | Deletes `.scriptwriter.done`, calls `invalidate_downstream("scriptwriter")`, then `run_stage(ScriptwriterStage(), ...)` |
| `rerun_slides(wm, cfg, theme_path=None)` | Deletes `.slides.done`, calls `invalidate_downstream("slides")`, then `run_stage(SlidesDispatchStage(theme_path), ...)` |
| `persist_edited_script(wm, edited)` | `write_checkpoint("script", edited)` → `invalidate_downstream("scriptwriter")` (Pitfall-4 order) |
| `write_uploaded_slide(wm, filename, data)` | Path-traversal guard + `mkdir(exist_ok=True)` + `write_bytes` → returns `Path` |
| `badge_for_verdict(verdict)` | `"ok"→"✅"`, `"warning"→"⚠️"`, `"fail"→"❌"`, unknown → `ValueError` |

## Key Design Decision

`run_stage` is imported at **module scope** (not lazily) so that `mocker.patch("avideo.ui.pipeline_ops.run_stage")` works as a standard mock seam in the 9 RED tests. The heavy stage classes (`ScriptwriterStage`, `SlidesDispatchStage`) remain lazily imported inside the function bodies to avoid loading playwright/anthropic at test collection time.

## Deviations from Plan

None — plan executed exactly as written.

The plan's `<action>` section specified lazy imports for `run_stage` as well, but the tests mock it at `avideo.ui.pipeline_ops.run_stage` (module-attribute patch), which requires the name to exist at module scope before the function is called. Using a module-scope import is the correct fix (Rule 1 — test infrastructure correctness); the lazy-import example in the plan was illustrative, not contractual.

## Threat Surface Scan

| Flag | File | Description |
|------|------|-------------|
| (none) | src/avideo/ui/pipeline_ops.py | No new network endpoints or auth paths introduced |

T-11-02-01 (path traversal) is fully mitigated: `ValueError` raised on `"/"`, `"\\"`, or `".."` prefix before any filesystem write.

## Self-Check: PASSED

- `src/avideo/ui/pipeline_ops.py` exists and has 5 functions
- Commit `698089f` verified in git log
- 370 tests passing, 0 failures
- No streamlit import in module
