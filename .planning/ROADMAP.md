# Roadmap: Auto Video Narrado

## Milestones

- ✅ **v1.60.0 MVP Pipeline** — Phases 1–7 (shipped 2026-05-29) — see [milestones/v1.60.0-ROADMAP.md](milestones/v1.60.0-ROADMAP.md)
- 🚧 **v2.0.0 Studio Guiado** — Phases 8–13 (in progress)

## Overview

Pipeline CLI en Python que transforma bullets + duración en un vídeo narrado (slides 1080p, voz ElevenLabs, subtítulos SRT/VTT, montaje FFmpeg). El MVP (Phases 1–7) está enviado y archivado. v2.0.0 añade una UI Streamlit local que guía las 6 fases de creación con validación humana obligatoria entre fases, orquestando el pipeline existente como motor headless.

## Phases

<details>
<summary>✅ v1.60.0 MVP Pipeline (Phases 1–7) — SHIPPED 2026-05-29</summary>

- [x] **Phase 1: Foundation** — Orquestador secuencial + CLI typer + modelos Pydantic + WorkdirManager + niveles L1-L4 (completed 2026-05-25)
- [x] **Phase 2: LLM Pipeline** — Ingesta de contexto + Storyboard (Claude) + Director de timing + Guionista (Claude) (completed 2026-05-25)
- [x] **Phase 3: Slides Auto** — Jinja2 + Playwright → PNG 1920×1080 + theme.yaml + iconos SVG offline (modo `auto`) (completed 2026-05-25)
- [x] **Phase 4: Voz + Subtítulos** — ElevenLabs TTS con timestamps + modo record + WhisperX + SRT/VTT (completed 2026-05-25)
- [x] **Phase 5: Montaje + QA** — FFmpeg concat + crossfade + loudnorm + quemado de subtítulos + informe QA (completed 2026-05-26)
- [x] **Phase 6: Slides Hybrid/Manual + Verificador** — Propuesta de diseño + ingesta de slides + verificador Claude Vision (completed 2026-05-26)
- [x] **Phase 7: Empaquetado + Tests + Docs** — pyproject.toml/uv + Dockerfile + pytest + README (completed 2026-05-26)

Full phase detail: [milestones/v1.60.0-ROADMAP.md](milestones/v1.60.0-ROADMAP.md)

</details>

### 🚧 v2.0.0 Studio Guiado (Phases 8–13)

- [ ] **Phase 8: Backend Integrations** — OpenAI Audio TTS + STT round-trip + audio enhancement + background music FFmpeg pipeline
- [ ] **Phase 9: UI Foundation** — Streamlit shell + PipelineBridge + state model + invalidate_downstream + workdir reconstruction
- [ ] **Phase 10: Contenido Page** — Fase 1 wizard: intake de tema + duración + auto-generación de bullets + gate de aprobación
- [ ] **Phase 11: Guion + Slides Pages** — Fases 2 y 3 wizard: guion editable + variaciones + slides interactivas + verificador QC
- [ ] **Phase 12: Voz Page** — Fase 4 wizard: selección de proveedor de narración + previews de audio + gate de aprobación
- [ ] **Phase 13: Extras + Ensamblaje + Polish** — Fases 5–6 wizard: extras + montaje final + preview/descarga + packaging y tests

## Phase Details

### Phase 8: Backend Integrations
**Goal**: Las tres nuevas capacidades de backend (OpenAI Audio TTS, mejora de audio, música de fondo) están implementadas, testeadas e integradas en el pipeline existente sin romper los 303 tests actuales
**Depends on**: Phase 7 (v1.60.0 complete pipeline)
**Requirements**: VOZ-02, VOZ-03, EXT-02, EXT-03
**Success Criteria** (what must be TRUE):
  1. El pipeline puede sintetizar voz con OpenAI Audio y produce `timings.json` con word-level timestamps (via whisper-1 STT round-trip) indistinguibles del formato de ElevenLabs/WhisperX
  2. El comando de mejora de audio (`enhance_audio`) aplica denoise + loudnorm sobre un archivo de entrada y produce un archivo de salida mejorado sin modificar el original
  3. El pipeline puede montar un vídeo con música de fondo (ducking + fade) usando una sola pasada loudnorm sobre la mezcla final; la narración mantiene su LUFS objetivo
  4. Los 303 tests previos siguen pasando; los nuevos módulos tienen cobertura de tests unitarios (stub de OpenAI, mock de FFmpeg subprocess)
