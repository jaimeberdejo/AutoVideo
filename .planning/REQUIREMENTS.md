# Requirements: Auto Video Narrado — Next Milestone (Media en `auto`)

**Defined:** 2026-05-29 (carried forward at v1.60.0 close)
**Core Value:** A partir de unos bullets + una duración, obtener un vídeo narrado coherente y de alta calidad (slides + voz + subtítulos sincronizados) sin intervención manual obligatoria, con checkpoints opcionales de supervisión.

> El milestone v1.60.0 (Phases 1–7) está enviado — sus requisitos están
> archivados en `milestones/v1.60.0-REQUIREMENTS.md`. Este archivo recoge el
> alcance del siguiente milestone: insertar medios del usuario (capturas y
> clips de vídeo) directamente en modo `auto`.

## Requirements

Requisitos del siguiente release. Cada uno se mapea a fases del roadmap.

### SLIDE — Capturas de pantalla en `auto` (Phase 8)

- [ ] **SLIDE-06**: En modo `auto`, soporta `visual_type: screenshot` con `image_path` y `caption` opcional — el slide renderiza la imagen del usuario dentro de un marco con tipografía y colores del tema (fit-inside + padding)
- [ ] **SLIDE-07**: `bullets.yaml` acepta items tanto string (actual) como `{text: ..., image: <path>}`; cuando `image` está presente, el storyboard usa `visual_type: screenshot` para ese slide

### VIDEO — Clips de vídeo en slides (Phase 9)

- [ ] **VIDEO-01**: En modo `auto`, soporta `visual_type: video` con `video_path` para insertar clips .mp4 cortos del usuario como contenido de slide
- [ ] **VIDEO-02**: La duración del clip de vídeo dicta la duración del slide en el timeline; el scriptwriter calibra la narración para encajar dentro de `wpm × duration(clip) / 60` palabras (overrides timing-director allocation)
- [ ] **VIDEO-03**: El audio original del clip se silencia en el output final; la narración se superpone; si la narración excede la duración del clip se mantiene el último frame para extender (no se cicla, no se acelera)
- [ ] **VIDEO-04**: FFmpeg normaliza cada clip a 1920×1080 H.264 yuv420p durante ingesta y los concatena con slides de imagen en un único timeline con crossfades funcionando en todas las transiciones (imagen↔vídeo, vídeo↔vídeo, vídeo↔imagen)

## v2 / Later Requirements

Diferidos a futuro. Reconocidos pero fuera del roadmap actual.

### Export y formatos

- **EXPORT-01**: Exportación de slides a `.pptx` con `python-pptx` (opción secundaria)
- **FMT-01**: Salida 9:16 vertical (formato social) con plantillas adaptadas
- **BRAND-01**: Sobreescritura del `theme.yaml` con marca propia (paleta/tipografías/logo)

## Out of Scope

Excluido explícitamente. Documentado para evitar scope creep.

| Feature | Razón |
|---------|-------|
| Generación de imágenes con IA | Solo iconos SVG y gráficos por código (control y consistencia visual) |
| Bancos de imágenes / stock | Visuales 100% reproducibles y editables |
| Orquestadores visuales (n8n) | Se quiere orquestador propio en Python, simple |
| Frameworks de agentes (LangGraph) | Innecesario para un pipeline lineal (DAG secuencial) |
| MoviePy | Se usa FFmpeg directo por rendimiento y control |
| Partir de un `.pptx` existente como flujo principal | El workflow genera las slides; ingesta solo en hybrid/manual |
| Avatares / lip-sync (p. ej. Wav2Lip) | Modelos pesados; resuelven un problema distinto |

## Traceability

Qué fases cubren qué requisitos.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SLIDE-06 | Phase 8 | Pending |
| SLIDE-07 | Phase 8 | Pending |
| VIDEO-01 | Phase 9 | Pending |
| VIDEO-02 | Phase 9 | Pending |
| VIDEO-03 | Phase 9 | Pending |
| VIDEO-04 | Phase 9 | Pending |

**Coverage:**
- Next-milestone requirements: 6 total
- Mapped to phases: 6
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-25; rescoped to next milestone 2026-05-29 after v1.60.0 close*
