"""Tests for load_bullets() shared loader and BulletsInput model.

Covers:
- Happy path: minimal_bullets fixture round-trips correctly into BulletsInput.
- Missing 'bullets' key raises a clear ValidationError or ValueError.
"""
import pytest
from pathlib import Path


def test_load_bullets_happy_path(minimal_bullets: Path) -> None:
    """load_bullets returns BulletsInput(title="Test", bullets=["Point 1","Point 2"])."""
    from avideo.utils.bullets import load_bullets  # noqa: PLC0415
    from avideo.models.bullets import BulletsInput  # noqa: PLC0415

    result = load_bullets(minimal_bullets)
    assert isinstance(result, BulletsInput)
    assert result.title == "Test"
    assert result.bullets == ["Point 1", "Point 2"]


def test_load_bullets_missing_bullets_key_raises(tmp_path: Path) -> None:
    """YAML with no 'bullets' key raises ValidationError or ValueError."""
    from avideo.utils.bullets import load_bullets  # noqa: PLC0415

    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("title: Test\n", encoding="utf-8")

    with pytest.raises(Exception):  # ValidationError (pydantic) or ValueError
        load_bullets(bad_yaml)


def test_load_bullets_missing_title_key_raises(tmp_path: Path) -> None:
    """YAML with no 'title' key raises ValidationError or ValueError."""
    from avideo.utils.bullets import load_bullets  # noqa: PLC0415

    bad_yaml = tmp_path / "notitle.yaml"
    bad_yaml.write_text("bullets:\n  - Point 1\n", encoding="utf-8")

    with pytest.raises(Exception):  # ValidationError (pydantic) or ValueError
        load_bullets(bad_yaml)


def test_bullets_input_model_fields() -> None:
    """BulletsInput can be instantiated directly with title and bullets."""
    from avideo.models.bullets import BulletsInput  # noqa: PLC0415

    bi = BulletsInput(title="My Title", bullets=["A", "B", "C"])
    assert bi.title == "My Title"
    assert len(bi.bullets) == 3


def test_bullets_input_exported_from_models() -> None:
    """BulletsInput is accessible via the top-level avideo.models package."""
    from avideo.models import BulletsInput  # noqa: PLC0415

    assert BulletsInput is not None
