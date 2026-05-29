---
phase: "04"
plan: "03"
subsystem: subtitles
tags: [subtitles, srt, vtt, tdd, subtitle-format, pipeline-swap, phase4]
dependency_graph:
  requires:
    - "04-01"  # VoiceStage + UnifiedTimings (words populated from char timestamps)
    - "04-02"  # AlignStage (no-op passthrough for elevenlabs; whisperx for record)
  provides:
    - utils/subtitle_format.py — pure cue segmentation + SRT/VTT serialization
    - stages/subtitles.py — SubtitlesStage reads align checkpoint, accumulates global offset
    - models/subtitles.py — SubtitlesOutput (srt_path, vtt_path, cue_count)
    - PIPELINE_STAGES with VoiceStage/AlignStage/SubtitlesStage (Phase 4 complete)
  affects:
    - "05-01"  # AssembleStage reads subs/output.srt for burn-in (--burn-subs)
tech_stack:
  added: []
  patterns:
    - "TDD: RED commit → GREEN commit (Tasks 1+2)"
    - "Pure utility module (subtitle_format.py) for testable logic sans I/O"
    - "Phase-N stub swap pattern (mirrors 02-03 and 03-XX)"
    - "Global offset accumulation: per-slide-relative → global video timestamps"
key_files:
  created:
    - src/avideo/utils/subtitle_format.py
    - src/avideo/stages/subtitles.py
    - src/avideo/models/subtitles.py
  modified:
    - src/avideo/stages/stubs.py
    - src/avideo/models/__init__.py
    - tests/test_subtitles.py
    - tests/test_orchestrator.py
decisions:
  - "SubtitlesOutput defined in models/subtitles.py (not inline in stages/) to avoid circular imports and follow project architecture"
  - "Empty words fallback: single empty-text cue spanning slide duration (no crash, no lost text — because there is no text)"
  - "CPS constraint only triggers split when ADDING a word would push the cue over limit; a single word that individually exceeds CPS is kept as-is (no text loss)"
  - "synthesize_slide mocked in orchestrator end-to-end tests via _fake_synthesize_slide_factory()"
metrics:
  duration: "~7 minutes"
  completed: "2026-05-25"
  tasks_completed: 3
  files_changed: 7
---

# Phase 4 Plan 03: Subtitles + Pipeline Swap Summary

SRT/VTT subtitle generation with pure segmentation logic (42 chars/line, ≤2 lines, ≤5s/cue, ≤17 CPS), global offset accumulation across slides, and final Phase 4 swap of voice/align/subs stubs to real stages in PIPELINE_STAGES.

## What Was Built

### Task 1: utils/subtitle_format.py (TDD — pure logic)

- `Cue` dataclass: `start`, `end`, `text` (≤2 lines joined by `\n`)
- `fmt_ts(seconds, *, vtt)`: `HH:MM:SS,mmm` (SRT comma) or `HH:MM:SS.mmm` (VTT dot)
  - Guards against ms rounding to 1000 (carry propagation)
- `to_srt(cues)`: 1-based index, `HH:MM:SS,mmm --> HH:MM:SS,mmm`, blank line between cues
- `to_vtt(cues)`: `WEBVTT` header + blank line, dot timestamps, no index
- `segment_words(words, ...)`: groups `WordTiming` list into `Cue` list
  - Breaks cue when ADDING the next word would exceed: `max_chars_per_line * max_lines` (84 total), `max_cue_seconds` (5.0), or `max_cps` (17.0)
  - Empty input → empty list; single word never split (no text loss)
  - `_wrap_to_lines()` applies `textwrap.wrap` for clean line breaks at word boundaries

### Task 2: stages/subtitles.py + models/subtitles.py (TDD)

- `SubtitlesOutput(srt_path, vtt_path, cue_count)` — Pydantic model in `models/subtitles.py`
  - Re-exported from `models/__init__.py`
- `SubtitlesStage(stage_name="subs")`:
  - Reads `align` checkpoint (`UnifiedTimings`) — source-agnostic (D-11)
  - **Global offset accumulation**: `offset = 0.0`; per slide: shift each `WordTiming` by offset → segment → `offset += slide.duration`
  - Converts per-slide-relative timestamps to global video timestamps (documented in `timings.py`)
  - Writes `workdir/subs/output.srt` (UTF-8, comma) and `workdir/subs/output.vtt` (UTF-8, dot + WEBVTT)
  - Paths fixed: `workdir.root / "subs" / "output.srt"` / `"output.vtt"` (T-04-10: no traversal)
  - **SUB-02**: `burn_subs=True` acknowledged but NO ffmpeg invoked; burning is Phase 5
  - Fallback: slide with `words=[]` → single empty-text cue spanning slide duration (no crash)

