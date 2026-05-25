"""Tests for StoryboardStage — STORY-01 / STORY-02.

All tests mock avideo.stages.storyboard.call_structured (the stage's import
site) so no real Anthropic API call or API key is needed.

Coverage:
  - StoryboardStage.run returns the fake StoryboardOutput returned by the mock.
  - The prompt passed to call_structured contains the real bullets from minimal_bullets.
  - config.language is honored on the returned StoryboardOutput.
  - visual_type values in the fake output are VisualType enum members (not raw strings).
  - stage_name is preserved as "storyboard" (matches the stub contract).
  - Works with and without a context checkpoint (CTX-02).
"""
from __future__ import annotations

import types
from pathlib import Path

import pytest

from avideo.models import SlideSpec, StoryboardOutput
from avideo.models.storyboard import VisualType
from avideo.utils.workdir import WorkdirManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_storyboard(language: str = "es") -> StoryboardOutput:
    """Build a minimal fake StoryboardOutput with a VisualType enum value."""
    return StoryboardOutput(
        slides=[
            SlideSpec(title="Slide A", bullets=["Point 1", "Point 2"], visual_type=VisualType.bullets)
        ],
        language=language,
    )


def _build_config(tmp_path: Path, bullets_path: Path, language: str = "es", duration: int = 60):
    """Build a minimal RunConfig for storyboard tests."""
    from avideo.models.config import RunConfig

    return RunConfig(
        bullets=bullets_path,
        duration=duration,
        language=language,
        # pydantic-settings will not look for config.yaml in tmp_path:
        # we rely on CLI kwargs (init_settings) taking priority.
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStoryboardStage:
    """Tests for StoryboardStage (STORY-01, STORY-02)."""

    def test_run_returns_storyboard_from_mock(self, mocker, tmp_workdir, minimal_bullets):
        """StoryboardStage.run returns the value returned by the mocked call_structured."""
        from avideo.stages.storyboard import StoryboardStage

        fake = _make_fake_storyboard()
        mocker.patch("avideo.stages.storyboard.call_structured", return_value=fake)

        stage = StoryboardStage()
        config = _build_config(tmp_workdir.parent, minimal_bullets)
        workdir = WorkdirManager(tmp_workdir)

        result = stage.run(workdir, config)

        assert result is fake
        assert isinstance(result, StoryboardOutput)

    def test_prompt_contains_bullet_text(self, mocker, tmp_workdir, minimal_bullets):
        """The user/system prompt passed to call_structured contains the real bullet text."""
        from avideo.stages.storyboard import StoryboardStage

        fake = _make_fake_storyboard()
        mock_cs = mocker.patch("avideo.stages.storyboard.call_structured", return_value=fake)

        stage = StoryboardStage()
        config = _build_config(tmp_workdir.parent, minimal_bullets)
        workdir = WorkdirManager(tmp_workdir)

        stage.run(workdir, config)

        assert mock_cs.called, "call_structured must be called"
        call_kwargs = mock_cs.call_args.kwargs
        # The 'user' prompt must contain the actual bullet text from minimal_bullets
        user_prompt = call_kwargs.get("user", "")
        assert "Point 1" in user_prompt, f"Expected 'Point 1' in prompt; got:\n{user_prompt}"
        assert "Point 2" in user_prompt, f"Expected 'Point 2' in prompt; got:\n{user_prompt}"

    def test_language_from_config_is_honored(self, mocker, tmp_workdir, minimal_bullets):
        """output.language matches config.language."""
        from avideo.stages.storyboard import StoryboardStage

        fake_en = _make_fake_storyboard(language="en")
        mocker.patch("avideo.stages.storyboard.call_structured", return_value=fake_en)

        stage = StoryboardStage()
        config = _build_config(tmp_workdir.parent, minimal_bullets, language="en")
        workdir = WorkdirManager(tmp_workdir)

        result = stage.run(workdir, config)

        assert result.language == "en"

    def test_visual_type_is_enum_member(self, mocker, tmp_workdir, minimal_bullets):
        """visual_type values in the output are VisualType enum members."""
        from avideo.stages.storyboard import StoryboardStage

        fake = _make_fake_storyboard()
        mocker.patch("avideo.stages.storyboard.call_structured", return_value=fake)

        stage = StoryboardStage()
        config = _build_config(tmp_workdir.parent, minimal_bullets)
        workdir = WorkdirManager(tmp_workdir)

        result = stage.run(workdir, config)

        for slide in result.slides:
            assert isinstance(slide.visual_type, VisualType), (
                f"Expected VisualType enum, got {type(slide.visual_type)}: {slide.visual_type}"
            )

    def test_stage_name_is_storyboard(self):
        """stage_name is 'storyboard' to preserve the stub contract."""
        from avideo.stages.storyboard import StoryboardStage

        assert StoryboardStage.stage_name == "storyboard"

    def test_checkpoint_name_is_storyboard(self):
        """checkpoint_name defaults to 'storyboard' (no override needed)."""
        from avideo.stages.storyboard import StoryboardStage

        stage = StoryboardStage()
        assert stage.checkpoint_name == "storyboard"

    def test_works_without_context_checkpoint(self, mocker, tmp_workdir, minimal_bullets):
        """StoryboardStage works when no context checkpoint exists (CTX-02)."""
        from avideo.stages.storyboard import StoryboardStage

        fake = _make_fake_storyboard()
        mocker.patch("avideo.stages.storyboard.call_structured", return_value=fake)

        stage = StoryboardStage()
        config = _build_config(tmp_workdir.parent, minimal_bullets)
        # No context.json written — workdir is fresh
        workdir = WorkdirManager(tmp_workdir)

        # Must not raise even without a context checkpoint
        result = stage.run(workdir, config)
        assert isinstance(result, StoryboardOutput)

    def test_works_with_context_checkpoint(self, mocker, tmp_workdir, minimal_bullets):
        """StoryboardStage includes context text in the prompt when checkpoint exists."""
        from avideo.models.context import ContextOutput
        from avideo.stages.storyboard import StoryboardStage

        fake = _make_fake_storyboard()
        mock_cs = mocker.patch("avideo.stages.storyboard.call_structured", return_value=fake)

        stage = StoryboardStage()
        config = _build_config(tmp_workdir.parent, minimal_bullets)
        workdir = WorkdirManager(tmp_workdir)

        # Write a context checkpoint with known text
        ctx = ContextOutput(used=True, text="Referencia de contexto para la presentación.")
        workdir.write_checkpoint("context", ctx)

        stage.run(workdir, config)

        call_kwargs = mock_cs.call_args.kwargs
        user_prompt = call_kwargs.get("user", "")
        # The context text must appear somewhere in the prompt
        assert "Referencia de contexto" in user_prompt, (
            f"Expected context text in prompt; got:\n{user_prompt}"
        )

    def test_duration_appears_in_prompt(self, mocker, tmp_workdir, minimal_bullets):
        """The target duration is included in the prompt passed to call_structured."""
        from avideo.stages.storyboard import StoryboardStage

        fake = _make_fake_storyboard()
        mock_cs = mocker.patch("avideo.stages.storyboard.call_structured", return_value=fake)

        stage = StoryboardStage()
        config = _build_config(tmp_workdir.parent, minimal_bullets, duration=120)
        workdir = WorkdirManager(tmp_workdir)

        stage.run(workdir, config)

        call_kwargs = mock_cs.call_args.kwargs
        # Duration should appear in either system or user prompt
        full_prompt = call_kwargs.get("system", "") + call_kwargs.get("user", "")
        assert "120" in full_prompt, f"Expected duration '120' in prompt; got:\n{full_prompt}"
