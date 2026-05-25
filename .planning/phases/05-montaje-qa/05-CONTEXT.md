# Phase 5: Montaje + QA - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 5 monta el **vídeo final** y emite un **informe QA**. Con FFmpeg (subprocess, lista de args, nunca shell=True) sincroniza los PNG de slides (Phase 3) con los audios por slide (Phase 4) usando **duraciones reales medidas con ffprobe** (no estimadas por WPM), aplica **crossfade configurable** entre slides (xfade vídeo + acrossfade audio), normaliza loudness con **loudnorm dos pasadas (EBU R128)**, opcionalmente quema subtítulos (`--burn-subs`), y produce `workdir/output.mp4` (1080p 16:9 H.264) + `workdir/qa_report.json`. Sustituye el stub `assemble`. Depende de Phase 3 (slides) y Phase 4 (audio + subs).

</domain>

<decisions>
## Implementation Decisions

### Montaje FFmpeg (ASMB-01, ASMB-02, ASMB-03)
- **D-01** **Un único filtergraph FFmpeg**: por cada slide, un segmento imagen (PNG en loop) + su audio; encadenados con **xfade (vídeo)** + **acrossfade (audio)** → salida **1080p 16:9 H.264** (`libx264`, pix_fmt yuv420p, `+faststart`).
- **D-02** Las **duraciones por segmento se miden con `ffprobe`** sobre los audios reales de `workdir/audio/` (NO se usan las estimaciones WPM de timings.json). Cada slide dura lo que dura su audio.
- **D-03** **Crossfade activado por defecto** ~0.5 s, **configurable en config.yaml** (`crossfade_seconds`, 0 lo desactiva → cortes secos). El offset de xfade se calcula acumulando (duración_segmento − crossfade) para sincronía A/V.
- **D-04** Invocación FFmpeg por `subprocess` con **lista de args** (nunca `shell=True`); fluent builder en `integrations/ffmpeg.py`; captura de stderr para diagnóstico; errores claros (Rich), no traceback.
- **D-05** Quemado de subtítulos **opcional** vía `--burn-subs`: cuando está activo, filtro `subtitles` (libass) sobre el vídeo usando `workdir/subs/output.srt`. Por defecto OFF (vídeo limpio + sidecar .srt/.vtt de Phase 4).

### QA (QA-01, QA-02)
- **D-06** **loudnorm dos pasadas** (EBU R128): 1ª pasada mide (`-af loudnorm=...:print_format=json`, parseo del JSON de stderr), 2ª pasada aplica con `measured_*` → target **-16 LUFS** (configurable `target_lufs`).
- **D-07** `workdir/qa_report.json`: **desviación duración real vs objetivo** (ffprobe sobre output.mp4 vs `RunConfig.duration`) + **nivel LUFS medido y normalizado** (input_i / output_i de loudnorm). Modelo Pydantic `QAReport`.
- **D-08** El informe QA se muestra también en la terminal con Rich (tabla legible).

### Integración con el pipeline
- **D-09** `integrations/ffmpeg.py` (builder + run + ffprobe helpers) + `stages/assemble.py` (montaje) + `stages/qa.py` (informe). La etapa `assemble` real reemplaza el stub respetando StageProtocol y el checkpoint (`output.mp4` + `assembly.json`). QA puede ser parte de assemble o una etapa/paso posterior que escribe `qa_report.json`.
- **D-10** Reanudable/idempotente: si `output.mp4` + checkpoint existen, no se re-monta. Escritura atómica del checkpoint JSON; el mp4 se escribe a tmp y se renombra.

### Claude's Discretion
- Estructura exacta del filtergraph (cómo encadenar N xfade/acrossfade), flags finos de libx264 (crf/preset por defecto, p. ej. crf 20 / preset medium), formato exacto de `QAReport`, si QA es etapa separada o sub-paso de assemble, manejo del caso 1 sola slide (sin crossfade) — a criterio de Claude siguiendo estas decisiones y CLAUDE.md.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/avideo/models/slides.py` (`SlidesOutput.png_paths`), `src/avideo/models/voice.py` (`VoiceOutput` — audios por slide), `src/avideo/models/subtitles.py` (`SubtitlesOutput` — srt/vtt paths), `src/avideo/models/timing.py` (referencia de duración objetivo) — entradas de Phase 5.
- `src/avideo/models/assembly.py` (`AssemblyOutput`) — contrato de salida del montaje (Phase 1 stub) a implementar.
- `src/avideo/orchestrator.py` + `stages/base.py` — StageProtocol/CheckpointMixin; la etapa `assemble` se enchufa aquí (último stub funcional junto con `verify` de Phase 6).
- `src/avideo/utils/workdir.py` — `WorkdirManager`; `output.mp4` es la salida final; `audio/`, `slides/`, `subs/` ya existen.
- `src/avideo/models/config.py` — `RunConfig`: añadir `crossfade_seconds` (default ~0.5) y `target_lufs` (default -16); `burn_subs` ya existe.
- Decisión STATE.md: FFmpeg por subprocess con lista de args (nunca shell=True); fluent builder en integrations/ffmpeg.py. Crossfade requiere cuidado (spike) — la investigación debe validar el filtergraph xfade/acrossfade.

### Established Patterns
- Pydantic v2, tipado, docstrings, errores Rich, idempotencia por checkpoint.
- Tests con pytest; FFmpeg se invoca por subprocess — en tests se mockea subprocess/ffprobe (no se codifica vídeo real en CI); la lógica pura (cálculo de offsets xfade, parseo loudnorm JSON, cálculo de desviación) se testea sin FFmpeg.

### Integration Points
- Lee `workdir/slides/slide_XX.png`, `workdir/audio/slide_XX.{mp3|wav}`, `workdir/subs/output.srt`. Escribe `workdir/output.mp4` + `workdir/qa_report.json`.
- Nuevo: `integrations/ffmpeg.py`, `stages/assemble.py`, `stages/qa.py`, `models` para `QAReport` (y enriquecer `AssemblyOutput`).
- Requiere binario `ffmpeg`/`ffprobe` en el sistema (documentar para Phase 7 Docker: `apt-get install ffmpeg`).

</code_context>

<specifics>
## Specific Ideas

- Success criteria: `output.mp4` 1080p 16:9 sincronizando slides+audios con duraciones reales ffprobe; crossfade configurable; `qa_report.json` con desviación duración real vs objetivo y LUFS medido/normalizado (EBU R128, dos pasadas).
- FFmpeg por subprocess con lista de args (seguridad: nunca shell=True).
- Caso borde: 1 sola slide → sin crossfade.

</specifics>

<deferred>
## Deferred Ideas

- Salida 9:16 vertical (FMT-01, v2) — fuera de alcance.

</deferred>
