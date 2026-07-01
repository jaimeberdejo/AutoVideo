---
phase: 11-guion-slides-pages
plan: "01"
subsystem: ui-tests
tags: [tdd, red-scaffold, pipeline_ops, testing]

dependency_graph:
  requires: []
  provides: [tests/test_pipeline_ops.py]
  affects: [avideo.ui.pipeline_ops (Plan 02)]

tech_stack:
  added: []
  patterns:
    - Deferred-import pattern for RED test scaffolds (same as test_bullets_gen.py)
    - mocker.patch.object for WorkdirManager instance method spying
    - tmp_path fixture + real WorkdirManager for filesystem integration tests

key_files:
  created:
    - tests/test_pipeline_ops.py
  modified: []

decisions:
  - "All 9 avideo.ui.pipeline_ops imports are deferred inside each test body (not at module top) — file collects cleanly before pipeline_ops.py exists"
  - "WorkdirManager constructed with real tmp_path in upload tests — no mocking needed for filesystem writes"
  - "badge_for_verdict tests use SlideVerdict directly (pure function, no mock)"

metrics:
  duration: "~5 min"
  completed_date: "2026-05-29"
  tasks_completed: 1
  files_changed: 1
---

# Phase 11 Plan 01: RED Test Scaffold for pipeline_ops.py Summary

RED test scaffold defining the exact contracts for the four pipeline_ops glue functions: single-stage scriptwriter re-run, edited-script persistence with invalidate_downstream, safe file upload with path-traversal guard, and emoji badge mapping from VerificationReport verdicts.

## What Was Built

Created `tests/test_pipeline_ops.py` with 9 RED tests across 4 test classes:

| Class | Tests | Contract Tested |
|-------|-------|-----------------|
| `TestSingleStageRerun` | 2 | `rerun_scriptwriter()` calls `invalidate_downstream("scriptwriter")` then `run_stage` |
| `TestScriptPersistence` | 2 | `persist_edited_script()` writes checkpoint "script" + calls `invalidate_downstream("scriptwriter")` |
| `TestUploadToWorkdir` | 2 | `write_uploaded_slide()` writes to `slides_user/`; rejects `"../evil.png"` path traversal |
| `TestBadgeMapping` | 3 | `badge_for_verdict()` maps `ok→✅`, `warning→⚠️`, `fail→❌` |

## Verification Results

- `uv run pytest tests/test_pipeline_ops.py --co -q` → 9 tests collected (no syntax errors)
- `uv run pytest tests/test_pipeline_ops.py -x` → FAILS RED with `ModuleNotFoundError: No module named 'avideo.ui.pipeline_ops'`
- `uv run pytest --co -q | tail -3` → 370 collected (361 baseline + 9 new = no regressions)
- `grep -c "from avideo.ui.pipeline_ops import" tests/test_pipeline_ops.py` → 9 (all deferred)

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 — RED scaffold | d1a6606 | test(11-01): RED scaffold for pipeline_ops glue functions |

## Deviations from Plan

None — plan executed exactly as written.

## Threat Flags

None — test file only; no new network endpoints, auth paths, or schema changes.

## Self-Check: PASSED

- [x] `tests/test_pipeline_ops.py` exists and contains 9 test items
- [x] Commit `d1a6606` confirmed in git log
- [x] All `avideo.ui.pipeline_ops` imports deferred inside test bodies
- [x] Baseline 361 tests unaffected (370 total collected)