**Plans**: TBD

### Phase 9: UI Foundation
**Goal**: La app Streamlit arranca con `avideo studio`, muestra un wizard de 6 fases navegable, reconstruye el estado desde `workdir/` en refresco de página, y ejecuta etapas largas sin bloquear la UI
**Depends on**: Phase 8
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07
**Success Criteria** (what must be TRUE):
  1. `avideo studio` abre el navegador en `localhost:8501` con un wizard de 6 fases; el stepper visual muestra la fase activa y las completadas
  2. El wizard no permite avanzar de fase sin que el usuario pulse "Aprobar" explícitamente; al retroceder aparece un diálogo de confirmación e invalida los checkpoints aguas abajo
  3. Al cerrar y reabrir el navegador con el mismo workdir, el wizard retoma exactamente la fase y estado donde se dejó (la UI se reconstruye desde `workdir/*.json`, no desde `session_state`)
  4. Una etapa larga (p. ej. render de slides) lanzada via bridge muestra progreso en tiempo real sin congelar la UI; el usuario puede interactuar con otros widgets mientras la etapa corre en background
  5. El CLI `avideo generate` sigue funcionando exactamente igual que en v1.60.0 (headless); la UI invoca las etapas existentes directamente sin reescribir el pipeline
**Plans**: TBD
**UI hint**: yes

### Phase 10: Contenido Page
**Goal**: El usuario puede introducir su tema y duración, y obtener bullets (propios o auto-generados por Claude) que aprueba antes de continuar
**Depends on**: Phase 9
**Requirements**: CNT-01, CNT-02, CNT-03
**Success Criteria** (what must be TRUE):
  1. El usuario puede escribir un tema y una duración objetivo y la UI los acepta con validación (duración mínima/máxima razonable)
  2. El usuario puede elegir entre escribir sus propios bullets o pedirle a la app que los genere desde el tema; ambas rutas terminan en el mismo editor
  3. Los bullets generados por Claude aparecen en un editor interactivo donde el usuario puede modificarlos, añadir o eliminar filas, y aprobar; al aprobar se persiste `workdir/bullets.yaml` y el wizard avanza a Fase 2
**Plans**: TBD
**UI hint**: yes

### Phase 11: Guion + Slides Pages
**Goal**: El usuario puede revisar y aprobar el guion slide a slide (con edición inline y variaciones) y las diapositivas generadas (con thumbnails, badges de QC y la opción de subir las suyas)
**Depends on**: Phase 10
**Requirements**: SCR-01, SCR-02, SCR-03, SCR-04, SLD-01, SLD-02, SLD-03
**Success Criteria** (what must be TRUE):
  1. Al entrar en Fase 2, el sistema genera automáticamente storyboard + timing + guion via bridge; el usuario ve un spinner por etapa y el guion aparece slide a slide al completarse
  2. El usuario puede editar el texto de cualquier slide directamente en la UI; los cambios se persisten en el checkpoint y los checkpoints aguas abajo se invalidan automáticamente
  3. El usuario puede pedir una variación del guion completo (o por slide); el bridge relanza solo la etapa scriptwriter, no todo el pipeline
  4. Al entrar en Fase 3, el usuario elige modo `auto` (la app genera slides) o subir las suyas; en modo auto, los thumbnails PNG aparecen al completarse el render con badges ok/warning/fail del verificador
  5. El usuario puede solicitar variaciones de slides en modo auto; en modo upload, el verificador Claude Vision muestra un informe por slide y permite re-subir antes de aprobar
