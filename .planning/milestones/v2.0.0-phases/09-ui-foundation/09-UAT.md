---
status: verified
phase: 09-ui-foundation
source:
  - 09-01-SUMMARY.md
  - 09-02-SUMMARY.md
  - 09-03-SUMMARY.md
  - 09-04-SUMMARY.md
started: 2026-06-18T23:56:43Z
updated: 2026-07-01T12:31:00Z
---

## Tests

### 1. App loads with 6-phase wizard + stepper
expected: Opening localhost:8501 shows a 6-phase wizard; stepper highlights active phase, marks completed ones; no redundant sidebar nav.
result: PASS — verified live via Chrome MCP + Playwright against a real `avideo studio` process (real bullets/duration, real Anthropic/OpenAI API calls). Sidebar shows all 6 phases with ▶/✅/○ markers; no redundant multipage nav. Also covered by automated test `tests/test_ui_wizard_e2e.py::test_app_loads_and_shows_six_phase_wizard`.

### 2. Gated continue (no advance without Aprobar)
expected: The wizard will not advance to the next phase until you explicitly click "Aprobar"/"Continuar". Trying to move forward without approving does nothing.
result: PASS — verified live: footer "Aprobar y continuar →" stays disabled until bullets are approved (Fase 1), script approved (Fase 2), slides approved (Fase 3), voice approved (Fase 4). Also covered by `test_cannot_advance_phase_1_without_bullets` / `test_can_advance_after_approving_bullets`.

### 3. Back-nav confirm + invalidate downstream
expected: Navigating back to a previous phase shows a confirmation dialog. Confirming invalidates downstream checkpoints (later phases reset / must be redone).
result: PASS — verified live: clicking "← Atrás" from Fase 6 showed "Volver a la Fase 5 invalidará el trabajo posterior (a partir de la etapa 'subs'). ¿Continuar?"; confirming deleted `.assemble.done` while correctly preserving `.subs.done` (Fase 5's own completion marker). `output.mp4` remains on disk (dead weight, not deleted) but is not shown until re-assembled — no staleness bug, since render() gates the video/QA section behind `assemble_done`.

### 4. Resume from workdir on refresh
expected: Refresh the browser (or close/reopen) with the same workdir. The wizard reopens at exactly the same phase and state — reconstructed from workdir/*.json, not lost.
result: PASS (after fix) — initial live test found a BLOCKER: after refresh past Phase 1, the app crashed with a raw Pydantic `ValidationError: duration Field required` because `session_state["run_config"]` (holding topic/duration) is never rehydrated from workdir on refresh/restart — only `phase` is. Fixed by adding `UIRunConfig` checkpoint (`ui/state.py`) written on Phase 1 approval and rehydrated into `session_state["run_config"]` on `_phase_initialised` (`ui/app.py`). Re-verified live: full app restart (kill + relaunch process) correctly resumed at the last completed phase with no error. Also covered by `test_refresh_resumes_from_workdir`.

### 5. Full 6-phase wizard, real topic, real assembly (added — not in original 4-item checklist but exercised end-to-end)
expected: A real topic ("Por qué las pequeñas empresas deberían monitorizar su huella de carbono", 60s) can be carried through all 6 phases to a downloadable, playable MP4.
result: PASS (after 2 fixes) — produced a real 1920x1080 H.264/AAC `output.mp4` (54.4s) with `qa_report.json`, `output.srt`/`.vtt`. Found and fixed 2 additional blockers along the way:
  - Scriptwriter's calibration-retry prompt lost all topic/slide context, causing the model to invent an unrelated generic script when word-budget drift triggered a retry (`stages/scriptwriter.py`).
  - FFmpeg assembly always failed on real runs ("Unable to choose an output format for '...output.mp4.tmp'") because the atomic-write temp filename had `.tmp` as its FINAL extension, which ffmpeg's format autodetection doesn't recognize (`stages/assemble.py`, `integrations/ffmpeg.py`). Neither bug was caught by the 446-test unit suite because it mocks all subprocess/API calls.

## Summary

total: 5
passed: 5
issues: 0 (2 blockers found were fixed in this session, plus 1 QA-metric correctness bug — see main report)
pending: 0
skipped: 0

## Gaps

None remaining for phase 9's own scope. See `.planning/v2.0.0-BROWSER-VERIFICATION.md` for phases 10–13 (which had no UAT tracking file at all before this session) and the full bug list.
