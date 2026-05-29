---
phase: "08"
plan: "04"
subsystem: audio-utils
tags: [voz, ffmpeg, enhancement, utils, non-destructive]
dependency_graph:
  requires: ["08-01", "08-02"]
  provides: [enhance_audio]
  affects: [src/avideo/utils/audio_enhance.py]
tech_stack:
  added: []
  patterns: [afftdn+loudnorm filter chain, run_ffmpeg list[str] pattern]
key_files:
  created:
    - src/avideo/utils/audio_enhance.py
  modified: []
decisions:
  - "afftdn=nr=6:nf=-25 used instead of arnndn — no model file dependency, works offline"
  - "Single -af value with comma-joined filters (denoise then normalize) — order is fixed"
  - "Plain function, not a pipeline stage — no CheckpointMixin, no workdir param"
metrics:
  duration: "1 min"
  completed_date: "2026-05-29"
---

# Phase 8 Plan 04: Audio Enhancement Utility Summary

**One-liner:** `enhance_audio(in_path, out_path)` standalone FFmpeg wrapper applying `afftdn=nr=6:nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11` conservatively — non-destructive, no model files, shell=False enforced.

## What Was Built

Created `src/avideo/utils/audio_enhance.py` — a single standalone function (VOZ-03) that wraps FFmpeg to apply noise reduction + loudness normalization to user-uploaded audio files before final video assembly.

### Key Implementation Details

- `enhance_audio(in_path: Path, out_path: Path) -> None` — plain callable, NOT a pipeline stage
- Filter chain: `afftdn=nr=6:nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11` as a single `-af` value (comma-joined)
- Uses `run_ffmpeg(list[str])` from `avideo.integrations.ffmpeg` — shell=False enforced (D-04)
- Non-destructive: `in_path` is never modified; `out_path` receives the enhanced audio
- Module docstring explicitly warns: **WhisperX alignment MUST use `in_path` (original), not `out_path`**

## Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create src/avideo/utils/audio_enhance.py | 2f3a1ea | src/avideo/utils/audio_enhance.py |

## Test Results

- VOZ-03 tests (tests/test_audio_enhance.py): 4/4 PASSED
- Full suite: 327 passed (9 pre-existing failures in test_ffmpeg_music.py unrelated to this plan)
- Zero regressions introduced

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. The function is complete and correct. No placeholder data or deferred wiring.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced.
The function calls `run_ffmpeg(list[str])` which enforces shell=False (T-08-04-01 mitigated).
`arnndn` filter excluded — no model file dependency (T-08-04-03 mitigated).

## Self-Check: PASSED

- File exists: `src/avideo/utils/audio_enhance.py` — FOUND
- Commit exists: `2f3a1ea` — FOUND
- VOZ-03 tests: 4/4 PASSED
- Full suite: 327 passed, 0 regressions
