---
gsd_state_version: 1.0
milestone: v2.0.0
milestone_name: Studio Guiado
current_phase: 0.0
current_phase_name: 8–13
status: uat_in_progress
stopped_at: context exhaustion at 75% (2026-07-01)
last_updated: "2026-07-01T19:16:56.610Z"
progress:
  total_phases: 6
  completed_phases: 6
  total_plans: 23
  completed_plans: 23
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-29)

**Core value:** A partir de unos bullets + una duración, obtener un vídeo narrado coherente y de alta calidad (slides + voz + subtítulos sincronizados) sin intervención manual obligatoria, con checkpoints opcionales de supervisión.
**Current focus:** v2.0.0 — UAT en navegador + cierre. Próximo trabajo planificado: SEED-002 (variación dirigida).

## Current Position

Phase: v2.0.0 todas las fases (8–13) completas + audit PASSED. En UAT manual.
Plan: —
Status: Paused for fresh-context planning of SEED-002

### Handoff (2026-05-31) — retomar tras /clear

**Hecho esta sesión (todo en master, 398→419 tests verdes):**

- v2.0.0 fases 8–13 completas; `/gsd-audit-milestone` → gaps_found (3 blockers integración) → fixed + verificado → **PASSED** (`.planning/v2.0.0-MILESTONE-AUDIT.md`).
- Fixes de UAT en la UI: bullets None en data_editor; duración mm:ss (parse_duration); "+" del editor estable; **cuelgues de encadenado Fase 2 y Fase 3** (poll que avanza + tiempo transcurrido en vivo); nav multipágina redundante oculta (`showSidebarNavigation=false`).
- Ejemplo de prueba: `examples/demo-presupuesto/` (bullets + music_bed.mp3 + README).
- App corriendo: `uv run streamlit run src/avideo/ui/app.py` → http://localhost:8501 (parar: `lsof -ti :8501 | xargs kill`).

**Próximos pasos (en orden):**

1. **SEED-002 — variación dirigida** (Opción A elegida): implementar con contexto fresco. Ver `.planning/seeds/SEED-002-steerable-variation.md` (text_area en Fase 2/3 + feedback en prompts scriptwriter/storyboard/slides; ojo: "nº de slides" = storyboard, no solo scriptwriter; "más visual" enlaza con SEED-001/Pexels). Sugerido: `/gsd-quick` o fase corta.
2. Terminar UAT de navegador de las 6 fases (las VERIFICATION.md están como human_needed por eso).
3. Cerrar milestone: `/gsd-complete-milestone v2.0.0` → `/gsd-cleanup`.

**Pendiente del usuario (no automático):** restaurar/reconciliar `git stash`→ (ya movido a rama `feature/pexels-slides` + SEED-001). Sin remoto git → commits/tag locales.

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
| Phase 10-contenido-page P10-01 | 4 | 1 tasks | 1 files |
| Phase 10-contenido-page P10-03 | 80 | 1 tasks | 1 files |
| Phase 11-guion-slides-pages P03 | 87 | 1 tasks | 1 files |
| Phase 12-voz-page P12-01 | 1 | 1 tasks | 1 files |
| Phase 12-voz-page P12-03 | 100 | 1 tasks | 1 files |
| Phase 13-extras-ensamblaje-polish P01 | 93 | 1 tasks | 1 files |
| Phase 13-extras-ensamblaje-polish P13-03 | 5 | 1 tasks | 1 files |
| Phase 13-extras-ensamblaje-polish P13-04 | 3 | 1 tasks | 2 files |

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
- [Phase 10-03]: bullets.yaml written via Path.write_text(yaml.safe_dump()) + separate context.json via workdir.write_checkpoint; both files needed for distinct consumers (CLI engine vs shell gate)
- [Phase ?]: Wave 0 RED scaffold: deferred imports inside test bodies allow 11 tests to collect before helpers exist (mirrors Phase 11 pattern)
- [Phase ?]: Deferred imports in RED test bodies so file collects before helpers exist (mirrors Phase 11/12 pattern)
- [Phase ?]: Auto-approved human-verify checkpoint (unattended run); live studio launch deferred to manual verification

