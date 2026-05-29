"""RED tests for generate_bullets(), duration validation, and bullets.yaml serialization.

These tests FAIL with ImportError/ModuleNotFoundError until Plan 02 creates
src/avideo/stages/bullets_gen.py. They define the exact contracts that
generate_bullets(), validate_duration(), and the yaml round-trip must satisfy.

Coverage:
  TestGenerateBullets:
    - generate_bullets calls call_structured once and returns a list[str]
    - generate_bullets returns a list of strings (all elements non-empty)
    - The user prompt passed to call_structured contains the duration
    - No real network call is made when mock is in place

  TestBulletsYamlRoundTrip:
    - BulletsInput serialized via yaml.safe_dump round-trips back via load_bullets()
    - The format produced by the UI (title + bullets) is identical to what avideo
      generate --bullets consumes

  TestDurationValidation:
    - validate_duration(15) == 15 (minimum boundary)
    - validate_duration(1800) == 1800 (maximum boundary)
    - validate_duration(14) raises ValueError (below minimum)
    - validate_duration(1801) raises ValueError (above maximum)
    - validate_duration(120) == 120 (typical mid-range value)

All imports of avideo.stages.bullets_gen are DEFERRED inside test bodies
(same pattern as test_storyboard.py and test_bridge.py), so this file collects
cleanly even before bullets_gen.py exists.
"""
from __future__ import annotations

import types
from pathlib import Path

import pytest
import yaml


# ---------------------------------------------------------------------------
# Class 1: TestGenerateBullets
# ---------------------------------------------------------------------------


class TestGenerateBullets:
    """Tests for generate_bullets() with a mocked call_structured seam.

    The mock target is 'avideo.stages.bullets_gen.call_structured' — the
    import site inside the stage module, same pattern as test_storyboard.py.
    """

    def test_generate_bullets_calls_call_structured_once(self, mocker):
        """generate_bullets("My topic", 120, n=4) calls call_structured exactly once
        and returns the list from the mock result's .bullets attribute.
        """
        from avideo.stages.bullets_gen import generate_bullets  # noqa: PLC0415

        mock_result = types.SimpleNamespace(bullets=["A", "B", "C", "D"])
        mock_call = mocker.patch(
            "avideo.stages.bullets_gen.call_structured",
            return_value=mock_result,
        )

        result = generate_bullets("My topic", duration_seconds=120, n=4)

        assert mock_call.call_count == 1
        assert result == ["A", "B", "C", "D"]

    def test_generate_bullets_returns_list_of_strings(self, mocker):
        """generate_bullets() returns list[str] with all elements being non-empty
        strings when the mock returns a .bullets list of strings.
        """
        from avideo.stages.bullets_gen import generate_bullets  # noqa: PLC0415

        mock_result = types.SimpleNamespace(bullets=["X", "Y"])
        mocker.patch(
            "avideo.stages.bullets_gen.call_structured",
            return_value=mock_result,
        )

        result = generate_bullets("Any topic", duration_seconds=60, n=2)

        assert isinstance(result, list)
        assert all(isinstance(b, str) for b in result)

    def test_generate_bullets_default_n_from_duration(self, mocker):
        """generate_bullets with no explicit n passes the duration to call_structured.

        The user/system prompt passed to call_structured must contain the string
        representation of the duration so the LLM has the timing context.
        The mock is satisfied with any .bullets list to confirm the function returns.
        """
        from avideo.stages.bullets_gen import generate_bullets  # noqa: PLC0415

        # Default n for 60s is max(2, 60 // 30) = 2; mock returns 2 bullets
        mock_result = types.SimpleNamespace(bullets=["Alpha", "Beta"])
        mock_call = mocker.patch(
            "avideo.stages.bullets_gen.call_structured",
            return_value=mock_result,
        )

        result = generate_bullets("topic", duration_seconds=60)

        # call_structured was called at all
        assert mock_call.call_count == 1
        # Confirm the duration string appears in at least one of the call kwargs
        call_kwargs = mock_call.call_args.kwargs
        # The user prompt (or system prompt) should mention the duration
        prompts_text = " ".join(str(v) for v in call_kwargs.values())
        assert "60" in prompts_text, (
            f"Expected duration '60' to appear in call_structured prompts; got: {prompts_text!r}"
        )
        # The function returns a list
        assert isinstance(result, list)

    def test_generate_bullets_no_real_network_call(self, mocker):
        """With mock in place, generate_bullets returns without raising a network error.

        Verifies the mock seam is correctly placed at the import site so no real
        HTTP call is attempted.
        """
        from avideo.stages.bullets_gen import generate_bullets  # noqa: PLC0415

        mock_result = types.SimpleNamespace(bullets=["Only mocked"])
        mocker.patch(
            "avideo.stages.bullets_gen.call_structured",
            return_value=mock_result,
        )

        # If any real network call were made, this would raise due to missing API key
        result = generate_bullets("safe topic", duration_seconds=30, n=1)

        assert result == ["Only mocked"]


