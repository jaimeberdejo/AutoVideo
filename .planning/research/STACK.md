# Stack Research

**Domain:** Python GUI-over-CLI — pipeline de vídeo narrado con UI Streamlit guiada (v2.0.0 Studio Guiado)
**Researched:** 2026-05-29
**Confidence:** HIGH (todas las versiones nuevas verificadas en PyPI y Context7; stack existente v1 sin cambios)

---

## Context: What Changes in v2.0.0

El stack de v1.60.0 (`anthropic`, `playwright`, `jinja2`, `elevenlabs`, `pydantic`, `typer`, `ffmpeg`, `rich`, `pyyaml`, `python-pptx`, `PyMuPDF`, `pdf2image`, `sounddevice`, `soundfile`, `whisperx`, `python-lucide`, `pytest`, `python-dotenv`) **no cambia**. Esta sección documenta SOLO las adiciones requeridas para las 4 capacidades nuevas:

1. UI Streamlit guiada (wizard de 6 fases)
2. OpenAI Audio como tercer proveedor TTS
3. Música de fondo con ducking + fades (FFmpeg puro)
4. Mejora automática de audio grabado (denoise + normalización)

---

## New Stack Additions for v2.0.0

### Core Technologies (nuevas)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `streamlit` | `>=1.58.0` | UI web local — wizard de 6 fases con human-check entre fases | Framework Python-only que convierte un script Python en una app web local sin ningún JS/frontend; 1.58.0 (mayo 2026) es la última estable con soporte Python 3.10-3.14; incluye `st.session_state`, `st.status`, `st.fragment`, `st.pagination` para wizard |
| `openai` | `>=2.38.0` | Tercer proveedor TTS: `client.audio.speech.create()` | SDK oficial OpenAI para Python ≥3.9; v2.38.0 es la última estable (mayo 2026); soporta `tts-1`, `tts-1-hd`, `gpt-4o-mini-tts`; `response_format="mp3"`; streaming vía `with_streaming_response.create()` |

### Supporting Libraries (nuevas)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `watchdog` | `>=6.0.0` | Monitorizar cambios en `workdir/` desde la UI para detectar progreso de etapas | Solo si se necesita polling reactivo desde la UI hacia los checkpoints del pipeline; alternativa: polling simple con `time.sleep` + `st.rerun()` |
| `python-dotenv` | `>=1.0` | Cargar `OPENAI_API_KEY` (y demás) desde `.env` | Ya en `[dev]`; **mover a `[project.dependencies]`** — la UI necesita leer claves en producción, no solo en dev |

**Nota sobre audio enhancement:** No se añade ninguna librería nueva. El denoise (`afftdn` o `arnndn`) y la normalización (`loudnorm` EBU R128) se implementan **100% con FFmpeg via subprocess**, que ya es dependencia del proyecto. Ver "Stack Patterns by Variant" abajo.

---

## FFmpeg Filters for New v2 Capabilities (sin dependencia nueva)

Estas capacidades se implementan con filtros FFmpeg ya presentes en el binario `>=6.1`:

### Música de fondo con ducking

```
ffmpeg -i narration.mp3 -i music.mp3 \
  -filter_complex "
    [1:a]volume=0.3,afade=t=in:st=0:d=2,afade=t=out:st=<end-2>:d=2[bg];
    [0:a]asplit=2[sc][main];
    [bg][sc]sidechaincompress=threshold=0.02:ratio=10:attack=50:release=500[ducked];
    [main][ducked]amix=inputs=2:duration=first[out]
  " -map "[out]" output.mp3
```

Filtros usados: `volume`, `afade` (fade in/out), `sidechaincompress` (ducking), `amix`. Todos built-in en FFmpeg ≥6.1. No requiere librería Python adicional.

### Denoise de audio grabado

```
ffmpeg -i recorded.wav \
  -af "afftdn=nr=12:nf=-40,loudnorm=I=-16:TP=-1.5:LRA=11" \
  enhanced.wav
```

Filtros usados: `afftdn` (denoising FFT built-in) + `loudnorm` (ya usado en el pipeline v1 para EBU R128). El flujo de dos pasadas de `loudnorm` ya está implementado en el ensamblador; reutilizar la misma lógica para el enhancement previo a la voz.

---

## Streamlit Architecture for the Guided Wizard

### Pattern: Session-State Gated Wizard

El wizard de 6 fases se implementa con un **entero de fase en `st.session_state`** — la única fuente de verdad sobre dónde está el usuario. Cada fase renderiza su contenido y solo muestra el botón "Aprobar y continuar" cuando los datos de esa fase están completos.

