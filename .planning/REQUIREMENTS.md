# Requirements: Auto Video Narrado

**Defined:** 2026-05-25
**Core Value:** A partir de unos bullets + una duración, obtener un vídeo narrado coherente y de alta calidad (slides + voz + subtítulos sincronizados) sin intervención manual obligatoria, con checkpoints opcionales de supervisión.

## v1 Requirements

Requisitos del release inicial. Cada uno se mapea a fases del roadmap.

### CLI — Interfaz de línea de comandos

- [x] **CLI-01**: El usuario puede ejecutar `generate` con `--bullets` y `--duration` y obtener un vídeo MP4 final
- [x] **CLI-02**: El usuario puede elegir la fuente de voz con `--voice {elevenlabs|record}`
- [x] **CLI-03**: El usuario puede elegir el modo de slides con `--slides-mode {auto|hybrid|manual}`
- [x] **CLI-04**: El usuario puede elegir el nivel de automatización con `--level {1..4}`
- [x] **CLI-05**: El usuario puede aportar un documento de contexto opcional con `--context`
- [x] **CLI-06**: El usuario puede ejecutar `--dry-run` para estimar tokens/coste y duración sin generar audio/vídeo
- [x] **CLI-07**: La configuración por defecto se lee de `config.yaml` y los flags de CLI la sobreescriben (validada con pydantic)
- [x] **CLI-08**: El progreso y los logs se muestran de forma legible con `rich`

### ORCH — Orquestador, checkpoints y niveles

- [x] **ORCH-01**: El pipeline ejecuta todas las etapas en orden de forma secuencial
- [x] **ORCH-02**: Cada etapa guarda su checkpoint en `./workdir/` y el pipeline puede reanudarse desde el último checkpoint
- [x] **ORCH-03**: Re-ejecutar una etapa ya completada no duplica trabajo (idempotencia con escritura atómica tmp→rename)
- [x] **ORCH-04**: Los niveles L1–L4 controlan en qué puntos el pipeline se pausa para aprobación del usuario
- [x] **ORCH-05**: La E/S entre etapas está tipada y validada con `pydantic` (contratos JSON entre etapas)

### CTX — Ingesta de contexto

- [x] **CTX-01**: El usuario puede aportar `.pptx`/`.pdf`/`.md` y el sistema extrae su texto como material de referencia
- [x] **CTX-02**: El ingestor es opcional; sin contexto el pipeline funciona igual

### STORY — Storyboard

- [x] **STORY-01**: El sistema genera un storyboard (nº de slides + título/puntos/tipo de visual por slide) con la API de Anthropic a partir de bullets + duración
- [x] **STORY-02**: El storyboard se devuelve como JSON estructurado, validado con pydantic y persistido en `workdir/storyboard.json`

### TIME — Director de timing

- [x] **TIME-01**: El director reparte la duración total entre slides según la densidad de contenido
- [x] **TIME-02**: Calcula el presupuesto de palabras por slide según WPM configurable (por defecto 150)

### SCRIPT — Guionista

- [x] **SCRIPT-01**: El guionista genera con Claude la narración por slide ajustada al presupuesto de palabras
- [x] **SCRIPT-02**: El guion se devuelve como JSON estructurado, en el idioma configurado (por defecto español), con tono natural para locución

### SLIDE — Diseño y generación de slides

