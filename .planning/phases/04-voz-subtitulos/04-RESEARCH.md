# Phase 4: Voz + Subtítulos - Research

**Researched:** 2026-05-25
**Domain:** TTS con timestamps (ElevenLabs) + alineación forzada de audio (WhisperX) + generación de subtítulos SRT/VTT
**Confidence:** HIGH (ElevenLabs API, subtitle formats, codebase patterns) / MEDIUM-HIGH (WhisperX CPU path, torch compat)

## Summary

Phase 4 implementa la etapa de voz y subtítulos sobre la base ya consolidada del orquestador (StageProtocol + CheckpointMixin + WorkdirManager, escritura atómica, idempotencia). Dos caminos de voz mutuamente excluyentes seleccionados por `RunConfig.voice`: (a) `elevenlabs` — un MP3 por slide vía `client.text_to_speech.convert_with_timestamps()` con timestamps por carácter ya incluidos (no se alinea); (b) `record` — exportar el guion segmentado por slide, grabar con `sounddevice`/`soundfile` o autodetectar `slide_XX.wav` aportados, y alinear con WhisperX para timings palabra a palabra. Ambos caminos convergen en un **formato interno de timings unificado (Pydantic)** del que `subtitles.py` produce SIEMPRE `output.srt` + `output.vtt` mediante lógica pura y testeable. El quemado en vídeo es Phase 5.

El hallazgo de mayor impacto es de **versión de API**: el SDK `elevenlabs>=2.x` devuelve un `CharacterAlignmentResponseModel` con campos `character_start_times_seconds` y `character_end_times_seconds` **en SEGUNDOS** `[VERIFIED: github.com/elevenlabs/elevenlabs-python types/character_alignment_response_model.py]`. CLAUDE.md y snapshots antiguos de Context7 mencionan `character_start_times_ms` / `character_durations_ms` (milisegundos) — eso corresponde a la API/SDK 1.x y está **obsoleto** para el SDK 2.49.0 que usa el proyecto. La capa `integrations/elevenlabs.py` debe leer los campos `_seconds` y la validación estrictamente-creciente debe correr sobre `character_start_times_seconds`.

El segundo hallazgo: el bug #607 que motivó la decisión D-02 es en realidad un bug de **speech-to-text con diarización** (`diarize=True`), NO de text-to-speech `[VERIFIED: github.com/elevenlabs/elevenlabs-python/issues/607]`. La validación estrictamente-creciente sigue siendo una salvaguarda defensiva correcta y barata, pero el plan debe documentar que mitiga "timestamps degenerados/congelados en general", no específicamente #607. El tercer hallazgo: `whisperx.load_model()` carga un modelo VAD (pyannote por defecto) sujeto al fallo `weights_only` de torch >=2.6; el entorno tiene torch 2.9.1 instalado, así que el camino `record` necesita mitigación explícita (pin torch o `vad_method`/parche).

