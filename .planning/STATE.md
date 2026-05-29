---
gsd_state_version: 1.0
milestone: v2.0.0
milestone_name: Studio Guiado
status: roadmap_ready
last_updated: "2026-05-29"
last_activity: 2026-05-29
progress:
  total_phases: 6
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-29)

**Core value:** A partir de unos bullets + una duración, obtener un vídeo narrado coherente y de alta calidad (slides + voz + subtítulos sincronizados) sin intervención manual obligatoria, con checkpoints opcionales de supervisión.
**Current focus:** v2.0.0 Studio Guiado — roadmap listo, Phase 8 es la siguiente

## Current Position

Phase: Phase 8 — Backend Integrations (not started)
Plan: —
Status: Roadmap ready; awaiting plan phase
Last activity: 2026-05-29 — Roadmap v2.0.0 created (Phases 8–13)

```
Progress: [░░░░░░░░░░░░░░░░░░░░] 0% (0/6 phases)
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

Last session: 2026-05-29
Stopped at: Roadmap v2.0.0 created; ready for `/gsd-plan-phase 8`
Resume file: None
