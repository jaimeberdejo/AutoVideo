"""Wave 0 scaffold for voice-record mode tests.

Covers requirement VOICE-03:
  - VOICE-03: 'record' mode exports segmented script; autodetects slide_XX.wav if
    present; falls back to sounddevice recording if not present.

Real tests are filled in by plan 04-02 (stages/voice_record.py implementation).
"""
import pytest


@pytest.mark.skip(reason="Wave 0 scaffold — implemented in plan 04-02")
def test_placeholder_voice_record():
    """Placeholder: VOICE-03 — autodetect WAV vs sounddevice recording."""
    pass
