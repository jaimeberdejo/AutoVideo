---
phase: 08-backend-integrations
plan: "01"
subsystem: testing
tags: [pytest, tdd, openai, ffmpeg, audio-enhance, background-music, wave-0]

# Dependency graph
requires:
  - phase: 07-verify-slides
    provides: existing 303-test suite baseline
provides:
  - Wave 0 RED test scaffolds for VOZ-02 (OpenAI TTS stage), VOZ-03 (audio enhance), EXT-02/EXT-03 (music mix)
  - Mock seam definitions for avideo.integrations.openai._get_client
  - Mock seam definitions for avideo.stages.voice_openai.{synthesize,transcribe}_slide_openai
  - Mock seam definitions for avideo.utils.audio_enhance.run_ffmpeg
  - Pure builder test spec for build_music_mix_args()
affects:
  - 08-02 (RunConfig + VoiceMode changes — tests verify config fields)
  - 08-03 (OpenAI integration implementation — tests turn GREEN)
  - 08-04 (audio enhance utility — tests turn GREEN)
  - 08-05 (music mix builder + AssembleStage — tests turn GREEN)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wave 0 deferred import pattern: all avideo imports inside test bodies with # noqa: PLC0415"
    - "SimpleNamespace mock shape for openai SDK transcription word objects"
    - "Stage-level music test with _fake_ffmpeg_factory capturing all call_args"

key-files:
  created:
    - tests/test_voice_openai.py
    - tests/test_audio_enhance.py
    - tests/test_ffmpeg_music.py
  modified: []

key-decisions:
  - "Mock seam for openai is _get_client (lazy singleton), not the OpenAI class itself — mirrors elevenlabs pattern"
  - "Stage-level music tests count loudnorm calls by scanning call_args_log for 'loudnorm' substring — works regardless of implementation structure"
  - "test_nondestructive asserts out_path does NOT exist when run_ffmpeg is mocked — tests the non-write guarantee at the function-call level"

patterns-established:
  - "Wave 0 scaffold pattern: deferred imports + collect-only check confirms syntax before modules exist"
  - "_fake_ffmpeg_factory(stderr, write_output) returns both side_effect and call_args_log list — allows post-run assertion on all ffmpeg invocations"

requirements-completed:
  - VOZ-02
  - VOZ-03
  - EXT-02
  - EXT-03

# Metrics
duration: 5min
completed: 2026-05-29
---

# Phase 8 Plan 01: Backend Integrations Wave 0 Summary

**21 RED test scaffolds covering OpenAI TTS stage (VOZ-02), FFmpeg audio enhancement (VOZ-03), and background music mix builder (EXT-02/EXT-03) — all using deferred imports so they collect without error before implementation modules exist**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-29T13:34:46Z
- **Completed:** 2026-05-29T13:39:46Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Created `tests/test_voice_openai.py` (7 tests): covers per-slide synthesis dispatch, whisper-1 word-object mapping, 4096-char guard, lazy client import-safety, and module-scope mock point verification
- Created `tests/test_audio_enhance.py` (4 tests): covers afftdn+loudnorm filter chain, filter order, non-destructive write guarantee, and no-shell-true invariant
- Created `tests/test_ffmpeg_music.py` (10 tests): 7 pure builder tests for `build_music_mix_args()` (normalize=0, volume before amix, sidechaincompress, afade, list return, -c:v copy, +faststart) + 3 stage-level AssembleStage music integration tests
- All 21 new tests collect without SyntaxError via `--collect-only`
- Existing 303-test baseline remains intact (302 passed + 1 pre-existing failure in test_record_branch_raises_import_error_gracefully, unchanged)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create tests/test_voice_openai.py (VOZ-02 scaffold)** - `0b4a903` (test)
2. **Task 2: Create tests/test_audio_enhance.py and tests/test_ffmpeg_music.py (VOZ-03, EXT-02, EXT-03 scaffolds)** - `e4bdf73` (test)

**Plan metadata:** _(docs commit follows)_

## Files Created/Modified

- `tests/test_voice_openai.py` (212 lines) — Wave 0 scaffold for VoiceOpenAIStage; 7 tests covering VOZ-02 behaviors
- `tests/test_audio_enhance.py` (88 lines) — Wave 0 scaffold for enhance_audio() utility; 4 tests covering VOZ-03 behaviors
- `tests/test_ffmpeg_music.py` (363 lines) — Wave 0 scaffold for build_music_mix_args() + AssembleStage music path; 10 tests covering EXT-02/EXT-03 behaviors

## Decisions Made

- Mock seam for openai integration is `_get_client` (lazy singleton function), not `openai.OpenAI` — mirrors the elevenlabs `_get_client` pattern so implementation tests are symmetric
- Stage-level music tests use a `_fake_ffmpeg_factory` helper that captures all `run_ffmpeg` call args, allowing post-run assertions on how many loudnorm passes occurred without imposing rigid call-order requirements
- `test_nondestructive` asserts `not out_path.exists()` when run_ffmpeg is mocked — this cleanly tests the non-destructive guarantee: if the implementation accidentally wrote to out_path before calling run_ffmpeg, the test would catch it

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Pre-existing failure in `tests/test_voice_elevenlabs.py::TestVoiceStage::test_record_branch_raises_import_error_gracefully` — confirmed pre-existing (present in git stash baseline before any changes). Not caused by this plan.

## Known Stubs

None — this plan creates only test files; no production code stubs exist.

## Threat Flags

None — test files only; no new network endpoints, auth paths, or schema changes.

## Next Phase Readiness

- All 21 RED tests ready as gates for Wave 1–3 implementation plans
- Wave 1 (plan 08-02): RunConfig + VoiceMode changes → will make `test_lazy_client_not_instantiated_at_import` and config-related tests approach GREEN
- Wave 2 (plans 08-03, 08-04): openai integration + audio enhance utility → 11 tests turn GREEN
- Wave 3 (plan 08-05): music mix builder + AssembleStage → 10 tests turn GREEN

## Self-Check: PASSED

- `tests/test_voice_openai.py` exists and contains 7 tests
- `tests/test_audio_enhance.py` exists and contains 4 tests
- `tests/test_ffmpeg_music.py` exists and contains 10 tests
- Commits 0b4a903 and e4bdf73 exist in git log
- 21 tests collected via `--collect-only`
- 302 existing tests pass (pre-existing failure is not new)

---
*Phase: 08-backend-integrations*
*Completed: 2026-05-29*