```python
# Inicialización
if "phase" not in st.session_state:
    st.session_state.phase = 1  # 1-6

# Cada fase renderiza condicionalmente
if st.session_state.phase >= 1:
    render_phase_1()
if st.session_state.phase >= 2:
    render_phase_2()
# ...

# Gate: avanzar solo al confirmar
if st.button("Aprobar y continuar", key="approve_p1"):
    st.session_state.phase = 2
    st.rerun()
```

- `st.session_state` persiste entre reruns en la misma sesión (single-user local — sin problema de concurrencia).
- `st.status` para mostrar progreso de etapas largas (storyboard, renders, TTS, FFmpeg).
- `st.fragment` para actualizar secciones de la UI sin rerun completo (thumbnails, previews).
- `st.pagination` (disponible desde specs 2026-03) como opción de navegación entre fases.

### Pattern: Pipeline Stages como Funciones Síncronas

Las etapas del pipeline existente (`run_storyboard`, `run_scriptwriter`, `run_slides_auto`, `run_voice_elevenlabs`, etc.) se invocan **directamente desde el script Streamlit**, no como subprocess. Streamlit ejecuta el script completo en cada rerun; las etapas largas deben envolver su llamada en `st.status` con un spinner.

```python
with st.status("Generando storyboard...", expanded=True) as s:
    result = run_storyboard(config, workdir)
    s.update(label="Storyboard listo", state="complete")
```

**IMPORTANTE:** No usar `threading.Thread` ni `subprocess.Popen` para invocar las etapas — Streamlit's `add_script_run_ctx` es necesario si se usan hilos, y añade complejidad. La arquitectura de checkpoints idempotentes del pipeline v1 hace que reinvocar una etapa ya completada sea barato (carga desde JSON en vez de reejecutar).

### Pattern: Previews de Media

- Slide thumbnails: `st.image(path_to_png)` — devuelve imagen desde ruta local.
- Audio preview: `st.audio(path_to_mp3)` — player HTML5 nativo.
- Video final: `st.video(path_to_mp4)` — player HTML5 nativo; `st.download_button` para descarga.

---

## OpenAI Audio TTS Integration Pattern

```python
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

response = client.audio.speech.create(
    model="gpt-4o-mini-tts",   # o "tts-1" para menor latencia
    voice="nova",               # alloy, ash, coral, echo, fable, onyx, nova, sage, shimmer
    input=script_text,
    response_format="mp3",
    speed=1.0,
)
response.stream_to_file(output_path)
```

**Limitación crítica vs ElevenLabs:** `client.audio.speech.create()` devuelve el audio pero **no devuelve timestamps** de caracteres o palabras. El proveedor OpenAI Audio no puede generar `timings.json` directamente. Opciones de mitigación:
1. Usar WhisperX post-hoc sobre el MP3 generado para alinear (añade latencia y dependencia torch).
2. Usar el endpoint de transcripción de OpenAI sobre el propio audio generado para obtener word timestamps (`client.audio.transcriptions.create(model="whisper-1", response_format="verbose_json", timestamp_granularities=["word"])`).
3. Estimar timings por duración proporcional al número de caracteres (opción mínima viable, menos precisa).

**Recomendación:** Implementar opción 2 (transcribir el propio audio con Whisper para obtener timestamps) — usa el mismo SDK `openai` ya añadido, no requiere torch, y es aceptablemente preciso para subtítulos. Documentar en código como limitación conocida del proveedor.

---

## Recommended Stack

### Core Technologies (stack completo v2.0.0)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11+ | Lenguaje base | Requisito del proyecto; sin cambio |
| `streamlit` | `>=1.58.0` | UI web local — wizard guiado | **NUEVO v2** — Python-only, zero JS, `session_state` para gated phases, media display nativo |
| `openai` | `>=2.38.0` | TTS OpenAI Audio + Whisper timestamps | **NUEVO v2** — SDK oficial; `audio.speech.create()` + `audio.transcriptions.create()` |
| `anthropic` | `>=0.104.1` | LLM: storyboard, guion, verificador visión | Sin cambio |
| `playwright` | `>=1.60.0` | Render HTML → PNG slides | Sin cambio |
| `jinja2` | `>=3.1.6` | Templates HTML slides | Sin cambio |
| `elevenlabs` | `>=2.49.0` | TTS con timestamps por carácter | Sin cambio |
| `pydantic` | `>=2.13.4` | Validación I/O entre etapas | Sin cambio |
| `typer` | `>=0.25.1` | CLI `avideo generate` (motor headless) | Sin cambio — la UI orquesta las etapas directamente, CLI conservado |
| `ffmpeg` (binary) | `>=6.1` | Montaje + ducking + denoise + loudnorm | Sin cambio — los filtros nuevos (`afftdn`, `sidechaincompress`, `afade`) son built-in |

