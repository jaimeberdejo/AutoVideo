# Auto Video Narrado — Pipeline de vídeo (slides generadas + voz en off)

## What This Is

Aplicación de línea de comandos en Python 3.11+ que automatiza de principio a fin la creación de un vídeo tipo "presentación narrada" (slides + voz en off). A partir de una lista de *bullet points*, una duración objetivo y, opcionalmente, un documento de contexto (`.pptx`/`.pdf`/`.md`), el sistema **diseña el storyboard, genera las diapositivas (HTML/CSS → imagen), escribe el guion calibrado a la duración, sintetiza o ingiere la voz, y monta el vídeo final** con subtítulos sincronizados. Está pensado para una persona técnica que quiere producir vídeos narrados de calidad sin edición manual, con control total del código.

## Core Value

A partir de unos bullets + una duración, obtener **un vídeo narrado coherente y de alta calidad (slides + voz + subtítulos sincronizados) sin intervención manual obligatoria** — y con puntos de control opcionales cuando se desee supervisar.

## Requirements

### Validated

<!-- Shipped y confirmado valioso. -->

- ✓ CLI funcional con `typer`: `generate` con todos los flags (`--bullets`, `--duration`, `--voice`, `--slides-mode`, `--level`, `--context`, `--dry-run`) — v1.60.0
- ✓ Orquestador propio, secuencial, con checkpoints reanudables/idempotentes y estado en `./workdir/` — v1.60.0
- ✓ Ingestor de contexto opcional (`.pptx`/`.pdf`/`.md`) — v1.60.0
- ✓ Storyboard generado con la API de Anthropic → JSON validado con Pydantic — v1.60.0
- ✓ Director de timing: reparto por densidad + presupuesto de palabras (WPM configurable, 150) — v1.60.0
- ✓ Guionista (Claude): narración por slide, tono de locución, idioma configurable (español) — v1.60.0
- ✓ Slides modo `auto`: Jinja2 + `theme.yaml` → HTML → PNG 1920×1080 con Playwright; solo SVG + código — v1.60.0
- ✓ Slides modo `hybrid`: propuesta de diseño por slide + ingesta de slides del usuario — v1.60.0
- ✓ Slides modo `manual`: ingesta de slides aportadas por el usuario — v1.60.0
- ✓ Verificador de slides (Claude visión) en `hybrid`/`manual`: informe JSON ok/warning/fail por slide — v1.60.0
- ✓ Voz modo `elevenlabs`: timestamps por carácter (validación estrictamente-creciente + retry) — v1.60.0
- ✓ Voz modo `record`: guion segmentado + grabación `sounddevice` / `slide_XX.wav` — v1.60.0
- ✓ Alineador con WhisperX (solo modo `record`) — v1.60.0
- ✓ Subtítulos `.srt`/`.vtt` desde timings (quemado opcional vía flag) — v1.60.0
- ✓ Montador con FFmpeg directo: crossfade configurable, salida 1080p 16:9 — v1.60.0
- ✓ QA: duración real vs objetivo + loudnorm EBU R128 dos pasadas + informe — v1.60.0
- ✓ 4 niveles de automatización (L1–L4) — v1.60.0
- ✓ `--dry-run` con estimación de tokens/coste sin generar audio/vídeo — v1.60.0
- ✓ Empaquetado `pyproject.toml`/`uv` + `Dockerfile` (Playwright pineado + FFmpeg + Poppler) — v1.60.0
- ✓ Tests mínimos `pytest` (storyboard mockeado, timing, render slide); suite de 303 tests verde — v1.60.0
- ✓ `README.md` con instalación y ejemplos — v1.60.0

### Active

<!-- Alcance del siguiente milestone (Media en `auto`). Hipótesis hasta validar. -->

- [ ] **Screenshot en `auto`** (Phase 8): `visual_type: screenshot` con `image_path`/`caption`; `bullets.yaml` acepta `{text, image}` (SLIDE-06, SLIDE-07)
- [ ] **Video clip en `auto`** (Phase 9): `visual_type: video` con `video_path`; el clip dicta la duración del slide, audio original silenciado + narración superpuesta, hold-last-frame, integración en el filtergraph FFmpeg (VIDEO-01..04)

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

- **Estado actual (post-v1.60.0):** Pipeline MVP completo y enviado — `avideo generate` recorre context → storyboard → timing → scriptwriter → slides → verify → voice → align → subs → assemble end-to-end. ~7.148 LOC Python, 303 tests verdes (todas las APIs/binarios externos mockeados), instalable con `uv` y reproducible en Docker. Auditoría de milestone: PASSED.
- **Foco siguiente milestone:** insertar medios del usuario (capturas y clips .mp4) directamente en modo `auto`, sin obligar a cambiar a `hybrid`/`manual` (Phases 8–9).
- **Deuda técnica conocida (no bloqueante):** imagen Docker verificada por inspección estática (recomendado `docker build` real antes del primer deploy); ingesta de `.pptx` de usuario es best-effort (rasterización offline no soportada → exportar PDF/PNG); WPM español de ElevenLabs (150) pendiente de calibración empírica; compatibilidad WhisperX/torch+pyannote en Docker por validar en la imagen opcional de `record`.
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
| Idioma de narración por defecto: **español** (modelo `eleven_multilingual_v2`), configurable | Usuario hispanohablante; soporte multilingüe disponible | ✓ Good — v1.60.0 |
| WPM por defecto: **150** (configurable) | Ritmo de locución natural estándar | ⚠️ Revisit — estimación pendiente de calibración empírica |
| Formato de salida por defecto: **16:9 1080p** | Estilo presentación/keynote; 9:16 queda como extensión futura | ✓ Good — v1.60.0 |
| Subtítulos: **siempre `.srt`/`.vtt`**; quemado en vídeo = flag opcional | Flexibilidad: vídeo limpio por defecto, quemado bajo demanda | ✓ Good — v1.60.0 |
| ElevenLabs: `voice_id` **placeholder configurable** + `ELEVENLABS_API_KEY` | Usuario aún no fija voz; se rellena en `config.yaml` | ✓ Good — v1.60.0 |
| Orquestador **propio secuencial** (no n8n/LangGraph) | Control total y simplicidad sobre un pipeline lineal | ✓ Good — v1.60.0 |
| Slides vía **HTML/CSS + Playwright** (no partir de .pptx) | Control pixel-perfect y reproducibilidad | ✓ Good — v1.60.0 |
| Montaje con **FFmpeg directo** (no MoviePy) | Rendimiento y control | ✓ Good — v1.60.0 |
| Visuales **solo SVG + código** (sin imágenes IA/stock) | Consistencia visual y reproducibilidad | ✓ Good — v1.60.0 (Phases 8–9 añaden medios aportados por el usuario, no generados por IA) |
| Validación de timestamps ElevenLabs **estrictamente crecientes** + retry≤3 antes de checkpoint | Mitiga el bug de timestamps "congelados" | ✓ Good — v1.60.0 |
| Timing por **largest-remainder** (suma exacta + clamps) | Reparto determinista que cuadra con la duración objetivo | ✓ Good — v1.60.0 |
| FFmpeg por **subprocess con lista de args** (nunca `shell=True`) | Seguridad y transparencia del comando | ✓ Good — v1.60.0 |

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
*Last updated: 2026-05-29 after v1.60.0 milestone*
