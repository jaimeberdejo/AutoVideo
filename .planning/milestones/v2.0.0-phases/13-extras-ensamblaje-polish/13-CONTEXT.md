# Phase 13: Extras + Ensamblaje + Polish - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning
**Mode:** Smart-discuss auto-accepted (autonomous; final phase, built on Phases 8–12)

<domain>
## Phase Boundary

Implement the Fase 5 (Extras) and Fase 6 (Ensamblaje) wizard pages + final packaging/polish. Fase 5: configure optional extras (burned subtitles toggle, background-music upload + volume slider + preview, crossfade config) → persist into RunConfig. Fase 6: run the EXISTING AssembleStage (which already does music mix via Phase 8 Step 8.5 + QA) via the PipelineBridge with live FFmpeg progress, then show an in-UI video player + download button for output.mp4 + the QA report (duration deviation + LUFS). Polish: confirm `avideo studio` entry point installs via pyproject; Dockerfile exposes port 8501 + headless UI launch; bridge/page smoke tests pass alongside the existing suite. Covers EXT-01, ASM-01, ASM-02. (EXT-02/03 music backend already shipped in Phase 8; ASMB-* assembly logic shipped in v1.60.0 — this phase WIRES them in the UI; no new pipeline logic.)

</domain>

<decisions>
## Implementation Decisions

### Fase 5 — Extras (EXT-01)
- Replace placeholder pages/phase_5_extras.py keeping render(workdir)->bool.
- Widgets: `st.toggle` "Quemar subtítulos" (burn_subs); `st.file_uploader` for background music (wav/mp3) → write immediately to workdir via pipeline_ops.write_uploaded_audio-style helper (or a music-specific path), with an `st.audio` preview + `st.slider` volume (maps to RunConfig bg_music_volume, the field added in Phase 8); `st.slider`/`st.number_input` crossfade seconds (RunConfig crossfade_seconds). Optional bg_music_fade_out_s.
- On "Aprobar extras", persist all into `session_state["run_config"]` (and any config the assemble step reads). Extras are optional — approving with none selected is valid. This is a config-only page (no long stage), so the gate is immediate.

### Fase 6 — Ensamblaje (ASM-01, ASM-02)
- Replace placeholder pages/phase_6_ensamble.py keeping render(workdir)->bool.
- "Montar vídeo" runs subtitles (if needed) + AssembleStage via PipelineBridge; FFmpeg progress shown via `st.status` + `@st.fragment(run_every="2s")` polling done-markers — no UI freeze (ASM-01). AssembleStage already integrates the configured extras (music mix Step 8.5, crossfade, burn-subs).
- On completion: `st.video(workdir/output.mp4)` player + `st.download_button` for output.mp4 (ASM-02); render the QA report (read qa_report.json: duration deviation + measured/normalized LUFS) in a table/metrics.
- Gate "Finalizar" marks the final stage done (terminal phase — completes the wizard).

### Polish
- Verify `avideo studio` entry point in pyproject (added in Phase 9) installs & runs; ensure `streamlit run src/avideo/ui/app.py` also works.
- Dockerfile: add an EXPOSE 8501 + a documented headless launch command (e.g. `streamlit run ... --server.headless=true --server.address=0.0.0.0`); do NOT break the existing image build (Playwright/ffmpeg/poppler stay).
- Tests: ensure bridge tests (thread launch, done-marker detection, invalidate_downstream) + page smoke tests (import all 6 pages + app) pass alongside the full suite. Add any missing smoke test.

### Claude's Discretion
- Music-file persistence location/helper; QA report layout (st.metric vs table); crossfade widget bounds; exact Dockerfile EXPOSE/CMD wording (keep generate as default entry, document studio).

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- stages/assemble.py (AssembleStage — music mix Step 8.5 + QA from Phase 8/v1.60.0), stages/subtitles.py, stages/qa.py, integrations/ffmpeg.py (build_music_mix_args, probe_duration), qa_report.json schema (QAReport: measured_lufs/normalized_lufs/duration deviation).
- RunConfig fields: bg_music_path, bg_music_volume, bg_music_fade_out_s (Phase 8), crossfade_seconds, target_lufs, burn_subs (v1.60.0).
- Phase 9: PipelineBridge, ui/state.py, shell gate/nav; Phase 11/12: ui/pipeline_ops.py (rerun_*/write_uploaded_* patterns), @st.fragment progress pattern.

### Established Patterns
- Pydantic v2; atomic writes; idempotent stages. Unit-test glue (extras→RunConfig persistence; music upload path guard; QA-report read/format) with stages MOCKED. Rendering + real ffmpeg assembly = manual-verify.

### Integration Points
- pages/phase_5_extras.py, pages/phase_6_ensamble.py; extend ui/pipeline_ops.py if a run_assemble/write_uploaded_music wrapper helps; Dockerfile; consumes script/slides/audio/timings from prior phases; produces output.mp4 + qa_report.json.

</code_context>

<specifics>
## Specific Ideas

Fase 6 must reuse the EXISTING AssembleStage (do not reimplement ffmpeg montage) — the bridge just runs it and the page reads output.mp4 + qa_report.json. Music/crossfade/burn-subs already flow through RunConfig into AssembleStage. Keep FFmpeg progress non-blocking via the fragment-polling pattern.

</specifics>

<deferred>
## Deferred Ideas

- None — this is the final phase of v2.0.0. (.pptx export, 9:16, theme editor, multi-user remain Later per REQUIREMENTS.)

</deferred>
