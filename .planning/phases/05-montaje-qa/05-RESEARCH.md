# Phase 5: Montaje + QA - Research

**Researched:** 2026-05-25
**Domain:** FFmpeg assembly (xfade/acrossfade crossfade filtergraph, two-pass loudnorm EBU R128, libass subtitle burn-in), ffprobe duration measurement, subprocess arg-list invocation, QA reporting
**Confidence:** HIGH — the hard parts (filtergraph, loudnorm, edge cases) were verified empirically against the local ffmpeg 8.0.1.

## Summary

Phase 5 replaces the `assemble` stub with a real FFmpeg pipeline that stitches per-slide PNGs (Phase 3) and per-slide audio (Phase 4) into a single 1080p 16:9 H.264 MP4, applies a configurable crossfade between slides, normalizes loudness to -16 LUFS with two-pass EBU R128 `loudnorm`, optionally burns subtitles via libass, and emits a `qa_report.json`. The known-hard part — the `xfade`(video) + `acrossfade`(audio) crossfade filtergraph for N segments — was the explicit spike concern in STATE.md and has now been **verified empirically** with 2-, 3-, and 4-slide chains, plus single-slide, odd-dimension, crossfade=0, and short-audio edge cases.

The verified architecture is a **three-invocation flow**: (1) `ffprobe` each audio file for its real duration; (2) one `ffmpeg` build call producing the assembled MP4 (scale+pad each image to exactly 1920×1080, chain `xfade`/`acrossfade` with computed offsets, encode H.264/AAC); (3) two-pass `loudnorm` (measure→apply). Loudness normalization runs as a separate measure pass then an apply pass that copies video (`-c:v copy`) and only re-encodes audio — fast and lossless for the picture. The crossfade offset for the k-th join is `offset_k = (cumulative duration of the merged stream so far) - crossfade`, which I confirmed produces exact durations (`sum(durations) - (N-1)*crossfade`, ±1 frame).

**Primary recommendation:** Build `integrations/ffmpeg.py` as a thin, mockable subprocess wrapper (arg-list builder + `run_ffmpeg` + `probe_duration` + `parse_loudnorm_json`), keep ALL math/parsing as pure functions (offset chain, loudnorm JSON parse, duration deviation), and put exactly ONE real-encode smoke test behind a `shutil.which("ffmpeg")` guard. Use the verified filtergraph strings in this document verbatim. When `crossfade == 0`, switch to the `concat` filter path (hard cuts) — do NOT pass `xfade` with offset 0. When a slide is shorter than the crossfade, clamp the crossfade per-boundary to `min(crossfade, prev_dur, next_dur)`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Measure real audio durations | `integrations/ffmpeg.py` (ffprobe wrapper) | — | Single place that shells out to ffprobe; returns floats |
| Build filtergraph string + offset math | `integrations/ffmpeg.py` (pure builder) | `stages/assemble.py` | Pure string/number logic, fully unit-testable without ffmpeg |
| Run ffmpeg (subprocess, arg list) | `integrations/ffmpeg.py` (`run_ffmpeg`) | — | The ONLY module that calls `subprocess.run` for ffmpeg; captures stderr |
| Orchestrate assembly (read checkpoints, write output.mp4) | `stages/assemble.py` | `integrations/ffmpeg.py` | StageProtocol stage; reads slides/voice/subs checkpoints, drives the builder |
| Two-pass loudnorm (measure + apply) | `integrations/ffmpeg.py` (commands) + pure JSON parse | `stages/qa.py` | Parsing is pure; running is the wrapper; QA stage decides target |
| QA report (deviation + LUFS) | `stages/qa.py` | `models/assembly.py` (`QAReport`) | Pure deviation calc + Pydantic model; ffprobe final duration via wrapper |
| Subtitle burn-in (libass) | `integrations/ffmpeg.py` (filter) | `stages/assemble.py` | Burn is a `-vf subtitles=` option toggled by `config.burn_subs` |
| Checkpoint / idempotence (output.mp4 + assembly.json) | `WorkdirManager` + orchestrator | `stages/assemble.py` | Existing atomic-write + done-marker machinery (do not reinvent) |

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ASMB-01 | Monta el vídeo con FFmpeg (subprocess) sincronizando slides + audios usando duraciones reales medidas con `ffprobe` (no WPM) | Verified `ffprobe -show_entries format=duration -of json/csv` per audio (Pattern 2); verified the full build filtergraph drives slide length from these durations (Pattern 1, 3-slide + 4-slide runs) |
| ASMB-02 | Aplica transiciones crossfade configurables entre slides | Verified `xfade`+`acrossfade` chain with computed offsets (Pattern 1); crossfade=0→concat path (Edge Case 3); short-slide clamping (Edge Case 4 + mitigation) |
| ASMB-03 | La salida por defecto es 1080p 16:9 | Verified output is exactly 1920×1080, SAR 1:1, yuv420p, H.264 via `scale=...:force_original_aspect_ratio=decrease,pad=1920:1080,setsar=1` (Pattern 1, Edge Case 2 odd-dimension) |
| QA-01 | Compara la duración real del vídeo vs la objetivo y reporta la desviación | Verified `ffprobe` final-mp4 duration (8.533s for a 8.5s-target chain); deviation = actual - target is a pure calc → `QAReport` (Pattern 4) |
| QA-02 | Mide y normaliza el loudness con FFmpeg `loudnorm` (dos pasadas) y emite un informe | Verified two-pass loudnorm end-to-end: measured -22.01 LUFS → applied → re-measured -16.01 LUFS; JSON field names confirmed (Pattern 5) |

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01** Un único filtergraph FFmpeg: por cada slide, un segmento imagen (PNG en loop) + su audio; encadenados con xfade (vídeo) + acrossfade (audio) → salida 1080p 16:9 H.264 (`libx264`, pix_fmt yuv420p, `+faststart`).
- **D-02** Las duraciones por segmento se miden con `ffprobe` sobre los audios reales de `workdir/audio/` (NO se usan las estimaciones WPM de timings.json). Cada slide dura lo que dura su audio.
- **D-03** Crossfade activado por defecto ~0.5 s, configurable en config.yaml (`crossfade_seconds`, 0 lo desactiva → cortes secos). El offset de xfade se calcula acumulando (duración_segmento − crossfade) para sincronía A/V.
- **D-04** Invocación FFmpeg por `subprocess` con lista de args (nunca `shell=True`); fluent builder en `integrations/ffmpeg.py`; captura de stderr para diagnóstico; errores claros (Rich), no traceback.
- **D-05** Quemado de subtítulos opcional vía `--burn-subs`: cuando está activo, filtro `subtitles` (libass) sobre el vídeo usando `workdir/subs/output.srt`. Por defecto OFF (vídeo limpio + sidecar .srt/.vtt de Phase 4).
- **D-06** loudnorm dos pasadas (EBU R128): 1ª pasada mide (`-af loudnorm=...:print_format=json`, parseo del JSON de stderr), 2ª pasada aplica con `measured_*` → target -16 LUFS (configurable `target_lufs`).
- **D-07** `workdir/qa_report.json`: desviación duración real vs objetivo (ffprobe sobre output.mp4 vs `RunConfig.duration`) + nivel LUFS medido y normalizado (input_i / output_i de loudnorm). Modelo Pydantic `QAReport`.
- **D-08** El informe QA se muestra también en la terminal con Rich (tabla legible).
- **D-09** `integrations/ffmpeg.py` (builder + run + ffprobe helpers) + `stages/assemble.py` (montaje) + `stages/qa.py` (informe). La etapa `assemble` real reemplaza el stub respetando StageProtocol y el checkpoint (`output.mp4` + `assembly.json`). QA puede ser parte de assemble o una etapa/paso posterior que escribe `qa_report.json`.
- **D-10** Reanudable/idempotente: si `output.mp4` + checkpoint existen, no se re-monta. Escritura atómica del checkpoint JSON; el mp4 se escribe a tmp y se renombra.

