---
phase: 13-extras-ensamblaje-polish
plan: "04"
subsystem: ui-packaging
tags: [dockerfile, smoke-tests, studio-ui, packaging, polish]
dependency_graph:
  requires: [13-01, 13-02, 13-03]
  provides: [Dockerfile EXPOSE 8501, page smoke tests, headless studio documentation]
  affects: [Dockerfile, tests/test_page_smoke.py]
tech_stack:
  added: []
  patterns: [smoke-test via importlib, dockerfile EXPOSE + comment docs]
key_files:
  created:
    - tests/test_page_smoke.py
  modified:
    - Dockerfile
decisions:
  - "Auto-approved human-verify checkpoint (unattended run); live browser launch deferred to manual verification"
  - "Smoke tests use importlib.import_module instead of direct import to avoid module caching issues across parametrize runs"
  - "app.py excluded from import smoke due to st.set_page_config() at module scope (requires running Streamlit server)"
metrics:
  duration: "~3 min"
  completed_date: "2026-05-29T17:56:41Z"
  tasks_completed: 1
  tasks_total: 1
  checkpoint_auto_approved: 1
---

# Phase 13 Plan 04: Polish — Dockerfile + Page Smoke Tests + Final Checkpoint Summary

**One-liner:** Dockerfile gets EXPOSE 8501 + headless studio launch docs; 7 page-import smoke tests confirm all 6 wizard pages loadable; 397 tests green.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Dockerfile EXPOSE 8501 + headless docs + page smoke tests | ad35802 | Dockerfile, tests/test_page_smoke.py |

## Checkpoint

**Task 2 (checkpoint:human-verify)** — Auto-approved (UNATTENDED run). See "Deferred Manual Verification" below.

## Verification Results

- `grep -c "EXPOSE 8501" Dockerfile` → 1 (PASS)
- `grep -c "server.headless" Dockerfile` → 1 (PASS)
- `grep -c "avideo-studio" pyproject.toml` → 1 (PASS — entry point confirmed)
- `uv run python -m pytest tests/test_page_smoke.py -v` → 7 passed (PASS)
- `uv run python -m pytest -q` → 397 passed, 0 failed (PASS)

## Deferred Manual Verification

The following steps require a human to confirm (deferred from the auto-approved checkpoint):

1. **avideo studio launch:** `uv run avideo studio` should open browser at http://localhost:8501 showing the 6-phase wizard.
2. **Fase 5 widgets visible:** burn_subs toggle, music upload, volume slider, crossfade slider, "Aprobar extras" button.
3. **Fase 6 button visible:** "Montar vídeo" button present.
4. **Docker build (optional):** `docker build -t avideo-test .` should complete without errors.

## Deviations from Plan

None — plan executed exactly as written. The smoke tests correctly exclude app.py (st.set_page_config at module scope raises outside a running server, which is documented in the test file).

## Threat Surface Scan

No new network endpoints or auth paths introduced. Dockerfile EXPOSE 8501 was the planned change. T-13-04-01 through T-13-04-04 mitigations applied as designed (keys via -e flag, default CMD is --help, studio requires explicit user action).

## Self-Check: PASSED

- Dockerfile exists and contains EXPOSE 8501: FOUND
- tests/test_page_smoke.py created: FOUND
- Commit ad35802 exists: FOUND
- 397 tests pass: VERIFIED