- [x] **SLIDE-01**: En modo `auto`, cada slide del storyboard se renderiza a PNG 1920×1080 desde HTML (Jinja2 + `theme.yaml`) con Playwright
- [x] **SLIDE-02**: Las slides usan solo iconos SVG (Lucide/Heroicons) y gráficos/diagramas generados por código (sin imágenes IA ni stock)
- [x] **SLIDE-03**: El tema (paleta, tipografías, espaciado) se parametriza en `theme.yaml` y lo propone la IA
- [x] **SLIDE-04**: En modo `hybrid`, el sistema genera una propuesta de diseño por slide (brief + mockup opcional) en `workdir/design_proposal/`
- [x] **SLIDE-05**: En modos `hybrid`/`manual`, el usuario aporta slides en `workdir/slides_user/slide_XX.{png|pdf|pptx}` y el sistema las ingiere (rasterizando si vienen en .pptx/.pdf)
- [ ] **SLIDE-06**: En modo `auto`, soporta `visual_type: screenshot` con `image_path` y `caption` opcional — el slide renderiza la imagen del usuario dentro de un marco con tipografía y colores del tema (fit-inside + padding)
- [ ] **SLIDE-07**: `bullets.yaml` acepta items tanto string (actual) como `{text: ..., image: <path>}`; cuando `image` está presente, el storyboard usa `visual_type: screenshot` para ese slide

### VERIFY — Verificador de slides (visión)

- [x] **VERIFY-01**: En `hybrid`/`manual`, el verificador usa Claude con visión para comprobar por slide: cobertura del contenido del storyboard, fidelidad a la propuesta/tema, encaje con guion/timing y completitud (ni falta ni sobra)
- [x] **VERIFY-02**: El verificador emite un informe JSON por slide con estado (`ok`/`warning`/`fail`), problemas detectados y sugerencias concretas (`workdir/verification_report.json`)
- [x] **VERIFY-03**: Según el nivel: L1/L2 muestran el informe y permiten iterar (corregir→re-verificar); L3/L4 continúan si todo es `ok` y se detienen si hay `fail`; en modo `auto` no se ejecuta

### VIDEO — Clips de vídeo en slides (auto mode)
- [ ] **VIDEO-01**: En modo `auto`, soporta `visual_type: video` con `video_path` para insertar clips .mp4 cortos del usuario como contenido de slide
- [ ] **VIDEO-02**: La duración del clip de vídeo dicta la duración del slide en el timeline; el scriptwriter calibra la narración para encajar dentro de `wpm × duration(clip) / 60` palabras (overrides timing-director allocation)
- [ ] **VIDEO-03**: El audio original del clip se silencia en el output final; la narración se superpone; si la narración excede la duración del clip se mantiene el último frame para extender (no se cicla, no se acelera)
- [ ] **VIDEO-04**: FFmpeg normaliza cada clip a 1920×1080 H.264 yuv420p durante ingesta y los concatena con slides de imagen en un único timeline con crossfades funcionando en todas las transiciones (imagen↔vídeo, vídeo↔vídeo, vídeo↔imagen)

### VOICE — Voz

- [x] **VOICE-01**: En modo `elevenlabs`, genera un clip de audio por slide con el endpoint con timestamps (modelo `eleven_multilingual_v2`, `voice_id` configurable)
- [x] **VOICE-02**: Valida que los timestamps devueltos sean estrictamente crecientes (mitiga el bug de timestamps "congelados"); reintenta o marca fallback si no
- [x] **VOICE-03**: En modo `record`, exporta el guion segmentado y permite grabar con `sounddevice` o aportar `slide_XX.wav`

### ALIGN — Alineación

- [x] **ALIGN-01**: En modo `record`, WhisperX alinea el audio y produce timings por palabra
- [x] **ALIGN-02**: En modo `elevenlabs`, no se ejecuta alineación (los timings ya vienen del API)

### SUB — Subtítulos

- [x] **SUB-01**: Genera subtítulos `.srt` y `.vtt` a partir de los timings (siempre)
- [x] **SUB-02**: El quemado de subtítulos en el vídeo es opcional mediante flag

### ASMB — Montaje

- [x] **ASMB-01**: Monta el vídeo con FFmpeg (subprocess) sincronizando slides + audios usando duraciones reales medidas con `ffprobe` (no estimadas por WPM)
- [x] **ASMB-02**: Aplica transiciones crossfade configurables entre slides
- [x] **ASMB-03**: La salida por defecto es 1080p 16:9

