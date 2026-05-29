---
phase: 9
slug: ui-foundation
type: ui-spec
status: ready
created: 2026-05-29
mode: auto-authored (autonomous; constrained by Streamlit + research/ARCHITECTURE.md)
---

# Phase 9 — UI Design Contract: Studio Wizard Shell

Design contract for the Streamlit shell. Per-page visual detail is specified in Phases 10–13; this contract covers the **frame** every page lives in.

## Layout

- **Single-page app**, wide layout (`st.set_page_config(layout="wide")`), title "Auto Video Narrado — Studio".
- **Sidebar:** vertical 6-step stepper showing the 6 phases with state markers — ✅ completed, ▶ active, ○ pending (and 🔒 for not-yet-reachable). Sidebar also shows the current `workdir` path and a "Nuevo proyecto" action.
- **Main area, top:** breadcrumb/title for the active phase + a one-line description.
- **Main area, body:** the active phase's content (placeholder in Phase 9: "Fase N — pendiente (Phase 1X)").
- **Main area, footer (sticky bottom):** navigation row — `← Atrás` (left), `Aprobar y continuar →` (right, primary). The continue button is **disabled** until the phase's completion condition is met (in Phase 9 placeholders, a simple "marcar lista" toggle stands in).

## Interaction & states

| Element | States |
|---------|--------|
| Stepper item | completed ✅ / active ▶ / pending ○ / locked 🔒 |
| Continue button | disabled (gate not met) → enabled (gate met) → busy (stage running) |
| Back button | enabled (phase>1) → confirm-dialog if it invalidates downstream → disabled (phase 1) |
| Long-stage area | idle → running (progress via `st.status` + `@st.fragment(run_every="2s")`) → done (result shown) → error (message + retry) |
| Preview panel | empty (no artifact yet) → populated (image/script/audio/video) |

## Human-validation gate (UI-02)

No phase auto-advances. `Aprobar y continuar` must be clicked; clicking it persists the phase's checkpoint (or marks done) and increments `st.session_state["phase"]`. Forward jump to a future phase via the stepper is blocked (locked) until prior phases are approved.

## Back-navigation & invalidation (UI-03)

`← Atrás` to an earlier phase, then editing/regenerating, calls `WorkdirManager.invalidate_downstream(from_stage)`. A modal/confirm (`st.dialog` or a confirm checkbox) warns: "Volver a la Fase N invalidará el trabajo posterior (guion/voz/vídeo). ¿Continuar?" before deleting downstream done-markers.

## State & resumability (UI-04)

`st.session_state` = `{workdir_path, phase, <transient form inputs>}` only. On load, the active phase is derived from `workdir/` done-markers (last completed stage + 1). Browser refresh/close resumes exactly. Uploaded files are written to `workdir/` immediately; session holds only paths.

## Progress without blocking (UI-05)

Long stages run in a `PipelineBridge` thread (never touches `st.*`); a `@st.fragment(run_every="2s")` polls `is_done()` and re-renders. Other widgets remain interactive while a stage runs.

## Visual system

Reuse the project's existing visual ethos (clean, content-first). Default Streamlit theme acceptable for v2.0.0; optional `.streamlit/config.toml` to set base theme colors aligned with `theme.yaml`. No custom JS. Icons: Streamlit emoji/markdown or inline SVG only (consistent with project's SVG-only rule).

## Accessibility / quality

- All actionable controls reachable by keyboard (native Streamlit).
- Disabled states must be visually distinct (Streamlit default).
- No blocking spinner that freezes the whole page during long work (that's the whole point of the bridge).

## Out of scope (Phase 9)

Per-page content/editors (Phases 10–13), theming polish beyond a base config, multi-user.
