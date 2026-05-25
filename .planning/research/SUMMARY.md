# Project Research Summary

**Project:** auto-video-narrado
**Domain:** CLI Python — pipeline secuencial de vídeo narrado (slides generadas + voz en off + subtítulos)
**Researched:** 2026-05-25
**Confidence:** HIGH

## Executive Summary

auto-video-narrado es un pipeline CLI totalmente secuencial que transforma bullets + duración objetivo en un vídeo narrado listo para consumir (slides 1080p 16:9, voz sintetizada por ElevenLabs, subtítulos SRT/VTT sincronizados, montaje FFmpeg). El enfoque recomendado por la investigación es un orquestador propio en Python — sin LangGraph, sin n8n, sin MoviePy — con checkpoints reanudables basados en ficheros JSON Pydantic-tipados en `workdir/`. La arquitectura de referencia en dominios análogos (AutoLectures 2025, PresentAgent 2024) confirma que un pipeline LLM secuencial con alineación de timestamps TTS es el patrón maduro de 2025-2026. El stack está completamente verificado en PyPI y fuentes oficiales, con versiones pineadas probadas en producción.

El mayor riesgo técnico del proyecto no es la integración individual de ninguna librería, sino la sincronía acumulada entre audio y vídeo y la idempotencia del orquestador ante fallos parciales de API. La investigación identifica cuatro puntos críticos que deben resolverse en los primeros sprints antes de cualquier llamada a API externa: orquestador con checkpoints atómicos, director de timing basado en ffprobe (no WPM estimado), validación de timestamps de ElevenLabs, y espera de fuentes en Playwright. El verificador de slides con Claude Visión es el diferenciador competitivo más claro — ningún competidor lo implementa — pero debe diferirse a v1.x para no bloquear el pipeline base.

El orden de construcción recomendado por la investigación de arquitectura es estrictamente bottom-up: modelos Pydantic y workdir primero, orquestador con stubs segundo (valida checkpoints sin APIs reales), y etapas externas en capas progresivas (LLM → Playwright → ElevenLabs → FFmpeg → WhisperX). Este orden es no negociable: construir el orquestador antes de las etapas externas es la única forma de validar la idempotencia sin incurrir en costes de API durante el desarrollo.

## Key Findings

### Recommended Stack

El stack está completamente determinado y verificado. Python 3.11 es el target (balance estabilidad/velocidad; todas las librerías clave lo soportan). La gestión de entorno es con `uv` (pyproject.toml); la imagen Docker base es `mcr.microsoft.com/playwright/python:v1.60.0-noble` — esta imagen debe pinearse a exactamente la misma versión que `playwright` en pyproject.toml, o el pipeline falla con "browser executable not found". FFmpeg se invoca siempre via `subprocess` con lista de argumentos (nunca `shell=True`). Lucide icons deben servirse offline con `python-lucide` (BD SQLite embebida) — jamás desde CDN.

**Core technologies:**
- Python 3.11+: lenguaje base — requisito; balance estabilidad/velocidad; todas las librerías lo soportan
- `anthropic >=0.104.1`: LLM API (storyboard, guion, verificador visión) — SDK oficial con visión base64/PNG; Structured Outputs disponibles desde Claude Sonnet 4.5+
- `playwright >=1.60.0`: render HTML/CSS → PNG — única opción pixel-perfect para CSS moderno; sync API obligatoria (no async)
- `jinja2 >=3.1.6`: templating HTML de slides — integración nativa con Playwright; permite theme.yaml → HTML
- `elevenlabs >=2.49.0`: TTS con timestamps por carácter — sin pipeline extra de alineación en modo elevenlabs
- `pydantic >=2.13.4`: I/O tipado entre etapas del pipeline — checkpoint serialization con model_dump_json/model_validate_json
- `typer >=0.25.1`: CLI con subcomandos tipados — estándar actual para CLIs Python 3.10+; requiere Python >=3.10
- `ffmpeg >=6.1` (binario sistema): montaje de vídeo — control total sobre filtros; invocación por subprocess con lista de argumentos
- `rich >=15.0.0`: UX de terminal (progress, logs, prompts de aprobación) — companion natural de Typer
- `uv` (latest): gestión de dependencias — 10-100x más rápido que pip; uv.lock multiplataforma

