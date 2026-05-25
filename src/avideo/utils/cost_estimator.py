"""cost_estimator — offline heuristic token/cost estimate for --dry-run.

Phase 2 upgrade (D-15): Estimates are now derived from real inputs — bullet count
(read from bullets.yaml) and duration — replacing the static Phase-1 placeholders.

Design:
- NEVER calls count_tokens (API / network) — offline dry-run contract preserved.
- Reads bullets.yaml via load_bullets() for the real bullet count (file I/O is
  acceptable; still no network and runs before any workdir exists).
- Falls back gracefully (bullet count = 0 + Rich warning) if bullets.yaml is missing.
- Pricing constants for Claude claude-sonnet-4-6: $3/MTok input, $15/MTok output (D-15).

Heuristics (documented for SUMMARY):
  Storyboard:
    est_slides ≈ clamp(round(duration / 25), 3, 20)
    in_tok ≈ 400 + num_bullets * 30  (system prompt + user bullets)
    out_tok ≈ est_slides * 120       (avg slide title+bullets in JSON)
  Scriptwriter:
    est_words ≈ duration * WPM_DEFAULT / 60  (total word budget)
    in_tok ≈ 600 + est_slides * 80 + num_bullets * 20  (prompt with all slide specs)
    out_tok ≈ max(1, est_words)              (narration tokens ≈ words)

Usage::

    from avideo.utils.cost_estimator import estimate_all
    estimate_all(config)   # prints Rich table to console; returns None
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from rich.table import Table

from avideo.utils.rich_ui import console

if TYPE_CHECKING:
    from avideo.models import RunConfig


# ---------------------------------------------------------------------------
# Pricing constants — Claude claude-sonnet-4-6 (verified 2026-05-25)
# ---------------------------------------------------------------------------

INPUT_USD_PER_MTOK: float = 3.0   # $3.00 per million input tokens
OUTPUT_USD_PER_MTOK: float = 15.0  # $15.00 per million output tokens


# ---------------------------------------------------------------------------
# Default WPM for cost estimation (same as RunConfig default)
# ---------------------------------------------------------------------------

_WPM_DEFAULT: int = 150


# ---------------------------------------------------------------------------
# Heuristic helpers
# ---------------------------------------------------------------------------


def _est_slides(duration: int) -> int:
    """Estimate number of slides from target duration.

    Args:
        duration: Target video duration in seconds.

    Returns:
        Estimated slide count in range [3, 20].
    """
    raw = round(duration / 25)
    return max(3, min(20, raw))


def estimate_storyboard_tokens(num_bullets: int, duration: int) -> tuple[int, int]:
    """Estimate input and output tokens for the storyboard LLM call.

    Heuristic:
        est_slides = clamp(round(duration / 25), 3, 20)
        in_tok = 400 + num_bullets * 30
        out_tok = est_slides * 120

    Args:
        num_bullets: Number of bullet points in bullets.yaml.
        duration: Target video duration in seconds.

    Returns:
        (in_tok, out_tok) — estimated integer token counts.
    """
    slides = _est_slides(duration)
    in_tok = 400 + num_bullets * 30
    out_tok = slides * 120
    return int(in_tok), int(out_tok)


def estimate_theme_tokens(num_bullets: int, duration: int) -> tuple[int, int]:
    """Estimate input and output tokens for the theme-generation LLM call.

    The theme prompt summarises the storyboard slide titles (one line per slide).
    Heuristic:
        est_slides = clamp(round(duration / 25), 3, 20)
        in_tok ≈ 300 + est_slides * 40  (system prompt + slide summary)
        out_tok ≈ 250                    (compact ThemeConfig JSON)

    T-03-06: Pure arithmetic — no network, no API key, preserves the offline
    dry-run contract (mirrors estimate_storyboard_tokens and estimate_script_tokens).

    Args:
        num_bullets: Number of bullet points (used only for consistency with other
            estimators; theme prompt does not include bullets).
        duration: Target video duration in seconds.

    Returns:
        (in_tok, out_tok) — estimated integer token counts.
    """
    slides = _est_slides(duration)
    in_tok = 300 + slides * 40
    out_tok = 250  # compact ThemeConfig JSON is ~200-300 tokens
    return int(in_tok), int(out_tok)


def estimate_script_tokens(num_bullets: int, duration: int) -> tuple[int, int]:
    """Estimate input and output tokens for the scriptwriter LLM call.

    Heuristic:
        est_words = duration * WPM_DEFAULT / 60
        est_slides = clamp(round(duration / 25), 3, 20)
        in_tok = 600 + est_slides * 80 + num_bullets * 20
        out_tok = max(1, round(est_words))   (narration tokens ≈ words)

    Args:
        num_bullets: Number of bullet points in bullets.yaml.
        duration: Target video duration in seconds.

    Returns:
        (in_tok, out_tok) — estimated integer token counts.
    """
    slides = _est_slides(duration)
    est_words = duration * _WPM_DEFAULT / 60
    in_tok = 600 + slides * 80 + num_bullets * 20
    out_tok = max(1, round(est_words))
    return int(in_tok), int(out_tok)


def _tok_to_usd(in_tok: int, out_tok: int) -> float:
    """Convert token counts to USD using Sonnet 4.6 pricing.

    Args:
        in_tok: Estimated input tokens.
        out_tok: Estimated output tokens.

    Returns:
        Estimated cost in USD.
    """
    return (in_tok * INPUT_USD_PER_MTOK + out_tok * OUTPUT_USD_PER_MTOK) / 1_000_000


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def estimate_all(config: "RunConfig") -> None:
    """Print a Rich table of per-stage token/cost estimates and return None.

    Reads bullet count from config.bullets (offline file read — no network).
    Falls back to num_bullets=0 with a warning if the file is missing or invalid.
    Runs NO stage and writes no checkpoint or done marker.

    Stages with no LLM cost (context, timing, slides, voice, align, subs, assemble)
    are shown with dashes (—) to avoid cluttering the table.

    Args:
        config: RunConfig with bullets, duration, and wpm fields.
    """
    # Read real bullet count (offline — load_bullets does no network I/O)
    num_bullets: int = 0
    try:
        from avideo.utils.bullets import load_bullets  # local import avoids circular

        bullets_input = load_bullets(config.bullets)
        num_bullets = len(bullets_input.bullets)
    except Exception:
        # Graceful fallback: file missing, bad YAML, etc.
        console.print(
            f"[dim yellow]Warning: could not read bullets from "
            f"{config.bullets!s} — using 0 bullets for estimate.[/dim yellow]"
        )

    duration = config.duration

    # Compute per-stage estimates
    sb_in, sb_out = estimate_storyboard_tokens(num_bullets, duration)
    sc_in, sc_out = estimate_script_tokens(num_bullets, duration)
    th_in, th_out = estimate_theme_tokens(num_bullets, duration)

    sb_usd = _tok_to_usd(sb_in, sb_out)
    sc_usd = _tok_to_usd(sc_in, sc_out)
    th_usd = _tok_to_usd(th_in, th_out)

    total_in = sb_in + sc_in + th_in
    total_out = sb_out + sc_out + th_out
    total_usd = sb_usd + sc_usd + th_usd

    # Build Rich table
    table = Table(
        "Stage",
        "Est. in-tokens",
        "Est. out-tokens",
        "Est. cost (USD)",
        title=(
            f"[bold cyan]Dry-Run Cost Estimate[/bold cyan] "
            f"({num_bullets} bullets · {duration}s · claude-sonnet-4-6)"
        ),
        border_style="cyan",
        show_footer=False,
    )

    # Rows: only LLM stages have non-zero costs
    # slides: theme generation call (one-time, idempotent after theme.yaml is written)
    _llm_stages = [
        ("context",    None, None),
        ("storyboard", sb_in, sb_out),
        ("timing",     None, None),
        ("scriptwriter", sc_in, sc_out),
        ("slides",     th_in, th_out),  # Phase 3: theme-generation LLM call (idempotent)
        ("verify",     None, None),   # Phase 6 — placeholder
        ("voice",      None, None),   # Phase 4 — ElevenLabs (not LLM)
        ("align",      None, None),
        ("subs",       None, None),
        ("assemble",   None, None),
    ]

    for stage_name, in_t, out_t in _llm_stages:
        if in_t is not None and out_t is not None:
            usd = _tok_to_usd(in_t, out_t)
            table.add_row(
                stage_name,
                f"{in_t:,}",
                f"{out_t:,}",
                f"${usd:.4f}",
            )
        else:
            table.add_row(stage_name, "—", "—", "—")

    # Total row
    table.add_section()
    table.add_row(
        "[bold]TOTAL (LLM)[/bold]",
        f"[bold]{total_in:,}[/bold]",
        f"[bold]{total_out:,}[/bold]",
        f"[bold]${total_usd:.4f}[/bold]",
    )

    console.print(table)
    console.print(
        f"[dim]Heuristic estimate — $3/MTok in + $15/MTok out (claude-sonnet-4-6). "
        f"Actual costs depend on prompt length and Claude's output verbosity.[/dim]"
    )
