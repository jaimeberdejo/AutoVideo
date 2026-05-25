# Roadmap: Auto Video Narrado

## Overview

Pipeline CLI en Python que transforma bullets + duración en un vídeo narrado (slides 1080p, voz ElevenLabs, subtítulos SRT/VTT, montaje FFmpeg). La construcción sigue un orden estrictamente bottom-up: primero la fundación (orquestador + modelos Pydantic + CLI), luego las etapas LLM, luego el render de slides, luego voz y subtítulos, luego el montaje final, y por último los modos avanzados (hybrid/manual + verificador) y el empaquetado. Cada fase entrega una capacidad coherente y verificable de forma independiente.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation** - Orquestador secuencial + CLI typer + modelos Pydantic + WorkdirManager + niveles L1-L4 (pipeline end-to-end con stubs) (completed 2026-05-25)
- [x] **Phase 2: LLM Pipeline** - Ingesta de contexto + Storyboard (Claude) + Director de timing + Guionista (Claude) (completed 2026-05-25)
- [ ] **Phase 3: Slides Auto** - Jinja2 + Playwright → PNG 1920×1080 + theme.yaml + iconos SVG offline (modo `auto`)
- [ ] **Phase 4: Voz + Subtítulos** - ElevenLabs TTS con timestamps + modo record + WhisperX (alineación) + SRT/VTT
- [ ] **Phase 5: Montaje + QA** - FFmpeg concat + crossfade + loudnorm + quemado de subtítulos + informe QA
- [ ] **Phase 6: Slides Hybrid/Manual + Verificador** - Propuesta de diseño + ingesta de slides del usuario + verificador Claude Vision
- [ ] **Phase 7: Empaquetado + Tests + Docs** - pyproject.toml/uv + Dockerfile + pytest mínimos + README

## Phase Details

### Phase 1: Foundation
**Goal**: El pipeline completo puede ejecutarse de extremo a extremo con etapas stub — CLI acepta todos los flags, el orquestador gestiona checkpoints reanudables e idempotentes, y los niveles L1-L4 controlan las pausas de aprobación
**Depends on**: Nothing (first phase)
**Requirements**: CLI-01, CLI-02, CLI-03, CLI-04, CLI-05, CLI-06, CLI-07, CLI-08, ORCH-01, ORCH-02, ORCH-03, ORCH-04, ORCH-05
**Success Criteria** (what must be TRUE):
  1. El usuario puede ejecutar `avideo generate --bullets bullets.yaml --duration 120` y el pipeline recorre todas las etapas (con stubs) sin error
  2. El usuario puede interrumpir el pipeline a mitad, relanzarlo, y las etapas ya completadas se saltan (checkpoint reanudable verificado con doble ejecución)
  3. El usuario puede ejecutar con `--level 1` y el pipeline pausa tras cada etapa para pedir aprobación; con `--level 4` nunca pausa
  4. El usuario puede ejecutar `--dry-run` y recibe una estimación de coste/tokens sin generar audio ni vídeo
  5. La configuración se carga de `config.yaml` y los flags de CLI la sobreescriben; errores de validación Pydantic se muestran con mensaje claro
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md — Bootstrap uv/Python 3.11 + modelos Pydantic (RunConfig + contratos I/O de todas las etapas) + WorkdirManager (escritura atómica os.replace, done markers)
- [x] 01-02-PLAN.md — CLI typer (`generate` con los 9 flags) + merge config.yaml (CLI>YAML>default) + ValidationError→tabla Rich + setup_logging
- [x] 01-03-PLAN.md — Orquestador secuencial (StageProtocol/CheckpointMixin, 10 stubs, skip-done, approval gates L1-L4) + cost_estimator --dry-run + RichUI pause/progress + checkpoint de aceptación

### Phase 2: LLM Pipeline
**Goal**: A partir de bullets y duración el sistema genera un storyboard estructurado, calcula la distribución de tiempo por slide con presupuesto de palabras, y produce el guion completo calibrado — todo persistido como JSON validado con Pydantic
**Depends on**: Phase 1
**Requirements**: CTX-01, CTX-02, STORY-01, STORY-02, TIME-01, TIME-02, SCRIPT-01, SCRIPT-02
**Success Criteria** (what must be TRUE):
  1. El usuario puede aportar un `.pdf` o `.pptx` con `--context` y el sistema extrae su texto como material de referencia; sin `--context` el pipeline funciona igual
  2. El sistema genera `workdir/storyboard.json` con estructura de slides (título, puntos, tipo de visual) validado por Pydantic — el pipeline es reanudable desde este checkpoint
  3. El sistema calcula `workdir/timings.json` con duración por slide y presupuesto de palabras (WPM configurable, por defecto 150) — la suma de duraciones iguala la duración objetivo
  4. El sistema genera `workdir/script.json` con narración por slide en español, ajustada al presupuesto de palabras y con tono natural para locución
