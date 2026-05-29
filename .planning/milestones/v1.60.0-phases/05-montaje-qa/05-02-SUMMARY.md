---
phase: 05-montaje-qa
plan: 02
subsystem: video
tags: [ffmpeg, loudnorm, qa, pipeline, assemble]

requires:
  - phase: 05-01
    provides: AssembleStage base (ffprobe durations, crossfade, 1080p encode), run_ffmpeg/probe_duration helpers, loudnorm_pass1_stderr conftest fixture

provides:
  - Two-pass EBU R128 loudnorm sub-step wired inside AssembleStage (QA-02)
  - QAReport with target/actual/deviation + measured_lufs + normalized_lufs (QA-01)
  - qa_report.json written atomically to workdir
  - Rich QA table rendered to terminal (D-08)
  - AssembleStage() in PIPELINE_STAGES (stub swap complete — Phase 5 done)

affects: [phase-06, phase-07, orchestrator-tests]

tech-stack:
  added: []
  patterns:
    - QA as AssembleStage sub-step (single assembly checkpoint, one idempotence boundary)
    - loudnorm two-pass (measure stderr → apply with linear=true -c:v copy +faststart)
    - Orchestrator test pattern for real stages with ffmpeg — _fake_run_ffmpeg_factory

key-files:
  created:
    - src/avideo/stages/qa.py
    - workdir/qa_report.json (runtime artifact)
  modified:
    - src/avideo/stages/assemble.py
    - src/avideo/stages/stubs.py
    - src/avideo/models/assembly.py
    - src/avideo/integrations/ffmpeg.py
    - tests/test_assemble.py
    - tests/test_orchestrator.py

key-decisions:
  - "QA wired as sub-step of AssembleStage (not a separate stage) — single assembly checkpoint, one idempotence boundary (05-RESEARCH OQ1)"
  - "loudnorm pass-2 uses -c:v copy (video already burned in 05-01 encode); +faststart re-added per Pitfall 2"
  - "parse_loudnorm_json extracts LAST {...} block from noisy stderr (Pitfall 4)"
  - "AssembleStub class retained in stubs.py for test back-compat (same pattern as phase 4)"

patterns-established:
  - "Orchestrator tests: patch avideo.stages.assemble.run_ffmpeg + probe_duration with _fake_run_ffmpeg_factory() (call-index-based: 0=encode, 1=pass-1, 2=pass-2)"
  - "Atomic tmp→rename for all QA side artifacts (qa_report.json.tmp, output.mp4.norm.tmp)"

requirements-completed: [QA-01, QA-02]

duration: ~90min (split across two sessions due to session limit)
completed: 2026-05-26
---

# Phase 05-02: QA Layer + PIPELINE_STAGES Swap Summary

**Two-pass EBU R128 loudnorm sub-step + QAReport wired into AssembleStage; PIPELINE_STAGES fully real with AssembleStage() completing Phase 5**

## Performance

- **Duration:** ~90 min (split across two sessions — session limit hit mid-execution)
- **Completed:** 2026-05-26
- **Tasks:** 2/2
- **Files modified:** 6

## Accomplishments

- `stages/qa.py` — pure-logic module: `duration_deviation`, `within_tolerance`, `build_qa_report`
- `integrations/ffmpeg.py` — `loudnorm_pass1_args`, `loudnorm_pass2_args`, `parse_loudnorm_json` (last-block extraction, float-cast, Pitfall 4)
- `models/assembly.py` — `QAReport` extended with `measured_lufs` + `normalized_lufs`
- `stages/assemble.py` — QA sub-step: pass-1 measure → pass-2 apply (linear=true, -c:v copy, +faststart) → `build_qa_report` → atomic `qa_report.json` → Rich table
- `stages/stubs.py` — `AssembleStage()` in `PIPELINE_STAGES` (stub class retained); Phase 5 pipeline fully wired
- `tests/test_orchestrator.py` — `_fake_run_ffmpeg_factory` helper patches all 7 orchestrator pipeline tests so no real ffmpeg runs

## Task Commits

1. **Task 1: QAReport + qa.py + loudnorm parse/builders (RED)** — `06c5ceb` + `deb714c`
2. **Task 2: QA wiring + PIPELINE_STAGES swap (RED)** — `60b3472`
3. **Task 2: QA sub-step in AssembleStage (GREEN)** — `25e9147`
4. **Task 2: PIPELINE_STAGES swap (GREEN)** — `c927404`
5. **Task 2: orchestrator test patches (fix)** — `1a2cc85`

## Files Created/Modified

- `src/avideo/stages/qa.py` — pure QA logic (deviation, build_qa_report, within_tolerance)
- `src/avideo/stages/assemble.py` — QA sub-step: two-pass loudnorm + QAReport + Rich table
- `src/avideo/stages/stubs.py` — AssembleStage() in PIPELINE_STAGES
- `src/avideo/models/assembly.py` — QAReport.measured_lufs + normalized_lufs
- `src/avideo/integrations/ffmpeg.py` — loudnorm arg builders + parse_loudnorm_json
- `tests/test_assemble.py` — end-to-end QA test + PIPELINE_STAGES test + UnifiedTimings fixture fix
- `tests/test_orchestrator.py` — ffmpeg mock helpers for all orchestrator pipeline tests

## Decisions Made

- QA as AssembleStage sub-step (not separate stage): single `assembly` checkpoint, one idempotence boundary per 05-RESEARCH OQ1
- loudnorm pass-2 `-c:v copy` (video already re-encoded in 05-01); `-movflags +faststart` re-added after copy (Pitfall 2)
- `parse_loudnorm_json` extracts LAST `{...}` block from noisy stderr (Pitfall 4)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Session limit hit mid-execution — uncommitted changes recovered**
- **Found during:** Task 2 execution
- **Issue:** Agent hit session limit with stubs.py + assemble.py changes uncommitted in worktree
- **Fix:** Recovered uncommitted changes from main working tree, committed atomically per task
- **Verification:** All 51 tests pass, all acceptance criteria met
- **Committed in:** `25e9147`, `c927404`

---

**Total deviations:** 1 auto-fixed (1 operational/blocking)
**Impact on plan:** No scope change — all plan tasks delivered as specified.

## Issues Encountered

- Session limit hit during worktree execution; partial work (stubs.py, assemble.py) was left uncommitted on main working tree — recovered and committed in correct atomic order

## Next Phase Readiness

- PIPELINE_STAGES fully wired end-to-end: all 10 stages real
- Phase 5 requirements ASMB-01/02/03 + QA-01/02 all satisfied
- 51 tests pass, 0 regressions
- Phase 6 (Slides Hybrid/Manual + Verificador) can proceed: needs CONTEXT.md + discuss-phase

---
*Phase: 05-montaje-qa*
*Completed: 2026-05-26*
