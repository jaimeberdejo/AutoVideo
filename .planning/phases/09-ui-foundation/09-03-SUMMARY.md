---
phase: 09-ui-foundation
plan: "03"
subsystem: ui-foundation
tags: [streamlit, bridge, session-state, threading, wizard]
dependency_graph:
  requires:
    - "09-01"  # RED test scaffolding (test_ui_state.py + test_bridge.py)
    - "09-02"  # WorkdirManager.invalidate_downstream
  provides:
    - avideo.ui.state (PHASES, PHASE_COMPLETION_STAGE, workdir_phase_from_done_markers, init_session_state, advance_phase)
    - avideo.ui.bridge (RunStatus, run_stage, stage_status, get_error, _reset_state)
  affects:
    - "09-04"  # app.py shell consumes state.py + bridge.py
    - "10+"    # All phase pages consume these two modules
tech_stack:
  added:
    - avideo.ui package (src/avideo/ui/)
  patterns:
    - Lazy st.* import (inside functions only) so state.py is unit-testable without Streamlit installed
    - Module-level thread/error dicts in bridge.py persist across Streamlit reruns (Python process boundary)
    - daemon=True threads die with the Streamlit process (no orphan threads)
    - Idempotent run_stage(): done-marker check before is_alive check (workdir is truth)
key_files:
  created:
    - src/avideo/ui/__init__.py
    - src/avideo/ui/state.py
    - src/avideo/ui/bridge.py
  modified: []
decisions:
  - "Lazy streamlit import inside init_session_state/advance_phase: st never imported at module level in state.py or bridge.py — unit tests run without streamlit installed"
  - "stage_status checks DONE first (done-marker), then ERROR, then is_alive: correct even when a thread writes done-marker and dies before the poll"
  - "run_stage checks is_done before is_alive: idempotent resume semantics — a resumed session with existing done-markers is always a no-op"
metrics:
  duration: "~3 minutes"
  completed_date: "2026-05-29T14:49:22Z"
  tasks_completed: 2
  files_created: 3
  tests_added: 11
  tests_baseline: 339
  tests_total: 350
---

# Phase 9 Plan 03: avideo.ui Package (state.py + bridge.py) Summary

**One-liner:** Streamlit-agnostic wizard state module (PHASES + workdir phase reconstruction) and PipelineBridge (RunStatus enum + daemon thread launcher) — 11 RED tests turned GREEN.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create ui/__init__.py and state.py | 82f94cd | src/avideo/ui/__init__.py, src/avideo/ui/state.py |
| 2 | Create bridge.py PipelineBridge | d7c7fb9 | src/avideo/ui/bridge.py |

## What Was Built

### `src/avideo/ui/__init__.py`
Empty package marker with docstring. Establishes the `avideo.ui` namespace.

### `src/avideo/ui/state.py`
Phase constants and workdir-based session reconstruction:
- `PHASES`: list of 6 `(int, str)` tuples for the wizard stepper
- `PHASE_COMPLETION_STAGE`: maps wizard phase → pipeline stage whose done-marker signals completion
- `workdir_phase_from_done_markers(workdir)`: scans PHASE_COMPLETION_STAGE in ascending order; returns first incomplete phase, or 6 if all complete
- `init_session_state()`: lazily imports streamlit; idempotently sets phase=1, workdir_path=None, run_config={}
- `advance_phase()`: lazily imports streamlit; increments phase up to 6, calls st.rerun()

No Streamlit import at module top level — confirmed by AST analysis.

### `src/avideo/ui/bridge.py`
Background-thread stage execution, Streamlit-agnostic:
- `RunStatus` enum: IDLE / RUNNING / DONE / ERROR
- `run_stage(stage, workdir, config)`: idempotent launcher — no-op if done-marker exists OR thread is_alive; otherwise spawns daemon thread that calls stage.run → write_checkpoint → mark_done; exceptions caught into `_errors`
- `stage_status(stage_name, workdir)`: priority order DONE > ERROR > RUNNING > IDLE
- `get_error(stage_name)`: returns stored Exception or None
- `_reset_state()`: test utility — clears `_threads` and `_errors`

No Streamlit import anywhere in this file.

## Test Results

```
tests/test_ui_state.py  6 passed
tests/test_bridge.py    5 passed
Total new tests:       11 passed
Total suite:          350 collected (339 baseline + 11 new)
```

## Deviations from Plan

None — plan executed exactly as written. The provided code sketches in the plan were used verbatim; no structural changes were needed.

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns introduced. bridge.py and state.py operate entirely on local filesystem (WorkdirManager) and in-process state.

## Self-Check: PASSED

- src/avideo/ui/__init__.py: EXISTS
- src/avideo/ui/state.py: EXISTS
- src/avideo/ui/bridge.py: EXISTS
- Commit 82f94cd: EXISTS (feat(09-03): add avideo.ui package init and state.py)
- Commit d7c7fb9: EXISTS (feat(09-03): add bridge.py PipelineBridge with RunStatus enum)
- No streamlit at top level: CONFIRMED (bridge.py: no grep match; state.py: AST-verified)
- 11 new tests GREEN: CONFIRMED
- Baseline 339 not regressed (350 now collected): CONFIRMED
