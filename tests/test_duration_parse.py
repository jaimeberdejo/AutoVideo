"""Tests for mm:ss duration parsing/formatting (Fase 1 duration input)."""
from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "text,expected",
    [
        ("330", 330),       # bare seconds
        ("5:30", 330),      # mm:ss
        ("0:45", 45),       # leading zero minutes
        ("12:00", 720),     # exact minutes
        ("1:00:00", 3600),  # h:mm:ss
        ("  2:00 ", 120),   # surrounding whitespace
    ],
)
def test_parse_duration_valid(text, expected):
    from avideo.stages.bullets_gen import parse_duration  # noqa: PLC0415

    assert parse_duration(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",          # empty
        "   ",       # blank
        "abc",       # non-numeric
        "5m30s",     # unsupported format
        "5:99",      # seconds >= 60
        "1:99:00",   # minutes >= 60
        "1:2:3:4",   # too many parts
        "-30",       # negative
    ],
)
def test_parse_duration_invalid(text):
    from avideo.stages.bullets_gen import parse_duration  # noqa: PLC0415

    with pytest.raises(ValueError):
        parse_duration(text)


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (330, "5:30"),
        (90, "1:30"),
        (45, "0:45"),
        (3600, "1:00:00"),
        (3661, "1:01:01"),
    ],
)
def test_format_duration(seconds, expected):
    from avideo.stages.bullets_gen import format_duration  # noqa: PLC0415

    assert format_duration(seconds) == expected
