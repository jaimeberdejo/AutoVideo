---
gsd_state_version: 1.0
milestone: v2.0.0
milestone_name: Studio Guiado
status: planning
last_updated: "2026-05-29T12:36:41.826Z"
last_activity: 2026-05-29
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-29)

**Core value:** A partir de unos bullets + una duración, obtener un vídeo narrado coherente y de alta calidad (slides + voz + subtítulos sincronizados) sin intervención manual obligatoria, con checkpoints opcionales de supervisión.
**Current focus:** v2.0.0 Studio Guiado — definiendo requisitos (UI Streamlit guiada sobre el pipeline)

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-05-29 — Milestone v2.0.0 started

## Performance Metrics

**Velocity:**

- Total plans completed: 18
- Average duration: — min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 3 | - | - |
| 2 | 3 | - | - |
| 3 | 2 | - | - |
| 4 | 3 | - | - |
| 05 | 2 | - | - |
| 06 | 2 | - | - |
| 07 | 3 | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Arquitectura: orquestador propio secuencial (no LangGraph/n8n); StageProtocol + CheckpointMixin
- Slides: sync_playwright (no async_playwright); un browser instance por run; fuentes offline
- FFmpeg: subprocess con lista de args (nunca shell=True); fluent builder en integrations/ffmpeg.py
- ElevenLabs: validar timestamps estrictamente crecientes antes de guardar checkpoint (bug #607)
- Orden de construcción: modelos Pydantic → WorkdirManager → orquestador (stubs) → LLM → Playwright → ElevenLabs → FFmpeg → WhisperX

### Pending Todos

None yet.

### Blockers/Concerns

Resolved during v1.60.0 (kept for history):

- ~~Crossfade xfade/acrossfade FFmpeg~~ — resuelto e integrado en Phase 5.
- ~~Compatibilidad torch + whisperx + pyannote.audio~~ — WhisperX/torch quedan fuera de la imagen Docker base; validar en la imagen opcional de `record`.

Open (carried forward — see PROJECT.md tech debt):

- WPM efectivo de ElevenLabs en español es estimado (150); requiere calibración empírica.

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| v2 | Export .pptx (python-pptx) | Deferred | Init |
| v2 | Salida 9:16 vertical | Deferred | Init |
| v2 | Sobreescritura theme.yaml con marca propia | Deferred | Init |

## Session Continuity

Last session: 2026-05-29
Stopped at: v1.60.0 shipped; Phases 8–9 removed from scope. No next milestone defined — use /gsd-new-milestone when ready.
Resume file: None
