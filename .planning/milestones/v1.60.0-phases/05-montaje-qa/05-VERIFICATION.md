---
phase: 05-montaje-qa
verified: 2026-05-26T00:00:00Z
status: passed
score: 7/7 must-haves verified
overrides_applied: 0
---

# Phase 5: Montaje + QA Verification Report

**Phase Goal:** El pipeline monta el vídeo final 1080p 16:9 sincronizando slides + audios con FFmpeg (duraciones reales medidas por ffprobe), aplica crossfade configurable y loudnorm, y emite un informe QA con desviación de duración y nivel LUFS
**Verified:** 2026-05-26
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | ASMB-01: ffprobe-driven durations — probe_duration called per audio file in AssembleStage | VERIFIED | `assemble.py:186` — `durations = [probe_duration(a) for a in audio_paths]`; comment explicitly states "NEVER use timings.json / WPM estimates — Pitfall 5" |
| 2 | ASMB-02: configurable crossfade — crossfade config field used in build_assemble_args | VERIFIED | `config.py:64` — `crossfade_seconds: float = Field(default=0.5, ge=0)`; `assemble.py:201` — `xfade=config.crossfade_seconds`; three dispatch paths (single/concat/xfade) in `build_filtergraph` |
| 3 | ASMB-03: 1080p 16:9 H.264 output in build_assemble_args | VERIFIED | `ffmpeg.py:111-112` — `scale=1920:1080`, `pad=1920:1080`, `setsar=1`, `format=yuv420p`; `ffmpeg.py:304-307` — `libx264`, `yuv420p`; `ffmpeg.py:310` — `-movflags +faststart` |
| 4 | QA-01: duration deviation — QAReport with target_seconds, actual_seconds, duration_deviation | VERIFIED | `assembly.py:25-27` — all three fields typed `float`; `qa.py:25-40` — `duration_deviation = actual_seconds - target_seconds`; `assemble.py:294-303` — wired with `probe_duration(output.mp4)` and `config.duration` |
| 5 | QA-02: two-pass loudnorm — loudnorm_pass1_args + loudnorm_pass2_args, linear=true, +faststart re-added | VERIFIED | `ffmpeg.py:342-412` — `loudnorm_pass1_args` uses `print_format=json`; `loudnorm_pass2_args` includes `linear=true`, `-c:v copy`, and `-movflags +faststart` (line 410); `parse_loudnorm_json` extracts last `{...}` block (line 434) |
| 6 | PIPELINE_STAGES last entry is AssembleStage(); AssembleStub class retained | VERIFIED | `stubs.py:296` — `AssembleStage()  # Phase 5: real (was AssembleStub)`; `stubs.py:261` — `class AssembleStub(CheckpointMixin)` retained; import at line 58 |
| 7 | Full test suite passes (274 tests) | VERIFIED | `uv run python -m pytest -q` → `274 passed, 5 warnings in 3.15s` |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/avideo/integrations/ffmpeg.py` | ffprobe duration, crossfade math, filtergraph builder, arg-list builder, run_ffmpeg | VERIFIED | 508 lines; all required functions present and substantive |
| `src/avideo/stages/assemble.py` | AssembleStage driving the ffmpeg builder, QA sub-step | VERIFIED | stage_name="assemble", checkpoint_name="assembly", full QA wiring |
| `src/avideo/stages/qa.py` | Pure QA logic: duration_deviation, build_qa_report, within_tolerance | VERIFIED | All three functions present and correct |
| `src/avideo/models/assembly.py` | QAReport with measured_lufs + normalized_lufs | VERIFIED | Both fields present as `Optional[float]` |
| `src/avideo/models/config.py` | crossfade_seconds + target_lufs fields | VERIFIED | Both fields at lines 64 and 69 |
| `src/avideo/stages/stubs.py` | PIPELINE_STAGES with AssembleStage(); AssembleStub class retained | VERIFIED | Line 296 has AssembleStage(); class AssembleStub at line 261 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `stages/assemble.py` | `integrations/ffmpeg.py` | `from avideo.integrations.ffmpeg import` | WIRED | Lines 54-61: imports `build_assemble_args`, `loudnorm_pass1_args`, `loudnorm_pass2_args`, `parse_loudnorm_json`, `probe_duration`, `run_ffmpeg` |
| `stages/assemble.py` | `stages/qa.py` | `from avideo.stages.qa import` | WIRED | Line 66: imports `build_qa_report`, `within_tolerance` |
| `stages/assemble.py` | `workdir/qa_report.json` | atomic write `qa_report.json.tmp` → rename | WIRED | Lines 305-308: atomic write pattern |
| `stages/stubs.py` | `stages/assemble.py` | `from avideo.stages.assemble import AssembleStage` | WIRED | Line 58; instantiated at line 296 in PIPELINE_STAGES |
| `build_assemble_args` | `crossfade_seconds` | `xfade=config.crossfade_seconds` | WIRED | `assemble.py:201` |
| `_run_qa` | `loudnorm_pass1_args` + `loudnorm_pass2_args` | called in sequence with `run_ffmpeg` | WIRED | `assemble.py:258-274` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `assemble.py` `durations` | `durations` list | `probe_duration(a)` for each audio path | Yes — ffprobe shell call on real files | FLOWING |
| `assemble.py` `qa_report` | `QAReport` | `build_qa_report(target, actual, measured_lufs, normalized_lufs)` | Yes — actual from `probe_duration(output.mp4)`, measured from `parse_loudnorm_json` | FLOWING |
| `assemble.py` `qa_report.json` | `QAReport.model_dump_json()` | written atomically at `assemble.py:307` | Yes — real report written | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite passes | `uv run python -m pytest -q` | `274 passed, 5 warnings in 3.15s` | PASS |
| No runtime `shell=True` in ffmpeg.py | `grep -n 'shell=True' src/avideo/integrations/ffmpeg.py` | All 5 hits are in comments/docstrings only | PASS |
| crossfade_seconds config field | `grep -n 'crossfade_seconds' src/avideo/models/config.py` | Found at line 64 | PASS |
| target_lufs config field | `grep -n 'target_lufs' src/avideo/models/config.py` | Found at line 69 | PASS |
| AssembleStage in PIPELINE_STAGES | `grep -n 'AssembleStage()' src/avideo/stages/stubs.py` | Found at line 296 | PASS |
| AssembleStub class retained | `grep -n 'class AssembleStub' src/avideo/stages/stubs.py` | Found at line 261 | PASS |
| linear=true in loudnorm pass-2 | `grep -n 'linear=true' src/avideo/integrations/ffmpeg.py` | Found at line 400 | PASS |
| +faststart re-added after -c:v copy | `grep -n '"-c:v", "copy"' src/avideo/integrations/ffmpeg.py` | Lines 406+410: `-c:v copy` followed by `-movflags +faststart` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| ASMB-01 | 05-01 | FFmpeg assembly using ffprobe real durations | SATISFIED | `assemble.py:186` — `[probe_duration(a) for a in audio_paths]` |
| ASMB-02 | 05-01 | Configurable crossfade between slides | SATISFIED | `config.py:64` crossfade_seconds field; `assemble.py:201` xfade=config.crossfade_seconds; three-path filtergraph dispatch |
| ASMB-03 | 05-01 | 1080p 16:9 H.264 output | SATISFIED | `ffmpeg.py:111-112` 1920x1080 normalization; `ffmpeg.py:304-307` libx264+yuv420p encode |
| QA-01 | 05-02 | Duration deviation report | SATISFIED | `assembly.py:25-27` target/actual/deviation fields; `qa.py:25-40` deviation = actual - target; wired in `assemble.py:293-303` |
| QA-02 | 05-02 | Two-pass loudnorm measure+apply with report | SATISFIED | `ffmpeg.py:342-412` pass-1/pass-2 builders with linear=true, print_format=json, +faststart; `assembly.py:29-30` measured_lufs+normalized_lufs; wired in `assemble.py:258-313` |

### Anti-Patterns Found

No blocking anti-patterns found.

| File | Pattern | Severity | Assessment |
|------|---------|----------|------------|
| `assemble.py:280` | `normalized_lufs = target_lufs` as fallback | Info | Intentional fallback when pass-2 stderr lacks parseable block; well-documented |
| `ffmpeg.py` | 5 occurrences of `shell=True` text | Info | All are in comments/docstrings only; zero runtime calls — confirmed by manual inspection |

### Human Verification Required

None. All observable truths are verifiable programmatically. Manual A/V playback to confirm crossfade smoothness and loudnorm audio quality is deferred to 05-VALIDATION Manual-Only (documented in the plan's verification section as an optional deferral).

### Gaps Summary

No gaps. All five requirement IDs (ASMB-01, ASMB-02, ASMB-03, QA-01, QA-02) are implemented, wired, and tested. The full test suite (274 tests) passes without regressions.

---

_Verified: 2026-05-26_
_Verifier: Claude (gsd-verifier)_
