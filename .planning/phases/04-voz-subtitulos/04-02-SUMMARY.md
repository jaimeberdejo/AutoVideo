---
phase: "04"
plan: "02"
subsystem: voice-record-align
tags: [whisperx, record-mode, forced-alignment, lazy-import, tdd, align-stage]
dependency_graph:
  requires:
    - "04-01"  # UnifiedTimings model, VoiceStage dispatcher, script checkpoint
  provides:
    - integrations/whisperx.py — align_wav (lazy import D-06) + word_segments_to_words
    - stages/voice_record.py — VoiceRecordStage (VOICE-03)
    - stages/align.py — AlignStage (ALIGN-01 / ALIGN-02)
  affects:
    - "04-03"  # subtitles stage consumes UnifiedTimings from both backends
    - "07-01"  # Docker must add torch==2.5.1 + portaudio before whisperx
tech_stack:
  added:
    - "whisperx (record extra) — forced-alignment via CPU int8; lazy import"
    - "sounddevice (record extra) — mic recording; lazy import"
    - "soundfile (record extra) — WAV read/write + duration measurement; lazy import"
  patterns:
    - "Lazy import of heavy deps (whisperx/sounddevice/soundfile) inside function bodies (D-06)"
    - "Module-scope mock point: from avideo.integrations.whisperx import align_wav (mirrors storyboard.py)"
    - "TDD: RED commit → GREEN commit per task"
    - "Non-zero duration guarantee via last word.end fallback (Warning 1)"
key_files:
  created:
    - src/avideo/integrations/whisperx.py
    - src/avideo/stages/voice_record.py
    - src/avideo/stages/align.py
    - tests/test_whisperx_integration.py
    - tests/test_voice_record.py (replaced scaffold)
    - tests/test_align.py (replaced scaffold)
decisions:
  - "align_wav imported at module scope in align.py so tests patch avideo.stages.align.align_wav (not integration layer)"
  - "word_segments_to_words() is pure helper in integrations/whisperx.py reused by align.py"
  - "VoiceRecordStage writes script_segments.txt to workdir/audio/ for user narration"
  - "Duration set from soundfile.info (real WAV duration) in voice_record; updated to last word.end in align"
  - "sounddevice/soundfile globals set to None at module scope so tests can patch via module path"
metrics:
  duration: "~7 minutes"
  completed: "2026-05-25"
  tasks_completed: 3
  files_changed: 6
---

# Phase 4 Plan 02: Voice Record + Alignment (WhisperX) Summary

WhisperX integration with lazy import (CPU int8), VoiceRecordStage (script export + WAV autodetect/record), and AlignStage (record→whisperx word-level timestamps; elevenlabs→no-op passthrough) — all with TDD and mocked heavy deps.

## What Was Built

### Task 1: integrations/whisperx.py (TDD)

- `align_wav(wav_path, language, model_size)`:
  - `import whisperx` inside the function body (D-06); NEVER at module top level
  - CPU `compute_type="int8"` — portable/CI; no CUDA required
  - Runs: `load_model` → `load_audio` → `transcribe` → `load_align_model` → `align`
  - Returns `aligned["word_segments"]` (list of dicts with `word`/`start`/`end` in seconds)
  - `ImportError` with clear message pointing to `uv sync --extra record`
- `word_segments_to_words(segments)` — pure conversion helper: list[dict] → list[WordTiming]
  - Skips segments without `start`/`end` (WhisperX edge case with very short words)
- Module import is **safe without whisperx installed** — import guard verified in tests
- Torch 2.5.1 pin + `vad_method="silero"` fallback documented in module docstring (Pitfall 2)
- No diarization (no HF token required)

### Task 2: stages/voice_record.py (TDD)

- `VoiceRecordStage(stage_name="voice")` — D-12 checkpoint contract
- Script export: `_export_script_segments()` writes `workdir/audio/script_segments.txt`
  with labeled blocks `=== Slide N ===\n{narration}\n` for user narration
- `_resolve_audio(workdir_root, slide_index, narration)`:
  - Path: `workdir.root / "audio" / f"slide_{i:02d}.wav"` — safe, no traversal (T-04-05)
  - If WAV exists → autodetect (D-04b); sounddevice NOT invoked
  - If WAV absent → records with lazy-loaded `sounddevice.rec` + `soundfile.write`
- `_measure_duration(wav_path)` — soundfile.info for real WAV duration (Warning 1 guard)
- Returns `UnifiedTimings(source="record", words=[])` — AlignStage fills words
- `audio_path` normalized to relative for checkpoint portability