### Expected Features

**Must have (table stakes — v1):**
- CLI typer + Pydantic config — punto de entrada del sistema; sin él no hay producto
- Director de timing (WPM x duración, calibración empírica) — sin esto el vídeo nunca dura lo esperado
- Storyboard generado por Claude — núcleo intelectual del pipeline
- Guionista Claude calibrado por slide — narración WPM-calibrada, idioma configurable (español por defecto)
- Slides modo `auto` (Jinja2 + Playwright → PNG 1920x1080) — camino feliz sin intervención; solo SVG Lucide offline
- Voz ElevenLabs con timestamps — TTS de calidad; timestamps a nivel de carácter sin WhisperX
- Subtítulos .srt/.vtt siempre generados — accesibilidad básica; coste cero adicional
- Montaje FFmpeg 1080p 16:9 — entregable final; duraciones reales medidas con ffprobe (no WPM estimado)
- Checkpoints reanudables (workdir/) — sin esto los fallos de API son bloqueantes para el usuario
- `--dry-run` con estimación de coste/tokens — control de gasto antes de lanzar; feature rara en competencia
- 4 niveles de automatización L1-L4 — human-in-the-loop configurable; diferenciador vs competencia fully-auto
- Tests pytest mínimos (storyboard mockeado, timing, render de slide) — base de confianza del pipeline

**Should have (v1.x — tras validar pipeline base):**
- Verificador de slides con Claude Visión (hybrid/manual) — diferenciador competitivo único; ningún competidor lo tiene
- Slides modos `hybrid` + `manual` — flexibilidad para usuarios con diseño propio
- Normalización loudness EBU R128 (dos pasadas FFmpeg) — calidad audio uniforme slide a slide
- Crossfade audio/vídeo configurable — refinamiento perceptivo; bajo coste una vez FFmpeg integrado
- Quemado de subtítulos (`--burn-subs`) — útil para distribución en RRSS
- Ingestión de contexto (.pptx/.pdf/.md) — usuarios con materiales previos
- QA report (duración real vs objetivo + LUFS)
- Dockerfile multi-stage (Playwright + FFmpeg; WhisperX separado)

**Defer (v2+):**
- Voz modo `record` + WhisperX — alta complejidad de dependencias (torch, CUDA, pyannote); validar demanda primero
- Export .pptx (python-pptx) — útil pero no core
- Soporte 9:16 vertical — requiere refactor de templates

### Architecture Approach

La arquitectura es un pipeline secuencial con orquestador propio que itera sobre etapas que implementan `StageProtocol` (typing.Protocol). El orquestador pasa solo `WorkdirManager` a cada etapa — nunca objetos Python entre etapas. Cada etapa lee su input de `workdir/*.json` (Pydantic model_validate_json) y escribe su output a `workdir/*.json` (Pydantic model_dump_json), luego toca un marcador `.{stage}.done`. Esta separación permite reanudar el pipeline en cualquier punto sin re-ejecutar etapas anteriores, y hace cada etapa independientemente testeable con fixtures JSON. La aprobación humana (L1-L4) es responsabilidad exclusiva del orquestador — las etapas son lógica pura y nunca interactúan con stdin ni llaman subprocess directamente.