**Plans**: TBD
**UI hint**: yes

### Phase 12: Voz Page
**Goal**: El usuario puede elegir su proveedor de narración (ElevenLabs, OpenAI Audio o grabaciones propias), escuchar previews por slide y aprobar el audio antes de continuar
**Depends on**: Phase 11
**Requirements**: VOZ-01
**Success Criteria** (what must be TRUE):
  1. La Fase 4 muestra tres opciones de proveedor (ElevenLabs, OpenAI Audio, grabación propia) y el usuario puede seleccionar y configurar cualquiera de las tres sin errores
  2. Para ElevenLabs y OpenAI Audio, la síntesis corre via bridge y al completarse aparece un widget `st.audio` reproducible por cada slide
  3. Para grabaciones propias, el usuario puede subir un archivo de audio por slide; al subir, el archivo se escribe a `workdir/` inmediatamente (no se pierde en el siguiente rerun); el botón de mejora automática produce un preview comparativo antes de confirmar
  4. El gate de aprobación de Fase 4 solo se desbloquea cuando todos los slides tienen audio y `timings.json` contiene word-level timestamps válidos
**Plans**: TBD
**UI hint**: yes

### Phase 13: Extras + Ensamblaje + Polish
**Goal**: El usuario puede configurar extras opcionales (subtítulos, música de fondo, transiciones), montar el vídeo final y descargarlo desde la UI; la app está empaquetada y testeada
**Depends on**: Phase 12
**Requirements**: EXT-01, ASM-01, ASM-02
**Success Criteria** (what must be TRUE):
  1. La Fase 5 permite activar/desactivar subtítulos quemados, subir una pista de música de fondo (con slider de volumen y preview), y configurar el crossfade; al aprobar, la configuración queda en `session_state["run_config"]`
  2. La Fase 6 monta el vídeo automáticamente via bridge integrando todos los extras configurados; el progreso de FFmpeg se muestra en tiempo real sin congelar la UI
  3. Al completarse el montaje, aparece un player de vídeo reproducible en la UI y un botón de descarga del `output.mp4`; el informe QA (desviación de duración + LUFS) queda visible
  4. `avideo studio` es un entry point instalable en `pyproject.toml`; la app arranca con `avideo studio` o `streamlit run`; el Dockerfile expone el puerto 8501 y arranca la UI en modo headless
  5. Los tests del bridge (thread launch, done-marker detection, `invalidate_downstream`) y smoke tests de las páginas de fase pasan junto a los 303 tests previos
**Plans**: TBD
**UI hint**: yes

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation | v1.60.0 | 3/3 | Complete | 2026-05-25 |
| 2. LLM Pipeline | v1.60.0 | 3/3 | Complete | 2026-05-25 |
| 3. Slides Auto | v1.60.0 | 2/2 | Complete | 2026-05-25 |
| 4. Voz + Subtítulos | v1.60.0 | 3/3 | Complete | 2026-05-25 |
| 5. Montaje + QA | v1.60.0 | 2/2 | Complete | 2026-05-26 |
| 6. Slides Hybrid/Manual + Verificador | v1.60.0 | 2/2 | Complete | 2026-05-26 |
| 7. Empaquetado + Tests + Docs | v1.60.0 | 3/3 | Complete | 2026-05-26 |
| 8. Backend Integrations | v2.0.0 | 0/- | Not started | - |
| 9. UI Foundation | v2.0.0 | 0/- | Not started | - |
| 10. Contenido Page | v2.0.0 | 0/- | Not started | - |
| 11. Guion + Slides Pages | v2.0.0 | 0/- | Not started | - |
| 12. Voz Page | v2.0.0 | 0/- | Not started | - |
| 13. Extras + Ensamblaje + Polish | v2.0.0 | 0/- | Not started | - |
