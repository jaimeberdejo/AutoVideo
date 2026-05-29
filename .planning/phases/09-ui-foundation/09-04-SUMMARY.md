---
phase: 09-ui-foundation
plan: "04"
subsystem: ui
tags: [streamlit, wizard, navigation, session-state, workdir, placeholder-pages]
dependency_graph:
  requires:
    - 09-02  # WorkdirManager.invalidate_downstream
    - 09-03  # state.py (init_session_state, workdir_phase_from_done_markers, PHASES, PHASE_COMPLETION_STAGE, advance_phase), bridge.py (RunStatus, stage_status)
  provides:
    - src/avideo/ui/app.py  # Streamlit entry point; avideo studio entry
    - src/avideo/ui/pages/  # 6 placeholder phase modules with render() contract
    - .streamlit/config.toml  # server config (address, maxUploadSize, theme)
  affects:
    - cli.py  # studio subcommand already implemented; no changes needed
tech_stack:
  added: []
  patterns:
    - "st.set_page_config(layout=wide) as first Streamlit call"
    - "Unconditional main() call at module level (correct Streamlit single-file pattern)"
    - "_phase_initialised sentinel in session_state — reconstruct phase from workdir on first load only"
    - "Lazy import of phase_modules inside main() to avoid circular import issues"
    - "Back-nav: _confirm_back session_state flag + inline st.container(border=True) confirmation"
    - "AVIDEO_STUDIO_WORKDIR env var for workdir resumption (set by avideo studio --workdir)"
    - "@st.fragment commented example for Phases 10-13 long-running stages"
key_files:
  created:
    - src/avideo/ui/app.py
    - src/avideo/ui/pages/__init__.py
    - src/avideo/ui/pages/phase_1_contenido.py
    - src/avideo/ui/pages/phase_2_guion.py
    - src/avideo/ui/pages/phase_3_slides.py
    - src/avideo/ui/pages/phase_4_voz.py
    - src/avideo/ui/pages/phase_5_extras.py
    - src/avideo/ui/pages/phase_6_ensamble.py
    - .streamlit/config.toml
  modified: []
decisions:
  - "Unconditional main() at module level — Streamlit re-runs the whole script on every interaction; calling main() once per run is the correct single-file Streamlit pattern"
  - "_phase_initialised sentinel — reconstruct phase from workdir done-markers on first load only; subsequent reruns use session_state phase directly so user navigation takes precedence"
  - "Lazy import of phase_modules inside main() — avoids potential circular-import issues at module load time; negligible performance cost"
  - "Back-nav confirmation uses _confirm_back session_state flag + inline container instead of st.dialog — simpler, no async, compatible with current Streamlit version"
  - "PHASE_COMPLETION_STAGE imported from state.py (not redefined in app.py) — single source of truth"
metrics:
  duration: "3m 11s"
  completed_date: "2026-05-29"
  tasks: 2
  files: 9
---

# Phase 09 Plan 04: App Shell + Placeholder Pages Summary

Streamlit wizard shell with sidebar 6-step stepper, workdir-backed session state, phase router, navigation footer, back-nav confirmation with invalidate_downstream, and 6 placeholder phase pages implementing the `render(workdir) -> bool` contract.

## What Was Built

### Task 1: src/avideo/ui/app.py (commit d823b59)

Full Streamlit entry point:

- `st.set_page_config(layout="wide", title="Auto Video Narrado — Studio")` as first call
- `init_session_state()` called at top of `main()` — sets phase/workdir_path/run_config defaults
- Workdir setup: uses `AVIDEO_STUDIO_WORKDIR` env var if set, otherwise creates `runs/run_<isoformat>/workdir/` on first load
- Phase reconstruction via `workdir_phase_from_done_markers()` on first load only (`_phase_initialised` sentinel prevents overwriting user navigation on subsequent reruns)
- Sidebar: "Studio Guiado" title, workdir path caption, 6-step stepper with ✅/▶/○ markers, "Nuevo proyecto" button
- Phase routing: `_PHASE_MODULES[phase].render(workdir)` dispatches to the active page module
- Navigation footer: `← Atrás` (disabled on phase 1) + `Aprobar y continuar →` (disabled until `gate_met`)
- Back-nav confirmation: `_confirm_back` session flag triggers inline `st.container(border=True)` with "Sí, volver atrás" / "Cancelar"; "Sí" calls `invalidate_downstream` then decrements phase
- `@st.fragment` commented example for Phases 10–13 long-running stages
- `load_dotenv(override=False)` at startup (T-09-04-01 mitigation — keys never stored in session_state)

