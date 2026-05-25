"""Tests for subtitle format utilities and SubtitlesStage.

Covers requirements SUB-01 and SUB-02:
  - SUB-01: UnifiedTimings → SRT (HH:MM:SS,mmm) + VTT (WEBVTT + HH:MM:SS.mmm)
  - SUB-02: burn_subs flag registered; Phase 4 does NOT burn (leaves .srt/.vtt ready)

Task 1 tests (pure logic — no I/O, no mocks):
  fmt_ts, to_srt, to_vtt, segment_words edge cases

Task 2 tests (SubtitlesStage):
  offset accumulation, file writing, burn_subs no-burn, stage_name
"""
from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Task 1 — Pure subtitle format helpers (utils/subtitle_format.py)
# ---------------------------------------------------------------------------


class TestFmtTs:
    """fmt_ts: seconds → HH:MM:SS,mmm (SRT) or HH:MM:SS.mmm (VTT)."""

    def test_srt_uses_comma(self):
        from avideo.utils.subtitle_format import fmt_ts
        result = fmt_ts(3661.5, vtt=False)
        assert result == "01:01:01,500", f"Expected comma separator, got: {result}"

    def test_vtt_uses_dot(self):
        from avideo.utils.subtitle_format import fmt_ts
        result = fmt_ts(3661.5, vtt=True)
        assert result == "01:01:01.500", f"Expected dot separator, got: {result}"

    def test_zero_seconds(self):
        from avideo.utils.subtitle_format import fmt_ts
        assert fmt_ts(0.0, vtt=False) == "00:00:00,000"
        assert fmt_ts(0.0, vtt=True) == "00:00:00.000"

    def test_millisecond_rounding(self):
        from avideo.utils.subtitle_format import fmt_ts
        # 1.0005 → rounds ms to 001 (1 ms after rounding)
        result = fmt_ts(1.001, vtt=False)
        assert result == "00:00:01,001"

    def test_hours_component(self):
        from avideo.utils.subtitle_format import fmt_ts
        # 7200s = 2h 0m 0s
        assert fmt_ts(7200.0, vtt=False) == "02:00:00,000"
        assert fmt_ts(7200.0, vtt=True) == "02:00:00.000"

    def test_full_timestamp_with_hours_minutes_seconds_ms(self):
        from avideo.utils.subtitle_format import fmt_ts
        # 3725.25 = 1h 2m 5.25s
        assert fmt_ts(3725.25, vtt=False) == "01:02:05,250"
        assert fmt_ts(3725.25, vtt=True) == "01:02:05.250"


class TestToSrt:
    """to_srt: list[Cue] → SRT string."""

    def test_empty_cues_produces_empty_string(self):
        from avideo.utils.subtitle_format import to_srt
        result = to_srt([])
        assert result == ""

    def test_single_cue_format(self):
        from avideo.utils.subtitle_format import Cue, to_srt
        cues = [Cue(start=1.0, end=3.0, text="Hello world")]
        result = to_srt(cues)
        lines = result.split("\n")
        assert lines[0] == "1", f"Expected index '1', got: {lines[0]}"
        assert lines[1] == "00:00:01,000 --> 00:00:03,000"
        assert lines[2] == "Hello world"
        assert lines[3] == ""  # blank line after cue

    def test_multiple_cues_one_indexed(self):
        from avideo.utils.subtitle_format import Cue, to_srt
        cues = [
            Cue(start=0.0, end=2.0, text="First"),
            Cue(start=2.5, end=4.5, text="Second"),
        ]
        result = to_srt(cues)
        lines = result.split("\n")
        assert lines[0] == "1"
        # After first cue: index, timestamp, text, blank line
        assert lines[4] == "2"
        assert lines[5] == "00:00:02,500 --> 00:00:04,500"

    def test_srt_uses_comma_in_timestamps(self):
        from avideo.utils.subtitle_format import Cue, to_srt
        cues = [Cue(start=1.5, end=2.5, text="Test")]
        result = to_srt(cues)
        assert "," in result, "SRT must use comma in timestamps"
        assert "." not in result.split("\n")[1], "SRT must NOT use dot in timestamps"

    def test_blank_line_between_cues(self):
        from avideo.utils.subtitle_format import Cue, to_srt
        cues = [
            Cue(start=0.0, end=1.0, text="A"),
            Cue(start=1.5, end=2.5, text="B"),
        ]
        result = to_srt(cues)
        # Format: "1\n...\nA\n\n2\n...\nB\n"
        assert "\n\n" in result, "SRT must have blank line between cues"


