# Requirements: Auto Video Narrado — v2.0.0 Studio Guiado

**Defined:** 2026-05-29
**Core Value:** A partir de unos bullets + una duración, obtener un vídeo narrado coherente y de alta calidad (slides + voz + subtítulos sincronizados) sin intervención manual obligatoria, con checkpoints opcionales de supervisión.

> Milestone v2.0.0: una UI Streamlit local que guía las 6 fases de creación
> del vídeo con validación humana obligatoria entre fases, orquestando el
> pipeline existente (v1.60.0) como motor headless. El pipeline NO se reescribe.
> Requisitos de v1.60.0 archivados en `milestones/v1.60.0-REQUIREMENTS.md`.

## v2.0.0 Requirements

### UI — Wizard Streamlit y orquestación

- [ ] **UI-01**: El usuario lanza la UI (p. ej. `avideo studio`) y se abre un wizard local de 6 fases en el navegador
- [ ] **UI-02**: Entre cada fase hay un gate de validación humana — el wizard no avanza hasta que el usuario confirma explícitamente
- [ ] **UI-03**: El usuario puede retroceder a una fase anterior; al editar o regenerar, los checkpoints aguas abajo se invalidan (no se muestran resultados desincronizados)
- [ ] **UI-04**: El estado del wizard se reconstruye desde los checkpoints de `workdir/` (sobrevive a refrescos/cierres del navegador); `session_state` solo guarda el workdir y la fase actual
- [ ] **UI-05**: Las etapas largas (render de slides, TTS, montaje) se ejecutan sin bloquear la UI y muestran progreso hasta completarse
- [ ] **UI-06**: La UI muestra previews en vivo: bullets, guion por slide, thumbnails de slides y el vídeo final reproducible/descargable
- [ ] **UI-07**: El CLI `generate` se conserva como motor headless; la UI invoca las etapas existentes sin reescribir el pipeline

### CNT — Fase 1 Contenido

- [ ] **CNT-01**: El usuario introduce el tema y la duración objetivo del vídeo
- [ ] **CNT-02**: El usuario elige aportar sus propios bullets o que la app los genere desde el tema (Claude)
- [ ] **CNT-03**: Los bullets generados se muestran para aprobar o editar antes de continuar

### SCR — Fase 2 Guion

- [ ] **SCR-01**: A partir de la duración, el sistema deriva el nº de slides y genera el guion por slide (reusa storyboard + timing + scriptwriter)
- [ ] **SCR-02**: El usuario puede editar directamente el texto del guion de cualquier slide en la UI
- [ ] **SCR-03**: El usuario puede pedir variaciones del guion (regenerar con Claude) e iterar hasta dar el visto bueno
- [ ] **SCR-04**: Al aprobar, el guion editado se persiste como checkpoint e invalida las etapas aguas abajo si cambió

### SLD — Fase 3 Diapositivas

- [ ] **SLD-01**: El usuario elige que la app genere las slides (modo `auto`) o subir las suyas siguiendo el esquema definido (orden, contenido, nº de slides)
- [ ] **SLD-02**: Si las genera la app, el usuario puede revisarlas, editar/regenerar y pedir variaciones, iterando hasta aprobar
- [ ] **SLD-03**: Si las sube el usuario, el verificador Claude Vision ejecuta un control de calidad por slide (ok/warning/fail) avisando de discrepancias con el esquema/guion; el usuario puede re-subir

### VOZ — Fase 4 Voz

- [ ] **VOZ-01**: El usuario elige el proveedor de narración: ElevenLabs, OpenAI Audio (nuevo) o subir sus propias grabaciones
- [ ] **VOZ-02**: OpenAI Audio sintetiza la voz por slide; como no entrega timestamps, se hace un round-trip STT (`whisper-1`, word-level) para mantener subtítulos sincronizados
- [ ] **VOZ-03**: Para audios subidos por el usuario, un botón aplica mejora automática (denoise + normalización, FFmpeg) con preview no destructivo antes de aplicar; la alineación de subtítulos usa el audio original sin procesar

### EXT — Fase 5 Extras

- [ ] **EXT-01**: El usuario elige qué extras añadir: subtítulos, transiciones, música de fondo
- [ ] **EXT-02**: El usuario aporta una pista de música de fondo (archivo) que se mezcla bajo la narración con ducking + fade in/out
- [ ] **EXT-03**: La música no degrada el loudness de la narración — una sola pasada loudnorm sobre la mezcla final (`amix normalize=0` + volumen explícito; fade desde la duración real medida por ffprobe)

### ASM — Fase 6 Ensamblaje

- [ ] **ASM-01**: El sistema monta el vídeo final automáticamente sincronizando cada audio con su slide e integrando voz + extras seleccionados
- [ ] **ASM-02**: El vídeo final se muestra en la UI para reproducir y descargar; el informe QA (desviación de duración + LUFS) queda disponible

## Later Requirements

Diferidos a futuro. Reconocidos pero fuera del roadmap actual.

### Export y formatos

- **EXPORT-01**: Exportación de slides a `.pptx` con `python-pptx` (opción secundaria)
- **FMT-01**: Salida 9:16 vertical (formato social) con plantillas adaptadas
- **BRAND-01**: Sobreescritura del `theme.yaml` con marca propia (paleta/tipografías/logo)

### UI / multimedia (futuro)

- **MUS-LIB-01**: Librería de música libre incluida en el repo (además del archivo del usuario) — requiere decidir licencias/almacenamiento
- **UI-MULTI-01**: Modo multi-usuario / hosteado con autenticación (hoy: local single-user)

## Out of Scope

Excluido explícitamente. Documentado para evitar scope creep.

| Feature | Razón |
|---------|-------|
| Generación de imágenes con IA | Solo iconos SVG y gráficos por código (control y consistencia visual) |
| Bancos de imágenes / stock | Visuales 100% reproducibles y editables |
| Frontend JS pesado (React/Next) | Se elige Streamlit por rapidez y mantener todo en Python |
| `noisereduce` / `pedalboard` para mejora de audio | FFmpeg (`afftdn`/`loudnorm`) cubre el caso sin deps compiladas nuevas |
| MoviePy | Se usa FFmpeg directo por rendimiento y control |
| Orquestadores visuales (n8n) / agentes (LangGraph) | Orquestador propio en Python; la UI es una capa fina sobre etapas existentes |
| Avatares / lip-sync | Modelos pesados; problema distinto |

## Traceability

Qué fases cubren qué requisitos. (Vacío — lo rellena el roadmap.)

| Requirement | Phase | Status |
|-------------|-------|--------|
| _pendiente_ | — | — |

**Coverage:**
- v2.0.0 requirements: 22 total
- Mapped to phases: 0 (pending roadmap)

---
*Requirements defined: 2026-05-29 for milestone v2.0.0 Studio Guiado*
