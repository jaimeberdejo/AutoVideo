"""Tests for SEED-002: steerable variation — feedback transport + prompt injection + dispatcher.

Test structure:
  - TestWorkdirFeedback        — Task 1: FeedbackCheckpoint + workdir helpers
  - TestStoryboardFeedbackPrompt  — Task 2: storyboard._build_prompts with feedback
  - TestScriptwriterFeedbackPrompt — Task 2: scriptwriter._build_prompts with feedback
  - TestSlidesAutoFeedbackPrompt  — Task 2: slides_auto.resolve_theme with feedback
  - TestFeedbackConsumedOnce      — Task 2: consumed-once lifecycle (scriptwriter)
  - TestRerunWithFeedback         — Task 3: pipeline_ops.rerun_with_feedback dispatcher
"""
from __future__ import annotations

from pathlib import Path

import pytest


# ===========================================================================
# Task 1: FeedbackCheckpoint model + workdir helpers
# ===========================================================================


class TestWorkdirFeedback:
    """Filesystem round-trip tests for write_feedback / read_feedback / clear_feedback."""

    def _make_wm(self, tmp_path: Path):
        """Helper: create a WorkdirManager rooted at tmp_path/workdir."""
        from avideo.utils.workdir import WorkdirManager

        return WorkdirManager(tmp_path / "workdir")

    # ------------------------------------------------------------------
    # write_feedback
    # ------------------------------------------------------------------

    def test_write_creates_feedback_json(self, tmp_path: Path) -> None:
        """write_feedback creates feedback.json in the workdir root."""
        wm = self._make_wm(tmp_path)
        wm.write_feedback("scriptwriter", "tono más cercano")

        feedback_path = wm.root / "feedback.json"
        assert feedback_path.exists(), "feedback.json must be created by write_feedback"

    def test_write_stores_text_under_stage_key(self, tmp_path: Path) -> None:
        """write_feedback stores the text keyed by stage name."""
        wm = self._make_wm(tmp_path)
        wm.write_feedback("scriptwriter", "tono más cercano")

        import json

        data = json.loads((wm.root / "feedback.json").read_text())
        assert data["entries"]["scriptwriter"] == "tono más cercano"

    def test_write_merges_multiple_stages(self, tmp_path: Path) -> None:
        """write_feedback on an existing file adds the new key without removing others."""
        wm = self._make_wm(tmp_path)
        wm.write_feedback("scriptwriter", "tono más cercano")
        wm.write_feedback("storyboard", "4 slides")

        import json

        data = json.loads((wm.root / "feedback.json").read_text())
        assert data["entries"]["scriptwriter"] == "tono más cercano"
        assert data["entries"]["storyboard"] == "4 slides"

    def test_write_overwrites_same_stage(self, tmp_path: Path) -> None:
        """write_feedback replaces an existing entry for the same stage."""
        wm = self._make_wm(tmp_path)
        wm.write_feedback("scriptwriter", "primero")
        wm.write_feedback("scriptwriter", "segundo")

        import json

        data = json.loads((wm.root / "feedback.json").read_text())
        assert data["entries"]["scriptwriter"] == "segundo"

    # ------------------------------------------------------------------
    # read_feedback
    # ------------------------------------------------------------------

    def test_read_returns_none_on_missing_file(self, tmp_path: Path) -> None:
        """read_feedback returns None when feedback.json does not exist."""
        wm = self._make_wm(tmp_path)
        assert wm.read_feedback("scriptwriter") is None

    def test_read_returns_text_after_write(self, tmp_path: Path) -> None:
        """read_feedback returns the stored text after write_feedback."""
        wm = self._make_wm(tmp_path)
        wm.write_feedback("scriptwriter", "tono más cercano")

        result = wm.read_feedback("scriptwriter")
        assert result == "tono más cercano"

    def test_read_returns_none_for_absent_stage_key(self, tmp_path: Path) -> None:
        """read_feedback returns None when the key is absent (file exists for other stage)."""
        wm = self._make_wm(tmp_path)
        wm.write_feedback("storyboard", "4 slides")

        assert wm.read_feedback("scriptwriter") is None

    # ------------------------------------------------------------------
    # clear_feedback
    # ------------------------------------------------------------------

    def test_clear_removes_stage_key(self, tmp_path: Path) -> None:
        """clear_feedback removes the specific stage key from feedback.json."""
        wm = self._make_wm(tmp_path)
        wm.write_feedback("scriptwriter", "tono")
        wm.write_feedback("storyboard", "4 slides")

        wm.clear_feedback("scriptwriter")

        assert wm.read_feedback("scriptwriter") is None
        # Other keys must survive
        assert wm.read_feedback("storyboard") == "4 slides"

    def test_clear_leaves_valid_json_after_removal(self, tmp_path: Path) -> None:
        """feedback.json remains valid JSON after clear_feedback removes a key."""
        wm = self._make_wm(tmp_path)
        wm.write_feedback("scriptwriter", "tono")
        wm.write_feedback("storyboard", "4 slides")

        wm.clear_feedback("scriptwriter")

        import json

        path = wm.root / "feedback.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert "scriptwriter" not in data["entries"]

    def test_clear_on_missing_file_is_silent_noop(self, tmp_path: Path) -> None:
        """clear_feedback on a missing feedback.json raises no exception."""
        wm = self._make_wm(tmp_path)
        # Must not raise
        wm.clear_feedback("scriptwriter")

    def test_clear_absent_key_is_silent_noop(self, tmp_path: Path) -> None:
        """clear_feedback on an absent stage key raises no exception."""
        wm = self._make_wm(tmp_path)
        wm.write_feedback("storyboard", "4 slides")

        # Should not raise even though 'slides' key is absent
        wm.clear_feedback("slides")
        assert wm.read_feedback("storyboard") == "4 slides"

    # ------------------------------------------------------------------
    # FeedbackCheckpoint model
    # ------------------------------------------------------------------

    def test_feedback_checkpoint_model_schema(self) -> None:
        """FeedbackCheckpoint is a pydantic BaseModel with entries: dict[str, str] = {}."""
        from avideo.models.feedback import FeedbackCheckpoint

        cp = FeedbackCheckpoint()
        assert cp.entries == {}

        cp2 = FeedbackCheckpoint(entries={"scriptwriter": "hello"})
        assert cp2.entries["scriptwriter"] == "hello"

    def test_feedback_checkpoint_serialization_round_trip(self) -> None:
        """FeedbackCheckpoint serializes and deserializes correctly."""
        from avideo.models.feedback import FeedbackCheckpoint

        original = FeedbackCheckpoint(entries={"scriptwriter": "tono", "storyboard": "4 slides"})
        json_str = original.model_dump_json()
        restored = FeedbackCheckpoint.model_validate_json(json_str)
        assert restored.entries == original.entries


