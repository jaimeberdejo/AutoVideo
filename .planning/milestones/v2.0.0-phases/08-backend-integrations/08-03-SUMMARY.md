---
phase: 08-backend-integrations
plan: "03"
subsystem: voice-pipeline
tags: [openai, tts, whisper, voice-stage, checkpoint-mixin, lazy-client]
dependency_graph:
  requires:
    - 08-01  # Wave 0 test scaffold (test_voice_openai.py)
    - 08-02  # VoiceMode.openai + RunConfig.openai_tts_model/voice fields
  provides:
    - integrations/openai.py  # synthesize_slide_openai + transcribe_slide_openai
    - stages/voice_openai.py  # VoiceOpenAIStage with stage_name="voice"
    - voice.py openai dispatch branch  # VoiceMode.openai routes to VoiceOpenAIStage
  affects:
    - stages/voice.py  # added openai dispatch branch
tech_stack:
  added: []  # openai>=2.38.0 was added in Plan 08-02
  patterns:
    - lazy-client-singleton  # mirrors integrations/elevenlabs.py _get_client()
    - checkpoint-mixin-stage  # CheckpointMixin with stage_name="voice"
    - module-scope-import-mock-seam  # synthesize/transcribe at module scope for patching
    - relative-audio-path-normalisation  # workdir-relative paths for checkpoint portability
key_files:
  created:
    - src/avideo/integrations/openai.py
    - src/avideo/stages/voice_openai.py
  modified:
    - src/avideo/stages/voice.py
decisions:
  - "transcribe_slide_openai passes Path directly to transcriptions.create (no open()) — enables mock seam to work without a real audio file on disk"
  - "whisper-1 hard-coded in transcribe_slide_openai — gpt-4o-transcribe lacks word timestamps (T-08-03-04)"
  - "4096-char ValueError raised before API call in synthesize_slide_openai — no silent truncation"
metrics:
  duration_seconds: 233
  completed_date: "2026-05-29"
  tasks_completed: 2
  files_created: 2
  files_modified: 1
---

# Phase 08 Plan 03: OpenAI Audio TTS Integration Summary

**One-liner:** OpenAI Audio TTS + whisper-1 STT round-trip voice provider with lazy client singleton, 4096-char guard, and word-level UnifiedTimings output.

## What Was Built

### Task 1: src/avideo/integrations/openai.py

New integration module following the exact `elevenlabs.py` lazy-client singleton pattern:

- `_get_client()`: lazy singleton, `OpenAI(max_retries=3)`, `_client` is `None` at import time — no `OPENAI_API_KEY` required at import or test collection
- `synthesize_slide_openai()`: keyword-only args, 4096-char guard (ValueError), `response.stream_to_file(str(out_path))`, returns `out_path`
- `transcribe_slide_openai()`: hard-coded `model="whisper-1"`, `response_format="verbose_json"`, `timestamp_granularities=["word"]`; maps `result.words` list → `WordTiming` list → `SlideTimings`; passes `Path` directly to SDK (no `open()` — enables mock seam)

**Key deviation from Research pattern:** The Research `CODE EXAMPLES` showed `with open(audio_path, "rb") as f:` before the SDK call. The test mock patches `_get_client` and passes `Path("dummy.mp3")` (non-existent file). Using `open()` causes `FileNotFoundError` before the mock intercepts the call. Fix: pass `audio_path` (Path) directly to `transcriptions.create(file=audio_path, ...)` — the OpenAI SDK accepts Path objects, and the mock intercepts the call before any file I/O. This is Rule 1 (auto-fix bug: test would fail even with correct logic).

### Task 2: src/avideo/stages/voice_openai.py + stages/voice.py

New stage and dispatcher branch:

- `VoiceOpenAIStage(CheckpointMixin)`: `stage_name = "voice"` (identical checkpoint contract to `VoiceElevenlabsStage`), `source="openai"` in returned `UnifiedTimings`
- `run()`: reads `"script"` checkpoint, calls `synthesize_slide_openai` then `transcribe_slide_openai` per slide, normalises `audio_path` to workdir-relative, returns `UnifiedTimings(source="openai")`
- Both integration functions imported at **module scope** (not inside `run()`) — this is the mock seam: `mocker.patch("avideo.stages.voice_openai.synthesize_slide_openai")`
- `voice.py`: lazy `VoiceOpenAIStage` import inside the `VoiceMode.openai` branch (before `raise NotImplementedError`) with `# noqa: PLC0415` — avoids loading `openai` package at module load when running other voice modes

## Verification

```
uv run python -c "import avideo.stages.voice_openai; import avideo.integrations.openai as m; assert m._client is None; print('import-safe OK')"
→ import-safe OK

uv run python -c "from avideo.stages.voice_openai import VoiceOpenAIStage; s=VoiceOpenAIStage(); assert s.stage_name == 'voice'; print('stage_name OK')"
→ stage_name OK

uv run pytest tests/test_voice_openai.py -v → 7 passed
uv run pytest tests/ -q (excl. Wave-0 stubs for 08-04/08-05) → 319 passed, 0 failures
```

## Test Results

| Scope | Before Plan | After Plan |
|-------|------------|------------|
| tests/test_voice_openai.py | 7 FAILED (Wave 0 RED) | 7 PASSED (GREEN) |
| Full suite (excl. other Wave 0) | 319 passing | 319 passing |
| Full suite (all 332 collected) | 319 passing, 13 other Wave 0 RED | 319 passing, 13 other Wave 0 RED |

No regressions. The 13 still-failing tests are Wave 0 scaffolds for Plans 08-04 (audio enhancement) and 08-05 (background music) — not implemented in this plan.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] transcribe_slide_openai: pass Path directly instead of open() to match test mock seam**
- **Found during:** Task 1 — test `test_transcribe_maps_word_objects` failing with `FileNotFoundError: dummy.mp3`
- **Issue:** Research `CODE EXAMPLES` showed `with open(audio_path, "rb") as f:` before calling the SDK. The test patches `_get_client` and passes `Path("dummy.mp3")` (non-existent file). The `open()` call happens before the mock intercepts the client call, causing `FileNotFoundError`.
- **Fix:** Changed `with open(audio_path, "rb") as f: ... create(file=f, ...)` to `create(file=audio_path, ...)` — the OpenAI SDK accepts `Path` objects as `file` argument; the mock intercepts the call without any file system access.
- **Files modified:** `src/avideo/integrations/openai.py`
- **Commit:** 9e28c79

## Known Stubs

None. Both integration functions (`synthesize_slide_openai`, `transcribe_slide_openai`) are fully implemented and call the real OpenAI SDK. The lazy client returns a real `OpenAI` instance when `OPENAI_API_KEY` is set.

## Threat Flags

None. All security surfaces are within the plan's threat model (T-08-03-01 through T-08-03-04). No new network endpoints, auth paths, or trust boundary crossings beyond what was designed.

## Self-Check: PASSED
