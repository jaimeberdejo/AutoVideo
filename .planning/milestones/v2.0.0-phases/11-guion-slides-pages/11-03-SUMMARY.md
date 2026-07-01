---
phase: 11-guion-slides-pages
plan: "03"
subsystem: ui-pages
tags: [streamlit, wizard, guion, scriptwriter, pipeline-bridge, SCR-01, SCR-02, SCR-03, SCR-04]
dependency_graph:
  requires: [11-02]
  provides: [phase_2_guion_page]
  affects: [ui/app.py wizard navigation]
tech_stack:
  added: []
  patterns:
    - "@st.fragment(run_every='2s') polling for background stage progress"
    - "bridge.run_stage idempotency for sequential stage auto-launch"
    - "session_state cache (scr_edited_narrations) for in-editor narration edits"
key_files:
  created: []
  modified:
    - src/avideo/ui/pages/phase_2_guion.py
decisions:
  - "Variation button deletes scr_edited_narrations from session_state so the editor repopulates from the new script rather than carrying over stale edits"
  - "Approval gate calls workdir.mark_done('scriptwriter') idempotently; done-marker set by bridge.run_stage may already be present"
  - "Stage auto-launch is sequential: storyboard first, then timing, then scriptwriter — each run_stage call is a no-op if the stage already ran"
  - "_save_edited_script uses persist_edited_script from pipeline_ops (which calls invalidate_downstream) rather than writing workdir directly"
  - "Auto-approve checkpoint (unattended run): live browser verification deferred as manual item"
metrics:
  duration_seconds: 87
  completed_date: "2026-05-29"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 1
---

# Phase 11 Plan 03: Fase 2 Guion Page Summary

**One-liner:** Full narration-script wizard page: auto-runs storyboard+timing+scriptwriter on entry with live progress, per-slide text_area editor with save/invalidate, scriptwriter-only variation, and approval gate.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Implement real Fase 2 Guion page | fa296c4 | src/avideo/ui/pages/phase_2_guion.py |

## What Was Built

Replaced the Phase 9 placeholder in `phase_2_guion.py` with the full SCR-01..04 implementation:

**SCR-01 — Auto-run on entry:** When `render(workdir)` is called and the scriptwriter done-marker is absent, the function launches the next pending pipeline stage (storyboard → timing → scriptwriter) via `bridge.run_stage` (idempotent). A `st.status` box shows per-stage progress (pending / generating / done / error). A `@st.fragment(run_every="2s")` function polls `stage_status("scriptwriter", workdir)` every 2 seconds and triggers `st.rerun()` once the scriptwriter completes, causing the editor to appear. `render()` returns `False` during this phase.

**SCR-02 — Per-slide editor:** Once `scriptwriter` done-marker is present, the script checkpoint is read and each slide's narration rendered in `st.text_area`. Edits are cached in `session_state["scr_edited_narrations"]`. A per-slide "Guardar edicion" button calls `persist_edited_script(workdir, updated_script)` which atomically writes `script.json` and calls `invalidate_downstream("scriptwriter")` to invalidate voice/align/subs/assemble.

**SCR-03 — Variation:** "Pedir variacion del guion" button deletes `scr_edited_narrations` from session_state (so the editor repopulates cleanly from the new script), then calls `rerun_scriptwriter(workdir, config)` which deletes only the scriptwriter done-marker and launches a new thread. Storyboard and timing done-markers are untouched.

**SCR-04 — Approval gate:** "Aprobar guion" button saves any in-editor edits via `persist_edited_script`, calls `workdir.mark_done("scriptwriter")` (idempotent), and triggers rerun. The function returns `workdir.is_done("scriptwriter")` — `True` only after approval. On browser refresh, if the done-marker exists, the editor appears immediately with the approved script.

## Verification

```
uv run python -c "from avideo.ui.pages.phase_2_guion import render; print('import ok')"
# → import ok

grep -c "def render" src/avideo/ui/pages/phase_2_guion.py        # → 1 ✅
grep -c "st.text_area" src/avideo/ui/pages/phase_2_guion.py      # → 2 ✅ (>= 1)
grep -c "rerun_scriptwriter" src/avideo/ui/pages/phase_2_guion.py # → 3 (docstring + import + call) ✅
grep -c "persist_edited_script" src/avideo/ui/pages/phase_2_guion.py # → 3 ✅ (>= 1)
grep -c "run_stage" src/avideo/ui/pages/phase_2_guion.py          # → 4 ✅ (>= 1)

uv run pytest -q --tb=no
# → 370 passed, 5 warnings in 3.47s ✅
```

## Deviations from Plan

### Auto-approved Checkpoint

**Type:** human-verify (checkpoint task 2)

The `<autonomous_checkpoint_handling>` directive for this unattended run specifies: auto-approve the human-verify gate; record live browser check as DEFERRED manual item. No live Streamlit server was started.

**Deferred manual verification steps:**
1. Start: `uv run avideo studio` (opens localhost:8501)
2. Create a project in Fase 1 (approve bullets)
3. Advance to Fase 2 — verify storyboard → timing → guion progress appears with per-stage st.status
4. Once complete, verify slide narrations appear in editable text_area widgets
5. Edit one narration and click "Guardar edicion slide N" — confirm workdir/script.json updates and downstream .done files are cleared
6. Click "Pedir variacion del guion" — verify progress re-appears and new narration text is generated
7. Click "Aprobar guion" — confirm gate returns True and wizard advances
8. Refresh browser — verify wizard resumes at Fase 2 with editor showing approved script

## Threat Flags

No new security surface introduced. The `scr_edited_narrations` session_state key holds only user-authored text that flows to `script.json` — this was already analyzed as T-11-03-02 (accept) in the plan's threat model.

## Self-Check: PASSED

- [x] `src/avideo/ui/pages/phase_2_guion.py` exists and imports cleanly
- [x] Commit fa296c4 exists in git log
- [x] 370 tests pass (no regressions vs baseline)
- [x] All SCR-01..04 requirements implemented and verifiable via grep
