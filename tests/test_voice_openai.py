"""Tests for VoiceOpenAIStage and VoiceStage openai dispatch (Phase 8, VOZ-02).

Wave 0 scaffold — tests are RED until Wave 1+2 implementation plans land:
  - avideo.integrations.openai (synthesize_slide_openai, transcribe_slide_openai,
    _get_client) — does not yet exist
  - avideo.stages.voice_openai (VoiceOpenAIStage) — does not yet exist
  - avideo.models.config.VoiceMode.openai — does not yet exist

Mock points:
  - avideo.integrations.openai._get_client (lazy client singleton; patch to inject
    a fake OpenAI client without OPENAI_API_KEY in the environment)
  - avideo.stages.voice_openai.synthesize_slide_openai (module-scope import)
  - avideo.stages.voice_openai.transcribe_slide_openai (module-scope import)

These tests turn GREEN when the Wave 1 (config model) + Wave 2 (openai integration
+ voice_openai stage) plans are executed.

Covers VOZ-02:
  - VoiceOpenAIStage.run reads script.json checkpoint, calls synthesize_slide_openai
    once per slide, calls transcribe_slide_openai once per slide, and returns
    UnifiedTimings(source="openai")
  - 4096-char per-request limit enforced in synthesize_slide_openai
  - Lazy client: importing avideo.integrations.openai does NOT instantiate the client
  - Module-scope imports: synthesize_slide_openai and transcribe_slide_openai imported
    at module scope in voice_openai.py so tests can patch the stage-level names
  - VoiceStage dispatcher routes voice=openai to VoiceOpenAIStage
"""
from __future__ import annotations

import types
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_script(workdir_manager, slides):
    """Write a minimal script.json checkpoint to workdir."""
    from avideo.models.script import ScriptOutput, SlideScript  # noqa: PLC0415

    script = ScriptOutput(
        slides=[SlideScript(slide_index=i, narration=n) for i, n in enumerate(slides)],
        language="es",
    )
    workdir_manager.write_checkpoint("script", script)


def _make_fake_synthesize(tmp_path):
    """Return a side_effect callable for mocking synthesize_slide_openai.

    Writes 4 dummy MP3 bytes to out_path and returns None.
    (synthesis writes to disk; the stage reads disk; no return value used for synthesis)
    """

    def _fake(*, text, slide_index, model, voice, out_path, **kwargs):
        Path(out_path).write_bytes(b"\xff\xe3\x10\x00")  # minimal fake mp3 bytes
        return None  # synthesize_slide_openai writes to disk; Stage reads disk

    return _fake


def _make_fake_transcribe(slide_index):
    """Return a SlideTimings-like value for transcribe_slide_openai return_value."""
    from avideo.models.timings import SlideTimings, WordTiming  # noqa: PLC0415

    return SlideTimings(
        slide_index=slide_index,
        audio_path=f"audio/slide_{slide_index:02d}.mp3",
        duration=2.0,
        words=[WordTiming(text="test", start=0.0, end=0.5)],
    )


# ---------------------------------------------------------------------------
# VoiceOpenAIStage
# ---------------------------------------------------------------------------


