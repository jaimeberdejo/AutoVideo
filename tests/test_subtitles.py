"""Wave 0 scaffold for subtitle generation tests.

Covers requirements SUB-01 and SUB-02:
  - SUB-01: UnifiedTimings → SRT (HH:MM:SS,mmm) + VTT (WEBVTT + HH:MM:SS.mmm)
  - SUB-02: burn_subs flag registered; Phase 4 does NOT burn (leaves .srt/.vtt ready)

Real tests are filled in by plan 04-03 (stages/subtitles.py implementation).
"""
import pytest


@pytest.mark.skip(reason="Wave 0 scaffold — implemented in plan 04-03")
def test_placeholder_subtitles():
    """Placeholder: SUB-01 — UnifiedTimings → SRT/VTT generation."""
    pass
