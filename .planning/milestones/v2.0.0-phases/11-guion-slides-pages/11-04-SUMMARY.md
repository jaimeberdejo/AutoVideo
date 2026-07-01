---
phase: 11-guion-slides-pages
plan: "04"
subsystem: ui-pages
tags: [streamlit, slides, verification, claude-vision, upload, bridge]
dependency_graph:
  requires: [11-02]
  provides: [phase_3_slides.render, Fase3DiappositivasPage]
  affects: [app.py phase router, bridge, pipeline_ops, verify_slides, slides_dispatch]
tech_stack:
  added: []
  patterns: [bridge-poll-fragment, file-upload-immediate-write, mode-radio-dispatch, thumbnail-grid-badges]
key_files:
  created: []
  modified:
    - src/avideo/ui/pages/phase_3_slides.py
decisions:
  - "Lazy imports inside render() body for all heavy stage/model modules — keeps import graph clean and avoids circular issues"
  - "Mode persisted as st.session_state['sld_mode'] and propagated to rc_dict['slides_mode'] so SlidesDispatchStage routes correctly on each rerun"
  - "Upload path uses fixed expected_name (slide_XX.png) as filename passed to write_uploaded_slide — user's original filename ignored (T-11-04-01/05 mitigated)"
  - "Approval gate (_approval_gate helper) shared between auto and upload paths — DRY; returns verify_done so shell footer enables correctly"
  - "Re-upload triggers workdir.invalidate_downstream('slides') then st.rerun — done-markers cleared, allowing fresh re-verification"
metrics:
  duration_seconds: 97
  completed_date: "2026-05-29"
  tasks_completed: 1
  files_modified: 1
---

# Phase 11 Plan 04: Fase 3 Diapositivas Page Summary

**One-liner:** Full SLD-01/02/03 Streamlit wizard page for slide generation (auto mode with PNG thumbnails and QC badges) and manual upload (Claude Vision per-slide verification with re-upload support).

## What Was Built

Replaced the Phase 9 placeholder `phase_3_slides.py` with a complete Fase 3 Diapositivas wizard page implementing all three SLD requirements:

- **SLD-01 — Mode radio:** `st.radio` with "Generar (auto)" and "Subir las mías" options; mode persisted in `session_state["sld_mode"]` and propagated into `run_config["slides_mode"]` for `SlidesDispatchStage` routing.
- **SLD-02 — Auto path:** Launches `SlidesDispatchStage` + `VerifyStage` via `bridge.run_stage`; `@st.fragment(run_every="2s")` polls progress; PNG thumbnails in a 3-column grid with `badge_for_verdict` badges (all `✅` in auto mode since verifier skips API calls); QC detail expanders for non-ok slides; "Pedir variación de slides" button calls `rerun_slides` via `pipeline_ops` then `st.rerun`.
- **SLD-03 — Upload path:** Per-slide `st.file_uploader` (PNG/PDF); each upload written immediately via `write_uploaded_slide` (Pitfall: Streamlit discards `UploadedFile` on next rerun); once all slots filled, "Verificar diapositivas (Claude Vision)" button runs `SlidesDispatchStage` + `VerifyStage`; per-slide badges + issues + suggestions; "Volver a subir / re-verificar" invalidates downstream and reruns.
- **Approval gate:** Shared `_approval_gate()` helper; button disabled until `workdir.is_done("verify")`; returns `verify_done` to shell — enables "Aprobar y continuar →".

The shell router (`app.py` `_PHASE_MODULES`) was already pointing to `phase_3_slides` — no change needed.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement real Fase 3 Diapositivas page | 9c90810 | src/avideo/ui/pages/phase_3_slides.py |

## Checkpoint: human-verify (auto-approved — unattended run)

The human-verify checkpoint was auto-approved per unattended execution instructions.

**Deferred manual check:** The following browser verification is deferred for the next interactive session:

- AUTO MODE: Reach Fase 3 with "Generar (auto)" selected; confirm ⏳ progress indicator appears, then PNG thumbnails load in 3-column grid with badges; click "Pedir variación de slides" and confirm regeneration; click "Aprobar diapositivas" and confirm footer enables.
- UPLOAD MODE: Switch to "Subir las mías"; upload PNG per slot; confirm immediate write to `workdir/slides_user/`; click "Verificar diapositivas (Claude Vision)"; confirm per-slide badges and issues display; re-upload and re-verify flow; click "Aprobar diapositivas".
- OVERALL: Browser refresh mid-wizard resumes at Fase 3 with correct state.

## Deviations from Plan

None - plan executed exactly as written. All interfaces used as documented in the plan's `<interfaces>` section.

## Known Stubs

None. The page is fully wired: auto path reads from `SlidesOutput` + `VerificationReport` checkpoints; upload path reads `StoryboardOutput` for slide count.

## Threat Flags

No new threat surface beyond the plan's threat model. Mitigations applied:
- T-11-04-01/05: filename overwritten with `expected_name` (`slide_XX.png`) — user's original filename never reaches `write_uploaded_slide`; `write_uploaded_slide` guards traversal via `/` check.
- T-11-04-02: image bytes passed to `VerifyStage` which applies existing `MAX_BYTES` guard (T-06-02).

## Self-Check: PASSED

- `src/avideo/ui/pages/phase_3_slides.py`: FOUND
- Commit `9c90810`: FOUND (`git log --oneline -1` confirms)
- `python -c "from avideo.ui.pages.phase_3_slides import render; print('import ok')"`: PASSED
- `def render` count: 1
- `st.radio` count: 1
- `st.file_uploader` count: 3
- `st.image` count: 3
- `rerun_slides` count: 2
- `write_uploaded_slide` count: 4
- `badge_for_verdict|VerificationReport` count: 9
- Test suite: 370 passed, 5 warnings (no regressions from 370 baseline)
