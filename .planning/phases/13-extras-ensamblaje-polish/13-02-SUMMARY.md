---
phase: 13-extras-ensamblaje-polish
plan: "02"
subsystem: ui-extras
tags:
  - pipeline_ops
  - phase_5_extras
  - extras
  - bg_music
  - burn_subs
  - crossfade
  - EXT-01
dependency_graph:
  requires:
    - 13-01  # RED test scaffold
  provides:
    - EXT-01  # Fase 5 Extras wizard page fully implemented
  affects:
    - src/avideo/ui/pipeline_ops.py
    - src/avideo/ui/pages/phase_5_extras.py
tech_stack:
  added: []
  patterns:
    - "Extras helpers follow write_uploaded_audio pattern (path-traversal guard, workdir subdir)"
    - "extras_to_run_config is a pure function — no I/O, no Streamlit, safe to unit-test"
    - "read_qa_report wraps all I/O in broad except Exception — never propagates parse errors"
    - "phase_5_extras.render() is a config-only page with immediate approve gate (no long stage)"
key_files:
  created: []
  modified:
    - src/avideo/ui/pipeline_ops.py
    - src/avideo/ui/pages/phase_5_extras.py
decisions:
  - "bg_music_path stored as str in session_state (Path not JSON-serializable in session_state); resolved back to Path before passing to extras_to_run_config"
  - "Approving extras with no extras selected is valid — gate is immediate config gate not quality gate"
metrics:
  duration: "3 minutes"
  completed_date: "2026-05-29T17:50:28Z"
  tasks_completed: 2
  files_modified: 2
---

# Phase 13 Plan 02: Extras Pipeline Ops + Fase 5 Extras Page Summary

**One-liner:** Three pipeline_ops helpers (write_uploaded_music, extras_to_run_config, read_qa_report) + real Fase 5 Extras wizard page implementing EXT-01 with burn_subs toggle, music upload/preview/volume, and crossfade slider.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Extend pipeline_ops.py with three Extras helpers | 3778fc8 | src/avideo/ui/pipeline_ops.py |
| 2 | Replace phase_5_extras.py with real Fase 5 Extras page | 66e667f | src/avideo/ui/pages/phase_5_extras.py |

## What Was Built

### Task 1 — pipeline_ops.py extensions

Three functions appended in a new "Extras helpers (Phase 13)" section:

**`write_uploaded_music(workdir, filename, data) -> Path`**
- Path-traversal guard: raises `ValueError` on `/`, `\\`, or `..` prefix (T-13-02-01)
- Writes to `workdir/music/<filename>` (creates dir if needed)
- Pattern mirrors `write_uploaded_audio` from Phase 12

**`extras_to_run_config(burn_subs, bg_music_path, bg_music_volume, bg_music_fade_out_s, crossfade_seconds) -> dict`**
- Pure function — no I/O, no Streamlit
- Returns dict with the five RunConfig field names as keys
- Safe to merge directly into `session_state["run_config"]`

**`read_qa_report(workdir) -> QAReport | None`**
- Reads `workdir/qa_report.json`
- Returns `QAReport` on success; `None` on any exception (FileNotFoundError, ValidationError, JSONDecodeError) — T-13-02-02
- Lazy import of QAReport inside function body

Also added `QAReport` to `TYPE_CHECKING` imports block.

### Task 2 — phase_5_extras.py (real Fase 5 page)

Replaced 49-line placeholder with 142-line real wizard page implementing EXT-01:

- **Subtítulos section:** `st.toggle` for `burn_subs` with informational `st.info` when enabled
- **Música de fondo section:** `st.file_uploader` (mp3/wav) → `write_uploaded_music` → `st.audio` preview + volume slider (0.0–1.0, step 0.01, default 0.12) + fade-out slider (0–10s, step 0.5, default 3.0s)
- **Transiciones section:** crossfade slider (0–3s, step 0.1, default 0.5s)
- **Session state merge:** all 5 values go through `extras_to_run_config` → dict update → `st.session_state["run_config"]`
- **Approve gate:** immediate config-only gate with `st.session_state["extras_approved"]` persistence; approving with no extras is valid

## Test Results

| Test File | Before | After | Delta |
|-----------|--------|-------|-------|
| test_extras_pipeline_ops.py | 0/9 (RED) | 9/9 (GREEN) | +9 |
| Full suite (non-broken tests) | 200 passed | 209 passed | +9 |

The 138 failures in the full suite are pre-existing (verified by stash check: 147 failed before changes). No previously-passing tests were broken.

## Deviations from Plan

None — plan executed exactly as written.

## Threat Model Compliance

| Threat ID | Status |
|-----------|--------|
| T-13-02-01 | Mitigated — `ValueError` on `/`, `\\`, `..` in `write_uploaded_music` |
| T-13-02-02 | Mitigated — `except Exception: return None` in `read_qa_report` |
| T-13-02-03 | Accepted — `bg_music_path` stored as str in session_state (in-process, single-user) |
| T-13-02-04 | Mitigated — filename sanitised by path-traversal guard before filesystem write |

## Known Stubs

None — all widgets wired to real data; approve gate persists config to session_state.

## Threat Flags

None — no new network endpoints, auth paths, or trust-boundary schema changes introduced.

## Self-Check: PASSED
