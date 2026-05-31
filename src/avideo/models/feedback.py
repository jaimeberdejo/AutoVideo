"""FeedbackCheckpoint — ephemeral per-stage user feedback transport model.

Lifecycle:
  - Written by pipeline_ops.rerun_with_feedback before invalidating done-markers.
  - Read by each stage at the start of run().
  - Cleared by each stage after a successful call_structured call (consumed-once).

The file lives at workdir/feedback.json alongside other checkpoint files.
It is never written by the CLI pipeline — only by the Streamlit UI — so
feedback=None is always the default for all stages (100% backward compatible).
"""
from __future__ import annotations

from pydantic import BaseModel


class FeedbackCheckpoint(BaseModel):
    """Keyed by stage name. Entries are ephemeral: cleared by each stage after use.

    Example::

        {
          "entries": {
            "scriptwriter": "tono más cercano",
            "storyboard": "cambia el número de slides a 4"
          }
        }
    """

    entries: dict[str, str] = {}
