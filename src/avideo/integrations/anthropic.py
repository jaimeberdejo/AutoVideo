"""Centralized Anthropic client + generic forced-tool-use → Pydantic helper.

Design decisions implemented here:
- D-12: MODEL constant — single place to change the model ID.
- D-13: Lazy singleton client with max_retries=3. The SDK (anthropic>=0.104.1)
  already handles exponential backoff + jitter + Retry-After on 408/409/429/5xx.
  Do NOT hand-roll a 429/5xx retry loop on top.
- D-14: call_structured() — generic helper reused by storyboard and scriptwriter.
- D-14b: call_structured_with_images() — vision variant for VerifyStage (Phase 6).

Security:
- T-02-07: Client is lazy so importing this module NEVER requires ANTHROPIC_API_KEY.
  The SDK reads the key from the environment only when the first call is made.
  Never log or embed the key.
- T-06-03: media_type is read from MEDIA_TYPE constant (avideo.utils.image_utils)
  to prevent case-sensitive typos ("image/PNG" is rejected by the API).
"""
from __future__ import annotations

from pathlib import Path
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from avideo.utils.image_utils import MEDIA_TYPE, downscale_png_for_api

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Current model ID. Change here to update storyboard, scriptwriter, AND the
#: vision-based slide verifier (Phase 6) — all three route through call_structured
#: / call_structured_with_images in this module, which both read MODEL.
#: claude-haiku-4-5-20251001 supports vision, so the verifier's image calls work
#: unchanged. Chosen over claude-sonnet-4-6 for cost — none of these three tasks
#: (structured JSON generation, narration writing, ok/warning/fail slide QC)
#: need Sonnet-tier reasoning.
MODEL: str = "claude-haiku-4-5-20251001"

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


# ---------------------------------------------------------------------------
# Vision-capable structured-output helper (D-14b / VERIFY-01)
# ---------------------------------------------------------------------------


def call_structured_with_images(
    *,
    system: str,
    user: str,
    image_paths: list[Path],
    tool_name: str,
    tool_description: str,
    output_model: type[T],
    max_tokens: int = 4096,
) -> T:
    """Force Claude to emit JSON from a vision call, validated by Pydantic.

    Extends ``call_structured`` with image content blocks (base64-encoded PNGs).
    Images are placed BEFORE the text block in the content list, as required by
    the Anthropic API best practice ("images-before-text"). Each image is
    downscaled to ≤ 1568 px on the longest side via ``downscale_png_for_api``
    before base64 encoding (T-06-02 / Pitfall 2).

    Uses the same forced tool-use pattern as ``call_structured`` (D-03):
    ``tool_choice={"type":"tool","name":tool_name}`` guarantees Claude returns
    a single ``tool_use`` block whose ``input`` is validated by Pydantic.

    The ``media_type`` is read from the module-level ``MEDIA_TYPE`` constant
    ("image/png" lowercase) to prevent case-sensitive API rejections (T-06-03).

    Mock point: ``downscale_png_for_api`` is imported at module scope from
    ``avideo.utils.image_utils``. Tests patch
    ``avideo.integrations.anthropic.downscale_png_for_api`` to skip real
    file I/O and Pillow operations (Pitfall 6).

    Args:
        system: System prompt framing Claude's role and constraints.
        user: User-turn text instruction (appended AFTER all image blocks).
        image_paths: List of PNG file paths to include as base64 image content
            blocks. Each is downscaled to ≤ 1568 px before encoding.
        tool_name: Name of the forced tool (e.g. ``"emit_verdict"``).
        tool_description: Human-readable description of the tool's output.
        output_model: The Pydantic ``BaseModel`` subclass to validate against.
            ``model_json_schema()`` is called to derive ``input_schema``.
        max_tokens: Maximum tokens in the response (default 4096 — sufficient
            for a single-slide ``SlideVerdict`` JSON).

    Returns:
        A validated instance of ``output_model``.

    Raises:
        RuntimeError: If the response contains no ``tool_use`` block matching
            ``tool_name``. Surfaced by the orchestrator as a Rich error.
        ValueError: If any image exceeds 20 MB after downscale (T-06-02).
        anthropic.APIError: Propagated from the SDK on unrecoverable failures.

    Example::

        verdict = call_structured_with_images(
            system=_VERIFY_SYSTEM_PROMPT,
            user=user_prompt,
            image_paths=[Path("workdir/slides/slide_00.png")],
            tool_name="emit_verdict",
            tool_description="Emit a per-slide verification verdict.",
            output_model=SlideVerdict,
        )
    """
    schema = output_model.model_json_schema()

    # Build content list: images FIRST, then text (images-before-text best practice)
    content: list[dict] = []
    for path in image_paths:
        encoded = downscale_png_for_api(path)
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": MEDIA_TYPE,  # "image/png" (T-06-03)
                    "data": encoded,
                },
            }
        )
    content.append({"type": "text", "text": user})

    resp = _get_client().messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": content}],
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
            return output_model.model_validate(block.input)
    raise RuntimeError(
        f"Model did not return a tool_use block for {tool_name!r}. "
        f"stop_reason={getattr(resp, 'stop_reason', 'unknown')!r}. "
        "Check max_tokens and tool_choice forcing."
    )
