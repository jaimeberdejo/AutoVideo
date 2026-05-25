"""Rich UI utilities: Console, validation-error table, and logging setup.

Provides the shared Rich Console instance plus helpers for displaying
Pydantic ValidationError as a structured table and configuring Rich
logging. Additional helpers (pause_for_approval, progress) are added by
plan 01-03 in this same file.
"""
from __future__ import annotations

import logging
from typing import Optional

from pydantic import ValidationError
from rich.console import Console
from rich.logging import RichHandler
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
