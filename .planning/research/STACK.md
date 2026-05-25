# Stack Research

**Domain:** CLI Python — pipeline de vídeo narrado (slides generadas + voz en off)
**Researched:** 2026-05-25
**Confidence:** HIGH (todas las versiones verificadas en PyPI y fuentes oficiales)

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11+ | Lenguaje base | Requisito del proyecto; 3.11 óptimo por balance estabilidad/velocidad vs 3.12/3.13; todas las librerías clave lo soportan |
| `anthropic` | `>=0.104.1` | LLM API: storyboard, guion, verificador con visión | SDK oficial de Anthropic; la versión 0.104.1 (mayo 2026) incluye soporte completo de visión base64/PNG para el verificador de slides |
| `playwright` | `>=1.60.0` | Render HTML/CSS → PNG para slides | Única opción fiable para render pixel-perfect de HTML a imagen en Python; headless Chromium; screenshots nativos en PNG sin dependencias externas |
| `jinja2` | `>=3.1.6` | Templating HTML para slides | Motor de plantillas estándar; integración nativa con Playwright; permite `theme.yaml` → HTML sin fricción |
| `elevenlabs` | `>=2.49.0` | TTS con timestamps por carácter | SDK oficial con `convert_with_timestamps()` y `stream_with_timestamps()` — devuelve `character_start_times_ms` y `character_durations_ms` sin pipeline extra de alineación |
| `pydantic` | `>=2.13.4` | Validación de I/O entre etapas del pipeline | v2 es la versión activa (v1 deprecated); `model_dump_json()` / `model_validate_json()` para checkpoints; Rust core = validación ultrarrápida |
| `typer` | `>=0.25.1` | CLI con subcomandos y opciones tipadas | Estándar actual para CLIs Python con type hints; `@app.callback()` + subcomandos; requiere Python >=3.10 |
| `ffmpeg` (binary) | `>=6.1` via sistema/Docker | Montaje de vídeo: concat slides+audio, subtítulos, loudnorm | Invocación directa por `subprocess`; control total sobre filtros, crossfade, `loudnorm`; sin intermediarios |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `rich` | `>=15.0.0` | Logging, progress bars, tablas en terminal | Siempre — es el companion natural de Typer para UX de CLI |
| `pyyaml` | `>=6.0.3` | Parsear `bullets.yaml` y `theme.yaml` | Carga de configuración del usuario (bullets, tema visual) |
| `python-pptx` | `>=1.0.2` | Ingesta de `.pptx` (modo hybrid/manual) y export opcional | Extracción de texto de slides existentes como contexto; export opcional a .pptx |
| `PyMuPDF` | `>=1.27.2.3` | Ingesta/rasterizado de PDF | Extracción de texto y rasterizado de páginas PDF a imagen para verificador; Python >=3.10 |
| `pdf2image` | `>=1.17.0` | Rasterizado PDF → PIL Image | Alternativa/complemento a PyMuPDF para convertir slides .pdf a imagen antes del verificador; requiere Poppler en sistema |
| `sounddevice` | `>=0.5.5` | Grabación de audio (modo record) | Solo modo `record`; captura desde micrófono a numpy array |
| `soundfile` | `>=0.13.1` | Lectura/escritura de archivos .wav | Guardar grabaciones y leer audios locales (modo record) |
| `whisperx` | `>=3.8.5` | Alineación audio-texto con timestamps (modo record) | Solo modo `record`; proporciona timestamps palabra-a-palabra para subtítulos SRT/VTT; requiere torch>=2.5 |
| `lucide-py` o `python-lucide` | latest | Iconos SVG Lucide incrustados en templates Jinja2 | Integración de iconos offline en HTML de slides; `python-lucide` tiene BD SQLite embebida sin internet |
| `pytest` | `>=8.x` | Tests unitarios | Framework estándar; testeo de storyboard (API mockeada), director de timing, render de slide |
| `pytest-mock` | `>=3.x` | Mocking de API calls en tests | Mockear llamadas Anthropic y ElevenLabs en tests |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `uv` | Gestión de dependencias y entorno virtual | Reemplaza pip+venv+pip-tools; 10-100x más rápido; genera `uv.lock` multiplataforma; `uv run`, `uv add`, `uv sync` |
| `pyproject.toml` | Declaración del proyecto y dependencias | Estándar PEP 517/518; `[project]` con `requires-python = ">=3.11"` + `[tool.uv]` |
| Docker (`mcr.microsoft.com/playwright/python:v1.60.0-noble`) | Empaquetado reproducible | Imagen oficial Microsoft con Python + Playwright + browsers Chromium/Firefox/WebKit + deps sistema; añadir FFmpeg y WhisperX encima |
| `python-dotenv` | Carga de claves de API desde `.env` | `ANTHROPIC_API_KEY` y `ELEVENLABS_API_KEY` en desarrollo local |

