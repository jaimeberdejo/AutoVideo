"""cost_estimator — static per-stage cost/token estimate table for --dry-run.

Phase 1: All numbers are static placeholders based on typical Phase 2–5 usage
patterns.  They are NOT calibrated to a real pipeline run.  Accurate estimation
(reading bullets.yaml, counting slides, measuring actual API calls) will be
implemented in Phase 2 once the LLM stages are real.

Usage::

    from avideo.utils.cost_estimator import estimate_all
    estimate_all(config)   # prints table to console and returns None
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from rich.table import Table

from avideo.utils.rich_ui import console

if TYPE_CHECKING:
    from avideo.models import RunConfig


# ---------------------------------------------------------------------------
# Static placeholder costs per stage
# Phase 1 numbers; Phase 2 will replace with dynamic estimation.
# ---------------------------------------------------------------------------

STAGE_COSTS: dict[str, dict[str, float]] = {
    "context":    {"tokens": 0,      "usd": 0.000},
    "storyboard": {"tokens": 2_000,  "usd": 0.006},
    "timing":     {"tokens": 0,      "usd": 0.000},
    "scriptwriter": {"tokens": 4_000, "usd": 0.012},
    "slides":     {"tokens": 0,      "usd": 0.000},
    "verify":     {"tokens": 3_000,  "usd": 0.009},
    "voice":      {"tokens": 0,      "usd": 0.030},
    "align":      {"tokens": 0,      "usd": 0.000},
    "subs":       {"tokens": 0,      "usd": 0.000},
    "assemble":   {"tokens": 0,      "usd": 0.000},
}


def estimate_all(config: "RunConfig") -> None:
    """Print a Rich table of per-stage token/cost estimates and a total row.

    Reads STAGE_COSTS (Phase-1 static placeholders) and builds a Rich Table
    with one row per pipeline stage plus a TOTAL summary row.  Prints to the
    module-level console (stderr) and returns None.  Runs NO stage and writes
    no checkpoint or done marker.

    Args:
        config: RunConfig — accepted for API consistency with real future
            estimators that may inspect ``config.duration`` or ``config.language``
            to compute dynamic estimates.
    """
    table = Table(
        "Stage",
        "Est. tokens",
        "Est. cost (USD)",
        title="[bold cyan]Dry-Run Cost Estimate[/bold cyan] (Phase-1 placeholders)",
        border_style="cyan",
        show_footer=False,
    )

    total_tokens: float = 0
    total_usd: float = 0.0

    for stage_name, costs in STAGE_COSTS.items():
        tokens = int(costs["tokens"])
        usd = costs["usd"]
        total_tokens += tokens
        total_usd += usd
        table.add_row(
            stage_name,
            f"{tokens:,}" if tokens else "—",
            f"${usd:.4f}" if usd else "—",
        )

    # Add total summary row
    table.add_section()
    table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]{int(total_tokens):,}[/bold]",
        f"[bold]${total_usd:.4f}[/bold]",
    )

    console.print(table)
    console.print(
        "[dim]Note: Phase-1 estimates are static placeholders. "
        "Accurate estimation arrives in Phase 2.[/dim]"
    )
