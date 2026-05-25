"""Rich UI utilities: Console, validation-error table, logging setup, and approval gates.

Provides the shared Rich Console instance plus helpers for:
- Displaying Pydantic ValidationError as a structured table.
- Configuring Rich logging.
- pause_for_approval: blocking approval gate for the orchestrator (L1/L2/L3 levels).
- make_progress: transient Rich Progress bar for pipeline stage tracking.
"""
from __future__ import annotations

import logging
from typing import Optional

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.table import Table

# Module-level Console writing to stderr so status/error output does not
# pollute piped stdout (e.g. when the caller redirects stdout to a file).
console = Console(stderr=True)


def show_validation_error(
    e: ValidationError,
    console: Optional[Console] = None,
) -> None:
    """Render all Pydantic validation errors as a Rich table.

    Each row shows the field path (joined by " → ") and the error message.
    Uses the module-level console if none is provided. Never lets a raw
    Python traceback reach the user.

    Args:
        e: The ValidationError raised by Pydantic.
        console: Optional Rich Console to print to. Defaults to the
            module-level ``console`` (stderr).
    """
    _console = console or globals()["console"]
    table = Table(
        "Field",
        "Error",
        title="[red bold]Configuration Error[/red bold]",
        border_style="red",
    )
    for err in e.errors():
        loc = " → ".join(str(x) for x in err["loc"])
        table.add_row(loc, err["msg"])
    _console.print(table)


def setup_logging(verbose: bool) -> None:
    """Configure the root logger with a RichHandler.

    When *verbose* is True the level is set to DEBUG and Rich tracebacks
    are enabled. Otherwise the level is INFO and tracebacks are compact.

    Args:
        verbose: Whether to enable debug-level logging and rich tracebacks.
    """
    level = logging.DEBUG if verbose else logging.INFO
    handler = RichHandler(
        markup=True,
        rich_tracebacks=verbose,
        show_path=verbose,
    )
    logging.basicConfig(
        level=level,
        handlers=[handler],
        format="%(message)s",
        force=True,  # override any previously configured root logger
    )


# ---------------------------------------------------------------------------
# Approval gate (added by plan 01-03)
# ---------------------------------------------------------------------------


def pause_for_approval(stage_name: str, reason: str = "") -> None:
    """Prompt the user to approve before continuing to the next stage.

    Displays the stage name and optional reason, then asks for confirmation.
    If the user declines, raises ``typer.Abort`` to halt the pipeline cleanly.

    This function is a module-level symbol so tests can monkeypatch it without
    patching the orchestrator's local namespace.

    Args:
        stage_name: Name of the stage about to run (displayed to the user).
        reason: Optional extra context, e.g. ``"warning detected"`` for L3 gates.

    Raises:
        typer.Abort: If the user declines to continue.
    """
    msg = f"[bold yellow]Checkpoint:[/bold yellow] stage [cyan]{stage_name}[/cyan]"
    if reason:
        msg += f" — {reason}"
    console.print(msg)
    if not Confirm.ask("Continue?", default=True):
        raise typer.Abort()


# ---------------------------------------------------------------------------
# Progress helper (added by plan 01-03)
# ---------------------------------------------------------------------------


def make_progress() -> Progress:
    """Return a transient Rich Progress bar configured for pipeline stage tracking.

    ``transient=True`` ensures the progress bar is cleared after completion,
    keeping the terminal output clean for automated runs and tests without a TTY.

    Returns:
        A configured :class:`rich.progress.Progress` instance.  Intended to be
        used as a context manager wrapping the orchestrator's stage loop.
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    )