class TestToVtt:
    """to_vtt: list[Cue] → VTT string."""

    def test_starts_with_webvtt_header(self):
        from avideo.utils.subtitle_format import to_vtt
        result = to_vtt([])
        assert result.startswith("WEBVTT"), f"VTT must start with WEBVTT, got: {result!r}"

    def test_webvtt_followed_by_blank_line(self):
        from avideo.utils.subtitle_format import to_vtt
        result = to_vtt([])
        lines = result.split("\n")
        assert lines[0] == "WEBVTT"
        assert lines[1] == "", f"Expected blank line after WEBVTT header, got: {lines[1]!r}"

    def test_no_numeric_index_in_vtt(self):
        from avideo.utils.subtitle_format import Cue, to_vtt
        cues = [Cue(start=1.0, end=2.0, text="Hello")]
        result = to_vtt(cues)
        lines = result.split("\n")
        # After "WEBVTT" and blank line, next non-empty line should be timestamp, not index
        non_empty = [l for l in lines if l.strip()]
        assert non_empty[0] == "WEBVTT"
        assert "-->" in non_empty[1], f"Expected timestamp line after WEBVTT, got: {non_empty[1]}"

    def test_vtt_uses_dot_in_timestamps(self):
        from avideo.utils.subtitle_format import Cue, to_vtt
        cues = [Cue(start=1.5, end=2.5, text="Test")]
        result = to_vtt(cues)
        timestamp_line = [l for l in result.split("\n") if "-->" in l][0]
        assert "." in timestamp_line, "VTT must use dot in timestamps"
        # Should not have comma in the timestamp portion
        parts = timestamp_line.split(" --> ")
        assert "," not in parts[0], "VTT start timestamp must not use comma"
        assert "," not in parts[1], "VTT end timestamp must not use comma"

    def test_single_cue_content(self):
        from avideo.utils.subtitle_format import Cue, to_vtt
        cues = [Cue(start=0.5, end=1.5, text="Line one")]
        result = to_vtt(cues)
        assert "Line one" in result


