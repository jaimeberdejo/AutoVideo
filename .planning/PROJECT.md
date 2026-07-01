# Auto Video Narrado — Pipeline de vídeo (slides generadas + voz en off)

## What This Is

Aplicación Python 3.11+ que automatiza de principio a fin la creación de un vídeo tipo "presentación narrada" (slides + voz en off), disponible tanto como CLI headless (`avideo generate`) como wizard guiado local (`avideo studio`, Streamlit). A partir de una lista de *bullet points* (o un tema, que Claude convierte en bullets), una duración objetivo y, opcionalmente, un documento de contexto (`.pptx`/`.pdf`/`.md`), el sistema **diseña el storyboard, genera las diapositivas (HTML/CSS → imagen), escribe el guion calibrado a la duración, sintetiza o ingiere la voz, y monta el vídeo final** con subtítulos sincronizados. El wizard añade validación humana obligatoria entre cada una de las 6 fases, con edición inline y variaciones dirigidas por feedback de texto. Está pensado para una persona técnica que quiere producir vídeos narrados de calidad sin edición manual, con control total del código.

## Core Value

A partir de unos bullets + una duración, obtener **un vídeo narrado coherente y de alta calidad (slides + voz + subtítulos sincronizados) sin intervención manual obligatoria** — y con puntos de control opcionales cuando se desee supervisar.

## Current State

**Shipped:** v1.60.0 MVP Pipeline (2026-05-29) + v2.0.0 Studio Guiado (2026-07-01).

Auto Video Narrado now ships both a headless CLI (`avideo generate`) and a guided local Streamlit UI (`avideo studio`) that walks the user through 6 wizard phases — Contenido, Guion, Diapositivas, Voz, Extras, Ensamblaje — each gated by explicit human approval, with live previews, inline editing, targeted variation regeneration, and full workdir-backed state reconstruction (survives browser refresh/close). Voice narration supports ElevenLabs, OpenAI Audio (with whisper-1 STT round-trip for timestamps), and user recordings with non-destructive audio enhancement. Background music mixing (ducking + fades + single-pass loudnorm) and Claude Vision slide QC round out the extras. 456 tests passing.

## Next Milestone Goals

Not yet planned — run `/gsd-new-milestone` to define scope. Candidates surfaced during v2.0.0 (see Active below and `.planning/milestones/v2.0.0-REQUIREMENTS.md` "Later Requirements"): SEED-001 (Pexels-sourced visual media in slides, currently on `feature/pexels-slides` branch, not merged), export to `.pptx`, 9:16 vertical output, custom theme/branding override, bundled royalty-free music library.

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
- ✓ UI Streamlit local (single-user, `localhost`) como superficie principal del flujo — v2.0.0
- ✓ Wizard de 6 fases con validación humana obligatoria entre fases (no avanza hasta confirmar) — v2.0.0
- ✓ Previews en vivo en la UI: bullets, guion por slide editable, thumbnails de slides, vídeo final reproducible/descargable — v2.0.0
- ✓ Fase 1: auto-generación de bullets desde un tema (Claude) + aprobar/editar — v2.0.0
- ✓ Fase 2: revisión interactiva del guion (editar texto / pedir variaciones / iterar hasta OK) — v2.0.0
- ✓ Fase 3: slides generadas por la app con revisión interactiva (editar / variaciones / iterar) — v2.0.0
- ✓ Fase 3: slides subidas por el usuario con control de calidad (verificador Claude Vision avisa de discrepancias) — v2.0.0
- ✓ Fase 4: OpenAI Audio como tercer proveedor de voz (junto a ElevenLabs y record) — v2.0.0
- ✓ Fase 4: para audios subidos por el usuario, botón de mejora automática de audio (denoise + normalización) — v2.0.0
- ✓ Fase 5: música de fondo desde archivo del usuario (mezcla con ducking + fades en FFmpeg) — v2.0.0
- ✓ Fase 6: ensamblaje automático sincronizado con preview/descarga en la UI — v2.0.0
- ✓ CLI `generate` conservado como motor headless orquestado por la UI — v2.0.0
- ✓ Variación dirigida por feedback de texto (SEED-002) en guion/storyboard/slides, no solo "regenerar a ciegas" — v2.0.0

### Active

<!-- Alcance del próximo milestone. Aún sin definir formalmente — ejecutar /gsd-new-milestone. -->

(Ninguno — próximo milestone sin definir. Ver candidatos abajo.)

### Out of Scope

<!-- Límites explícitos con razón, para no re-añadirlos. -->

