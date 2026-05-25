"""Tests for SlidesAutoStage — SLIDE-01, SLIDE-02, SLIDE-03.

All tests mock:
  avideo.stages.slides_auto.SlideRenderer  — so no Chromium launches in unit tests
  avideo.stages.slides_auto.call_structured — so no API key needed

The fake_storyboard fixture (conftest.py) provides 7 VisualType slides.

Coverage:
  - test_stage_contract: stage_name == "slides" and checkpoint_name == "slides".
  - test_renders_all_slides: run() over fake_storyboard writes/returns one png_path per slide.
  - test_theme_idempotent: when theme.yaml already exists, call_structured is NOT called.
  - test_theme_generated: when theme.yaml is absent, call_structured IS called and theme.yaml is written.
  - test_theme_fallback_on_error: when call_structured raises, falls back to DEFAULT_THEME.
  - test_all_visual_types_render: all 7 visual_types render without KeyError.
  - test_offline_only: rendered HTML contains inline SVG and no external URL.
  - test_lucide_offline: icon() helper returns SVG string for known Lucide name (no network).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, call

import pytest
import yaml

from avideo.models.storyboard import StoryboardOutput, SlideSpec, VisualType
from avideo.models.theme import ThemeConfig, DEFAULT_THEME
from avideo.utils.workdir import WorkdirManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_config(tmp_path: Path, bullets_path: Path | None = None) -> Any:
    """Build a minimal RunConfig for slides_auto tests."""
    from avideo.models.config import RunConfig

    if bullets_path is None:
        bullets_path = tmp_path / "bullets.yaml"
        bullets_path.write_text(
            "title: Test\nbullets:\n  - Point 1\n  - Point 2\n", encoding="utf-8"
        )
    return RunConfig(bullets=bullets_path, duration=120)


def _mock_renderer_class():
    """Return a MagicMock that stands in for SlideRenderer (context manager)."""
    mock_instance = MagicMock()
    mock_instance.__enter__ = MagicMock(return_value=mock_instance)
    mock_instance.__exit__ = MagicMock(return_value=False)
    mock_instance.render_to_png = MagicMock()

    mock_class = MagicMock(return_value=mock_instance)
    return mock_class, mock_instance


# ---------------------------------------------------------------------------
# Test: stage contract
# ---------------------------------------------------------------------------


class TestStageContract:
    """Verify stage_name and checkpoint_name meet the pipeline contract (D-10)."""

    def test_stage_name(self) -> None:
        """SlidesAutoStage.stage_name must be 'slides'."""
        from avideo.stages.slides_auto import SlidesAutoStage

        stage = SlidesAutoStage()
        assert stage.stage_name == "slides", (
            f"Expected stage_name='slides', got {stage.stage_name!r}"
        )

    def test_checkpoint_name(self) -> None:
        """SlidesAutoStage.checkpoint_name must default to 'slides'."""
        from avideo.stages.slides_auto import SlidesAutoStage

        stage = SlidesAutoStage()
        assert stage.checkpoint_name == "slides", (
            f"Expected checkpoint_name='slides', got {stage.checkpoint_name!r}"
        )


# ---------------------------------------------------------------------------
# Test: renders all slides
# ---------------------------------------------------------------------------


class TestRendersAllSlides:
    """run() produces one png_path per slide in workdir/slides/."""

    def test_renders_all_slides(
        self, tmp_path: Path, fake_storyboard: StoryboardOutput
    ) -> None:
        """run() returns SlidesOutput with one png_path per slide (mode='auto')."""
        from avideo.stages.slides_auto import SlidesAutoStage
        from avideo.models.slides import SlidesOutput

        workdir = WorkdirManager(tmp_path / "workdir")
        workdir.write_checkpoint("storyboard", fake_storyboard)

        config = _build_config(tmp_path)
        theme_path = tmp_path / "theme.yaml"
        # Pre-write theme.yaml to avoid API call
        theme_path.write_text(yaml.safe_dump(DEFAULT_THEME.model_dump()), encoding="utf-8")

        mock_cls, mock_inst = _mock_renderer_class()

        with patch("avideo.stages.slides_auto.SlideRenderer", mock_cls):
            stage = SlidesAutoStage(theme_path=theme_path)
            result = stage.run(workdir, config)

        assert isinstance(result, SlidesOutput)
        assert result.mode == "auto"
        num_slides = len(fake_storyboard.slides)
        assert len(result.png_paths) == num_slides, (
            f"Expected {num_slides} png_paths, got {len(result.png_paths)}"
        )

    def test_png_paths_under_workdir_slides(
        self, tmp_path: Path, fake_storyboard: StoryboardOutput
    ) -> None:
        """png_paths must be under workdir/slides/ and named slide_XX.png."""
        from avideo.stages.slides_auto import SlidesAutoStage

        workdir = WorkdirManager(tmp_path / "workdir")
        workdir.write_checkpoint("storyboard", fake_storyboard)

        config = _build_config(tmp_path)
        theme_path = tmp_path / "theme.yaml"
        theme_path.write_text(yaml.safe_dump(DEFAULT_THEME.model_dump()), encoding="utf-8")

        mock_cls, mock_inst = _mock_renderer_class()

        with patch("avideo.stages.slides_auto.SlideRenderer", mock_cls):
            stage = SlidesAutoStage(theme_path=theme_path)
            result = stage.run(workdir, config)

        slides_dir = tmp_path / "workdir" / "slides"
        for i, png_path in enumerate(result.png_paths):
            p = Path(png_path)
            assert p.parent == slides_dir, f"Expected parent {slides_dir}, got {p.parent}"
            expected_name = f"slide_{i:02d}.png"
            assert p.name == expected_name, f"Expected {expected_name}, got {p.name}"

    def test_render_to_png_called_per_slide(
        self, tmp_path: Path, fake_storyboard: StoryboardOutput
    ) -> None:
        """render_to_png must be called once per slide."""
        from avideo.stages.slides_auto import SlidesAutoStage

        workdir = WorkdirManager(tmp_path / "workdir")
        workdir.write_checkpoint("storyboard", fake_storyboard)

        config = _build_config(tmp_path)
        theme_path = tmp_path / "theme.yaml"
        theme_path.write_text(yaml.safe_dump(DEFAULT_THEME.model_dump()), encoding="utf-8")

        mock_cls, mock_inst = _mock_renderer_class()

        with patch("avideo.stages.slides_auto.SlideRenderer", mock_cls):
            stage = SlidesAutoStage(theme_path=theme_path)
            stage.run(workdir, config)

        assert mock_inst.render_to_png.call_count == len(fake_storyboard.slides)

    def test_does_not_write_checkpoint(
        self, tmp_path: Path, fake_storyboard: StoryboardOutput
    ) -> None:
        """Stage must NOT write checkpoint or done-marker (orchestrator's responsibility)."""
        from avideo.stages.slides_auto import SlidesAutoStage

        workdir = WorkdirManager(tmp_path / "workdir")
        workdir.write_checkpoint("storyboard", fake_storyboard)

        config = _build_config(tmp_path)
        theme_path = tmp_path / "theme.yaml"
        theme_path.write_text(yaml.safe_dump(DEFAULT_THEME.model_dump()), encoding="utf-8")

        mock_cls, _ = _mock_renderer_class()

        with patch("avideo.stages.slides_auto.SlideRenderer", mock_cls):
            stage = SlidesAutoStage(theme_path=theme_path)
            stage.run(workdir, config)

        assert not workdir.checkpoint_path("slides").exists(), (
            "Stage must NOT write slides.json — that is the orchestrator's job"
        )
        assert not workdir.is_done("slides"), (
            "Stage must NOT mark_done — that is the orchestrator's job"
        )


# ---------------------------------------------------------------------------
# Test: theme idempotency
# ---------------------------------------------------------------------------


class TestThemeIdempotent:
    """When theme.yaml already exists, call_structured must NOT be called (D-03)."""

    def test_theme_idempotent(self, tmp_path: Path, fake_storyboard: StoryboardOutput) -> None:
        """Existing theme.yaml is loaded; call_structured is not called."""
        from avideo.stages.slides_auto import SlidesAutoStage

        workdir = WorkdirManager(tmp_path / "workdir")
        workdir.write_checkpoint("storyboard", fake_storyboard)
        config = _build_config(tmp_path)

        # Pre-write a custom theme.yaml
        custom_theme = ThemeConfig(base_font_px=40)
        theme_path = tmp_path / "theme.yaml"
        theme_path.write_text(yaml.safe_dump(custom_theme.model_dump()), encoding="utf-8")

        mock_cls, _ = _mock_renderer_class()

        with patch("avideo.stages.slides_auto.SlideRenderer", mock_cls), \
             patch("avideo.stages.slides_auto.call_structured") as mock_cs:
            stage = SlidesAutoStage(theme_path=theme_path)
            stage.run(workdir, config)

        mock_cs.assert_not_called()

    def test_existing_theme_values_loaded(
        self, tmp_path: Path, fake_storyboard: StoryboardOutput
    ) -> None:
        """When theme.yaml exists, the loaded ThemeConfig reflects its values."""
        from avideo.stages.slides_auto import SlidesAutoStage

        workdir = WorkdirManager(tmp_path / "workdir")
        workdir.write_checkpoint("storyboard", fake_storyboard)
        config = _build_config(tmp_path)

        # Write theme with distinctive color
        custom_theme = ThemeConfig()
        custom_theme.palette.primary = "#abcdef"
        theme_path = tmp_path / "theme.yaml"
        theme_path.write_text(yaml.safe_dump(custom_theme.model_dump()), encoding="utf-8")

        captured_html = []
        mock_cls, mock_inst = _mock_renderer_class()
        mock_inst.render_to_png.side_effect = lambda html, out: captured_html.append(html)

        with patch("avideo.stages.slides_auto.SlideRenderer", mock_cls), \
             patch("avideo.stages.slides_auto.call_structured") as mock_cs:
            stage = SlidesAutoStage(theme_path=theme_path)
            stage.run(workdir, config)

        mock_cs.assert_not_called()
        # The theme color should appear in rendered HTML
        assert any("#abcdef" in html for html in captured_html), (
            "Loaded theme palette.primary '#abcdef' should appear in rendered HTML"
        )


# ---------------------------------------------------------------------------
# Test: theme generation when absent
# ---------------------------------------------------------------------------


class TestThemeGenerated:
    """When theme.yaml is absent, call_structured is called once and theme.yaml is written."""

    def test_theme_generated_when_absent(
        self, tmp_path: Path, fake_storyboard: StoryboardOutput
    ) -> None:
        """call_structured is called once when theme.yaml does not exist (D-01)."""
        from avideo.stages.slides_auto import SlidesAutoStage

        workdir = WorkdirManager(tmp_path / "workdir")
        workdir.write_checkpoint("storyboard", fake_storyboard)
        config = _build_config(tmp_path)

        theme_path = tmp_path / "theme.yaml"
        assert not theme_path.exists()

        mock_cls, _ = _mock_renderer_class()
        fake_theme = ThemeConfig()

        with patch("avideo.stages.slides_auto.SlideRenderer", mock_cls), \
             patch("avideo.stages.slides_auto.call_structured", return_value=fake_theme) as mock_cs:
            stage = SlidesAutoStage(theme_path=theme_path)
            stage.run(workdir, config)

        mock_cs.assert_called_once()
        call_kwargs = mock_cs.call_args
        # Ensure tool_name is "emit_theme"
        assert call_kwargs.kwargs.get("tool_name") == "emit_theme", (
            f"Expected tool_name='emit_theme', got {call_kwargs.kwargs.get('tool_name')!r}"
        )

    def test_theme_yaml_written_after_generation(
        self, tmp_path: Path, fake_storyboard: StoryboardOutput
    ) -> None:
        """After AI generation, theme.yaml is written to disk (idempotency for next run)."""
        from avideo.stages.slides_auto import SlidesAutoStage

        workdir = WorkdirManager(tmp_path / "workdir")
        workdir.write_checkpoint("storyboard", fake_storyboard)
        config = _build_config(tmp_path)

        theme_path = tmp_path / "theme.yaml"
        assert not theme_path.exists()

        mock_cls, _ = _mock_renderer_class()
        fake_theme = ThemeConfig()

        with patch("avideo.stages.slides_auto.SlideRenderer", mock_cls), \
             patch("avideo.stages.slides_auto.call_structured", return_value=fake_theme):
            stage = SlidesAutoStage(theme_path=theme_path)
            stage.run(workdir, config)

        assert theme_path.exists(), "theme.yaml must be written after AI generation"
        loaded = ThemeConfig.model_validate(yaml.safe_load(theme_path.read_text(encoding="utf-8")))
        assert loaded == fake_theme


# ---------------------------------------------------------------------------
# Test: theme fallback on error
# ---------------------------------------------------------------------------


class TestThemeFallback:
    """When call_structured raises, run() falls back to DEFAULT_THEME and still renders."""

    def test_theme_fallback_on_api_error(
        self, tmp_path: Path, fake_storyboard: StoryboardOutput
    ) -> None:
        """call_structured raising → run() falls back to DEFAULT_THEME, no exception (D-01)."""
        from avideo.stages.slides_auto import SlidesAutoStage
        from avideo.models.slides import SlidesOutput

        workdir = WorkdirManager(tmp_path / "workdir")
        workdir.write_checkpoint("storyboard", fake_storyboard)
        config = _build_config(tmp_path)

        theme_path = tmp_path / "theme.yaml"  # Does not exist → triggers AI call
        assert not theme_path.exists()

        mock_cls, _ = _mock_renderer_class()

        with patch("avideo.stages.slides_auto.SlideRenderer", mock_cls), \
             patch("avideo.stages.slides_auto.call_structured", side_effect=RuntimeError("API error")):
            stage = SlidesAutoStage(theme_path=theme_path)
            result = stage.run(workdir, config)  # Must NOT raise

        assert isinstance(result, SlidesOutput)
        assert len(result.png_paths) == len(fake_storyboard.slides)

    def test_fallback_uses_default_theme_colors(
        self, tmp_path: Path, fake_storyboard: StoryboardOutput
    ) -> None:
        """On API error, rendered HTML uses DEFAULT_THEME colors."""
        from avideo.stages.slides_auto import SlidesAutoStage

        workdir = WorkdirManager(tmp_path / "workdir")
        workdir.write_checkpoint("storyboard", fake_storyboard)
        config = _build_config(tmp_path)

        theme_path = tmp_path / "theme.yaml"
        captured_html = []
        mock_cls, mock_inst = _mock_renderer_class()
        mock_inst.render_to_png.side_effect = lambda html, out: captured_html.append(html)

        with patch("avideo.stages.slides_auto.SlideRenderer", mock_cls), \
             patch("avideo.stages.slides_auto.call_structured", side_effect=RuntimeError("fail")):
            stage = SlidesAutoStage(theme_path=theme_path)
            stage.run(workdir, config)

        # DEFAULT_THEME primary color should appear in HTML
        assert any(DEFAULT_THEME.palette.primary in html for html in captured_html), (
            f"DEFAULT_THEME.palette.primary={DEFAULT_THEME.palette.primary!r} "
            "should appear in rendered HTML on fallback"
        )


# ---------------------------------------------------------------------------
# Test: all visual_types render
# ---------------------------------------------------------------------------


class TestAllVisualTypesRender:
    """All 7 visual_types render without KeyError; unknown type falls back to bullets."""

    def test_all_visual_types_render_without_error(
        self, tmp_path: Path, fake_storyboard: StoryboardOutput
    ) -> None:
        """All 7 VisualType values render without KeyError (SLIDE-02, Pitfall 5)."""
        from avideo.stages.slides_auto import SlidesAutoStage

        assert {s.visual_type for s in fake_storyboard.slides} == set(VisualType), (
            "fake_storyboard must cover all 7 VisualType values"
        )

        workdir = WorkdirManager(tmp_path / "workdir")
        workdir.write_checkpoint("storyboard", fake_storyboard)
        config = _build_config(tmp_path)
        theme_path = tmp_path / "theme.yaml"
        theme_path.write_text(yaml.safe_dump(DEFAULT_THEME.model_dump()), encoding="utf-8")

        mock_cls, mock_inst = _mock_renderer_class()
        rendered_htmls = []
        mock_inst.render_to_png.side_effect = lambda html, out: rendered_htmls.append(html)

        with patch("avideo.stages.slides_auto.SlideRenderer", mock_cls):
            stage = SlidesAutoStage(theme_path=theme_path)
            # Must not raise — any KeyError would propagate
            stage.run(workdir, config)

        assert len(rendered_htmls) == 7

    def test_unknown_visual_type_falls_back_to_bullets(
        self, tmp_path: Path
    ) -> None:
        """A slide with an unknown (legacy) visual_type falls back to bullets_slide macro."""
        from avideo.stages.slides_auto import SlidesAutoStage

        # Build a storyboard with a single slide using a VisualType.bullets (normal),
        # but inject an unknown visual_type value at dict/JSON level
        storyboard = StoryboardOutput(
            slides=[
                SlideSpec(title="Legacy Slide", bullets=["text"], visual_type=VisualType.bullets)
            ],
            language="es",
        )
        # Manually monkey-patch visual_type.value to simulate an unknown string
        storyboard.slides[0].__dict__["visual_type"] = type(
            "FakeVT", (), {"value": "unknown_legacy_type"}
        )()

        workdir = WorkdirManager(tmp_path / "workdir")
        workdir.write_checkpoint("storyboard", storyboard)
        config = _build_config(tmp_path)
        theme_path = tmp_path / "theme.yaml"
        theme_path.write_text(yaml.safe_dump(DEFAULT_THEME.model_dump()), encoding="utf-8")

        mock_cls, mock_inst = _mock_renderer_class()
        rendered_htmls = []
        mock_inst.render_to_png.side_effect = lambda html, out: rendered_htmls.append(html)

        with patch("avideo.stages.slides_auto.SlideRenderer", mock_cls):
            stage = SlidesAutoStage(theme_path=theme_path)
            # Must not raise KeyError
            stage.run(workdir, config)

        assert len(rendered_htmls) == 1
        # Fallback renders bullet-like content (title in HTML)
        assert "Legacy Slide" in rendered_htmls[0]


# ---------------------------------------------------------------------------
# Test: offline-only (SLIDE-02)
# ---------------------------------------------------------------------------


class TestOfflineOnly:
    """Rendered HTML must use only inline SVG — no external URLs (SLIDE-02, D-08)."""

    def test_html_contains_inline_svg(
        self, tmp_path: Path, fake_storyboard: StoryboardOutput
    ) -> None:
        """At least one slide's HTML must contain an inline <svg element (Lucide icons)."""
        from avideo.stages.slides_auto import SlidesAutoStage

        workdir = WorkdirManager(tmp_path / "workdir")
        workdir.write_checkpoint("storyboard", fake_storyboard)
        config = _build_config(tmp_path)
        theme_path = tmp_path / "theme.yaml"
        theme_path.write_text(yaml.safe_dump(DEFAULT_THEME.model_dump()), encoding="utf-8")

        mock_cls, mock_inst = _mock_renderer_class()
        rendered_htmls = []
        mock_inst.render_to_png.side_effect = lambda html, out: rendered_htmls.append(html)

        with patch("avideo.stages.slides_auto.SlideRenderer", mock_cls):
            stage = SlidesAutoStage(theme_path=theme_path)
            stage.run(workdir, config)

        # At least one rendered slide must have an inline SVG
        assert any("<svg" in html for html in rendered_htmls), (
            "Expected at least one rendered slide HTML to contain an inline <svg element"
        )

    def test_html_has_no_external_http_url(
        self, tmp_path: Path, fake_storyboard: StoryboardOutput
    ) -> None:
        """No rendered HTML must contain an external http/https URL (D-08, T-03-06)."""
        from avideo.stages.slides_auto import SlidesAutoStage

        workdir = WorkdirManager(tmp_path / "workdir")
        workdir.write_checkpoint("storyboard", fake_storyboard)
        config = _build_config(tmp_path)
        theme_path = tmp_path / "theme.yaml"
        theme_path.write_text(yaml.safe_dump(DEFAULT_THEME.model_dump()), encoding="utf-8")

        mock_cls, mock_inst = _mock_renderer_class()
        rendered_htmls = []
        mock_inst.render_to_png.side_effect = lambda html, out: rendered_htmls.append(html)

        with patch("avideo.stages.slides_auto.SlideRenderer", mock_cls):
            stage = SlidesAutoStage(theme_path=theme_path)
            stage.run(workdir, config)

        # No external URL references allowed in rendered HTML
        external_url_pattern = re.compile(r'<img[^>]+src=["\']https?://', re.IGNORECASE)
        css_url_pattern = re.compile(r'url\(https?://', re.IGNORECASE)
        for html in rendered_htmls:
            assert not external_url_pattern.search(html), (
                "Rendered HTML contains an <img src=http...> — violates D-08 offline constraint"
            )
            assert not css_url_pattern.search(html), (
                "Rendered HTML contains a CSS url(http...) — violates D-08 offline constraint"
            )


# ---------------------------------------------------------------------------
# Test: lucide offline (SLIDE-02)
# ---------------------------------------------------------------------------


class TestLucideOffline:
    """icon() helper returns inline SVG without any network call (SLIDE-02, D-07)."""

    def test_lucide_offline_returns_svg(self) -> None:
        """icon('chart-bar') returns a non-empty SVG string (no mock — pure offline)."""
        from lucide import lucide_icon

        def icon(name: str, size: int = 48, stroke: str = "currentColor") -> str:
            return lucide_icon(name, width=size, height=size, stroke=stroke)

        svg = icon("chart-bar")
        assert isinstance(svg, str), "icon() must return a string"
        assert "<svg" in svg, f"Expected SVG in output, got: {svg[:200]!r}"
        assert "http://" not in svg and "https://" not in svg, (
            "SVG output must not contain any external URL"
        )

    def test_lucide_offline_multiple_icons(self) -> None:
        """Several common Lucide icon names return valid SVG strings without network."""
        from lucide import lucide_icon

        test_icons = ["zap", "star", "check", "arrow-right", "play"]
        for name in test_icons:
            svg = lucide_icon(name, width=24, height=24)
            assert "<svg" in svg, f"icon({name!r}) did not return SVG: {svg[:100]!r}"
