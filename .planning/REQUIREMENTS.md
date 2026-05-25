# Requirements: Auto Video Narrado

**Defined:** 2026-05-25
**Core Value:** A partir de unos bullets + una duración, obtener un vídeo narrado coherente y de alta calidad (slides + voz + subtítulos sincronizados) sin intervención manual obligatoria, con checkpoints opcionales de supervisión.

## v1 Requirements

Requisitos del release inicial. Cada uno se mapea a fases del roadmap.

### CLI — Interfaz de línea de comandos

- [ ] **CLI-01**: El usuario puede ejecutar `generate` con `--bullets` y `--duration` y obtener un vídeo MP4 final
- [ ] **CLI-02**: El usuario puede elegir la fuente de voz con `--voice {elevenlabs|record}`
- [ ] **CLI-03**: El usuario puede elegir el modo de slides con `--slides-mode {auto|hybrid|manual}`
- [ ] **CLI-04**: El usuario puede elegir el nivel de automatización con `--level {1..4}`
- [ ] **CLI-05**: El usuario puede aportar un documento de contexto opcional con `--context`
- [ ] **CLI-06**: El usuario puede ejecutar `--dry-run` para estimar tokens/coste y duración sin generar audio/vídeo
- [ ] **CLI-07**: La configuración por defecto se lee de `config.yaml` y los flags de CLI la sobreescriben (validada con pydantic)
- [ ] **CLI-08**: El progreso y los logs se muestran de forma legible con `rich`

### ORCH — Orquestador, checkpoints y niveles

- [ ] **ORCH-01**: El pipeline ejecuta todas las etapas en orden de forma secuencial
- [ ] **ORCH-02**: Cada etapa guarda su checkpoint en `./workdir/` y el pipeline puede reanudarse desde el último checkpoint
- [ ] **ORCH-03**: Re-ejecutar una etapa ya completada no duplica trabajo (idempotencia con escritura atómica tmp→rename)
- [ ] **ORCH-04**: Los niveles L1–L4 controlan en qué puntos el pipeline se pausa para aprobación del usuario
- [ ] **ORCH-05**: La E/S entre etapas está tipada y validada con `pydantic` (contratos JSON entre etapas)

### CTX — Ingesta de contexto

- [ ] **CTX-01**: El usuario puede aportar `.pptx`/`.pdf`/`.md` y el sistema extrae su texto como material de referencia
- [ ] **CTX-02**: El ingestor es opcional; sin contexto el pipeline funciona igual

### STORY — Storyboard

- [ ] **STORY-01**: El sistema genera un storyboard (nº de slides + título/puntos/tipo de visual por slide) con la API de Anthropic a partir de bullets + duración
- [ ] **STORY-02**: El storyboard se devuelve como JSON estructurado, validado con pydantic y persistido en `workdir/storyboard.json`

### TIME — Director de timing

- [ ] **TIME-01**: El director reparte la duración total entre slides según la densidad de contenido
- [ ] **TIME-02**: Calcula el presupuesto de palabras por slide según WPM configurable (por defecto 150)

### SCRIPT — Guionista

- [ ] **SCRIPT-01**: El guionista genera con Claude la narración por slide ajustada al presupuesto de palabras
- [ ] **SCRIPT-02**: El guion se devuelve como JSON estructurado, en el idioma configurado (por defecto español), con tono natural para locución

### SLIDE — Diseño y generación de slides

- [ ] **SLIDE-01**: En modo `auto`, cada slide del storyboard se renderiza a PNG 1920×1080 desde HTML (Jinja2 + `theme.yaml`) con Playwright
- [ ] **SLIDE-02**: Las slides usan solo iconos SVG (Lucide/Heroicons) y gráficos/diagramas generados por código (sin imágenes IA ni stock)
- [ ] **SLIDE-03**: El tema (paleta, tipografías, espaciado) se parametriza en `theme.yaml` y lo propone la IA
- [ ] **SLIDE-04**: En modo `hybrid`, el sistema genera una propuesta de diseño por slide (brief + mockup opcional) en `workdir/design_proposal/`
- [ ] **SLIDE-05**: En modos `hybrid`/`manual`, el usuario aporta slides en `workdir/slides_user/slide_XX.{png|pdf|pptx}` y el sistema las ingiere (rasterizando si vienen en .pptx/.pdf)

### VERIFY — Verificador de slides (visión)

