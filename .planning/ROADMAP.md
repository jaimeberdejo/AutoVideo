# Roadmap: Auto Video Narrado

## Milestones

- ✅ **v1.60.0 MVP Pipeline** — Phases 1–7 (shipped 2026-05-29) — see [milestones/v1.60.0-ROADMAP.md](milestones/v1.60.0-ROADMAP.md)
- 📋 **Next — Media en `auto`** — Phases 8–9 (planned)

## Overview

Pipeline CLI en Python que transforma bullets + duración en un vídeo narrado (slides 1080p, voz ElevenLabs, subtítulos SRT/VTT, montaje FFmpeg). La construcción siguió un orden estrictamente bottom-up: fundación (orquestador + modelos Pydantic + CLI) → etapas LLM → render de slides → voz y subtítulos → montaje final → modos avanzados (hybrid/manual + verificador) → empaquetado. El siguiente milestone añade soporte para medios del usuario (capturas y clips de vídeo) en modo `auto`.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

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

### 📋 Next Milestone — Media en `auto` (Planned)

- [ ] **Phase 8: Screenshot Support (auto mode)** — `visual_type: screenshot` + `image_path`/`caption` en SlideSpec + plantilla Jinja para imagen del usuario + extensión de bullets.yaml `{text, image}`
- [ ] **Phase 9: Video Clip Support (auto mode)** — `visual_type: video` + `video_path` para clips .mp4 del usuario; duración del clip dicta la del slide; audio original silenciado + narración superpuesta; hold-last-frame si la narración excede

## Phase Details

### Phase 8: Screenshot Support (auto mode)
**Goal**: En modo `auto`, los usuarios pueden insertar sus propias capturas de pantalla como contenido de slide vía `visual_type: screenshot`, con encuadre y caption opcional siguiendo el `theme.yaml`, sin tener que cambiar a modo `hybrid`/`manual`
**Depends on**: Phase 3, Phase 7
**Requirements**: SLIDE-06, SLIDE-07
**Success Criteria** (what must be TRUE):
  1. Un item de `bullets.yaml` con forma `{text: "...", image: "ruta/captura.png"}` genera un slide cuyo `visual_type` es `screenshot` y cuyo PNG renderizado contiene la imagen del usuario encuadrada a 1920×1080
  2. La imagen del usuario se ajusta dentro del canvas (fit-inside + padding del color de fondo del tema); imágenes mayores se reescalan con calidad, menores se centran sin upscaling agresivo
  3. Un `caption` opcional en el item se renderiza como subtítulo del slide con la tipografía/colores del tema
  4. Si `image` apunta a un fichero inexistente, el pipeline falla con un error claro indicando ruta y slide_index (no se cae silenciosamente)
  5. El downstream (voice/timing/subs/assemble) trata estos slides idénticos a cualquier otro PNG — sin cambios necesarios aguas abajo
**Plans**: TBD

Plans:
- [ ] 08-01: Extender modelos + schema (visual_type screenshot, image_path/caption en SlideSpec, soporte `{text,image}` en bullets.yaml) + plantilla Jinja + integración en slides_auto + tests
**UI hint**: no

### Phase 9: Video Clip Support (auto mode)
**Goal**: En modo `auto`, los usuarios pueden insertar clips de vídeo (.mp4) cortos como slide; el clip dicta la duración del slide, la narración se calibra para encajar en ella, el audio original del clip se silencia y la narración se reproduce por encima; si la narración excede la duración del clip, se mantiene el último frame para extender
**Depends on**: Phase 3, Phase 5, Phase 8
**Requirements**: VIDEO-01, VIDEO-02, VIDEO-03, VIDEO-04
**Success Criteria** (what must be TRUE):
  1. Un item de `bullets.yaml` con forma `{text: "...", video: "ruta/clip.mp4"}` genera un slide con `visual_type: video` y el clip se integra en el output final con la narración superpuesta
  2. La duración del slide en el timeline final es `max(duration(clip), duration(narration))`; si narración > clip se mantiene el último frame del vídeo extendido (no se cicla, no se acelera)
  3. El word-budget del scriptwriter para slides de vídeo se deriva de `wpm × duration(clip) / 60` (no del reparto por densidad) — la narración se ajusta al clip por defecto
  4. El audio original del clip se silencia en el output final; solo se oye la narración (y la pista normalizada con loudnorm)
  5. FFmpeg normaliza cada clip a 1920×1080 H.264 yuv420p durante ingesta y los concatena con las slides de imagen en un único timeline; los crossfades (`xfade`/`acrossfade`) funcionan en transiciones imagen↔vídeo, vídeo↔vídeo, vídeo↔imagen
  6. Los subtítulos `.srt`/`.vtt` se sincronizan con la línea de tiempo final (incluyendo el offset acumulado de slides de vídeo)
  7. El verificador (en hybrid/manual) salta los slides de vídeo retornando `ok` automáticamente — la auditoría visión-en-frame único no es representativa de un clip
**Plans**: TBD

Plans:
- [ ] 09-01: Modelos + schema (visual_type video, video_path en SlideSpec, soporte `{text,video}` en bullets.yaml) + ingest/normalize en integrations/ffmpeg.py (probe duration + re-encode a 1920×1080 H.264 yuv420p si necesario) + extender plantilla Jinja stub (placeholder en HTML render) + tests unitarios
- [ ] 09-02: Calibración del scriptwriter para slides de vídeo (override del word-budget desde clip duration) + extender AssembleStage para integrar clips en el filtergraph con hold-last-frame, silenciar audio original, mantener loudnorm sobre la pista de narración + tests end-to-end del orquestador
**UI hint**: no

## Progress

**Execution Order:**
Next phases execute in numeric order: 8 → 9

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation | v1.60.0 | 3/3 | Complete | 2026-05-25 |
| 2. LLM Pipeline | v1.60.0 | 3/3 | Complete | 2026-05-25 |
| 3. Slides Auto | v1.60.0 | 2/2 | Complete | 2026-05-25 |
| 4. Voz + Subtítulos | v1.60.0 | 3/3 | Complete | 2026-05-25 |
| 5. Montaje + QA | v1.60.0 | 2/2 | Complete | 2026-05-26 |
| 6. Slides Hybrid/Manual + Verificador | v1.60.0 | 2/2 | Complete | 2026-05-26 |
| 7. Empaquetado + Tests + Docs | v1.60.0 | 3/3 | Complete | 2026-05-26 |
| 8. Screenshot Support (auto mode) | Next | 0/1 | Not started | - |
| 9. Video Clip Support (auto mode) | Next | 0/2 | Not started | - |