### Task 3: PIPELINE_STAGES swap + test_orchestrator.py

- `stubs.py` imports: `VoiceStage`, `AlignStage`, `SubtitlesStage` from Phase-4 modules
- `PIPELINE_STAGES`: `VoiceStub()` → `VoiceStage()`, `AlignStub()` → `AlignStage()`, `SubsStub()` → `SubtitlesStage()`
- Stub classes `VoiceStub`/`AlignStub`/`SubsStub` **retained** (tests importing them directly)
- `test_orchestrator.py`:
  - Added `_fake_synthesize_slide_factory()` — produces valid `SlideTimings` with words; touches the audio file; no ElevenLabs API call
  - All `run_pipeline` tests now patch `avideo.stages.voice_elevenlabs.synthesize_slide`
  - `test_stub_run_returns_pydantic_basemodel`: writes checkpoint between each `stage.run()` call (mirrors real orchestrator loop)

## Requirements Satisfied

| Req | Status | Implementation |
|-----|--------|---------------|
| SUB-01 | Done | `subtitle_format.py` pure logic + `SubtitlesStage` always writes output.srt + output.vtt |
| SUB-02 | Done | `burn_subs` acknowledged; Phase 4 does NOT burn (no ffmpeg call); Phase 5 to consume |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] CPS test with single-word per cue scenario**
- **Found during:** Task 1 TDD RED/GREEN
- **Issue:** Test `test_break_on_cps_limit` used single words of 20 chars in 0.5s (40 CPS). A single word cannot be split without losing text — CPS enforcement on single-word cues is physically impossible.
- **Fix:** Updated test to use multi-word scenario (8 chars/word, adding 2nd word → 21.25 CPS > 17). Implementation correctly enforces CPS when ADDING a word would push over the limit.
- **Files modified:** `tests/test_subtitles.py`
- **Commit:** bc6f806 (inline with GREEN commit)

**2. [Rule 2 - Missing critical functionality] SubtitlesOutput in models/ not stages/**
- **Found during:** Task 2 implementation
- **Issue:** Initial draft had `SubtitlesOutput` defined inline in `stages/subtitles.py` and imported from there in `models/__init__.py` — architecturally inconsistent and could cause confusion.
- **Fix:** Created `models/subtitles.py` following the project's pattern (voice.py, slides.py, etc.); stages/subtitles.py imports from models.
- **Files modified:** `src/avideo/models/subtitles.py` (created), `src/avideo/stages/subtitles.py`, `src/avideo/models/__init__.py`
- **Commit:** bc6f806

**3. [Rule 2 - Missing critical functionality] Mock synthesize_slide in orchestrator tests**
- **Found during:** Task 3 (PIPELINE_STAGES swap)
- **Issue:** After replacing VoiceStub with VoiceStage in PIPELINE_STAGES, the orchestrator end-to-end tests (`test_orch_full_run_all_stages_done` etc.) called VoiceElevenlabsStage.run() which tried to read `script.json` checkpoint (not pre-written) and would call the real ElevenLabs API.
- **Fix:** Added `_fake_synthesize_slide_factory()` helper; patched `avideo.stages.voice_elevenlabs.synthesize_slide` in all run_pipeline tests; added `workdir.write_checkpoint()` between stage runs in `test_stub_run_returns_pydantic_basemodel`.
- **Files modified:** `tests/test_orchestrator.py`
- **Commit:** c788df0

## Known Stubs

None — all planned functionality is implemented. Phase 5 (AssembleStage) will consume `subs/output.srt` and `subs/output.vtt` for the optional burn-in.

## Threat Flags

No new threat surfaces beyond the plan's threat model:
- T-04-09 (subtitle text tampering): text from Phase 2 script, written as plain text (not executed)
- T-04-10 (path traversal): output paths fixed as `workdir.root/subs/output.{srt,vtt}` — no user input

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `src/avideo/utils/subtitle_format.py` | FOUND |
| `src/avideo/stages/subtitles.py` | FOUND |
| `src/avideo/models/subtitles.py` | FOUND |
| Commit 5318405 (test: RED) | FOUND |
| Commit bc6f806 (feat: GREEN) | FOUND |
| Commit c788df0 (feat: swap) | FOUND |
| `uv run pytest -q` | 241 passed |
| `grep -q 'stage_name.*subs' src/avideo/stages/subtitles.py` | FOUND |
| `grep -q 'VoiceStage()' src/avideo/stages/stubs.py` | FOUND |
| `grep -q 'WEBVTT' src/avideo/utils/subtitle_format.py` | FOUND |