---

## Installation

```bash
# Inicializar proyecto con uv
uv init auto-video-narrado
cd auto-video-narrado

# Especificar Python 3.11
echo "3.11" > .python-version

# Dependencias core
uv add anthropic>=0.104.1 playwright>=1.60.0 jinja2>=3.1.6 \
       elevenlabs>=2.49.0 pydantic>=2.13.4 typer>=0.25.1 \
       rich>=15.0.0 pyyaml>=6.0.3

# Ingesta de contexto
uv add "python-pptx>=1.0.2" "PyMuPDF>=1.27.2.3" "pdf2image>=1.17.0"

# Audio (modo record)
uv add sounddevice>=0.5.5 soundfile>=0.13.1

# WhisperX — instalación separada por complejidad de dependencias torch
# IMPORTANTE: instalar torch PRIMERO con la versión correcta de CUDA antes de whisperx
# pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
uv add whisperx>=3.8.5  # Requiere torch>=2.5.1, torchaudio, faster-whisper, pyannote.audio

# Iconos SVG
uv add python-lucide  # O lucide-py — ver notas en "Patterns by Variant"

# Dev dependencies
uv add --dev pytest pytest-mock python-dotenv

# Instalar browsers de Playwright (NECESARIO tras instalar el paquete)
uv run playwright install chromium
# O todos los browsers:
uv run playwright install
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `playwright` + Chromium | `WeasyPrint`, `wkhtmltopdf` | Nunca para este caso: WeasyPrint no soporta CSS moderno (grid, variables, transforms); wkhtmltopdf abandonado |
| `playwright` (sync API) | `playwright` (async API) | Usar async si el pipeline se convierte a asyncio; para pipeline secuencial, sync es más simple y legible |
| `ffmpeg` por subprocess | `moviepy` | MoviePy está explícitamente excluido (ver Out of Scope); ffmpeg directo da control total sobre filtros, codecs y rendimiento |
| `ffmpeg` por subprocess | `ffmpeg-python` (wrapper) | Si se necesita construir grafos de filtros complejos dinámicamente; para este pipeline, subprocess con strings de comando es más transparente y debuggable |
| `pydantic` v2 | `pydantic` v1 | Nunca: v1 está en mantenimiento únicamente; v2 es incompatible hacia atrás pero es el estándar activo |
| `typer` | `click` | Si se necesita compatibilidad Python <3.10; typer se basa en click internamente pero añade type hints y autocompletado |
| `typer` | `argparse` | Nunca para este proyecto: argparse no escala bien a CLI complejas con múltiples subcomandos y opciones tipadas |
| `elevenlabs` SDK | HTTP directo con `httpx`/`requests` | Si el SDK introduce breaking changes; la API REST de ElevenLabs es bien documentada y estable |
| `python-lucide` | CDN de Lucide | Nunca en producción: la generación de slides debe funcionar offline y en Docker sin acceso a internet |
| `whisperx` | `openai-whisper` directo | Si no se necesitan timestamps palabra-a-palabra; whisperX añade forced alignment con wav2vec2 sobre Whisper |
| `PyMuPDF` | `pdfplumber`, `pypdf` | Si solo se necesita extracción de texto (sin rasterizado): pdfplumber es más simple; PyMuPDF es superior para rasterizado de páginas |
| `uv` | `poetry`, `pipenv`, `pip` | Si el equipo ya usa poetry y no quiere migrar; uv es compatible con pyproject.toml estándar |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `moviepy` | Explícitamente excluido del proyecto; overhead de abstracciones innecesarias; más lento que FFmpeg directo | `ffmpeg` por `subprocess` |
| `langchain` / `langgraph` | Excesiva complejidad para un pipeline secuencial; dependencias pesadas; abstracción opaca sobre la API de Anthropic | SDK `anthropic` directo + orquestador propio |
| `n8n` | Orquestador visual externo; requiere servidor adicional; no es código Python controlable | Orquestador propio en Python con checkpoints en `./workdir/` |
| `pydantic` v1 | En modo mantenimiento únicamente; incompatible con ecosistema moderno; `.json()` deprecated | `pydantic>=2.13` con `model_dump_json()` |
| `dalle` / `stable-diffusion` / cualquier generador de imágenes IA | Decisión de diseño explícita: visuales 100% reproducibles | Iconos SVG (Lucide/Heroicons) + gráficos por código en HTML/CSS |
| `openai` SDK para Whisper | Requiere API key y envío de audio a la nube; latencia y coste | `whisperx` local (solo modo record) |
| `wkhtmltopdf` | Proyecto abandonado (último release 2020); no soporta CSS moderno | `playwright` headless |
| `WeasyPrint` | No soporta CSS Grid, CSS Custom Properties, ni transformaciones complejas | `playwright` headless |
| `imageio` / `PIL/Pillow` como renderizador de slides | No pueden renderizar HTML/CSS | `playwright` para render; `Pillow` solo como utilidad de post-proceso si fuera necesario |
| Stocks de imágenes / bancos de fotos | Excluido explícitamente; problemas de licencias y reproducibilidad | Iconos SVG offline + gráficos por código |

---

## Stack Patterns by Variant

**Modo de voz `elevenlabs` (default):**
- Usar `client.text_to_speech.convert_with_timestamps()` con `model_id="eleven_multilingual_v2"`
- El response devuelve `alignment.character_start_times_ms` — no se necesita WhisperX
- Output: audio base64 decodificado a `.mp3` + `timings.json` con timestamps por slide/segmento

**Modo de voz `record`:**
- Grabar con `sounddevice.rec()` → guardar con `soundfile.write()` como `.wav`
- Alinear con `whisperx` (modelo base o small para CPU, large-v3 para GPU)
- Generar `timings.json` a partir de los word-level timestamps de WhisperX

**Modo de slides `auto`:**
- Flujo completo: `theme.yaml` → Jinja2 render HTML → `playwright` screenshot PNG
- No se ejecuta el Verificador (Claude con visión)
- Incrustar iconos Lucide con `python-lucide` en el contexto de Jinja2

**Modo de slides `hybrid` / `manual`:**
- Pipeline pausa tras propuesta de diseño en `workdir/design_proposal/`
- El usuario aporta slides; se rasterizan a PNG con `PyMuPDF` o `pdf2image` (si son PDF) o `python-pptx` (si son .pptx)
- Se ejecuta el Verificador: PNG de slides → `anthropic` SDK con visión (base64 PNG) → JSON informe

**Docker (producción):**
- Base: `mcr.microsoft.com/playwright/python:v1.60.0-noble` (Ubuntu 24.04 + Python + browsers)
- Añadir FFmpeg: `apt-get install -y ffmpeg`
- Añadir WhisperX: multistage o instalación directa con torch CPU (`--extra-index-url https://download.pytorch.org/whl/cpu`)
- Añadir Poppler (requerido por pdf2image): `apt-get install -y poppler-utils`
- Copiar binario `uv` para gestión de deps: `COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv`
- Pinear la imagen Docker a la versión exacta de Playwright que use el proyecto

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `playwright>=1.60.0` | Python 3.9-3.13 | Pinear imagen Docker `mcr.microsoft.com/playwright/python:v1.60.0-noble` para que coincida; mismatch de versión = browsers no encontrados |
| `pydantic>=2.13.4` | Python 3.9-3.14 | v2 incompatible con v1: `.json()` → `model_dump_json()`, `.dict()` → `model_dump()` |
| `typer>=0.25.1` | Python >=3.10 | Requiere Python 3.10+ (no 3.9); si se necesita 3.9, usar typer 0.12.x (última versión compatible 3.9) |
| `PyMuPDF>=1.27.2.3` | Python >=3.10 | Requiere Python 3.10+; importar como `import fitz` (nombre interno del módulo) |
| `whisperx>=3.8.5` | Python 3.10-3.13 | Requiere `torch>=2.5.1` y `torchaudio>=2.5.1`; instalar torch ANTES de whisperx; con torch 2.6+ puede fallar la carga de modelos pyannote (weights_only=True); usar `torch==2.5.1` para mayor estabilidad |
| `whisperx>=3.8.5` | `faster-whisper`, `pyannote.audio>=3.3` | Cadena de dependencias: whisperx → pyannote.audio → lightning → pytorch-lightning → torch>=2.1; dejar que uv resuelva el grafo completo |
| `anthropic>=0.104.1` | Python >=3.9 | Visión: imágenes PNG base64 con `type="base64"`, `media_type="image/png"`; tamaño máximo 20MB antes de codificar; dimensión máxima ~1568px (se reduce internamente) |
| `elevenlabs>=2.49.0` | Python 3.8-3.x | `convert_with_timestamps()` devuelve timestamps a nivel de carácter (no palabra); para subtítulos, agrupar caracteres en palabras |
| `pdf2image>=1.17.0` | Sistema: Poppler | Requiere `poppler-utils` en el sistema (Linux: `apt-get install poppler-utils`; macOS: `brew install poppler`); sin Poppler el import falla en runtime |
| `sounddevice>=0.5.5` | Sistema: PortAudio | Requiere `portaudio19-dev` en Linux; en Docker sin acceso a hardware de audio, usar solo para modo desarrollo local |
| `uv` (latest) | `pyproject.toml` PEP 517/518 | `uv.lock` es multiplataforma; `uv sync` reproduce el entorno exacto; compatible con `pip install -e .` |

