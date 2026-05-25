---
phase: 05-montaje-qa
plan: "01"
subsystem: assembly
tags: [ffmpeg, assembly, crossfade, ffprobe, subprocess, idempotent]
dependency_graph:
  requires: [04-03]
  provides: [ASMB-01, ASMB-02, ASMB-03]
  affects: [05-02]
tech_stack:
  added: [integrations/ffmpeg.py]
  patterns: [arg-list subprocess, crossfade math, filtergraph builder, atomic-rename, ffprobe duration]
key_files:
  created:
    - tests/test_assemble.py
    - src/avideo/integrations/ffmpeg.py
    - src/avideo/stages/assemble.py
  modified:
    - tests/conftest.py
    - src/avideo/models/config.py
decisions:
  - "FFmpeg invoked via list[str] + shell=False (never shell=True) — T-05-01 enforcement"
  - "Segment durations from ffprobe format.duration, NOT timings.json WPM estimates — ASMB-01/D-02"
  - "Crossfade default 0.5s; XF=0 uses concat filter path (not xfade offset=0 anti-pattern) — D-03"
  - "output.mp4 written atomically via tmp→os.replace — D-10"
  - "PIPELINE_STAGES swap deferred to plan 05-02 (waits for QA wiring for single idempotence boundary)"
metrics:
  duration: "~15 minutes (respawn verification run)"
  completed: "2026-05-25"
  tasks_completed: 3
  tasks_total: 3
  files_created: 3
  files_modified: 2
---

# Phase 5 Plan 01: FFmpeg Assembly Foundation Summary

## One-liner

Real FFmpeg video assembly (1080p H.264 yuv420p) with configurable crossfade math, ffprobe-driven slide durations, atomic output, and idempotent AssembleStage satisfying ASMB-01/02/03.

## What Was Built

### Task 1: Wave-0 Test Scaffold (tests/test_assemble.py + conftest fixtures)

- `tests/test_assemble.py`: 18 tests covering all required selectors per 05-VALIDATION.md
  - `crossfade`: verifies `crossfade_offsets([3.0,4.0,2.5], 0.5) == [2.5, 6.0]` and 4-slide case `== [2.5, 6.0, 8.0]`; `expected_total` and `clamp_crossfade` with hard-cut signal
  - `probe_drives_duration`: mocked subprocess confirms `probe_duration` reads `format.duration` from ffprobe JSON; args contain `format=duration` and `-of json`; no WPM
  - `build_filtergraph`: substring assertions for xfade path (scale, setsar, format=yuv420p, xfade=, acrossfade=), concat path (concat=, no xfade=), and single-slide path (no xfade=, no concat=)
  - `build_assemble_args`: list[str] return, -movflags +faststart present, -filter_complex is one element, no shell=True element
  - `assemble_idempotent`: AssembleStage with existing output.mp4+assembly.json does NOT call run_ffmpeg
  - `smoke_dimensions` (guarded by shutil.which): real ffmpeg run asserting width==1920, height==1080, pix_fmt==yuv420p, abs(duration - expected_total) < 0.1
- `tests/conftest.py` additions:
  - `loudnorm_pass1_stderr` fixture: canned stderr with verified JSON block (field names input_i, input_tp, input_lra, input_thresh, output_i, target_offset) — consumed by plan 05-02
  - `tiny_av_assets(tmp_path)` fixture: Pillow tiny PNGs + ffmpeg lavfi sine WAVs via subprocess list[str]; skips cleanly when ffmpeg absent

**Commit:** `2d802a2` — test(05-01): add Wave-0 test scaffold for FFmpeg assembly

### Task 2: Config Fields + integrations/ffmpeg.py

**Config extension (src/avideo/models/config.py):**
- `crossfade_seconds: float = Field(default=0.5, ge=0)` — crossfade duration; 0 = hard cuts (D-03)
- `target_lufs: float = Field(default=-16.0)` — EBU R128 loudness target for two-pass loudnorm (plan 05-02)

**src/avideo/integrations/ffmpeg.py** — 506 lines, three sections:

PURE MATH (no I/O):
- `crossfade_offsets(durations, xfade)` — verified algorithm: merged=d[0]; for each d: offset=round(merged-xfade,6); merged+=d-xfade
- `expected_total(durations, xfade)` — sum(d) - max(0, N-1)*xfade
- `clamp_crossfade(xfade, prev_dur, next_dur)` — min(xfade, prev_dur, next_dur); <=0 signals hard cut (Pitfall 1)

PURE BUILDERS:
- `_input_normalize(label_in, label_out, fps)` — per-input chain: scale=1920:1080:force_original_aspect_ratio=decrease,pad,setsar=1,fps,format=yuv420p
- `build_filtergraph(durations, xfade, fps)` — three dispatch paths (single / concat for XF=0 / xfade-clamped for XF>0); per-boundary clamp prevents negative offsets (Pitfall 1)
- `build_assemble_args(...)` — full ffmpeg arg list with -loop 1, per-audio -i, -filter_complex (ONE element), -movflags +faststart, optional -shortest, optional libass subtitle burn-in
- `probe_duration_args(path)` — ffprobe args using format=duration + -of json
- `loudnorm_pass1_args`, `loudnorm_pass2_args`, `parse_loudnorm_json` — pre-built for plan 05-02 QA

SUBPROCESS PLUMBING (the only place that shells out):
- `run_ffmpeg(args)` — subprocess.run(args, capture_output=True, text=True) with implicit shell=False; raises RuntimeError with last 8 stderr lines on failure (D-04)
- `probe_duration(path)` — runs probe_duration_args, parses format.duration
- `ffmpeg_available()` — shutil.which check for both ffmpeg and ffprobe

