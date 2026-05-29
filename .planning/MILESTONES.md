# Milestones

## v1.60.0 MVP Pipeline (Shipped: 2026-05-29)

**Phases completed:** 7 phases, 18 plans, 22 tasks
**Git range:** d510858 (init) → d10120d · 142 commits · ~7,148 LOC Python · 28 test files (303 tests passing)
**Timeline:** 2026-05-25 → 2026-05-26 (execution); archived 2026-05-29

**Delivered:** El pipeline `avideo generate` produce un vídeo narrado completo (slides + voz + subtítulos sincronizados) a partir de bullets + duración, sin intervención manual obligatoria y con checkpoints opcionales (niveles L1–L4).

**Key accomplishments:**

- **Foundation (Phase 1):** orquestador secuencial propio con checkpoints reanudables/idempotentes (escritura atómica tmp→rename), CLI `typer` con todos los flags, modelos Pydantic tipados para la I/O de cada etapa, y niveles de automatización L1–L4 con `--dry-run` para estimación de coste.
- **LLM Pipeline (Phase 2):** ingesta opcional de contexto (`.pdf`/`.pptx`/`.md`), storyboard generado con Claude → JSON validado, director de timing (largest-remainder con suma exacta + presupuesto de palabras por WPM), y guionista calibrado a la duración.
- **Slides `auto` (Phase 3):** render pixel-perfect Jinja2 + Playwright → PNG 1920×1080, tema parametrizable en `theme.yaml`, iconos SVG Lucide servidos 100% offline (sin CDN).
- **Voz + Subtítulos (Phase 4):** TTS ElevenLabs con timestamps por carácter (validación estrictamente-creciente + retry), modo `record` con WhisperX para alineación palabra-a-palabra, y subtítulos `.srt`/`.vtt` siempre generados.
- **Montaje + QA (Phase 5):** montaje FFmpeg por subprocess (duraciones reales por ffprobe), crossfade configurable, loudnorm EBU R128 de dos pasadas, salida 1080p 16:9, e informe QA (desviación de duración + LUFS).
- **Slides `hybrid`/`manual` + Verificador (Phase 6):** propuestas de diseño por slide, ingesta de slides del usuario (PNG/PDF), y verificador Claude Vision (informe `ok`/`warning`/`fail` por slide) con comportamiento diferenciado por nivel L1–L4.
- **Empaquetado + Tests + Docs (Phase 7):** instalación con `uv` + entry point `avideo`, `Dockerfile` reproducible (Playwright 1.60.0 pineado + FFmpeg + Poppler), 303 tests verdes (API/binarios mockeados), y README de instalación y uso.

**Requirements:** 43/43 in-scope complete. Deferred to v2: EXPORT-01 (.pptx export), FMT-01 (9:16 vertical), BRAND-01 (custom theme override).

**Archived:** `milestones/v1.60.0-ROADMAP.md`, `milestones/v1.60.0-REQUIREMENTS.md`, `milestones/v1.60.0-MILESTONE-AUDIT.md` (verdict: PASSED).

---
