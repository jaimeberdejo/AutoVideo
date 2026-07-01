# Milestones

## v2.0.0 Studio Guiado (Shipped: 2026-07-01)

**Phases completed:** 6 phases, 23 plans, 15 tasks

**Key accomplishments:**

- 21 RED test scaffolds covering OpenAI TTS stage (VOZ-02), FFmpeg audio enhancement (VOZ-03), and background music mix builder (EXT-02/EXT-03) — all using deferred imports so they collect without error before implementation modules exist
- Additive Pydantic model layer additions — VoiceMode.openai enum value + 5 new RunConfig fields (openai_tts_model, openai_tts_voice, bg_music_path, bg_music_volume, bg_music_fade_out_s) + openai>=2.38.0 in production deps.
- OpenAI Audio TTS + whisper-1 STT round-trip voice provider with lazy client singleton, 4096-char guard, and word-level UnifiedTimings output.
- `enhance_audio(in_path, out_path)` standalone FFmpeg wrapper applying `afftdn=nr=6:nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11` conservatively — non-destructive, no model files, shell=False enforced.
- 1. [Rule 1 - Bug] Fixed test factory call ordering + loudnorm detection in test_ffmpeg_music.py
- Three RED TDD scaffold files define contracts for invalidate_downstream (workdir), PipelineBridge thread lifecycle, and wizard-phase reconstruction from done-markers.
- STAGE_ORDER constant + invalidate_downstream safety method added to WorkdirManager; avideo studio subcommand wires streamlit launch; streamlit>=1.58.0 added to deps; all 5 RED tests go GREEN; 339 total tests pass.
- Streamlit-agnostic wizard state module (PHASES + workdir phase reconstruction) and PipelineBridge (RunStatus enum + daemon thread launcher) — 11 RED tests turned GREEN.
- Real Fase 1 Contenido page — topic+duration form, manual/Claude-generate radio, dynamic data_editor, approval writes bullets.yaml in engine format and marks context done.
- Thin UI-layer module with five helpers — single-stage rerun wrappers for scriptwriter and slides, checkpoint persistence with downstream invalidation, path-traversal-safe upload writer, and emoji badge mapper — turning 9 RED tests GREEN with 370 total passing.
- Full narration-script wizard page: auto-runs storyboard+timing+scriptwriter on entry with live progress, per-slide text_area editor with save/invalidate, scriptwriter-only variation, and approval gate.
- Full SLD-01/02/03 Streamlit wizard page for slide generation (auto mode with PNG thumbnails and QC badges) and manual upload (Claude Vision per-slide verification with re-upload support).
- 11 RED tests defining contracts for rerun_voice, write_uploaded_audio, and audio_gate_ready — all using deferred imports, collected cleanly against 370 baseline
- Three voice-layer helpers — rerun_voice, write_uploaded_audio, audio_gate_ready — added to pipeline_ops.py, turning 11 RED tests GREEN (381 total passing).
- Real Fase 4 Voz page replacing placeholder — three TTS providers (ElevenLabs/OpenAI/record), bridge polling with per-slide st.audio previews, non-destructive enhance BEFORE/AFTER, timings-valid gate.
- 9 RED tests locking contracts for write_uploaded_music / extras_to_run_config / read_qa_report before any implementation.
- Three pipeline_ops helpers (write_uploaded_music, extras_to_run_config, read_qa_report) + real Fase 5 Extras wizard page implementing EXT-01 with burn_subs toggle, music upload/preview/volume, and crossfade slider.
- Dockerfile gets EXPOSE 8501 + headless studio launch docs; 7 page-import smoke tests confirm all 6 wizard pages loadable; 397 tests green.

---

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
