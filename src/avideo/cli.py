"""Typer CLI for Auto Video Narrado.

Entry point: `avideo generate` parses all pipeline flags into a validated
RunConfig and hands control to the orchestrator. Config priority follows
RunConfig's settings_customise_sources: CLI flag > config.yaml > default.

Usage:
    avideo generate --bullets bullets.yaml --duration 120 [options]
"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer
from dotenv import load_dotenv
from pydantic import ValidationError

# Source .env from the current working directory into os.environ before any
# integration module is imported, so the Anthropic/ElevenLabs SDKs (which read
# ANTHROPIC_API_KEY / ELEVENLABS_API_KEY from os.environ at client-construction
# time) see the keys. Existing env vars take precedence (override=False), so
# CI/Docker setups that set vars explicitly are unaffected. Silent no-op if no
# .env exists — matches the README's "optional .env" model.
load_dotenv(override=False)

from avideo.models.config import RunConfig, SlidesMode, VoiceMode  # noqa: E402
from avideo.utils.rich_ui import setup_logging, show_validation_error  # noqa: E402

app = typer.Typer(
    rich_markup_mode="rich",
    help="Auto Video Narrado — generate narrated slide videos from bullet points.",
)


@app.callback()
def _main() -> None:
    """Auto Video Narrado CLI.

    Use a subcommand to get started (e.g. ``avideo generate --help``).
    """


@app.command()
def generate(
    bullets: Annotated[
        Path,
        typer.Option(
            "--bullets",
            exists=True,
            file_okay=True,
            dir_okay=False,
            help="Path to the bullets.yaml input file.",
        ),
    ],
    duration: Annotated[
        int,
        typer.Option(
            "--duration",
            min=1,
            help="Target video duration in seconds.",
        ),
    ],
    voice: Annotated[
        Optional[VoiceMode],
        typer.Option("--voice", help="TTS source: elevenlabs or record."),
    ] = None,
    slides_mode: Annotated[
        Optional[SlidesMode],
        typer.Option("--slides-mode", help="Slide generation mode: auto, hybrid, or manual."),
    ] = None,
    level: Annotated[
        Optional[int],
        typer.Option(
            "--level",
            min=1,
            max=4,
            help="Automation level 1 (pause every stage) to 4 (fully autonomous).",
        ),
    ] = None,
    context: Annotated[
        Optional[Path],
        typer.Option(
            "--context",
            exists=True,
            file_okay=True,
            dir_okay=False,
            help="Optional context document (.pptx/.pdf/.md).",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show cost estimate without generating any output."),
    ] = False,
    burn_subs: Annotated[
        bool,
        typer.Option("--burn-subs", help="Burn subtitles into the video output."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", help="Enable debug logging with Rich tracebacks."),
    ] = False,
) -> None:
    """Generate a narrated video from bullet points.

    Reads *bullets* (required) and *duration* (required), merges optional flags
    with config.yaml and Pydantic defaults (CLI > YAML > default), validates the
    full RunConfig, then delegates to the orchestrator.
    """
    # 1. Configure logging before anything else so all subsequent output is styled.
    setup_logging(verbose)

    # 2. Build kwargs — include ONLY optional flags that were explicitly set so that
    #    unset values fall through to config.yaml / Pydantic defaults, preserving the
    #    CLI > YAML > default precedence defined in RunConfig.settings_customise_sources.
    kwargs: dict = {
        "bullets": bullets,
        "duration": duration,
        # Boolean flags always have an explicit user-visible default (False) that matches
        # the model default, so including them unconditionally is safe and correct.
        "dry_run": dry_run,
        "burn_subs": burn_subs,
        "verbose": verbose,
    }
    if voice is not None:
        kwargs["voice"] = voice
    if slides_mode is not None:
        kwargs["slides_mode"] = slides_mode
    if level is not None:
        kwargs["level"] = level
    if context is not None:
        kwargs["context"] = context

    # 3. Validate — RunConfig is BaseSettings and merges YAML + env automatically.
    try:
        config = RunConfig(**kwargs)
    except ValidationError as e:
        show_validation_error(e)
        raise typer.Exit(1)

    # 4. Hand off to orchestrator. Lazy import so tests can stub avideo.orchestrator
    #    via sys.modules before importing this module. Plan 01-03 provides the real
    #    run_pipeline implementation.
    import avideo.orchestrator as _orch  # noqa: PLC0415

    _orch.run_pipeline(config)


@app.command()
def studio(
    port: Annotated[
        int,
        typer.Option("--port", min=1, max=65535, help="Port for the Streamlit server."),
    ] = 8501,
    workdir: Annotated[
        Optional[Path],
        typer.Option(
            "--workdir",
            help="Path to an existing workdir to resume. Passed to the UI via AVIDEO_STUDIO_WORKDIR env var.",
        ),
    ] = None,
) -> None:
    """Launch the Studio Guiado — a guided 6-phase wizard UI in the browser."""
    import subprocess  # noqa: PLC0415
    import sys  # noqa: PLC0415
    from pathlib import Path as _Path  # noqa: PLC0415

    ui_app = _Path(__file__).parent / "ui" / "app.py"
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(ui_app),
        "--server.port",
        str(port),
        "--server.address",
        "127.0.0.1",
        "--server.headless",
        "false",
    ]
    env = None
    if workdir is not None:
        import os  # noqa: PLC0415

        env = {**os.environ, "AVIDEO_STUDIO_WORKDIR": str(workdir)}
    subprocess.run(cmd, env=env, check=False)