class TestSegmentWords:
    """segment_words: list[WordTiming] → list[Cue] with cue constraints."""

    def test_empty_words_returns_no_cues(self):
        from avideo.utils.subtitle_format import segment_words
        assert segment_words([]) == []

    def test_single_word_single_cue(self):
        from avideo.utils.subtitle_format import segment_words
        from avideo.models.timings import WordTiming
        words = [WordTiming(text="Hello", start=0.0, end=0.5)]
        cues = segment_words(words)
        assert len(cues) == 1
        assert cues[0].text == "Hello"
        assert cues[0].start == 0.0
        assert cues[0].end == 0.5

    def test_single_very_long_word_kept_in_one_cue(self):
        """A single word that exceeds char limit still produces exactly one cue."""
        from avideo.utils.subtitle_format import segment_words
        from avideo.models.timings import WordTiming
        long_word = "A" * 100  # exceeds 42 chars
        words = [WordTiming(text=long_word, start=0.0, end=1.0)]
        cues = segment_words(words)
        assert len(cues) == 1, "Single word must not be split or lost"
        assert long_word in cues[0].text

    def test_break_on_char_limit(self):
        """Words are split into new cue when adding next word would exceed ~42 chars/line."""
        from avideo.utils.subtitle_format import segment_words
        from avideo.models.timings import WordTiming
        # Each word is 10 chars; 4 fit per 42-char line but 5 would exceed (~50 chars with spaces)
        words = [
            WordTiming(text="AAAAAAAAAA", start=float(i), end=float(i) + 0.5)
            for i in range(6)  # 6 words of 10 chars each
        ]
        cues = segment_words(words)
        # Should produce at least 2 cues due to char limit
        assert len(cues) >= 2, f"Expected multiple cues from char limit, got {len(cues)}"
        # No text should be lost
        all_text = " ".join(c.text.replace("\n", " ") for c in cues)
        for w in words:
            assert w.text in all_text, f"Word {w.text} lost in segmentation"

    def test_break_on_duration_limit(self):
        """Cue duration must not exceed 5 seconds."""
        from avideo.utils.subtitle_format import segment_words
        from avideo.models.timings import WordTiming
        # 10 short words spread over 12 seconds
        words = [
            WordTiming(text="hi", start=float(i) * 1.5, end=float(i) * 1.5 + 0.5)
            for i in range(8)
        ]
        cues = segment_words(words)
        for cue in cues:
            duration = cue.end - cue.start
            assert duration <= 5.0 + 0.001, f"Cue duration {duration:.3f}s exceeds 5s limit: {cue}"

    def test_break_on_cps_limit(self):
        """High CPS must trigger a new cue when multiple words are involved (≤17 CPS).

        A single word that individually exceeds CPS cannot be split without losing text,
        so the CPS constraint only prevents ADDING more words to a cue that would
        push it over the limit.  Each single-word cue keeps its word regardless.
        """
        from avideo.utils.subtitle_format import segment_words
        from avideo.models.timings import WordTiming
        # 3 short words in a 1-second window: combined = 15+15+15 = 45 chars in 1.5s = 30 CPS
        # Each word alone = 15 chars in 0.5s = 30 CPS (single word — unavoidable)
        # Together they would be even worse, so segment_words should split them
        words = [
            WordTiming(text="a" * 8, start=0.0, end=0.4),   # 8 chars / 0.4s = 20 CPS
            WordTiming(text="b" * 8, start=0.4, end=0.8),   # adding → 17 chars / 0.8s = 21 CPS
            WordTiming(text="c" * 8, start=0.8, end=1.2),
        ]
        cues = segment_words(words)
        # Adding the 2nd word to the 1st would give "aaaaaaaa bbbbbbbb" = 17 chars / 0.8s = 21.25 CPS
        # So the segmenter should split them into separate cues
        assert len(cues) >= 2, (
            f"CPS limit should have split words into ≥2 cues, got {len(cues)}: {cues}"
        )

    def test_all_words_preserved(self):
        """No word text must be lost during segmentation."""
        from avideo.utils.subtitle_format import segment_words
        from avideo.models.timings import WordTiming
        words = [
            WordTiming(text=f"word{i}", start=float(i) * 0.3, end=float(i) * 0.3 + 0.2)
            for i in range(20)
        ]
        cues = segment_words(words)
        all_text = " ".join(c.text.replace("\n", " ") for c in cues)
        for w in words:
            assert w.text in all_text, f"Word {w.text!r} was lost in segmentation"

    def test_cue_start_end_from_first_last_word(self):
        """Cue start = first word start, end = last word end."""
        from avideo.utils.subtitle_format import segment_words
        from avideo.models.timings import WordTiming
        words = [
            WordTiming(text="The", start=1.2, end=1.5),
            WordTiming(text="quick", start=1.6, end=1.9),
            WordTiming(text="brown", start=2.0, end=2.3),
        ]
        cues = segment_words(words)
        # All short words, should fit in one cue
        assert len(cues) >= 1
        assert cues[0].start == 1.2
        # Last cue end should be 2.3
        assert cues[-1].end == 2.3


# ---------------------------------------------------------------------------
# Task 2 — SubtitlesStage integration tests
# ---------------------------------------------------------------------------