- [ ] **VERIFY-01**: En `hybrid`/`manual`, el verificador usa Claude con visión para comprobar por slide: cobertura del contenido del storyboard, fidelidad a la propuesta/tema, encaje con guion/timing y completitud (ni falta ni sobra)
- [ ] **VERIFY-02**: El verificador emite un informe JSON por slide con estado (`ok`/`warning`/`fail`), problemas detectados y sugerencias concretas (`workdir/verification_report.json`)
- [ ] **VERIFY-03**: Según el nivel: L1/L2 muestran el informe y permiten iterar (corregir→re-verificar); L3/L4 continúan si todo es `ok` y se detienen si hay `fail`; en modo `auto` no se ejecuta

### VOICE — Voz

- [ ] **VOICE-01**: En modo `elevenlabs`, genera un clip de audio por slide con el endpoint con timestamps (modelo `eleven_multilingual_v2`, `voice_id` configurable)
- [ ] **VOICE-02**: Valida que los timestamps devueltos sean estrictamente crecientes (mitiga el bug de timestamps "congelados"); reintenta o marca fallback si no
- [ ] **VOICE-03**: En modo `record`, exporta el guion segmentado y permite grabar con `sounddevice` o aportar `slide_XX.wav`

### ALIGN — Alineación

- [ ] **ALIGN-01**: En modo `record`, WhisperX alinea el audio y produce timings por palabra
- [ ] **ALIGN-02**: En modo `elevenlabs`, no se ejecuta alineación (los timings ya vienen del API)

### SUB — Subtítulos

- [ ] **SUB-01**: Genera subtítulos `.srt` y `.vtt` a partir de los timings (siempre)
- [ ] **SUB-02**: El quemado de subtítulos en el vídeo es opcional mediante flag

### ASMB — Montaje

- [ ] **ASMB-01**: Monta el vídeo con FFmpeg (subprocess) sincronizando slides + audios usando duraciones reales medidas con `ffprobe` (no estimadas por WPM)
- [ ] **ASMB-02**: Aplica transiciones crossfade configurables entre slides
- [ ] **ASMB-03**: La salida por defecto es 1080p 16:9

### QA — Control de calidad

- [ ] **QA-01**: Compara la duración real del vídeo vs la objetivo y reporta la desviación
- [ ] **QA-02**: Mide y normaliza el loudness con FFmpeg `loudnorm` (dos pasadas) y emite un informe

### PKG — Empaquetado

- [ ] **PKG-01**: El proyecto se instala con `pyproject.toml` gestionado con `uv`
- [ ] **PKG-02**: Un `Dockerfile` reproducible incluye navegadores de Playwright (versión alineada con el paquete), FFmpeg y Poppler

### TEST — Tests mínimos

- [ ] **TEST-01**: Test del storyboard con la API de Anthropic mockeada
- [ ] **TEST-02**: Test del director de timing (reparto de duración + presupuesto de palabras)
- [ ] **TEST-03**: Test de render de una slide a PNG

### DOC — Documentación

- [ ] **DOC-01**: `README.md` con instalación (Playwright browsers, FFmpeg, modelos WhisperX) y ejemplos de uso

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
| CLI-01 | Phase 1 | Pending |
| CLI-02 | Phase 1 | Pending |
| CLI-03 | Phase 1 | Pending |
| CLI-04 | Phase 1 | Pending |
| CLI-05 | Phase 1 | Pending |
| CLI-06 | Phase 1 | Pending |
| CLI-07 | Phase 1 | Pending |
| CLI-08 | Phase 1 | Pending |
| ORCH-01 | Phase 1 | Pending |
| ORCH-02 | Phase 1 | Pending |
| ORCH-03 | Phase 1 | Pending |
| ORCH-04 | Phase 1 | Pending |
| ORCH-05 | Phase 1 | Pending |
| CTX-01 | Phase 2 | Pending |
| CTX-02 | Phase 2 | Pending |
| STORY-01 | Phase 2 | Pending |
| STORY-02 | Phase 2 | Pending |
| TIME-01 | Phase 2 | Pending |
| TIME-02 | Phase 2 | Pending |
| SCRIPT-01 | Phase 2 | Pending |
| SCRIPT-02 | Phase 2 | Pending |
| SLIDE-01 | Phase 3 | Pending |
| SLIDE-02 | Phase 3 | Pending |
| SLIDE-03 | Phase 3 | Pending |
| VOICE-01 | Phase 4 | Pending |
| VOICE-02 | Phase 4 | Pending |
| VOICE-03 | Phase 4 | Pending |
| ALIGN-01 | Phase 4 | Pending |
| ALIGN-02 | Phase 4 | Pending |
| SUB-01 | Phase 4 | Pending |
| SUB-02 | Phase 4 | Pending |
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
