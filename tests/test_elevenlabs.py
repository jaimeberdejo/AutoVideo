"""Wave 0 scaffold for ElevenLabs integration tests.

Covers requirement VOICE-02:
  - VOICE-02: Validate character timestamps are strictly increasing; retry ≤3;
    raise VoiceTimestampError with a clear message if all retries fail.

Real tests are filled in by Task 3 of plan 04-01 (integrations/elevenlabs.py).
"""
import pytest


@pytest.mark.skip(reason="Wave 0 scaffold — implemented in Task 3 of 04-01")
def test_placeholder_elevenlabs():
    """Placeholder: VOICE-02 — strictly-increasing timestamp validation + retry."""
    pass
