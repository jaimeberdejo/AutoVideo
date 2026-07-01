---
phase: 09-ui-foundation
plan: "02"
subsystem: workdir + cli + deps
tags: [workdir, invalidate_downstream, cli, streamlit, tdd-green]
dependency_graph:
  requires:
    - 09-01 (RED test_workdir_invalidate.py contract)
  provides:
    - src/avideo/utils/workdir.py (STAGE_ORDER + invalidate_downstream)
    - src/avideo/cli.py (avideo studio subcommand)
    - pyproject.toml (streamlit>=1.58.0 dep + avideo-studio entry point)
  affects:
    - 09-03-PLAN.md (depends on WorkdirManager.invalidate_downstream being stable)
tech_stack:
  added:
    - streamlit>=1.58.0 (new project.dependencies entry)
  patterns:
    - TDD GREEN: 5 RED tests made green by adding STAGE_ORDER + invalidate_downstream
    - Lazy subprocess import inside studio() to avoid ImportError when streamlit not installed
    - Workdir path passed via env var (not shell-interpolated arg) — T-09-02-02 mitigation
    - STAGE_ORDER whitelist validates from_stage before any filesystem operation — T-09-02-01 mitigation
key_files:
  created: []
  modified:
    - src/avideo/utils/workdir.py
    - src/avideo/cli.py
    - pyproject.toml
decisions:
  - "STAGE_ORDER defined as module-level constant (not class attribute) so bridge/state modules can import it independently without instantiating WorkdirManager"
  - "invalidate_downstream only deletes markers strictly after boundary (boundary stage marker preserved) — user's boundary stage data is not lost"
  - "studio uses subprocess.run with list args and sys.executable (not shell=True) — avoids injection, inherits exact Python env"
  - "AVIDEO_STUDIO_WORKDIR env var preferred over CLI arg for workdir to studio — avoids Streamlit's own --arg parsing ambiguities"
  - "avideo-studio entry point added as alias to avideo.cli:app — typer handles routing; both avideo studio and avideo-studio subcommand work"
metrics:
  duration_seconds: 180
  completed_date: "2026-05-29"
  tasks_completed: 2
  files_changed: 3
---

# Phase 9 Plan 02: WorkdirManager.invalidate_downstream + avideo studio CLI Summary

**One-liner:** STAGE_ORDER constant + invalidate_downstream safety method added to WorkdirManager; avideo studio subcommand wires streamlit launch; streamlit>=1.58.0 added to deps; all 5 RED tests go GREEN; 339 total tests pass.

## What Was Built

### Task 1: STAGE_ORDER + invalidate_downstream (WorkdirManager)

Added two additive-only items to `src/avideo/utils/workdir.py`:

1. **STAGE_ORDER module-level constant** — ordered list of the 10 canonical pipeline stages.  Placed before the class definition so it can be imported independently by future bridge/state modules.

2. **invalidate_downstream(from_stage) method** — deletes done-markers for all stages strictly after the boundary stage. Returns list of deleted names. Raises `ValueError` for unknown stage names. All filesystem operations are scoped to `done_marker(stage)` which always resolves inside `workdir.root`.

No existing methods were modified.

### Task 2: avideo studio + pyproject.toml

1. **cli.py `studio` subcommand** — launches `streamlit run src/avideo/ui/app.py` via `subprocess.run` with a list of args (no shell interpolation). Accepts `--port` (default 8501) and `--workdir`. All imports inside the function body to avoid `ImportError` if streamlit is not installed.

2. **pyproject.toml** — added `streamlit>=1.58.0` to `[project.dependencies]` and `avideo-studio = "avideo.cli:app"` to `[project.scripts]`.

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add STAGE_ORDER + invalidate_downstream to WorkdirManager | ff95613 | src/avideo/utils/workdir.py |
| 2 | Add avideo studio CLI command + streamlit dep | 8f2e2a7 | src/avideo/cli.py, pyproject.toml |

## Test Results

| Suite | Before | After | Delta |
|-------|--------|-------|-------|
| test_workdir_invalidate.py | 5 FAILED (RED) | 5 PASSED | +5 GREEN |
| test_workdir.py | 8 PASSED | 8 PASSED | 0 |
| test_cli.py | 11 PASSED | 11 PASSED | 0 |
| Full suite (excluding bridge+ui_state) | 334 PASSED | 339 PASSED | +5 |

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

The plan's threat model is fully implemented:

| Threat ID | Mitigation Applied |
|-----------|-------------------|
| T-09-02-01 | from_stage validated against STAGE_ORDER whitelist before any filesystem op; done_marker() paths are always workdir.root relative |
| T-09-02-02 | subprocess.run with list args + sys.executable; workdir via env var not CLI arg |
| T-09-02-03 | Accepted — local single-user tool |

No new threat surface beyond the plan's model.

## Self-Check: PASSED

- [x] src/avideo/utils/workdir.py exists, contains `def invalidate_downstream` and `STAGE_ORDER`
- [x] src/avideo/cli.py exists, contains `def studio`
- [x] pyproject.toml contains `streamlit>=1.58.0` and `avideo-studio`
- [x] Commits ff95613 and 8f2e2a7 exist in git log
- [x] 339 tests pass (uv run python -m pytest); 0 regressions
- [x] `avideo --help` shows both `generate` and `studio` subcommands