### Task 2: 6 Phase Pages + config.toml (commit 728ffbc)

- `src/avideo/ui/pages/__init__.py`: package docstring establishing the `render(workdir) -> bool` contract
- `phase_1_contenido.py` through `phase_6_ensamble.py`: each provides `render(WorkdirManager) -> bool` with:
  - `st.info()` placeholder body ("Fase N — Name (implementado en Phase 1X)")
  - `st.toggle("Marcar esta fase como lista", key="gate_phase_N")` as Phase 9 gate condition
  - `st.success()` when gate met
  - Commented stub preview areas (`st.image`/`st.audio`/`st.video`) for Phases 10–13
- `.streamlit/config.toml`: `address = "127.0.0.1"` (T-09-04-03), `maxUploadSize = 200`, `base = "light"`, `fastReruns = true`

## Checkpoint: AUTO-APPROVED (Unattended)

The human-verify checkpoint was auto-approved per unattended execution instructions.

## Manual Verification Needed

The following browser check was deferred and requires manual confirmation before v2.0.0 ship:

1. Run `uv run avideo studio` (or `avideo studio`)
2. Browser opens at http://localhost:8501
3. Confirm page title is "Auto Video Narrado — Studio"; layout is wide
4. Confirm sidebar shows 6 phases with ▶ on Phase 1, ○ on phases 2–6
5. Confirm "Aprobar y continuar →" button is DISABLED (grey) initially
6. Toggle "Marcar esta fase como lista" → button becomes ENABLED (blue primary)
7. Click "Aprobar y continuar →" → wizard advances to Phase 2; sidebar shows ✅ on Phase 1
8. Click "← Atrás" → inline confirmation dialog appears; click "Sí, volver atrás" → returns to Phase 1
9. Close browser, reopen at localhost:8501 → wizard shows the phase where you left off
10. Verify `avideo generate --help` still works from a separate terminal (headless CLI unaffected)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

All 6 phase pages are intentional placeholders. Each page's body is marked "(implementado en Phase 1X)" and contains commented `st.image`/`st.audio`/`st.video` stubs. These are the expected deliverables for Phases 10–13 (Contenido, Guion+Slides, Voz, Extras+Ensamblaje).

The stubs do NOT prevent the plan's goal (navigable wizard shell) from being achieved — the toggle gate and navigation work end-to-end.

## Threat Flags

None — all threats addressed:
- T-09-04-01: `load_dotenv(override=False)` at app startup; keys never in session_state or UI
- T-09-04-02: `WorkdirManager(Path(...))` only creates subdirs under root; no user-controlled path segments in Phase 9
- T-09-04-03: `.streamlit/config.toml` sets `address = "127.0.0.1"`; `avideo studio` CLI also passes `--server.address=127.0.0.1`

## Headless Smoke Results

| Check | Result |
|-------|--------|
| `app.py` syntax | PASS |
| All 6 page files syntax | PASS |
| `layout="wide"` present | PASS (1 match) |
| `def main` present | PASS (1 match) |
| `invalidate_downstream` called | PASS (1 match) |
| `init_session_state` called | PASS (2 matches: import + call) |
| `workdir_phase_from_done_markers` called | PASS (2 matches: import + call) |
| `@st.fragment` commented example | PASS (1 match) |
| All 6 pages define `render()` | PASS |
| `address = "127.0.0.1"` in config.toml | PASS (1 match) |
| All 6 page modules import without error | PASS |
| `avideo generate --help` | PASS (untouched) |
| `pytest` (350 tests) | PASS (350 passed, 5 warnings) |

## Self-Check: PASSED
