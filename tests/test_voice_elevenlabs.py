"""Tests for VoiceElevenlabsStage and VoiceStage (Task 4 of 04-01).

Covers VOICE-01:
  - VoiceElevenlabsStage.run reads script.json checkpoint, calls synthesize_slide
    once per slide, writes audio files, and returns UnifiedTimings(source="elevenlabs")
  - Mock point: avideo.stages.voice_elevenlabs.synthesize_slide (module-scope import)
  - VoiceStage.stage_name == "voice" (checkpoint contract D-12)
  - VoiceStage dispatches to ElevenLabs branch when config.voice == elevenlabs
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_script(workdir_manager, slides):
    """Write a minimal script.json checkpoint to workdir."""
    from avideo.models.script import ScriptOutput, SlideScript

    script = ScriptOutput(
        slides=[SlideScript(slide_index=i, narration=n) for i, n in enumerate(slides)],
        language="es",
    )
    workdir_manager.write_checkpoint("script", script)


def _make_fake_synthesize(tmp_path):
    """Return a side_effect function for mocking synthesize_slide.

    Writes a tiny mp3-like file to out_path and returns a SlideTimings.
    """
    from avideo.models.timings import SlideTimings, WordTiming

    def _fake(*, text, slide_index, voice_id, out_path, **kwargs):
        out_path.write_bytes(b"\xff\xe3\x10\x00")  # minimal fake bytes
        return SlideTimings(
            slide_index=slide_index,
            audio_path=str(out_path),
            duration=2.0,
            words=[WordTiming(text=text.split()[0], start=0.0, end=1.0)],
        )

    return _fake


# ---------------------------------------------------------------------------
# VoiceElevenlabsStage
# ---------------------------------------------------------------------------


class TestVoiceElevenlabsStage:
    """VoiceElevenlabsStage produces UnifiedTimings(source="elevenlabs")."""

    def test_stage_name_is_voice(self):
        from avideo.stages.voice_elevenlabs import VoiceElevenlabsStage

        stage = VoiceElevenlabsStage()
        assert stage.stage_name == "voice"

    def test_run_calls_synthesize_once_per_slide(self, tmp_path, mocker):
        from avideo.stages.voice_elevenlabs import VoiceElevenlabsStage
        from avideo.utils.workdir import WorkdirManager

        wm = WorkdirManager(tmp_path / "workdir")
        _write_script(wm, ["Narración slide uno.", "Narración slide dos."])

        mock_synth = mocker.patch(
            "avideo.stages.voice_elevenlabs.synthesize_slide",
            side_effect=_make_fake_synthesize(tmp_path),
        )

        from avideo.models.config import RunConfig, VoiceMode

        bullets = tmp_path / "b.yaml"
        bullets.write_text("title: T\nbullets:\n  - x\n", encoding="utf-8")
        config = RunConfig(bullets=bullets, duration=60, voice_id="test-voice")

        stage = VoiceElevenlabsStage()
        result = stage.run(wm, config)

        assert mock_synth.call_count == 2

    def test_run_returns_unified_timings_source_elevenlabs(self, tmp_path, mocker):
        from avideo.models.timings import UnifiedTimings
        from avideo.stages.voice_elevenlabs import VoiceElevenlabsStage
        from avideo.utils.workdir import WorkdirManager

        wm = WorkdirManager(tmp_path / "workdir")
        _write_script(wm, ["Hola mundo.", "Adiós mundo."])

        mocker.patch(
            "avideo.stages.voice_elevenlabs.synthesize_slide",
            side_effect=_make_fake_synthesize(tmp_path),
        )

        from avideo.models.config import RunConfig

        bullets = tmp_path / "b.yaml"
        bullets.write_text("title: T\nbullets:\n  - x\n", encoding="utf-8")
        config = RunConfig(bullets=bullets, duration=60)

        result = VoiceElevenlabsStage().run(wm, config)

        assert isinstance(result, UnifiedTimings)
        assert result.source == "elevenlabs"
        assert len(result.slides) == 2

    def test_run_produces_slide_timings_with_correct_indices(self, tmp_path, mocker):
        from avideo.stages.voice_elevenlabs import VoiceElevenlabsStage
        from avideo.utils.workdir import WorkdirManager

        wm = WorkdirManager(tmp_path / "workdir")
        _write_script(wm, ["Slide cero.", "Slide uno.", "Slide dos."])

        mocker.patch(
            "avideo.stages.voice_elevenlabs.synthesize_slide",
            side_effect=_make_fake_synthesize(tmp_path),
        )

        from avideo.models.config import RunConfig

        bullets = tmp_path / "b.yaml"
        bullets.write_text("title: T\nbullets:\n  - x\n", encoding="utf-8")
        config = RunConfig(bullets=bullets, duration=90)

        result = VoiceElevenlabsStage().run(wm, config)

        assert [s.slide_index for s in result.slides] == [0, 1, 2]

    def test_run_writes_mp3_via_synthesize(self, tmp_path, mocker):
        """Verify that synthesize_slide receives out_path in audio/ subdir."""
        from avideo.stages.voice_elevenlabs import VoiceElevenlabsStage
        from avideo.utils.workdir import WorkdirManager

        wm = WorkdirManager(tmp_path / "workdir")
        _write_script(wm, ["Narración test."])

        captured_paths = []

        def _capturing_synth(*, text, slide_index, voice_id, out_path, **kwargs):
            captured_paths.append(out_path)
            out_path.write_bytes(b"\xff\xe3")
            from avideo.models.timings import SlideTimings, WordTiming

            return SlideTimings(
                slide_index=slide_index,
                audio_path=str(out_path),
                duration=1.0,
                words=[WordTiming(text="test", start=0.0, end=0.5)],
            )

        mocker.patch("avideo.stages.voice_elevenlabs.synthesize_slide", side_effect=_capturing_synth)

        from avideo.models.config import RunConfig

        bullets = tmp_path / "b.yaml"
        bullets.write_text("title: T\nbullets:\n  - x\n", encoding="utf-8")
        config = RunConfig(bullets=bullets, duration=30)

        VoiceElevenlabsStage().run(wm, config)

        assert len(captured_paths) == 1
        assert "audio" in str(captured_paths[0])
        assert "slide_00" in str(captured_paths[0])

    def test_synthesize_slide_imported_at_module_scope(self):
        """Mock point: synthesize_slide must be imported at module scope in voice_elevenlabs."""
        import avideo.stages.voice_elevenlabs as mod

        assert hasattr(mod, "synthesize_slide"), (
            "synthesize_slide must be imported at module scope in voice_elevenlabs "
            "so tests can patch avideo.stages.voice_elevenlabs.synthesize_slide"
        )


# ---------------------------------------------------------------------------
# VoiceStage dispatcher
# ---------------------------------------------------------------------------


class TestVoiceStage:
    """VoiceStage(stage_name='voice') dispatches by config.voice."""

    def test_stage_name_is_voice(self):
        from avideo.stages.voice import VoiceStage

        assert VoiceStage().stage_name == "voice"

    def test_checkpoint_name_is_voice(self):
        from avideo.stages.voice import VoiceStage

        assert VoiceStage().checkpoint_name == "voice"

    def test_elevenlabs_dispatches_to_voice_elevenlabs_stage(self, tmp_path, mocker):
        from avideo.models.config import RunConfig, VoiceMode
        from avideo.models.timings import SlideTimings, UnifiedTimings
        from avideo.stages.voice import VoiceStage
        from avideo.utils.workdir import WorkdirManager

        wm = WorkdirManager(tmp_path / "workdir")
        _write_script(wm, ["Una sola slide."])

        mock_synth = mocker.patch(
            "avideo.stages.voice_elevenlabs.synthesize_slide",
            side_effect=_make_fake_synthesize(tmp_path),
        )

        bullets = tmp_path / "b.yaml"
        bullets.write_text("title: T\nbullets:\n  - x\n", encoding="utf-8")
        config = RunConfig(bullets=bullets, duration=60, voice=VoiceMode.elevenlabs)

        result = VoiceStage().run(wm, config)

        assert isinstance(result, UnifiedTimings)
        assert result.source == "elevenlabs"
        assert mock_synth.call_count == 1

    def test_record_branch_raises_import_error_gracefully(self, tmp_path, mocker):
        """Record mode must fail with an ImportError or a clear message (not AttributeError)."""
        from avideo.models.config import RunConfig, VoiceMode
        from avideo.stages.voice import VoiceStage
        from avideo.utils.workdir import WorkdirManager

        wm = WorkdirManager(tmp_path / "workdir")
        _write_script(wm, ["Una slide."])

        bullets = tmp_path / "b.yaml"
        bullets.write_text("title: T\nbullets:\n  - x\n", encoding="utf-8")
        config = RunConfig(bullets=bullets, duration=60, voice=VoiceMode.record)

        # The record stage is not implemented yet (04-02); must raise a clear error
        with pytest.raises((ImportError, NotImplementedError, RuntimeError)):
            VoiceStage().run(wm, config)
