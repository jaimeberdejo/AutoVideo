"""Tests for avideo.integrations.anthropic — call_structured helper.

Uses a fully-faked Message-like object (no real API call, no ANTHROPIC_API_KEY
required). Tests verify:
  - call_structured extracts the tool_use block and returns a validated model.
  - call_structured raises RuntimeError when no matching tool_use block is present.

TEST-01 (deep integration path):
  Patch _get_client() to return a fake client whose .messages.create returns a
  fake Message with a tool_use block → verify Pydantic model is returned.
"""
from __future__ import annotations

import types
from typing import Any

import pytest
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Minimal Pydantic model for round-trip tests
# ---------------------------------------------------------------------------


class _SampleOutput(BaseModel):
    value: str
    count: int


# ---------------------------------------------------------------------------
# Helpers to build fake anthropic response objects
# ---------------------------------------------------------------------------


def _make_tool_use_block(name: str, input_: dict[str, Any]) -> types.SimpleNamespace:
    """Build a namespace that looks like an anthropic ToolUseBlock."""
    return types.SimpleNamespace(type="tool_use", name=name, input=input_)


def _make_text_block(text: str) -> types.SimpleNamespace:
    """Build a namespace that looks like an anthropic TextBlock."""
    return types.SimpleNamespace(type="text", text=text)


def _make_message(content: list) -> types.SimpleNamespace:
    """Build a namespace that looks like an anthropic Message."""
    return types.SimpleNamespace(content=content, stop_reason="tool_use")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCallStructured:
    """Tests for the call_structured() helper (TEST-01)."""

    def test_returns_validated_model_from_tool_use_block(self, mocker):
        """call_structured extracts the tool_use block and returns a Pydantic model."""
        from avideo.integrations.anthropic import call_structured

        input_data = {"value": "hello", "count": 42}
        fake_msg = _make_message([_make_tool_use_block("emit_test", input_data)])
        fake_client = mocker.MagicMock()
        fake_client.messages.create.return_value = fake_msg

        mocker.patch("avideo.integrations.anthropic._get_client", return_value=fake_client)

        result = call_structured(
            system="You are a test assistant.",
            user="Generate output.",
            tool_name="emit_test",
            tool_description="Emit test output.",
            output_model=_SampleOutput,
        )

        assert isinstance(result, _SampleOutput)
        assert result.value == "hello"
        assert result.count == 42

    def test_raises_runtime_error_when_no_tool_use_block(self, mocker):
        """call_structured raises RuntimeError if no matching tool_use block is present."""
        from avideo.integrations.anthropic import call_structured

        # Response contains only a text block — no tool_use
        fake_msg = _make_message([_make_text_block("I cannot call tools.")])
        fake_client = mocker.MagicMock()
        fake_client.messages.create.return_value = fake_msg

        mocker.patch("avideo.integrations.anthropic._get_client", return_value=fake_client)

        with pytest.raises(RuntimeError, match="emit_test"):
            call_structured(
                system="You are a test assistant.",
                user="Generate output.",
                tool_name="emit_test",
                tool_description="Emit test output.",
                output_model=_SampleOutput,
            )

    def test_raises_runtime_error_when_wrong_tool_name(self, mocker):
        """call_structured raises RuntimeError if the tool_use block has a different name."""
        from avideo.integrations.anthropic import call_structured

        # tool_use block with wrong tool name
        fake_msg = _make_message([_make_tool_use_block("other_tool", {"value": "x", "count": 1})])
        fake_client = mocker.MagicMock()
        fake_client.messages.create.return_value = fake_msg

        mocker.patch("avideo.integrations.anthropic._get_client", return_value=fake_client)

        with pytest.raises(RuntimeError, match="emit_test"):
            call_structured(
                system="You are a test assistant.",
                user="Generate output.",
                tool_name="emit_test",
                tool_description="Emit test output.",
                output_model=_SampleOutput,
            )

    def test_passes_correct_model_and_tool_choice_to_api(self, mocker):
        """call_structured sends forced tool_choice and correct tool schema to the API."""
        from avideo.integrations.anthropic import MODEL, call_structured

        input_data = {"value": "ok", "count": 1}
        fake_msg = _make_message([_make_tool_use_block("emit_test", input_data)])
        fake_client = mocker.MagicMock()
        fake_client.messages.create.return_value = fake_msg

        mocker.patch("avideo.integrations.anthropic._get_client", return_value=fake_client)

        call_structured(
            system="system",
            user="user",
            tool_name="emit_test",
            tool_description="Emit test output.",
            output_model=_SampleOutput,
        )

        call_kwargs = fake_client.messages.create.call_args.kwargs
        # Model must be the configured constant
        assert call_kwargs["model"] == MODEL
        # Tool choice must force the specific tool
        assert call_kwargs["tool_choice"] == {"type": "tool", "name": "emit_test"}
        # Tools list must contain the tool with the correct name
        assert any(t["name"] == "emit_test" for t in call_kwargs["tools"])

    def test_import_does_not_require_api_key(self):
        """Importing avideo.integrations.anthropic succeeds with no ANTHROPIC_API_KEY set."""
        import os
        orig = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            import importlib

            import avideo.integrations.anthropic as m  # noqa: F401
            importlib.reload(m)
            # If we get here, import succeeded without a key
        finally:
            if orig is not None:
                os.environ["ANTHROPIC_API_KEY"] = orig
