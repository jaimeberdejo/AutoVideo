---
phase: 09-ui-foundation
plan: "01"
subsystem: tests
tags: [tdd, red-scaffold, workdir, bridge, ui-state]
dependency_graph:
  requires: []
  provides:
    - tests/test_workdir_invalidate.py (RED contract for WorkdirManager.invalidate_downstream)
    - tests/test_bridge.py (RED contract for PipelineBridge lifecycle)
    - tests/test_ui_state.py (RED contract for workdir_phase_from_done_markers)
  affects:
    - .planning/phases/09-ui-foundation/09-02-PLAN.md (must make test_workdir_invalidate GREEN)
    - .planning/phases/09-ui-foundation/09-03-PLAN.md (must make test_bridge + test_ui_state GREEN)
tech_stack:
  added: []
  patterns:
    - TDD RED scaffold (plain imports at module level cause ModuleNotFoundError/AttributeError until implementation exists)
    - model_construct for env-free RunConfig in tests
    - _reset_state() pattern for bridge module-level state isolation between tests
key_files:
  created:
    - tests/test_workdir_invalidate.py
    - tests/test_bridge.py
    - tests/test_ui_state.py
  modified: []
decisions:
  - "Used plain top-level imports (not pytest.importorskip) so test collection fails with ModuleNotFoundError — meaningful RED"
  - "Used model_construct to build RunConfig in bridge tests, avoiding pydantic_settings env/yaml loading (T-09-01-02 mitigation)"
  - "_reset_state() added to bridge imports list — test isolation for module-level _threads/_errors dicts"
  - "Deferred import (inside test function body) for WorkdirManager in invalidate tests — matches existing test_workdir.py pattern"
metrics:
  duration_seconds: 128
  completed_date: "2026-05-29"
  tasks_completed: 3
  files_changed: 3
---

# Phase 9 Plan 01: Wave-0 RED Test Scaffolds Summary

**One-liner:** Three RED TDD scaffold files define contracts for invalidate_downstream (workdir), PipelineBridge thread lifecycle, and wizard-phase reconstruction from done-markers.

## What Was Built

Created three new test files as Wave-0 RED scaffolds. No implementation modules were created or modified. All new tests fail in the expected way — they will become GREEN when Plans 02 and 03 land their implementations.

| File | Tests | Fail Mode | Target |
|------|-------|-----------|--------|
| `tests/test_workdir_invalidate.py` | 5 | `AttributeError: 'WorkdirManager' has no attribute 'invalidate_downstream'` | Plan 02 |
| `tests/test_bridge.py` | 5 | `ModuleNotFoundError: No module named 'avideo.ui'` | Plan 03 |
| `tests/test_ui_state.py` | 6 | `ModuleNotFoundError: No module named 'avideo.ui'` | Plan 03 |

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | RED tests for WorkdirManager.invalidate_downstream | 9bfe027 | tests/test_workdir_invalidate.py |
| 2 | RED tests for PipelineBridge thread lifecycle | 4334350 | tests/test_bridge.py |
| 3 | RED tests for ui.state workdir_phase_from_done_markers | ed669f2 | tests/test_ui_state.py |

## Contracts Defined

### WorkdirManager.invalidate_downstream (Plan 02 must satisfy)

```python
def invalidate_downstream(self, from_stage: str) -> list[str]:
    """Delete done-markers for all stages strictly after from_stage.
    Returns list of stage names whose markers were deleted.
    Raises ValueError for unknown stage names."""
```

Test cases cover: boundary deletion, first-stage (9 deleted), last-stage (no-op), return value of deleted names, unknown-stage ValueError.

### PipelineBridge (Plan 03 must satisfy)

```python
from avideo.ui.bridge import run_stage, stage_status, RunStatus, get_error, _reset_state
```

Test cases cover: thread launch transitions IDLE→RUNNING/DONE, idempotent when already-done, DONE status after completion, get_error=None on success, ERROR status + stored exception on failure.

### State module (Plan 03 must satisfy)

```python
from avideo.ui.state import workdir_phase_from_done_markers, PHASES, PHASE_COMPLETION_STAGE
```

Test cases cover: fresh workdir=phase1, phase1-complete=phase2, phase2-complete=phase3, all-complete=phase6 (clamped), PHASES has 6 entries with correct first/last, PHASE_COMPLETION_STAGE keys={1,2,3,4,5,6}.

## Deviations from Plan

None - plan executed exactly as written.

## Baseline Preserved

- **Existing suite (excluding new files):** 334 tests collected. New RED files do not affect the existing suite when excluded.
- **test_workdir_invalidate.py:** Collects cleanly (5 tests), all FAIL with AttributeError.
- **test_bridge.py:** Collection ERROR (ModuleNotFoundError) — 0 tests collected, as designed.
- **test_ui_state.py:** Collection ERROR (ModuleNotFoundError) — 0 tests collected, as designed.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. Test files only.

## Self-Check: PASSED

- [x] tests/test_workdir_invalidate.py exists
- [x] tests/test_bridge.py exists
- [x] tests/test_ui_state.py exists
- [x] Commits 9bfe027, 4334350, ed669f2 exist in git log
- [x] test_workdir_invalidate.py: 5 FAILED tests, all AttributeError
- [x] test_bridge.py: collection error (ModuleNotFoundError)
- [x] test_ui_state.py: collection error (ModuleNotFoundError)