**Commit:** `57b4f95` — feat(05-01): add FFmpeg integration module + config fields

### Task 3: stages/assemble.py (AssembleStage)

- `stage_name = "assemble"` (class attribute); `checkpoint_name` property returns `"assembly"`
- `run(workdir, config)` flow:
  1. Idempotence: if output.mp4 + assembly.json exist → read and return existing AssemblyOutput, no run_ffmpeg call (D-10)
  2. Read slides + voice checkpoints (SlidesOutput, VoiceOutput)
  3. Validate len(png_paths) == len(audio_paths) > 0 with clear RuntimeError (Assumption A1)
  4. Resolve relative paths against workdir.root
  5. `durations = [probe_duration(a) for a in audio_paths]` — REAL audio durations, never timings.json (ASMB-01/D-02)
  6. `subs_path = workdir.root / "subs" / "output.srt"` only if config.burn_subs (D-05/T-05-02)
  7. `build_assemble_args(...)` with output=output.mp4.tmp
  8. `run_ffmpeg(args)`
  9. `os.replace(tmp, output_mp4)` — atomic publish (D-10)
  10. Returns `AssemblyOutput(output_path=..., qa=None)` — QA wired in plan 05-02
- Does NOT call write_checkpoint/mark_done (orchestrator's job per StageProtocol)
- Does NOT touch PIPELINE_STAGES (deferred to plan 05-02 for single idempotence boundary)

**Commit:** `75e7c8c` — feat(05-01): implement AssembleStage (real FFmpeg assembly, idempotent, atomic)

## Test Results

```
uv run pytest tests/test_assemble.py -x -q
18 passed in 3.17s

uv run pytest -q
259 passed, 5 warnings in 7.05s
```

All 18 assemble tests pass including the real-ffmpeg smoke test (1920x1080 yuv420p, duration tolerance <0.1s). Full suite: 259 passed, 0 failed, 0 regressions.

## Verification Gates Passed

- `grep -c 'def test_' tests/test_assemble.py` → 18 (>= 6 required)
- `grep -q 'crossfade_offsets' tests/test_assemble.py` — FOUND
- `grep -q 'probe_drives_duration' tests/test_assemble.py` — FOUND
- `grep -q 'smoke_dimensions' tests/test_assemble.py` — FOUND
- `grep -q 'shutil.which' tests/test_assemble.py` — FOUND
- `grep -q 'loudnorm_pass1_stderr' tests/conftest.py` — FOUND
- `grep -q 'sine=frequency' tests/conftest.py` — FOUND
- `grep -q 'crossfade_seconds' src/avideo/models/config.py` — FOUND
- `grep -q 'target_lufs' src/avideo/models/config.py` — FOUND
- `grep -q 'def crossfade_offsets' src/avideo/integrations/ffmpeg.py` — FOUND
- `grep -q 'movflags' ... && grep -q 'faststart'` — FOUND
- `grep -q 'setsar=1'` — FOUND
- AST check for runtime shell=True in ffmpeg.py — PASS (zero occurrences)
- `grep -q 'stage_name.*=.*"assemble"'` — FOUND
- `grep -q 'os.replace'` — FOUND
- `grep -q 'output.mp4.tmp'` — FOUND

## Commits

| Task | Commit | Type | Description |
|------|--------|------|-------------|
| 1 (Wave-0 tests) | `2d802a2` | test | Add Wave-0 test scaffold for FFmpeg assembly |
| 2 (ffmpeg.py + config) | `57b4f95` | feat | Add FFmpeg integration module + config fields |
| 3 (AssembleStage) | `75e7c8c` | feat | Implement AssembleStage (real FFmpeg assembly, idempotent, atomic) |

## Deviations from Plan

None — plan executed exactly as written.

The implementation includes `loudnorm_pass1_args`, `loudnorm_pass2_args`, and `parse_loudnorm_json` in `integrations/ffmpeg.py` (not explicitly listed in Task 2's file list but part of the PURE BUILDERS section described in the action). These are pre-built helpers required by plan 05-02 QA, consistent with the plan's "sections" directive. The `conftest.py` `loudnorm_pass1_stderr` fixture was also added per plan spec (Wave-0 fixture for plan 05-02).

## Known Stubs

None — `AssembleStage.run()` fully implements the described behavior. `qa=None` in `AssemblyOutput` is intentionally deferred to plan 05-02 (documented in code and plan).

`PIPELINE_STAGES` still references `AssembleStub` (not `AssembleStage`) — this is explicitly intentional per plan: "This plan does NOT touch stubs.py / PIPELINE_STAGES — the swap happens in 05-02 after QA is wired."

## Threat Surface Scan

No new threat surface beyond what was documented in the plan's threat model:

| Flag | File | Description |
|------|------|-------------|
| threat_flag: subprocess | src/avideo/integrations/ffmpeg.py | All ffmpeg/ffprobe invocations use list[str] + implicit shell=False (T-05-01 mitigated) |
| threat_flag: path-construction | src/avideo/stages/assemble.py | Output paths are workdir.root / fixed-name only; no user component (T-05-02 mitigated) |

Both threats are fully mitigated as designed. AST verification confirms zero runtime `shell=True` calls.

## Self-Check: PASSED

- `tests/test_assemble.py` — FOUND
- `src/avideo/integrations/ffmpeg.py` — FOUND
- `src/avideo/stages/assemble.py` — FOUND
- Commit `2d802a2` — FOUND in git log
- Commit `57b4f95` — FOUND in git log
- Commit `75e7c8c` — FOUND in git log
- 259 tests pass — VERIFIED
