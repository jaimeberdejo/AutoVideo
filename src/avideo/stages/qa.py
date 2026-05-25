"""Pure QA logic for Phase 5 — duration deviation and QAReport construction.

This module contains ONLY pure computations and model construction.  It does
NOT invoke subprocess, ffmpeg, or any I/O.  Subprocess calls (running two-pass
loudnorm) live in ``integrations/ffmpeg.py`` and are wired by
``stages/assemble.py`` as a sub-step of ``AssembleStage.run``.

Per 05-RESEARCH Open Question 1: QA runs as a sub-step inside AssembleStage
(single ``assembly`` checkpoint, single idempotence boundary — D-10).

Design references (from 05-CONTEXT.md):
    D-06  Two-pass loudnorm (EBU R128); measured and normalized LUFS stored.
    D-07  QAReport: deviation (actual - target) + measured/normalized LUFS.
    D-10  Reanudable/idempotente.

Threat mitigations (from 05-02 threat model):
    T-05-07  parse_loudnorm_json lives in integrations/ffmpeg.py; this module
             only receives already-parsed float values — no raw stderr here.
"""
from __future__ import annotations

from avideo.models.assembly import QAReport


def duration_deviation(actual_seconds: float, target_seconds: float) -> float:
    """Compute the signed duration deviation between actual and target.

    Deviation = actual_seconds − target_seconds.
    Positive means the video is longer than requested; negative means shorter.
    Never use strict equality in QA assertions — use :func:`within_tolerance`
    instead (Pitfall 7: ±1-frame overshoot from ffmpeg crossfade math).

    Args:
        actual_seconds: Real video duration from ffprobe on output.mp4.
        target_seconds: Target duration from RunConfig.duration.

    Returns:
        Signed deviation in seconds (float).
    """
    return actual_seconds - target_seconds


def within_tolerance(deviation: float, tol: float = 0.5) -> bool:
    """Return True if abs(deviation) is within the acceptable tolerance.

    Default tolerance is 0.5 s — permissive enough to absorb the ±1-frame
    overshoot from xfade math (Pitfall 7) plus minor encoder rounding.
    The QA Rich table uses this flag to colour-code the deviation row.

    Args:
        deviation: Signed deviation in seconds (from :func:`duration_deviation`).
        tol:       Maximum acceptable absolute deviation (default 0.5 s).

    Returns:
        True if ``abs(deviation) <= tol``; False otherwise.
    """
    return abs(deviation) <= tol


def build_qa_report(
    target_seconds: float,
    actual_seconds: float,
    measured_lufs: float | None,
    normalized_lufs: float | None,
) -> QAReport:
    """Construct a QAReport from duration and loudness measurements.

    Computes ``duration_deviation`` internally so callers only supply the
    raw measurements.  Both LUFS fields are optional to allow partial reports
    when loudnorm is skipped (e.g. when ffmpeg is unavailable in tests).

    Args:
        target_seconds:   Target video duration (RunConfig.duration cast to float).
        actual_seconds:   Real video duration from ffprobe on output.mp4.
        measured_lufs:    Pre-normalization LUFS (pass-1 ``input_i``); None if not run.
        normalized_lufs:  Post-normalization LUFS (pass-2 ``output_i`` or re-measured);
                          None if not run.

    Returns:
        A fully populated :class:`~avideo.models.assembly.QAReport`.
    """
    dev = duration_deviation(actual_seconds=actual_seconds, target_seconds=target_seconds)
    return QAReport(
        target_seconds=target_seconds,
        actual_seconds=actual_seconds,
        duration_deviation=dev,
        measured_lufs=measured_lufs,
        normalized_lufs=normalized_lufs,
    )
