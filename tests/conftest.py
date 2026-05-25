"""Shared pytest fixtures for avideo test suite."""
import pytest
from pathlib import Path


@pytest.fixture
def tmp_workdir(tmp_path: Path) -> Path:
    """Return a workdir path inside tmp_path (not yet created)."""
    return tmp_path / "workdir"


@pytest.fixture
def minimal_bullets(tmp_path: Path) -> Path:
    """Write a minimal bullets.yaml and return its Path."""
    bullets = tmp_path / "bullets.yaml"
    bullets.write_text(
        "title: Test\nbullets:\n  - Point 1\n  - Point 2\n",
        encoding="utf-8",
    )
    return bullets


@pytest.fixture
def minimal_config(tmp_path: Path) -> Path:
    """Write a minimal config.yaml and return its Path."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "voice: elevenlabs\nslides_mode: auto\nlevel: 4\nwpm: 150\n",
        encoding="utf-8",
    )
    return cfg