# ===========================================================================
# Task 2: Stage prompt injection
# ===========================================================================


class TestStoryboardFeedbackPrompt:
    """_build_prompts in storyboard.py includes/excludes feedback block correctly."""

    def _make_storyboard_fixtures(self):
        """Return minimal fixtures needed to call storyboard._build_prompts."""
        from avideo.models.storyboard import StoryboardOutput, SlideSpec, VisualType

        sb = StoryboardOutput(
            slides=[
                SlideSpec(
                    title="Intro",
                    bullets=["Bienvenidos"],
                    visual_type=VisualType.TITLE,
                ),
            ],
            language="es",
        )
        return sb

    def test_no_feedback_block_when_feedback_is_none(self, tmp_path: Path) -> None:
        """_build_prompts with feedback=None does NOT include the feedback delimiter."""
        from avideo.stages.storyboard import _build_prompts
        from avideo.utils.bullets import BulletsInput

        bullets_input = BulletsInput(title="Demo", bullets=["Punto A"])
        _system, user = _build_prompts(
            bullets_input=bullets_input,
            context_text=None,
            title="Demo",
            duration=60,
            language="es",
            feedback=None,
        )
        assert "Instrucción del usuario" not in user

    def test_feedback_block_present_when_feedback_is_string(self, tmp_path: Path) -> None:
        """_build_prompts with feedback='cambia a 4 slides' includes the delimiter block."""
        from avideo.stages.storyboard import _build_prompts
        from avideo.utils.bullets import BulletsInput

        bullets_input = BulletsInput(title="Demo", bullets=["Punto A"])
        _system, user = _build_prompts(
            bullets_input=bullets_input,
            context_text=None,
            title="Demo",
            duration=60,
            language="es",
            feedback="cambia a 4 slides",
        )
        assert "Instrucción del usuario" in user
        assert "cambia a 4 slides" in user

    def test_feedback_block_present_with_context(self, tmp_path: Path) -> None:
        """_build_prompts includes feedback block even when context_text is also present."""
        from avideo.stages.storyboard import _build_prompts
        from avideo.utils.bullets import BulletsInput

        bullets_input = BulletsInput(title="Demo", bullets=["Punto A"])
        _system, user = _build_prompts(
            bullets_input=bullets_input,
            context_text="Contexto de referencia",
            title="Demo",
            duration=60,
            language="es",
            feedback="tono formal",
        )
        assert "Instrucción del usuario" in user
        assert "tono formal" in user


