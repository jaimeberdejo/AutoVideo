---
gsd_state_version: 1.0
milestone: v2.0.0
milestone_name: Studio Guiado
status: verifying
stopped_at: Completed 08-03-PLAN.md
last_updated: "2026-05-29T14:56:07.290Z"
last_activity: 2026-05-29
progress:
  total_phases: 6
  completed_phases: 2
  total_plans: 9
  completed_plans: 9
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-29)

**Core value:** A partir de unos bullets + una duración, obtener un vídeo narrado coherente y de alta calidad (slides + voz + subtítulos sincronizados) sin intervención manual obligatoria, con checkpoints opcionales de supervisión.
**Current focus:** Phase 9 — UI Foundation

## Current Position

Phase: 9 (UI Foundation) — EXECUTING
Plan: 4 of 4
Status: Phase complete — ready for verification
Last activity: 2026-05-29

```
Progress: [██████████] 100%
```

## Performance Metrics

**Velocity (v1.60.0 baseline):**

- Total plans completed: 18
- Average duration: — min
- Total execution time: 0.0 hours

**By Phase (v2.0.0):**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 8. Backend Integrations | - | - | - |
| 9. UI Foundation | - | - | - |
| 10. Contenido Page | - | - | - |
| 11. Guion + Slides Pages | - | - | - |
| 12. Voz Page | - | - | - |
| 13. Extras + Ensamblaje + Polish | - | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 08-backend-integrations P01 | 5 | 2 tasks | 3 files |
| Phase 08 P02 | 126 | - tasks | - files |
| Phase 08-backend-integrations P03 | 233 | 2 tasks | 3 files |
| Phase 08 P08-05 | 4 | 2 tasks | 3 files |
| Phase 09-ui-foundation P09-01 | 128 | 3 tasks | 3 files |
| Phase 09-ui-foundation P09-02 | 180 | 2 tasks | 3 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work (v2.0.0):

- **UI framework:** Streamlit (local, single-user) — rapidez de implementación, todo en Python; no FastAPI+frontend
- **Backend before UI:** Phase 8 builds all new backend integrations independently testable before any Streamlit code
- **PipelineBridge pattern:** background thread + `@st.fragment(run_every="2s")` polling of done markers — never call st.* from a thread
- **workdir is sole source of truth:** `session_state` holds only `workdir_path` (str) and `phase` (int); all pipeline artifacts read from workdir/*.json on every rerun
- **OpenAI Audio STT round-trip:** OpenAI TTS returns no timestamps; mandatory whisper-1 STT round-trip for word-level timestamps; OPENAI_API_KEY in .env
- **Audio enhancement:** FFmpeg-only (`afftdn=nr=6:nf=-25` + `loudnorm`); no noisereduce/pedalboard; alignment always on original unprocessed audio
- **Background music:** `amix=inputs=2:normalize=0` always; loudnorm single pass on final mix only when music present; per-narration loudnorm skipped when bg_music set
- **File upload:** write to workdir immediately on receipt (Streamlit discards UploadedFile on next rerun if not written)
- **invalidate_downstream:** implement in WorkdirManager before building any editable widget; deletes done markers for all stages after a given stage
- [Phase ?]: Wave 0 scaffold — deferred imports allow 21 tests to collect before implementation modules exist
- [Phase ?]: Mock seam for OpenAI integration is _get_client (lazy singleton) — mirrors elevenlabs pattern for import-safety
- [Phase ?]: All new RunConfig fields use Optional/defaults — backward-compatible with 303 tests
- [Phase ?]: openai>=2.38.0 in core deps; python-dotenv promoted from dev to core
- [Phase ?]: transcribe_slide_openai passes Path directly to SDK (no open()) — mock seam works without real file on disk; OpenAI SDK accepts Path objects
- [Phase ?]: whisper-1 hard-coded in transcribe_slide_openai — gpt-4o-transcribe lacks word timestamps (T-08-03-04 / Pitfall 17)
- [Phase ?]: Single-pass loudnorm when music present

### Pending Todos

- Plan Phase 8 when roadmap approved

### Blockers/Concerns

Carried forward from v1.60.0 (non-blocking):

- WPM efectivo de ElevenLabs en español es estimado (150); requiere calibración empírica
- FFmpeg `arnndn` requiere archivo modelo `.rnnn`; usar `afftdn` como default (no model file needed)
- `whisper-1` quality for Spanish word timestamps: acceptable but not perfect; fallback = WhisperX (already in [record] optional group)
- `fcntl.flock` for workdir lockfile is Unix/macOS only — acceptable for v2.0.0 target (macOS + Docker/Linux)

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| v2.x | Export .pptx (python-pptx) from UI | Deferred | v2.0.0 planning |
| v2.x | Project history / multiple workdir management | Deferred | v2.0.0 planning |
| v2.x | theme.yaml visual editor (color picker) | Deferred | v2.0.0 planning |
| Later | Salida 9:16 vertical | Deferred | Init |
| Later | Sobreescritura theme.yaml con marca propia | Deferred | Init |
| Later | Música de librería libre incluida en el repo | Deferred | v2.0.0 planning |
| Later | Modo multi-usuario / hosteado con autenticación | Deferred | v2.0.0 planning |

## Session Continuity

Last session: 2026-05-29T14:56:07.287Z
Stopped at: Completed 08-03-PLAN.md
Resume file: None
