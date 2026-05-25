"""Subtitle format utilities — pure serialization and cue segmentation (SUB-01).

This module contains ONLY pure logic: no I/O, no network calls, no Pydantic model
validation beyond what is needed for type annotations.  It is the testable heart
of Phase 4's subtitle generation.

Key functions:
    fmt_ts      — format a float seconds value as HH:MM:SS,mmm (SRT) or HH:MM:SS.mmm (VTT)
    to_srt      — serialize a list of Cue objects to SRT format
    to_vtt      — serialize a list of Cue objects to VTT format (with WEBVTT header)
    segment_words — segment a list of WordTiming objects into Cue objects with constraints

Cue constraints (D-08 + RESEARCH Pitfall 6):
    - ~42 chars per line
    - ≤ 2 lines per cue
    - ≤ 5 seconds per cue
    - ≤ 17 CPS (characters per second) for readability

Design (RESEARCH "Don't Hand-Roll" key insight):
    Generating both SRT and VTT from the same Cue model is the correct approach —
    hand-rolling regex conversion between formats is fragile and bug-prone.
    Both formats are derived from the same list[Cue], with only the timestamp
    separator (comma vs dot) and the absence/presence of a numeric index differing.

Security (T-04-09, T-04-10):
    Text comes from Phase 2 script (Pydantic-validated); it is written as plain text
    (not executed).  All path construction happens in stages/subtitles.py using
    workdir.root — this module has no filesystem access.
"""
from __future__ import annotations

import textwrap
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from avideo.models.timings import WordTiming


@dataclass
class Cue:
    """A single subtitle cue with start/end timestamps and display text.

    Attributes:
        start: Cue start time in seconds (global video timeline).
        end: Cue end time in seconds (global video timeline).
        text: Display text; multi-line cues use ``"\\n"`` as the line separator.
            At most 2 lines; each line ≤ ~42 characters.
    """

    start: float
    end: float
    text: str


def fmt_ts(seconds: float, *, vtt: bool) -> str:
    """Format a timestamp in seconds to SRT or VTT notation.

    SRT uses a comma as the decimal separator (HH:MM:SS,mmm).
    VTT uses a dot as the decimal separator (HH:MM:SS.mmm).

    Args:
        seconds: Timestamp in seconds (non-negative float).
        vtt: If True, use dot separator (VTT); if False, use comma (SRT).

    Returns:
        Formatted timestamp string, e.g. ``"01:02:03,456"`` or ``"01:02:03.456"``.

    Examples:
        >>> fmt_ts(3661.5, vtt=False)
        '01:01:01,500'
        >>> fmt_ts(3661.5, vtt=True)
        '01:01:01.500'
    """
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    # Guard against ms rounding to 1000 (e.g. 1.9995 rounds to 2000ms)
    if ms >= 1000:
        ms -= 1000
        s += 1
        if s >= 60:
            s -= 60
            m += 1
            if m >= 60:
                m -= 60
                h += 1
    sep = "." if vtt else ","
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def to_srt(cues: list[Cue]) -> str:
    """Serialize a list of Cue objects to SRT (SubRip Subtitle) format.

    SRT format:
        <index>
        HH:MM:SS,mmm --> HH:MM:SS,mmm
        <text>
        <blank line>

    Indices are 1-based.  Text may contain ``\\n`` for multi-line cues.

    Args:
        cues: Ordered list of subtitle cues.

    Returns:
        SRT-formatted string.  Empty string if ``cues`` is empty.
    """
    if not cues:
        return ""
    out: list[str] = []
    for i, cue in enumerate(cues, start=1):
        out.append(str(i))
        out.append(f"{fmt_ts(cue.start, vtt=False)} --> {fmt_ts(cue.end, vtt=False)}")
        out.append(cue.text)
        out.append("")  # blank line between cues
    return "\n".join(out)


def to_vtt(cues: list[Cue]) -> str:
    """Serialize a list of Cue objects to WebVTT format.

    VTT format:
        WEBVTT
        <blank line>
        HH:MM:SS.mmm --> HH:MM:SS.mmm
        <text>
        <blank line>

    No numeric indices are used (they are optional in WebVTT and not added here).

    Args:
        cues: Ordered list of subtitle cues.

    Returns:
        WebVTT-formatted string, always starting with ``"WEBVTT\\n"``.
    """
    out: list[str] = ["WEBVTT", ""]  # header + blank line
    for cue in cues:
        out.append(f"{fmt_ts(cue.start, vtt=True)} --> {fmt_ts(cue.end, vtt=True)}")
        out.append(cue.text)
        out.append("")  # blank line between cues
    return "\n".join(out)


