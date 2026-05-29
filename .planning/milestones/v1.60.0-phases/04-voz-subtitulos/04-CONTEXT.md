# Phase 4: Voz + Subtítulos - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 4 genera el **audio por slide** y los **subtítulos** del vídeo. Dos modos de voz: `elevenlabs` (TTS con timestamps por carácter, sin alineación posterior) y `record` (exportar guion segmentado + grabar con sounddevice o aportar `slide_XX.wav`, luego alinear con WhisperX). Siempre produce `output.srt` y `output.vtt` a partir de los timings; el quemado en vídeo es opcional (flag, se aplica en Phase 5). Sustituye los stubs `voice`, `align`, `subs`. Depende solo de Phase 2 (necesita `script.json` y `timings.json`). Puede construirse en paralelo con Phase 3.

</domain>

<decisions>
## Implementation Decisions

### Voz — ElevenLabs (VOICE-01, VOICE-02, ALIGN-02)
- **D-01** Modo `elevenlabs`: un clip de audio por slide usando `convert_with_timestamps()`, modelo `eleven_multilingual_v2`, `voice_id` configurable (placeholder en `config.yaml`). Output: `workdir/audio/slide_XX.mp3` (decodificado de base64) + timings por slide.
- **D-02** **Validación de timestamps estrictamente crecientes** antes de guardar el checkpoint (mitiga el bug de timestamps "congelados", #607): si la secuencia no es estrictamente creciente, **reintenta hasta 3 veces**; si sigue mal, error claro / fallback marcado.
- **D-03** En modo `elevenlabs` **NO se ejecuta alineación** (los timings vienen del API). `ELEVENLABS_API_KEY` se lee del entorno.

### Voz — Record + WhisperX (VOICE-03, ALIGN-01)
- **D-04** Modo `record`: exporta el guion **segmentado por slide** (texto que el usuario va a locutar) y permite (a) grabar con `sounddevice` → `soundfile.write()` a `slide_XX.wav`, o (b) **aportar** `workdir/audio/slide_XX.wav` ya grabados (autodetección de los archivos presentes).
- **D-05** Alineación con **WhisperX**, modelo por defecto **`small`** (balance CPU/precisión), **configurable** (p. ej. `large-v3` para GPU). Produce timings **palabra a palabra**.
- **D-06** WhisperX solo se ejecuta en modo `record`. La importación de whisperx/torch es **perezosa** (solo se importa cuando se usa) para no penalizar el modo `elevenlabs` ni el arranque.

### Subtítulos (SUB-01, SUB-02)
- **D-07** **Siempre** genera `workdir/subs/output.srt` y `output.vtt` a partir de los timings (de ElevenLabs o de WhisperX, unificados a un formato interno de timings por palabra/segmento).
- **D-08** **Segmentación de subtítulos**: agrupar timestamps de carácter/palabra en **líneas de subtítulo legibles** (~42 caracteres por línea, ≤2 líneas, ≤5 s por cue). Lógica pura y testeable.
- **D-09** El **quemado** de subtítulos en el vídeo es **opcional** vía flag `--burn-subs` (ya registrado en `RunConfig` en Phase 1); el quemado real ocurre en el montaje (Phase 5). Phase 4 solo deja los .srt/.vtt listos.

### Integración y robustez
- **D-10** `integrations/elevenlabs.py` encapsula el cliente y `convert_with_timestamps` + validación de secuencia + retry. `integrations/whisperx.py` encapsula carga de modelo + alineación (import perezoso). Etapas: `stages/voice_elevenlabs.py`, `stages/voice_record.py`, `stages/align.py`, `stages/subtitles.py`.
- **D-11** Un **formato interno de timings unificado** (Pydantic) que ambos caminos (elevenlabs / whisperx) producen, para que `subtitles.py` sea agnóstico de la fuente.
- **D-12** Las etapas reales reemplazan los stubs `voice`/`align`/`subs` en el orquestador respetando StageProtocol y los nombres de checkpoint. La selección de etapa de voz depende de `RunConfig.voice`.

### Claude's Discretion
- Estructura exacta del formato interno de timings, parámetros finos de segmentación de subtítulos, UX concreta de la grabación con sounddevice, formato del guion segmentado exportado, manejo de mp3 vs wav — a criterio de Claude siguiendo estas decisiones y CLAUDE.md.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/avideo/models/script.py` (`ScriptOutput`) y `src/avideo/models/timing.py` (`TimingOutput`) — entradas de Phase 4 (qué narrar y cuánto debe durar/word budget).
- `src/avideo/models/voice.py` — contrato de salida de voz (Phase 1 stub) a implementar.
- `src/avideo/orchestrator.py` + `stages/base.py` — StageProtocol/CheckpointMixin; las etapas voice/align/subs se enchufan aquí; la voz elige etapa según `RunConfig.voice`.
- `src/avideo/utils/workdir.py` — `WorkdirManager` ya crea `audio/` y `subs/`.
- `src/avideo/models/config.py` — `RunConfig` ya expone `voice`, `burn_subs`, `language`; añadir `voice_id` y `whisperx_model` configurables (vía config.yaml, prefijo `AVIDEO_`).

### Established Patterns
- Pydantic v2, tipado, docstrings, errores Rich, idempotencia por checkpoint.
- Tests con pytest + pytest-mock; las llamadas a ElevenLabs y WhisperX se **mockean** (sin red ni audio real en CI).
- Decisión STATE.md: validar timestamps estrictamente crecientes antes de checkpoint (#607).

### Integration Points
- Lee `workdir/script.json` + `workdir/timings.json` (Phase 2). Escribe `workdir/audio/slide_XX.{mp3|wav}`, timings internos, y `workdir/subs/output.{srt,vtt}`.
- Nuevo: `integrations/elevenlabs.py`, `integrations/whisperx.py`, `stages/voice_elevenlabs.py`, `stages/voice_record.py`, `stages/align.py`, `stages/subtitles.py`, modelo de timings internos.
- whisperx/torch + sounddevice/soundfile: dependencias pesadas/de sistema; import perezoso; documentar para Phase 7 Docker (torch CPU, portaudio).

</code_context>

<specifics>
## Specific Ideas

- Success criteria: `--voice elevenlabs` genera audio por slide con timestamps validados (estrictamente crecientes, retry ≤3); `--voice record` exporta guion segmentado y autodetecta `slide_XX.wav`; en `record` WhisperX alinea por palabra, en `elevenlabs` no se alinea; siempre se generan `output.srt` y `output.vtt`; quemado opcional vía `--burn-subs`.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
