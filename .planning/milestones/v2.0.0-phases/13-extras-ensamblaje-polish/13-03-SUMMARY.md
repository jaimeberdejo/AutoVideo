---
phase: 13-extras-ensamblaje-polish
plan: "03"
subsystem: ui-wizard
tags: [streamlit, assembly, bridge, fragment-polling, video-player, qa-report]
dependency_graph:
  requires:
    - 13-02 (pipeline_ops.read_qa_report)
    - phases/12 (PipelineBridge, fragment-polling pattern)
  provides:
    - Fase 6 Ensamblaje page (ASM-01, ASM-02)
  affects:
    - src/avideo/ui/pages/phase_6_ensamble.py
tech_stack:
  added: []
  patterns:
    - "@st.fragment(run_every='2s') for non-blocking FFmpeg progress polling"
    - "Lazy imports inside render() body for all bridge/stage references"
key_files:
  created: []
  modified:
    - src/avideo/ui/pages/phase_6_ensamble.py
decisions:
  - "st.status() used inside fragment polling for in-context progress display (T-13-03-01 mitigated)"
  - "SubtitlesStage launched synchronously before AssembleStage when burn_subs=True — both are idempotent via done-markers"
  - "Finalizar button calls st.balloons() on click but does NOT advance phase — it is the terminal phase gate; render(workdir)->bool returns assemble_done"
metrics:
  duration: "~5 minutes"
  completed: "2026-05-29"
  tasks_completed: 1
  files_modified: 1
---

# Phase 13 Plan 03: Fase 6 Ensamblaje Page Summary

Real Fase 6 wizard page with non-blocking FFmpeg assembly via PipelineBridge fragment-polling + video player + download button + QA metrics.

## What Was Built

Replaced the `phase_6_ensamble.py` placeholder with the full Fase 6 assembly page:

**ASM-01 — Non-blocking assembly:**
- "Montar vídeo" button launches `SubtitlesStage` (if `config.burn_subs`) then `AssembleStage` via `bridge.run_stage()`
- `@st.fragment(run_every="2s")` polls `stage_status("assemble", workdir)` — UI stays interactive while FFmpeg runs
- Progress shown via `st.status()` in the fragment
- Button disabled while stage is `RunStatus.RUNNING`

**ASM-02 — Results:**
- `st.video(str(output_mp4))` renders the final video inline
- `st.download_button` for `output.mp4` download
- `read_qa_report(workdir)` parsed as three `st.metric` widgets: duration, deviation, LUFS
- Graceful handling when `qa_report.json` absent (shows "no disponible")

**Gate:**
- `render(workdir) -> bool` returns `workdir.is_done("assemble")`
- "Finalizar" button enabled only when assembly done; calls `st.balloons()` on click

## Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fase 6 Ensamblaje page | d2773f9 | src/avideo/ui/pages/phase_6_ensamble.py |

## Deviations from Plan

None — plan executed exactly as written.

## Test Results

390 passed, 0 failed, 5 warnings (baseline maintained).

## Known Stubs

None — all data sources wired: bridge for stage launch, `read_qa_report` for QA metrics, `workdir.root / "output.mp4"` for video player.

## Threat Flags

None — no new network endpoints, auth paths, or trust boundary surface introduced. All threats from the plan's threat model were addressed:
- T-13-03-01 (DoS): bridge daemon thread + fragment polling — no blocking st.spinner
- T-13-03-03 (Tampering): `bg_music_path` flows through Pydantic RunConfig validation
- T-13-03-04 (DoS): `read_qa_report` returns None on any parse error

## Self-Check: PASSED

- [x] `src/avideo/ui/pages/phase_6_ensamble.py` — exists and imports headlessly
- [x] commit `d2773f9` — verified in git log
- [x] 390 tests passing
