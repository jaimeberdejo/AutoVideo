---
phase: "08"
plan: "05"
subsystem: backend-integrations
tags:
  - ffmpeg
  - background-music
  - audio-mixing
  - EXT-02
  - EXT-03
dependency_graph:
  requires:
    - "08-01"  # RunConfig bg_music_path/bg_music_volume fields
    - "08-04"  # audio_enhance utility pattern
  provides:
    - build_music_mix_args() pure builder in integrations/ffmpeg.py
    - Step 8.5 music mix pass in AssembleStage
  affects:
    - AssembleStage.run() — adds conditional Step 8.5 block
    - AssembleStage._run_qa() — NOT modified; idempotence path short-circuits two-pass when music present
tech_stack:
  added:
    - build_music_mix_args(): pure FFmpeg arg-list builder for sidechaincompress+amix music overlay
  patterns:
    - amix=inputs=2:normalize=0 enforced (Pitfall 19: default normalize=1 drops narration -6 dB)
    - sidechaincompress voice-keyed ducking (threshold=0.02, ratio=10:1, attack=50ms, release=500ms)
    - afade in/out; fade_out_start from probe_duration(output_mp4) not config.duration (Pitfall 21)
    - single-pass loudnorm on final mix when music present (EXT-03, avoids double-normalization pumping)
    - qa_report.json pre-written to short-circuit _run_qa two-pass idempotence check
    - filter_complex as ONE list element (Pitfall 6: no shell interpretation)
    - -c:v copy + -movflags +faststart (Pitfall 2)
    - atomic music_tmp → os.replace pattern (music_tmp = output.music.tmp.mp4, .mp4 ext required)
key_files:
  created: []
  modified:
    - src/avideo/integrations/ffmpeg.py
    - src/avideo/stages/assemble.py
    - tests/test_ffmpeg_music.py
decisions:
  - "Single-pass loudnorm (not two-pass) when music is present: pre-write qa_report.json so _run_qa idempotence check fires immediately; avoids double-normalization pumping (EXT-03)"
  - "build_music_mix_args has no loudnorm in filter_complex: caller (Step 8.5) handles the single loudnorm pass after music mix"
  - "_run_qa() unchanged; Step 8.5 pre-writes qa_report.json to control which loudnorm path fires"
metrics:
  duration: "4 min"
  completed: "2026-05-29"
  tasks: 2
  files: 3
---

# Phase 8 Plan 05: Background Music Mixing Summary

Background music integration via `build_music_mix_args()` pure builder in `integrations/ffmpeg.py` and a new Step 8.5 in `AssembleStage.run()` that overlays music with sidechaincompress ducking, afade fades, and single-pass EBU R128 loudnorm on the final mixed output.

## What Was Built

### Task 1: build_music_mix_args() pure builder (ffmpeg.py)

Added `build_music_mix_args()` after `loudnorm_pass2_args()` in the PURE BUILDERS section of `src/avideo/integrations/ffmpeg.py`. The function:

- Returns `list[str]` (no I/O, no subprocess) — exact analog of `build_assemble_args()`
- `amix=inputs=2:normalize=0` enforced — `normalize=1` (default) drops both inputs -6 dB
- Explicit `volume=<music_volume>` on music track BEFORE amix for precise level control
- `sidechaincompress` with narration as sidechain key: music ducked under voice
- `afade=t=in` and `afade=t=out` for smooth entry/exit
- `fade_out_start` is a required parameter (caller computes from probe_duration — Pitfall 21)
- `-c:v copy` + `-movflags +faststart` (Pitfall 2: copy drops faststart)
- `filter_complex` is ONE list element (Pitfall 6: no shell quoting needed)
- Updated PURE BUILDERS section comment in module docstring

### Task 2: Step 8.5 music mix pass in AssembleStage (assemble.py)

Inserted Step 8.5 between Step 8 (atomic rename of assembled MP4) and Step 9 (_run_qa):

