"""Tests for Stage protocol, stubs, PIPELINE_STAGES, and orchestrator loop.

Task 1 tests (stage/protocol/stub): tests prefixed with stage_, pipeline_order_, protocol_,
  stub_ — run with: uv run pytest tests/test_orchestrator.py -x -q -k "stage or pipeline_order or protocol or stub"

Task 2 tests (orchestrator loop): tests prefixed with test_orch_ — run with:
  uv run pytest tests/test_orchestrator.py -x -q
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers for patching AssembleStage ffmpeg calls (Phase 5 swap)
# ---------------------------------------------------------------------------

_CANNED_LOUDNORM_PASS1 = (
    "ffmpeg version 8.0.1\n"
    "{\n"
    '    "input_i" : "-22.01",\n'
    '    "input_tp" : "-20.91",\n'
    '    "input_lra" : "0.70",\n'
    '    "input_thresh" : "-32.01",\n'
    '    "output_i" : "-15.74",\n'
    '    "output_tp" : "-14.60",\n'
    '    "output_lra" : "0.50",\n'
    '    "output_thresh" : "-25.74",\n'
    '    "normalization_type" : "dynamic",\n'
    '    "target_offset" : "-0.26"\n'
    "}\n"
)

_CANNED_LOUDNORM_PASS2 = (
    "{\n"
    '    "input_i" : "-16.09",\n'
    '    "input_tp" : "-1.50",\n'
    '    "input_lra" : "0.50",\n'
    '    "input_thresh" : "-26.09",\n'
    '    "output_i" : "-16.01",\n'
    '    "output_tp" : "-1.50",\n'
    '    "output_lra" : "0.50",\n'
    '    "output_thresh" : "-26.01",\n'
    '    "normalization_type" : "linear",\n'
    '    "target_offset" : "0.09"\n'
    "}\n"
)


def _fake_run_ffmpeg_factory():
    """Return a run_ffmpeg side_effect that creates output files without real ffmpeg.

    Call order: 0=assembly encode, 1=loudnorm pass-1 (measure), 2=loudnorm pass-2 (apply).
    """
    call_count = [0]

    def _fake(args):
        idx = call_count[0]
        call_count[0] += 1
        if idx == 0:  # assembly encode → create output.tmp.mp4
            out = Path(args[-1])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"fake mp4")
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")
        elif idx == 1:  # loudnorm pass-1 → return canned stderr
            return types.SimpleNamespace(returncode=0, stdout="", stderr=_CANNED_LOUDNORM_PASS1)
        else:  # loudnorm pass-2 → create output.norm.tmp.mp4
            out = Path(args[-1])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"fake normalised mp4")
            return types.SimpleNamespace(returncode=0, stdout="", stderr=_CANNED_LOUDNORM_PASS2)

    return _fake


def _fake_probe_duration(_path: str) -> float:
    return 5.0


def _fake_verify_factory():
    """Return a side_effect for call_structured_with_images that returns an ok SlideVerdict.

    Mirrors _fake_run_ffmpeg_factory() pattern — returns a canned ok verdict
    so full-pipeline tests never hit the Anthropic API.
    """
    from avideo.models.verification import SlideVerdict

    call_count = [0]

    def _fake(**kwargs):
        idx = call_count[0]
        call_count[0] += 1
        return SlideVerdict(slide_index=idx, status="ok")

    return _fake


def _make_slide_pngs(workdir: Path, n: int = 2) -> list[str]:
    """Create tiny PNG files in workdir/slides/ and return their paths."""
    from PIL import Image

    slides_dir = workdir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in range(n):
        p = slides_dir / f"slide_{i:02d}.png"
        Image.new("RGB", (100, 60), (10, 20, 30)).save(p, format="PNG")
        paths.append(str(p))
    return paths


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
    """ORCH-05: each stage.run returns a Pydantic BaseModel instance.

    Real stages (storyboard, scriptwriter, voice) are mocked so no API calls are made.
    Checkpoints are written between stage runs to simulate the real orchestrator loop.
    """
    from pydantic import BaseModel

    from avideo.models import RunConfig
    from avideo.models.storyboard import SlideSpec, StoryboardOutput, VisualType
    from avideo.models.timing import SlideTiming, TimingOutput
    from avideo.models.timings import SlideTimings, WordTiming
    from avideo.stages.stubs import PIPELINE_STAGES
    from avideo.utils.workdir import WorkdirManager

    # Create a real bullets.yaml so StoryboardStage can load it
    bullets_file = tmp_path / "bullets.yaml"
    bullets_file.write_text(
        "title: Test\nbullets:\n  - Bullet 1\n  - Bullet 2\n",
        encoding="utf-8",
    )
    config = RunConfig(
        bullets=bullets_file,
        duration=120,
    )
    workdir = WorkdirManager(tmp_path)

    # Pre-write storyboard + timings checkpoints so timing/scriptwriter stages can read them
    storyboard_out = StoryboardOutput(
        slides=[SlideSpec(title="Slide 1", bullets=["B1", "B2"], visual_type=VisualType.bullets)],
        language="es",
    )
    timings_out = TimingOutput(
        slides=[SlideTiming(slide_index=0, seconds=120.0, word_budget=300)],
        total_seconds=120.0,
        wpm=150,
    )
    from avideo.models.script import ScriptOutput, SlideScript
    script_out = ScriptOutput(
        slides=[SlideScript(slide_index=0, narration=" ".join(["palabra"] * 290))],
        language="es",
    )
    workdir.write_checkpoint("storyboard", storyboard_out)
    workdir.write_checkpoint("timings", timings_out)

    from avideo.models.theme import DEFAULT_THEME, ThemeConfig

    def _cs_side_effect(**kwargs):
        """Route call_structured by output_model for all three LLM stages."""
        from avideo.models.script import ScriptOutput
        output_model = kwargs.get("output_model")
        if output_model is StoryboardOutput:
            return storyboard_out
        if output_model is ScriptOutput:
            return script_out
        if output_model is ThemeConfig:
            return DEFAULT_THEME
        raise RuntimeError(f"Unexpected output_model: {output_model}")

    # Mock synthesize_slide for VoiceStage (ElevenLabs path — no real API call)
    fake_slide_timings = SlideTimings(
        slide_index=0,
        audio_path="audio/slide_00.mp3",
        duration=5.0,
        words=[
            WordTiming(text="palabra", start=0.1, end=0.5),
            WordTiming(text="narrada", start=0.6, end=1.0),
        ],
    )

    mock_cs = MagicMock(side_effect=_cs_side_effect)
    mock_renderer_cls, _ = _mock_renderer_cls()

    # Mock call_structured for storyboard, scriptwriter, slides_auto; mock SlideRenderer;
    # mock synthesize_slide for VoiceElevenlabsStage (Phase 4); mock verify vision call.
    with (
        patch("avideo.stages.storyboard.call_structured", mock_cs),
        patch("avideo.stages.scriptwriter.call_structured", mock_cs),
        patch("avideo.stages.slides_auto.call_structured", mock_cs),
        patch("avideo.stages.slides_auto.SlideRenderer", mock_renderer_cls),
        patch("avideo.stages.verify_slides.call_structured_with_images", side_effect=_fake_verify_factory()),
        patch("avideo.stages.voice_elevenlabs.synthesize_slide", return_value=fake_slide_timings),
        patch("avideo.stages.assemble.run_ffmpeg", side_effect=_fake_run_ffmpeg_factory()),
        patch("avideo.stages.assemble.probe_duration", side_effect=_fake_probe_duration),
    ):
        for stage in PIPELINE_STAGES:
            result = stage.run(workdir, config)
            assert isinstance(result, BaseModel), (
                f"{stage.stage_name}.run() returned {type(result)}, expected BaseModel"
            )
            # Write checkpoint between runs so downstream stages can read it
            # (mirrors what the real orchestrator loop does)
            workdir.write_checkpoint(stage.checkpoint_name, result)


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


def test_real_stages_have_correct_checkpoint_names():
    """Real stages must keep the same checkpoint_name as their stubs."""
    from avideo.stages.timing import TimingStage
    from avideo.stages.scriptwriter import ScriptwriterStage

    assert TimingStage().checkpoint_name == "timings"
    assert ScriptwriterStage().checkpoint_name == "script"


# ---------------------------------------------------------------------------
# Task 2 — Orchestrator loop tests
# ---------------------------------------------------------------------------


def _make_config(tmp_path: Path, **kwargs: Any):
    """Helper: build a RunConfig pointing at tmp_path/workdir with a real bullets.yaml."""
    from avideo.models import RunConfig

    # Create a real bullets.yaml so StoryboardStage can load it
    bullets_file = tmp_path / "bullets.yaml"
    if not bullets_file.exists():
        bullets_file.write_text(
            "title: Test\nbullets:\n  - Bullet 1\n  - Bullet 2\n",
            encoding="utf-8",
        )

    defaults = dict(
        bullets=bullets_file,
        duration=120,
        workdir=tmp_path / "workdir",
        level=4,
    )
    defaults.update(kwargs)
    return RunConfig(**defaults)


def _mock_renderer_cls():
    """Return (mock_class, mock_instance) for SlideRenderer — no Chromium launched."""
    mock_instance = MagicMock()
    mock_instance.__enter__ = MagicMock(return_value=mock_instance)
    mock_instance.__exit__ = MagicMock(return_value=False)
    mock_instance.render_to_png = MagicMock()
    mock_class = MagicMock(return_value=mock_instance)
    return mock_class, mock_instance


def _mock_call_structured_for_pipeline(tmp_path: Path):
    """Return a call_structured mock that produces valid stage outputs.

    The mock inspects output_model to return the appropriate Pydantic object
    for StoryboardStage, ScriptwriterStage, and SlidesAutoStage (theme).
    """
    from avideo.models.script import ScriptOutput, SlideScript
    from avideo.models.storyboard import SlideSpec, StoryboardOutput, VisualType
    from avideo.models.theme import DEFAULT_THEME, ThemeConfig

    storyboard_out = StoryboardOutput(
        slides=[
            SlideSpec(title="Slide 1", bullets=["Bullet 1", "Bullet 2"], visual_type=VisualType.bullets),
            SlideSpec(title="Slide 2", bullets=["Bullet 3"], visual_type=VisualType.bullets),
        ],
        language="es",
    )
    script_out = ScriptOutput(
        slides=[
            SlideScript(slide_index=0, narration=" ".join(["palabra"] * 50)),
            SlideScript(slide_index=1, narration=" ".join(["palabra"] * 30)),
        ],
        language="es",
    )

    def _side_effect(**kwargs):
        output_model = kwargs.get("output_model")
        if output_model is StoryboardOutput:
            return storyboard_out
        if output_model is ScriptOutput:
            return script_out
        if output_model is ThemeConfig:
            return DEFAULT_THEME
        raise RuntimeError(f"Unexpected output_model: {output_model}")

    return MagicMock(side_effect=_side_effect)


def _fake_synthesize_slide_factory():
    """Return a side_effect function for mocking synthesize_slide in pipeline tests.

    Produces a SlideTimings with real words so SubtitlesStage can generate cues.
    The slide_index is read from the kwargs to produce correctly indexed output.
    """
    from avideo.models.timings import SlideTimings, WordTiming

    def _synthesize(text, slide_index, voice_id, out_path):
        # Write a zero-byte file so subsequent file-existence checks don't fail
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.touch()
        return SlideTimings(
            slide_index=slide_index,
            audio_path=str(out_path),
            duration=3.0,
            words=[
                WordTiming(text="hola", start=0.1, end=0.5),
                WordTiming(text="mundo", start=0.6, end=1.0),
            ],
        )

    return _synthesize


def test_orch_full_run_all_stages_done(tmp_path):
    """ORCH-01: run_pipeline level=4 executes all 10 stages; workdir.is_done True for each; output.mp4 exists."""
    from avideo.orchestrator import run_pipeline
    from avideo.utils.workdir import WorkdirManager

    config = _make_config(tmp_path, level=4)
    mock_cs = _mock_call_structured_for_pipeline(tmp_path)
    mock_renderer_cls, _ = _mock_renderer_cls()

    with (
        patch("avideo.stages.storyboard.call_structured", mock_cs),
        patch("avideo.stages.scriptwriter.call_structured", mock_cs),
        patch("avideo.stages.slides_auto.call_structured", mock_cs),
        patch("avideo.stages.slides_auto.SlideRenderer", mock_renderer_cls),
        patch("avideo.stages.verify_slides.call_structured_with_images", side_effect=_fake_verify_factory()),
        patch("avideo.stages.voice_elevenlabs.synthesize_slide", side_effect=_fake_synthesize_slide_factory()),
        patch("avideo.stages.assemble.run_ffmpeg", side_effect=_fake_run_ffmpeg_factory()),
        patch("avideo.stages.assemble.probe_duration", side_effect=_fake_probe_duration),
    ):
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
    mock_cs = _mock_call_structured_for_pipeline(tmp_path)
    mock_renderer_cls, _ = _mock_renderer_cls()

    with (
        patch("avideo.stages.storyboard.call_structured", mock_cs),
        patch("avideo.stages.scriptwriter.call_structured", mock_cs),
        patch("avideo.stages.slides_auto.call_structured", mock_cs),
        patch("avideo.stages.slides_auto.SlideRenderer", mock_renderer_cls),
        patch("avideo.stages.verify_slides.call_structured_with_images", side_effect=_fake_verify_factory()),
        patch("avideo.stages.voice_elevenlabs.synthesize_slide", side_effect=_fake_synthesize_slide_factory()),
        patch("avideo.stages.assemble.run_ffmpeg", side_effect=_fake_run_ffmpeg_factory()),
        patch("avideo.stages.assemble.probe_duration", side_effect=_fake_probe_duration),
    ):
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
    from avideo.models.context import ContextOutput
    from avideo.models.storyboard import SlideSpec, StoryboardOutput, VisualType
    from avideo.models.timing import SlideTiming, TimingOutput

    config = _make_config(tmp_path, level=4)
    wd = WorkdirManager(config.workdir)

    # Simulate first 3 stages already done — write real checkpoints so downstream
    # real stages (scriptwriter) can read them
    context_out = ContextOutput(used=False)
    storyboard_out = StoryboardOutput(
        slides=[
            SlideSpec(title="S1", bullets=["B1", "B2"], visual_type=VisualType.bullets),
            SlideSpec(title="S2", bullets=["B3"], visual_type=VisualType.bullets),
        ],
        language="es",
    )
    timings_out = TimingOutput(
        slides=[
            SlideTiming(slide_index=0, seconds=70.0, word_budget=175),
            SlideTiming(slide_index=1, seconds=50.0, word_budget=125),
        ],
        total_seconds=120.0,
        wpm=150,
    )
    wd.write_checkpoint("context", context_out)
    wd.mark_done("context")
    wd.write_checkpoint("storyboard", storyboard_out)
    wd.mark_done("storyboard")
    wd.write_checkpoint("timings", timings_out)
    wd.mark_done("timing")

    # Spy on all stages
    run_calls: dict[str, MagicMock] = {}
    for stage in stubs_module.PIPELINE_STAGES:
        original_run = stage.run
        mock = MagicMock(side_effect=original_run)
        monkeypatch.setattr(stage, "run", mock)
        run_calls[stage.stage_name] = mock

    mock_cs = _mock_call_structured_for_pipeline(tmp_path)
    mock_renderer_cls, _ = _mock_renderer_cls()
    with (
        patch("avideo.stages.storyboard.call_structured", mock_cs),
        patch("avideo.stages.scriptwriter.call_structured", mock_cs),
        patch("avideo.stages.slides_auto.call_structured", mock_cs),
        patch("avideo.stages.slides_auto.SlideRenderer", mock_renderer_cls),
        patch("avideo.stages.verify_slides.call_structured_with_images", side_effect=_fake_verify_factory()),
        patch("avideo.stages.voice_elevenlabs.synthesize_slide", side_effect=_fake_synthesize_slide_factory()),
        patch("avideo.stages.assemble.run_ffmpeg", side_effect=_fake_run_ffmpeg_factory()),
        patch("avideo.stages.assemble.probe_duration", side_effect=_fake_probe_duration),
    ):
        run_pipeline(config)

    first_three = ["context", "storyboard", "timing"]
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
    mock_cs = _mock_call_structured_for_pipeline(tmp_path)
    mock_renderer_cls, _ = _mock_renderer_cls()

    with (
        patch("avideo.stages.storyboard.call_structured", mock_cs),
        patch("avideo.stages.scriptwriter.call_structured", mock_cs),
        patch("avideo.stages.slides_auto.call_structured", mock_cs),
        patch("avideo.stages.slides_auto.SlideRenderer", mock_renderer_cls),
        patch("avideo.stages.verify_slides.call_structured_with_images", side_effect=_fake_verify_factory()),
        patch("avideo.stages.voice_elevenlabs.synthesize_slide", side_effect=_fake_synthesize_slide_factory()),
        patch("avideo.stages.assemble.run_ffmpeg", side_effect=_fake_run_ffmpeg_factory()),
        patch("avideo.stages.assemble.probe_duration", side_effect=_fake_probe_duration),
    ):
        run_pipeline(config)

    mock_pause.assert_not_called()


def test_orch_level1_pauses_each_stage(tmp_path, monkeypatch):
    """ORCH-04 L1: level=1 calls pause_for_approval once per executed stage (10 times)."""
    import avideo.orchestrator as orch_module

    from avideo.orchestrator import run_pipeline

    mock_pause = MagicMock()
    monkeypatch.setattr(orch_module, "pause_for_approval", mock_pause)

    config = _make_config(tmp_path, level=1)
    mock_cs = _mock_call_structured_for_pipeline(tmp_path)
    mock_renderer_cls, _ = _mock_renderer_cls()

    with (
        patch("avideo.stages.storyboard.call_structured", mock_cs),
        patch("avideo.stages.scriptwriter.call_structured", mock_cs),
        patch("avideo.stages.slides_auto.call_structured", mock_cs),
        patch("avideo.stages.slides_auto.SlideRenderer", mock_renderer_cls),
        patch("avideo.stages.verify_slides.call_structured_with_images", side_effect=_fake_verify_factory()),
        patch("avideo.stages.voice_elevenlabs.synthesize_slide", side_effect=_fake_synthesize_slide_factory()),
        patch("avideo.stages.assemble.run_ffmpeg", side_effect=_fake_run_ffmpeg_factory()),
        patch("avideo.stages.assemble.probe_duration", side_effect=_fake_probe_duration),
    ):
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
    mock_cs = _mock_call_structured_for_pipeline(tmp_path)
    mock_renderer_cls, _ = _mock_renderer_cls()

    with (
        patch("avideo.stages.storyboard.call_structured", mock_cs),
        patch("avideo.stages.scriptwriter.call_structured", mock_cs),
        patch("avideo.stages.slides_auto.call_structured", mock_cs),
        patch("avideo.stages.slides_auto.SlideRenderer", mock_renderer_cls),
        patch("avideo.stages.verify_slides.call_structured_with_images", side_effect=_fake_verify_factory()),
        patch("avideo.stages.voice_elevenlabs.synthesize_slide", side_effect=_fake_synthesize_slide_factory()),
        patch("avideo.stages.assemble.run_ffmpeg", side_effect=_fake_run_ffmpeg_factory()),
        patch("avideo.stages.assemble.probe_duration", side_effect=_fake_probe_duration),
    ):
        run_pipeline(config)

    # Creative stages: storyboard, scriptwriter, slides, verify (auto mode: verify uses pre-run pause)
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


# ---------------------------------------------------------------------------
# Verify-gate tests (VERIFY-03) — Wave-0 RED scaffold
# ---------------------------------------------------------------------------

def _make_hybrid_config(tmp_path: Path, level: int = 3, **kwargs):
    """Build a hybrid-mode RunConfig for verify-gate tests."""
    from avideo.models import RunConfig

    bullets_file = tmp_path / "bullets.yaml"
    if not bullets_file.exists():
        bullets_file.write_text(
            "title: Test\nbullets:\n  - Bullet 1\n  - Bullet 2\n",
            encoding="utf-8",
        )
    defaults = dict(
        bullets=bullets_file,
        duration=120,
        workdir=tmp_path / "workdir",
        level=level,
        slides_mode="hybrid",
    )
    defaults.update(kwargs)
    return RunConfig(**defaults)


def _pre_populate_hybrid_workdir(tmp_path: Path, workdir: Path, fail_slide: bool = False):
    """Write all checkpoint data needed for a hybrid pipeline run through verify.

    Returns the mock side_effect for call_structured_with_images so the test
    can supply either an ok or fail verdict.
    """
    from avideo.models.context import ContextOutput
    from avideo.models.script import ScriptOutput, SlideScript
    from avideo.models.slides import SlidesOutput
    from avideo.models.storyboard import SlideSpec, StoryboardOutput, VisualType
    from avideo.models.timing import SlideTiming, TimingOutput
    from avideo.models.verification import SlideVerdict
    from avideo.utils.workdir import WorkdirManager

    wd = WorkdirManager(workdir)

    # Write all pre-verify checkpoints
    context_out = ContextOutput(used=False)
    storyboard_out = StoryboardOutput(
        slides=[
            SlideSpec(title="S1", bullets=["B1"], visual_type=VisualType.bullets),
            SlideSpec(title="S2", bullets=["B2"], visual_type=VisualType.bullets),
        ],
        language="es",
    )
    timings_out = TimingOutput(
        slides=[
            SlideTiming(slide_index=0, seconds=60.0, word_budget=150),
            SlideTiming(slide_index=1, seconds=60.0, word_budget=150),
        ],
        total_seconds=120.0,
        wpm=150,
    )
    script_out = ScriptOutput(
        slides=[
            SlideScript(slide_index=0, narration="Narración diapositiva uno."),
            SlideScript(slide_index=1, narration="Narración diapositiva dos."),
        ],
        language="es",
    )

    # Create real slide PNGs
    png_paths = _make_slide_pngs(workdir, n=2)
    slides_out = SlidesOutput(png_paths=png_paths, mode="hybrid")

    wd.write_checkpoint("context", context_out)
    wd.mark_done("context")
    wd.write_checkpoint("storyboard", storyboard_out)
    wd.mark_done("storyboard")
    wd.write_checkpoint("timings", timings_out)
    wd.mark_done("timing")
    wd.write_checkpoint("script", script_out)
    wd.mark_done("scriptwriter")
    wd.write_checkpoint("slides", slides_out)
    wd.mark_done("slides")

    # Build the vision side_effect
    if fail_slide:
        verdicts = [
            SlideVerdict(slide_index=0, status="fail", issues=["Missing title"]),
            SlideVerdict(slide_index=1, status="fail", issues=["Wrong layout"]),
        ]
    else:
        verdicts = [
            SlideVerdict(slide_index=0, status="ok"),
            SlideVerdict(slide_index=1, status="ok"),
        ]

    call_count = [0]
    def _vision_side_effect(**kwargs):
        idx = call_count[0]
        call_count[0] += 1
        return verdicts[min(idx, len(verdicts) - 1)]

    return _vision_side_effect


def test_orch_level3_verify_fail_exits(tmp_path):
    """VERIFY-03 L3: run_pipeline with a fail verdict at level=3 raises typer.Exit(1)."""
    import typer as typer_module

    from avideo.orchestrator import run_pipeline

    config = _make_hybrid_config(tmp_path, level=3)
    vision_side_effect = _pre_populate_hybrid_workdir(tmp_path, config.workdir, fail_slide=True)
    mock_cs = _mock_call_structured_for_pipeline(tmp_path)
    mock_renderer_cls, _ = _mock_renderer_cls()

    with (
        patch("avideo.stages.storyboard.call_structured", mock_cs),
        patch("avideo.stages.scriptwriter.call_structured", mock_cs),
        patch("avideo.stages.slides_auto.call_structured", mock_cs),
        patch("avideo.stages.slides_auto.SlideRenderer", mock_renderer_cls),
        patch("avideo.stages.verify_slides.call_structured_with_images", side_effect=vision_side_effect),
        patch("avideo.stages.voice_elevenlabs.synthesize_slide", side_effect=_fake_synthesize_slide_factory()),
        patch("avideo.stages.assemble.run_ffmpeg", side_effect=_fake_run_ffmpeg_factory()),
        patch("avideo.stages.assemble.probe_duration", side_effect=_fake_probe_duration),
    ):
        with pytest.raises(typer_module.Exit) as exc_info:
            run_pipeline(config)

    assert exc_info.value.exit_code == 1, (
        f"Expected Exit(1) for L3 fail verdict, got exit_code={exc_info.value.exit_code}"
    )


def test_orch_level3_verify_ok_continues(tmp_path):
    """VERIFY-03 L3: run_pipeline with all-ok verdicts at level=3 continues to completion."""
    from avideo.orchestrator import run_pipeline
    from avideo.utils.workdir import WorkdirManager

    config = _make_hybrid_config(tmp_path, level=3)
    vision_side_effect = _pre_populate_hybrid_workdir(tmp_path, config.workdir, fail_slide=False)
    mock_cs = _mock_call_structured_for_pipeline(tmp_path)
    mock_renderer_cls, _ = _mock_renderer_cls()

    with (
        patch("avideo.stages.storyboard.call_structured", mock_cs),
        patch("avideo.stages.scriptwriter.call_structured", mock_cs),
        patch("avideo.stages.slides_auto.call_structured", mock_cs),
        patch("avideo.stages.slides_auto.SlideRenderer", mock_renderer_cls),
        patch("avideo.stages.verify_slides.call_structured_with_images", side_effect=vision_side_effect),
        patch("avideo.stages.voice_elevenlabs.synthesize_slide", side_effect=_fake_synthesize_slide_factory()),
        patch("avideo.stages.assemble.run_ffmpeg", side_effect=_fake_run_ffmpeg_factory()),
        patch("avideo.stages.assemble.probe_duration", side_effect=_fake_probe_duration),
    ):
        run_pipeline(config)  # Must NOT raise

    wd = WorkdirManager(config.workdir)
    assert wd.is_done("assemble"), "Pipeline must complete assembly when verify is all-ok at L3"


def test_orch_level4_verify_fail_exits(tmp_path):
    """VERIFY-03 L4: run_pipeline with a fail verdict at level=4 raises typer.Exit(1)."""
    import typer as typer_module

    from avideo.orchestrator import run_pipeline

    config = _make_hybrid_config(tmp_path, level=4)
    vision_side_effect = _pre_populate_hybrid_workdir(tmp_path, config.workdir, fail_slide=True)
    mock_cs = _mock_call_structured_for_pipeline(tmp_path)
    mock_renderer_cls, _ = _mock_renderer_cls()

    with (
        patch("avideo.stages.storyboard.call_structured", mock_cs),
        patch("avideo.stages.scriptwriter.call_structured", mock_cs),
        patch("avideo.stages.slides_auto.call_structured", mock_cs),
        patch("avideo.stages.slides_auto.SlideRenderer", mock_renderer_cls),
        patch("avideo.stages.verify_slides.call_structured_with_images", side_effect=vision_side_effect),
        patch("avideo.stages.voice_elevenlabs.synthesize_slide", side_effect=_fake_synthesize_slide_factory()),
        patch("avideo.stages.assemble.run_ffmpeg", side_effect=_fake_run_ffmpeg_factory()),
        patch("avideo.stages.assemble.probe_duration", side_effect=_fake_probe_duration),
    ):
        with pytest.raises(typer_module.Exit) as exc_info:
            run_pipeline(config)

    assert exc_info.value.exit_code == 1, (
        f"Expected Exit(1) for L4 fail verdict, got exit_code={exc_info.value.exit_code}"
    )


def test_orch_level4_verify_ok_continues(tmp_path):
    """VERIFY-03 L4: run_pipeline with all-ok verdicts at level=4 continues to completion."""
    from avideo.orchestrator import run_pipeline
    from avideo.utils.workdir import WorkdirManager

    config = _make_hybrid_config(tmp_path, level=4)
    vision_side_effect = _pre_populate_hybrid_workdir(tmp_path, config.workdir, fail_slide=False)
    mock_cs = _mock_call_structured_for_pipeline(tmp_path)
    mock_renderer_cls, _ = _mock_renderer_cls()

    with (
        patch("avideo.stages.storyboard.call_structured", mock_cs),
        patch("avideo.stages.scriptwriter.call_structured", mock_cs),
        patch("avideo.stages.slides_auto.call_structured", mock_cs),
        patch("avideo.stages.slides_auto.SlideRenderer", mock_renderer_cls),
        patch("avideo.stages.verify_slides.call_structured_with_images", side_effect=vision_side_effect),
        patch("avideo.stages.voice_elevenlabs.synthesize_slide", side_effect=_fake_synthesize_slide_factory()),
        patch("avideo.stages.assemble.run_ffmpeg", side_effect=_fake_run_ffmpeg_factory()),
        patch("avideo.stages.assemble.probe_duration", side_effect=_fake_probe_duration),
    ):
        run_pipeline(config)  # Must NOT raise

    wd = WorkdirManager(config.workdir)
    assert wd.is_done("assemble"), "Pipeline must complete assembly when verify is all-ok at L4"


def test_orch_level2_verify_pauses(tmp_path, monkeypatch):
    """VERIFY-03 L2: level=2 hybrid renders the verification report and pauses once for 'verify'."""
    import avideo.orchestrator as orch_module

    from avideo.orchestrator import run_pipeline

    mock_pause = MagicMock()
    monkeypatch.setattr(orch_module, "pause_for_approval", mock_pause)

    config = _make_hybrid_config(tmp_path, level=2)
    vision_side_effect = _pre_populate_hybrid_workdir(tmp_path, config.workdir, fail_slide=False)
    mock_cs = _mock_call_structured_for_pipeline(tmp_path)
    mock_renderer_cls, _ = _mock_renderer_cls()

    with (
        patch("avideo.stages.storyboard.call_structured", mock_cs),
        patch("avideo.stages.scriptwriter.call_structured", mock_cs),
        patch("avideo.stages.slides_auto.call_structured", mock_cs),
        patch("avideo.stages.slides_auto.SlideRenderer", mock_renderer_cls),
        patch("avideo.stages.verify_slides.call_structured_with_images", side_effect=vision_side_effect),
        patch("avideo.stages.voice_elevenlabs.synthesize_slide", side_effect=_fake_synthesize_slide_factory()),
        patch("avideo.stages.assemble.run_ffmpeg", side_effect=_fake_run_ffmpeg_factory()),
        patch("avideo.stages.assemble.probe_duration", side_effect=_fake_probe_duration),
    ):
        run_pipeline(config)

    # In hybrid mode, verify pre-run pause is suppressed; post-run iterate pause is called once.
    verify_pauses = [c for c in mock_pause.call_args_list if c.args[0] == "verify"]
    assert len(verify_pauses) == 1, (
        f"Expected exactly 1 pause call for 'verify', got {len(verify_pauses)}: {verify_pauses}"
    )
