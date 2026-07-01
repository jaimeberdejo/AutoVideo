---
status: verified
phase: 13-extras-ensamblaje-polish
started: 2026-07-01T11:48:00Z
updated: 2026-07-01T12:31:00Z
---

## Tests

### 1. Extras widgets (subtitles, music, crossfade)
expected: Fase 5 shows a subtitle burn-in checkbox, music upload + volume/fade sliders, and a crossfade slider; all optional (approve without any selected).
result: PASS — verified live. Enabled "Quemar subtítulos en el vídeo" and approved with defaults for music/crossfade.

### 2. Fase 6 assembly is non-blocking with live progress
expected: "Montar vídeo" launches SubtitlesStage (if burn_subs) + AssembleStage via the bridge; a 2s-polling fragment shows progress without freezing the UI.
result: PASS (after 2 fixes) — real FFmpeg assembly, with real narration audio + burned subtitles, initially failed on EVERY run with "Unable to choose an output format for '...output.mp4.tmp'" because the atomic-write temp file had `.tmp` as its final extension (ffmpeg infers container format from the filename extension). Fixed in `stages/assemble.py` + `integrations/ffmpeg.py` (temp files renamed to `output.tmp.mp4` / `output.norm.tmp.mp4`, keeping `.mp4` as the final extension). Also found and fixed the same "button stuck disabled after error" bug as Fase 4's voice synthesis (same root cause, same fix pattern). Also fixed a silent-wrong-duration fallback: if `run_config` is missing `duration` this page used to default to 60s and assemble silently against the wrong target with no warning — now shows a clear error directing the user back to Fase 1.
result (continued): after fixes, produced a real playable 1920x1080 H.264/AAC MP4 (54.4s for a 60s target — 5.6s deviation, within expectation given real TTS speech rate vs the WPM estimate).

### 3. Video player + download + QA report
expected: On completion, `st.video` plays the result, a download button serves `output.mp4`, and QA metrics (duration deviation, LUFS) are shown.
result: PASS (after 1 correctness fix) — player and download button both worked. Found and fixed a QA correctness bug: `normalized_lufs` was read from the wrong JSON field (`input_i`, the PRE-normalization loudness) instead of `output_i` (the actual post-normalization result), so the QA report always showed `normalized_lufs == measured_lufs` (e.g. both -29.5 LUFS) even when the real audio was correctly normalized to ~-16 LUFS — verified by independently re-measuring the produced `output.mp4`'s actual loudness, which was ~-16 LUFS as expected. Fixed in `integrations/ffmpeg.py` (`parse_loudnorm_json` now also returns `output_i`) and `stages/assemble.py` (both the two-pass and single-pass-with-music code paths).

### 4. Back-nav invalidation from Fase 6
expected: Going back from Fase 6 invalidates the assemble done-marker.
result: PASS — see phase 09 UAT item 3 (same session, same click sequence).

## Not exercised in this session
- Background music upload + mix (ducking/fade) — widgets present, not exercised with a real uploaded track.
- Docker build verification (`docker build -t avideo-test .`) — not run in this session.

## Summary

total: 4
passed: 4
issues: 0 (3 blockers/bugs found — fixed, see main report)
pending: 0
skipped: 2 (music mix, docker build)
