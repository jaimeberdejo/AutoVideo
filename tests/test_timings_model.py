"""Tests for UnifiedTimings model (Task 2 of 04-01).

Covers:
- UnifiedTimings, SlideTimings, WordTiming construction and round-trip JSON
- whisperx_model field added to RunConfig with default "small"
- RunConfig backward compatibility (existing Phase 1/2 tests unaffected)
"""
from __future__ import annotations

import pytest


class TestWordTiming:
    """WordTiming: text + start + end floats in seconds (relative to slide)."""

    def test_construction(self):
        from avideo.models.timings import WordTiming

        w = WordTiming(text="hola", start=0.0, end=0.5)
        assert w.text == "hola"
        assert w.start == 0.0
        assert w.end == 0.5

    def test_round_trip_json(self):
        from avideo.models.timings import WordTiming

        w = WordTiming(text="world", start=1.2, end=1.8)
        assert WordTiming.model_validate_json(w.model_dump_json()) == w


class TestSlideTimings:
    """SlideTimings: one slide's audio path, duration, and word list."""

    def test_construction_with_words(self):
        from avideo.models.timings import SlideTimings, WordTiming

        st = SlideTimings(
            slide_index=0,
            audio_path="audio/slide_00.mp3",
            duration=5.0,
            words=[WordTiming(text="hi", start=0.0, end=0.5)],
        )
        assert st.slide_index == 0
        assert st.audio_path == "audio/slide_00.mp3"
        assert st.duration == 5.0
        assert len(st.words) == 1

    def test_construction_words_default_empty(self):
        from avideo.models.timings import SlideTimings

        st = SlideTimings(slide_index=1, audio_path="audio/slide_01.wav", duration=3.0)
        assert st.words == []

    def test_round_trip_json(self):
        from avideo.models.timings import SlideTimings, WordTiming

        st = SlideTimings(
            slide_index=0,
            audio_path="audio/slide_00.mp3",
            duration=2.5,
            words=[WordTiming(text="abc", start=0.1, end=0.9)],
        )
        assert SlideTimings.model_validate_json(st.model_dump_json()) == st


class TestUnifiedTimings:
    """UnifiedTimings: top-level container over all slides."""

    def test_construction_elevenlabs(self):
        from avideo.models.timings import SlideTimings, UnifiedTimings, WordTiming

        ut = UnifiedTimings(
            source="elevenlabs",
            slides=[
                SlideTimings(
                    slide_index=0,
                    audio_path="audio/slide_00.mp3",
                    duration=1.0,
                    words=[WordTiming(text="hi", start=0.0, end=0.5)],
                )
            ],
        )
        assert ut.source == "elevenlabs"
        assert len(ut.slides) == 1
        assert ut.slides[0].words[0].text == "hi"

    def test_construction_whisperx(self):
        from avideo.models.timings import SlideTimings, UnifiedTimings, WordTiming

        ut = UnifiedTimings(
            source="whisperx",
            slides=[
                SlideTimings(
                    slide_index=0,
                    audio_path="audio/slide_00.wav",
                    duration=2.0,
                    words=[
                        WordTiming(text="hola", start=0.0, end=0.4),
                        WordTiming(text="mundo", start=0.5, end=0.9),
                    ],
                )
            ],
        )
        assert ut.source == "whisperx"
        assert len(ut.slides[0].words) == 2

    def test_round_trip_json(self):
        from avideo.models.timings import SlideTimings, UnifiedTimings, WordTiming

        ut = UnifiedTimings(
            source="elevenlabs",
            slides=[
                SlideTimings(
                    slide_index=0,
                    audio_path="audio/slide_00.mp3",
                    duration=1.0,
                    words=[WordTiming(text="hi", start=0.0, end=0.5)],
                )
            ],
        )
        restored = UnifiedTimings.model_validate_json(ut.model_dump_json())
        assert restored.slides[0].words[0].text == "hi"

    def test_re_exported_from_models_init(self):
        """UnifiedTimings, SlideTimings, WordTiming must be in avideo.models."""
        from avideo.models import SlideTimings, UnifiedTimings, WordTiming  # noqa: F401

        assert UnifiedTimings is not None

    def test_multi_slide_round_trip(self):
        from avideo.models.timings import SlideTimings, UnifiedTimings, WordTiming

        ut = UnifiedTimings(
            source="elevenlabs",
            slides=[
                SlideTimings(
                    slide_index=i,
                    audio_path=f"audio/slide_{i:02d}.mp3",
                    duration=float(i + 1),
                    words=[WordTiming(text=f"word{i}", start=0.0, end=0.5)],
                )
                for i in range(3)
            ],
        )
        restored = UnifiedTimings.model_validate_json(ut.model_dump_json())
        assert len(restored.slides) == 3
        assert restored.slides[2].slide_index == 2


class TestRunConfigWhisperxModel:
    """RunConfig.whisperx_model — new field with default 'small'."""

    def test_default_whisperx_model(self, tmp_path):
        from pathlib import Path

        from avideo.models.config import RunConfig

        bullets = tmp_path / "b.yaml"
        bullets.write_text("title: T\nbullets:\n  - x\n", encoding="utf-8")
        config = RunConfig(bullets=bullets, duration=60)
        assert config.whisperx_model == "small"

    def test_override_whisperx_model(self, tmp_path):
        from pathlib import Path

        from avideo.models.config import RunConfig

        bullets = tmp_path / "b.yaml"
        bullets.write_text("title: T\nbullets:\n  - x\n", encoding="utf-8")
        config = RunConfig(bullets=bullets, duration=60, whisperx_model="large-v3")
        assert config.whisperx_model == "large-v3"

    def test_existing_fields_still_work(self, tmp_path):
        """Adding whisperx_model must not break Phase 1/2 RunConfig construction."""
        from avideo.models.config import RunConfig, VoiceMode

        bullets = tmp_path / "b.yaml"
        bullets.write_text("title: T\nbullets:\n  - x\n", encoding="utf-8")
        config = RunConfig(bullets=bullets, duration=120, voice=VoiceMode.elevenlabs)
        assert config.voice == VoiceMode.elevenlabs
        assert config.burn_subs is False
        assert config.language == "es"
