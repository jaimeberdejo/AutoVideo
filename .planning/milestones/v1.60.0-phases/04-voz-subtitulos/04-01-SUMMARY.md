---
phase: "04"
plan: "01"
subsystem: voice-elevenlabs
tags: [tts, elevenlabs, timestamps, pydantic, tdd, voice-stage]
dependency_graph:
  requires:
    - "03-02"  # SlidesAutoStage (script.json checkpoint present)
    - "02-03"  # ScriptwriterStage (produces script.json)
  provides:
    - UnifiedTimings model (D-11) — consumed by 04-02 (align) and 04-03 (subtitles)
    - VoiceStage(stage_name="voice") — replaces VoiceStub in PIPELINE_STAGES (04-03)
    - synthesize_slide integration with retry≤3 + strictly-increasing validation
  affects:
    - "04-02"  # align stage consumes UnifiedTimings
    - "04-03"  # subtitles stage consumes UnifiedTimings; also swaps PIPELINE_STAGES
tech_stack:
  added:
    - "elevenlabs>=2.49.0 (PyPI) — TTS with per-character timestamps"
  patterns:
    - "Lazy client singleton (mirrors anthropic.py D-13)"
    - "Module-scope mock point (mirrors storyboard.py pattern)"
    - "TDD: RED commit → GREEN commit per task"
    - "Per-character timestamp grouping into WordTiming list"
key_files:
  created:
    - src/avideo/models/timings.py
    - src/avideo/integrations/elevenlabs.py
    - src/avideo/stages/voice_elevenlabs.py
    - src/avideo/stages/voice.py
    - tests/test_elevenlabs.py
    - tests/test_voice_elevenlabs.py
    - tests/test_timings_model.py
    - tests/test_subtitles.py
    - tests/test_voice_record.py
    - tests/test_align.py
  modified:
    - pyproject.toml
    - src/avideo/models/__init__.py
    - src/avideo/models/config.py
    - tests/conftest.py
decisions:
  - "Timestamps stored as SECONDS relative to each slide clip (not global); subtitles.py accumulates offset = Σ durations"
  - "words populated by grouping per-character timestamps on whitespace splits (never empty when chars exist)"
  - "record extra declared in [project.optional-dependencies] WITHOUT torch pin (uv resolution conflict); torch==2.5.1 documented as comment"
  - "voice_elevenlabs.py stores audio_path as relative to workdir.root for checkpoint portability"
metrics:
  duration: "~9 minutes"
  completed: "2026-05-25"
  tasks_completed: 4
  files_changed: 14
---

# Phase 4 Plan 01: Voice ElevenLabs + UnifiedTimings Foundation Summary

ElevenLabs TTS integration with per-character timestamp validation, UnifiedTimings Pydantic model, VoiceElevenlabsStage, and VoiceStage dispatcher — with TDD for tasks 2/3/4 and Wave 0 test scaffolding for the full phase.

## What Was Built