**Plans**: 3 plans

Plans:
- [x] 02-01-PLAN.md — [Wave 1] Ingestor de contexto (PyMuPDF/python-pptx/markdown → ContextOutput) + loader compartido bullets.yaml (BulletsInput + load_bullets, cierra el gap de bullets nunca parseados) + deps anthropic/PyMuPDF/python-pptx
- [x] 02-02-PLAN.md — [Wave 2] integrations/anthropic.py (cliente lazy max_retries=3 + helper call_structured tool-use→Pydantic) + VisualType enum + stages/storyboard.py → StoryboardOutput
- [x] 02-03-PLAN.md — [Wave 3] stages/timing.py (largest-remainder, suma exacta + clamps) + stages/scriptwriter.py (whole-script + 1 reintento de calibración) + cost_estimator offline real + swap final de stubs en PIPELINE_STAGES

### Phase 3: Slides Auto
**Goal**: En modo `auto`, cada slide del storyboard se renderiza a PNG 1920×1080 píxeles con calidad pixel-perfect usando HTML/CSS + Playwright — con tema parametrizable en `theme.yaml` e iconos SVG Lucide servidos offline
**Depends on**: Phase 2
**Requirements**: SLIDE-01, SLIDE-02, SLIDE-03
**Success Criteria** (what must be TRUE):
  1. El usuario puede lanzar el pipeline en modo `--slides-mode auto` y obtiene un PNG 1920×1080 por slide en `workdir/slides/` con las fuentes del tema cargadas correctamente
  2. Las slides usan únicamente iconos SVG Lucide/Heroicons servidos offline (sin CDN) y gráficos generados por código — ningún elemento externo descargado en runtime
  3. El tema (paleta, tipografías, espaciado) se lee de `theme.yaml` y la IA propone un tema coherente con el contenido; el usuario puede sobreescribirlo editando el archivo
**Plans**: TBD

Plans:
- [ ] 03-01: integrations/playwright.py (sync_playwright, wait_for_function fonts.ready, animations=disabled) + template HTML base (Jinja2) + theme.yaml
- [ ] 03-02: stages/slides_auto.py (Jinja2 → HTML → Playwright → PNG por slide; iconos Lucide offline) + test de smoke de render

### Phase 4: Voz + Subtítulos
**Goal**: El pipeline genera audio sincronizado por slide (ElevenLabs con timestamps o grabación del usuario) y produce subtítulos `.srt`/`.vtt` listos para el montaje
**Depends on**: Phase 2
**Requirements**: VOICE-01, VOICE-02, VOICE-03, ALIGN-01, ALIGN-02, SUB-01, SUB-02
**Success Criteria** (what must be TRUE):
  1. En modo `--voice elevenlabs`, el sistema genera un clip de audio por slide en `workdir/audio/` con timestamps de carácter validados (secuencia estrictamente creciente); si los timestamps están congelados, reintenta hasta 3 veces
  2. En modo `--voice record`, el sistema exporta el guion segmentado y permite grabar con `sounddevice` o aportar `slide_XX.wav` — los archivos ingestados se detectan automáticamente
  3. En modo `record`, WhisperX alinea el audio y produce timings por palabra; en modo `elevenlabs` la alineación no se ejecuta
  4. El sistema siempre genera `workdir/subs/output.srt` y `output.vtt` a partir de los timings — el quemado en vídeo es opcional mediante flag `--burn-subs`
**Plans**: TBD

Plans:
- [ ] 04-01: integrations/elevenlabs.py (convert_with_timestamps, validación de secuencia start_times, retry) + stages/voice_elevenlabs.py → audio/ + timings
- [ ] 04-02: stages/voice_record.py (exportar guion segmentado, ingestar slide_XX.wav) + integrations/whisperx.py + stages/align.py → word-level timings
- [ ] 04-03: stages/subtitles.py (timings → SRT/VTT, lógica pura) + flag --burn-subs registrado en RunConfig

