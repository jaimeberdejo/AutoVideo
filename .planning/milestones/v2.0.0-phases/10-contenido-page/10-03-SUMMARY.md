---
phase: 10-contenido-page
plan: "03"
subsystem: ui-pages
tags: [streamlit, ui, contenido, bullets, wizard]
dependency_graph:
  requires:
    - 10-02 (bullets_gen.py with generate_bullets + validate_duration)
    - 09 (WorkdirManager, app.py shell, PHASE_COMPLETION_STAGE contract)
  provides:
    - src/avideo/ui/pages/phase_1_contenido.py (real render implementation)
    - workdir/bullets.yaml (runtime artifact, format: BulletsInput.model_dump())
  affects:
    - All downstream wizard phases (11-13) that read workdir/bullets.yaml
tech_stack:
  added: []
  patterns:
    - st.data_editor with num_rows="dynamic" for interactive bullet editing
    - st.spinner wrapping generate_bullets() to avoid blocking the main thread
    - session_state cache keys (cnt_generated_bullets, cnt_manual_bullets) for rerun survival
    - workdir.write_checkpoint("context", bi) + workdir.mark_done("context") for gate signaling
    - yaml.safe_dump(BulletsInput.model_dump()) for bullets.yaml persistence in engine format
key_files:
  created: []
  modified:
    - src/avideo/ui/pages/phase_1_contenido.py
decisions:
  - "Wrote bullets.yaml via Path.write_text(yaml.safe_dump(...)) instead of WorkdirManager.write_checkpoint to produce .yaml (not .json); checkpoint JSON is separately written as context.json for the shell's is_done check"
  - "Defensive validate_duration() call retained even though st.number_input enforces bounds (belt-and-suspenders, aligns with T-10-03-04 threat)"
  - "Session_state cache keys (cnt_generated_bullets, cnt_manual_bullets) survive reruns; generated bullets are not re-fetched on every Streamlit rerun"
metrics:
  duration_seconds: 80
  completed_date: "2026-05-29"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 1
---

# Phase 10 Plan 03: Fase 1 Contenido Page Summary

**One-liner:** Real Fase 1 Contenido page — topic+duration form, manual/Claude-generate radio, dynamic data_editor, approval writes bullets.yaml in engine format and marks context done.

## What Was Built

Replaced the Phase 9 placeholder toggle in `phase_1_contenido.py` with the full CNT-01/02/03 implementation:

- **Topic + duration inputs:** `st.text_input` for topic, `st.number_input` (15–1800 s, step 15) for duration, `validate_duration()` guard.
- **Source choice (CNT-02):** `st.radio` between "Escribir mis bullets" and "Generar desde el tema (Claude)".
- **Auto-generate path:** "Generar bullets" button calls `generate_bullets()` inside `st.spinner`; result cached in `st.session_state["cnt_generated_bullets"]` to survive Streamlit reruns without re-calling the API.
- **Data editor (CNT-03):** Both paths use `st.data_editor(num_rows="dynamic")` for add/edit/delete of bullets.
- **Approval gate (CNT-01):** "Aprobar bullets y continuar" writes `workdir/bullets.yaml` via `yaml.safe_dump(BulletsInput.model_dump())`, writes `context.json` checkpoint, touches `.context.done` marker, updates `session_state["run_config"]`.
- **Resume path:** If `.context.done` already exists (browser refresh), `gate_met=True` without re-click.

## Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement real phase_1_contenido.py | b839ac6 | src/avideo/ui/pages/phase_1_contenido.py |

## Checkpoint Handling

**Task 2 (checkpoint:human-verify)** — Unattended autonomous run. Auto-approved after passing all headless smoke checks:
- `from avideo.ui.pages.phase_1_contenido import render` — import clean
- `def render(` present (count=1)
- `st.data_editor`, `num_rows="dynamic"`, `bullets.yaml`, `mark_done`, `generate_bullets`, `st.number_input` all present
- Full pytest suite: **361 passed, 5 warnings**

**Manual verification needed (deferred):** Run `uv run avideo studio`, navigate Fase 1:
1. Enter topic + duration (default 120 s).
2. Test "Escribir mis bullets" path: type bullets in data_editor, approve.
3. Test "Generar desde el tema (Claude)" path: click "Generar bullets" → spinner → edit → approve.
4. Verify `workdir/bullets.yaml` has `title:` and `bullets:` keys matching approved bullets.
5. Confirm shell footer "Aprobar y continuar →" is enabled after approval, advances to Phase 2.
6. Confirm browser refresh resumes at Phase 2 (done-marker survived).
7. `uv run avideo generate --bullets workdir/bullets.yaml --dry-run` should parse without error.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — `workdir/bullets.yaml` is written with real user-approved content on approval.

## Threat Flags

None — all threat mitigations from T-10-03-01 through T-10-03-05 are in place:
- T-10-03-01: topic injected into user turn only (generate_bullets passes it as user content, not system prompt).
- T-10-03-04: `st.number_input` bounds + `validate_duration()` double-guard applied.

## Self-Check: PASSED

Files exist:
- src/avideo/ui/pages/phase_1_contenido.py — FOUND
- (workdir/bullets.yaml is a runtime artifact, not a source file)

Commits exist:
- b839ac6 — FOUND (feat(10-03): implement real Fase 1 Contenido page)

Test suite: 361 passed.
