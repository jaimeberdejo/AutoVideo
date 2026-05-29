"""RED tests for Phase 13 extras helpers in avideo.ui.pipeline_ops.

Fail with AttributeError until Plan 02 adds the three new functions:
write_uploaded_music, extras_to_run_config, and read_qa_report.

Coverage:
  TestWriteUploadedMusic:
    - write_uploaded_music writes bytes to workdir/music/<filename>
    - write_uploaded_music rejects path-traversal filenames with ".."
    - write_uploaded_music rejects filenames containing "/"

  TestExtrasToRunConfig:
    - extras_to_run_config maps burn_subs=True into kwargs["burn_subs"]
    - extras_to_run_config maps bg_music_path, bg_music_volume, crossfade_seconds
    - extras_to_run_config returns expected keys with all-defaults / no music

  TestReadQaReport:
    - read_qa_report returns None when qa_report.json is missing
    - read_qa_report parses valid JSON and returns QAReport with correct values
    - read_qa_report returns None on corrupt / non-JSON content

All imports of the new functions from avideo.ui.pipeline_ops are DEFERRED
inside each test body (same pattern as tests/test_voz_pipeline_ops.py), so
this file collects cleanly before pipeline_ops.py has the new helpers
(RED phase).

Threat model compliance:
    T-13-01-01 (Tampering): write_uploaded_music must raise ValueError on
    "../evil.mp3" and "sub/dir.mp3" — tests enforce this guard.
"""
from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Model imports (modules already exist — top-level import is fine)
# ---------------------------------------------------------------------------
from avideo.models.assembly import QAReport
from avideo.utils.workdir import WorkdirManager


# ---------------------------------------------------------------------------
# Class 1: TestWriteUploadedMusic
# ---------------------------------------------------------------------------


class TestWriteUploadedMusic:
    """Tests for write_uploaded_music() — path-traversal-safe music upload."""

    def test_write_uploaded_music_creates_file_in_music_dir(
        self,
        tmp_path: Path,
    ) -> None:
        """write_uploaded_music(wm, "bg.mp3", b"RIFF...") writes bytes to
        workdir/music/bg.mp3 and returns that Path.

        No mocking needed — real filesystem write.
        """
        from avideo.ui.pipeline_ops import write_uploaded_music  # noqa: PLC0415

        wm = WorkdirManager(tmp_path / "workdir")
        data = b"RIFF\x00data"

        result = write_uploaded_music(wm, "bg.mp3", data)

        expected = wm.root / "music" / "bg.mp3"
        assert result == expected, (
            f"Expected returned path {expected}, got {result}"
        )
        assert expected.read_bytes() == data, (
            "File contents must match the uploaded bytes"
        )

    def test_write_uploaded_music_rejects_path_traversal(
        self,
        tmp_path: Path,
    ) -> None:
        """write_uploaded_music(wm, '../evil.mp3', b'') raises ValueError.

        Path traversal via '..' must be rejected (mirrors T-12-02-01 guard).
        """
        from avideo.ui.pipeline_ops import write_uploaded_music  # noqa: PLC0415

        wm = WorkdirManager(tmp_path / "workdir")

        with pytest.raises(ValueError):
            write_uploaded_music(wm, "../evil.mp3", b"")

    def test_write_uploaded_music_rejects_slash_in_filename(
        self,
        tmp_path: Path,
    ) -> None:
        """write_uploaded_music(wm, 'sub/dir.mp3', b'') raises ValueError.

        Filenames containing '/' must be rejected (T-13-01-01).
        """
        from avideo.ui.pipeline_ops import write_uploaded_music  # noqa: PLC0415

        wm = WorkdirManager(tmp_path / "workdir")

        with pytest.raises(ValueError):
            write_uploaded_music(wm, "sub/dir.mp3", b"")


# ---------------------------------------------------------------------------
# Class 2: TestExtrasToRunConfig
# ---------------------------------------------------------------------------


