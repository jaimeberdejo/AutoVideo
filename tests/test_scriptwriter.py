"""Tests for ScriptwriterStage — SCRIPT-01 (calibration retry, no infinite loop)
and SCRIPT-02 (language, structured ScriptOutput).

call_structured is mocked at the stage's module scope so no real API calls are made.
Storyboard and timing checkpoints are provided via a mock WorkdirManager.

Key invariants tested:
- SCRIPT-01: calibration fires ONCE on >25% drift (exactly 2 call_structured calls)
- SCRIPT-01: no retry when within budget (exactly 1 call_structured call)
- SCRIPT-01: no infinite loop — 2 calls maximum regardless of 2nd result quality
- SCRIPT-02: output.language == config.language; structure is ScriptOutput
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, call

import pytest

from avideo.models.script import ScriptOutput, SlideScript
from avideo.models.storyboard import SlideSpec, StoryboardOutput, VisualType
from avideo.models.timing import SlideTiming, TimingOutput


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_storyboard(n_slides: int = 3) -> StoryboardOutput:
    return StoryboardOutput(
        slides=[
            SlideSpec(
                title=f"Slide {i}",
                bullets=[f"Bullet {i}.{j}" for j in range(2)],
                visual_type=VisualType.bullets,
            )
            for i in range(n_slides)
        ],
        language="es",
    )


def _make_timing(seconds_list: list[float], wpm: int = 150) -> TimingOutput:
    return TimingOutput(
        slides=[
            SlideTiming(
                slide_index=i,
                seconds=s,
                word_budget=round(s * wpm / 60),
            )
            for i, s in enumerate(seconds_list)
        ],
        total_seconds=sum(seconds_list),
        wpm=wpm,
    )


def _make_script_output(narrations: list[str], language: str = "es") -> ScriptOutput:
    return ScriptOutput(
        slides=[
            SlideScript(slide_index=i, narration=n)
            for i, n in enumerate(narrations)
        ],
        language=language,
    )


def _make_workdir_for_scriptwriter(
    storyboard: StoryboardOutput, timing: TimingOutput
) -> Any:
    """Return a mock WorkdirManager that serves storyboard + timing checkpoints."""
    mock_wd = MagicMock()

    def _read_checkpoint(name: str, model_class: type) -> Any:
        if name == "storyboard":
            return storyboard
        if name == "timings":
            return timing
        raise FileNotFoundError(f"Unknown checkpoint: {name}")

    mock_wd.read_checkpoint.side_effect = _read_checkpoint
    return mock_wd


def _make_config(language: str = "es", wpm: int = 150) -> Any:
    from avideo.models import RunConfig

    return RunConfig(bullets=Path("bullets.yaml"), duration=90, wpm=wpm, language=language)


# ---------------------------------------------------------------------------
# SCRIPT-01 — calibration retry tests
# ---------------------------------------------------------------------------


def test_calibration_fires_once_on_high_drift() -> None:
    """SCRIPT-01: when 1st result has >25% drift, call_structured is called exactly 2 times.

    The 2nd narration is returned (no 3rd call — no infinite loop).
    """
    # 3 slides, 30s each → budget = round(30 * 150 / 60) = 75 words per slide
    timing = _make_timing([30.0, 30.0, 30.0])
    storyboard = _make_storyboard(3)
    workdir = _make_workdir_for_scriptwriter(storyboard, timing)
    config = _make_config()

    # Budget = 75 words per slide
    # off_budget_script: each slide has ~10 words (way under budget → >25% drift)
    off_budget_narrations = [
        "Esta es la introducción del tema.",       # ~6 words
        "El punto central se explica aquí.",       # ~7 words
        "Finalmente, concluimos el análisis.",     # ~5 words
    ]
    # still_off_script: even the 2nd result is off-budget, but we accept it (no 3rd call)
    still_off_narrations = [
        "El tema se desarrolla con más detalle.",  # ~8 words
        "Analizamos los aspectos fundamentales.",  # ~5 words
        "La conclusión recoge las ideas expuestas.", # ~7 words
    ]

    off_budget_script = _make_script_output(off_budget_narrations)
    still_off_script = _make_script_output(still_off_narrations)

    with patch("avideo.stages.scriptwriter.call_structured") as mock_call:
        mock_call.side_effect = [off_budget_script, still_off_script]

        from avideo.stages.scriptwriter import ScriptwriterStage
        stage = ScriptwriterStage()
        result = stage.run(workdir, config)

    assert mock_call.call_count == 2, (
        f"Expected exactly 2 call_structured calls (1 initial + 1 retry), "
        f"got {mock_call.call_count}"
    )
    # Must return the 2nd result (the calibration result), not the 1st
    assert result.slides[0].narration == still_off_narrations[0]
    assert isinstance(result, ScriptOutput)


def test_no_retry_when_within_budget() -> None:
    """SCRIPT-01: when 1st result is within 25% drift, call_structured is called exactly 1 time."""
    # 3 slides, 40s each → budget = round(40 * 150 / 60) = 100 words per slide
    timing = _make_timing([40.0, 40.0, 40.0])
    storyboard = _make_storyboard(3)
    workdir = _make_workdir_for_scriptwriter(storyboard, timing)
    config = _make_config()

    # Budget = 100 words per slide. ~95 words = within 5% drift → no retry
    # We approximate by counting spaces+1 in a roughly 95-word narration
    good_narration = " ".join(["palabra"] * 95)  # exactly 95 words per slide
    good_script = _make_script_output([good_narration, good_narration, good_narration])

    with patch("avideo.stages.scriptwriter.call_structured") as mock_call:
        mock_call.side_effect = [good_script]

        from avideo.stages.scriptwriter import ScriptwriterStage
        stage = ScriptwriterStage()
        result = stage.run(workdir, config)

    assert mock_call.call_count == 1, (
        f"Expected exactly 1 call_structured call (no retry needed), "
        f"got {mock_call.call_count}"
    )
    assert isinstance(result, ScriptOutput)


def test_no_infinite_loop_max_two_calls() -> None:
    """SCRIPT-01: at most 2 calls — even if 2nd result is also bad, no 3rd call."""
    timing = _make_timing([30.0, 30.0, 30.0])
    storyboard = _make_storyboard(3)
    workdir = _make_workdir_for_scriptwriter(storyboard, timing)
    config = _make_config()

    # Both results are ~10 words (budget=75, drift >> 25%)
    bad_narration = "Muy corto."
    bad_script_1 = _make_script_output([bad_narration, bad_narration, bad_narration])
    bad_script_2 = _make_script_output([bad_narration, bad_narration, bad_narration])

    with patch("avideo.stages.scriptwriter.call_structured") as mock_call:
        mock_call.side_effect = [bad_script_1, bad_script_2]

        from avideo.stages.scriptwriter import ScriptwriterStage
        stage = ScriptwriterStage()
        result = stage.run(workdir, config)

    # MUST be exactly 2 calls — accept result after retry without further checking
    assert mock_call.call_count == 2, (
        f"Expected 2 calls (no infinite loop), got {mock_call.call_count}"
    )
    # Returns the 2nd result (the retry result)
    assert result.slides[0].narration == bad_narration


def test_calibration_threshold_boundary() -> None:
    """SCRIPT-01: drift exactly at 25% boundary — should NOT trigger retry."""
    # Budget = 100 words per slide; 75 words = exactly 25% drift
    # Threshold is > 0.25, so 25% is NOT over threshold → no retry
    timing = _make_timing([40.0, 40.0, 40.0])  # budget = 100 words each
    storyboard = _make_storyboard(3)
    workdir = _make_workdir_for_scriptwriter(storyboard, timing)
    config = _make_config()

    # 75 words = (100 - 75) / 100 = 0.25 drift — exactly at boundary, not OVER
    at_boundary_narration = " ".join(["palabra"] * 75)
    at_boundary_script = _make_script_output(
        [at_boundary_narration, at_boundary_narration, at_boundary_narration]
    )

    with patch("avideo.stages.scriptwriter.call_structured") as mock_call:
        mock_call.side_effect = [at_boundary_script]

        from avideo.stages.scriptwriter import ScriptwriterStage
        stage = ScriptwriterStage()
        result = stage.run(workdir, config)

    # 25% drift should NOT trigger retry (threshold is STRICTLY > 0.25)
    assert mock_call.call_count == 1, (
        f"25% drift should not trigger retry (need > 0.25), got {mock_call.call_count} calls"
    )


# ---------------------------------------------------------------------------
# SCRIPT-02 — language and output structure
# ---------------------------------------------------------------------------


def test_output_language_matches_config() -> None:
    """SCRIPT-02: output.language == config.language."""
    timing = _make_timing([30.0, 30.0])
    storyboard = _make_storyboard(2)
    workdir = _make_workdir_for_scriptwriter(storyboard, timing)
    config = _make_config(language="en")

    script = _make_script_output(
        [" ".join(["word"] * 50), " ".join(["word"] * 50)], language="en"
    )

    with patch("avideo.stages.scriptwriter.call_structured") as mock_call:
        mock_call.return_value = script

        from avideo.stages.scriptwriter import ScriptwriterStage
        stage = ScriptwriterStage()
        result = stage.run(workdir, config)

    assert result.language == "en"


def test_output_is_script_output_instance() -> None:
    """SCRIPT-02: stage returns a ScriptOutput Pydantic model."""
    timing = _make_timing([60.0])
    storyboard = _make_storyboard(1)
    workdir = _make_workdir_for_scriptwriter(storyboard, timing)
    config = _make_config()

    script = _make_script_output([" ".join(["palabra"] * 100)])

    with patch("avideo.stages.scriptwriter.call_structured") as mock_call:
        mock_call.return_value = script

        from avideo.stages.scriptwriter import ScriptwriterStage
        stage = ScriptwriterStage()
        result = stage.run(workdir, config)

    assert isinstance(result, ScriptOutput)
    assert len(result.slides) == 1
    assert isinstance(result.slides[0], SlideScript)


def test_output_default_language_es() -> None:
    """SCRIPT-02: default language is 'es' (Spanish)."""
    timing = _make_timing([30.0, 30.0])
    storyboard = _make_storyboard(2)
    workdir = _make_workdir_for_scriptwriter(storyboard, timing)
    config = _make_config(language="es")

    script = _make_script_output(
        [" ".join(["palabra"] * 75), " ".join(["palabra"] * 75)]
    )

    with patch("avideo.stages.scriptwriter.call_structured") as mock_call:
        mock_call.return_value = script

        from avideo.stages.scriptwriter import ScriptwriterStage
        stage = ScriptwriterStage()
        result = stage.run(workdir, config)

    assert result.language == "es"


# ---------------------------------------------------------------------------
# ScriptwriterStage metadata
# ---------------------------------------------------------------------------


def test_stage_name_and_checkpoint_name() -> None:
    """stage_name must be 'scriptwriter'; checkpoint_name must be 'script'."""
    from avideo.stages.scriptwriter import ScriptwriterStage

    stage = ScriptwriterStage()
    assert stage.stage_name == "scriptwriter"
    assert stage.checkpoint_name == "script"


def test_call_structured_imported_at_module_scope() -> None:
    """call_structured must be importable from avideo.stages.scriptwriter (mock point).

    This verifies the import exists at module scope so tests can patch it via
    'avideo.stages.scriptwriter.call_structured' without touching the integration layer.
    """
    import avideo.stages.scriptwriter as scriptwriter_module

    assert hasattr(scriptwriter_module, "call_structured"), (
        "call_structured must be imported at module scope in scriptwriter.py "
        "so tests can patch avideo.stages.scriptwriter.call_structured"
    )
