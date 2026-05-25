"""Tests for TimingStage — TIME-01 (exact-sum + clamps) and TIME-02 (word budget).

All tests are pure (no mocks, no network, no workdir). The timing stage is
deterministic (D-08) so all invariants are testable offline.

Key invariants tested:
- exact_sum: sum(slide.seconds for slide in output.slides) == config.duration EXACTLY
  (largest-remainder apportionment guarantees this even with clamps active)
- word_budget: every slide.word_budget == round(slide.seconds * wpm / 60)
- clamp: no slide below MIN_SECONDS or above MAX_SECONDS (unless degenerate)
- apportion_seconds: helper returns ints summing to total for various weight patterns
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from avideo.models.storyboard import SlideSpec, StoryboardOutput, VisualType
from avideo.models.timing import SlideTiming, TimingOutput


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------


def _make_storyboard(*slide_specs: tuple[str, list[str]]) -> StoryboardOutput:
    """Build a StoryboardOutput from (title, bullets) tuples."""
    return StoryboardOutput(
        slides=[
            SlideSpec(title=title, bullets=bullets, visual_type=VisualType.bullets)
            for title, bullets in slide_specs
        ],
        language="es",
    )


def _make_workdir_with_storyboard(storyboard: StoryboardOutput) -> Any:
    """Return a mock WorkdirManager that serves the given storyboard."""
    mock_wd = MagicMock()
    mock_wd.read_checkpoint.return_value = storyboard
    return mock_wd


def _make_config(duration: int, wpm: int = 150) -> Any:
    """Return a minimal RunConfig-like object for the timing stage."""
    from avideo.models import RunConfig

    return RunConfig(bullets=Path("bullets.yaml"), duration=duration, wpm=wpm)


# ---------------------------------------------------------------------------
# apportion_seconds — pure unit tests (no stage instantiation)
# ---------------------------------------------------------------------------


def test_apportion_seconds_sums_to_total() -> None:
    """apportion_seconds must return ints summing exactly to total."""
    from avideo.stages.timing import apportion_seconds

    weights = [3, 2, 5]
    result = apportion_seconds(weights, 30)
    assert sum(result) == 30
    assert all(isinstance(x, int) for x in result)


def test_apportion_seconds_even_weights() -> None:
    """Equal weights → durations as equal as possible; sum exact."""
    from avideo.stages.timing import apportion_seconds

    weights = [1, 1, 1, 1]
    result = apportion_seconds(weights, 40)
    assert sum(result) == 40
    # All equal (each gets 10)
    assert set(result) == {10}


def test_apportion_seconds_single_slide() -> None:
    """Single slide gets 100% of the duration."""
    from avideo.stages.timing import apportion_seconds

    result = apportion_seconds([5], 120)
    assert result == [120]


def test_apportion_seconds_zero_weights_fallback() -> None:
    """If all weights are 0, apportion_seconds should not crash and must still sum to total."""
    from avideo.stages.timing import apportion_seconds

    result = apportion_seconds([0, 0, 0], 60)
    assert sum(result) == 60


def test_apportion_seconds_ties() -> None:
    """Tied fractional parts — exactly one slide should get the extra second."""
    from avideo.stages.timing import apportion_seconds

    # 3 equal weights, total = 10 → 3.33...; one slide must get 4, two get 3
    result = apportion_seconds([1, 1, 1], 10)
    assert sum(result) == 10
    assert sorted(result) == [3, 3, 4]


def test_apportion_seconds_large_slide_count() -> None:
    """12 slides, 300s total — must still sum exactly."""
    from avideo.stages.timing import apportion_seconds

    weights = [i + 1 for i in range(12)]  # varied weights
    result = apportion_seconds(weights, 300)
    assert sum(result) == 300
    assert len(result) == 12


# ---------------------------------------------------------------------------
# TimingStage.run — exact_sum invariant (TIME-01)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "slide_specs, duration",
    [
        (
            [("Intro", ["Punto 1", "Punto 2"]), ("Body", ["X", "Y", "Z"]), ("End", ["Final"])],
            90,
        ),
        (
            [("A", ["a"]), ("B", ["b", "c"]), ("C", ["c", "d", "e"])],
            60,
        ),
        (
            [
                ("Slide 1", ["One", "Two"]),
                ("Slide 2", ["Three"]),
                ("Slide 3", ["Four", "Five", "Six"]),
                ("Slide 4", ["Seven"]),
                ("Slide 5", ["Eight", "Nine"]),
            ],
            120,
        ),
    ],
)
def test_exact_sum(slide_specs: list, duration: int) -> None:
    """TIME-01: sum(slide.seconds) == duration EXACTLY with clamps active."""
    from avideo.stages.timing import TimingStage

    sb = _make_storyboard(*slide_specs)
    workdir = _make_workdir_with_storyboard(sb)
    config = _make_config(duration)

    stage = TimingStage()
    output = stage.run(workdir, config)

    total = sum(s.seconds for s in output.slides)
    assert total == duration, (
        f"Expected sum of seconds == {duration}, got {total}. "
        f"Slide durations: {[s.seconds for s in output.slides]}"
    )
    assert output.total_seconds == float(duration)


def test_exact_sum_with_varied_content() -> None:
    """TIME-01 variant: diverse bullet counts; sum invariant must hold."""
    from avideo.stages.timing import TimingStage

    sb = _make_storyboard(
        ("Short slide", ["One bullet"]),
        ("Medium slide", ["A", "B", "C", "D"]),
        ("Long slide", ["W " * 10] * 5),  # long bullets
        ("Final", ["Fin"]),
    )
    workdir = _make_workdir_with_storyboard(sb)
    config = _make_config(180)

    stage = TimingStage()
    output = stage.run(workdir, config)

    assert sum(s.seconds for s in output.slides) == 180


def test_exact_sum_clamps_active_still_holds() -> None:
    """TIME-01: even when min clamp forces redistribution, sum must equal duration."""
    from avideo.stages.timing import MIN_SECONDS, TimingStage

    # Build a storyboard where one slide has nearly zero content (would get < MIN_SECONDS
    # without clamping). A short duration with many slides triggers the min clamp.
    # 10 slides, 100s total → avg = 10s. Slides with tiny weights would get < MIN_SECONDS (8).
    sb = _make_storyboard(
        ("A", ["x"]),  # tiny
        ("B long title with lots of content", ["Bullet " * 15] * 4),  # heavy
        ("C", ["y"]),  # tiny
        ("D long slide", ["Content " * 10] * 3),  # medium-heavy
        ("E", ["z"]),  # tiny
    )
    workdir = _make_workdir_with_storyboard(sb)
    config = _make_config(100)

    stage = TimingStage()
    output = stage.run(workdir, config)

    total = sum(s.seconds for s in output.slides)
    assert total == 100, f"sum must be 100, got {total}"


# ---------------------------------------------------------------------------
# TimingStage.run — clamp behavior
# ---------------------------------------------------------------------------


def test_no_slide_below_min_seconds() -> None:
    """TIME-01 clamp: no slide should receive fewer seconds than MIN_SECONDS
    (unless there are so many slides that the total cannot satisfy all minimums —
    degenerate case skipped here by construction)."""
    from avideo.stages.timing import MIN_SECONDS, TimingStage

    sb = _make_storyboard(
        *[("Slide", ["Bullet"]) for _ in range(5)]
    )
    # 300s / 5 slides = 60s each — well above MIN_SECONDS
    workdir = _make_workdir_with_storyboard(sb)
    config = _make_config(300)

    stage = TimingStage()
    output = stage.run(workdir, config)

    for s in output.slides:
        assert s.seconds >= MIN_SECONDS, (
            f"Slide {s.slide_index} has {s.seconds}s < MIN_SECONDS ({MIN_SECONDS})"
        )


def test_no_slide_above_max_seconds() -> None:
    """TIME-01 clamp: no slide should receive more seconds than MAX_SECONDS.

    Uses 10 slides and 300s so unclamped share = 30s each, which is below MAX_SECONDS.
    The degenerate case (total > n * MAX_SECONDS, e.g. 3 slides, 300s) cannot satisfy
    the max clamp and is not tested here (documented as skipped degenerate case in SUMMARY).
    """
    from avideo.stages.timing import MAX_SECONDS, TimingStage

    # 10 slides, 300s → unclamped = 30s each, well under MAX_SECONDS (45)
    # However, if ONE slide has much more content it may get more than others.
    # Use equal-content slides so all get ~30s, then add one heavy slide to see clamping.
    # Make 8 tiny slides + 1 huge slide — the huge slide should get capped at MAX_SECONDS.
    sb = _make_storyboard(
        *[("Slide", ["Bullet"]) for _ in range(8)],
        ("Heavy Slide", ["Very long bullet content " * 20] * 5),  # heavy
    )
    # 9 slides, 270s → avg=30s. Heavy slide without clamp might get ~100+ but with MAX=45 it's capped.
    # However sum must still == 270.
    workdir = _make_workdir_with_storyboard(sb)
    config = _make_config(270)

    stage = TimingStage()
    output = stage.run(workdir, config)

    # The total sum still holds
    assert sum(s.seconds for s in output.slides) == 270

    # With MAX_SECONDS = 45 and total=270 distributed across 9 slides,
    # it's feasible to keep all slides <= MAX_SECONDS (9 * 45 = 405 >= 270)
    for s in output.slides:
        assert s.seconds <= MAX_SECONDS, (
            f"Slide {s.slide_index} has {s.seconds}s > MAX_SECONDS ({MAX_SECONDS})"
        )


# ---------------------------------------------------------------------------
# TimingStage.run — word_budget (TIME-02)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("wpm", [120, 150, 180])
def test_word_budget(wpm: int) -> None:
    """TIME-02: every slide.word_budget == round(seconds * wpm / 60)."""
    from avideo.stages.timing import TimingStage

    sb = _make_storyboard(
        ("Intro", ["Punto 1", "Punto 2", "Punto 3"]),
        ("Development", ["A", "B"]),
        ("Conclusion", ["Final"]),
    )
    workdir = _make_workdir_with_storyboard(sb)
    config = _make_config(duration=120, wpm=wpm)

    stage = TimingStage()
    output = stage.run(workdir, config)

    for s in output.slides:
        expected_budget = round(s.seconds * wpm / 60)
        assert s.word_budget == expected_budget, (
            f"Slide {s.slide_index}: word_budget={s.word_budget}, "
            f"expected round({s.seconds} * {wpm} / 60) = {expected_budget}"
        )


def test_word_budget_default_wpm() -> None:
    """TIME-02: with default WPM=150 (RunConfig default), budgets match."""
    from avideo.stages.timing import TimingStage

    sb = _make_storyboard(
        ("Slide A", ["Content A1", "Content A2"]),
        ("Slide B", ["Content B1"]),
    )
    workdir = _make_workdir_with_storyboard(sb)
    config = _make_config(duration=90, wpm=150)

    stage = TimingStage()
    output = stage.run(workdir, config)

    for s in output.slides:
        expected = round(s.seconds * 150 / 60)
        assert s.word_budget == expected


def test_wpm_stored_in_output() -> None:
    """TimingOutput.wpm should reflect the config.wpm value."""
    from avideo.stages.timing import TimingStage

    sb = _make_storyboard(("S1", ["b1"]), ("S2", ["b2"]))
    workdir = _make_workdir_with_storyboard(sb)
    config = _make_config(duration=60, wpm=180)

    stage = TimingStage()
    output = stage.run(workdir, config)

    assert output.wpm == 180


# ---------------------------------------------------------------------------
# TimingStage metadata
# ---------------------------------------------------------------------------


def test_stage_name_and_checkpoint_name() -> None:
    """stage_name must be 'timing'; checkpoint_name must be 'timings' (workdir contract)."""
    from avideo.stages.timing import TimingStage

    stage = TimingStage()
    assert stage.stage_name == "timing"
    assert stage.checkpoint_name == "timings"
