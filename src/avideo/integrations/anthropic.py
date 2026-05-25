"""Centralized Anthropic client + generic forced-tool-use → Pydantic helper.

Design decisions implemented here:
- D-12: MODEL constant — single place to change the model ID.
- D-13: Lazy singleton client with max_retries=3. The SDK (anthropic>=0.104.1)
  already handles exponential backoff + jitter + Retry-After on 408/409/429/5xx.
  Do NOT hand-roll a 429/5xx retry loop on top.
- D-14: call_structured() — generic helper reused by storyboard and scriptwriter.

Security:
- T-02-07: Client is lazy so importing this module NEVER requires ANTHROPIC_API_KEY.
  The SDK reads the key from the environment only when the first call is made.
  Never log or embed the key.
"""
from __future__ import annotations

from typing import TypeVar

import anthropic
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Current model ID. Change here to update both storyboard and scriptwriter.
#: VERIFIED against platform.claude.com 2026-05-25: claude-sonnet-4-6 is the
#: pinned dateless snapshot ($3/$15 per MTok, 1M ctx, 64k output).
#: Do NOT use claude-sonnet-4-20250514 — deprecated, retires 2026-06-15.
MODEL: str = "claude-sonnet-4-6"

# ---------------------------------------------------------------------------
# Generic type variable for the output model
# ---------------------------------------------------------------------------

T = TypeVar("T", bound=BaseModel)

# ---------------------------------------------------------------------------
# Lazy client singleton (D-13 / T-02-07)
# ---------------------------------------------------------------------------

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    """Return the lazily-instantiated Anthropic client.

    The client is created on first call, then cached.  Importing this module
    does NOT instantiate the client and therefore does NOT require
    ANTHROPIC_API_KEY to be set — keeping --dry-run and tests import-safe.

    The SDK handles exponential backoff + jitter + Retry-After on network
    errors (408/409/429/5xx) via ``max_retries=3``.  Do NOT add a custom
    retry loop on top.

    Returns:
        A shared ``anthropic.Anthropic`` instance.
    """
    global _client
    if _client is None:
        _client = anthropic.Anthropic(max_retries=3)
    return _client


# ---------------------------------------------------------------------------
# Generic structured-output helper (D-14)
# ---------------------------------------------------------------------------


def call_structured(
    *,
    system: str,
    user: str,
    tool_name: str,
    tool_description: str,
    output_model: type[T],
    max_tokens: int = 8192,
) -> T:
    """Force Claude to emit JSON conforming to ``output_model``, validated by Pydantic.

    Uses forced tool-use (D-03): ``tool_choice={"type":"tool","name":tool_name}``
    guarantees Claude returns a single ``tool_use`` block whose ``input`` is a
    parsed dict — no fragile text-block JSON parsing needed.

    The ``input_schema`` is derived from ``output_model.model_json_schema()``
    (Pydantic v2 draft-2020-12), which the Anthropic API accepts directly.

    Args:
        system: System prompt framing Claude's role and constraints.
        user: User-turn message containing the input data (bullets, duration, etc.).
        tool_name: Name of the forced tool (e.g. ``"emit_storyboard"``).
        tool_description: Human-readable description of what the tool should emit.
        output_model: The Pydantic ``BaseModel`` subclass to validate against.
            ``model_json_schema()`` is called to derive ``input_schema``.
        max_tokens: Maximum tokens in the response (default 8192 — ample for
            storyboard; scale up for scriptwriter if needed).

    Returns:
        A validated instance of ``output_model``.

    Raises:
        RuntimeError: If the response contains no ``tool_use`` block matching
            ``tool_name``.  This is surfaced by the orchestrator as a Rich error.
        anthropic.APIError: Propagated from the SDK on unrecoverable API failures
            after max_retries exhausted.
    """
    schema = output_model.model_json_schema()
    resp = _get_client().messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        tools=[
            {
                "name": tool_name,
                "description": tool_description,
                "input_schema": schema,
            }
        ],
        tool_choice={"type": "tool", "name": tool_name},  # D-03: forced tool-use
    )
    for block in resp.content:
        if block.type == "tool_use" and block.name == tool_name:
            # block.input is already a parsed dict — do NOT json.loads a text block
            return output_model.model_validate(block.input)
    raise RuntimeError(
        f"Model did not return a tool_use block for {tool_name!r}. "
        f"stop_reason={getattr(resp, 'stop_reason', 'unknown')!r}. "
        "Check max_tokens (Pitfall 7) and tool_choice forcing."
    )