class TestScriptwriterFeedbackPrompt:
    """_build_prompts in scriptwriter.py includes/excludes feedback block correctly."""

    def _make_fixtures(self):
        from avideo.models.storyboard import StoryboardOutput, SlideSpec, VisualType
        from avideo.models.timing import TimingOutput, SlideTimingSpec

        sb = StoryboardOutput(
            slides=[
                SlideSpec(title="Intro", bullets=["Bienvenidos"], visual_type=VisualType.TITLE),
            ],
            language="es",
        )
        tm = TimingOutput(
            total_seconds=60.0,
            slides=[SlideTimingSpec(slide_index=0, duration_s=60.0, word_budget=100)],
        )
        return sb, tm

    def test_no_feedback_block_when_feedback_is_none(self) -> None:
        """scriptwriter._build_prompts with feedback=None omits the delimiter."""
        from avideo.stages.scriptwriter import _build_prompts

        sb, tm = self._make_fixtures()
        _system, user = _build_prompts(sb, tm, "es", feedback=None)
        assert "Instrucción del usuario" not in user

    def test_feedback_block_present_when_feedback_given(self) -> None:
        """scriptwriter._build_prompts with feedback includes the delimiter block."""
        from avideo.stages.scriptwriter import _build_prompts

        sb, tm = self._make_fixtures()
        _system, user = _build_prompts(sb, tm, "es", feedback="tono más cercano")
        assert "Instrucción del usuario" in user
        assert "tono más cercano" in user


class TestSlidesAutoFeedbackPrompt:
    """resolve_theme in slides_auto.py includes feedback in the user prompt when provided."""

    def test_no_feedback_block_when_feedback_is_none(self, tmp_path: Path, mocker) -> None:
        """resolve_theme with feedback=None does NOT include the feedback delimiter."""
        from avideo.models.storyboard import StoryboardOutput, SlideSpec, VisualType
        from avideo.stages.slides_auto import resolve_theme

        sb = StoryboardOutput(
            slides=[SlideSpec(title="Intro", bullets=["x"], visual_type=VisualType.TITLE)],
            language="es",
        )

        captured_kwargs = {}

        def fake_call_structured(**kwargs):
            captured_kwargs.update(kwargs)
            from avideo.models.theme import DEFAULT_THEME
            return DEFAULT_THEME

        mocker.patch("avideo.stages.slides_auto.call_structured", side_effect=fake_call_structured)

        theme_path = tmp_path / "theme.yaml"
        resolve_theme(theme_path, sb, feedback=None)
        assert "Instrucción del usuario" not in captured_kwargs.get("user", "")

    def test_feedback_block_present_when_feedback_given(self, tmp_path: Path, mocker) -> None:
        """resolve_theme with feedback='esquema azul' includes the delimiter block."""
        from avideo.models.storyboard import StoryboardOutput, SlideSpec, VisualType
        from avideo.stages.slides_auto import resolve_theme

        sb = StoryboardOutput(
            slides=[SlideSpec(title="Intro", bullets=["x"], visual_type=VisualType.TITLE)],
            language="es",
        )

        captured_kwargs = {}

        def fake_call_structured(**kwargs):
            captured_kwargs.update(kwargs)
            from avideo.models.theme import DEFAULT_THEME
            return DEFAULT_THEME

        mocker.patch("avideo.stages.slides_auto.call_structured", side_effect=fake_call_structured)

        theme_path = tmp_path / "theme.yaml"
        resolve_theme(theme_path, sb, feedback="esquema azul")
        assert "Instrucción del usuario" in captured_kwargs.get("user", "")
        assert "esquema azul" in captured_kwargs.get("user", "")


