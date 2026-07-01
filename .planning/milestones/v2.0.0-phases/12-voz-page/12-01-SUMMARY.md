---
phase: 12-voz-page
plan: "01"
subsystem: testing
tags: [tdd, red-tests, pipeline_ops, voice, audio, timings, path-traversal]

# Dependency graph
requires:
  - phase: 11-guion-slides-pages
    provides: pipeline_ops.py pattern with deferred imports for RED test scaffold
  - phase: 08-backend-integrations
    provides: voice stages (VoiceStage), UnifiedTimings/SlideTimings/WordTiming models, audio_enhance
provides:
  - RED test scaffold tests/test_voz_pipeline_ops.py (11 tests for rerun_voice, write_uploaded_audio, audio_gate_ready)
affects:
  - 12-02 (GREEN — must implement rerun_voice, write_uploaded_audio, audio_gate_ready to pass these tests)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Deferred import pattern: all avideo.ui.pipeline_ops imports inside test bodies so file collects before helpers exist"
    - "audio_gate_ready gate contract: n_slides audio files + voice.json with non-empty words per slide"
    - "path-traversal guard contract: ValueError on '..', '/', '\\\\' in filename"

key-files:
  created:
    - tests/test_voz_pipeline_ops.py
  modified: []

key-decisions:
  - "Deferred imports inside test bodies (not module-level) allow 11 RED tests to collect and fail cleanly before Plan 02 adds helpers"
  - "audio_gate_ready gate checks both audio file existence AND timings word-level data validity (not just file existence)"
  - "voice.json path follows workdir checkpoint naming convention (wm.write_checkpoint('voice', timings))"

patterns-established:
  - "RED TDD wave 0: write tests that define helper contracts before implementation; use deferred imports to avoid ImportError at collection time"

requirements-completed: [VOZ-01]

# Metrics
duration: 1min
completed: 2026-05-29
---

# Phase 12 Plan 01: Voz Pipeline Ops RED Scaffold Summary

**11 RED tests defining contracts for rerun_voice, write_uploaded_audio, and audio_gate_ready — all using deferred imports, collected cleanly against 370 baseline**

## Performance

- **Duration:** 1 min
- **Started:** 2026-05-29T15:56:38Z
- **Completed:** 2026-05-29T15:58:04Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Created tests/test_voz_pipeline_ops.py with 11 RED tests across 3 test classes
- All tests collect without error (381 total) and fail with ImportError/AttributeError (RED) until Plan 02 adds helpers
- Path-traversal guard tested for "..", "/", and "\\" patterns (T-12-01-01)
- Audio gate tested for: missing audio, missing timings, empty words, all conditions met

## Task Commits

1. **Task 1: Write RED test scaffold for voice pipeline_ops helpers** - `9bcf7c7` (test)

**Plan metadata:** (to be committed below)

## Files Created/Modified
- `tests/test_voz_pipeline_ops.py` - 11 RED tests for rerun_voice, write_uploaded_audio, audio_gate_ready; all pipeline_ops imports deferred inside test bodies

## Decisions Made
- All `from avideo.ui.pipeline_ops import ...` statements are inside test bodies (not top-level) so the file collects cleanly before Plan 02 adds the helpers. This is the same pattern established in Phase 11 for test_pipeline_ops.py.
- `audio_gate_ready` gate contract: gate returns False if any of (audio files missing, voice.json absent, any SlideTimings.words empty); returns True only when all conditions met.
- `voice.json` is the checkpoint name used by `wm.write_checkpoint("voice", timings)` — consistent with WorkdirManager naming convention.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plan 02 (GREEN) can now implement rerun_voice, write_uploaded_audio, audio_gate_ready in ui/pipeline_ops.py to pass these 11 tests
- Baseline 370 tests remain unaffected; 381 total collected

---
*Phase: 12-voz-page*
*Completed: 2026-05-29*

## Self-Check: PASSED

- tests/test_voz_pipeline_ops.py: FOUND
- Commit 9bcf7c7: FOUND
- 381 tests collected (370 baseline + 11 new): VERIFIED
- Zero top-level pipeline_ops imports: VERIFIED
