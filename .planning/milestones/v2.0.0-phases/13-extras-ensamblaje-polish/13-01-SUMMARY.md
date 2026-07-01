---
phase: 13-extras-ensamblaje-polish
plan: "01"
subsystem: test-scaffold
tags: [tdd, red-phase, pipeline-ops, extras]
dependency_graph:
  requires: []
  provides: [test-contract-write_uploaded_music, test-contract-extras_to_run_config, test-contract-read_qa_report]
  affects: [avideo.ui.pipeline_ops]
tech_stack:
  added: []
  patterns: [deferred-import-red-phase, path-traversal-guard-test]
key_files:
  created:
    - tests/test_extras_pipeline_ops.py
  modified: []
decisions:
  - Deferred imports inside test bodies (not module-level) so file collects before helpers exist — mirrors Phase 11/12 pattern
  - QAReport imported at module level (already exists); only the 3 new pipeline_ops functions deferred
  - Path-traversal test covers ".." prefix and "/" in filename (mirrors T-12-02-01; see T-13-01-01)
metrics:
  duration_seconds: 93
  completed_date: "2026-05-29"
  tasks_completed: 1
  tasks_total: 1
---

# Phase 13 Plan 01: RED Test Scaffold for Extras Pipeline Ops

**One-liner:** 9 RED tests locking contracts for write_uploaded_music / extras_to_run_config / read_qa_report before any implementation.

## Summary

Created `tests/test_extras_pipeline_ops.py` with 9 RED test functions across 3 test classes. All tests use deferred imports (functions not yet in pipeline_ops.py) so the file collects cleanly with 0 errors while failing at runtime with ImportError — the canonical RED phase state.

## Tasks

| Task | Name | Status | Commit | Files |
|------|------|--------|--------|-------|
| 1 | Write RED test scaffold | Done | 85958ec | tests/test_extras_pipeline_ops.py |

## Verification Results

- `python -m pytest tests/test_extras_pipeline_ops.py --collect-only -q` → 9 tests collected, 0 errors
- `python -m pytest --collect-only -q` → 390 tests collected, 0 errors
- All 9 new tests FAIL with ImportError at runtime (correct RED behavior)
- Existing 200 passing tests remain unchanged

## Deviations from Plan

None — plan executed exactly as written. Tests collect as 9 (not 0) and fail with ImportError as expected.

## Known Stubs

None — this is a test-only scaffold plan. No implementation stubs introduced.

## Threat Flags

None — no new network endpoints, auth paths, or schema changes.

## Self-Check: PASSED

- tests/test_extras_pipeline_ops.py: FOUND
- commit 85958ec: FOUND