class TestExtrasToRunConfig:
    """Tests for extras_to_run_config() — maps widget values to RunConfig kwargs."""

    def test_extras_to_run_config_burn_subs_true(self) -> None:
        """extras_to_run_config(burn_subs=True, ...) returns kwargs with burn_subs=True."""
        from avideo.ui.pipeline_ops import extras_to_run_config  # noqa: PLC0415

        kwargs = extras_to_run_config(
            burn_subs=True,
            bg_music_path=None,
            bg_music_volume=0.12,
            bg_music_fade_out_s=3.0,
            crossfade_seconds=0.5,
        )

        assert kwargs["burn_subs"] is True

    def test_extras_to_run_config_music_path_set(self) -> None:
        """extras_to_run_config maps bg_music_path, bg_music_volume, crossfade_seconds."""
        from avideo.ui.pipeline_ops import extras_to_run_config  # noqa: PLC0415

        mp = Path("/tmp/music.mp3")
        kwargs = extras_to_run_config(
            burn_subs=False,
            bg_music_path=mp,
            bg_music_volume=0.2,
            bg_music_fade_out_s=2.0,
            crossfade_seconds=1.0,
        )

        assert kwargs["bg_music_path"] == mp
        assert kwargs["bg_music_volume"] == pytest.approx(0.2)
        assert kwargs["crossfade_seconds"] == pytest.approx(1.0)

    def test_extras_to_run_config_all_defaults_no_music(self) -> None:
        """extras_to_run_config with no music returns expected keys including burn_subs."""
        from avideo.ui.pipeline_ops import extras_to_run_config  # noqa: PLC0415

        kwargs = extras_to_run_config(
            burn_subs=False,
            bg_music_path=None,
            bg_music_volume=0.12,
            bg_music_fade_out_s=3.0,
            crossfade_seconds=0.5,
        )

        assert kwargs.get("bg_music_path") is None
        assert "burn_subs" in kwargs


# ---------------------------------------------------------------------------
# Class 3: TestReadQaReport
# ---------------------------------------------------------------------------


class TestReadQaReport:
    """Tests for read_qa_report() — reads qa_report.json from workdir."""

    def test_read_qa_report_returns_none_when_missing(
        self,
        tmp_path: Path,
    ) -> None:
        """read_qa_report returns None when qa_report.json does not exist."""
        from avideo.ui.pipeline_ops import read_qa_report  # noqa: PLC0415

        wm = WorkdirManager(tmp_path / "workdir")

        result = read_qa_report(wm)

        assert result is None

    def test_read_qa_report_parses_valid_json(
        self,
        tmp_path: Path,
    ) -> None:
        """read_qa_report parses a valid qa_report.json and returns a QAReport."""
        from avideo.ui.pipeline_ops import read_qa_report  # noqa: PLC0415

        wm = WorkdirManager(tmp_path / "workdir")
        qa = QAReport(
            target_seconds=60.0,
            actual_seconds=61.2,
            duration_deviation=1.2,
            measured_lufs=-18.0,
            normalized_lufs=-16.0,
        )
        qa_path = wm.root / "qa_report.json"
        qa_path.parent.mkdir(parents=True, exist_ok=True)
        qa_path.write_text(qa.model_dump_json(), encoding="utf-8")

        result = read_qa_report(wm)

        assert result is not None
        assert result.duration_deviation == pytest.approx(1.2)
        assert result.measured_lufs == pytest.approx(-18.0)

    def test_read_qa_report_returns_none_on_corrupt_json(
        self,
        tmp_path: Path,
    ) -> None:
        """read_qa_report returns None when qa_report.json contains invalid JSON."""
        from avideo.ui.pipeline_ops import read_qa_report  # noqa: PLC0415

        wm = WorkdirManager(tmp_path / "workdir")
        wm.root.mkdir(parents=True, exist_ok=True)
        (wm.root / "qa_report.json").write_text("not json", encoding="utf-8")

        result = read_qa_report(wm)

        assert result is None