**Major components:**
1. CLI (`cli.py` + typer) — parsea args, construye RunConfig (Pydantic), llama al orquestador
2. Orchestrator (`orchestrator.py`) — loop secuencial, checkpoint checks, approval gates L1-L4; la única pieza que sabe sobre niveles de automatización
3. Models (`models/`) — contratos Pydantic de I/O entre etapas; fuente de verdad del schema de checkpoints; sin lógica de negocio
4. Stages (`stages/`) — una etapa por fichero; autocontenidas; sin lógica de aprobación ni subprocess directo
5. Integrations (`integrations/`) — adaptadores delgados sobre Playwright, FFmpeg, WhisperX, Anthropic, ElevenLabs; aíslan efectos de lado
6. WorkdirManager (`utils/workdir.py`) — autoridad única de paths en workdir/; todas las rutas pasan por aquí
7. RichUI (`utils/rich_ui.py`) — progress bars, prompts de aprobación, display de reportes QA; mockeable en tests

### Critical Pitfalls

1. **No-idempotencia del pipeline** — Checkpoints basados en existencia + validación Pydantic del contenido (no solo existencia del fichero). Escritura atómica con `.tmp` + rename. Construir antes de cualquier llamada a API externa.

2. **Timestamps ElevenLabs congelados** (bug documentado en issue #607) — Validar que la secuencia de start_times es estrictamente creciente antes de guardar el checkpoint. Reintentar hasta 3 veces o usar WhisperX como fallback de alineación sobre el audio ya generado.

3. **Fuentes no cargadas en screenshots Playwright** — Llamar `page.wait_for_function("document.fonts.ready")` + `page.screenshot(animations='disabled')` siempre. Servir fuentes localmente (jamás CDN). Instalar paquetes de fuentes del sistema en Dockerfile.

4. **Drift de timing audio/slide acumulado** — Medir la duración real de cada slide_XX.mp3 con ffprobe antes del montaje. La suma de duraciones reales (no WPM estimado) es el offset de cada slide en el concat de FFmpeg.

5. **WPM inexacto para ElevenLabs en español** — Calibración empírica obligatoria: 100 palabras con la voz y modelo exactos → medir duración real → WPM efectivo. Añadir margen -10% al presupuesto de palabras. Documentar en config.yaml.

6. **JSON Claude no parseable** — Usar Structured Outputs de la API (disponible Claude Sonnet 4.5+) con JSON Schema Pydantic. Nunca prompting manual para formato. Fijar max_tokens por presupuesto calculado.

7. **Playwright versión no alineada en Docker** — Pinear exactamente la misma versión en pyproject.toml y en el FROM de la imagen Docker. Nunca Alpine (musl libc). Siempre imagen oficial Microsoft.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Foundation — Orquestador + Modelos + Skeleton

**Rationale:** La investigación de arquitectura es explícita: construir el orquestador y los contratos Pydantic antes de cualquier etapa externa. El pitfall de no-idempotencia solo se puede validar sin costes de API si el orquestador tiene checkpoints operativos antes de conectar SDKs reales. Esta fase es el riesgo arquitectónico más alto y debe resolverse primero.

**Delivers:** CLI funcional con typer; RunConfig validado; WorkdirManager; StageProtocol; orquestador con loop de checkpoints + approval gates L1-L4 (etapas stub); todos los modelos Pydantic de I/O; test de idempotencia doble-ejecución; `--dry-run` skeleton.

**Addresses:** Table stakes: CLI, orquestador con checkpoints, 4 niveles de automatización.

**Avoids:** Pitfall #10 (no-idempotencia) — es el fundamento de esta fase.

### Phase 2: LLM Pipeline — Storyboard + Timing + Guionista

**Rationale:** Las etapas LLM dependen solo de la foundation (Phase 1). El director de timing es lógica pura (sin APIs externas), testeable completamente offline. El storyboard y guionista establecen el patrón de Structured Outputs + validación Pydantic + retry exponencial, reutilizado luego en el verificador.

**Delivers:** `integrations/anthropic.py` con retry (tenacity) + Structured Outputs; storyboard.json; timings.json (lógica WPM + presupuesto por slide); script.json; cost_estimator para `--dry-run`; tests con mocks Anthropic.

**Uses:** `anthropic >=0.104.1`, `pydantic >=2.13.4`, `tenacity`.

**Avoids:** Pitfall #9 (JSON Claude no parseable) — patrón Structured Outputs establecido aquí para todo el pipeline.

### Phase 3: Slides Auto — Jinja2 + Playwright + Tema

**Rationale:** Las slides modo `auto` son el camino feliz de mayor impacto visual. Dependen de storyboard y script (Phase 2). Esta fase incluye el pitfall más sutil (fuentes Playwright) y debe validarse con un test de render de slide antes de seguir. Es donde se fija el patrón `sync_playwright` — elegir async aquí rompe todo lo construido después.

**Delivers:** `integrations/playwright.py` con sync_playwright, wait de fuentes, animations=disabled; slides_auto.py con Jinja2 + theme.yaml → HTML → PNG 1920x1080; template HTML base; iconos Lucide offline; test de smoke de render con fuente del tema.

**Uses:** `playwright >=1.60.0` (sync), `jinja2 >=3.1.6`, `python-lucide`, `pyyaml`.

**Avoids:** Pitfall #1 (fuentes no cargadas), Pitfall #2 (gráficos JS no renderizados), Anti-pattern async_playwright.

### Phase 4: Voz + Subtítulos — ElevenLabs + SRT/VTT

**Rationale:** La voz depende del script (Phase 2). Es donde se establece la validación de timestamps — el bug de timestamps congelados debe detectarse aquí, no en el montaje. Los subtítulos son lógica pura derivada de los timings.

**Delivers:** `integrations/elevenlabs.py` con convert_with_timestamps, validación de secuencia start_times, retry hasta 3 intentos; voice_elevenlabs.py → audio/slide_XX.mp3 + timings.json; subtitles.py → output.srt + output.vtt (timestamps en segundos decimales, framerate-independiente); calibración empírica de WPM documentada.

**Uses:** `elevenlabs >=2.49.0`.

**Avoids:** Pitfall #5 (timestamps congelados), Pitfall #4 (calibración WPM), Pitfall #8 (subtítulos desfasados por framerate).

### Phase 5: Montaje Final — FFmpeg + QA

**Rationale:** El montaje es la etapa de integración final. Aquí se resuelven los pitfalls de sincronía de crossfade y loudnorm — ambos requieren spikes de prueba con clip de test antes de integrar en el pipeline general. El pipeline end-to-end completo es verificable por primera vez en esta fase.

**Delivers:** `integrations/ffmpeg.py` fluent builder (subprocess list, sin shell=True, captura stderr); assemble.py con concat usando duraciones medidas por ffprobe, crossfade xfade/acrossfade verificado, quemado de subtítulos con paths escapados, flag `--burn-subs`; normalización loudness EBU R128 dos pasadas; qa.py → qa_report.json (duración real vs objetivo, LUFS medido); pipeline end-to-end funcional.

**Uses:** `ffmpeg >=6.1` (subprocess), `ffprobe`.

**Avoids:** Pitfall #3 (drift timing), Pitfall #6 (crossfade desincronizado), Pitfall #7 (loudnorm single-pass), Pitfall #8 (subtítulos desfasados).

### Phase 6: Slides Hybrid/Manual + Verificador Claude Vision (v1.x)

**Rationale:** Los modos hybrid/manual son diferenciadores pero se difieren porque no bloquean el pipeline base. El verificador con Claude Vision es el diferenciador competitivo más valioso del proyecto — ningún competidor lo implementa — y requiere que slides y guion estén estables para poder validarlo.

**Delivers:** slides_hybrid.py (propuesta JSON por slide + pausa orquestador); slides_manual.py (validación PNGs del usuario); verify_slides.py (rasterizado PyMuPDF/pdf2image → Claude Vision → VerificationReport JSON por slide); context.py (ingestión .pptx/.pdf/.md); integración de modos hybrid/manual en approval gates L1-L4.

**Uses:** `anthropic` (vision base64 PNG), `PyMuPDF >=1.27.2.3`, `pdf2image >=1.17.0`, `python-pptx >=1.0.2`.

### Phase 7: Docker + Empaquetado + Modo Record (v2)

**Rationale:** Docker es el último paso — las versiones deben estar pineadas antes de construir la imagen. WhisperX se separa en servicio Docker independiente para mantener la imagen principal ligera (~2 GB). El modo record (sounddevice + WhisperX) es v2 por su complejidad de dependencias (torch, CUDA, pyannote).

**Delivers:** Dockerfile principal (playwright:v1.60.0-noble + FFmpeg + Poppler); Dockerfile separado WhisperX (torch CUDA, modelos pre-descargados en build); README con instrucciones completas; voice_record.py + align.py + integrations/whisperx.py.

**Uses:** `sounddevice`, `soundfile`, `whisperx` (torch 2.5.1 pineado), Docker.

**Avoids:** Pitfall #11 (WhisperX imagen pesada), Pitfall #12 (Playwright version mismatch en Docker).

### Phase Ordering Rationale

- **Foundation primero (Phase 1):** El orquestador con checkpoints es la base de idempotencia. Construirlo antes de cualquier llamada a API externa permite validar la lógica de reanudación sin coste y sin mocking complejo.
- **LLM antes que renders (Phase 2 → 3):** El storyboard define el schema de slides. Las etapas de rendering dependen de storyboard.json — construir primero el contrato LLM evita iterar sobre el schema mientras Playwright ya está integrado.
- **Voz antes que montaje (Phase 4 → 5):** Los timestamps del audio son el input crítico del montaje. Validar el pitfall de timestamps congelados antes de construir el concat de FFmpeg evita bugs silenciosos de sincronía.
- **Verificador diferido (Phase 6):** Alto valor pero alta complejidad. Diferirlo a v1.x permite lanzar en modo `auto` con alta confianza, y añadir el verificador sobre una base estable.
- **Docker al final (Phase 7):** Las versiones deben estar pineadas antes de construir la imagen. Construir Docker primero lleva a iterar el Dockerfile continuamente mientras el stack evoluciona.

### Research Flags

Phases likely needing deeper research during planning:

- **Phase 5 (Montaje FFmpeg):** El crossfade xfade/acrossfade requiere un spike experimental con clip de test antes de integrar. Las duraciones relativas de los filtros no son simétricas por documentación y requieren verificación empírica. Recomendado: task de spike dedicada antes de la tarea de integración.
- **Phase 7 (Docker + WhisperX):** La instalación de torch con CUDA en Docker tiene combinaciones de versiones sensibles (torch 2.5.1 + CUDA 12.4 + pyannote.audio 3.3). Requiere verificar la matriz de compatibilidad en el momento de construcción del Dockerfile.

Phases with standard patterns (skip research-phase):

- **Phase 1 (Foundation):** Pydantic v2, typer, WorkdirManager — patrones bien documentados y verificados.
- **Phase 2 (LLM Pipeline):** Structured Outputs de Anthropic está documentado oficialmente. Tenacity para backoff es estándar.
- **Phase 3 (Playwright Slides):** sync_playwright + wait_for_function + animations=disabled está documentado en la guía oficial.
- **Phase 4 (ElevenLabs + Subtítulos):** convert_with_timestamps está documentado. Formato SRT en segundos decimales es estándar.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Todas las versiones verificadas en PyPI y fuentes oficiales; compatibilidades documentadas en tablas explícitas |
| Features | HIGH | Fundamentado en papers de investigación 2024-2025 (AutoLectures, PresentAgent) y análisis de competidores directos (SlideNarrator) |
| Architecture | HIGH | Patrones Protocol/Pydantic/checkpoint verificados contra fuentes oficiales; orden de construcción por capas documentado |
| Pitfalls | HIGH | Mayoría verificados contra issues reales de GitHub (ElevenLabs #607, Playwright #35972, WhisperX #1247) y documentación oficial |

**Overall confidence:** HIGH

### Gaps to Address

- **WPM efectivo de ElevenLabs en español:** El valor 150 WPM es una estimación. La calibración empírica debe ejecutarse como primera tarea de Phase 4 antes de fijar el presupuesto de palabras del guionista.
- **Compatibilidad torch + whisperx + pyannote.audio en Docker:** La cadena de dependencias es sensible. Usar torch==2.5.1 como ancla; verificar la matriz de compatibilidad al construir el Dockerfile de Phase 7.
- **Crossfade xfade/acrossfade sync empírica:** La documentación de FFmpeg no garantiza simetría temporal entre filtros de vídeo y audio. Requiere spike con clip de test en Phase 5 antes de integrar.
- **Tamaño de imagen para Claude Visión en verificador:** El pipeline envía PNGs 1920x1080 con deviceScaleFactor=2. Verificar preprocesado que respeta el límite de 20 MB y la dimensión máxima ~1568px que Claude Visión reduce internamente.

## Sources

### Primary (HIGH confidence)

- anthropic SDK Python (Context7) — visión base64, Structured Outputs, instalación — verificado 2026-05-25
- playwright-python (Context7) — Page.screenshot(), sync API, Docker — verificado 2026-05-25
- elevenlabs-python (Context7) — convert_with_timestamps, stream_with_timestamps — verificado 2026-05-25
- pydantic v2 (Context7) — BaseModel, model_dump_json(), model_validate_json() — verificado 2026-05-25
- typer (Context7) — app.callback(), subcomandos — verificado 2026-05-25
- https://pypi.org/project/anthropic/ — versión 0.104.1 verificada mayo 2026
- https://pypi.org/project/playwright/ — versión 1.60.0 verificada mayo 2026
- https://pypi.org/project/elevenlabs/ — versión 2.49.0 verificada mayo 2026
- https://pypi.org/project/pydantic/ — versión 2.13.4 verificada mayo 2026
- https://playwright.dev/docs/docker — imagen oficial Microsoft verificada
- https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps — endpoint verificado
- https://docs.claude.com/en/docs/build-with-claude/structured-outputs — disponible Sonnet 4.5+
- https://platform.claude.com/docs/en/build-with-claude/vision — límites de imagen verificados
- https://github.com/m-bain/whisperX — API verificada; torch 2.5.1 ancla de compatibilidad

### Secondary (MEDIUM confidence)

- https://arxiv.org/html/2505.02966v1 — AutoLectures (arXiv 2025): patrón pipeline narrado + TTS sync
- https://arxiv.org/html/2507.04036v1 — PresentAgent (arXiv 2024): comparación de enfoques de generación de presentaciones
- https://32blog.com/en/ffmpeg/ffmpeg-audio-normalization-loudnorm — procedimiento dos pasadas EBU R128
- https://gist.github.com/royshil/369e175960718b5a03e40f279b131788 — patrón crossfade xfade/acrossfade FFmpeg
- https://www.prefect.io/blog/the-importance-of-idempotent-data-pipelines-for-resilience — patrón done markers
- https://peps.python.org/pep-0544/ — justificación typing.Protocol sobre ABC

### Tertiary (LOW confidence — verificar en implementación)

- https://github.com/elevenlabs/elevenlabs-python/issues/607 — bug timestamps congelados; comportamiento no determinista
- https://github.com/jim60105/docker-whisperX — referencia Dockerfile multi-stage WhisperX + CUDA
- https://github.com/microsoft/playwright/issues/35972 — workaround espera de fuentes documentado en issues

---
*Research completed: 2026-05-25*
*Ready for roadmap: yes*
