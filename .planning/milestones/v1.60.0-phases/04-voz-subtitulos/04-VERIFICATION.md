---
phase: 04-voz-subtitulos
verified: 2026-05-25T00:00:00Z
status: passed
score: 7/7 must-haves verified
overrides_applied: 0
verification_method: "Inline goal-backward verification by the autonomous orchestrator. Evidence: 241-test suite green (65 voice/subtitle tests), grep-confirmed seconds-API + lazy-import + pipeline swap, runtime check that whisperx/torch stay unimported on the default elevenlabs path."
---

# Phase 4: Voz + Subtítulos — Verification

**Goal:** El pipeline genera audio sincronizado por slide (ElevenLabs con timestamps o grabación del usuario) y produce subtítulos `.srt`/`.vtt` listos para el montaje.

**Status:** passed — 7/7 requirements verified.

## Requirement coverage (evidence)

| Req | Truth | Evidence | Status |
|-----|-------|----------|--------|
| VOICE-01 | elevenlabs per-slide mp3 with char timestamps | `integrations/elevenlabs.py` `synthesize_slide` (model eleven_multilingual_v2, voice_id config); words built from char timestamps; `VoiceElevenlabsStage` | ✅ |
| VOICE-02 | strictly-increasing timestamps validated, retry ≤3 | `is_strictly_increasing` reads `character_start_times_seconds`; retry + `VoiceTimestampError`; tests green | ✅ |
| VOICE-03 | record mode: segmented script + sounddevice/autodetect wav | `stages/voice_record.py` exports script, autodetects `slide_XX.wav` else records; mocked in tests | ✅ |
| ALIGN-01 | record: WhisperX word-level timings | `stages/align.py` record branch → `align_wav` (lazy whisperx) → words | ✅ |
| ALIGN-02 | elevenlabs: no alignment | `align.py` elevenlabs branch is idempotent no-op passthrough (align_wav NOT called — test-verified) | ✅ |
| SUB-01 | always generate output.srt + output.vtt | `utils/subtitle_format.py` `to_srt` (comma) + `to_vtt` (WEBVTT header); `SubtitlesStage` always writes both | ✅ |
| SUB-02 | burn-in optional (deferred to Phase 5) | burn_subs flag in RunConfig; Phase 4 only writes files even when burn_subs=True (test-verified) | ✅ |

## Quality gates

- **Tests:** 241 passed (`uv run pytest -q`); +94 over Phase 3 baseline. Targeted voice/subtitle/align/record: 65 passed.
- **CLAUDE.md:** Pydantic v2; ElevenLabs `convert_with_timestamps` using `*_seconds` (obsolete `*_ms` grep-forbidden); WhisperX lazy-imported (record-only); torch pin documented; record deps optional extra; all integrations mockable.
- **Lazy import verified at runtime:** importing `avideo.stages.voice` + `avideo.orchestrator` does NOT pull `whisperx` or `torch` (default elevenlabs path stays light).
- **UnifiedTimings (D-11):** single Pydantic contract both backends produce; `subtitles.py` is source-agnostic, reads the `align` checkpoint.
- **Checker warnings addressed during execution:** (1) record-mode per-slide duration guaranteed non-zero → no subtitle offset collapse; (2) `UnifiedTimings.words` populated from ElevenLabs char timestamps so SRT/VTT carry real narration text on the DEFAULT elevenlabs path (test-asserted), not placeholders; global per-slide offset accumulated (multi-slide offset test green).
- **Pipeline wired:** `VoiceStage`/`AlignStage`/`SubtitlesStage` replace stubs in `PIPELINE_STAGES` (stage_names voice/align/subs preserved). Remaining stubs: `verify` (Phase 6), `assemble` (Phase 5).

## Human verification (deferred, non-blocking)

Real ElevenLabs audio quality (needs ELEVENLABS_API_KEY), real WhisperX alignment on recorded audio, and live mic recording are best validated by a human. All automated + structural checks pass.
