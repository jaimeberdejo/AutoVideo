---
phase: 12-voz-page
plan: "02"
subsystem: ui/pipeline_ops
tags: [voice, pipeline-ops, upload-guard, gate-check]
dependency_graph:
  requires: [12-01]
  provides: [rerun_voice, write_uploaded_audio, audio_gate_ready]
  affects: [src/avideo/ui/pipeline_ops.py]
tech_stack:
  added: []
  patterns:
    - lazy-import-stage (same pattern as rerun_scriptwriter / rerun_slides)
    - path-traversal-guard (mirrors write_uploaded_slide, T-12-02-01)
    - try-except gate (returns False on any exception, T-12-02-02)
key_files:
  created: []
  modified:
    - src/avideo/ui/pipeline_ops.py
decisions:
  - "Lazy import of VoiceStage inside rerun_voice body — identical pattern to ScriptwriterStage / SlidesDispatchStage; keeps module-level run_stage as the sole mock seam"
  - "audio_gate_ready catches bare Exception — FileNotFoundError, ValidationError, and any other corrupt-checkpoint error all safely return False without crashing the wizard"
metrics:
  duration_minutes: 3
  completed_date: "2026-05-29"
  tasks_completed: 1
  files_modified: 1
---

# Phase 12 Plan 02: Voice Pipeline Ops Helpers Summary

**One-liner:** Three voice-layer helpers — rerun_voice, write_uploaded_audio, audio_gate_ready — added to pipeline_ops.py, turning 11 RED tests GREEN (381 total passing).

## What Was Built

Extended `src/avideo/ui/pipeline_ops.py` with three functions under a new "Voice helpers (Phase 12)" section:

**`rerun_voice(workdir, config) -> None`**
Mirrors `rerun_scriptwriter` exactly: deletes `.voice.done` via `unlink(missing_ok=True)`, calls `invalidate_downstream("voice")`, then `run_stage(VoiceStage(), workdir, config)`. VoiceStage imported lazily inside the function body to avoid heavy-stage imports at module load time.

**`write_uploaded_audio(workdir, filename, data) -> Path`**
Identical path-traversal guard as `write_uploaded_slide` (raises `ValueError` on `/`, `\\`, or `..` prefix). Writes bytes to `workdir.root / "audio" / filename` after `mkdir(exist_ok=True)`. Returns the destination `Path`.

**`audio_gate_ready(workdir, n_slides) -> bool`**
Gate logic: (1) check each `slide_{i:02d}.mp3` or `.wav` exists; (2) `read_checkpoint("voice", UnifiedTimings)` wrapped in `try/except Exception` returning `False` on any failure; (3) `len(timings.slides) == n_slides`; (4) all `SlideTimings.words` non-empty. Returns `True` only when all four conditions pass.

## Test Results

| Suite | Before | After |
|-------|--------|-------|
| tests/test_voz_pipeline_ops.py | 11 FAILED (RED) | 11 PASSED (GREEN) |
| tests/test_pipeline_ops.py | 9 PASSED | 9 PASSED |
| Full suite | 370 PASSED | 381 PASSED |

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. Path-traversal mitigations for T-12-02-01 and T-12-02-02 (try/except gate) both implemented as specified in the threat register.

## Self-Check: PASSED

- `src/avideo/ui/pipeline_ops.py` modified: FOUND
- Commit `0986500` exists: FOUND
- 3 new functions present: CONFIRMED (grep -c == 3)
- No streamlit import: CONFIRMED (grep -c == 0)
- 381 tests GREEN, 0 failures: CONFIRMED