### Phase 5: Montaje + QA
**Goal**: El pipeline monta el vídeo final 1080p 16:9 sincronizando slides + audios con FFmpeg (duraciones reales medidas por ffprobe), aplica crossfade configurable y loudnorm, y emite un informe QA con desviación de duración y nivel LUFS
**Depends on**: Phase 3, Phase 4
**Requirements**: ASMB-01, ASMB-02, ASMB-03, QA-01, QA-02
**Success Criteria** (what must be TRUE):
  1. El pipeline produce `workdir/output.mp4` en 1080p 16:9 sincronizando slides y audios usando las duraciones reales medidas por ffprobe (no estimadas por WPM)
  2. El vídeo final aplica transiciones crossfade configurables entre slides (parámetro en config.yaml)
  3. El informe QA (`workdir/qa_report.json`) muestra la desviación entre duración real y objetivo, y el nivel LUFS medido y normalizado (EBU R128, dos pasadas)
**Plans**: TBD

Plans:
- [ ] 05-01: integrations/ffmpeg.py (fluent builder subprocess, captura stderr, spike crossfade xfade/acrossfade) + stages/assemble.py (concat duraciones reales ffprobe, crossfade, burn-subs opcional)
- [ ] 05-02: stages/qa.py (ffprobe duración real vs objetivo, loudnorm dos pasadas) + qa_report.json + display QA en RichUI

### Phase 6: Slides Hybrid/Manual + Verificador
**Goal**: Los modos `hybrid` y `manual` permiten que el usuario aporte sus propias slides; el verificador usa Claude con visión para auditar cobertura, fidelidad y encaje con el guion — con comportamiento diferenciado según el nivel L1-L4
**Depends on**: Phase 3, Phase 5
**Requirements**: SLIDE-04, SLIDE-05, VERIFY-01, VERIFY-02, VERIFY-03
**Success Criteria** (what must be TRUE):
  1. En modo `--slides-mode hybrid`, el sistema genera una propuesta de diseño JSON por slide en `workdir/design_proposal/` y el pipeline pausa para que el usuario aporte las slides
  2. En modo `--slides-mode manual`, el pipeline valida que `workdir/slides_user/` contiene los PNGs completos antes de continuar
  3. El verificador Claude Vision emite `workdir/verification_report.json` con estado `ok`/`warning`/`fail` por slide, problemas detectados y sugerencias concretas
  4. Con `--level 1` o `--level 2`, el pipeline muestra el informe y pausa para iteración (corregir→re-verificar); con `--level 3`/`4` continúa si todo es `ok` y solo para si hay `fail`; en modo `auto` el verificador no se ejecuta
**Plans**: TBD

Plans:
- [ ] 06-01: stages/slides_hybrid.py (propuesta diseño JSON por slide con Claude, pausa orquestador) + stages/slides_manual.py (validación PNGs del usuario)
- [ ] 06-02: stages/verify_slides.py (rasterizado PyMuPDF/pdf2image, Claude Vision, VerificationReport) + integración approval gates L1-L4 en orquestador
**UI hint**: yes

### Phase 7: Empaquetado + Tests + Docs
**Goal**: El proyecto se puede instalar con `uv`, ejecutar reproduciblemente en Docker, tiene tests mínimos que validan el core del pipeline, y un README con instrucciones de instalación completas
**Depends on**: Phase 6
**Requirements**: PKG-01, PKG-02, TEST-01, TEST-02, TEST-03, DOC-01
**Success Criteria** (what must be TRUE):
  1. El proyecto se instala con `uv sync` y el comando `avideo` está disponible en el entorno; `uv.lock` es reproducible entre plataformas
  2. El Dockerfile construye una imagen que incluye navegadores Playwright (versión pineada), FFmpeg y Poppler — el pipeline completo en modo `auto` funciona dentro del contenedor
  3. `pytest` pasa los tres tests mínimos: storyboard con API mockeada, director de timing (reparto + presupuesto), render de una slide a PNG
  4. El README explica la instalación (Playwright browsers, FFmpeg, WhisperX), la configuración de claves API y ejemplos de uso con los flags principales
**Plans**: TBD

Plans:
- [ ] 07-01: pyproject.toml (uv, entry point avideo, dependencias pineadas) + Dockerfile (playwright:v1.60.0-noble + FFmpeg + Poppler)
- [ ] 07-02: tests/test_storyboard.py (mock Anthropic) + tests/test_timing.py + tests/test_slides_render.py (smoke PNG)
- [ ] 07-03: README.md (instalación, configuración, ejemplos de uso)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 3/3 | Complete    | 2026-05-25 |
| 2. LLM Pipeline | 3/3 | Complete   | 2026-05-25 |
| 3. Slides Auto | 0/2 | Not started | - |
| 4. Voz + Subtítulos | 0/3 | Not started | - |
| 5. Montaje + QA | 0/2 | Not started | - |
| 6. Slides Hybrid/Manual + Verificador | 0/2 | Not started | - |
| 7. Empaquetado + Tests + Docs | 0/3 | Not started | - |
