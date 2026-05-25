"""Tests for integrations/whisperx.py — import-safety + align_wav contract.

Covers the lazy-import guarantee (D-06): importing ``avideo.integrations.whisperx``
must NOT fail even when whisperx/torch are not installed (record extra absent).

The actual align_wav behaviour (mocked whisperx calls) is tested more thoroughly
in test_align.py (Task 3) where AlignStage exercises align_wav end-to-end.
"""
import sys
import types
import pytest


# ---------------------------------------------------------------------------
# Task 1 RED: import-safety + align_wav contract
# ---------------------------------------------------------------------------


def test_module_imports_without_whisperx():
    """Importing avideo.integrations.whisperx must NOT fail without whisperx installed.

    D-06: lazy import inside the function body — top-level module import is clean.
    """
    # Force-reload to ensure we are not relying on a cached import
    import importlib
    import avideo.integrations.whisperx as wmod
    importlib.reload(wmod)
    assert callable(wmod.align_wav), "align_wav must be a callable"


def test_align_wav_function_exists():
    """align_wav must be exported from the module."""
    from avideo.integrations.whisperx import align_wav
    assert callable(align_wav)


def test_word_segments_to_words_helper_exists():
    """word_segments_to_words (helper) must exist for use by align.py."""
    from avideo.integrations import whisperx as wmod
    assert hasattr(wmod, "word_segments_to_words"), (
        "word_segments_to_words helper expected for converting word_segments → WordTiming list"
    )


def test_word_segments_to_words_converts_correctly():
    """word_segments_to_words should convert raw word_segment dicts to WordTiming list."""
    from avideo.integrations.whisperx import word_segments_to_words
    from avideo.models.timings import WordTiming

    segs = [
        {"word": "hola", "start": 0.0, "end": 0.4},
        {"word": "mundo", "start": 0.5, "end": 0.9},
    ]
    result = word_segments_to_words(segs)
    assert len(result) == 2
    assert all(isinstance(w, WordTiming) for w in result)
    assert result[0].text == "hola"
    assert result[0].start == 0.0
    assert result[0].end == 0.4
    assert result[1].text == "mundo"
    assert result[1].start == 0.5
    assert result[1].end == 0.9


def test_align_wav_raises_import_error_without_whisperx(monkeypatch):
    """align_wav must raise ImportError with clear message when whisperx not installed."""
    # Temporarily simulate whisperx as unavailable
    import builtins
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "whisperx":
            raise ImportError("No module named 'whisperx'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    # Also remove whisperx from sys.modules if present
    whisperx_mod = sys.modules.pop("whisperx", None)
    try:
        from avideo.integrations.whisperx import align_wav
        with pytest.raises(ImportError, match="record"):
            align_wav("dummy.wav")
    finally:
        if whisperx_mod is not None:
            sys.modules["whisperx"] = whisperx_mod


def test_align_wav_with_mocked_whisperx():
    """align_wav should call load_model/transcribe/load_align_model/align and return word_segments."""
    import sys
    import types

    # Build a mock whisperx module
    mock_whisperx = types.ModuleType("whisperx")

    fake_word_segs = [
        {"word": "hola", "start": 0.0, "end": 0.4},
        {"word": "mundo", "start": 0.5, "end": 0.9},
    ]

    fake_model = types.SimpleNamespace(
        transcribe=lambda audio, batch_size=16: {"segments": [{"text": "hola mundo"}]}
    )
    fake_align_model = types.SimpleNamespace()
    fake_metadata = {}
    fake_audio = object()

    mock_whisperx.load_model = lambda size, device, compute_type=None, language=None: fake_model
    mock_whisperx.load_audio = lambda path: fake_audio
    mock_whisperx.load_align_model = lambda language_code=None, device=None: (fake_align_model, fake_metadata)
    mock_whisperx.align = lambda segs, model_a, metadata, audio, device, return_char_alignments=False: {
        "word_segments": fake_word_segs
    }

    # Inject mock into sys.modules so the lazy import inside align_wav picks it up
    sys.modules["whisperx"] = mock_whisperx
    try:
        import importlib
        import avideo.integrations.whisperx as wmod
        importlib.reload(wmod)

        result = wmod.align_wav("fake.wav", language="es", model_size="small")
        assert result == fake_word_segs
    finally:
        del sys.modules["whisperx"]
