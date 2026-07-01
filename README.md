# Auto Video Narrado

A tool that generates a fully narrated slide video from a list of bullet points and a target duration. Given a topic or `bullets.yaml`, it designs the storyboard, generates slides (HTML/CSS rendered to PNG via Playwright), writes a calibrated voice-over script, synthesizes or ingests audio, and assembles the final video with synchronized subtitles — with no manual editing required. Visuals use only SVG icons (Lucide) and code-drawn graphics; no AI-generated or stock images.

Two ways to use it:

- **`avideo studio`** — a guided Streamlit wizard that walks through the 6 stages (content → script/slides → voice → extras → assembly) with a human approval gate at each step, live previews, and the ability to request variations before moving on.
- **`avideo generate`** — the same pipeline as a single headless CLI command, for scripting and automation.

## Installation

### System dependencies

**macOS:**
```bash
brew install ffmpeg poppler
```

**Debian/Ubuntu:**
```bash
sudo apt-get install -y ffmpeg poppler-utils
```

FFmpeg is required for video assembly. Poppler (`poppler-utils`) is required for PDF ingestion via `pdf2image`.

### Project installation

```bash
uv sync
uv run playwright install chromium
```

`uv sync` installs all default dependencies (slides mode `auto` + voice modes `elevenlabs`/`openai`). The `playwright install chromium` step downloads the Chromium browser used to render slides.

### Optional: `record` mode (microphone / local audio — ~2 GB)

The `record` voice mode uses WhisperX for word-level timestamp alignment. It requires PyTorch, which must be installed **before** WhisperX:

```bash
pip install torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cpu
uv sync --extra record
```

The default installation (above) does **not** include torch or WhisperX. You only need this if you plan to use `record` voice mode (own recordings or microphone capture) instead of `elevenlabs`/`openai`.

## Configuration

### API keys

Create a `.env` file in the project root (loaded automatically via `python-dotenv`):

```
ANTHROPIC_API_KEY=sk-ant-...
ELEVENLABS_API_KEY=...
OPENAI_API_KEY=sk-...
```

`ANTHROPIC_API_KEY` is required for storyboard, script, and slide verification. `ELEVENLABS_API_KEY` and `OPENAI_API_KEY` are only needed for the corresponding voice mode — skip either if you use `record` mode or the other provider. In Docker, inject these at runtime with `-e` or `--env-file` — never bake secrets into the image.

### `bullets.yaml`

The main input file for headless (`avideo generate`) runs. Contains a title and a list of bullet points:

```yaml
title: "Ejemplo de presentación"
bullets:
  - "Primer punto clave"
  - "Segundo punto clave"
  - "Tercer punto clave"
```

In `avideo studio`, you write these directly in the Fase 1 editor (or have Claude generate them from a topic) instead of hand-editing this file.

### `config.yaml`

Optional project-level defaults for `avideo generate`. CLI flags take precedence over `config.yaml`, which takes precedence over built-in defaults (CLI > YAML > default):

```yaml
voice: elevenlabs        # elevenlabs | openai | record
slides_mode: auto        # auto | hybrid | manual
level: 4                 # 1-4 (1 = pause every stage, 4 = fully autonomous)
wpm: 150                 # words per minute for script calibration
voice_id: "21m00Tcm4TlvDq8ikWAM"  # ElevenLabs voice ID
language: es             # script language
```

### `theme.yaml`

Parametrizes the visual theme applied to slides (color palette, typography, spacing). Edit it to customize the look of generated slides.

## Usage

### Studio (guided wizard)

```bash
uv run avideo studio
```

Opens `http://localhost:8501` with a 6-phase wizard. Each phase requires explicit approval before advancing; going back invalidates and re-runs downstream stages. State is reconstructed from the workdir on every page load, so closing and reopening the browser (or restarting the process) resumes exactly where you left off.

```bash
uv run avideo studio --port 8080 --workdir ./my-project/workdir
```