### Pending Todos

- Plan Phase 8 when roadmap approved

### Blockers/Concerns

**⚠ ACTION REQUIRED ON RETURN — your uncommitted WIP is stashed.**
Before this autonomous run, your tracked working-tree edits (`bullets.yaml`, `config.yaml`,
`src/avideo/stages/assemble.py`, `src/avideo/stages/slides_auto.py`,
`src/avideo/templates/base.html.j2`, `src/avideo/templates/macros.html.j2`) were saved to
**`git stash@{0}`** (label: `gsd-autonomous-wip-backup-2026-05-29`) so Phase 8 could rebuild
`assemble.py` cleanly. Nothing was lost. Untracked files were left in place
(`pexels.py`, `Apuntes/`, `FinFeed/`, `GUION.md`, `HANDOFF.md`, `theme.yaml`).
To recover: `git stash show -p stash@{0}` to inspect; `git stash pop` to restore
(EXPECT a conflict on `assemble.py` — Phase 8 added the music-mix Step 8.5 there;
reconcile manually or `git checkout --theirs/--ours` per hunk).

**⚠ Milestone v2.0.0 lifecycle NOT run (left for you per "ask when I come back"):**
All 6 phases (8–13) are complete + verified, 397 tests green. The close-out steps were
intentionally NOT run autonomously. When ready: `/gsd-audit-milestone` → `/gsd-complete-milestone v2.0.0` → `/gsd-cleanup`.

**Deferred manual (browser/visual) verifications** — each phase verified `human_needed`;
the automated layers all passed. Run `uv run avideo studio` and confirm:

- Phase 9: 6-phase wizard, stepper, gated continue, back-nav confirm + invalidate, resume-from-workdir on refresh.
- Phase 10: Fase 1 topic+duration, both bullet sources, data_editor, approve → bullets.yaml (then `avideo generate --bullets workdir/bullets.yaml --dry-run`).
- Phase 11: Fase 2 guion auto-run + inline edit + variation (only scriptwriter); Fase 3 slides auto thumbnails+QC badges + upload+Claude-Vision QC.
- Phase 12: Fase 4 three providers + per-slide st.audio + non-destructive enhance (before/after + Adoptar) + gate.
- Phase 13: Fase 5 extras widgets; Fase 6 "Montar vídeo" non-blocking progress → st.video + download + QA metrics. Optional: `docker build -t avideo-test .`.

Carried forward from v1.60.0 (non-blocking):

- WPM efectivo de ElevenLabs en español es estimado (150); requiere calibración empírica
- `whisper-1` quality for Spanish word timestamps: acceptable but not perfect; fallback = WhisperX (already in [record] optional group)
- `fcntl.flock` for workdir lockfile is Unix/macOS only — acceptable for v2.0.0 target (macOS + Docker/Linux)
- Code review was run on Phase 8 (2 blockers + 5 warnings fixed); deferred for the UI phases 9–13 (verifier-confirmed against code + 397 tests). Consider `/gsd-code-review` on the ui/ package on return.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260531-npu | SEED-002 — variación dirigida (text_area + selector de etapa en Fase 2/3; feedback.json → prompts; nº slides re-ejecuta storyboard; Pexels diferido a SEED-001) | 2026-05-31 | 32b300f | [260531-npu-seed-002-steerable-variation](./quick/260531-npu-seed-002-steerable-variation/) |

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

Last session: 2026-07-01T19:16:56.602Z
Stopped at: context exhaustion at 75% (2026-07-01)
Resume file: None
Next: restore/reconcile stash@{0}; run the deferred `avideo studio` browser checks; then `/gsd-audit-milestone` → `/gsd-complete-milestone v2.0.0` → `/gsd-cleanup`.
