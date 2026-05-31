"""bullets_gen — generate a bullet list from a topic via Claude.

Used by Phase 10 (Contenido page) to offer auto-generation of bullets.
The storyboard stage (Phase 2) consumes the resulting bullets.yaml.

Mock seam: ``avideo.stages.bullets_gen.call_structured`` — patch this in tests
to avoid real Anthropic API calls (same pattern as storyboard.py).
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from avideo.integrations.anthropic import call_structured  # module-level = mock seam

# ---------------------------------------------------------------------------
# Duration validation constants
# ---------------------------------------------------------------------------

DURATION_MIN: int = 15    # seconds
DURATION_MAX: int = 1800  # 30 minutes


# ---------------------------------------------------------------------------
# Pydantic output model for Claude response
# ---------------------------------------------------------------------------

class BulletsListOutput(BaseModel):
    """Claude's structured output: an ordered list of bullet strings."""
    bullets: list[str] = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------

def validate_duration(seconds: int) -> int:
    """Validate that seconds is within acceptable bounds.

    Args:
        seconds: Target video duration in seconds.

    Returns:
        seconds unchanged if valid.

    Raises:
        ValueError: If seconds < DURATION_MIN or > DURATION_MAX.
    """
    if seconds < DURATION_MIN or seconds > DURATION_MAX:
        raise ValueError(
            f"Duration must be between {DURATION_MIN} and {DURATION_MAX} seconds, "
            f"got {seconds}."
        )
    return seconds


def parse_duration(text: str) -> int:
    """Parse a human duration into total seconds.

    Accepts either a bare integer number of seconds (``"330"``) or a
    colon-separated ``mm:ss`` / ``h:mm:ss`` form (``"5:30"`` -> 330). Does NOT
    enforce the [DURATION_MIN, DURATION_MAX] bounds — call ``validate_duration``
    on the result for that.

    Args:
        text: User-entered duration string.

    Returns:
        Total duration in seconds.

    Raises:
        ValueError: If the string is empty or not a valid seconds / mm:ss value.
    """
    s = (text or "").strip()
    if not s:
        raise ValueError("Duración vacía. Usa mm:ss (p. ej. 5:30) o segundos.")

    if ":" in s:
        parts = [p.strip() for p in s.split(":")]
        if len(parts) > 3 or not all(p.isdigit() for p in parts):
            raise ValueError(
                f"Formato de duración inválido: '{text}'. Usa mm:ss (p. ej. 5:30) "
                f"o un número de segundos."
            )
        nums = [int(p) for p in parts]
        while len(nums) < 3:  # left-pad to [h, m, s]
            nums.insert(0, 0)
        hours, minutes, secs = nums
        if minutes > 59 or secs > 59:
            raise ValueError(
                f"Minutos y segundos deben ser menores que 60: '{text}'."
            )
        return hours * 3600 + minutes * 60 + secs

    if not s.isdigit():
        raise ValueError(
            f"Formato de duración inválido: '{text}'. Usa mm:ss (p. ej. 5:30) "
            f"o un número de segundos."
        )
    return int(s)


def format_duration(seconds: int) -> str:
    """Format seconds as ``m:ss`` (or ``h:mm:ss`` when >= 1 hour)."""
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


# ---------------------------------------------------------------------------
# System / user prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert presentation writer specialised in clear, engaging narrated video presentations.
Your task: given a topic and a target video duration, write an ordered list of concise bullet points
that together cover the topic well within the time available.

Guidelines:
- Each bullet is one short sentence or phrase (max ~12 words); no sub-bullets.
- Bullets must form a coherent, logical narrative arc when read in order.
- Do NOT include introduction or conclusion meta-bullets like "Today we will cover...".
- Language: match the language of the topic provided by the user.
"""

_USER_TEMPLATE = """\
Topic: {topic}
Target duration: {duration_seconds} seconds
Required number of bullets: {n}

Write exactly {n} bullet points covering the topic.
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _default_n(duration_seconds: int) -> int:
    """Derive a sensible bullet count from duration (1 bullet per 30 s, clamp 2-20)."""
    return max(2, min(20, duration_seconds // 30))


def generate_bullets(
    topic: str,
    duration_seconds: int,
    n: int | None = None,
) -> list[str]:
    """Generate a list of bullet points for *topic* using Claude.

    Args:
        topic: Short description of the presentation topic.
        duration_seconds: Target video duration in seconds (used to derive n if not given).
        n: Number of bullets to generate. Defaults to max(2, min(20, duration_seconds // 30)).

    Returns:
        List of *n* non-empty bullet strings.

    Raises:
        RuntimeError: Propagated from call_structured on API failure.
    """
    effective_n = n if n is not None else _default_n(duration_seconds)
    result: BulletsListOutput = call_structured(
        system=_SYSTEM_PROMPT,
        user=_USER_TEMPLATE.format(
            topic=topic,
            duration_seconds=duration_seconds,
            n=effective_n,
        ),
        tool_name="emit_bullets",
        tool_description=(
            f"Emit exactly {effective_n} ordered bullet points covering the given topic."
        ),
        output_model=BulletsListOutput,
        max_tokens=2048,
    )
    return result.bullets