class TestVoiceOpenAIStage:
    """VoiceOpenAIStage produces UnifiedTimings(source="openai")."""

    def test_run_returns_unified_timings(self, tmp_path, mocker):
        """VoiceOpenAIStage.run returns UnifiedTimings(source="openai") for 2 slides."""
        from avideo.models.config import RunConfig, VoiceMode  # noqa: PLC0415
        from avideo.models.timings import UnifiedTimings  # noqa: PLC0415
        from avideo.stages.voice_openai import VoiceOpenAIStage  # noqa: PLC0415
        from avideo.utils.workdir import WorkdirManager  # noqa: PLC0415

        wm = WorkdirManager(tmp_path / "workdir")
        _write_script(wm, ["Primera narración.", "Segunda narración."])

        mocker.patch(
            "avideo.stages.voice_openai.synthesize_slide_openai",
            side_effect=_make_fake_synthesize(tmp_path),
        )
        slide_timings_side_effect = [
            _make_fake_transcribe(0),
            _make_fake_transcribe(1),
        ]
        mocker.patch(
            "avideo.stages.voice_openai.transcribe_slide_openai",
            side_effect=slide_timings_side_effect,
        )

        bullets = tmp_path / "b.yaml"
        bullets.write_text("title: T\nbullets:\n  - x\n", encoding="utf-8")
        config = RunConfig(bullets=bullets, duration=60, voice=VoiceMode.openai)

        result = VoiceOpenAIStage().run(wm, config)

        assert isinstance(result, UnifiedTimings)
        assert result.source == "openai"
        assert len(result.slides) == 2

    def test_voice_stage_dispatches_openai(self, tmp_path, mocker):
        """VoiceStage dispatches to openai branch when config.voice == VoiceMode.openai."""
        from avideo.models.config import RunConfig, VoiceMode  # noqa: PLC0415
        from avideo.models.timings import UnifiedTimings  # noqa: PLC0415
        from avideo.stages.voice import VoiceStage  # noqa: PLC0415
        from avideo.utils.workdir import WorkdirManager  # noqa: PLC0415

        wm = WorkdirManager(tmp_path / "workdir")
        _write_script(wm, ["Una slide."])

        mocker.patch(
            "avideo.stages.voice_openai.synthesize_slide_openai",
            side_effect=_make_fake_synthesize(tmp_path),
        )
        mocker.patch(
            "avideo.stages.voice_openai.transcribe_slide_openai",
            return_value=_make_fake_transcribe(0),
        )

        bullets = tmp_path / "b.yaml"
        bullets.write_text("title: T\nbullets:\n  - x\n", encoding="utf-8")
        config = RunConfig(bullets=bullets, duration=60, voice=VoiceMode.openai)

        result = VoiceStage().run(wm, config)

        assert isinstance(result, UnifiedTimings)
        assert result.source == "openai"

    def test_4096_char_limit(self, tmp_path, mocker):
        """synthesize_slide_openai must raise ValueError when text exceeds 4096 chars."""
        mocker.patch("avideo.integrations.openai._get_client")

        from avideo.integrations.openai import synthesize_slide_openai  # noqa: PLC0415

        with pytest.raises(ValueError):
            synthesize_slide_openai(
                text="x" * 4097,
                slide_index=0,
                model="tts-1",
                voice="nova",
                out_path=tmp_path / "a.mp3",
            )

    def test_transcribe_maps_word_objects(self, tmp_path, mocker):
        """transcribe_slide_openai maps whisper-1 word objects to WordTiming list."""
        mock_client = mocker.MagicMock()
        mock_client.audio.transcriptions.create.return_value = types.SimpleNamespace(
            words=[
                types.SimpleNamespace(word="hola", start=0.0, end=0.4),
                types.SimpleNamespace(word="mundo", start=0.5, end=0.9),
            ]
        )
        mocker.patch("avideo.integrations.openai._get_client", return_value=mock_client)

        from avideo.integrations.openai import transcribe_slide_openai  # noqa: PLC0415

        result = transcribe_slide_openai(
            audio_path=Path("dummy.mp3"),
            slide_index=0,
        )

        assert len(result.words) == 2
        assert result.words[0].text == "hola"
        assert result.words[0].start == 0.0
        assert result.words[1].text == "mundo"
        assert result.words[1].end == 0.9

    def test_lazy_client_not_instantiated_at_import(self):
        """Importing avideo.integrations.openai must NOT create the client (_client is None)."""
        import avideo.integrations.openai as mod  # noqa: PLC0415

        assert mod._client is None, (
            "_client must be None at import time; lazy client must not instantiate "
            "the OpenAI SDK at module load (keeps tests import-safe when OPENAI_API_KEY "
            "is absent from the environment)"
        )

    def test_synthesize_slide_openai_at_module_scope(self):
        """Mock point: synthesize_slide_openai must be imported at module scope in voice_openai."""
        import avideo.stages.voice_openai as mod  # noqa: PLC0415

        assert hasattr(mod, "synthesize_slide_openai"), (
            "synthesize_slide_openai must be imported at module scope in voice_openai "
            "so tests can patch avideo.stages.voice_openai.synthesize_slide_openai"
        )

    def test_transcribe_slide_openai_at_module_scope(self):
        """Mock point: transcribe_slide_openai must be imported at module scope in voice_openai."""
        import avideo.stages.voice_openai as mod  # noqa: PLC0415

        assert hasattr(mod, "transcribe_slide_openai"), (
            "transcribe_slide_openai must be imported at module scope in voice_openai "
            "so tests can patch avideo.stages.voice_openai.transcribe_slide_openai"
        )