### Supporting Libraries (stack completo v2.0.0)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `rich` | `>=15.0.0` | Logging CLI | Sin cambio |
| `pyyaml` | `>=6.0.3` | `bullets.yaml`, `theme.yaml` | Sin cambio |
| `python-pptx` | `>=1.0.2` | Ingesta .pptx | Sin cambio |
| `PyMuPDF` | `>=1.27.2.3` | Ingesta/rasterizado PDF | Sin cambio |
| `pdf2image` | `>=1.17.0` | Rasterizado PDF → PIL | Sin cambio |
| `sounddevice` | `>=0.5.5` | Grabación modo record | Sin cambio |
| `soundfile` | `>=0.13.1` | Lectura/escritura .wav | Sin cambio |
| `whisperx` | `>=3.8.5` | Alineación modo record | Sin cambio; extra opcional `[record]` |
| `python-lucide` | `>=0.2.24` | Iconos SVG offline | Sin cambio |
| `python-dotenv` | `>=1.0` | Cargar claves API | **MOVER de `[dev]` a `[project.dependencies]`** — UI necesita claves en producción |

### Development Tools (sin cambio)

| Tool | Purpose | Notes |
|------|---------|-------|
| `uv` | Gestión de dependencias | Sin cambio; añadir `streamlit` y `openai` con `uv add` |
| `pyproject.toml` | Declaración del proyecto | Añadir `streamlit>=1.58.0` y `openai>=2.38.0` a `[project.dependencies]` |
| Docker (`mcr.microsoft.com/playwright/python:v1.60.0-noble`) | Empaquetado reproducible | Sin cambio de imagen base; Streamlit sirve en `localhost:8501` — exponer puerto en Dockerfile |
| `pytest` + `pytest-mock` | Tests | Sin cambio |

---

## Installation (adiciones v2.0.0)

