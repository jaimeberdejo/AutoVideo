"""Tests for ContextStage real text extraction.

Covers:
- CTX-02: config.context is None → ContextOutput(used=False), text=="".
- CTX-01: .md fixture → used=True, text contains file content.
- CTX-01: .pdf fixture → used=True, text non-empty.
- CTX-01: .pptx fixture → used=True, text contains slide text.
- Encrypted PDF → raises ValueError mentioning password/protected.
- Extracted text longer than the token cap is truncated.
- Unsupported suffix → raises ValueError.
- test_no_context: exact name for -k no_context matching in VALIDATION.
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock


def _make_config(tmp_path: Path, context: Path | None = None) -> MagicMock:
    """Build a minimal RunConfig-like mock with the given context path."""
    cfg = MagicMock()
    cfg.context = context
    return cfg


def _make_workdir() -> MagicMock:
    """Build a minimal WorkdirManager-like mock."""
    wd = MagicMock()
    wd.is_done.return_value = False
    return wd


def test_no_context(tmp_path: Path) -> None:
    """CTX-02: config.context is None → ContextOutput(used=False), text==""."""
    from avideo.stages.context import ContextStage  # noqa: PLC0415

    stage = ContextStage()
    result = stage.run(_make_workdir(), _make_config(tmp_path, context=None))
    assert result.used is False
    assert result.text == ""


def test_md_extraction(tmp_path: Path, sample_md: Path) -> None:
    """CTX-01: .md file → ContextOutput(used=True) with non-empty text."""
    from avideo.stages.context import ContextStage  # noqa: PLC0415

    stage = ContextStage()
    result = stage.run(_make_workdir(), _make_config(tmp_path, context=sample_md))
    assert result.used is True
    assert result.source_path == str(sample_md)
    assert "MD context text" in result.text


def test_pdf_extraction(tmp_path: Path, sample_pdf: Path) -> None:
    """CTX-01: non-encrypted .pdf → ContextOutput(used=True) with non-empty text."""
    from avideo.stages.context import ContextStage  # noqa: PLC0415

    stage = ContextStage()
    result = stage.run(_make_workdir(), _make_config(tmp_path, context=sample_pdf))
    assert result.used is True
    assert result.text.strip() != ""


def test_pptx_extraction(tmp_path: Path, sample_pptx: Path) -> None:
    """CTX-01: .pptx → ContextOutput(used=True) with slide text."""
    from avideo.stages.context import ContextStage  # noqa: PLC0415

    stage = ContextStage()
    result = stage.run(_make_workdir(), _make_config(tmp_path, context=sample_pptx))
    assert result.used is True
    assert "PPTX context text" in result.text


def test_encrypted_pdf_raises(tmp_path: Path, encrypted_pdf: Path) -> None:
    """Encrypted PDF → raises ValueError mentioning password or protected."""
    from avideo.stages.context import ContextStage  # noqa: PLC0415

    stage = ContextStage()
    with pytest.raises(ValueError, match=r"[Pp]assword|[Pp]rotected"):
        stage.run(_make_workdir(), _make_config(tmp_path, context=encrypted_pdf))


def test_text_truncated_to_cap(tmp_path: Path) -> None:
    """Extracted text longer than token cap is truncated to cap_chars."""
    from avideo.stages.context import ContextStage, CONTEXT_TOKEN_CAP  # noqa: PLC0415

    # Create a very large .md file that exceeds the token cap
    cap_chars = CONTEXT_TOKEN_CAP * 4
    big_text = "A" * (cap_chars + 1000)
    big_md = tmp_path / "big.md"
    big_md.write_text(big_text, encoding="utf-8")

    stage = ContextStage()
    result = stage.run(_make_workdir(), _make_config(tmp_path, context=big_md))
    assert result.used is True
    assert len(result.text) <= cap_chars


def test_unsupported_suffix_raises(tmp_path: Path) -> None:
    """Unsupported file suffix → raises ValueError listing allowed suffixes."""
    from avideo.stages.context import ContextStage  # noqa: PLC0415

    bad_file = tmp_path / "context.docx"
    bad_file.write_text("content", encoding="utf-8")

    stage = ContextStage()
    with pytest.raises(ValueError):
        stage.run(_make_workdir(), _make_config(tmp_path, context=bad_file))


def test_stage_name_is_context() -> None:
    """ContextStage.stage_name must be 'context' (matches stub's checkpoint contract)."""
    from avideo.stages.context import ContextStage  # noqa: PLC0415

    assert ContextStage.stage_name == "context"
