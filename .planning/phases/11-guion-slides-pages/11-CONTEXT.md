# Phase 11: Guion + Slides Pages - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning
**Mode:** Smart-discuss auto-accepted (autonomous; built on Phase 9 shell + Phase 10 contenido)

<domain>
## Phase Boundary

Implement the Fase 2 (Guion) and Fase 3 (Diapositivas) wizard pages on the Phase 9 shell, wiring the EXISTING pipeline stages — storyboard → timing → scriptwriter (Fase 2) and slides_dispatch/slides_auto + verify_slides (Fase 3) — into interactive, human-gated review loops. NO new pipeline logic; reuse stages as-is and drive them via the PipelineBridge. Covers SCR-01, SCR-02, SCR-03, SCR-04, SLD-01, SLD-02, SLD-03. Replaces the Phase 9 placeholders `pages/phase_2_guion.py` and `pages/phase_3_diapositivas.py` (keep `render(workdir)->bool`).

</domain>

<decisions>
## Implementation Decisions

### Fase 2 — Guion (SCR-01..04)
- On entry, if `script.json` not done: auto-run storyboard → timing → scriptwriter via `PipelineBridge.run_stage` (these are LLM calls; show per-stage progress via `st.status` / `@st.fragment(run_every="2s")` polling done-markers). Script appears slide-by-slide on completion (SCR-01).
- Editing (SCR-02): render each slide's narration in an editable `st.text_area`; on save, write the edited `script.json` checkpoint (atomic) and call `WorkdirManager.invalidate_downstream("script")` so voice/align/subs/assemble are invalidated (SCR-04).
- Variation (SCR-03): a "Pedir variación" control (whole-script or per-slide) re-runs ONLY the scriptwriter stage (not storyboard/timing/the whole pipeline) via the bridge; result repopulates the editor. Iterate until the user approves.
- Gate: "Aprobar guion" persists the (possibly edited) script and marks the script stage done → shell advances.

### Fase 3 — Diapositivas (SLD-01..03)
- Mode choice (SLD-01): `st.radio` — "Generar (auto)" vs "Subir las mías". This maps to the existing `slides_mode` (auto vs manual/hybrid). Persist into RunConfig.
- Auto path (SLD-02): run slides via the existing slides_auto/slides_dispatch through the bridge; show PNG thumbnails (`st.image`) as they complete. "Pedir variación" re-runs slide generation (regenerate). Iterate until approved. (If the auto verifier runs, show ok/warning/fail badges from `verification_report.json`.)
- Upload path (SLD-03): `st.file_uploader` (PNG/PDF) per slide written immediately to `workdir/slides_user/` (filename convention the existing slides_ingest/manual expects); then run the existing `verify_slides` (Claude Vision) via the bridge and show the per-slide report (ok/warning/fail + issues/suggestions) with `st.image` thumbnails. The user can re-upload and re-verify before approving.
- Gate: "Aprobar diapositivas" marks the slides stage done → shell advances. Editing/re-uploading invalidates downstream.

### Reuse & contracts
- Use the EXISTING stage classes/functions: `storyboard.py`, `timing.py`, `scriptwriter.py`, `slides_dispatch.py`/`slides_auto.py`, `slides_ingest.py`/`slides_manual.py`, `verify_slides.py`. The bridge calls them with the workdir/RunConfig built from earlier phases. Do NOT modify their logic; if a stage needs a "regenerate this one stage" entry that doesn't exist, add a thin wrapper in the UI layer (not in the stage).
- `bullets.yaml` (from Phase 10) + RunConfig feed storyboard. Reading checkpoints uses WorkdirManager (workdir is source of truth).

### Claude's Discretion
- Per-slide vs whole-script variation UX detail; thumbnail grid layout; how badges render; whether timing is shown read-only. Exact wrapper for single-stage re-run.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- Stages: storyboard/timing/scriptwriter (Phase 2), slides_auto/slides_dispatch (Phase 3), slides_ingest/slides_manual/slides_hybrid + verify_slides (Phase 6).
- Phase 9: PipelineBridge (run stages off-thread), ui/state.py, WorkdirManager.invalidate_downstream, the shell gate/nav.
- Checkpoints: storyboard.json, timings.json, script.json, slides/ or slides_user/, verification_report.json.

### Established Patterns
- Pydantic v2; atomic writes; idempotent stages (re-run skips done). Unit-test the UI glue logic (single-stage re-run wrapper, edited-script persistence + invalidate_downstream call, upload-to-workdir path handling, badge mapping from verification_report) with stages MOCKED. Rendering is manual-verify.

### Integration Points
- pages/phase_2_guion.py, pages/phase_3_diapositivas.py; possibly a small ui/pipeline_ops.py wrapper for single-stage re-runs; consumes Phase 10 bullets.yaml; produces script.json + slides for Phase 12 (voz).

</code_context>

<specifics>
## Specific Ideas

Variation MUST re-run only the scriptwriter (SCR-03) / only slide generation (SLD-02) — never the whole pipeline. Lean on stage idempotence + invalidate_downstream so edits stay consistent. Use the bridge for the LLM/render stages (they're slow); keep the UI responsive.

</specifics>

<deferred>
## Deferred Ideas

- Voz (Phase 12), Extras+Ensamblaje (Phase 13). Screenshot/video bullet items are out of scope (removed).

</deferred>
