"""Audio enhancement utility — FFmpeg-based denoise + loudnorm (VOZ-03).

Standalone function (NOT a pipeline stage). Called on demand from the UI
(Phase 12) or directly. Non-destructive: always writes to out_path;
never modifies in_path.

Filter chain (locked decision — 08-CONTEXT.md):
  afftdn=nr=6:nf=-25    — conservative FFT denoising (no model file; NOT arnndn).
                          nr=6 is conservative (default 12 is too aggressive).
                          nf=-25 is the noise floor threshold in dB.
  loudnorm=I=-16:TP=-1.5:LRA=11  — EBU R128 single-pass normalize.

CRITICAL (Pitfall 22 in PITFALLS.md):
  WhisperX / subtitle alignment ALWAYS runs on the ORIGINAL in_path.
  out_path is for the final assembled video only.
  Never use out_path as the alignment audio source.
"""
from __future__ import annotations

from pathlib import Path

from avideo.integrations.ffmpeg import run_ffmpeg


def enhance_audio(in_path: Path, out_path: Path) -> None:
    """Apply denoise + loudnorm enhancement via FFmpeg. Non-destructive.

    Runs FFmpeg with the conservative afftdn=nr=6:nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11
    filter chain (locked decision). Writes output to out_path; never touches in_path.

    Args:
        in_path: Original (unprocessed) audio file. NOT modified.
        out_path: New file for the enhanced output. Must differ from in_path.

    Note:
        Alignment (WhisperX/whisper-1) must always use in_path (the original),
        not out_path. The enhanced file is only for the final assembled video.
    """
    run_ffmpeg([
        "ffmpeg", "-hide_banner", "-y",
        "-i", str(in_path),
        "-af", "afftdn=nr=6:nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11",
        str(out_path),
    ])