### Claude's Discretion

- Estructura exacta del filtergraph (cómo encadenar N xfade/acrossfade), flags finos de libx264 (crf/preset por defecto, p. ej. crf 20 / preset medium), formato exacto de `QAReport`, si QA es etapa separada o sub-paso de assemble, manejo del caso 1 sola slide (sin crossfade) — a criterio de Claude siguiendo estas decisiones y CLAUDE.md.

### Deferred Ideas (OUT OF SCOPE)

- Salida 9:16 vertical (FMT-01, v2) — fuera de alcance.

## Project Constraints (from CLAUDE.md)

- **FFmpeg via `subprocess`, NEVER `shell=True`, NEVER MoviePy.** `moviepy` is explicitly forbidden ("Use Instead: `ffmpeg` por `subprocess`"). `ffmpeg-python` wrapper not used either — plain arg-list strings are "más transparente y debuggable".
- **Python 3.11+**, modular, typed, docstrings, clear error handling, **resumable and idempotent**.
- **Pydantic v2** for all I/O contracts: `model_dump_json()` / `model_validate_json()` (v1 `.json()`/`.dict()` forbidden).
- **`rich`** for terminal output (the QA table, D-08); errors surface as Rich messages, not tracebacks.
- **`typer`** CLI; `--burn-subs` flag already exists (`RunConfig.burn_subs`).
- **`pytest` + `pytest-mock`** for tests; mock API/subprocess calls — do not encode real video in CI.
- ffmpeg binary documented for Phase 7 Docker (`apt-get install -y ffmpeg`); base image `mcr.microsoft.com/playwright/python:v1.60.0-noble` needs FFmpeg added.

## Standard Stack

This phase adds **no new Python dependencies**. It shells out to the system `ffmpeg`/`ffprobe` binaries via the standard-library `subprocess` module.

### Core
| Tool / Library | Version | Purpose | Why Standard |
|----------------|---------|---------|--------------|
| `ffmpeg` (system binary) | 8.0.1 verified locally; `>=6.1` minimum | Build filtergraph, encode H.264/AAC, loudnorm, burn subs | `[VERIFIED: /opt/homebrew/bin/ffmpeg -version]` Project mandates ffmpeg-by-subprocess (CLAUDE.md). All required filters present. |
| `ffprobe` (system binary) | ships with ffmpeg 8.0.1 | Measure real per-slide audio duration + final mp4 duration | `[VERIFIED]` `format=duration` reliable for mp3 and wav |
| `subprocess` (stdlib) | Python 3.11 | Invoke ffmpeg/ffprobe with an arg LIST, `capture_output=True` | `[CITED: CLAUDE.md]` arg-list, never `shell=True` |
| `pydantic` v2 | `>=2.13.4` (already installed) | `QAReport`, `AssemblyOutput` checkpoint models | `[VERIFIED: src/avideo/models/assembly.py]` already present as stubs |
| `rich` | `>=15.0.0` (already installed) | QA table in terminal (D-08) | `[CITED: CLAUDE.md]` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `json` (stdlib) | — | Parse loudnorm JSON block from ffmpeg stderr; ffprobe `-of json` | Pass-1 loudnorm parse, ffprobe duration parse |
| `re` (stdlib) | — | Extract the last `{...}` JSON block from loudnorm stderr | loudnorm prints other log lines before the JSON; regex isolates it |
| `shutil.which` (stdlib) | — | Test guard: skip real-encode smoke test if ffmpeg absent | `[VERIFIED]` `shutil.which('ffmpeg')` returns the path |
| `Pillow` | `>=12.2.0` (dev dep) | Generate tiny test PNGs in unit tests | `[VERIFIED: pyproject.toml dev deps]` already available |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `ffmpeg` subprocess arg-list | `ffmpeg-python` / `moviepy` | FORBIDDEN by CLAUDE.md. moviepy is slower + excluded; ffmpeg-python adds opacity over an already-transparent string filtergraph |
| `xfade`+`acrossfade` crossfade | `concat` demuxer / hard cuts only | concat gives no crossfade (ASMB-02 requires configurable crossfade). concat IS the correct path only when `crossfade == 0` |
| Two-pass loudnorm | single-pass `loudnorm` (dynamic) | Single-pass is less accurate (QA-02 explicitly requires two passes; "dos pasadas") |
| loudnorm as separate apply pass (`-c:v copy`) | loudnorm inside the assembly filtergraph (1 encode) | Two-pass needs the measured values from a completed analysis pass, so measurement must happen on assembled audio. Separate apply with `-c:v copy` avoids re-encoding video → faster + lossless picture (VERIFIED) |

