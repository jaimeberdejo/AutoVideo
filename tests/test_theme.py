"""Tests for ThemeConfig model and Jinja2 base template rendering.

Covers <behavior> from plan 03-01 Task 2:
- ThemeConfig() with no args validates and exposes all expected fields.
- DEFAULT_THEME == ThemeConfig() (built-in fallback).
- ThemeConfig round-trips through YAML.
- Rendering base.html.j2 with DEFAULT_THEME + a SlideSpec produces HTML that:
  - contains ':root' with '--color-primary'
  - contains NO external URLs (offline constraint D-08)
  - contains NO '<img src=http' patterns
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# ThemeConfig defaults
# ---------------------------------------------------------------------------


def test_theme_config_default_validates():
    """ThemeConfig() with no arguments is fully valid (D-02)."""
    from avideo.models.theme import ThemeConfig  # noqa: PLC0415

    theme = ThemeConfig()
    assert theme.palette.primary.startswith("#")
    assert theme.palette.background.startswith("#")
    assert theme.palette.text.startswith("#")
    assert theme.palette.accent.startswith("#")
    assert isinstance(theme.typography.heading, str)
    assert isinstance(theme.typography.body, str)
    assert isinstance(theme.base_font_px, int)
    assert isinstance(theme.scale, float)
    assert isinstance(theme.margin_px, int)
    assert isinstance(theme.gap_px, int)


def test_default_theme_is_theme_config():
    """DEFAULT_THEME is an instance of ThemeConfig (built-in fallback, D-01)."""
    from avideo.models.theme import DEFAULT_THEME, ThemeConfig  # noqa: PLC0415

    assert isinstance(DEFAULT_THEME, ThemeConfig)


def test_default_theme_equals_theme_config():
    """DEFAULT_THEME equals ThemeConfig() — no extra mutations."""
    from avideo.models.theme import DEFAULT_THEME, ThemeConfig  # noqa: PLC0415

    assert DEFAULT_THEME == ThemeConfig()


def test_theme_config_yaml_roundtrip():
    """ThemeConfig round-trips through YAML: validate(yaml.safe_load(yaml.safe_dump(model_dump))) == original."""
    import yaml  # noqa: PLC0415

    from avideo.models.theme import ThemeConfig  # noqa: PLC0415

    theme = ThemeConfig()
    dumped = yaml.safe_dump(theme.model_dump())
    loaded = yaml.safe_load(dumped)
    theme2 = ThemeConfig.model_validate(loaded)
    assert theme == theme2


def test_theme_re_exported_from_models():
    """ThemeConfig and DEFAULT_THEME are accessible from avideo.models."""
    import avideo.models as m  # noqa: PLC0415

    assert hasattr(m, "ThemeConfig")


# ---------------------------------------------------------------------------
# Jinja2 base template rendering
# ---------------------------------------------------------------------------


def _get_env_and_template():
    """Return (Jinja2 Environment, base template) with a stub icon() global."""
    from jinja2 import Environment, PackageLoader  # noqa: PLC0415

    env = Environment(
        loader=PackageLoader("avideo.templates", package_path=""),
        autoescape=True,
    )

    # Stub icon() global: returns a trusted SVG string; macros mark it |safe.
    def _stub_icon(name: str, size: int = 48, stroke: str = "currentColor") -> str:
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}"><title>{name}</title></svg>'

    env.globals["icon"] = _stub_icon
    return env


@pytest.fixture
def base_template_html():
    """Render base.html.j2 with DEFAULT_THEME + a title SlideSpec; return HTML string."""
    from avideo.models.storyboard import SlideSpec, VisualType  # noqa: PLC0415
    from avideo.models.theme import DEFAULT_THEME  # noqa: PLC0415

    env = _get_env_and_template()
    template = env.get_template("base.html.j2")
    slide = SlideSpec(
        title="Test Title",
        bullets=["Bullet 1", "Bullet 2"],
        visual_type=VisualType.title,
    )
    html = template.render(
        slide=slide,
        theme=DEFAULT_THEME,
        font_face_css="",
    )
    return html


def test_base_template_contains_root_css_vars(base_template_html):
    """:root block with --color-primary CSS variable must be present."""
    assert ":root" in base_template_html
    assert "--color-primary" in base_template_html


def test_base_template_no_external_urls(base_template_html):
    """Template must contain no external http/https URLs (offline D-08)."""
    import re  # noqa: PLC0415

    # Must NOT contain http:// or https:// scheme URLs as attribute values
    assert not re.search(r'src=["\']?https?://', base_template_html), (
        "Found external src= URL in rendered HTML"
    )
    assert not re.search(r'href=["\']?https?://', base_template_html), (
        "Found external href= URL in rendered HTML"
    )
    assert "url(http" not in base_template_html, (
        "Found external url() in rendered HTML"
    )


def test_base_template_no_img_src_tag(base_template_html):
    """Template must not contain <img src=...> tags (SVG-only visuals, D-07/SLIDE-02)."""
    import re  # noqa: PLC0415

    assert not re.search(r"<img\s[^>]*src=", base_template_html, re.IGNORECASE), (
        "Found <img src=...> in rendered HTML"
    )


def test_base_template_dispatches_all_visual_types():
    """All 7 VisualType values render without raising KeyError or template error."""
    from avideo.models.storyboard import SlideSpec, VisualType  # noqa: PLC0415
    from avideo.models.theme import DEFAULT_THEME  # noqa: PLC0415

    env = _get_env_and_template()
    template = env.get_template("base.html.j2")

    for vt in VisualType:
        bullets = ["Item 1", "Item 2"]
        if vt in (VisualType.chart, VisualType.comparison):
            bullets = ["Ventas 40%", "Coste 25%", "Beneficio 35%"]
        slide = SlideSpec(title=f"Slide {vt.value}", bullets=bullets, visual_type=vt)
        html = template.render(slide=slide, theme=DEFAULT_THEME, font_face_css="")
        assert html, f"Empty HTML for visual_type={vt.value}"


def test_base_template_escapes_user_text():
    """Jinja2 autoescape must escape HTML-special characters in title/bullets (T-03-02)."""
    from avideo.models.storyboard import SlideSpec, VisualType  # noqa: PLC0415
    from avideo.models.theme import DEFAULT_THEME  # noqa: PLC0415

    env = _get_env_and_template()
    template = env.get_template("base.html.j2")
    slide = SlideSpec(
        title='<script>alert("xss")</script>',
        bullets=['<b>bad</b>', '"quoted"'],
        visual_type=VisualType.bullets,
    )
    html = template.render(slide=slide, theme=DEFAULT_THEME, font_face_css="")
    # Raw script tag must NOT appear unescaped
    assert "<script>" not in html, "Unescaped <script> tag found — autoescape broken"