def _wrap_to_lines(text: str, max_chars_per_line: int) -> str:
    """Wrap ``text`` to at most 2 lines of ``max_chars_per_line`` each.

    Uses ``textwrap.wrap`` for clean word-boundary wrapping, then takes the
    first two wrapped lines.  If the text is a single very long word, it is
    left on one line without truncation.

    Args:
        text: The text to wrap (may already contain spaces).
        max_chars_per_line: Maximum characters per line.

    Returns:
        Text with at most one ``"\\n"`` in it (≤ 2 lines).
    """
    if len(text) <= max_chars_per_line:
        return text
    lines = textwrap.wrap(text, width=max_chars_per_line, break_long_words=False, break_on_hyphens=False)
    if not lines:
        return text
    # Take at most 2 lines
    return "\n".join(lines[:2])


def segment_words(
    words: "list[WordTiming]",
    *,
    max_chars_per_line: int = 42,
    max_lines: int = 2,
    max_cue_seconds: float = 5.0,
    max_cps: float = 17.0,
) -> list[Cue]:
    """Segment a list of word timings into subtitle cues.

    Groups consecutive ``WordTiming`` objects into ``Cue`` objects.  A new cue
    is started whenever adding the next word would violate any of the following
    constraints:

    - **Chars per line**: total chars in the current cue's text would exceed
      ``max_chars_per_line * max_lines`` (≈ the maximum displayable content).
    - **Duration**: ``word.end - cue_start`` would exceed ``max_cue_seconds``.
    - **CPS**: ``(total_chars + len(word)) / (word.end - cue_start)`` > ``max_cps``
      (only when the duration window is non-zero).

    Edge cases:
    - Empty ``words`` → returns ``[]``.
    - A single word that exceeds all limits by itself is still placed in one cue
      (text is never lost — the word must appear somewhere).

    Args:
        words: List of ``WordTiming`` objects with ``text``, ``start``, ``end``
            (all in seconds, already offset-adjusted to global timeline by the
            calling stage — this function treats them as absolute timestamps).
        max_chars_per_line: Maximum characters per display line (~42 for TV).
        max_lines: Maximum lines per cue (2 for standard subtitles).
        max_cue_seconds: Maximum cue duration in seconds (5.0 standard).
        max_cps: Maximum characters per second for readability (17.0 broadcast).

    Returns:
        Ordered list of ``Cue`` objects covering all input words without gaps or
        lost text.
    """
    if not words:
        return []

    max_total_chars = max_chars_per_line * max_lines  # e.g. 84 for 2×42

    cues: list[Cue] = []
    # Accumulator for the current cue
    current_words: list[WordTiming] = []
    current_text = ""  # text built so far in this cue (words joined by spaces)

    for word in words:
        if not current_words:
            # First word always starts a cue — never discard
            current_words.append(word)
            current_text = word.text
            continue

        # Tentative text if we include this word
        tentative_text = current_text + " " + word.text
        tentative_chars = len(tentative_text)
        cue_start = current_words[0].start
        cue_end_tentative = word.end
        duration = cue_end_tentative - cue_start

        # Check all four constraints
        exceeds_chars = tentative_chars > max_total_chars
        exceeds_duration = duration > max_cue_seconds
        exceeds_cps = (duration > 0) and (tentative_chars / duration > max_cps)

        if exceeds_chars or exceeds_duration or exceeds_cps:
            # Flush the current cue
            cue_text = _wrap_to_lines(current_text, max_chars_per_line)
            cues.append(Cue(
                start=current_words[0].start,
                end=current_words[-1].end,
                text=cue_text,
            ))
            # Start fresh with the current word
            current_words = [word]
            current_text = word.text
        else:
            current_words.append(word)
            current_text = tentative_text

    # Flush the last cue (always has at least one word)
    if current_words:
        cue_text = _wrap_to_lines(current_text, max_chars_per_line)
        cues.append(Cue(
            start=current_words[0].start,
            end=current_words[-1].end,
            text=cue_text,
        ))

    return cues
