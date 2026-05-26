# Auto Video Narrado

A command-line pipeline that generates a fully narrated slide video from a list of bullet points and a target duration. Given a `bullets.yaml` and an optional context document (`.pptx`, `.pdf`, or `.md`), the system designs the storyboard, generates slides (HTML/CSS rendered to PNG via Playwright), writes a calibrated voice-over script, synthesizes or ingests audio, and assembles the final video with synchronized subtitles — all without manual editing. Visuals use only SVG icons (Lucide) and code-drawn graphics; no AI-generated or stock images.

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

`uv sync` installs all default dependencies (modes `auto` + `elevenlabs`). The `playwright install chromium` step downloads the Chromium browser used to render slides.

### Optional: `record` mode (microphone / local audio — ~2 GB)

The `record` mode uses WhisperX for word-level timestamp alignment. It requires PyTorch, which must be installed **before** WhisperX:

```bash
pip install torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cpu
uv sync --extra record
```

The default installation (above) does **not** include torch or WhisperX. If you only use `elevenlabs` voice mode, you do not need this step.

## Configuration

### API keys

Create a `.env` file in the project root (loaded automatically in development via `python-dotenv`):

```
ANTHROPIC_API_KEY=sk-ant-...
ELEVENLABS_API_KEY=...
```

In Docker, inject these at runtime with `-e` or `--env-file` — never bake secrets into the image.

### `bullets.yaml`

The main input file. Contains a title and a list of bullet points:

```yaml
title: "Ejemplo de presentación"
bullets:
  - "Primer punto clave"
  - "Segundo punto clave"
  - "Tercer punto clave"
```

### `config.yaml`

Optional project-level defaults. CLI flags take precedence over `config.yaml`, which takes precedence over built-in defaults (CLI > YAML > default):

```yaml
voice: elevenlabs        # elevenlabs | record
slides_mode: auto        # auto | hybrid | manual
level: 4                 # 1-4 (1 = pause every stage, 4 = fully autonomous)
wpm: 150                 # words per minute for script calibration
voice_id: "21m00Tcm4TlvDq8ikWAM"  # ElevenLabs voice ID
language: es             # script language
```

### `theme.yaml`

Parametrizes the visual theme applied to slides (color palette, typography, spacing). Edit it to customize the look of generated slides.

## Usage

### `avideo generate` flags

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--bullets PATH` | Yes | — | Path to the `bullets.yaml` input file |
| `--duration INT` | Yes | — | Target video duration in seconds (min 1) |
| `--voice {elevenlabs\|record}` | No | from `config.yaml` | TTS source |
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
| `auto` | The pipeline generates slides from scratch using Jinja2 templates rendered to PNG via Playwright (default) |
| `hybrid` | The pipeline proposes a design; the user provides the final slide files |
| `manual` | The user supplies all slide files; the pipeline handles only voice and assembly |

### Voice modes (`--voice`)

| Mode | Description |
|------|-------------|
| `elevenlabs` | Text-to-speech via ElevenLabs API with character-level timestamps (default) |
| `record` | Ingests a user-recorded `.wav` or captures from microphone; uses WhisperX for word-level alignment |

### Automation levels (`--level`)

| Level | Behavior |
|-------|----------|
| 1 | Pauses after every pipeline stage for review |
| 2 | Pauses at major checkpoints |
| 3 | Pauses only at critical decisions |
| 4 | Fully autonomous — runs end to end without intervention (default) |

## Docker

The Docker image covers modes `auto` + `elevenlabs`. The `record` mode (torch/WhisperX) is not included by default to avoid adding ~2 GB of ML dependencies.

### Build

```bash
docker build -t avideo .
```

### Run

Inject API keys at runtime and mount your working directory and input file:

```bash
docker run --rm \
  -e ANTHROPIC_API_KEY -e ELEVENLABS_API_KEY \
  -v "$PWD/workdir:/app/workdir" \
  -v "$PWD/bullets.yaml:/app/bullets.yaml" \
  avideo generate --bullets bullets.yaml --duration 120
```

To load both keys from a local `.env` file:

```bash
docker run --rm \
  --env-file .env \
  -v "$PWD/workdir:/app/workdir" \
  -v "$PWD/bullets.yaml:/app/bullets.yaml" \
  avideo generate --bullets bullets.yaml --duration 120
```

The `ENTRYPOINT` is `uv run avideo`, so any `avideo` subcommand (e.g. `generate --help`) works directly as the Docker `CMD`.