**Installation:** No `uv add` needed. Document system requirement for Phase 7 Docker:
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
```

**Version verification:** `[VERIFIED]` Local: `ffmpeg version 8.0.1` (built 2025), configured with `--enable-libx264 --enable-libass --enable-gpl`. Filters confirmed present: `xfade`, `acrossfade`, `loudnorm`, `subtitles` (libass), `ass`, `setsar`, `concat`.

## Architecture Patterns

### System Architecture Diagram

```
  workdir/slides/slide_XX.png   workdir/audio/slide_XX.{mp3|wav}   workdir/subs/output.srt
        (Phase 3 PNGs)               (Phase 4 audio)                 (Phase 4 subs)
              │                            │                              │
              │            ┌───────────────┘                              │
              ▼            ▼                                              │
        ┌──────────────────────────┐                                    │
        │  ffprobe per audio file   │  ── real durations [d0,d1,...]     │
        │  (integrations/ffmpeg.py) │                                    │
        └────────────┬─────────────┘                                    │
                     ▼                                                   │
        ┌──────────────────────────────────────┐                       │
        │  build_filtergraph(durations, XF)     │  PURE                 │
        │   • per-input: scale+pad 1920x1080,   │  (offset chain math)  │
        │     setsar=1, fps=30, format=yuv420p  │                       │
        │   • xfade chain (video) offsets       │                       │
        │   • acrossfade chain (audio)          │                       │
        │   • OR concat path if XF==0           │                       │
        └────────────┬──────────────────────────┘                      │
                     ▼                                                   │
        ┌──────────────────────────┐         (if config.burn_subs) ◄────┘
        │  run_ffmpeg(build args)   │  -vf subtitles=output.srt (libass)
        │  → workdir/output.mp4.tmp │  -c:v libx264 -crf 20 -pix_fmt yuv420p
        │  (subprocess, arg list,   │  -c:a aac -b:a 192k -movflags +faststart
        │   capture stderr)         │
        └────────────┬─────────────┘
                     ▼
        ┌──────────────────────────┐   PASS 1: loudnorm print_format=json → stderr
        │  two-pass loudnorm        │ ─ parse_loudnorm_json() PURE → measured_I/TP/LRA/thresh/offset
        │  (QA stage)               │   PASS 2: apply measured_* -c:v copy +faststart → output.mp4
        └────────────┬─────────────┘
                     ▼
        ┌──────────────────────────┐
        │  ffprobe output.mp4 dur   │  QAReport(target, actual, deviation,
        │  + deviation calc (PURE)  │           measured_lufs, normalized_lufs)
        │  → qa_report.json         │  + Rich table (D-08)
        └──────────────────────────┘
                     ▼
        atomic rename output.mp4.tmp → output.mp4 ; write assembly.json + qa_report.json
```

### Recommended Project Structure
```
src/avideo/
├── integrations/
│   └── ffmpeg.py          # NEW: arg-list builders, run_ffmpeg, probe_duration,
│                          #      build_filtergraph (pure), parse_loudnorm_json (pure),
│                          #      loudnorm_pass1_args / loudnorm_pass2_args, crossfade math
├── stages/
│   ├── assemble.py        # NEW: AssembleStage (stage_name="assemble", checkpoint="assembly")
│   │                      #      reads slides/voice/subs checkpoints, drives ffmpeg builder
│   └── qa.py              # NEW: QA logic (two-pass loudnorm + deviation) → QAReport
├── models/
│   └── assembly.py        # EXTEND: QAReport (add measured/normalized LUFS), AssemblyOutput
└── (config.py)            # EXTEND RunConfig: crossfade_seconds (default 0.5), target_lufs (default -16)
tests/
└── test_assemble.py       # NEW: pure-logic unit tests (offsets, parse, deviation) + 1 guarded smoke
```

### Pattern 1: The verified xfade + acrossfade filtergraph (N segments)

**What:** Loop each PNG to its real audio duration, normalize each video input to exactly 1920×1080 / SAR 1:1 / 30fps / yuv420p, then chain `xfade` (video) and `acrossfade` (audio) with computed offsets.

**Offset math (VERIFIED for N=2,3,4):**
```
Given durations d[0..N-1] and crossfade XF:
  merged_dur after first segment = d[0]
  for k in 1..N-1 (joining segment k):
      offset_k       = merged_dur - XF      # where xfade transition begins
      merged_dur     = merged_dur + d[k] - XF
  final total duration = sum(d) - (N-1)*XF   # VERIFIED ±1 frame