---

## Sources

- [anthropic · PyPI](https://pypi.org/project/anthropic/) — versión 0.104.1 verificada (mayo 2026)
- [playwright · PyPI](https://pypi.org/project/playwright/) — versión 1.60.0 verificada (mayo 2026)
- [microsoft/playwright-python Docker Hub](https://hub.docker.com/r/microsoft/playwright-python) — imagen `v1.60.0-noble` verificada
- [playwright.dev/python/docs/docker](https://playwright.dev/python/docs/docker) — documentación oficial de Playwright en Docker
- [elevenlabs · PyPI](https://pypi.org/project/elevenlabs/) — versión 2.49.0 verificada (mayo 2026)
- [ElevenLabs convert_with_timestamps API](https://github.com/elevenlabs/elevenlabs-python/blob/main/reference.md) — endpoint verificado con Context7
- [pydantic · PyPI](https://pypi.org/project/pydantic/) — versión 2.13.4 verificada (mayo 2026)
- [typer · PyPI](https://pypi.org/project/typer/) — versión 0.25.1 verificada (abril 2026)
- [rich · PyPI](https://pypi.org/project/rich/) — versión 15.0.0 verificada (abril 2026)
- [Jinja2 · PyPI](https://pypi.org/project/Jinja2/) — versión 3.1.6 verificada (marzo 2025)
- [PyMuPDF · PyPI](https://pypi.org/project/PyMuPDF/) — versión 1.27.2.3 verificada (abril 2026)
- [pdf2image · PyPI](https://pypi.org/project/pdf2image/) — versión 1.17.0 verificada
- [python-pptx · PyPI](https://pypi.org/project/python-pptx/) — versión 1.0.2 verificada
- [PyYAML · PyPI](https://pypi.org/project/PyYAML/) — versión 6.0.3 verificada (sept 2025)
- [sounddevice · PyPI](https://pypi.org/project/sounddevice/) — versión 0.5.5 verificada
- [soundfile · PyPI](https://pypi.org/project/soundfile/) — versión 0.13.1 verificada
- [whisperx · PyPI](https://pypi.org/project/whisperx/) — versión 3.8.5 verificada; Python 3.10-3.13; torch>=2.5.1
- [m-bain/whisperX GitHub issues](https://github.com/m-bain/whisperX/issues/1051) — problemas de compatibilidad torch documentados en issues
- [python-lucide · PyPI](https://pypi.org/project/python-lucide/) — BD SQLite offline con iconos Lucide
- [docs.astral.sh/uv](https://docs.astral.sh/uv/guides/integration/docker/) — integración uv + Docker
- Context7 — anthropic SDK Python: visión, instalación (CONFIANZA: ALTA)
- Context7 — playwright-python: `Page.screenshot()` PNG (CONFIANZA: ALTA)
- Context7 — elevenlabs-python: `convert_with_timestamps`, `stream_with_timestamps` (CONFIANZA: ALTA)
- Context7 — pydantic: `BaseModel`, `model_dump_json()`, `model_validate_json()` v2 (CONFIANZA: ALTA)
- Context7 — typer: `@app.callback()`, subcomandos (CONFIANZA: ALTA)

---

*Stack research for: CLI Python — pipeline de vídeo narrado (slides + voz en off)*
*Researched: 2026-05-25*