- **Generación de imágenes con IA** — decisión de diseño: solo iconos SVG y gráficos por código para control y consistencia visual
- **Bancos de imágenes / stock** — misma razón: visuales 100% reproducibles y editables (nota: SEED-001/Pexels explora medios de stock con licencia libre para slides, en rama separada `feature/pexels-slides`, sin fusionar — pendiente de decisión explícita si se retoma)
- **Orquestadores visuales (n8n)** — se quiere un orquestador propio en Python, simple y controlable
- **Frameworks pesados de agentes (LangGraph)** — innecesarios para un pipeline secuencial; añaden complejidad
- **MoviePy** — se usa FFmpeg directo por rendimiento y control
- **Marca/branding propio como requisito de entrada** — el tema lo propone la IA en `theme.yaml`; sobreescritura de marca es opcional/futura (candidato BRAND-01 para milestone futuro)
- **Partir de un `.pptx` existente como flujo principal** — el workflow genera las slides; ingerir slides del usuario solo en modos `hybrid`/`manual`
- **9:16 vertical como salida por defecto** — por defecto 16:9 1080p (candidato FMT-01 para milestone futuro)
- **Exportación a `.pptx`** — diferido (candidato EXPORT-01)
- **Modo multi-usuario / hosteado con autenticación** — hoy: local single-user (candidato UI-MULTI-01)

## Context

- **Estado actual (post-v2.0.0):** Ambos milestones enviados y auditados PASSED. `avideo generate` (CLI headless) y `avideo studio` (wizard Streamlit de 6 fases) comparten el mismo motor de pipeline y checkpoints de `workdir/`. ~10.688 LOC Python, 456 tests verdes. Una sesión de UAT real en navegador (Chrome MCP + Playwright, APIs reales de Anthropic/OpenAI, FFmpeg real) recorrió las 6 fases end-to-end hasta un MP4 descargable y encontró/corrigió 3 bugs bloqueantes (contexto de tema perdido en retry del guionista, nombre de archivo temporal de FFmpeg rompiendo autodetección de formato, `run_config` no sobrevivía a un refresco del navegador) más varios bugs menores de UX. Ver `.planning/milestones/v2.0.0-MILESTONE-AUDIT.md` y `.planning/milestones/v2.0.0-BROWSER-VERIFICATION.md` (si se archivó) para detalle completo.
- **Decisión UI (validada):** Streamlit (web local), no FastAPI+frontend ni TUI — la elección de rapidez de implementación se confirmó correcta; la UI quedó como capa fina sobre etapas ya construidas sin fricción.
- **Deuda técnica conocida (no bloqueante, ver auditoría v2.0.0 para detalle completo):** `bridge.py` indexa hilos/errores solo por `stage_name` (no por `(workdir, stage_name)`) — dos sesiones concurrentes en el mismo stage interferirían; bajo riesgo para herramienta single-user localhost. `write_feedback`/`clear_feedback` (SEED-002) hacen read-modify-write sin lock sobre `feedback.json` — ventana de carrera estrecha, no observada en producción. Rutas de subida de audio propio + mejora, subida de slides + QC, y subida de música de fondo no se ejercitaron en la sesión de UAT en navegador (se priorizó el camino OpenAI TTS + auto-slides para llegar a un vídeo completo) — pendiente de una pasada de UAT dedicada si se detectan problemas en uso real. Imagen Docker verificada por inspección estática (recomendado `docker build` real antes del primer deploy); WPM español de ElevenLabs (150) pendiente de calibración empírica.
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
- **Tech stack — UI (v2.0.0):** `streamlit` (web UI local, single-user); la UI orquesta el CLI/etapas como motor.
- **Tech stack — TTS (v2.0.0):** además de `elevenlabs`, `openai` (OpenAI Audio API) como tercer proveedor de voz; `OPENAI_API_KEY` en `.env`.
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
| Streamlit para la UI (no FastAPI+frontend/TUI) | Rapidez de implementación + todo en Python | ✓ Good — v2.0.0 (sin fricción en UAT real) |
| Reconstrucción de estado desde `workdir/*.json`, no `session_state` | Sobrevive a refrescos/cierres del navegador; single source of truth | ✓ Good — v2.0.0 |
| Etapas largas vía `PipelineBridge` (hilo daemon + polling), no bloqueo síncrono de Streamlit | UI responsiva durante render/TTS/montaje | ✓ Good — v2.0.0 |
| OpenAI Audio TTS + round-trip STT (`whisper-1`) para timestamps | OpenAI TTS no da timestamps nativos; reusa formato `UnifiedTimings` existente | ✓ Good — v2.0.0 |
| Mejora de audio no destructiva (`enhance_audio`, FFmpeg `afftdn`+`loudnorm`) con preview antes/después | Evita perder el original; alineación de subtítulos usa el audio sin procesar | ✓ Good — v2.0.0 |
| Música de fondo: una sola pasada loudnorm sobre la mezcla final (no dos pasadas separadas) | Evita que el ducking de la música desplace el LUFS objetivo de la narración | ✓ Good — v2.0.0 |
| SEED-002: feedback de texto dirigido en vez de "regenerar a ciegas" | El usuario puede guiar la variación (más visual, más corto, etc.) en vez de repetir intentos aleatorios | ✓ Good — v2.0.0 |
| `invalidate_downstream` explícito al editar/regenerar en vez de invalidación implícita | Evita mostrar al usuario resultados desincronizados con el checkpoint editado | ✓ Good — v2.0.0 |

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
*Last updated: 2026-07-01 — milestone v2.0.0 Studio Guiado completed*
