# Phase 9: UI Foundation - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning
**Mode:** Smart-discuss auto-accepted (autonomous; decisions locked in .planning/research/ARCHITECTURE.md + SUMMARY.md + STATE.md)

<domain>
## Phase Boundary

Build the Streamlit foundation that turns the existing headless pipeline into a guided 6-phase wizard: the app shell (`avideo studio` entry point), the navigation/stepper with mandatory human-validation gates, the state model bridging `st.session_state` to `workdir/` checkpoints, the `PipelineBridge` that runs long stages off the Streamlit script thread, and the live-preview surface. NO per-phase page logic yet (Contenido/Guion/Voz/Extras pages are Phases 10–13) — Phase 9 delivers a navigable shell with placeholder phase bodies and the plumbing every page will use. Covers UI-01..UI-07. The CLI `avideo generate` must remain byte-for-byte functional (UI-07). Reuse existing stages — do NOT rewrite the pipeline.

</domain>

<decisions>
## Implementation Decisions

### App shell & entry point (UI-01)
- New `src/avideo/ui/` package: `app.py` (Streamlit entry), `state.py` (session/workdir state), `bridge.py` (PipelineBridge), `pages/` (placeholder phase renderers wired in 10–13).
- New console entry point `avideo studio` (typer subcommand or a thin launcher) that runs `streamlit run .../ui/app.py` on `localhost:8501`. Keep `avideo generate` untouched.
- `streamlit>=1.58.0` dependency (added in Phase 8's pyproject? if not, add here). `load_dotenv()` at app startup so API keys reach SDKs.

### Navigation, stepper & human gates (UI-02, UI-03)
- 6-phase wizard with a visible stepper (active + completed phases). Phase index held in `st.session_state["phase"]` (int).
- Forward navigation BLOCKED until the user clicks an explicit "Aprobar / Continuar" button for the current phase (no auto-advance).
- Back navigation allowed; going back and editing/regenerating invalidates downstream checkpoints via `WorkdirManager.invalidate_downstream(from_stage)` (deletes done-markers + dependent artifacts for all stages after the edited one) so the user never sees a desynced result. A confirmation dialog precedes destructive back-navigation.

### State model — workdir is source of truth (UI-04)
- `st.session_state` holds ONLY `workdir_path` (str) and `phase` (int) (+ transient form inputs). ALL pipeline artifacts are read from `workdir/*.json` via `WorkdirManager` on every rerun.
- On (re)load, reconstruct the wizard position from done-markers on disk — browser refresh/close must resume exactly where left off. No artifact state cached in session_state.
- Uploaded files are written to `workdir/` immediately on receipt (Streamlit discards UploadedFile bytes on the next rerun); only the path is kept in session_state.

### Long-running stages without blocking (UI-05)
- `PipelineBridge.run_stage(stage)` launches the stage in a `threading.Thread`; the thread writes ONLY to `workdir/` (done-markers/checkpoints) and NEVER calls `st.*`.
- A `@st.fragment(run_every="2s")` polls `WorkdirManager.is_done(stage_name)` and re-renders progress; on completion it shows the result. This is the documented Streamlit background-job pattern.
- The pipeline stages are already idempotent (checkpoint → fast reload), so a synchronous call inside `st.status` is the acceptable fallback if threading proves flaky — but default to the thread+fragment model.

### Previews (UI-06)
- Preview surface helpers (used by later pages): `st.image` for slide PNG thumbnails, editable text areas for the script, `st.video`/download for the final MP4, `st.audio` for clips. Phase 9 stubs these into a reusable preview component; pages fill them in 10–13.

### CLI preserved (UI-07)
- The UI imports and calls existing stage objects / orchestrator directly; it does NOT shell out to `avideo generate` per stage and does NOT modify pipeline logic. `avideo generate` and its 303→334 tests stay green.

### Claude's Discretion
- Exact stepper rendering (sidebar radio vs columns vs custom HTML), button labels, layout polish.
- Whether `avideo studio` is a typer subcommand vs a separate console_script — pick the cleaner integration.
- Bridge thread vs `concurrent.futures` — choose the simplest reliable approach; document the choice.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `WorkdirManager` (atomic writes, done-markers, `is_done`) — extend with `invalidate_downstream(from_stage)`.
- Orchestrator `PIPELINE_STAGES` + StageProtocol/CheckpointMixin — the bridge drives these.
- `models/config.py` RunConfig — the UI builds a RunConfig from wizard inputs.
- CLI entry (`cli.py`) with `load_dotenv()` already called at entry (commit d10120d) — mirror for the studio launcher.

### Established Patterns
- Atomic tmp→rename; idempotent stages; typed + docstrings; subprocess never shell=True (n/a for UI).
- Tests: logic that CAN be unit-tested (state reconstruction, invalidate_downstream, bridge lifecycle, RunConfig-from-inputs) should be; pure-Streamlit rendering is manual-verify.

### Integration Points
- New `src/avideo/ui/` package; new `avideo studio` entry in pyproject/cli; `WorkdirManager.invalidate_downstream`; `streamlit` dependency.

</code_context>

<specifics>
## Specific Ideas

Implementation-ready Streamlit patterns (session_state gating, `@st.fragment(run_every)`, file-upload-to-workdir, thread + done-marker polling, the PipelineBridge code sketch) are in `.planning/research/ARCHITECTURE.md` and `STACK.md`. Follow the cross-cutting invariants in `SUMMARY.md`.

</specifics>

<deferred>
## Deferred Ideas

- Actual phase page bodies (Contenido=Phase 10, Guion+Slides=Phase 11, Voz=Phase 12, Extras+Ensamblaje=Phase 13). Phase 9 ships navigable placeholders + the shared plumbing only.
- Multi-user/hosted mode, project history — Later.

</deferred>
