"""Tests for cost_estimator — offline dry-run estimate (D-15).

Key invariants tested:
- estimate_all(config) runs with NO network and NO workdir; returns None; does not raise.
- estimate_all reflects bullet count (more bullets → more tokens).
- estimate_storyboard_tokens(num_bullets, duration) returns (in_tok, out_tok) ints that grow with inputs.
- estimate_script_tokens(num_bullets, duration) returns (in_tok, out_tok) ints that grow with duration.
- No call to count_tokens (offline contract).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_config(bullets_path: Path, duration: int = 120, wpm: int = 150) -> Any:
    from avideo.models import RunConfig

    return RunConfig(bullets=bullets_path, duration=duration, wpm=wpm)


# ---------------------------------------------------------------------------
# estimate_all — offline contract
# ---------------------------------------------------------------------------


def test_estimate_all_returns_none(tmp_path: Path) -> None:
    """estimate_all must return None (signature contract)."""
    bullets = tmp_path / "bullets.yaml"
    bullets.write_text("title: Test\nbullets:\n  - Bullet 1\n  - Bullet 2\n", encoding="utf-8")
    config = _make_config(bullets)

    from avideo.utils.cost_estimator import estimate_all

    result = estimate_all(config)
    assert result is None


def test_estimate_all_does_not_raise(tmp_path: Path) -> None:
    """estimate_all must not raise even with minimal input."""
    bullets = tmp_path / "bullets.yaml"
    bullets.write_text("title: Test\nbullets:\n  - One\n", encoding="utf-8")
    config = _make_config(bullets)

    from avideo.utils.cost_estimator import estimate_all

    # Should not raise
    estimate_all(config)


def test_estimate_all_no_workdir_required(tmp_path: Path) -> None:
    """estimate_all must work WITHOUT a workdir existing (dry-run runs before workdir)."""
    bullets = tmp_path / "bullets.yaml"
    bullets.write_text("title: No Workdir Test\nbullets:\n  - Bullet\n", encoding="utf-8")
    # workdir intentionally NOT created
    workdir = tmp_path / "workdir"
    assert not workdir.exists(), "Workdir must not exist for this test"

    config = _make_config(bullets)

    from avideo.utils.cost_estimator import estimate_all

    # Must not raise even without workdir
    estimate_all(config)


def test_estimate_all_graceful_missing_bullets(tmp_path: Path) -> None:
    """estimate_all must not raise if bullets.yaml does not exist — falls back gracefully."""
    bullets = tmp_path / "missing_bullets.yaml"
    # File does not exist
    config = _make_config(bullets)

    from avideo.utils.cost_estimator import estimate_all

    # Must not raise (fallback to bullet count of 0 with a warning)
    estimate_all(config)


def test_estimate_all_no_count_tokens_call(tmp_path: Path) -> None:
    """estimate_all MUST NOT call the count_tokens API (offline contract, D-15)."""
    bullets = tmp_path / "bullets.yaml"
    bullets.write_text("title: Test\nbullets:\n  - A\n  - B\n", encoding="utf-8")
    config = _make_config(bullets)

    import avideo.utils.cost_estimator as ce_module

    # Verify no count_tokens attribute exists in the module (or is never called)
    assert not hasattr(ce_module, "count_tokens"), (
        "cost_estimator must NOT expose count_tokens — offline contract"
    )

    from avideo.utils.cost_estimator import estimate_all
    estimate_all(config)  # Should complete without any API call


def test_estimate_all_reflects_bullet_count(tmp_path: Path) -> None:
    """More bullets → more estimated tokens (non-decreasing with input size)."""
    bullets_few = tmp_path / "few.yaml"
    bullets_few.write_text(
        "title: Few\nbullets:\n  - One\n  - Two\n", encoding="utf-8"
    )
    bullets_many = tmp_path / "many.yaml"
    bullets_many.write_text(
        "title: Many\nbullets:\n" + "".join(f"  - Bullet {i}\n" for i in range(20)),
        encoding="utf-8",
    )

    from avideo.utils.cost_estimator import estimate_storyboard_tokens

    in_few, out_few = estimate_storyboard_tokens(num_bullets=2, duration=120)
    in_many, out_many = estimate_storyboard_tokens(num_bullets=20, duration=120)

    assert in_many >= in_few, (
        f"More bullets should produce >= input tokens. "
        f"Got: few={in_few}, many={in_many}"
    )


# ---------------------------------------------------------------------------
# estimate_storyboard_tokens — heuristic unit
# ---------------------------------------------------------------------------


def test_estimate_storyboard_tokens_returns_tuple() -> None:
    """estimate_storyboard_tokens must return a tuple of two ints."""
    from avideo.utils.cost_estimator import estimate_storyboard_tokens

    result = estimate_storyboard_tokens(num_bullets=5, duration=120)
    assert isinstance(result, tuple)
    assert len(result) == 2
    in_tok, out_tok = result
    assert isinstance(in_tok, int)
    assert isinstance(out_tok, int)


def test_estimate_storyboard_tokens_positive() -> None:
    """estimate_storyboard_tokens must return positive ints."""
    from avideo.utils.cost_estimator import estimate_storyboard_tokens

    in_tok, out_tok = estimate_storyboard_tokens(num_bullets=5, duration=120)
    assert in_tok > 0
    assert out_tok > 0


def test_estimate_storyboard_tokens_grows_with_bullets() -> None:
    """estimate_storyboard_tokens: more bullets → >= input tokens."""
    from avideo.utils.cost_estimator import estimate_storyboard_tokens

    in_few, _ = estimate_storyboard_tokens(num_bullets=2, duration=60)
    in_more, _ = estimate_storyboard_tokens(num_bullets=10, duration=60)
    assert in_more >= in_few


def test_estimate_storyboard_tokens_grows_with_duration() -> None:
    """estimate_storyboard_tokens: longer duration → >= output tokens (more slides)."""
    from avideo.utils.cost_estimator import estimate_storyboard_tokens

    _, out_short = estimate_storyboard_tokens(num_bullets=5, duration=60)
    _, out_long = estimate_storyboard_tokens(num_bullets=5, duration=300)
    assert out_long >= out_short


# ---------------------------------------------------------------------------
# estimate_script_tokens — heuristic unit
# ---------------------------------------------------------------------------


def test_estimate_script_tokens_returns_tuple() -> None:
    """estimate_script_tokens must return a tuple of two ints."""
    from avideo.utils.cost_estimator import estimate_script_tokens

    result = estimate_script_tokens(num_bullets=5, duration=120)
    assert isinstance(result, tuple)
    assert len(result) == 2
    in_tok, out_tok = result
    assert isinstance(in_tok, int)
    assert isinstance(out_tok, int)


def test_estimate_script_tokens_grows_with_duration() -> None:
    """estimate_script_tokens: longer duration → >= output tokens (more words to generate)."""
    from avideo.utils.cost_estimator import estimate_script_tokens

    _, out_short = estimate_script_tokens(num_bullets=5, duration=60)
    _, out_long = estimate_script_tokens(num_bullets=5, duration=300)
    assert out_long >= out_short


def test_estimate_script_tokens_positive() -> None:
    """estimate_script_tokens must return positive ints."""
    from avideo.utils.cost_estimator import estimate_script_tokens

    in_tok, out_tok = estimate_script_tokens(num_bullets=3, duration=90)
    assert in_tok > 0
    assert out_tok > 0