```bash
# Añadir dependencias nuevas al proyecto existente
uv add "streamlit>=1.58.0" "openai>=2.38.0"

# Mover python-dotenv de dev a producción
uv add "python-dotenv>=1.0"
uv remove --dev python-dotenv  # si estaba solo en dev

# Añadir OPENAI_API_KEY al .env
echo "OPENAI_API_KEY=sk-..." >> .env

# Ejecutar la UI Streamlit
uv run streamlit run src/avideo/ui/app.py

# En Docker: exponer el puerto de Streamlit
# EXPOSE 8501
# CMD ["uv", "run", "streamlit", "run", "src/avideo/ui/app.py", "--server.headless=true"]
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `streamlit` | FastAPI + React/Vue | Si se necesita multi-usuario real, auth, REST API propia, o despliegue en la nube con muchos usuarios simultáneos; para uso local single-user, FastAPI+frontend es exceso de complejidad |
| `streamlit` | Gradio | Si el dominio fuera puramente ML inference (demo de modelos); para un wizard multi-fase con estado complejo y previews de media, Streamlit es más flexible |
| `streamlit` | Textual (TUI) | Si se quisiera una TUI en terminal en vez de browser; descartado en PROJECT.md — la UI debe mostrar thumbnails de slides y reproducir vídeo |
| `streamlit` | Panel/Dash | Si el caso fuera dashboards analíticos reactivos; overhead arquitectural vs Streamlit para un wizard lineal single-user |
| `openai` SDK (audio) | HTTP directo `httpx` | Si el SDK introduce breaking changes; la API REST de OpenAI Audio es estable y documentada |
| `openai` SDK para Whisper timestamps | `whisperx` post-TTS OpenAI | Si se quieren timestamps word-level más precisos con forced alignment; añade dependencia torch (~2GB); para el caso OpenAI-TTS, transcribir el propio audio con `whisper-1` es suficientemente preciso y no añade dependencia |
| FFmpeg `afftdn` (denoise built-in) | `noisereduce` Python lib | Si se necesita denoise parametrizable desde Python sin invocar ffmpeg; para este proyecto, mantener todo en ffmpeg preserva la homogeneidad del stack y no añade dependencia |
| FFmpeg `sidechaincompress` (ducking) | `pydub` + manual mix | Pydub no ofrece ducking por sidechain; ffmpeg tiene el filtro nativo y ya es dependencia; no añadir pydub |
| FFmpeg filtros + subprocess (enhancement) | `ffmpeg-normalize` CLI wrapper | `ffmpeg-normalize` 1.37.8 es un wrapper útil pero añade una dep para algo que ya se puede hacer con los filtros que el pipeline usa en su etapa de assemble; no justificado para un solo comando |

---

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Frameworks JS frontend (React, Vue, Svelte, Next.js) | Out of scope explícito; Python-only es requisito; añadirían build toolchain, npm, node — destruyen la simplicidad del proyecto | `streamlit` Python-only |
| `moviepy` | Excluido explícitamente en PROJECT.md; overhead de abstracciones; más lento que FFmpeg directo | `ffmpeg` via `subprocess` |
| `gradio` | Más limitado que Streamlit para wizards multi-fase con estado complejo; su UX es por defecto para demos de inference, no para pipelines de producción | `streamlit` |
| `fastapi` + frontend | Multi-usuario, REST API, JS frontend — exceso para single-user local | `streamlit` |
| `pydub` | Wralea `ffmpeg`/`avconv` con API Python pero no soporta sidechain compression ni filtros avanzados; añade dep sin beneficio | FFmpeg filtros directos |
| `noisereduce` (Python) | Librería de denoise en Python/scipy; añade dependencia de ~50MB cuando `afftdn` built-in de FFmpeg es suficiente para el caso de uso (mejora de grabación de usuario) | FFmpeg `afftdn` filter |
| `whisperx` para timestamps de OpenAI TTS | `torch>=2.5.1` + modelo ~150MB solo para alinear audio que OpenAI ya puede transcribir de vuelta con `whisper-1`; el extra `[record]` ya tiene whisperx para quien graba | `openai.audio.transcriptions.create()` con `verbose_json` + `timestamp_granularities=["word"]` |
| `langchain` / `langgraph` | Pipeline secuencial; ya existe el orquestador propio; LangChain añade abstracción opaca sobre el SDK `anthropic` que ya está integrado | SDK `anthropic` directo |
| `streamlit-authenticator` o auth libraries | Single-user local, localhost — auth es innecesario | Sin auth |
| `celery` / `rq` (task queues) | Single-user, pipeline secuencial, ejecución síncrona; no hay concurrencia real que justifique una cola | Llamadas síncronas directas desde Streamlit |

---

## Stack Patterns by Variant

**UI Streamlit — wizard de 6 fases:**
- `st.session_state["phase"]` (int 1-6) controla qué fases se renderizan
- Botón "Aprobar" avanza el int y llama `st.rerun()` — no hay framework de wizard externo
- `st.status(label, expanded=True)` para etapas largas (storyboard, TTS, render slides, FFmpeg)
- `st.fragment` para actualizar thumbnails sin rerun completo de la app
- `st.image()`, `st.audio()`, `st.video()` para previews locales directamente desde `workdir/`
- `st.download_button(data=open(mp4, "rb"))` para descarga del vídeo final

**Modo de voz `openai` (nuevo):**
- `client.audio.speech.create(model="gpt-4o-mini-tts", voice="nova", input=text, response_format="mp3")` → `.stream_to_file(path)`
- Para timestamps: `client.audio.transcriptions.create(file=open(mp3, "rb"), model="whisper-1", response_format="verbose_json", timestamp_granularities=["word"])` sobre el propio audio generado
- Guardar `timings.json` con el mismo esquema que ElevenLabs (word-level timestamps)
- `OPENAI_API_KEY` en `.env`, cargada con `python-dotenv` al inicio del script

**Audio enhancement (Fase 4 UI — audios subidos por usuario):**
- Denoise + normalize en una sola pasada FFmpeg:
  `ffmpeg -i input.wav -af "afftdn=nr=12:nf=-40,loudnorm=I=-16:TP=-1.5:LRA=11" output_enhanced.wav`
- Botón en UI: "Mejorar audio" → llama a función Python que invoca subprocess con el filtro → `st.audio(enhanced_path)` para preview
- No se ejecuta si el usuario usa ElevenLabs u OpenAI TTS (solo para grabaciones propias subidas)

**Música de fondo con ducking (Fase 5 UI):**
- `st.file_uploader("Música de fondo", type=["mp3", "wav", "aac"])` → guardar en `workdir/bgmusic.<ext>`
- En la etapa de assemble: añadir music track al filtro FFmpeg existente con `sidechaincompress` para ducking
- Parámetros ducking recomendados: `threshold=0.02:ratio=10:attack=50:release=500`
- `afade=t=in:st=0:d=2` y `afade=t=out:st=<end-2>:d=2` para fades de entrada/salida
- Si no se sube música, el assemble procede igual que v1 (rama condicional en el comando ffmpeg)

**Docker con Streamlit:**
- Misma imagen base: `mcr.microsoft.com/playwright/python:v1.60.0-noble`
- Añadir al Dockerfile:
  ```dockerfile
  EXPOSE 8501
  CMD ["uv", "run", "streamlit", "run", "src/avideo/ui/app.py", \
       "--server.headless=true", "--server.address=0.0.0.0"]
  ```
- No se necesita ningún servidor web adicional (Streamlit incluye Tornado)

---

## Version Compatibility (adiciones v2.0.0)

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `streamlit>=1.58.0` | Python 3.10-3.14 | Requiere Python >=3.10; compatible con Python 3.11 del proyecto; 1.58.0 publicado mayo 2026 |
| `openai>=2.38.0` | Python 3.9-3.14 | Versión 2.38.0 publicada mayo 21, 2026; compatible con Python 3.11; instalar `httpx` transitive dep (ya incluido) |
| `streamlit>=1.58.0` | `pydantic>=2.13.4` | Compatible; Streamlit usa pydantic internamente en versiones recientes |
| `openai>=2.38.0` | `anthropic>=0.104.1` | Compatible; ambos usan `httpx` como HTTP client; sin conflicto de dependencias |
| `streamlit>=1.58.0` | `typer>=0.25.1` | Sin conflicto; Streamlit no interfiere con Typer CLI (son entry points distintos) |
| `python-dotenv>=1.0` | todos | Sin conflicto; mover de `[dev]` a `[project.dependencies]` para que `load_dotenv()` funcione en la UI |

---

## pyproject.toml Changes for v2.0.0

```toml
[project.dependencies]  # añadir:
"streamlit>=1.58.0",
"openai>=2.38.0",
"python-dotenv>=1.0",   # mover desde [dev]