### `avideo generate` (headless CLI)

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--bullets PATH` | Yes | — | Path to the `bullets.yaml` input file |
| `--duration INT` | Yes | — | Target video duration in seconds (min 1) |
| `--voice {elevenlabs\|openai\|record}` | No | from `config.yaml` | TTS source |
| `--slides-mode {auto\|hybrid\|manual}` | No | from `config.yaml` | Slide generation mode |
| `--level INT` | No | from `config.yaml` | Automation level 1–4 |
| `--context PATH` | No | — | Optional context document (`.pptx`/`.pdf`/`.md`) |
| `--dry-run` | No | false | Show cost/token estimate without generating any output |
| `--burn-subs` | No | false | Burn subtitles into the video output |
| `--verbose` | No | false | Enable debug logging with Rich tracebacks |

### Examples

```bash
# Basic 2-minute video in auto mode, fully autonomous
uv run avideo generate --bullets bullets.yaml --duration 120

# With context document and burned subtitles, pausing at every stage
uv run avideo generate --bullets bullets.yaml --duration 180 --context notas.pdf --burn-subs --level 1

# Estimate cost/tokens without generating anything
uv run avideo generate --bullets bullets.yaml --duration 120 --dry-run
```

## Modes & Levels

### Slide generation modes (`--slides-mode`)

| Mode | Description |
|------|-------------|
| `auto` | The pipeline generates slides from scratch using Jinja2 templates rendered to PNG via Playwright (default). Claude Vision verifies each slide (ok/warning/fail). |
| `hybrid` | The pipeline proposes a design; the user provides the final slide files |
| `manual` | The user supplies all slide files; the pipeline handles only voice and assembly |

### Voice modes (`--voice`)

| Mode | Description |
|------|-------------|
| `elevenlabs` | Text-to-speech via ElevenLabs API with character-level timestamps (default) |
| `openai` | Text-to-speech via OpenAI Audio (`tts-1`/`tts-1-hd`), with a `whisper-1` speech-to-text round-trip to produce word-level timestamps |
| `record` | Ingests user-recorded audio (own `.wav` files, or microphone capture); uses WhisperX for word-level alignment. In Studio, uploaded audio can optionally be denoised/normalized before use. |

### Extras (Studio Fase 5 / assembly)

Subtitles (burned-in or soft `.srt`/`.vtt`), background music with ducking and fades, and configurable crossfade between slides. The final assembly runs two-pass EBU R128 loudnorm and produces a QA report (target vs. actual duration, measured/normalized loudness).

### Automation levels (`--level`)

| Level | Behavior |
|-------|----------|
| 1 | Pauses after every pipeline stage for review |
| 2 | Pauses at major checkpoints |
| 3 | Pauses only at critical decisions |
| 4 | Fully autonomous — runs end to end without intervention (default) |

## Docker

The Docker image covers slides mode `auto` + voice modes `elevenlabs`/`openai`. The `record` mode (torch/WhisperX) is not included by default to avoid adding ~2 GB of ML dependencies. Port 8501 is exposed for `avideo studio`.

### Build

```bash
docker build -t avideo .
```

### Run — headless CLI

Inject API keys at runtime and mount your working directory and input file:

```bash
docker run --rm \
  -e ANTHROPIC_API_KEY -e ELEVENLABS_API_KEY -e OPENAI_API_KEY \
  -v "$PWD/workdir:/app/workdir" \
  -v "$PWD/bullets.yaml:/app/bullets.yaml" \
  avideo generate --bullets bullets.yaml --duration 120
```

To load keys from a local `.env` file instead:

```bash
docker run --rm \
  --env-file .env \
  -v "$PWD/workdir:/app/workdir" \
  -v "$PWD/bullets.yaml:/app/bullets.yaml" \
  avideo generate --bullets bullets.yaml --duration 120
```

### Run — Studio UI

```bash
docker run --rm -p 8501:8501 \
  --env-file .env \
  -v "$PWD/workdir:/app/workdir" \
  avideo studio --port 8501
```

The `ENTRYPOINT` is `uv run avideo`, so any `avideo` subcommand (e.g. `generate --help`, `studio`) works directly as the Docker `CMD`.

## Tests

```bash
uv run pytest -q
```

446+ unit tests, all external calls (Anthropic, ElevenLabs, OpenAI, ffmpeg, subprocess) mocked. A separate opt-in suite drives a real headless browser against a real `avideo studio` process:

```bash
uv run playwright install chromium   # once
AVIDEO_E2E=1 uv run pytest tests/test_ui_wizard_e2e.py -v
```