### Task 3: stages/align.py (TDD)

- `AlignStage(stage_name="align")` — D-12 checkpoint contract
- **ALIGN-01 (record)**:
  - Reads voice checkpoint → for each slide: `align_wav(wav_path, language, model_size)`
  - `word_segments_to_words(segs)` → populates `SlideTimings.words`
  - Duration updated to `last_word.end` (Warning 1: non-zero when words exist)
  - Returns `UnifiedTimings(source="whisperx")`
- **ALIGN-02 (elevenlabs)**:
  - No-op idempotent passthrough: reads voice checkpoint, returns it unchanged
  - `align_wav` is NOT called — whisperx/torch never loaded on this path
- `align_wav` imported at **module scope** (`from avideo.integrations.whisperx import align_wav`)
  so tests patch `avideo.stages.align.align_wav` (storyboard mock-point pattern)
- The heavy `import whisperx` stays inside `integrations/whisperx.align_wav` (D-06 preserved)

## Requirements Satisfied

| Req | Status | Implementation |
|-----|--------|---------------|
| VOICE-03 | Done | VoiceRecordStage: script export + autodetect WAV + sounddevice recording (mocked in CI) |
| ALIGN-01 | Done | AlignStage record path: align_wav per slide → UnifiedTimings(source=whisperx) with words |
| ALIGN-02 | Done | AlignStage elevenlabs path: no-op idempotent, align_wav NOT called |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] sounddevice/soundfile module-scope aliases**
- **Found during:** Task 2 implementation
- **Issue:** The plan says to import sounddevice/soundfile lazily inside functions (D-06/Pitfall-5). To allow tests to patch `avideo.stages.voice_record.sounddevice` (the expected mock target), the names need to exist at module scope — but set to `None` initially.
- **Fix:** Added `sounddevice = None` and `soundfile = None` at module scope as lazy-load aliases resolved by `_load_sounddevice()` / `_load_soundfile()` helpers. This satisfies both D-06 (no import at module level) and the mock point contract.
- **Files modified:** `src/avideo/stages/voice_record.py`
- **Commit:** 4f04866

**2. [Rule 1 - Bug] numpy dependency in test_voice_record.py**
- **Found during:** Task 2 RED test run
- **Issue:** RED test used `np.zeros()` for fake audio data, but numpy is not installed in the project environment (record extra uses sounddevice's own numpy, not project numpy).
- **Fix:** Replaced `np.zeros(...)` with a plain Python list; removed `import numpy as np` from test imports.
- **Files modified:** `tests/test_voice_record.py`
- **Commit:** a82cbe3

## Known Stubs

- `VoiceRecordStage` returns `words=[]` in `UnifiedTimings` — this is **intentional by design** (plan spec), not a stub. AlignStage (Task 3, same plan) fills the words. Both stages are implemented and tested.

## Threat Surface Scan

No new threat surfaces beyond what was in the plan's threat model:
- T-04-05 (path traversal): WAV path constructed only from `workdir.root / "audio" / f"slide_{i:02d}.wav"` — no user-controlled filename.
- T-04-06 (whisperx pickle): lazy import + torch 2.5.1 pin documented; no diarization.
- T-04-07 (sounddevice CI): lazy import + autodetect fallback + mock in tests.
- T-04-08 (info disclosure): no API keys on record path; whisperx local.

## Self-Check: PASSED

All created files verified on disk. All 6 plan commits verified in git log.

| Check | Result |
|-------|--------|
| `src/avideo/integrations/whisperx.py` | FOUND |
| `src/avideo/stages/voice_record.py` | FOUND |
| `src/avideo/stages/align.py` | FOUND |
| `tests/test_whisperx_integration.py` | FOUND |
| `tests/test_voice_record.py` (replaced scaffold) | FOUND |
| `tests/test_align.py` (replaced scaffold) | FOUND |
| Commit 8a92d12 (test: RED whisperx integration) | FOUND |
| Commit 5ad03b9 (feat: GREEN whisperx.py) | FOUND |
| Commit a82cbe3 (test: RED voice_record) | FOUND |
| Commit 4f04866 (feat: GREEN voice_record.py) | FOUND |
| Commit f81a8e3 (test: RED align tests) | FOUND |
| Commit 77e9c89 (feat: GREEN align.py) | FOUND |
| `uv run pytest -q` | 208 passed, 1 skipped |
| `uv run pytest tests/test_align.py -k elevenlabs` | 2 passed |
| `uv run python -c "import avideo.integrations.whisperx"` | OK import-safe |
| whisperx NOT imported on elevenlabs path | VERIFIED |