### Task 1: Dependencies + Wave 0 scaffolding
- Added `elevenlabs>=2.49.0` to `[project.dependencies]`
- Declared `[project.optional-dependencies].record` with sounddevice/soundfile/whisperx
  - torch==2.5.1 pin documented as comment (cannot be in optional-deps due to uv resolution conflict with whisperx's torchaudio requirement on Python 3.12)
- Created 5 Wave 0 scaffold test files (skipped placeholders for 04-01..04-03)
- Added `fake_elevenlabs_response`, `fake_word_segments`, `voice_config` fixtures to conftest.py

### Task 2: UnifiedTimings model + RunConfig.whisperx_model (TDD)
- `models/timings.py`: `WordTiming`, `SlideTimings`, `UnifiedTimings` (D-11)
  - `start`/`end` documented as SECONDS relative to slide clip, NOT global
  - `words: list[WordTiming] = []` — populated by elevenlabs path, not empty
  - Round-trip JSON validated
- Re-exported from `models/__init__.py`
- `RunConfig.whisperx_model: str = "small"` added (D-05); configurable via `AVIDEO_WHISPERX_MODEL`

### Task 3: integrations/elevenlabs.py (TDD)
- Lazy `_get_client()` singleton (import-safe, mirrors `anthropic.py` pattern)
- `MODEL_ID = "eleven_multilingual_v2"`, `OUTPUT_FORMAT = "mp3_44100_128"` (D-01)
- `is_strictly_increasing()`: pure function, vacuously true for 0/1 elements
- `VoiceTimestampError`: domain error for degenerate timestamps (general safeguard, NOT a #607 fix)
- `synthesize_slide()`:
  - reads `character_start_times_seconds` / `character_end_times_seconds` (SECONDS, NOT the obsolete `_ms` fields)
  - retry loop ≤3 for timestamp validation ONLY (not for network errors — SDK handles those)
  - groups per-character timestamps into `WordTiming` list (never empty when characters exist)
  - `duration = ends[-1]` (last character end time)
  - `audio_path = str(out_path)` (caller constructs path via WorkdirManager)

### Task 4: stages/voice_elevenlabs.py + VoiceStage (TDD)
- `VoiceElevenlabsStage(stage_name="voice")`:
  - reads `script.json` via `workdir.read_checkpoint("script", ScriptOutput)`
  - calls `synthesize_slide` once per slide (module-scope import = mock point)
  - normalizes `audio_path` to relative path for checkpoint portability
  - returns `UnifiedTimings(source="elevenlabs", slides=[...])`
- `VoiceStage(stage_name="voice")`:
  - dispatches to `VoiceElevenlabsStage` when `config.voice == VoiceMode.elevenlabs`
  - lazy-imports `VoiceRecordStage` (04-02) for record path with clear `ImportError` message
  - `checkpoint_name` defaults to `"voice"` (D-12 contract preserved)

## Requirements Satisfied

| Req | Status | Implementation |
|-----|--------|---------------|
| VOICE-01 | Done | `synthesize_slide` + `VoiceElevenlabsStage.run` |
| VOICE-02 | Done | `is_strictly_increasing` + retry≤3 + `VoiceTimestampError` |
| ALIGN-02 | Prepared | Voice stage produces `UnifiedTimings` directly; align will be no-op |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] torch==2.5.1 pin in optional-dependencies caused uv resolution failure**
- **Found during:** Task 1
- **Issue:** `whisperx>=3.8.5` specifies `torchaudio>=2.8.0,<2.9` in its metadata for Python 3.12+, making `torch==2.5.1 + torchaudio==2.5.1` unsolvable in the same `[project.optional-dependencies]` resolution
- **Fix:** Removed `torch==2.5.1`/`torchaudio==2.5.1` from the declarative extra; documented them as a mandatory pre-install comment with exact versions and install command
- **Files modified:** `pyproject.toml`
- **Commit:** e68f2a0

**2. [Rule 2 - Missing critical functionality] WordTiming grouping from per-character timestamps**
- **Found during:** Task 3 implementation (critical guidance in plan prompt)
- **Issue:** Plan task 3 action said `words=[]` in `synthesize_slide`, but the plan's critical guidance (#2) states words MUST be populated on the elevenlabs path for subtitle generation
- **Fix:** Implemented `_group_chars_to_words()` helper that groups per-character timestamps by whitespace into `WordTiming` instances
- **Files modified:** `src/avideo/integrations/elevenlabs.py`
- **Commit:** 44978f8

**3. [Rule 2 - Missing critical functionality] audio_path stored as relative path**
- **Found during:** Task 4 implementation
- **Issue:** `synthesize_slide` returns `str(out_path)` (absolute), but absolute paths break checkpoint portability (workdir may be moved)
- **Fix:** `VoiceElevenlabsStage.run` normalizes audio_path to `out_path.relative_to(workdir.root)` before building SlideTimings
- **Files modified:** `src/avideo/stages/voice_elevenlabs.py`
- **Commit:** 74458c4

## Known Stubs

None — all new functionality is implemented. The Wave 0 scaffold files (`test_subtitles.py`, `test_voice_record.py`, `test_align.py`) are intentionally skipped placeholders for plans 04-02 and 04-03.

## Threat Flags

None — all security-relevant surfaces are accounted for in the plan's threat model (T-04-01 through T-04-04). No new network endpoints, auth paths, or schema changes at trust boundaries were introduced beyond what was planned.

## Self-Check: PASSED

All created files verified on disk. All 7 plan commits verified in git log.

| Check | Result |
|-------|--------|
| `src/avideo/models/timings.py` | FOUND |
| `src/avideo/integrations/elevenlabs.py` | FOUND |
| `src/avideo/stages/voice_elevenlabs.py` | FOUND |
| `src/avideo/stages/voice.py` | FOUND |
| Commit e68f2a0 (chore: deps + scaffolding) | FOUND |
| Commit 4684a43 (test: RED UnifiedTimings) | FOUND |
| Commit 98ead81 (feat: GREEN UnifiedTimings) | FOUND |
| Commit fd64a16 (test: RED elevenlabs.py) | FOUND |
| Commit 44978f8 (feat: GREEN elevenlabs.py) | FOUND |
| Commit f2db8e2 (test: RED voice stages) | FOUND |
| Commit 74458c4 (feat: GREEN voice stages) | FOUND |
| `uv run pytest -q` | 187 passed, 3 skipped |