1. Check `config.bg_music_path` and verify file exists
2. Call `probe_duration(str(output_mp4))` for `actual_dur` (Pitfall 21: real duration)
3. Compute `fade_out_start = max(0.0, actual_dur - fade_out_s)`
4. Run `build_music_mix_args(...)` → `run_ffmpeg(music_args)` → atomic `os.replace(music_tmp, output_mp4)`
5. Single-pass loudnorm on mixed output: `loudnorm=I={target_lufs}:TP=-1.5:LRA=11` inline args
6. Pre-write `qa_report.json` via `build_qa_report()` + atomic write
7. `_run_qa()` called unchanged — idempotence check (`qa_json.exists()`) fires immediately, no additional ffmpeg calls

**EXT-03 compliance:** Exactly ONE loudnorm pass when music is present. The pre-written `qa_report.json` ensures `_run_qa`'s two-pass loudnorm is short-circuited without any modification to `_run_qa`'s internals.

**Without music:** Existing two-pass loudnorm via `_run_qa()` is fully preserved.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test factory call ordering + loudnorm detection in test_ffmpeg_music.py**
- **Found during:** Task 2 implementation
- **Issue 1:** `_fake_ffmpeg_factory` only wrote output files at call indices 0, 2, 3. With music mix at call index 1, `os.replace(music_tmp, output_mp4)` raised `FileNotFoundError` because `music_tmp` was never written.
- **Issue 2:** Loudnorm detection used `"loudnorm" in " ".join(args)` which matched ANY call whose args contained the pytest tmp_path directory name (e.g. `test_single_loudnorm_with_musi0/` — "loudnorm" in path). This caused ALL calls to match, making `len(loudnorm_calls) == 3` instead of the intended 2.
- **Fix:** Updated `_fake_ffmpeg_factory` to write at n=1 when `args[-1] != "-"` (music mix path vs. loudnorm pass-1 null output). Changed detection to `any("loudnorm=" in a for a in args)` which only matches actual loudnorm filter invocations.
- **Files modified:** `tests/test_ffmpeg_music.py`
- **Commit:** 38c539a

**2. [Rule 1 - Bug] Single-pass loudnorm instead of plan's assumed two-pass when music present**
- **Found during:** Task 2 implementation
- **Issue:** The plan stated "_run_qa() has zero changes" AND "loudnorm runs exactly once". These are contradictory: `_run_qa()` always runs two-pass loudnorm (pass1 + pass2 = 2 calls), making `test_single_loudnorm_with_music`'s `assert len(loudnorm_calls) == 1` impossible without a change.
- **Fix:** Step 8.5 runs a single-pass loudnorm inline (one ffmpeg call with `-af loudnorm=...`) and pre-writes `qa_report.json` so `_run_qa`'s idempotence check short-circuits the two-pass path. `_run_qa()`'s internal logic is truly unchanged.
- **Files modified:** `src/avideo/stages/assemble.py`
- **Commit:** 38c539a

## Test Results

| Test Class | Tests | Result |
|------------|-------|--------|
| TestBuildMusicMixArgs | 7 | GREEN (all pass) |
| TestAssembleMusicPath | 3 | GREEN (all pass) |
| Full suite (332 total) | 332 | GREEN (0 regressions) |

## Known Stubs

None — `build_music_mix_args()` and the music mix path in `AssembleStage` are fully functional. The `bg_music_path` field is optional (None by default) so the no-music path is unchanged.

## Threat Flags

No new security surface beyond what was planned. `filter_complex` is ONE list element (T-08-05-01). `bg_music_path` validated via Pydantic `Optional[Path]` before use (T-08-05-02). No `shell=True` anywhere (T-08-05-03). Single loudnorm on final mix prevents pumping (T-08-05-04).

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| src/avideo/integrations/ffmpeg.py | FOUND |
| src/avideo/stages/assemble.py | FOUND |
| tests/test_ffmpeg_music.py | FOUND |
| 08-05-SUMMARY.md | FOUND |
| commit 2bf59ca (build_music_mix_args) | FOUND |
| commit 38c539a (Step 8.5 assemble) | FOUND |
| build_music_mix_args importable | OK |
| AssembleStage Step 8.5 present | OK |
| 332 tests pass (0 regressions) | OK |
