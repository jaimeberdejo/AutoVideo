# Phase 12: Voz Page - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning
**Mode:** Smart-discuss auto-accepted (autonomous; built on Phase 8 voice backend + Phase 9 shell + Phase 11 patterns)

<domain>
## Phase Boundary

Implement the Fase 4 (Voz) wizard page on the Phase 9 shell, wiring the EXISTING voice backend (built/extended in Phase 8) into the UI: provider selection (ElevenLabs / OpenAI Audio / own recordings), per-slide `st.audio` previews, the automatic audio-enhancement button for uploaded recordings, and an approval gate that only unlocks when every slide has audio and `timings.json` has valid word-level timestamps. Covers VOZ-01 (the page/selection). The synthesis/STT/enhancement LOGIC already exists (VOZ-02 OpenAI+whisper-1, VOZ-03 enhance_audio from Phase 8; ElevenLabs + record from v1.60.0). NO new backend logic — reuse stages + enhance_audio via the bridge/pipeline_ops. Replaces placeholder `pages/phase_4_voz.py` (keep `render(workdir)->bool`).

</domain>

<decisions>
## Implementation Decisions

### Provider selection (VOZ-01, criterion 1)
- `st.radio`/`st.selectbox`: "ElevenLabs" | "OpenAI Audio" | "Grabaciones propias". Persist into RunConfig `voice` (VoiceMode: elevenlabs | openai | record) so the existing VoiceStage dispatcher routes correctly.
- Provider-specific config widgets: ElevenLabs voice_id; OpenAI voice/model (defaults from RunConfig); record = upload widgets. All optional with sensible defaults; no errors when switching.

### Synthesis via bridge (criterion 2)
- For ElevenLabs/OpenAI: "Generar voz" runs the VoiceStage (+ align/subs as needed) via PipelineBridge with `st.status`/`@st.fragment(run_every="2s")` progress. On completion, render one `st.audio(workdir/audio/slide_XX.*)` per slide. Reuse a single-stage run helper (extend ui/pipeline_ops.py with `rerun_voice` if needed — thin wrapper, no stage logic changes).

### Own recordings + enhancement (VOZ-03 surfacing, criterion 3)
- For "record": per-slide `st.file_uploader` (wav/mp3); on upload write immediately to `workdir/audio/` (or the record-mode expected location) via a write-uploaded helper (path-traversal guarded) — never lost on rerun.
- "Mejorar audio automáticamente" button per slide (or batch): calls `utils.audio_enhance.enhance_audio(original, enhanced)` and shows a BEFORE/AFTER comparison (`st.audio` original vs enhanced) — NON-destructive preview; the user confirms before the enhanced file is adopted. CRITICAL: subtitle alignment still uses the ORIGINAL unprocessed audio (per Phase 8 decision) — the enhanced file is for the final video track only.

### Approval gate (criterion 4)
- Gate unlocks ONLY when: every slide has an audio file AND `timings.json` exists with valid word-level timestamps (strictly-increasing check already enforced by the pipeline). Provide a helper to assert this. "Aprobar voz" marks the voice (+align) stage done → shell advances. Editing/regenerating invalidates downstream (subs/assemble).

### Claude's Discretion
- Exact provider config widget layout; per-slide vs batch enhancement UX; how the timings-valid check is surfaced; whether align runs automatically after synthesis.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- Voice backend: stages/voice.py dispatcher (elevenlabs/openai/record), stages/voice_openai.py (Phase 8), integrations/elevenlabs.py + integrations/openai.py, stages/voice_record.py, stages/align.py, utils/audio_enhance.py (Phase 8).
- UnifiedTimings/timings.json (word-level) — the gate checks this.
- Phase 9: PipelineBridge, ui/state.py, WorkdirManager.invalidate_downstream; Phase 11: ui/pipeline_ops.py (rerun_*/write_uploaded_slide/badge helpers — mirror for voice), bridge progress + @st.fragment pattern, page structure.

### Established Patterns
- Pydantic v2; atomic writes; idempotent stages. Unit-test the glue (rerun_voice runs only voice; uploaded-audio write path; timings-valid gate helper; enhance preview is non-destructive) with stages/enhance MOCKED. Rendering = manual-verify.

### Integration Points
- pages/phase_4_voz.py; extend ui/pipeline_ops.py (rerun_voice, write_uploaded_audio, audio_gate_ready); consumes script.json (Phase 11) + RunConfig; produces audio/ + timings.json for Phase 13 (ensamblaje).

</code_context>

<specifics>
## Specific Ideas

The heavy lifting (TTS, STT round-trip, enhancement DSP) is ALREADY built in Phase 8 — this phase is UI wiring + the enhancement preview UX + the timings-valid gate. Enhancement preview must be non-destructive and alignment must use the original audio.

</specifics>

<deferred>
## Deferred Ideas

- Extras (subtítulos/música/transiciones) + Ensamblaje + packaging/Polish = Phase 13.

</deferred>
