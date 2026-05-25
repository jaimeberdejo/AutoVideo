"""Tests for Stage protocol, stubs, PIPELINE_STAGES, and orchestrator loop.

Task 1 tests (stage/protocol/stub): tests prefixed with stage_, pipeline_order_, protocol_,
  stub_ — run with: uv run pytest tests/test_orchestrator.py -x -q -k "stage or pipeline_order or protocol or stub"

Task 2 tests (orchestrator loop): tests prefixed with test_orch_ — run with:
  uv run pytest tests/test_orchestrator.py -x -q
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Task 1 — Stage protocol, stubs, PIPELINE_STAGES
# ---------------------------------------------------------------------------

def test_pipeline_order():
    """PIPELINE_STAGES must follow canonical stage_name order."""
    from avideo.stages.stubs import PIPELINE_STAGES

    names = [s.stage_name for s in PIPELINE_STAGES]
    expected = [
        "context",
        "storyboard",
        "timing",
        "scriptwriter",
        "slides",
        "verify",
        "voice",
        "align",
        "subs",
        "assemble",
    ]
    assert names == expected, f"Got: {names}"


def test_all_stages_have_stage_name_and_callable_run():
    """ORCH-01: every stage has a non-empty stage_name and callable run(workdir, config)."""
    from avideo.stages.stubs import PIPELINE_STAGES

    for stage in PIPELINE_STAGES:
        assert isinstance(stage.stage_name, str) and stage.stage_name, (
            f"Empty stage_name on {stage!r}"
        )
        assert callable(stage.run), f"run() not callable on {stage!r}"


def test_stage_protocol_isinstance():
    """isinstance(stage, StageProtocol) must be True for all stages (runtime_checkable)."""
    from avideo.stages.base import StageProtocol
    from avideo.stages.stubs import PIPELINE_STAGES

    for stage in PIPELINE_STAGES:
        assert isinstance(stage, StageProtocol), (
            f"{stage!r} does not satisfy StageProtocol"
        )


def test_stub_run_returns_pydantic_basemodel(tmp_path):
    """ORCH-05: each stub.run returns a Pydantic BaseModel instance."""
    from pydantic import BaseModel

    from avideo.models import RunConfig
    from avideo.stages.stubs import PIPELINE_STAGES
    from avideo.utils.workdir import WorkdirManager

    config = RunConfig(
        bullets=Path("bullets.yaml"),
        duration=120,
    )
    workdir = WorkdirManager(tmp_path)
    for stage in PIPELINE_STAGES:
        result = stage.run(workdir, config)
        assert isinstance(result, BaseModel), (
            f"{stage.stage_name}.run() returned {type(result)}, expected BaseModel"
        )


def test_storyboard_stub_returns_at_least_one_slide(tmp_path):
    """StoryboardStub.run must return StoryboardOutput with at least one SlideSpec."""
    from avideo.models import RunConfig, StoryboardOutput
    from avideo.stages.stubs import StoryboardStub
    from avideo.utils.workdir import WorkdirManager

    config = RunConfig(bullets=Path("bullets.yaml"), duration=120)
    workdir = WorkdirManager(tmp_path)
    out = StoryboardStub().run(workdir, config)
    assert isinstance(out, StoryboardOutput)
    assert len(out.slides) >= 1


def test_context_stub_used_false_when_no_context(tmp_path):
    """ContextStub writes ContextOutput(used=False) when config.context is None."""
    from avideo.models import ContextOutput, RunConfig
    from avideo.stages.stubs import ContextStub
    from avideo.utils.workdir import WorkdirManager

    config = RunConfig(bullets=Path("bullets.yaml"), duration=120, context=None)
    workdir = WorkdirManager(tmp_path)
    out = ContextStub().run(workdir, config)
    assert isinstance(out, ContextOutput)
    assert out.used is False


def test_context_stub_used_true_with_context(tmp_path):
    """ContextStub writes ContextOutput(used=True) when config.context is set."""
    from avideo.models import ContextOutput, RunConfig
    from avideo.stages.stubs import ContextStub
    from avideo.utils.workdir import WorkdirManager

    ctx_file = tmp_path / "deck.pdf"
    ctx_file.touch()
    config = RunConfig(bullets=Path("bullets.yaml"), duration=120, context=ctx_file)
    workdir = WorkdirManager(tmp_path / "wd")
    out = ContextStub().run(workdir, config)
    assert isinstance(out, ContextOutput)
    assert out.used is True


def test_assemble_stub_creates_output_mp4(tmp_path):
    """AssembleStub.run must create workdir/output.mp4 and return AssemblyOutput."""
    from avideo.models import AssemblyOutput, RunConfig
    from avideo.stages.stubs import AssembleStub
    from avideo.utils.workdir import WorkdirManager

    config = RunConfig(bullets=Path("bullets.yaml"), duration=120)
    workdir = WorkdirManager(tmp_path)
    out = AssembleStub().run(workdir, config)
    assert isinstance(out, AssemblyOutput)
    assert out.output_path.endswith("output.mp4")
    assert (tmp_path / "output.mp4").exists(), "output.mp4 marker file not created"


def test_checkpoint_name_distinct_from_stage_name():
    """Some stages must have checkpoint_name != stage_name (timing, scriptwriter, verify, assemble)."""
    from avideo.stages.stubs import (
        AssembleStub,
        ScriptwriterStub,
        TimingStub,
        VerifyStub,
    )

    assert TimingStub().checkpoint_name == "timings"
    assert ScriptwriterStub().checkpoint_name == "script"
    assert VerifyStub().checkpoint_name == "verification"
    assert AssembleStub().checkpoint_name == "assembly"


# ---------------------------------------------------------------------------
# Task 2 — Orchestrator loop tests
# ---------------------------------------------------------------------------


def _make_config(tmp_path: Path, **kwargs: Any):
    """Helper: build a RunConfig pointing at tmp_path/workdir."""
    from avideo.models import RunConfig

    defaults = dict(
        bullets=Path("bullets.yaml"),
        duration=120,
        workdir=tmp_path / "workdir",
        level=4,
    )
    defaults.update(kwargs)
    return RunConfig(**defaults)


def test_orch_full_run_all_stages_done(tmp_path):
    """ORCH-01: run_pipeline level=4 executes all 10 stages; workdir.is_done True for each; output.mp4 exists."""
    from avideo.orchestrator import run_pipeline
    from avideo.utils.workdir import WorkdirManager

    config = _make_config(tmp_path, level=4)
    run_pipeline(config)

    wd = WorkdirManager(config.workdir)
    stage_names = [
        "context", "storyboard", "timing", "scriptwriter", "slides",
        "verify", "voice", "align", "subs", "assemble",
    ]
    for name in stage_names:
        assert wd.is_done(name), f"Stage {name!r} not marked done"
    assert (config.workdir / "output.mp4").exists(), "output.mp4 not created"


def test_orch_idempotent_second_run(tmp_path, monkeypatch):
    """ORCH-02/03: after full run, calling run_pipeline again calls zero stage.run()."""
    from avideo.orchestrator import run_pipeline
    from avideo.stages import stubs as stubs_module

    # Full first run
    config = _make_config(tmp_path, level=4)
    run_pipeline(config)

    # Spy: replace each stage's run with a MagicMock
    run_calls = []
    for stage in stubs_module.PIPELINE_STAGES:
        original_run = stage.run
        mock = MagicMock(side_effect=original_run)
        monkeypatch.setattr(stage, "run", mock)
        run_calls.append(mock)

    # Second run — all stages should be skipped
    run_pipeline(config)

    for mock in run_calls:
        mock.assert_not_called()


def test_orch_resume_after_partial(tmp_path, monkeypatch):
    """Resume: mark first 3 stages done manually; only remaining 7 are called."""
    from avideo.orchestrator import run_pipeline
    from avideo.stages import stubs as stubs_module
    from avideo.utils.workdir import WorkdirManager

    config = _make_config(tmp_path, level=4)
    wd = WorkdirManager(config.workdir)

    # Simulate first 3 stages already done
    first_three = ["context", "storyboard", "timing"]
    for name in first_three:
        wd.mark_done(name)

    # Spy on all stages
    run_calls: dict[str, MagicMock] = {}
    for stage in stubs_module.PIPELINE_STAGES:
        original_run = stage.run
        mock = MagicMock(side_effect=original_run)
        monkeypatch.setattr(stage, "run", mock)
        run_calls[stage.stage_name] = mock

    run_pipeline(config)

    for name in first_three:
        run_calls[name].assert_not_called()

    remaining = ["scriptwriter", "slides", "verify", "voice", "align", "subs", "assemble"]
    for name in remaining:
        run_calls[name].assert_called_once()


def test_orch_level4_no_pause(tmp_path, monkeypatch):
    """ORCH-04 L4: level=4 never calls pause_for_approval."""
    import avideo.utils.rich_ui as rich_ui_module

    from avideo.orchestrator import run_pipeline

    mock_pause = MagicMock()
    monkeypatch.setattr(rich_ui_module, "pause_for_approval", mock_pause)

    # Also patch orchestrator's imported reference
    import avideo.orchestrator as orch_module
    monkeypatch.setattr(orch_module, "pause_for_approval", mock_pause)

    config = _make_config(tmp_path, level=4)
    run_pipeline(config)

    mock_pause.assert_not_called()


def test_orch_level1_pauses_each_stage(tmp_path, monkeypatch):
    """ORCH-04 L1: level=1 calls pause_for_approval once per executed stage (10 times)."""
    import avideo.orchestrator as orch_module

    from avideo.orchestrator import run_pipeline

    mock_pause = MagicMock()
    monkeypatch.setattr(orch_module, "pause_for_approval", mock_pause)

    config = _make_config(tmp_path, level=1)
    run_pipeline(config)

    assert mock_pause.call_count == 10, (
        f"Expected 10 pause calls for L1, got {mock_pause.call_count}"
    )


def test_orch_level2_pauses_creative_stages(tmp_path, monkeypatch):
    """ORCH-04 L2: level=2 calls pause_for_approval exactly 4 times for creative stages."""
    import avideo.orchestrator as orch_module

    from avideo.orchestrator import run_pipeline

    mock_pause = MagicMock()
    monkeypatch.setattr(orch_module, "pause_for_approval", mock_pause)

    config = _make_config(tmp_path, level=2)
    run_pipeline(config)

    # Creative stages: storyboard, scriptwriter, slides, verify
    assert mock_pause.call_count == 4, (
        f"Expected 4 pause calls for L2, got {mock_pause.call_count}"
    )
    paused_names = [c.args[0] for c in mock_pause.call_args_list]
    assert set(paused_names) == {"storyboard", "scriptwriter", "slides", "verify"}


def test_orch_dry_run_no_stages_no_mp4(tmp_path, monkeypatch):
    """CLI-06: dry_run=True calls estimate_all and runs no stage; no output.mp4 created."""
    import avideo.orchestrator as orch_module

    from avideo.orchestrator import run_pipeline
    from avideo.stages import stubs as stubs_module

    mock_estimate = MagicMock()
    monkeypatch.setattr(orch_module, "estimate_all", mock_estimate)

    # Spy on all stages
    for stage in stubs_module.PIPELINE_STAGES:
        monkeypatch.setattr(stage, "run", MagicMock())

    config = _make_config(tmp_path, dry_run=True)
    run_pipeline(config)

    mock_estimate.assert_called_once_with(config)
    for stage in stubs_module.PIPELINE_STAGES:
        stage.run.assert_not_called()

    assert not (config.workdir / "output.mp4").exists(), (
        "output.mp4 must NOT exist after dry_run"
    )
    assert not config.workdir.exists(), (
        "workdir must NOT be created during dry_run (side-effect free)"
    )


def test_orch_mark_done_not_called_on_exception(tmp_path, monkeypatch):
    """Pitfall 4: if stage.run raises, mark_done is NOT called; is_done stays False.
    The orchestrator converts any stage exception to typer.Exit(1) for clean UX."""
    import typer as typer_module

    from avideo.orchestrator import run_pipeline
    from avideo.stages import stubs as stubs_module
    from avideo.utils.workdir import WorkdirManager

    config = _make_config(tmp_path, level=4)

    # Make the first stage (context) raise
    monkeypatch.setattr(stubs_module.PIPELINE_STAGES[0], "run", MagicMock(side_effect=RuntimeError("boom")))

    # Stage exceptions are now caught and converted to typer.Exit(1)
    with pytest.raises(typer_module.Exit) as exc_info:
        run_pipeline(config)
    assert exc_info.value.exit_code == 1

    wd = WorkdirManager(config.workdir)
    assert not wd.is_done("context"), "mark_done must not be called when run() raises"
