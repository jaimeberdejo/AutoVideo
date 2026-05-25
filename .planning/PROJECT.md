# Auto Video Narrado — Pipeline de vídeo (slides generadas + voz en off)

## What This Is

Aplicación de línea de comandos en Python 3.11+ que automatiza de principio a fin la creación de un vídeo tipo "presentación narrada" (slides + voz en off). A partir de una lista de *bullet points*, una duración objetivo y, opcionalmente, un documento de contexto (`.pptx`/`.pdf`/`.md`), el sistema **diseña el storyboard, genera las diapositivas (HTML/CSS → imagen), escribe el guion calibrado a la duración, sintetiza o ingiere la voz, y monta el vídeo final** con subtítulos sincronizados. Está pensado para una persona técnica que quiere producir vídeos narrados de calidad sin edición manual, con control total del código.

## Core Value

A partir de unos bullets + una duración, obtener **un vídeo narrado coherente y de alta calidad (slides + voz + subtítulos sincronizados) sin intervención manual obligatoria** — y con puntos de control opcionales cuando se desee supervisar.

## Requirements

### Validated

<!-- Shipped y confirmado valioso. -->

(Ninguno aún — greenfield, se valida al enviar)

### Active

<!-- Alcance actual. Hipótesis hasta que se construyan y validen. -->

- [ ] CLI funcional con `typer`: `generate --bullets bullets.yaml --duration 120 --voice elevenlabs --slides-mode hybrid --level 3 [--context deck.pdf]`
- [ ] Orquestador propio, secuencial, con checkpoints reanudables y estado en `./workdir/`
- [ ] Ingestor de contexto opcional (`.pptx`/`.pdf`/`.md`) que extrae texto de referencia
- [ ] Storyboard generado con la API de Anthropic (Claude más reciente) → JSON estructurado
- [ ] Director de timing: reparto de duración por slide + presupuesto de palabras (WPM configurable, por defecto 150)
- [ ] Guionista (Claude): narración por slide, tono natural para locución, idioma configurable (por defecto español)
- [ ] Generación de slides modo `auto`: Jinja2 + `theme.yaml` → HTML → PNG alta resolución con Playwright; solo iconos SVG (Lucide/Heroicons) y gráficos por código (sin imágenes IA)
- [ ] Generación de slides modo `hybrid`: propuesta de diseño por slide en `workdir/design_proposal/` + ingesta de slides del usuario
- [ ] Generación de slides modo `manual`: ingesta de slides aportadas por el usuario
- [ ] Verificador de slides (Claude con visión) en `hybrid`/`manual`: informe JSON por slide (ok/warning/fail) sobre cobertura de contenido, fidelidad al diseño/tema, encaje con guion/timing y completitud
- [ ] Voz modo `elevenlabs`: API con endpoint de timestamps (sin alineación posterior); modelo `eleven_multilingual_v2`, `voice_id` configurable
- [ ] Voz modo `record`: exporta guion segmentado; grabación con `sounddevice` o `slide_XX.wav` aportado
- [ ] Alineador con WhisperX (solo modo `record`)
- [ ] Subtítulos `.srt`/`.vtt` desde timings (siempre generados; quemado en vídeo opcional vía flag)
- [ ] Montador con FFmpeg directo (subprocess): slides + audios, crossfade configurable, subtítulos opcionales, salida 1080p 16:9 por defecto
- [ ] QA: duración real vs objetivo, medición y normalización de loudness (FFmpeg `loudnorm`), informe
- [ ] 4 niveles de automatización (L1–L4) que controlan las pausas de aprobación
- [ ] `--dry-run` que estima tokens/coste y duración sin generar audio/vídeo
- [ ] Empaquetado: `pyproject.toml` (gestión con `uv`) + `Dockerfile` (incluye navegadores Playwright + FFmpeg)
- [ ] Tests mínimos con `pytest`: storyboard (API mockeada), director de timing, render de una slide
- [ ] `README.md` con instalación (Playwright browsers, FFmpeg, modelos WhisperX) y ejemplos

### Out of Scope

<!-- Límites explícitos con razón, para no re-añadirlos. -->

- **Generación de imágenes con IA** — decisión de diseño: solo iconos SVG y gráficos por código para control y consistencia visual
- **Bancos de imágenes / stock** — misma razón: visuales 100% reproducibles y editables
- **Orquestadores visuales (n8n)** — se quiere un orquestador propio en Python, simple y controlable
- **Frameworks pesados de agentes (LangGraph)** — innecesarios para un pipeline secuencial; añaden complejidad
- **MoviePy** — se usa FFmpeg directo por rendimiento y control
- **Marca/branding propio como requisito de entrada** — el tema lo propone la IA en `theme.yaml`; sobreescritura de marca es opcional/futura
- **Partir de un `.pptx` existente como flujo principal** — el workflow genera las slides; ingerir slides del usuario solo en modos `hybrid`/`manual`
- **9:16 vertical como salida por defecto** — por defecto 16:9 1080p (9:16 puede añadirse como extensión futura)