# ---------------------------------------------------------------------------
# Class 2: TestBulletsYamlRoundTrip
# ---------------------------------------------------------------------------


class TestBulletsYamlRoundTrip:
    """Tests for bullets.yaml serialization/deserialization round-trip.

    No mocking needed — these are pure data transformation tests that verify
    the YAML format the Contenido page produces is identical to what
    avideo generate --bullets consumes.
    """

    def test_bullets_yaml_serialization_round_trip(self, tmp_path: Path):
        """BulletsInput serialized via yaml.safe_dump round-trips back via load_bullets.

        Build BulletsInput → model_dump → yaml.safe_dump → write to file
        → load_bullets() → assert equality.
        """
        from avideo.models.bullets import BulletsInput  # noqa: PLC0415
        from avideo.utils.bullets import load_bullets  # noqa: PLC0415

        bi = BulletsInput(
            title="Test Title",
            bullets=["Bullet A", "Bullet B", "Bullet C"],
        )

        yaml_path = tmp_path / "bullets.yaml"
        yaml_path.write_text(
            yaml.safe_dump(bi.model_dump()),
            encoding="utf-8",
        )

        loaded = load_bullets(yaml_path)

        assert loaded.title == "Test Title"
        assert loaded.bullets == ["Bullet A", "Bullet B", "Bullet C"]

    def test_bullets_yaml_format_matches_engine_input(self, minimal_bullets: Path):
        """The bullets.yaml format matches what load_bullets() (the engine entry point)
        already consumes, confirming UI output == CLI input.

        Uses the minimal_bullets fixture from conftest (title="Test",
        bullets=["Point 1", "Point 2"]).
        """
        from avideo.utils.bullets import load_bullets  # noqa: PLC0415

        loaded = load_bullets(minimal_bullets)

        assert loaded.title == "Test"
        assert loaded.bullets == ["Point 1", "Point 2"]


# ---------------------------------------------------------------------------
# Class 3: TestDurationValidation
# ---------------------------------------------------------------------------


class TestDurationValidation:
    """Tests for validate_duration(seconds: int) -> int from bullets_gen.py.

    validate_duration enforces the bounds: minimum 15s, maximum 1800s.
    All imports are deferred so this file collects before bullets_gen.py exists.
    """

    def test_validate_duration_minimum_boundary(self):
        """validate_duration(15) returns 15 — the minimum allowed value (inclusive)."""
        from avideo.stages.bullets_gen import validate_duration  # noqa: PLC0415

        assert validate_duration(15) == 15

    def test_validate_duration_maximum_boundary(self):
        """validate_duration(1800) returns 1800 — the maximum allowed value (inclusive)."""
        from avideo.stages.bullets_gen import validate_duration  # noqa: PLC0415

        assert validate_duration(1800) == 1800

    def test_validate_duration_below_min_raises(self):
        """validate_duration(14) raises ValueError — one below the minimum."""
        from avideo.stages.bullets_gen import validate_duration  # noqa: PLC0415

        with pytest.raises(ValueError):
            validate_duration(14)

    def test_validate_duration_above_max_raises(self):
        """validate_duration(1801) raises ValueError — one above the maximum."""
        from avideo.stages.bullets_gen import validate_duration  # noqa: PLC0415

        with pytest.raises(ValueError):
            validate_duration(1801)

    def test_validate_duration_typical_value(self):
        """validate_duration(120) returns 120 — a typical 2-minute presentation value."""
        from avideo.stages.bullets_gen import validate_duration  # noqa: PLC0415

        assert validate_duration(120) == 120
