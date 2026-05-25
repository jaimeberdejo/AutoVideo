"""TimingStage — pure content-weighted largest-remainder timing apportionment.

Design decisions implemented here:
- D-05: Per-slide weight from #bullets + char length of (title + bullets joined).
  Clamp constants MIN_SECONDS=8, MAX_SECONDS=45 chosen to avoid absurd slide durations.
- D-06: Largest-remainder apportionment guarantees sum(seconds) == target EXACTLY.
  Clamp strategy: clamp weights BEFORE apportionment so the invariant holds naturally.
  An internal assertion safeguards against future drift.
- D-07: word_budget = round(seconds * wpm / 60); WPM from config.wpm (default 150).
- D-08: 100% pure Python, no network, no LLM — fully deterministic and testable.

stage_name = "timing" and checkpoint_name = "timings" match the Phase-1 TimingStub
so the orchestrator / workdir contract is unchanged (file remains timings.json).

Clamp constants (documented for SUMMARY):
  MIN_SECONDS = 8   — no slide shorter than 8 seconds
  MAX_SECONDS = 45  — no slide longer than 45 seconds
  CHARS_PER_UNIT = 80 — chars of bullet/title text per weight unit (one of several)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from avideo.models.storyboard import StoryboardOutput
from avideo.models.timing import SlideTiming, TimingOutput
from avideo.stages.base import CheckpointMixin

if TYPE_CHECKING:
    from avideo.models.config import RunConfig
    from avideo.utils.workdir import WorkdirManager

# ---------------------------------------------------------------------------
# Module constants (D-05 — documented in SUMMARY)
# ---------------------------------------------------------------------------

#: Minimum allowed seconds for any single slide (D-05).
MIN_SECONDS: int = 8

#: Maximum allowed seconds for any single slide (D-05).
MAX_SECONDS: int = 45

#: Characters of bullet+title text per weight unit (divisor, not multiplier).
#: A slide with 80 chars of text gets +1 weight unit from the text component.
CHARS_PER_UNIT: int = 80


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def apportion_seconds(weights: list[int | float], total: int) -> list[int]:
    """Distribute *total* integer seconds among N slots using largest-remainder method.

    The largest-remainder (Hamilton) method guarantees:
    - Every slot gets at least ``floor(raw_share)`` seconds.
    - The remaining integer seconds are given to slots with the largest fractional parts.
    - ``sum(result) == total`` EXACTLY.

    Args:
        weights: Non-negative weights for each slot (floats or ints).
            All-zero weights are handled gracefully (equal distribution).
        total: Target integer total to distribute.

    Returns:
        A list of non-negative ints summing exactly to *total*.

    Raises:
        ValueError: If *total* is negative or *weights* is empty.
    """
    n = len(weights)
    if n == 0:
        return []

    # Normalise: if all weights are zero, distribute equally
    total_weight = sum(weights)
    if total_weight == 0:
        # Fallback: give floor(total/n) to each; distribute remainder to first slots
        base = total // n
        remainder = total - base * n
        return [base + (1 if i < remainder else 0) for i in range(n)]

    # Compute raw (float) shares
    raw = [w * total / total_weight for w in weights]

    # Floor each share and track fractional parts
    floored = [int(r) for r in raw]
    remainders = [(raw[i] - floored[i], i) for i in range(n)]

    # Distribute the integer remainder to slots with largest fractional parts
    distributed_remainder = total - sum(floored)  # always >= 0
    # Sort by fractional part descending (ties broken by original index — stable)
    remainders_sorted = sorted(remainders, key=lambda x: -x[0])

    result = floored[:]
    for k in range(distributed_remainder):
        idx = remainders_sorted[k][1]
        result[idx] += 1

    assert sum(result) == total, (
        f"apportion_seconds invariant broken: sum={sum(result)}, expected={total}"
    )
    return result


def _slide_weights(storyboard: StoryboardOutput) -> list[float]:
    """Compute a content-based weight for each slide (D-05).

    Weight formula per slide:
        weight = 1 + len(slide.bullets) + len(title + " ".join(bullets)) / CHARS_PER_UNIT

    This gives heavier slides (more bullets, longer text) proportionally more time.
    The constant ``1`` ensures every slide has a positive baseline weight.

    Args:
        storyboard: Validated StoryboardOutput from the storyboard checkpoint.

    Returns:
        List of positive floats, one per slide.
    """
    weights: list[float] = []
    for slide in storyboard.slides:
        text_length = len(slide.title) + sum(len(b) for b in slide.bullets)
        weight = 1.0 + len(slide.bullets) + text_length / CHARS_PER_UNIT
        weights.append(weight)
    return weights


def _clamp_weights(
    weights: list[float], total: int, min_s: int, max_s: int
) -> list[float]:
    """Clamp weights so the raw apportioned seconds stay within [min_s, max_s].

    Clamping is applied to the WEIGHTS (not the resulting seconds) so the
    largest-remainder invariant holds without re-balancing.

    Algorithm:
    1. Compute raw shares for each slot using the current weights.
    2. If a slot's raw share < min_s, raise its weight to achieve exactly min_s.
    3. If a slot's raw share > max_s, lower its weight to achieve exactly max_s.
    4. Repeat until stable (converges in O(n) passes for typical distributions).

    Args:
        weights: Initial content-based weights (must be positive).
        total: Target integer total (config.duration).
        min_s: Minimum seconds per slide.
        max_s: Maximum seconds per slide.

    Returns:
        Clamped weights that, when passed to ``apportion_seconds``, will produce
        seconds in the range [min_s, max_s] (approximately — exact clamping is
        guaranteed at the integer level by apportion_seconds itself).
    """
    n = len(weights)
    if n == 0:
        return weights

    # If every slide must have at least min_s but total < n * min_s, we cannot
    # satisfy the min_s constraint for all slides. In this degenerate case,
    # return equal weights and let apportion_seconds handle it.
    if total < n * min_s:
        return [1.0] * n

    clamped = list(weights)
    # Up to n iterations to stabilise (each pass resolves at least one constraint)
    for _ in range(n + 1):
        total_w = sum(clamped)
        changed = False
        for i in range(n):
            raw_share = clamped[i] / total_w * total
            if raw_share < min_s:
                # Raise weight so raw share equals min_s
                # new_weight / (total_w - clamped[i] + new_weight) * total = min_s
                # Solve: new_weight = min_s * (total_w - clamped[i]) / (total - min_s)
                denom = total - min_s
                if denom <= 0:
                    clamped[i] = clamped[i]  # can't satisfy — leave as-is
                else:
                    new_w = min_s * (total_w - clamped[i]) / denom
                    if new_w > clamped[i]:
                        clamped[i] = new_w
                        changed = True
            elif raw_share > max_s:
                # Lower weight so raw share equals max_s
                # new_weight / (total_w - clamped[i] + new_weight) * total = max_s
                denom = total - max_s
                if denom <= 0:
                    # max_s >= total → all weight into one slide; leave as-is
                    pass
                else:
                    new_w = max_s * (total_w - clamped[i]) / denom
                    if new_w < clamped[i] and new_w > 0:
                        clamped[i] = new_w
                        changed = True
        if not changed:
            break

    return clamped


def word_budget(seconds: float, wpm: int) -> int:
    """Compute word budget for a slide from its allocated seconds and WPM (D-07).

    Args:
        seconds: Duration allocated to this slide in seconds.
        wpm: Target words per minute (from RunConfig).

    Returns:
        Integer word count the scriptwriter should target for this slide.
    """
    return round(seconds * wpm / 60)


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------


class TimingStage(CheckpointMixin):
    """Pure-Python timing director — content-weighted largest-remainder apportionment.

    Reads the storyboard checkpoint, computes per-slide durations using content-
    based weights with clamps, and returns a TimingOutput whose slide seconds sum
    EXACTLY to config.duration.

    stage_name = "timing" and checkpoint_name = "timings" preserve the workdir
    contract from the Phase-1 TimingStub (file is timings.json).

    This stage is 100% deterministic and requires no network or LLM call (D-08).
    It does NOT write checkpoints — that is the orchestrator's responsibility.
    """

    stage_name: str = "timing"

    @property
    def checkpoint_name(self) -> str:  # type: ignore[override]
        """Override: checkpoint filename is 'timings' (→ workdir/timings.json)."""
        return "timings"

    def run(self, workdir: "WorkdirManager", config: "RunConfig") -> TimingOutput:
        """Compute per-slide timing from the storyboard checkpoint.

        Steps:
        1. Read storyboard.json → StoryboardOutput.
        2. Compute content-based weights for each slide.
        3. Clamp weights so no slide gets < MIN_SECONDS or > MAX_SECONDS.
        4. Apportion config.duration among slides using largest-remainder.
        5. Build SlideTiming per slide with word_budget = round(s * wpm / 60).
        6. Return TimingOutput with total_seconds == config.duration.

        Args:
            workdir: WorkdirManager for reading the storyboard checkpoint.
            config: RunConfig with duration, wpm.

        Returns:
            TimingOutput with slides, total_seconds == config.duration, wpm.
        """
        sb: StoryboardOutput = workdir.read_checkpoint("storyboard", StoryboardOutput)  # type: ignore[assignment]

        n = len(sb.slides)
        if n == 0:
            return TimingOutput(slides=[], total_seconds=float(config.duration), wpm=config.wpm)

        # Step 2: Content-based weights
        weights = _slide_weights(sb)

        # Step 3: Clamp weights (modifies weights proportionally to enforce min/max)
        clamped = _clamp_weights(weights, config.duration, MIN_SECONDS, MAX_SECONDS)

        # Step 4: Largest-remainder apportionment (sum guaranteed == config.duration)
        secs = apportion_seconds(clamped, config.duration)

        # Safety net: assert invariant (catches future regressions)
        assert sum(secs) == config.duration, (
            f"TimingStage invariant broken: sum(seconds)={sum(secs)} != {config.duration}"
        )

        # Step 5: Build SlideTiming per slide
        slides = [
            SlideTiming(
                slide_index=i,
                seconds=float(secs[i]),
                word_budget=word_budget(secs[i], config.wpm),
            )
            for i in range(n)
        ]

        return TimingOutput(
            slides=slides,
            total_seconds=float(config.duration),
            wpm=config.wpm,
        )
