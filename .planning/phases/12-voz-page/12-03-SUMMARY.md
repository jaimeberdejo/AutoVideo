---
phase: "12-voz-page"
plan: "03"
subsystem: "ui/pages"
tags: [voice, wizard, streamlit, elevenlabs, openai-tts, audio-enhance, bridge]
dependency_graph:
  requires: ["12-02", "phase_4_voz placeholder", "pipeline_ops.rerun_voice", "pipeline_ops.write_uploaded_audio", "pipeline_ops.audio_gate_ready", "utils.audio_enhance.enhance_audio", "ui.bridge"]
  provides: ["phase_4_voz.render(workdir)->bool (VOZ-01)", "non-destructive enhance preview (VOZ-03)"]
  affects: ["app.py phase routing (phase 4)", "voice approval gate → phase 5 navigation"]
tech_stack:
  added: []
  patterns: ["@st.fragment(run_every=2s) bridge polling", "lazy imports inside function bodies (noqa: PLC0415)", "non-destructive audio preview before adoption", "per-slide container layout with border=True"]
key_files:
  created: []
  modified:
    - path: "src/avideo/ui/pages/phase_4_voz.py"
      change: "Replaced 49-line placeholder with 280-line real VOZ-01/VOZ-03 implementation"
decisions:
  - "Alignment always uses original audio (not enhanced copy) per Phase 8 Pitfall 22 decision"
  - "Enhanced file adoption overwrites only the audio slot for video assembly; align checkpoint is not invalidated"
  - "st.container(border=True) used for per-slide upload sections for visual clarity"
  - "AlignStage polling uses the same @st.fragment pattern as VoiceStage polling"
metrics:
  duration: "1m 40s"
  completed_date: "2026-05-29"
  tasks_completed: 1
  tasks_total: 2
  files_changed: 1
---

# Phase 12 Plan 03: Voz Wizard Page Summary

**One-liner:** Real Fase 4 Voz page replacing placeholder — three TTS providers (ElevenLabs/OpenAI/record), bridge polling with per-slide st.audio previews, non-destructive enhance BEFORE/AFTER, timings-valid gate.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement phase_4_voz.py — provider selection, synthesis, upload, gate | 3cb9b1d | src/avideo/ui/pages/phase_4_voz.py |

## What Was Built

The Phase 9 placeholder in `pages/phase_4_voz.py` (49 lines, `st.toggle` gate) was replaced with the real Fase 4 Voz wizard (280+ lines):

**Provider selection (VOZ-01/1):** `st.radio` with three options — ElevenLabs (voice_id text input), OpenAI Audio (voice selectbox + model selectbox), Grabaciones propias (per-slide upload). Selection persists into `session_state['run_config']['voice']` as `VoiceMode`.

**Synthesis path (VOZ-01/2):** "Generar voz" button calls `rerun_voice(workdir, config)` via `pipeline_ops`; button is disabled while RUNNING. `@st.fragment(run_every="2s")` polls `stage_status("voice", workdir)`; exits fragment on DONE via `st.rerun()`. Post-synthesis: per-slide `st.expander` with `st.audio` for each slide's mp3/wav.

**Record path (VOZ-01/3 + VOZ-03):** Per-slide `st.file_uploader` writes immediately via `write_uploaded_audio`; "Mejorar audio" button calls `enhance_audio(original, enhanced_path)` NON-DESTRUCTIVELY; BEFORE/AFTER `st.audio` comparison shown side-by-side; "Adoptar" copies enhanced over original slot. "Generar alineación" button runs `AlignStage` via `run_stage` (whisperx).

**Approval gate (VOZ-01/4):** `_approval_gate(workdir, n_slides)` calls `audio_gate_ready()` — disabled until all slides have audio AND `voice.json` has valid word-level timestamps.

## Checkpoint: Auto-Approved (Unattended Run)

The `checkpoint:human-verify` task was auto-approved per unattended execution mode.

## Deferred Items

**DEFERRED: Live browser verification of Phase 4 Voz UI**

Manual steps to perform when next running the studio interactively:
1. `uv run avideo studio` → navigate to Phase 4
2. Confirm three radio options appear: ElevenLabs / OpenAI Audio / Grabaciones propias
3. ElevenLabs: check voice_id text input; OpenAI: check voice/model selectors
4. Click "Generar voz" — confirm button disables, progress message appears
5. If API keys available: confirm per-slide st.audio previews after synthesis
6. Switch to "Grabaciones propias": upload a WAV, click "Mejorar audio", confirm BEFORE/AFTER comparison; click "Adoptar"
7. Confirm "Aprobar voz" button is disabled with no audio/timings; enables after synthesis
8. Navigate back to Phase 3 — confirm no regression

## Deviations from Plan

None — plan executed exactly as written. All required functions (`rerun_voice`, `write_uploaded_audio`, `audio_gate_ready`, `enhance_audio`) already existed in pipeline_ops and audio_enhance; no backend changes were needed.

## Known Stubs

None — render(workdir)->bool returns a real gate condition. The placeholder `st.toggle` and `st.info` stubs are completely replaced.

## Threat Flags

No new threat surface introduced. File write path uses `write_uploaded_audio` (already path-traversal guarded by T-12-02-01). `enhance_audio` same-path guard (T-12-03-04) is enforced by computing `slide_{i:02d}_enhanced.mp3` ≠ `slide_{i:02d}.mp3`.

## Verification Results

```
grep -c "st.radio|st.audio|st.file_uploader|rerun_voice|enhance_audio|audio_gate_ready" = 25 (>= 6 required)
grep -c "Marcar esta fase como lista" = 0 (placeholder gone)
uv run pytest tests/ -q: 381 passed, 5 warnings in 3.63s (0 failures)
```

## Self-Check: PASSED

- src/avideo/ui/pages/phase_4_voz.py: EXISTS (280+ lines, syntax OK)
- Commit 3cb9b1d: EXISTS
- 381 tests passing: CONFIRMED
- Placeholder toggle removed: CONFIRMED
- render(workdir)->bool signature: CONFIRMED
