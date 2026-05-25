"""Wave 0 scaffold for alignment stage tests.

Covers requirements ALIGN-01 and ALIGN-02:
  - ALIGN-01: 'record' mode — WhisperX aligns audio → word_segments → UnifiedTimings
  - ALIGN-02: 'elevenlabs' mode — align stage is a no-op (timings already in UnifiedTimings)

Real tests are filled in by plan 04-02 (stages/align.py + integrations/whisperx.py).
"""
import pytest


@pytest.mark.skip(reason="Wave 0 scaffold — implemented in plan 04-02")
def test_placeholder_align():
    """Placeholder: ALIGN-01/ALIGN-02 — whisperx align + elevenlabs skip."""
    pass