## Context

- **Prioridades de diseño (en orden):** (1) máxima calidad de salida, (2) rapidez de implementación, (3) control total del código.
- **Ejecución local** en Python, empaquetable en Docker.
- **Slides pixel-perfect** vía HTML/CSS renderizado con Playwright; editable como CSS plano; export a `.pptx` con `python-pptx` como opción secundaria.
- **Pipeline de etapas** (cada una con I/O tipada con `pydantic`) y checkpoints: `context.json`, `storyboard.json`, `script.json`, `design_proposal/`, `slides/` (auto) o `slides_user/` (hybrid/manual), `verification_report.json`, `timings.json`, `audio/`, `subs/`. Idempotente: re-ejecutar una etapa no duplica trabajo.
- **Interacción niveles × slides_mode:** en `hybrid`/`manual` el pipeline pausa tras la propuesta de diseño para que el usuario cree/aporte slides; tras el Verificador, en L1/L2 siempre muestra el informe e itera, en L3/L4 continúa si todo es `ok` y solo se detiene si hay `fail`. En modo `auto` no se ejecuta el verificador.
- **Claves externas requeridas en runtime:** `ANTHROPIC_API_KEY` (storyboard/guion/verificador) y `ELEVENLABS_API_KEY` (voz modo elevenlabs).
- **Orden de implementación sugerido:** Storyboard → Timing → Guionista → Slides `auto` → Slides `hybrid`/`manual` → Verificador (Claude visión) → Voz/ElevenLabs → Montaje FFmpeg → WhisperX (modo record) al final.

## Constraints

- **Tech stack — Lenguaje:** Python 3.11+ — requisito.
- **Tech stack — LLM:** SDK `anthropic`, modelo Claude más reciente, con visión para el verificador — requisito.
- **Tech stack — Slides:** `jinja2` + `playwright` (render PNG); `python-pptx` para export opcional — control pixel-perfect.
- **Tech stack — Entrada/ingesta:** `python-pptx`, `PyMuPDF`, `pdf2image` (rasterizar slides .pptx/.pdf antes de verificar).
- **Tech stack — TTS:** `elevenlabs` (API con timestamps).
- **Tech stack — Grabación/alineación:** `sounddevice`, `soundfile`; `whisperx` (solo modo record).
- **Tech stack — Vídeo:** `ffmpeg` vía subprocess (no MoviePy).
- **Tech stack — CLI/config/logs:** `typer`, `pydantic`, `pyyaml`, `rich`.
- **Tech stack — Tests/empaquetado:** `pytest`; `pyproject.toml` gestionado con `uv`; `Dockerfile`.
- **Calidad de código:** modular, tipado, docstrings, manejo de errores claro, reanudable e idempotente.
- **Visuales:** solo iconos SVG (Lucide/Heroicons) y gráficos por código; nada de imágenes IA ni stock.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Idioma de narración por defecto: **español** (modelo `eleven_multilingual_v2`), configurable | Usuario hispanohablante; soporte multilingüe disponible | — Pending |
| WPM por defecto: **150** (configurable) | Ritmo de locución natural estándar | — Pending |
| Formato de salida por defecto: **16:9 1080p** | Estilo presentación/keynote; 9:16 queda como extensión futura | — Pending |
| Subtítulos: **siempre `.srt`/`.vtt`**; quemado en vídeo = flag opcional | Flexibilidad: vídeo limpio por defecto, quemado bajo demanda | — Pending |
| ElevenLabs: `voice_id` **placeholder configurable** + `ELEVENLABS_API_KEY` | Usuario aún no fija voz; se rellena en `config.yaml` | — Pending |
| Orquestador **propio secuencial** (no n8n/LangGraph) | Control total y simplicidad sobre un pipeline lineal | — Pending |
| Slides vía **HTML/CSS + Playlwright** (no partir de .pptx) | Control pixel-perfect y reproducibilidad | — Pending |
| Montaje con **FFmpeg directo** (no MoviePy) | Rendimiento y control | — Pending |
| Visuales **solo SVG + código** (sin imágenes IA/stock) | Consistencia visual y reproducibilidad | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-25 after initialization*