```

**VERIFIED example (3 slides, durations 3.0/4.0/2.5, XF=0.5 → expected 8.5s, got 8.533s = +1 frame @30fps):**
```bash
# Source: empirical spike, ffmpeg 8.0.1, this research session
ffmpeg -hide_banner \
  -loop 1 -t 3.0 -i slide_00.png \
  -loop 1 -t 4.0 -i slide_01.png \
  -loop 1 -t 2.5 -i slide_02.png \
  -i audio_00.mp3 -i audio_01.mp3 -i audio_02.wav \
  -filter_complex "
    [0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p[v0];
    [1:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p[v1];
    [2:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p[v2];
    [v0][v1]xfade=transition=fade:duration=0.5:offset=2.5[vx01];
    [vx01][v2]xfade=transition=fade:duration=0.5:offset=6.0[vout];
    [3:a]aresample=48000[a0];[4:a]aresample=48000[a1];[5:a]aresample=48000[a2];
    [a0][a1]acrossfade=d=0.5[ax01];[ax01][a2]acrossfade=d=0.5[aout]
  " \
  -map "[vout]" -map "[aout]" \
  -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -movflags +faststart \
  output.mp4
# RESULT: 1920x1080, SAR 1:1, yuv420p, 30fps, H.264 + AAC, duration 8.533333s
```
Offsets here: join1 = d0 - XF = 3.0-0.5 = **2.5**; join2 = (d0+d1-XF) - XF = (6.5) - 0.5 = **6.0**. The 4-slide run (3.0/4.0/2.5/3.5, XF=0.5) gave offsets 2.5/6.0/8.0 and total 11.533s (expected 11.5) — formula generalizes.

**When to use:** `crossfade_seconds > 0` AND `N >= 2`.

### Pattern 2: ffprobe real audio duration (ASMB-01, drives slide length)

**VERIFIED:** `format.duration` agrees with `stream.duration` for both mp3 and wav. Use `format=duration` (container-level, more robust for VBR mp3).
```bash
# Per audio file (Source: empirical spike)
ffprobe -v error -show_entries format=duration -of json audio_00.mp3
#   {"format": {"duration": "3.000000"}}
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 output.mp4
#   8.533333   (used for QA deviation)
```
Parse: `float(json.loads(stdout)["format"]["duration"])`.

### Pattern 3: Single-slide path (no xfade)

**What:** With N==1, there is no transition — loop the one PNG to its audio duration, no `xfade`/`acrossfade`. Use `-shortest` so the looped video ends with the audio.
```bash
# VERIFIED: dur 3.000 exactly (Source: empirical spike, Edge Case 1)
ffmpeg -hide_banner -loop 1 -t 3.0 -i slide_00.png -i audio_00.mp3 \
  -filter_complex "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p[vout];[1:a]aresample=48000[aout]" \
  -map "[vout]" -map "[aout]" -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart -shortest output.mp4
```

### Pattern 4: crossfade == 0 → concat filter (hard cuts)

**What:** When the user disables crossfade, do NOT call `xfade` with offset 0 — use the `concat` filter. Each input still normalized, then concatenated.
```bash
# VERIFIED: 3 slides → dur 9.533 (= full sum 9.5, no overlap) (Source: empirical spike, Edge Case 3)
ffmpeg -hide_banner \
  -loop 1 -t 3.0 -i slide_00.png -loop 1 -t 4.0 -i slide_01.png -loop 1 -t 2.5 -i slide_02.png \
  -i audio_00.mp3 -i audio_01.mp3 -i audio_02.wav \
  -filter_complex "
    [0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p[v0];
    [1:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p[v1];
    [2:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p[v2];
    [3:a]aresample=48000[a0];[4:a]aresample=48000[a1];[5:a]aresample=48000[a2];
    [v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[vout][aout]
  " \
  -map "[vout]" -map "[aout]" -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart output.mp4
```
Note the interleaved input order to `concat`: `[v0][a0][v1][a1]...` (video then audio, per segment), with `n=N:v=1:a=1`.

### Pattern 5: Two-pass loudnorm (QA-02) — VERIFIED end-to-end

**Pass 1 (measure):** target params + `print_format=json`; loudnorm prints a JSON block to **stderr**.
```bash
# Source: empirical spike (VERIFIED). Use -f null - (no output file).
ffmpeg -hide_banner -i output.mp4 -af "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json" -f null -
```
The JSON block (CONFIRMED field names):
```json
{
  "input_i" : "-22.01",  "input_tp" : "-20.91",  "input_lra" : "0.70",
  "input_thresh" : "-32.01",  "output_i" : "-15.74",  "output_tp" : "-14.60",
  "output_lra" : "0.50",  "output_thresh" : "-25.74",
  "normalization_type" : "dynamic",  "target_offset" : "-0.26"
}
```
Parse (pure): isolate the last `{...}` block with `re.findall(r'\{[^{}]*\}', stderr, re.DOTALL)[-1]`, then `json.loads`. **`input_i` is the measured loudness; `target_offset` is the field to pass as `offset=` in pass 2.**

**Pass 2 (apply):** supply `measured_I`/`measured_TP`/`measured_LRA`/`measured_thresh` (from pass-1 `input_*` / `input_thresh`) and `offset` (from pass-1 `target_offset`), with `linear=true`. Re-encode audio, **copy video, and RE-ADD `-movflags +faststart`** (does NOT carry over from source under `-c:v copy`).
```bash
# Source: empirical spike (VERIFIED). measured_* come from pass-1 input_* / target_offset.
ffmpeg -hide_banner -i output_assembled.mp4 \
  -af "loudnorm=I=-16:TP=-1.5:LRA=11:measured_I=-22.01:measured_TP=-20.91:measured_LRA=0.70:measured_thresh=-32.01:offset=-0.26:linear=true:print_format=json" \
  -c:v copy -c:a aac -b:a 192k -ar 48000 -movflags +faststart output.mp4
```
**VERIFIED result:** pass-2 reported `output_i: -16.09`; an independent re-measure of the normalized file read `input_i: -16.01` LUFS — landed almost exactly on the -16 target. For `qa_report.json`, store `measured_lufs = pass1.input_i` and `normalized_lufs = re-measured input_i` (or pass-2 `output_i`, both ≈ target).

### Pattern 6: Subtitle burn-in (libass, D-05)

**What:** When `config.burn_subs`, add `-vf subtitles=<path>` (libass). Burn REQUIRES re-encoding video (cannot `-c:v copy`).
```bash
# VERIFIED (Source: empirical spike): 1920x1080 preserved, dur preserved
ffmpeg -hide_banner -i assembled.mp4 \
  -vf "subtitles=subs/output.srt:force_style='FontSize=36'" \
  -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -c:a copy out_subbed.mp4
```
Path-with-spaces VERIFIED to work both bare (`subtitles=subs dir/output.srt`) and quoted (`subtitles=filename='subs dir/output.srt'`). The workdir path is fixed (`subs/output.srt`, no user input) so escaping risk is low, but prefer the `filename='...'` form for robustness. **Ordering note:** because burn re-encodes video, when both burn AND loudnorm are active, do the burn during the assembly encode (or a re-encode pass), then loudnorm pass-2 can still `-c:v copy` the already-burned video.

### Anti-Patterns to Avoid
- **`shell=True` / string commands.** FORBIDDEN (CLAUDE.md). Build a Python `list[str]` and pass to `subprocess.run`. The `filter_complex` value is ONE list element (newlines/spaces inside it are fine).
- **`xfade` with `offset=0` for hard cuts.** Use the `concat` filter instead (Pattern 4). `xfade` with degenerate offset produces wrong durations.
- **Negative xfade offset when a slide < crossfade.** VERIFIED to silently produce a corrupt/short result (offset=-0.2 made the first slide vanish, total 4.0 instead of ~3.8). Clamp per-boundary: `eff_XF = min(XF, d[k-1], d[k])`; if `eff_XF <= 0`, fall back to a hard cut for that boundary.
- **Forgetting `-movflags +faststart` on the loudnorm pass-2.** VERIFIED: `-c:v copy` drops faststart; moov atom ends up at the END of the file (`ftyp,free,mdat`). Re-add the flag (→ `ftyp,moov,free,mdat`).
- **Omitting `setsar=1`.** Mixed-SAR inputs make `xfade`/`concat` refuse or produce wrong DAR. Always `setsar=1` after pad.
- **Omitting `format=yuv420p` / `fps=30` per input.** `xfade` requires matching pixel format and frame rate across both inputs; normalize each input first.
- **Using `timings.json` (WPM estimate) for slide durations.** ASMB-01 + D-02 require REAL ffprobe durations of the actual audio.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Crossfade between clips | Frame-by-frame alpha blending | `xfade` (video) + `acrossfade` (audio) | Native, GPU-friendly, handles timing/format internally (VERIFIED) |
| Loudness normalization | Custom RMS/peak gain | `loudnorm` two-pass (EBU R128) | Standard broadcast loudness; QA-02 mandates it; gating + true-peak limiting built in |
| Media duration | Parsing mp3 frame headers / wav chunks | `ffprobe -show_entries format=duration` | Handles every container/codec; VERIFIED consistent for mp3+wav |
| Image→video segment | Pillow frame export + manual mux | `-loop 1 -t <dur> -i image.png` | One flag loops a still to a duration |
| Aspect-ratio fit | Manual crop/letterbox math | `scale=...:force_original_aspect_ratio=decrease,pad=1920:1080,setsar=1` | VERIFIED to make any input exactly 1920×1080 16:9 (Edge Case 2: 1280×720 → 1920×1080) |
| Subtitle rendering | Drawing text with drawtext | `subtitles=` (libass) | Reads SRT/VTT directly, full styling, RTL/Unicode |
| MP4 web-readiness | Manual atom reordering | `-movflags +faststart` | Moves moov atom to front (VERIFIED atom order) |
| Atomic checkpoint write + done markers | New file logic | `WorkdirManager.write_checkpoint` / `mark_done` (existing) | Already atomic (tmp→os.replace); reuse for idempotence (D-10) |

**Key insight:** Every assembly/QA concern in this phase already has a battle-tested ffmpeg filter. The ONLY custom code is (a) the offset-chain math, (b) loudnorm-JSON parsing, (c) the deviation calc, and (d) the subprocess plumbing — all small, pure, and unit-testable.

## Runtime State Inventory

This is a greenfield stage implementation (replacing a stub), not a rename/refactor — but because it consumes prior-phase artifacts and writes new runtime state, the relevant items:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data (inputs) | `workdir/slides/slide_XX.png` (Phase 3), `workdir/audio/slide_XX.{mp3,wav}` (Phase 4), `workdir/subs/output.srt` (Phase 4), checkpoints `slides.json`, `voice.json`, `subs.json`, `timings.json` | Read via `WorkdirManager.read_checkpoint`; derive slide order from `SlidesOutput.png_paths` and `VoiceOutput.audio_paths` (one per slide, index-aligned) |
| Stored data (outputs) | `workdir/output.mp4` (currently a 0-byte stub touched by `AssembleStub`), `workdir/assembly.json`, NEW `workdir/qa_report.json` | Replace stub's empty `output.mp4` with real encode; write `assembly.json` (enriched `AssemblyOutput`) + `qa_report.json` |
| Live service config | None — pure local subprocess | None |
| OS-registered state | System `ffmpeg`/`ffprobe` on PATH (`/opt/homebrew/bin` locally; `apt-get install ffmpeg` in Docker) | None at runtime; document Phase 7 Docker dependency |
| Secrets/env vars | None — no API keys (offline ffmpeg) | None |
| Build artifacts | The stub `AssembleStub` in `stubs.py` + its `PIPELINE_STAGES` entry; `.assemble.done` marker from prior runs | Swap `AssembleStub()` → `AssembleStage()` in `PIPELINE_STAGES`; existing `.assemble.done` markers in test/dev workdirs become valid for the new stage (same `stage_name="assemble"`, same checkpoint `"assembly"`) — re-runs skip correctly per D-10 |

## Common Pitfalls

### Pitfall 1: Negative xfade offset on a short slide
**What goes wrong:** A slide whose audio is shorter than the crossfade yields `offset = d - XF < 0`; ffmpeg does not error but silently drops/corrupts the segment (VERIFIED: total became 4.0s with the first 0.3s slide effectively gone).
**Why it happens:** `xfade` expects the transition to start within the first stream's timeline.
**How to avoid:** Clamp per boundary: `eff_XF = min(XF, prev_dur, next_dur)`; if `eff_XF <= 0`, hard-cut that boundary (no xfade). The mitigation was VERIFIED: with `eff_XF=0.3` for a 0.3s slide, output was correct (4.0s).
**Warning signs:** Final duration shorter than `sum(d) - (N-1)*XF`; a slide missing from the video.

### Pitfall 2: `-c:v copy` drops `+faststart`
**What goes wrong:** loudnorm pass-2 with `-c:v copy` writes the moov atom at the END of the file; the MP4 isn't progressively streamable.
**Why it happens:** faststart is a muxer-time operation; it must be requested on the output that writes the container.
**How to avoid:** Always include `-movflags +faststart` on the FINAL output command, including the copy-video loudnorm pass (VERIFIED fix).
**Warning signs:** Atom order `ftyp,free,mdat` instead of `ftyp,moov,...`.

### Pitfall 3: Mixed pixel format / SAR / fps across inputs breaks xfade
**What goes wrong:** `xfade` errors or produces stretched/striped frames when inputs differ in pix_fmt, SAR, or fps.
**How to avoid:** Normalize EVERY input identically before the chain: `scale=...,pad=1920:1080,setsar=1,fps=30,format=yuv420p`. VERIFIED across red/green/blue 1920×1080 and a 1280×720 odd input.
**Warning signs:** ffmpeg error "First input link ... parameters do not match"; visual tearing.

### Pitfall 4: Parsing loudnorm JSON from noisy stderr
**What goes wrong:** loudnorm prints log lines around the JSON; naive `json.loads(stderr)` fails.
**How to avoid:** Extract the LAST `{...}` block: `re.findall(r'\{[^{}]*\}', stderr, re.DOTALL)[-1]`. Values are STRINGS ("-22.01") — `float()` them. VERIFIED.
**Warning signs:** `JSONDecodeError: Expecting value: line 1 column 1`.

### Pitfall 5: Using WPM/estimated durations instead of real audio
**What goes wrong:** Slides desync from voice (A/V drift) because actual TTS audio differs from the WPM estimate in `timings.json`.
**How to avoid:** ffprobe the real `workdir/audio/slide_XX.*` files (D-02/ASMB-01). The `timings.json` total is only the QA TARGET (`RunConfig.duration`), not the segment lengths.

### Pitfall 6: Building the filter_complex with shell quoting (shell=True risk)
**What goes wrong:** Embedding the filtergraph in a shell string invites quoting bugs and is forbidden.
**How to avoid:** The whole `filter_complex` string is a SINGLE element of the arg list passed to `subprocess.run([...], shell=False)`. Newlines and spaces inside it are passed literally to ffmpeg. VERIFIED via the Python arg-list pass-2 run.

### Pitfall 7: `±1 frame` duration overshoot tripping a strict QA assertion
**What goes wrong:** Final duration is `sum(d) - (N-1)*XF + ~1 frame` (e.g. 8.533 vs 8.5). A strict equality QA check would fail.
**How to avoid:** QA deviation compares against `RunConfig.duration` (the TARGET), not the theoretical sum, and uses a tolerance (e.g. report deviation as a float; flag only if `abs(deviation) > threshold`). Do not assert exact equality on durations in tests.

## Code Examples

### Pure offset-chain builder (unit-testable, no ffmpeg)
```python
# Source: derived from verified offset math (this research session)
def crossfade_offsets(durations: list[float], xfade: float) -> list[float]:
    """Return the xfade `offset=` value for each join (len = N-1).

    offset_k = (cumulative merged duration so far) - xfade
    Verified empirically for N=2,3,4: total = sum(d) - (N-1)*xfade.
    """
    offsets: list[float] = []
    merged = durations[0]
    for d in durations[1:]:
        offsets.append(round(merged - xfade, 6))
        merged = merged + d - xfade
    return offsets

def expected_total(durations: list[float], xfade: float) -> float:
    n = len(durations)
    return sum(durations) - max(0, n - 1) * xfade
```

### Pure loudnorm JSON parse (unit-testable)
```python
# Source: verified field names from ffmpeg 8.0.1 loudnorm stderr (this session)
import json, re

def parse_loudnorm_json(stderr: str) -> dict[str, float]:
    """Extract loudnorm measurement block from ffmpeg stderr.

    Returns floats for measured_I/TP/LRA/thresh + offset, plus input_i.
    """
    blocks = re.findall(r"\{[^{}]*\}", stderr, re.DOTALL)
    if not blocks:
        raise ValueError("No loudnorm JSON block found in ffmpeg stderr")
    raw = json.loads(blocks[-1])
    return {
        "measured_I": float(raw["input_i"]),
        "measured_TP": float(raw["input_tp"]),
        "measured_LRA": float(raw["input_lra"]),
        "measured_thresh": float(raw["input_thresh"]),
        "offset": float(raw["target_offset"]),
    }
```

### Subprocess runner (mockable; never shell=True)
```python
# Source: matches existing integrations pattern + CLAUDE.md
import shutil, subprocess

def run_ffmpeg(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run ffmpeg/ffprobe with an arg list; capture stderr for diagnosis.

    Never uses shell=True. Raises RuntimeError with captured stderr tail on
    nonzero exit so the orchestrator surfaces a clean Rich message (D-04).
    """
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-8:])
        raise RuntimeError(f"ffmpeg failed (exit {proc.returncode}):\n{tail}")
    return proc

def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| MoviePy / per-frame compositing | Direct ffmpeg `xfade`/`acrossfade` filtergraph | ffmpeg 4.3 added `xfade` (2020) | Faster, fewer deps, exact control — and MoviePy is forbidden here |
| Single-pass `loudnorm` | Two-pass measure→apply | loudnorm gained `print_format=json` early | Accurate, deterministic normalization to target LUFS (QA-02) |
| `-vf ass=` only | `subtitles=` filter reads SRT/VTT directly via libass | long-standing | No SRT→ASS conversion step needed |

**Deprecated/outdated:** Pydantic v1 `.json()` (use `model_dump_json()`); `moviepy`/`ffmpeg-python` (forbidden/unused per CLAUDE.md).

## Validation Architecture

Test framework is `pytest` + `pytest-mock` (`mocker`/`monkeypatch`), config in `pyproject.toml` (`[tool.pytest.ini_options]` testpaths=`tests`, pythonpath=`src`). Quick run: `uv run pytest tests/test_assemble.py -x`. Full suite: `uv run pytest`.

### What is PURE (mock-free, no ffmpeg) — the bulk of the tests
| Logic | Function | Test approach |
|-------|----------|---------------|
| xfade offset chain | `crossfade_offsets(durations, xfade)` | Assert offsets for N=2/3/4 against verified values (2.5/6.0/8.0...) |
| expected total duration | `expected_total(durations, xfade)` | `sum(d) - (N-1)*XF`; XF=0 → full sum |
| crossfade clamping | `min(XF, prev, next)` per boundary; ≤0 → hard cut | Short-slide case → eff_XF, fallback flag |
| loudnorm JSON parse | `parse_loudnorm_json(stderr)` | Feed the captured stderr fixture; assert float fields + JSONDecodeError on garbage |
| duration deviation | `actual - target` (and within-tolerance flag) | Pure arithmetic on `QAReport` |
| filtergraph string build | `build_filtergraph(...)` returns str | Assert substrings: `scale=1920:1080`, `setsar=1`, `xfade=`/`concat=`, correct labels — NO ffmpeg run |
| arg-list build | `build_assemble_args(...)` returns `list[str]` | Assert it's a list, `-movflags +faststart` present, filter_complex is ONE element, NO `shell=True` |
| path selection (single/N/XF=0) | dispatch in `AssembleStage` | Parametrize 1 slide / 3 slides / XF=0 → assert which builder branch fires (mock `run_ffmpeg`) |

### What must be MOCKED
| External call | Mock |
|---------------|------|
| `subprocess.run` (ffmpeg/ffprobe) | `mocker.patch("avideo.integrations.ffmpeg.subprocess.run", ...)` returning a fake `CompletedProcess` with `returncode=0` and a canned loudnorm stderr fixture |
| ffprobe duration | patch `probe_duration` to return fixed floats so the offset/total assertions are deterministic |
| AssembleStage end-to-end | mock `run_ffmpeg` + `probe_duration`; create empty `slide_XX.png`/`audio_XX.mp3` placeholders; assert `output.mp4`/`assembly.json`/`qa_report.json` written and checkpoint shape |

### Real-ffmpeg SMOKE TEST (exactly one, guarded)
```python
import shutil, pytest
pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed",
)
# Generate 2-3 tiny PNGs with Pillow (already a dev dep) + 2-3 ~1s sine audios via ffmpeg lavfi,
# run the REAL assemble path, then ffprobe-assert: width==1920, height==1080, pix_fmt==yuv420p,
# and abs(duration - expected_total) < 0.1  (±1-frame tolerance, Pitfall 7).
```
This mirrors the existing `tests/test_slides_render.py` pattern (`pytest.importorskip("playwright")` guard) — the smoke test runs locally/Docker where ffmpeg exists and skips cleanly in a bare CI.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ASMB-01 | real ffprobe durations drive slide length | unit (mock probe) | `uv run pytest tests/test_assemble.py -k probe_drives_duration -x` | ❌ Wave 0 |
| ASMB-02 | crossfade offsets + XF=0 concat + clamp | unit (pure) | `uv run pytest tests/test_assemble.py -k crossfade -x` | ❌ Wave 0 |
| ASMB-03 | output is 1920×1080 yuv420p | smoke (guarded) | `uv run pytest tests/test_assemble.py -k smoke_dimensions -x` | ❌ Wave 0 |
| QA-01 | duration deviation vs target | unit (pure) | `uv run pytest tests/test_assemble.py -k deviation -x` | ❌ Wave 0 |
| QA-02 | two-pass loudnorm parse + apply args | unit (parse) + smoke (lands ≈ -16) | `uv run pytest tests/test_assemble.py -k loudnorm -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_assemble.py -x`
- **Per wave merge:** `uv run pytest`
- **Phase gate:** Full suite green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_assemble.py` — covers ASMB-01/02/03, QA-01/02 (pure unit + one guarded smoke)
- [ ] conftest fixture: a canned loudnorm pass-1 stderr string (for `parse_loudnorm_json` tests) — add to `tests/conftest.py`
- [ ] conftest helper: tiny-PNG + tiny-audio generator for the smoke test (Pillow + ffmpeg lavfi)
- [ ] No framework install needed — `pytest`, `pytest-mock`, `pillow` already in dev deps.

## Security Domain

`security_enforcement` is not set in config → treated as enabled.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth surface (offline CLI) |
| V3 Session Management | no | No sessions |
| V4 Access Control | no | Local filesystem only |
| V5 Input Validation | yes | All ffmpeg/ffprobe args are a Python `list[str]` (never a shell string); paths derived from `WorkdirManager` fixed layout + checkpoint data, not raw user CLI input; durations are floats validated > 0 |
| V6 Cryptography | no | No crypto in this phase |
| V12 Files/Resources | yes | Output paths fixed under `workdir/` (`output.mp4`, `assembly.json`, `qa_report.json`); subtitle path is the fixed `subs/output.srt`; atomic tmp→rename for output.mp4 and checkpoints (D-10) |

### Known Threat Patterns for ffmpeg-by-subprocess
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Shell/command injection via filenames or filtergraph | Tampering / EoP | `subprocess.run(list, shell=False)`; NEVER `shell=True`; filter_complex is one list element (VERIFIED). CLAUDE.md hard rule |
| Path traversal via crafted slide/audio paths | Tampering | Build all paths from `WorkdirManager.root / fixed-subdir / fixed-name`; do not interpolate untrusted strings into output paths |
| Subtitle filter arg injection (`:` `'` `\` in path) | Tampering | Subtitle path is the fixed `subs/output.srt` (no user component); prefer `subtitles=filename='...'`; escaping VERIFIED for spaces |
| Resource exhaustion (huge/many slides) | DoS | Out of scope for this phase; bounded by storyboard slide count from earlier phases |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Phase 4 writes one audio file per slide, index-aligned with `SlidesOutput.png_paths` (so segment k = slide k = audio k) | Architecture, Runtime State | LOW — verify by reading `voice.json`/`slides.json` at plan time; if counts mismatch, assemble must error clearly |
| A2 | Default crossfade 0.5s and libx264 `crf 20 / preset medium` are acceptable quality/size defaults | Standard Stack, Pattern 1 | LOW — Claude's discretion per CONTEXT; configurable; tune if file size/quality complaints |
| A3 | 30fps output is acceptable (slides are static, so fps mainly affects crossfade smoothness) | Pattern 1 | LOW — 30fps is standard for slideshow video; 25/60 trivially changeable; not user-locked |
| A4 | `target_lufs` -16 LUFS (web/voice standard) is the desired loudness target | Pattern 5 | LOW — D-06 locks -16 as default, configurable via `target_lufs` |
| A5 | AAC 192k / 48kHz audio is acceptable | Pattern 1/5 | LOW — standard MP4 audio; configurable |
| A6 | QA report stores BOTH measured (pre-norm) and normalized (post-norm) LUFS; existing `QAReport.lufs` single field should be extended to two fields | Pattern 5, model | LOW — D-07 says "medido y normalizado"; extend `QAReport` accordingly (current model has only `lufs`) |

## Open Questions

1. **Should QA be a sub-step of `assemble` or its own `qa` stage?**
   - What we know: D-09 allows either; `PIPELINE_STAGES` currently ends with one `AssembleStub` (checkpoint `assembly`). The orchestrator iterates a flat list and writes ONE checkpoint per stage.
   - What's unclear: A separate `qa` stage means a new `PIPELINE_STAGES` entry, a new `stage_name`/checkpoint, and the orchestrator writing `qa.json` (then the stage also writes `qa_report.json`).
   - Recommendation: **Make QA a sub-step inside `AssembleStage.run`** (assemble → two-pass loudnorm → ffprobe → build `QAReport`), returning an enriched `AssemblyOutput` that embeds the `QAReport`, and writing `qa_report.json` as a side artifact. This keeps a single checkpoint (`assembly`), single done-marker, single idempotence boundary (D-10), and avoids touching `PIPELINE_STAGES` beyond the stub swap. The Roadmap's "05-02: stages/qa.py" can be a pure-logic module (`qa.py`) imported by `assemble.py` rather than a separate StageProtocol stage.

2. **Exact shape of the extended `QAReport`.**
   - What we know: current model has `target_seconds`, `actual_seconds`, `duration_deviation`, `lufs: Optional[float]`. D-07 wants measured AND normalized LUFS.
   - Recommendation: extend to `measured_lufs: Optional[float]` + `normalized_lufs: Optional[float]` (keep `lufs` deprecated/aliased or replace). Decide at plan time; both are simple floats.

3. **Crossfade transition type — `fade` only, or expose others?**
   - What we know: `xfade transition` has 57 options (`fade`, `wipeleft`, `dissolve`, ...); `fade` is the default and the natural slideshow transition.
   - Recommendation: default `transition=fade`; do NOT expose other transitions in v1 (not in requirements). Hardcode `fade`.

4. **Output frame rate value.**
   - What we know: slides are static; fps mainly governs crossfade smoothness and encoder behavior. 30 was used in the spike and produced clean results.
   - Recommendation: default 30fps (config-overridable if desired). Document as A3.

5. **Does ElevenLabs-produced mp3 duration drift enough to matter?**
   - What we know: lavfi-generated mp3 reported exact durations; real VBR mp3 with encoder delay can drift a few ms.
   - Recommendation: `ffprobe format=duration` already accounts for container duration; the per-segment offset math uses these real values, so any drift is absorbed. No action; revisit only if A/V desync appears in a real run.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `ffmpeg` | assembly, loudnorm, burn-subs | ✓ | 8.0.1 (`/opt/homebrew/bin`) | none (hard requirement); document `apt-get install ffmpeg` for Docker |
| `ffprobe` | real durations (ASMB-01), final duration (QA-01) | ✓ | 8.0.1 (`/opt/homebrew/bin`) | none (ships with ffmpeg) |
| libx264 | H.264 encode (ASMB-03) | ✓ | `--enable-libx264` | none |
| libass | subtitle burn-in (D-05) | ✓ | `--enable-libass` (`subtitles`/`ass` filters present) | sidecar SRT (burn is opt-in anyway) |
| `Pillow` | tiny test PNGs (smoke) | ✓ | `>=12.2.0` dev dep | ffmpeg lavfi `color=` source |

**Missing dependencies with no fallback:** none — all present locally.
**Missing dependencies with fallback:** none.
**Note for Phase 7 (Docker):** the Playwright base image does NOT include ffmpeg; add `apt-get install -y ffmpeg` (already noted in CLAUDE.md Docker section).

## Sources

### Primary (HIGH confidence)
- **Empirical spike, ffmpeg 8.0.1, this research session (2026-05-25)** — VERIFIED: 2/3/4-slide xfade+acrossfade chains (durations & dimensions via ffprobe), single-slide path, odd-dimension scale+pad, crossfade=0 concat, short-audio negative-offset failure + clamping mitigation, two-pass loudnorm (measured -22.01 → re-measured -16.01 LUFS, JSON field names), `+faststart` atom ordering under `-c:v copy`, subtitle burn-in with libass, ffprobe duration for mp3/wav, `shutil.which` discovery.
- `/opt/homebrew/bin/ffmpeg -version` and `-filters` — VERIFIED filters: xfade, acrossfade, loudnorm, subtitles, ass, setsar, concat.
- Codebase: `src/avideo/stages/base.py`, `orchestrator.py`, `stubs.py`, `utils/workdir.py`, `models/assembly.py`, `models/config.py`, `integrations/playwright.py`, `stages/subtitles.py`, `tests/conftest.py`, `pyproject.toml` — VERIFIED contracts and conventions.

### Secondary (MEDIUM confidence)
- FFmpeg filter documentation (xfade `transition` list, loudnorm options) — cross-checked against `ffmpeg -h filter=xfade` output locally.

### Tertiary (LOW confidence)
- None — all load-bearing claims were verified against the local ffmpeg.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new deps; binaries verified present at exact version.
- Filtergraph / crossfade: HIGH — verified empirically for N=2,3,4 plus all edge cases; offset formula confirmed.
- Two-pass loudnorm: HIGH — verified end-to-end; field names and -16 LUFS landing confirmed.
- Edge cases (single, odd-dim, XF=0, short audio): HIGH — each run and probed.
- Integration/checkpoint shape: HIGH — matches existing StageProtocol/CheckpointMixin/WorkdirManager.
- QA model exact fields / QA-as-substep decision: MEDIUM — Claude's discretion per CONTEXT; recommendation given in Open Questions.

**Research date:** 2026-05-25
**Valid until:** 2026-06-24 (30 days — ffmpeg filtergraph behavior is stable; the empirical results are reproducible on ffmpeg ≥ 4.3).