**Primary recommendation:** Construir `integrations/elevenlabs.py` (cliente lazy + `convert_with_timestamps` + validación seconds-crecientes + retry≤3) e `integrations/whisperx.py` (import perezoso + `load_model`/`load_align_model`/`align` en CPU `int8`), un modelo Pydantic `UnifiedTimings` (palabras con start/end en segundos por slide) que ambos backends producen, y `stages/subtitles.py` 100% puro que agrupa palabras en cues (~42 chars/línea, ≤2 líneas, ≤5s/cue, ≤17 CPS) y serializa SRT (coma) + VTT (punto). Reemplazar `VoiceStub`/`AlignStub`/`SubsStub` en `PIPELINE_STAGES` con selección de etapa de voz por `config.voice`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01** Modo `elevenlabs`: un clip de audio por slide usando `convert_with_timestamps()`, modelo `eleven_multilingual_v2`, `voice_id` configurable (placeholder en `config.yaml`). Output: `workdir/audio/slide_XX.mp3` (decodificado de base64) + timings por slide.
- **D-02** Validación de timestamps estrictamente crecientes antes de guardar el checkpoint (mitiga timestamps "congelados", referencia #607): si la secuencia no es estrictamente creciente, reintenta hasta 3 veces; si sigue mal, error claro / fallback marcado.
- **D-03** En modo `elevenlabs` NO se ejecuta alineación (los timings vienen del API). `ELEVENLABS_API_KEY` se lee del entorno.
- **D-04** Modo `record`: exporta el guion segmentado por slide y permite (a) grabar con `sounddevice` → `soundfile.write()` a `slide_XX.wav`, o (b) aportar `workdir/audio/slide_XX.wav` ya grabados (autodetección).
- **D-05** Alineación con WhisperX, modelo por defecto `small` (configurable, p. ej. `large-v3`). Produce timings palabra a palabra.
- **D-06** WhisperX solo se ejecuta en modo `record`. Importación de whisperx/torch perezosa (solo al usar) para no penalizar `elevenlabs` ni el arranque.
- **D-07** SIEMPRE genera `workdir/subs/output.srt` y `output.vtt` a partir de timings unificados (de ElevenLabs o WhisperX).
- **D-08** Segmentación de subtítulos: agrupar timestamps de carácter/palabra en líneas legibles (~42 chars/línea, ≤2 líneas, ≤5s/cue). Lógica pura y testeable.
- **D-09** Quemado de subtítulos opcional vía `--burn-subs` (ya en `RunConfig`); el quemado real ocurre en Phase 5. Phase 4 deja los .srt/.vtt listos.
- **D-10** `integrations/elevenlabs.py` (cliente + convert_with_timestamps + validación + retry). `integrations/whisperx.py` (carga de modelo + alineación, import perezoso). Etapas: `stages/voice_elevenlabs.py`, `stages/voice_record.py`, `stages/align.py`, `stages/subtitles.py`.
- **D-11** Un formato interno de timings unificado (Pydantic) que ambos caminos producen, para que `subtitles.py` sea agnóstico de la fuente.
- **D-12** Las etapas reales reemplazan los stubs `voice`/`align`/`subs` respetando StageProtocol y los nombres de checkpoint. La etapa de voz se selecciona según `RunConfig.voice`.

### Claude's Discretion
- Estructura exacta del formato interno de timings, parámetros finos de segmentación de subtítulos, UX concreta de la grabación con sounddevice, formato del guion segmentado exportado, manejo de mp3 vs wav — a criterio de Claude siguiendo estas decisiones y CLAUDE.md.

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| VOICE-01 | Modo `elevenlabs`: clip de audio por slide con endpoint de timestamps (`eleven_multilingual_v2`, `voice_id` configurable) | `convert_with_timestamps(voice_id=, text=, model_id="eleven_multilingual_v2", output_format="mp3_44100_128")` → `response.audio_base64` (decode→mp3) + `response.alignment`. Ver "Code Examples" |
| VOICE-02 | Validar timestamps estrictamente crecientes; reintentar o marcar fallback | Validación pura sobre `alignment.character_start_times_seconds` (estrictamente creciente). Retry ≤3 en `integrations/elevenlabs.py`. Ver "Pitfall: campo seconds vs ms" |
| VOICE-03 | Modo `record`: exporta guion segmentado + grabar con `sounddevice` o aportar `slide_XX.wav` | `sounddevice.rec()` + `soundfile.write()`; autodetección con `glob audio/slide_*.wav`. Ver "Architecture: record mode" |
| ALIGN-01 | `record`: WhisperX alinea → timings por palabra | `load_model` (faster-whisper) + `transcribe` + `load_align_model(es)` + `align` → `word_segments` con start/end en segundos. Import perezoso |
| ALIGN-02 | `elevenlabs`: NO se ejecuta alineación | Etapa `align` se salta si `config.voice == elevenlabs` (los timings ya vienen del API). Ver "Architecture: stage wiring" |
| SUB-01 | Genera `.srt` y `.vtt` siempre, desde timings | `stages/subtitles.py` puro: `UnifiedTimings` → cues → SRT (HH:MM:SS,mmm) + VTT (WEBVTT + HH:MM:SS.mmm). Ver "Code Examples" |
| SUB-02 | Quemado de subtítulos opcional vía flag | `RunConfig.burn_subs` ya existe; Phase 4 NO quema (deja .srt/.vtt listos); Phase 5 consume vía ffmpeg `subtitles=` filter |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| TTS por slide (elevenlabs) | Integration (`integrations/elevenlabs.py`) | Stage (`voice_elevenlabs`) | El cliente HTTP/SDK y la lógica de validación+retry viven en integration; la etapa orquesta por-slide y persiste |
| Validación timestamps crecientes | Integration (pura, dentro de elevenlabs.py) | — | Lógica de decisión retry/fallback junto a la llamada; función pura testeable sin red |
| Grabación de audio | Stage (`voice_record`) | Integration (sounddevice/soundfile wrapper opcional) | Captura de hardware es side-effecting; mejor en la etapa con UX rich |
| Autodetección de WAVs aportados | Stage (`voice_record`) | WorkdirManager (paths) | Decisión "grabar vs ingerir" pertenece a la etapa; los paths vienen del WorkdirManager |
| Alineación forzada (WhisperX) | Integration (`integrations/whisperx.py`) | Stage (`align`) | Carga de modelos pesados + import perezoso encapsulados; la etapa decide cuándo correr |
| Modelo de timings unificado | Models (`models/timings.py` nuevo) | — | Contrato Pydantic compartido por ambos backends + subtítulos |
| Generación SRT/VTT | Stage (`subtitles.py`, lógica pura en util) | — | Transformación pura timings→texto; sin red ni I/O de modelos; ideal para tests |
| Quemado en vídeo | (Phase 5 — `assemble`) | — | Fuera de scope de Phase 4; solo se dejan los archivos listos |

## Standard Stack

### Core
| Library | Version (verificada) | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `elevenlabs` | `2.49.0` (latest PyPI) `[VERIFIED: pip index versions]` | TTS con timestamps por carácter | SDK oficial; `convert_with_timestamps()` devuelve audio_base64 + alignment sin pipeline extra |
| `whisperx` | `3.8.6` (latest; CLAUDE.md fija 3.8.5) `[VERIFIED: pip index versions]` | Alineación forzada wav2vec2 → timings palabra (modo record) | Única opción con forced alignment sobre Whisper; soporta `es` nativo |
| `sounddevice` | `0.5.5` `[VERIFIED: pip index versions]` | Grabar audio del micrófono (modo record) | Captura a numpy array; estándar para grabación en Python |
| `soundfile` | `0.13.1` (latest; instalado: 0.12.1 — actualizar) `[VERIFIED: pip index versions]` | Leer/escribir WAV | Companion de sounddevice; libsndfile bindings |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `torch` + `torchaudio` | `2.5.1` recomendado (instalado: 2.9.1) `[VERIFIED: python -c import torch]` | Backend de WhisperX (faster-whisper + wav2vec2 align) | Solo modo record; CLAUDE.md fija 2.5.1 por estabilidad pyannote VAD |
| `rich` | `15.0.0` (ya en stack) | Progress de grabación / TTS por slide | UX de CLI en ambas etapas |
| `pydantic` | `2.13.4` (ya en stack) | `UnifiedTimings` + `VoiceOutput` | Contrato unificado + checkpoints |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `convert_with_timestamps` | `stream_with_timestamps` | Streaming útil para baja latencia; el pipeline es secuencial por slide → la versión no-streaming es más simple y suficiente |
| pyannote VAD (default whisperx) | `vad_method="silero"` | Silero evita el fallo pickle de torch >=2.6 y suele ir mejor en CPU; verificar que el parámetro existe en whisperx 3.8.6 |
| `int8` CPU compute | `float16` GPU | GPU solo si disponible (`large-v3`); default `small` + `int8` + `cpu` es el camino portable y para CI |
| Decodificar base64 manual | helper SDK | El SDK devuelve `audio_base64` como str; `base64.b64decode()` directo es lo correcto, no hay helper de archivo |

**Installation (añadir al pyproject vía `uv add`):**
```bash
# Núcleo de voz (modo elevenlabs — ligero, sin torch)
uv add "elevenlabs>=2.49.0"

# Modo record (pesado — grupo opcional recomendado para no forzar torch en todos)
uv add "sounddevice>=0.5.5" "soundfile>=0.13.1"
# torch ANTES de whisperx (CLAUDE.md): para CPU portable / Docker
# uv add "torch==2.5.1" "torchaudio==2.5.1" --index-url https://download.pytorch.org/whl/cpu
uv add "whisperx>=3.8.5"
```
> **Recomendación de empaquetado:** declarar `sounddevice`/`soundfile`/`whisperx`/`torch` como **extra opcional** (p. ej. `[project.optional-dependencies] record = [...]`) para que el modo `elevenlabs` (el por defecto) no arrastre torch (~2 GB). El import perezoso (D-06) entonces falla con un mensaje claro "instala el extra `record`" si faltan. Coordinar con Phase 7 (Docker añade torch CPU + portaudio).

**Version verification (ejecutada 2026-05-25):**
- `elevenlabs`: latest = `2.49.0` `[VERIFIED: pip index versions]`
- `whisperx`: latest = `3.8.6` (CLAUDE.md fija 3.8.5; ambas válidas) `[VERIFIED: pip index versions]`
- `sounddevice`: latest = `0.5.5` `[VERIFIED]`; `soundfile`: latest = `0.13.1`, **instalado 0.12.1** (actualizar) `[VERIFIED]`
- `torch`: instalado `2.9.1`; CLAUDE.md recomienda `2.5.1` por compat pyannote VAD `[VERIFIED]`

## Architecture Patterns

### System Architecture Diagram

```
                    workdir/script.json (ScriptOutput)   workdir/timings.json (TimingOutput)
                              │                                    │
                              └──────────────┬─────────────────────┘
                                             │  (leídos por la etapa de voz)
                                             ▼
                              ┌──────────────────────────────┐
                  config.voice│   SELECCIÓN DE ETAPA DE VOZ   │
                  ─────────────────────┬───────────────┬──────┘
                       elevenlabs      │               │   record
                                       ▼               ▼
        ┌─────────────────────────────────┐   ┌──────────────────────────────────┐
        │ stage voice_elevenlabs           │   │ stage voice_record                │
        │  por slide:                      │   │  1. exporta guion segmentado      │
        │  integrations/elevenlabs         │   │     workdir/audio/script_segments │
        │  .synthesize_slide(text, cfg)    │   │  2. autodetect slide_XX.wav?      │
        │   → convert_with_timestamps      │   │     SÍ → usar; NO → sounddevice.rec│
        │   → decode base64 → slide_XX.mp3 │   │     → soundfile.write slide_XX.wav│
        │   → alignment.char_start_seconds │   └──────────────┬───────────────────┘
        │   → VALIDA estrictamente creciente│                  │
        │   → retry ≤3 / fallback          │                  ▼
        │   → produce UnifiedTimings        │   ┌──────────────────────────────────┐
        └───────────────┬─────────────────┘   │ stage align (SOLO record)         │
                        │                       │  integrations/whisperx (lazy)     │
            (elevenlabs: align SE SALTA)        │  load_model(small,cpu,int8)       │
                        │                       │  + transcribe + load_align_model  │
                        │                       │  + align → word_segments (s)      │
                        │                       │  → produce UnifiedTimings         │
                        │                       └──────────────┬───────────────────┘
                        │                                      │
                        └──────────────┬───────────────────────┘
                                       ▼
                        workdir/timings_unified.json (UnifiedTimings — checkpoint de voz/align)
                                       │
                                       ▼
                        ┌──────────────────────────────────┐
                        │ stage subtitles (SIEMPRE, puro)   │
                        │  UnifiedTimings → cues            │
                        │   (~42 chars/línea, ≤2 líneas,    │
                        │    ≤5s/cue, ≤17 CPS)              │
                        │  → workdir/subs/output.srt        │
                        │  → workdir/subs/output.vtt        │
                        └──────────────┬───────────────────┘
                                       ▼
                        (Phase 5: assemble + --burn-subs opcional)
```

### Recommended Project Structure
```
src/avideo/
├── models/
│   ├── timings.py          # NUEVO: UnifiedTimings (WordTiming, SlideTimings) — D-11
│   └── voice.py            # AMPLIAR: VoiceOutput (audio_paths ya existe)
├── integrations/
│   ├── elevenlabs.py       # NUEVO: cliente lazy + convert_with_timestamps + validación + retry — D-10
│   └── whisperx.py         # NUEVO: import perezoso + load/transcribe/align — D-10
├── stages/
│   ├── voice_elevenlabs.py # NUEVO — D-10/D-12
│   ├── voice_record.py     # NUEVO — D-10/D-12
│   ├── align.py            # NUEVO (reemplaza AlignStub) — D-10/D-12
│   └── subtitles.py        # NUEVO (reemplaza SubsStub) — D-10/D-12
└── utils/
    └── subtitle_format.py  # NUEVO (opcional): lógica pura SRT/VTT serialización — facilita tests
```

### Pattern 1: Cliente lazy + mock point a nivel de módulo (replicar de anthropic.py)
**What:** Cliente instanciado en primera llamada (no en import), constante de modelo en un solo sitio, función llamable importada a scope de módulo en la etapa para que los tests parcheen `avideo.stages.X.fn`.
**When to use:** En `integrations/elevenlabs.py` y en cada etapa que llama integración.
**Example:**
```python
# Source: patrón existente en src/avideo/integrations/anthropic.py
# integrations/elevenlabs.py
from __future__ import annotations
import base64

MODEL_ID = "eleven_multilingual_v2"          # D-01: single source of truth
OUTPUT_FORMAT = "mp3_44100_128"              # default; mp3 por slide
_client = None

def _get_client():
    """Lazy: importar el módulo NO requiere ELEVENLABS_API_KEY."""
    global _client
    if _client is None:
        from elevenlabs import ElevenLabs  # SDK lee la key del entorno
        _client = ElevenLabs()             # ELEVENLABS_API_KEY desde env (D-03)
    return _client
```

### Pattern 2: convert_with_timestamps + validación seconds-crecientes + retry
**What:** Llamada TTS, decode base64, validación pura, retry ≤3, fallback marcado.
**Example:**
```python
# Source: github.com/elevenlabs/elevenlabs-python types/character_alignment_response_model.py [VERIFIED]
def synthesize_slide(text: str, voice_id: str, out_path) -> "SlideTimings":
    last_err = None
    for attempt in range(3):                       # D-02: retry ≤3
        resp = _get_client().text_to_speech.convert_with_timestamps(
            voice_id=voice_id,
            text=text,
            model_id=MODEL_ID,                     # eleven_multilingual_v2
            output_format=OUTPUT_FORMAT,
        )
        starts = resp.alignment.character_start_times_seconds   # SEGUNDOS, no ms
        if is_strictly_increasing(starts):         # pura, testeable (D-02)
            out_path.write_bytes(base64.b64decode(resp.audio_base64))  # → slide_XX.mp3
            return build_slide_timings(resp.alignment)
        last_err = "non-increasing timestamps"
    raise VoiceTimestampError(f"slide TTS failed after 3 retries: {last_err}")  # error claro

def is_strictly_increasing(xs: list[float]) -> bool:
    return all(b > a for a, b in zip(xs, xs[1:]))
```

### Pattern 3: WhisperX import perezoso + align en CPU
**What:** Importar whisperx/torch SOLO dentro de la función (D-06); CPU `int8` por defecto.
**Example:**
```python
# Source: github.com/m-bain/whisperX README + Context7 /m-bain/whisperx [VERIFIED]
def align_wav(wav_path: str, language: str = "es", model_size: str = "small"):
    import whisperx           # import PEREZOSO — no penaliza el modo elevenlabs (D-06)
    device, compute = "cpu", "int8"   # portable / CI; GPU+float16 si large-v3 y CUDA
    model = whisperx.load_model(model_size, device, compute_type=compute, language=language)
    audio = whisperx.load_audio(wav_path)
    result = model.transcribe(audio, batch_size=16)
    model_a, metadata = whisperx.load_align_model(language_code=language, device=device)
    aligned = whisperx.align(result["segments"], model_a, metadata, audio, device,
                             return_char_alignments=False)
    # aligned["word_segments"]: [{"start": float_s, "end": float_s, "word": str}, ...]
    return aligned["word_segments"]
```

### Pattern 4: Modelo de timings unificado (D-11)
**What:** Estructura Pydantic común a ambos backends para que `subtitles.py` sea agnóstico.
**Example:**
```python
# models/timings.py — propuesta (Claude's discretion sobre forma exacta)
from pydantic import BaseModel

class WordTiming(BaseModel):
    text: str
    start: float        # SEGUNDOS desde inicio del slide (o global — decidir y documentar)
    end: float

class SlideTimings(BaseModel):
    slide_index: int
    audio_path: str     # slide_XX.mp3 | slide_XX.wav
    duration: float     # segundos
    words: list[WordTiming]

class UnifiedTimings(BaseModel):
    source: str         # "elevenlabs" | "whisperx"
    slides: list[SlideTimings]
```
> **Nota clave para Phase 5:** decidir y DOCUMENTAR si los `start/end` son por-slide (relativos) o globales (acumulados sobre toda la línea de tiempo). Subtítulos del vídeo final necesitan timestamps GLOBALES; lo más simple es persistir por-slide y acumular el offset al serializar (offset = suma de duraciones de slides previos). Para ElevenLabs, los timestamps son relativos al clip del slide. Para WhisperX, también (un wav por slide).

### Anti-Patterns to Avoid
- **Leer `character_start_times_ms`/`character_durations_ms`:** son campos de la API/SDK 1.x. El SDK 2.49.0 expone `character_start_times_seconds`/`character_end_times_seconds`. Usar los `_seconds`.
- **Importar whisperx/torch a scope de módulo:** penaliza arranque y el modo elevenlabs (rompe D-06). Importar dentro de la función.
- **Hand-rollar retry de red sobre el SDK ElevenLabs:** el SDK ya reintenta errores de red; el retry ≤3 de D-02 es SOLO para timestamps degenerados, no para 429/5xx.
- **Generar solo SRT y "convertir" a VTT con regex frágil:** generar ambos desde el mismo modelo de cues (SRT usa coma, VTT usa punto + cabecera WEBVTT).
- **Quemar subtítulos en Phase 4:** prohibido por D-09; solo dejar los archivos.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Alineación audio↔texto palabra | Tu propio forced-aligner | `whisperx` (wav2vec2) | Forced alignment es un problema de ML resuelto; hacerlo a mano es inviable |
| TTS con timing | Estimar timing por WPM | `convert_with_timestamps` | El API devuelve timing real por carácter; estimar produce subtítulos desincronizados |
| Decode de audio | Parser MP3 propio | `base64.b64decode` + escribir bytes | El SDK devuelve audio listo; solo decodificar base64 y escribir |
| Leer/escribir WAV | struct/wave manual | `soundfile` (libsndfile) | Maneja formatos, samplerate, dtype, edge cases |
| Captura de micrófono | PortAudio ctypes | `sounddevice` | Wrapper Pythónico estable sobre PortAudio |
| Retry de red API | Loop 429/5xx propio | El SDK ya lo hace | Solo añadir retry para timestamps degenerados (lógica de dominio) |

**Key insight:** En este dominio, todo lo "pesado" (TTS, alineación, codecs de audio) ya está resuelto por SDKs maduros. El código propio de Phase 4 debe concentrarse en: (1) validación de timestamps, (2) modelo unificado de timings, (3) segmentación de cues + serialización SRT/VTT — los tres son **lógica pura y 100% testeable sin red**.

## Runtime State Inventory

> Phase 4 NO es un rename/refactor; es greenfield (nuevas etapas). Esta sección se incluye solo para confirmar que no hay estado runtime preexistente que migrar.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Ninguno — los checkpoints de voz/subs aún no existen (stubs escriben modelos vacíos) | Ninguna |
| Live service config | `voice_id` placeholder `21m00Tcm4TlvDq8ikWAM` en RunConfig (default Rachel de ElevenLabs) | Documentar que es placeholder; mover a config.yaml |
| OS-registered state | Ninguno | Ninguna |
| Secrets/env vars | `ELEVENLABS_API_KEY` (entorno, D-03); `ANTHROPIC_API_KEY` ya en uso; nuevo: NINGUNO para record | Ninguna — el SDK lee la key del entorno |
| Build artifacts | torch 2.9.1 + soundfile 0.12.1 ya instalados (entorno actual); no declarados en pyproject | Declarar deps; alinear torch a 2.5.1 para record |

## Common Pitfalls

### Pitfall 1: Campo de alineación seconds vs ms (versión de SDK)
**What goes wrong:** Leer `alignment.character_start_times_ms` lanza AttributeError o devuelve None con el SDK 2.49.0.
**Why it happens:** CLAUDE.md y snapshots viejos de Context7 documentan la API 1.x (milisegundos). El SDK 2.x renombró a `character_start_times_seconds`/`character_end_times_seconds` (segundos) en `CharacterAlignmentResponseModel` `[VERIFIED: github.com/elevenlabs/elevenlabs-python types/character_alignment_response_model.py]`.
**How to avoid:** Usar los campos `_seconds`. NO multiplicar por 1000 ni dividir. La validación estrictamente-creciente corre sobre `character_start_times_seconds`. Un test con un response mockeado fija el contrato.
**Warning signs:** `AttributeError: ... has no attribute 'character_start_times_ms'`; timestamps "x1000" en los subtítulos.

### Pitfall 2: torch >=2.6 rompe la carga del modelo VAD de WhisperX
**What goes wrong:** `whisperx.load_model()` falla con `_pickle.UnpicklingError: Weights only load failed` al cargar el VAD (pyannote).
**Why it happens:** torch 2.6 cambió `weights_only` a `True` por defecto en `torch.load`; los checkpoints de pyannote VAD no son seguros bajo esa política `[VERIFIED: github.com/m-bain/whisperX/issues/1304, github.com/pyannote/pyannote-audio/issues/1908]`. El entorno tiene torch 2.9.1.
**How to avoid:** Opción A (recomendada): pin `torch==2.5.1`/`torchaudio==2.5.1` (CLAUDE.md ya lo indica). Opción B: `whisperx.load_model(..., vad_method="silero")` si la versión 3.8.6 lo soporta (verificar en runtime). Opción C: `torch.serialization.add_safe_globals([...])` o parche `weights_only=False` (frágil; último recurso). El plan debe elegir A para record + Docker.
**Warning signs:** `UnpicklingError` / `Unsupported global: omegaconf.listconfig.ListConfig` al primer `load_model`.
**Nota:** La fase NO usa diarización (no requiere HF token ni pyannote diarization), pero el VAD de `load_model` SÍ usa pyannote por defecto — el pitfall aplica al camino `record`.

### Pitfall 3: El bug #607 no es de TTS sino de STT con diarización
**What goes wrong:** El plan documenta D-02 como "mitiga el bug #607 de convert_with_timestamps", cuando #607 es de `speech_to_text.convert` con `diarize=True` `[VERIFIED: github.com/elevenlabs/elevenlabs-python/issues/607]`.
**Why it happens:** Confusión de scope al referenciar el issue.
**How to avoid:** Mantener la validación estrictamente-creciente (es una salvaguarda barata y correcta) pero documentarla como "defensa contra timestamps degenerados/congelados en general", no como fix específico de #607. La intención de D-02 se respeta plenamente.
**Warning signs:** Tests que esperan reproducir #607 vía TTS (no se puede; es otro endpoint).

### Pitfall 4: ElevenLabs WPM efectivo en español ≠ duración objetivo
**What goes wrong:** La duración real del audio TTS no coincide con `timings.json` (WPM=150 estimado en Phase 2). El audio puede ser más corto/largo que el slot calculado.
**Why it happens:** El WPM efectivo de ElevenLabs en español es estimado (STATE.md lo marca como blocker pendiente de calibración en Phase 4).
**How to avoid:** Phase 4 usa la duración REAL del clip (`SlideTimings.duration`, medible del último `character_end_times_seconds` o vía ffprobe en Phase 5) como fuente de verdad para subtítulos. NO forzar el audio al slot WPM. Phase 5 (ASMB-01) ya está decidido a medir duraciones reales con ffprobe. Documentar la desviación para QA (Phase 5).
**Warning signs:** Subtítulos que terminan antes/después del audio; desfase acumulado entre slides.

### Pitfall 5: sounddevice requiere PortAudio + hardware (falla en CI/Docker)
**What goes wrong:** `import sounddevice` falla sin PortAudio; `sounddevice.rec()` falla sin dispositivo de audio (CI, Docker headless).
**Why it happens:** sounddevice es binding de PortAudio; necesita la librería de sistema y un dispositivo.
**How to avoid:** Import perezoso de sounddevice (igual que whisperx). En tests, mockear `sounddevice.rec`/`soundfile.write` (nunca grabar real). La autodetección de `slide_XX.wav` aportados permite usar `record` sin micrófono. Documentar `portaudio19-dev` para Phase 7 Docker (modo record solo desarrollo local).
**Warning signs:** `OSError: PortAudio library not found`; `PortAudioError: Error querying device`.

### Pitfall 6: Segmentación de cues que excede velocidad de lectura
**What goes wrong:** Cues con demasiado texto para su duración → ilegibles (>21 CPS).
**Why it happens:** Agrupar palabras solo por longitud sin chequear duración.
**How to avoid:** Aplicar las cuatro restricciones de D-08 + CPS: ~42 chars/línea, ≤2 líneas, ≤5s/cue, y ≤17 CPS (caracteres por segundo) como guía de legibilidad `[VERIFIED: subtitle QA best practices, múltiples fuentes]`. Romper cue cuando se exceda cualquiera. Lógica pura → test con casos límite.
**Warning signs:** Cues de 1s con 40+ caracteres; líneas que no caben en pantalla.

## Code Examples

### Serialización SRT y VTT desde cues (lógica pura — SUB-01)
```python
# Source: WebVTT spec + SRT convención [VERIFIED: múltiples fuentes subtitle format]
def fmt_ts(seconds: float, *, vtt: bool) -> str:
    h = int(seconds // 3600); m = int((seconds % 3600) // 60)
    s = int(seconds % 60); ms = int(round((seconds - int(seconds)) * 1000))
    sep = "." if vtt else ","          # VTT usa punto; SRT usa coma
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"

def to_srt(cues: list["Cue"]) -> str:
    out = []
    for i, c in enumerate(cues, start=1):           # SRT: índice 1-based
        out.append(str(i))
        out.append(f"{fmt_ts(c.start, vtt=False)} --> {fmt_ts(c.end, vtt=False)}")
        out.append(c.text)                          # ≤2 líneas separadas por \n
        out.append("")                              # línea en blanco entre cues
    return "\n".join(out)

def to_vtt(cues: list["Cue"]) -> str:
    out = ["WEBVTT", ""]                            # VTT: cabecera obligatoria, sin índices
    for c in cues:
        out.append(f"{fmt_ts(c.start, vtt=True)} --> {fmt_ts(c.end, vtt=True)}")
        out.append(c.text)
        out.append("")
    return "\n".join(out)
```

### Autodetección de WAVs aportados vs grabar (VOICE-03)
```python
# Source: patrón derivado de WorkdirManager existente
def resolve_audio(workdir, slide_index: int):
    wav = workdir.root / "audio" / f"slide_{slide_index:02d}.wav"
    if wav.exists():
        return wav                       # (b) usuario aportó el WAV → usar
    # (a) grabar con sounddevice → soundfile.write
    import sounddevice as sd, soundfile as sf
    # ... rich prompt "graba el slide N", sd.rec(...), sd.wait(), sf.write(wav, data, sr)
    return wav
```

### Wiring de etapas en PIPELINE_STAGES (D-12)
```python
# Source: patrón existente stages/stubs.py PIPELINE_STAGES
# La etapa de voz se elige por config.voice. Dos opciones de diseño:
#  A) una sola VoiceStage(stage_name="voice") que internamente despacha por config.voice
#  B) un selector que inserta VoiceElevenlabsStage o VoiceRecordStage al construir la lista
# Recomendado A: mantiene stage_name="voice" (checkpoint contract intacto, D-12) y
# evita ramas en el orquestador. La etapa align se auto-salta si config.voice==elevenlabs
# (ALIGN-02) escribiendo un UnifiedTimings ya producido por voz, o no-op idempotente.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `character_start_times_ms` / `character_durations_ms` (ms) | `character_start_times_seconds` / `character_end_times_seconds` (s) | SDK elevenlabs 2.x | Phase 4 debe leer campos `_seconds`; CLAUDE.md desactualizado |
| `generate()` / funciones top-level elevenlabs | `client.text_to_speech.convert*` métodos | SDK 1.0+ | Usar la clase `ElevenLabs` y subnamespace `text_to_speech` |
| torch.load `weights_only=False` default | `weights_only=True` default | torch 2.6 | Rompe carga VAD pyannote en whisperx → pin torch 2.5.1 |
| WhisperX VAD solo pyannote | `vad_method="silero"` disponible | whisperx 3.7+ (verificar) | Alternativa para evitar el fallo pickle |

**Deprecated/outdated:**
- `character_start_times_ms` / `character_durations_ms`: campos de la API 1.x; no presentes en `CharacterAlignmentResponseModel` del SDK 2.49.0.
- `from elevenlabs import generate`: estilo viejo; usar `ElevenLabs().text_to_speech.convert_with_timestamps`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `whisperx.align()` devuelve `word_segments` con `start`/`end` en **segundos** (float) | Patterns/Code Examples | Bajo — confirmado por Context7+README; si fuera ms, ajustar factor |
| A2 | `whisperx 3.8.6` acepta `vad_method="silero"` como alternativa al VAD pyannote | Pitfall 2 / Alternatives | Medio — verificar firma en runtime; si no existe, usar pin torch 2.5.1 (plan A) |
| A3 | El default `voice_id="21m00Tcm4TlvDq8ikWAM"` (Rachel) funciona con `eleven_multilingual_v2` en español | User Constraints | Bajo — es voz multilingüe estándar; el usuario lo configurará |
| A4 | Los timestamps de ElevenLabs y WhisperX son **relativos al clip del slide** (no globales) | Pattern 4 nota | Medio — afecta el offset al serializar subtítulos; documentar y testear con 2+ slides |
| A5 | `model.transcribe()` + `load_align_model("es")` produce buena alineación en español sin initial_prompt | ALIGN-01 | Bajo — `es` es idioma con modelo wav2vec2 por defecto en torchaudio |
| A6 | El SDK ElevenLabs reintenta errores de red por su cuenta (como el SDK anthropic) | Anti-patterns | Bajo — comportamiento estándar de SDKs Fern-generated; si no, el retry≤3 de dominio no cubre red |

## Open Questions

1. **¿Timestamps por-slide relativos o globales en `UnifiedTimings`?**
   - What we know: ElevenLabs da timestamps relativos al clip; WhisperX también (un wav por slide).
   - What's unclear: si persistir relativos (+offset al serializar) o globales.
   - Recommendation: persistir RELATIVOS por slide (más simple, idempotente por slide) y acumular offset en `subtitles.py` (offset = Σ duraciones de slides previos). Documentarlo en el modelo.

2. **¿`vad_method="silero"` existe en whisperx 3.8.6, o se fija torch 2.5.1?**
   - What we know: el VAD pyannote rompe con torch 2.6+; silero es alternativa en forks/versiones recientes.
   - What's unclear: si el parámetro está en 3.8.6 estable.
   - Recommendation: plan principal = pin `torch==2.5.1`/`torchaudio==2.5.1` (CLAUDE.md). Probar `vad_method="silero"` como mejora opcional. Decidir en Phase 7 Docker.

3. **¿Cómo selecciona el orquestador la etapa de voz por `config.voice`?**
   - What we know: D-12 exige respetar StageProtocol y `stage_name="voice"`.
   - What's unclear: una etapa que despacha internamente vs. selector que inserta clase distinta.
   - Recommendation: una `VoiceStage` única (`stage_name="voice"`) que internamente delega a `voice_elevenlabs`/`voice_record` según `config.voice` — mantiene el contrato de checkpoint y evita lógica en el orquestador.

4. **¿La etapa `align` se salta o es no-op en modo elevenlabs (ALIGN-02)?**
   - What we know: en elevenlabs los timings ya vienen del API.
   - What's unclear: si `align` no corre (skip en orquestador) o corre como passthrough.
   - Recommendation: que la voz produzca SIEMPRE `UnifiedTimings` (el checkpoint que consume subtitles). En elevenlabs, `align` es no-op idempotente (lee/reescribe el unified ya producido); en record, `align` lo genera desde los WAV. Así `subtitles.py` es agnóstico (D-11) sin ramas en el orquestador.

5. **¿`voice_id` y `whisperx_model` como nuevos campos de `RunConfig`?**
   - What we know: `voice_id` ya existe en RunConfig; CONTEXT pide `whisperx_model` configurable.
   - Recommendation: añadir `whisperx_model: str = "small"` a `RunConfig` (prefijo `AVIDEO_`, config.yaml). `voice_id` ya está; mover su default a config.yaml como placeholder documentado.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `elevenlabs` SDK | modo elevenlabs (VOICE-01) | ✗ (no instalado) | — (declarar 2.49.0) | Ninguno — bloquea elevenlabs; `uv add` |
| `ELEVENLABS_API_KEY` | modo elevenlabs (D-03) | ✗ (env no verificable aquí) | — | Ninguno — error claro en runtime si falta |
| `sounddevice` | grabación record (VOICE-03) | ✗ | — (0.5.5) | Aportar `slide_XX.wav` (autodetect) — sí hay fallback |
| `soundfile` | leer/escribir WAV | ✓ (instalado, viejo) | 0.12.1 (actualizar a 0.13.1) | — |
| `whisperx` | alineación record (ALIGN-01) | ✗ | — (3.8.5/3.8.6) | Ninguno para record; elevenlabs no lo necesita |
| `torch`/`torchaudio` | backend whisperx | ✓ (versión riesgosa) | 2.9.1 (recomendado 2.5.1) | Pin 2.5.1 o `vad_method="silero"` |
| PortAudio (sistema) | sounddevice | ? (macOS suele traerlo) | — | Aportar WAVs en vez de grabar |

**Missing dependencies with no fallback:**
- `elevenlabs` SDK + `ELEVENLABS_API_KEY` para modo elevenlabs (el por defecto) — el plan DEBE incluir `uv add elevenlabs` y leer la key del entorno.
- `whisperx` para modo record (alineación) — `uv add whisperx` (con torch primero).

**Missing dependencies with fallback:**
- `sounddevice`/PortAudio: el usuario puede aportar `slide_XX.wav` (autodetección D-04) sin grabar.
- torch 2.9.1 (riesgoso): mitigar con pin 2.5.1 o `vad_method="silero"`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest>=8.0` + `pytest-mock>=3.0` `[VERIFIED: pyproject.toml dependency-groups.dev]` |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=["tests"], pythonpath=["src"]) `[VERIFIED]` |
| Quick run command | `uv run pytest tests/test_subtitles.py tests/test_elevenlabs.py -x -q` |
| Full suite command | `uv run pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VOICE-01 | convert_with_timestamps por slide → mp3 + timings | unit (mock SDK) | `uv run pytest tests/test_voice_elevenlabs.py -x` | ❌ Wave 0 |
| VOICE-02 | validación estrictamente-creciente + retry≤3 + fallback | unit (pura + mock) | `uv run pytest tests/test_elevenlabs.py -k increasing -x` | ❌ Wave 0 |
| VOICE-03 | autodetect WAV vs grabar; export guion segmentado | unit (mock sounddevice/soundfile) | `uv run pytest tests/test_voice_record.py -x` | ❌ Wave 0 |
| ALIGN-01 | whisperx align → word_segments → UnifiedTimings | unit (mock whisperx module) | `uv run pytest tests/test_align.py -x` | ❌ Wave 0 |
| ALIGN-02 | en elevenlabs align NO corre (no-op idempotente) | unit | `uv run pytest tests/test_align.py -k elevenlabs_skip -x` | ❌ Wave 0 |
| SUB-01 | UnifiedTimings → SRT (coma) + VTT (punto, WEBVTT) | unit (PURA, sin mocks) | `uv run pytest tests/test_subtitles.py -x` | ❌ Wave 0 |
| SUB-02 | flag burn_subs registrado; Phase 4 no quema | unit | `uv run pytest tests/test_subtitles.py -k burn -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_subtitles.py tests/test_elevenlabs.py -x -q` (lógica pura, <2s)
- **Per wave merge:** `uv run pytest -q` (suite completa)
- **Phase gate:** Suite completa en verde antes de `/gsd-verify-work`.

### Qué se mockea vs qué es puro
| Componente | Estrategia de test |
|------------|--------------------|
| ElevenLabs API (`convert_with_timestamps`) | MOCK — parchear `avideo.stages.voice_elevenlabs.<fn>` (mock point a nivel módulo, patrón anthropic) con un response que tenga `.audio_base64` y `.alignment.character_start_times_seconds` |
| WhisperX (`load_model`/`align`) | MOCK — parchear el módulo whisperx; nunca cargar modelos reales en CI |
| sounddevice (`rec`/`wait`) + soundfile (`write`) | MOCK — nunca grabar/escribir audio real en CI |
| Validación estrictamente-creciente | PURO — función testeable con listas (crecientes, planas, decrecientes) |
| Segmentación de cues (42 chars, ≤2 líneas, ≤5s, ≤17 CPS) | PURO — casos límite sin I/O |
| Serialización SRT/VTT (fmt_ts coma vs punto, índices, WEBVTT) | PURO — assert sobre strings exactos |
| Autodetección WAV (existe → usar) | PURO/semi — tmp_path con/sin slide_XX.wav |

### Wave 0 Gaps
- [ ] `tests/test_subtitles.py` — SUB-01/SUB-02 (PURO: SRT/VTT format, cue segmentation, CPS)
- [ ] `tests/test_elevenlabs.py` — VOICE-02 (validación creciente + retry; mock SDK)
- [ ] `tests/test_voice_elevenlabs.py` — VOICE-01 (mp3 escrito, UnifiedTimings)
- [ ] `tests/test_voice_record.py` — VOICE-03 (autodetect + mock grabación)
- [ ] `tests/test_align.py` — ALIGN-01/ALIGN-02 (mock whisperx; skip en elevenlabs)
- [ ] `tests/conftest.py` — fixtures: fake ElevenLabs response, fake whisperx word_segments, WorkdirManager en tmp_path
- [ ] Framework install: ya presente (pytest+pytest-mock en dev group) — sin acción

## Security Domain

> `security_enforcement` no aparece explícito en config.json `workflow` — se asume habilitado (defensa por defecto). Phase 4 tiene superficie de seguridad acotada (API keys + entrada de texto a TTS).

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — (no hay auth de usuarios) |
| V3 Session Management | no | — |
| V4 Access Control | no | — (CLI local mono-usuario) |
| V5 Input Validation | yes | Pydantic valida `UnifiedTimings`/`VoiceOutput`; el texto del guion ya viene validado de Phase 2; validar paths de WAV aportados dentro de `workdir/audio/` (no path traversal) |
| V6 Cryptography | no (relevante: secretos) | `ELEVENLABS_API_KEY` SOLO desde entorno (D-03); nunca loguear ni incrustar (mismo patrón que `ANTHROPIC_API_KEY` en anthropic.py) |
| V7 Error Handling/Logging | yes | Errores claros con rich; NUNCA loguear la API key ni el audio base64 completo |

### Known Threat Patterns for {Python CLI + APIs externas}
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Fuga de API key en logs/checkpoints | Information Disclosure | Key solo en entorno; cliente lazy; no serializar la key; no loguear headers |
| Path traversal en `slide_XX.wav` aportado | Tampering | Construir paths SOLO vía WorkdirManager; validar que el archivo está bajo `workdir/audio/` |
| Texto malicioso del guion enviado a TTS | Tampering | Bajo riesgo (es nuestro propio guion de Phase 2); no se ejecuta como código |
| Carga de modelo whisperx (pickle) | Tampering/RCE | Modelos de fuentes oficiales (faster-whisper/torchaudio); el fix `weights_only` de torch reduce superficie pickle |

## Sources

### Primary (HIGH confidence)
- Context7 `/elevenlabs/elevenlabs-python` — `convert_with_timestamps`, alignment shape, audio_base64
- `github.com/elevenlabs/elevenlabs-python/blob/main/src/elevenlabs/types/character_alignment_response_model.py` — campos `character_start_times_seconds`/`character_end_times_seconds` (SEGUNDOS) [VERIFIED]
- `elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps` — response fields, output formats
- Context7 `/m-bain/whisperx` — `load_model`/`load_align_model`/`align`, word_segments, CPU int8
- `github.com/m-bain/whisperX/blob/main/README.md` — CPU usage, idiomas (es), model sizes
- `pip index versions` (local) — versiones exactas elevenlabs/whisperx/sounddevice/soundfile [VERIFIED]
- Código existente: `src/avideo/integrations/anthropic.py`, `stages/storyboard.py`, `utils/workdir.py`, `models/*` — patrones del proyecto [VERIFIED]

### Secondary (MEDIUM confidence)
- `github.com/elevenlabs/elevenlabs-python/issues/607` — bug es STT+diarize, no TTS [VERIFIED via WebFetch]
- `github.com/m-bain/whisperX/issues/1304`, `github.com/pyannote/pyannote-audio/issues/1908` — torch 2.6 weights_only rompe VAD pyannote
- Múltiples fuentes subtitle QA — 42 chars/línea, ≤17 CPS, SRT coma vs VTT punto

### Tertiary (LOW confidence)
- Snapshot Context7 con `character_start_times_ms` — OBSOLETO (API 1.x); marcado y desestimado a favor del source code del SDK 2.x

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versiones verificadas contra PyPI; API shape contra source code del SDK
- Architecture: HIGH — replica patrones ya consolidados en el codebase (lazy client, module-scope mock point, checkpoint contract)
- ElevenLabs API (seconds vs ms): HIGH — confirmado en el source del SDK 2.x
- WhisperX CPU/torch compat: MEDIUM-HIGH — workflow verificado; el detalle `vad_method="silero"` en 3.8.6 requiere verificación en runtime (A2)
- Subtitle formats: HIGH — spec WebVTT + convención SRT bien establecidas
- Pitfalls: HIGH — los tres principales (seconds/ms, torch VAD, #607 scope) verificados con fuentes primarias

**Research date:** 2026-05-25
**Valid until:** 2026-06-24 (30 días; ecosistema TTS/whisperx evoluciona — re-verificar versiones si se planifica tarde)