### QA — Control de calidad

- [x] **QA-01**: Compara la duración real del vídeo vs la objetivo y reporta la desviación
- [x] **QA-02**: Mide y normaliza el loudness con FFmpeg `loudnorm` (dos pasadas) y emite un informe

### PKG — Empaquetado

- [x] **PKG-01**: El proyecto se instala con `pyproject.toml` gestionado con `uv`
- [x] **PKG-02**: Un `Dockerfile` reproducible incluye navegadores de Playwright (versión alineada con el paquete), FFmpeg y Poppler

### TEST — Tests mínimos

- [x] **TEST-01**: Test del storyboard con la API de Anthropic mockeada
- [x] **TEST-02**: Test del director de timing (reparto de duración + presupuesto de palabras)
- [x] **TEST-03**: Test de render de una slide a PNG

### DOC — Documentación

- [x] **DOC-01**: `README.md` con instalación (Playwright browsers, FFmpeg, modelos WhisperX) y ejemplos de uso

## v2 Requirements

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
| CLI-01 | Phase 1 | Complete |
| CLI-02 | Phase 1 | Complete |
| CLI-03 | Phase 1 | Complete |
| CLI-04 | Phase 1 | Complete |
| CLI-05 | Phase 1 | Complete |
| CLI-06 | Phase 1 | Complete |
| CLI-07 | Phase 1 | Complete |
| CLI-08 | Phase 1 | Complete |
| ORCH-01 | Phase 1 | Complete |
| ORCH-02 | Phase 1 | Complete |
| ORCH-03 | Phase 1 | Complete |
| ORCH-04 | Phase 1 | Complete |
| ORCH-05 | Phase 1 | Complete |
| CTX-01 | Phase 2 | Complete |
| CTX-02 | Phase 2 | Complete |
| STORY-01 | Phase 2 | Complete |
| STORY-02 | Phase 2 | Complete |
| TIME-01 | Phase 2 | Complete |
| TIME-02 | Phase 2 | Complete |
| SCRIPT-01 | Phase 2 | Complete |
| SCRIPT-02 | Phase 2 | Complete |
| SLIDE-01 | Phase 3 | Complete |
| SLIDE-02 | Phase 3 | Complete |
| SLIDE-03 | Phase 3 | Complete |
| VOICE-01 | Phase 4 | Complete |
| VOICE-02 | Phase 4 | Complete |
| VOICE-03 | Phase 4 | Complete |
| ALIGN-01 | Phase 4 | Complete |
| ALIGN-02 | Phase 4 | Complete |
| SUB-01 | Phase 4 | Complete |
| SUB-02 | Phase 4 | Complete |
| ASMB-01 | Phase 5 | Pending |
| ASMB-02 | Phase 5 | Pending |
| ASMB-03 | Phase 5 | Pending |
| QA-01 | Phase 5 | Pending |
| QA-02 | Phase 5 | Pending |
| SLIDE-04 | Phase 6 | Pending |
| SLIDE-05 | Phase 6 | Pending |
| VERIFY-01 | Phase 6 | Pending |
| VERIFY-02 | Phase 6 | Pending |
| VERIFY-03 | Phase 6 | Pending |
| VIDEO-01 | Phase 9 | Pending |
| VIDEO-02 | Phase 9 | Pending |
| VIDEO-03 | Phase 9 | Pending |
| VIDEO-04 | Phase 9 | Pending |
| PKG-01 | Phase 7 | Pending |
| PKG-02 | Phase 7 | Pending |
| TEST-01 | Phase 7 | Pending |
| TEST-02 | Phase 7 | Pending |
| TEST-03 | Phase 7 | Pending |
| DOC-01 | Phase 7 | Pending |

**Coverage:**
- v1 requirements: 49 total
- Mapped to phases: 49
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-25*
*Last updated: 2026-05-25 after roadmap creation*