class TestSubtitlesStage:
    """SubtitlesStage: reads align checkpoint, writes output.srt + output.vtt."""

    def _make_unified_timings(self, num_slides=2):
        """Build UnifiedTimings with real words for testing."""
        from avideo.models.timings import SlideTimings, UnifiedTimings, WordTiming
        slides = []
        for i in range(num_slides):
            offset = i * 5.0  # 5s per slide
            words = [
                WordTiming(text="Hello", start=0.1, end=0.5),
                WordTiming(text="world", start=0.6, end=1.0),
                WordTiming(text="from", start=1.1, end=1.4),
                WordTiming(text="slide", start=1.5, end=1.8),
            ]
            slides.append(SlideTimings(
                slide_index=i,
                audio_path=f"audio/slide_{i:02d}.mp3",
                duration=5.0,
                words=words,
            ))
        return UnifiedTimings(source="elevenlabs", slides=slides)

    def test_stage_name_is_subs(self):
        from avideo.stages.subtitles import SubtitlesStage
        assert SubtitlesStage().stage_name == "subs"

    def test_writes_srt_and_vtt_files(self, tmp_path):
        from avideo.models import RunConfig
        from avideo.stages.subtitles import SubtitlesStage
        from avideo.utils.workdir import WorkdirManager

        workdir = WorkdirManager(tmp_path)
        timings = self._make_unified_timings(num_slides=2)
        workdir.write_checkpoint("align", timings)

        bullets_file = tmp_path / "bullets.yaml"
        bullets_file.write_text("title: T\nbullets:\n  - B\n")
        config = RunConfig(bullets=bullets_file, duration=10)

        SubtitlesStage().run(workdir, config)

        assert (tmp_path / "subs" / "output.srt").exists(), "output.srt must be created"
        assert (tmp_path / "subs" / "output.vtt").exists(), "output.vtt must be created"

    def test_srt_uses_comma_timestamps(self, tmp_path):
        from avideo.models import RunConfig
        from avideo.stages.subtitles import SubtitlesStage
        from avideo.utils.workdir import WorkdirManager

        workdir = WorkdirManager(tmp_path)
        timings = self._make_unified_timings(num_slides=1)
        workdir.write_checkpoint("align", timings)

        bullets_file = tmp_path / "bullets.yaml"
        bullets_file.write_text("title: T\nbullets:\n  - B\n")
        config = RunConfig(bullets=bullets_file, duration=10)

        SubtitlesStage().run(workdir, config)

        srt_content = (tmp_path / "subs" / "output.srt").read_text(encoding="utf-8")
        # Find timestamp line
        timestamp_lines = [l for l in srt_content.split("\n") if "-->" in l]
        assert timestamp_lines, "No timestamp lines found in SRT"
        assert "," in timestamp_lines[0], f"SRT must use comma in timestamps: {timestamp_lines[0]}"

    def test_vtt_starts_with_webvtt(self, tmp_path):
        from avideo.models import RunConfig
        from avideo.stages.subtitles import SubtitlesStage
        from avideo.utils.workdir import WorkdirManager

        workdir = WorkdirManager(tmp_path)
        timings = self._make_unified_timings(num_slides=1)
        workdir.write_checkpoint("align", timings)

        bullets_file = tmp_path / "bullets.yaml"
        bullets_file.write_text("title: T\nbullets:\n  - B\n")
        config = RunConfig(bullets=bullets_file, duration=10)

        SubtitlesStage().run(workdir, config)

        vtt_content = (tmp_path / "subs" / "output.vtt").read_text(encoding="utf-8")
        assert vtt_content.startswith("WEBVTT"), "VTT must start with WEBVTT"

    def test_global_offset_slide2_shifted_by_slide1_duration(self, tmp_path):
        """Multi-slide: cues from slide 2 must be shifted by slide 1 duration (5s)."""
        from avideo.models import RunConfig
        from avideo.stages.subtitles import SubtitlesStage
        from avideo.utils.workdir import WorkdirManager

        workdir = WorkdirManager(tmp_path)
        timings = self._make_unified_timings(num_slides=2)  # each slide 5s duration
        workdir.write_checkpoint("align", timings)

        bullets_file = tmp_path / "bullets.yaml"
        bullets_file.write_text("title: T\nbullets:\n  - B\n")
        config = RunConfig(bullets=bullets_file, duration=10)

        SubtitlesStage().run(workdir, config)

        srt_content = (tmp_path / "subs" / "output.srt").read_text(encoding="utf-8")
        timestamp_lines = [l for l in srt_content.split("\n") if "-->" in l]

        # Slide 1 words start at 0.1s (relative) → should be 0.1s globally
        # Slide 2 words start at 0.1s (relative) + 5.0s offset → should be 5.1s globally
        # First cue start: 00:00:00,100
        # Slide 2 first cue start: must be ≥ 5.0s from start

        assert len(timestamp_lines) >= 2, f"Need at least 2 cues, got: {timestamp_lines}"

        # Find slide-2 cues: their timestamps must be ≥ 5 seconds
        # Slide 2 first word is at 0.1 + 5.0 = 5.1s global
        # Check that at least one timestamp line shows a time >= 5s
        def parse_start(ts_line: str) -> float:
            """Parse HH:MM:SS,mmm --> ... to float seconds."""
            start_str = ts_line.split(" --> ")[0].strip()
            # Handle comma (SRT) or dot (VTT)
            start_str = start_str.replace(",", ".")
            parts = start_str.split(":")
            h, m, s = int(parts[0]), int(parts[1]), float(parts[2])
            return h * 3600 + m * 60 + s

        starts = [parse_start(l) for l in timestamp_lines]
        # At least one cue should start at >= 5s (slide 2 offset)
        assert any(s >= 5.0 for s in starts), (
            f"No slide-2 cues found at >= 5s offset. Starts: {starts}"
        )
        # First cue should start near 0s (slide 1)
        assert starts[0] < 5.0, (
            f"First cue should be from slide 1 (<5s). Got: {starts[0]}"
        )

    def test_burn_subs_true_only_writes_files_no_ffmpeg(self, tmp_path, monkeypatch):
        """SUB-02: burn_subs=True does NOT invoke ffmpeg; only writes .srt/.vtt."""
        import subprocess
        from avideo.models import RunConfig
        from avideo.stages.subtitles import SubtitlesStage
        from avideo.utils.workdir import WorkdirManager

        # Patch subprocess.run to detect any ffmpeg calls
        mock_run = MagicMock = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock
        ffmpeg_called = []

        original_run = subprocess.run

        def spy_run(args, **kwargs):
            if args and "ffmpeg" in str(args[0]):
                ffmpeg_called.append(args)
            return original_run(args, **kwargs)

        monkeypatch.setattr(subprocess, "run", spy_run)

        workdir = WorkdirManager(tmp_path)
        timings = self._make_unified_timings(num_slides=1)
        workdir.write_checkpoint("align", timings)

        bullets_file = tmp_path / "bullets.yaml"
        bullets_file.write_text("title: T\nbullets:\n  - B\n")
        config = RunConfig(bullets=bullets_file, duration=10, burn_subs=True)

        SubtitlesStage().run(workdir, config)

        # Files must exist
        assert (tmp_path / "subs" / "output.srt").exists()
        assert (tmp_path / "subs" / "output.vtt").exists()
        # ffmpeg must NOT have been called
        assert not ffmpeg_called, (
            f"Phase 4 must NOT burn subtitles; ffmpeg called with: {ffmpeg_called}"
        )

    def test_output_contains_real_narration_text(self, tmp_path):
        """SRT/VTT must contain the actual word text from words list."""
        from avideo.models import RunConfig
        from avideo.stages.subtitles import SubtitlesStage
        from avideo.utils.workdir import WorkdirManager

        workdir = WorkdirManager(tmp_path)
        timings = self._make_unified_timings(num_slides=1)
        workdir.write_checkpoint("align", timings)

        bullets_file = tmp_path / "bullets.yaml"
        bullets_file.write_text("title: T\nbullets:\n  - B\n")
        config = RunConfig(bullets=bullets_file, duration=10)

        SubtitlesStage().run(workdir, config)

        srt_content = (tmp_path / "subs" / "output.srt").read_text(encoding="utf-8")
        # Words from _make_unified_timings are: Hello, world, from, slide
        assert "Hello" in srt_content, "Real word 'Hello' must appear in SRT"
        assert "world" in srt_content, "Real word 'world' must appear in SRT"

    def test_returns_serializable_model(self, tmp_path):
        """stage.run() must return a Pydantic BaseModel (write_checkpoint can call it)."""
        from pydantic import BaseModel
        from avideo.models import RunConfig
        from avideo.stages.subtitles import SubtitlesStage
        from avideo.utils.workdir import WorkdirManager

        workdir = WorkdirManager(tmp_path)
        timings = self._make_unified_timings(num_slides=1)
        workdir.write_checkpoint("align", timings)

        bullets_file = tmp_path / "bullets.yaml"
        bullets_file.write_text("title: T\nbullets:\n  - B\n")
        config = RunConfig(bullets=bullets_file, duration=10)

        result = SubtitlesStage().run(workdir, config)
        assert isinstance(result, BaseModel), f"Expected BaseModel, got {type(result)}"
        # Must be JSON-serializable
        json_str = result.model_dump_json()
        assert json_str, "model_dump_json() must return non-empty string"

    def test_empty_words_falls_back_gracefully(self, tmp_path):
        """When words list is empty, stage still writes files (no crash, no placeholder lost)."""
        from avideo.models import RunConfig
        from avideo.models.timings import SlideTimings, UnifiedTimings
        from avideo.stages.subtitles import SubtitlesStage
        from avideo.utils.workdir import WorkdirManager

        workdir = WorkdirManager(tmp_path)
        # Slide with no words
        timings = UnifiedTimings(
            source="elevenlabs",
            slides=[
                SlideTimings(
                    slide_index=0,
                    audio_path="audio/slide_00.mp3",
                    duration=5.0,
                    words=[],  # empty
                ),
            ],
        )
        workdir.write_checkpoint("align", timings)

        bullets_file = tmp_path / "bullets.yaml"
        bullets_file.write_text("title: T\nbullets:\n  - B\n")
        config = RunConfig(bullets=bullets_file, duration=10)

        # Must not crash
        result = SubtitlesStage().run(workdir, config)
        assert (tmp_path / "subs" / "output.srt").exists()
        assert (tmp_path / "subs" / "output.vtt").exists()