class TestFeedbackConsumedOnce:
    """Consumed-once lifecycle: stage clears its feedback after successful call_structured."""

    def test_scriptwriter_clears_feedback_after_run(self, tmp_path: Path, mocker) -> None:
        """ScriptwriterStage.run() clears scriptwriter feedback after first call_structured."""
        from avideo.models.script import ScriptOutput, SlideScript
        from avideo.models.storyboard import StoryboardOutput, SlideSpec, VisualType
        from avideo.models.timing import TimingOutput, SlideTimingSpec
        from avideo.stages.scriptwriter import ScriptwriterStage
        from avideo.utils.workdir import WorkdirManager

        # Build workdir with required checkpoints
        wm = WorkdirManager(tmp_path / "workdir")
        sb = StoryboardOutput(
            slides=[SlideSpec(title="Intro", bullets=["x"], visual_type=VisualType.TITLE)],
            language="es",
        )
        tm = TimingOutput(
            total_seconds=60.0,
            slides=[SlideTimingSpec(slide_index=0, duration_s=60.0, word_budget=50)],
        )
        wm.write_checkpoint("storyboard", sb)
        wm.write_checkpoint("timings", tm)

        # Write feedback before run
        wm.write_feedback("scriptwriter", "tono más cercano")

        # Mock call_structured to return a valid ScriptOutput
        fake_script = ScriptOutput(
            slides=[SlideScript(slide_index=0, narration="Esta es la narración.")],
            language="es",
        )
        mocker.patch("avideo.stages.scriptwriter.call_structured", return_value=fake_script)

        from avideo.models.config import RunConfig

        config = RunConfig(bullets=tmp_path / "bullets.yaml")
        (tmp_path / "bullets.yaml").write_text("title: Demo\nbullets:\n  - Punto A\n")

        stage = ScriptwriterStage()
        stage.run(wm, config)

        # Feedback must be cleared after successful run
        assert wm.read_feedback("scriptwriter") is None, (
            "scriptwriter feedback must be cleared after a successful run()"
        )

    def test_storyboard_clears_feedback_after_run(self, tmp_path: Path, mocker) -> None:
        """StoryboardStage.run() clears storyboard feedback after call_structured."""
        from avideo.models.storyboard import StoryboardOutput, SlideSpec, VisualType
        from avideo.stages.storyboard import StoryboardStage
        from avideo.utils.workdir import WorkdirManager

        wm = WorkdirManager(tmp_path / "workdir")

        # Write bullets.yaml
        bullets_path = tmp_path / "workdir" / "bullets.yaml"
        bullets_path.write_text("title: Demo\nbullets:\n  - Punto A\n")

        # Write feedback before run
        wm.write_feedback("storyboard", "cambia a 4 slides")

        fake_sb = StoryboardOutput(
            slides=[SlideSpec(title="Intro", bullets=["x"], visual_type=VisualType.TITLE)],
            language="es",
        )
        mocker.patch("avideo.stages.storyboard.call_structured", return_value=fake_sb)

        from avideo.models.config import RunConfig

        config = RunConfig(bullets=bullets_path)

        stage = StoryboardStage()
        stage.run(wm, config)

        assert wm.read_feedback("storyboard") is None, (
            "storyboard feedback must be cleared after a successful run()"
        )


# ===========================================================================
# Task 3: pipeline_ops.rerun_with_feedback dispatcher
# ===========================================================================