[dependency-groups]
dev = [
    # python-dotenv ya no aquí
    "pillow>=12.2.0",
    "pytest>=8.0",
    "pytest-mock>=3.0",
]
```

---

## Sources

- [streamlit · PyPI](https://pypi.org/project/streamlit/) — versión 1.58.0 verificada (mayo 2026); Python >=3.10
- [openai · PyPI](https://pypi.org/project/openai/) — versión 2.38.0 verificada (mayo 2026); Python >=3.9
- Context7 `/streamlit/streamlit` — `st.session_state`, `st.pagination`, `st.fragment`, `st.status`, `st.rerun`, `st.file_uploader` (CONFIANZA: ALTA)
- Context7 `/openai/openai-python` — `audio.speech.create()`, `SpeechCreateParams`, `response_format`, modelos `tts-1`/`gpt-4o-mini-tts` (CONFIANZA: ALTA)
- [OpenAI Text to Speech guide](https://developers.openai.com/api/docs/guides/text-to-speech) — modelos, voces, streaming (CONFIANZA: ALTA)
- [FFmpeg Filters Documentation](https://ffmpeg.org/ffmpeg-filters.html) — `afftdn`, `arnndn`, `sidechaincompress`, `afade`, `loudnorm`, `amix` (CONFIANZA: ALTA)
- [ffmpeg-normalize · PyPI](https://pypi.org/project/ffmpeg-normalize/) — versión 1.37.8 (mayo 2026); descartado — el pipeline ya usa `loudnorm` directamente (CONFIANZA: ALTA)
- [Streamlit Threading Docs](https://docs.streamlit.io/develop/concepts/design/multithreading) — patrones de threading y `add_script_run_ctx` (CONFIANZA: ALTA)
- [Streamlit Session State Docs](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state) — wizard pattern via session state integer (CONFIANZA: ALTA)
- [Streamlit st.status Docs](https://docs.streamlit.io/develop/api-reference/status/st.status) — long-running task display (CONFIANZA: ALTA)
- [m-bain/whisperX GitHub issues #1051](https://github.com/m-bain/whisperX/issues/1051) — torch compatibility (sin cambio v2) (CONFIANZA: ALTA)

---

*Stack research for: CLI Python + Streamlit UI — pipeline de vídeo narrado v2.0.0 Studio Guiado*
*Researched: 2026-05-29*