class TestRerunWithFeedback:
    """rerun_with_feedback routes correctly to the target stage and validates inputs."""

    def _make_wm(self, tmp_path: Path):
        from avideo.utils.workdir import WorkdirManager

        wm = WorkdirManager(tmp_path / "workdir")
        # Create a minimal done-marker so unlink() has something to test
        wm.done_marker("scriptwriter").touch()
        wm.done_marker("storyboard").touch()
        wm.done_marker("slides").touch()
        return wm

    def _make_config(self, tmp_path: Path):
        from avideo.models.config import RunConfig

        bp = tmp_path / "bullets.yaml"
        bp.write_text("title: Demo\nbullets:\n  - x\n")
        return RunConfig(bullets=bp)

    def test_scriptwriter_route_writes_feedback_and_runs_stage(
        self, tmp_path: Path, mocker
    ) -> None:
        """rerun_with_feedback('scriptwriter', ...) writes feedback, unlinks marker, runs stage."""
        from avideo.stages.scriptwriter import ScriptwriterStage
        from avideo.ui.pipeline_ops import rerun_with_feedback

        wm = self._make_wm(tmp_path)
        config = self._make_config(tmp_path)

        mock_run_stage = mocker.patch("avideo.ui.pipeline_ops.run_stage")
        mock_write = mocker.patch.object(wm, "write_feedback")
        mock_invalidate = mocker.patch.object(wm, "invalidate_downstream", return_value=[])

        rerun_with_feedback(wm, config, "scriptwriter", "tono más cercano")

        mock_write.assert_called_once_with("scriptwriter", "tono más cercano")
        mock_invalidate.assert_called_once_with("scriptwriter")
        assert not wm.done_marker("scriptwriter").exists(), "done-marker must be unlinked"
        assert mock_run_stage.call_count == 1
        stage_arg = mock_run_stage.call_args[0][0]
        assert isinstance(stage_arg, ScriptwriterStage)

    def test_storyboard_route_writes_feedback_and_runs_stage(
        self, tmp_path: Path, mocker
    ) -> None:
        """rerun_with_feedback('storyboard', ...) writes feedback, unlinks marker, runs StoryboardStage."""
        from avideo.stages.storyboard import StoryboardStage
        from avideo.ui.pipeline_ops import rerun_with_feedback

        wm = self._make_wm(tmp_path)
        config = self._make_config(tmp_path)

        mock_run_stage = mocker.patch("avideo.ui.pipeline_ops.run_stage")
        mock_write = mocker.patch.object(wm, "write_feedback")
        mock_invalidate = mocker.patch.object(wm, "invalidate_downstream", return_value=[])

        rerun_with_feedback(wm, config, "storyboard", "cambia a 4 slides")

        mock_write.assert_called_once_with("storyboard", "cambia a 4 slides")
        mock_invalidate.assert_called_once_with("storyboard")
        assert not wm.done_marker("storyboard").exists(), "storyboard done-marker must be unlinked"
        assert mock_run_stage.call_count == 1
        stage_arg = mock_run_stage.call_args[0][0]
        assert isinstance(stage_arg, StoryboardStage)

    def test_slides_route_writes_feedback_and_runs_stage(
        self, tmp_path: Path, mocker
    ) -> None:
        """rerun_with_feedback('slides', ...) writes feedback, unlinks marker, runs SlidesDispatchStage."""
        from avideo.stages.slides_dispatch import SlidesDispatchStage
        from avideo.ui.pipeline_ops import rerun_with_feedback

        wm = self._make_wm(tmp_path)
        config = self._make_config(tmp_path)

        mock_run_stage = mocker.patch("avideo.ui.pipeline_ops.run_stage")
        mock_write = mocker.patch.object(wm, "write_feedback")
        mock_invalidate = mocker.patch.object(wm, "invalidate_downstream", return_value=[])

        rerun_with_feedback(wm, config, "slides", "esquema azul")

        mock_write.assert_called_once_with("slides", "esquema azul")
        mock_invalidate.assert_called_once_with("slides")
        assert not wm.done_marker("slides").exists(), "slides done-marker must be unlinked"
        assert mock_run_stage.call_count == 1
        stage_arg = mock_run_stage.call_args[0][0]
        assert isinstance(stage_arg, SlidesDispatchStage)

    def test_unknown_stage_raises_value_error(self, tmp_path: Path, mocker) -> None:
        """rerun_with_feedback raises ValueError for an unknown stage name."""
        from avideo.ui.pipeline_ops import rerun_with_feedback

        wm = self._make_wm(tmp_path)
        config = self._make_config(tmp_path)

        mocker.patch("avideo.ui.pipeline_ops.run_stage")

        with pytest.raises(ValueError, match="Unknown feedback stage"):
            rerun_with_feedback(wm, config, "voice", "some feedback")

    def test_empty_feedback_skips_write_feedback(self, tmp_path: Path, mocker) -> None:
        """rerun_with_feedback with empty-string feedback does not call write_feedback."""
        from avideo.ui.pipeline_ops import rerun_with_feedback

        wm = self._make_wm(tmp_path)
        config = self._make_config(tmp_path)

        mocker.patch("avideo.ui.pipeline_ops.run_stage")
        mock_write = mocker.patch.object(wm, "write_feedback")
        mocker.patch.object(wm, "invalidate_downstream", return_value=[])

        rerun_with_feedback(wm, config, "scriptwriter", "")

        mock_write.assert_not_called()
