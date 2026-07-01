# Phase 8: Backend Integrations - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning
**Mode:** Smart-discuss auto-accepted (autonomous run; grey areas resolved from .planning/research/SUMMARY.md + STATE.md decisions)

<domain>
## Phase Boundary

Implement the three NEW backend capabilities for v2.0.0 — (1) OpenAI Audio TTS as a third voice provider, (2) automatic audio enhancement for user-uploaded recordings, (3) background music mixing — fully testable WITHOUT any Streamlit code. Reuse the existing pipeline (stages, WorkdirManager, integrations/ffmpeg.py, UnifiedTimings); do NOT rewrite the pipeline and do NOT add UI here. The 303 existing tests must stay green. Covers VOZ-02, VOZ-03, EXT-02, EXT-03.

</domain>

<decisions>
## Implementation Decisions

### OpenAI Audio TTS (VOZ-02)
- New stage `stages/voice_openai.py` selected by a new `VoiceMode.openai` branch in the existing VoiceStage dispatcher; output contract is the SAME `UnifiedTimings` as elevenlabs/record (so subtitles/assembly are unchanged).
- Synthesis via `openai` SDK: `client.audio.speech.create(model="tts-1"/"gpt-4o-mini-tts", voice=<config>, input=<slide text>)`, one clip per slide, written to `workdir/audio/slide_XX.*`.
- OpenAI TTS returns NO timestamps → mandatory STT round-trip on the generated audio: `client.audio.transcriptions.create(model="whisper-1", response_format="verbose_json", timestamp_granularities=["word"])`. Use `whisper-1` specifically (gpt-4o-transcribe lacks word timestamps). Map word objects → existing WordTiming/UnifiedTimings.
- Enforce the 4096-char per-request limit per slide (split/guard); `OPENAI_API_KEY` from `.env`/config; lazy client, max_retries=3 (mirror the anthropic/elevenlabs integration pattern).
- New dep `openai>=2.38.0`; promote `python-dotenv` from dev to core dependencies.

### Audio Enhancement (VOZ-03)
- FFmpeg-only — `utils/audio_enhance.py` as a plain function (NOT a pipeline stage), `enhance_audio(in_path, out_path)`. NO `noisereduce`/`pedalboard` (no compiled deps).
- Filter chain: conservative denoise `afftdn=nr=6:nf=-25` + `loudnorm` (do not use aggressive `arnndn`/`afftdn` defaults; no `.rnnn` model file).
- Non-destructive: writes a NEW output file; the original upload is never modified.
- CRITICAL: WhisperX/subtitle alignment always runs on the ORIGINAL unprocessed audio; the enhanced file is for the final video only.

### Background Music (EXT-02, EXT-03)
- New `build_music_mix_args()` in `integrations/ffmpeg.py` + a new `RunConfig` field (e.g. `bg_music_path`, `bg_music_volume`) consumed by `AssembleStage`. PIPELINE_STAGES length/order unchanged.
- Mix: `amix=inputs=2:normalize=0` ALWAYS (never default normalize=1, which drops both tracks -6 dB); music level via explicit `volume=` (default ~0.10–0.15) before amix; ducking via `sidechaincompress` (music keyed by narration).
- Fades: `afade` in/out; fade-out timing computed from the ffprobe-MEASURED actual duration of the assembled video, not the config target.
- Loudness: exactly ONE loudnorm pass on the FINAL mixed track when music is present; skip the per-narration loudnorm in that path to avoid double-normalization/pumping.

### Claude's Discretion
- Exact OpenAI TTS model id (tts-1 vs gpt-4o-mini-tts) and default voice — pick sensible defaults, expose via config.
- Default music `volume` and `sidechaincompress` params — choose musical defaults; make configurable.
- Test structure mirroring existing `tests/` conventions (mock OpenAI SDK + ffmpeg subprocess; no real network/binary calls).

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/avideo/stages/` VoiceStage dispatcher (elevenlabs/record branches) — add openai branch.
- `src/avideo/integrations/ffmpeg.py` — fluent arg-list builder (NEVER shell=True), loudnorm two-pass, xfade/concat helpers — extend with music mix.
- `src/avideo/integrations/anthropic.py` / `elevenlabs.py` — lazy-client + retry pattern to mirror for the openai client.
- `models/timings.py` UnifiedTimings / WordTiming — target contract for the OpenAI STT round-trip.
- WorkdirManager — atomic tmp→rename, done markers, idempotent checkpoints.

### Established Patterns
- Pydantic v2 models, typed + docstring'd; subprocess with arg lists; atomic writes; idempotent stages; SVG-only visuals (n/a here).
- Tests mock all external APIs/binaries; smoke tests skip when binaries absent.

### Integration Points
- VoiceStage dispatcher (new openai branch); RunConfig (new fields: openai voice/model, bg_music_path, bg_music_volume, enhance toggle); AssembleStage (music mix path); pyproject.toml (openai dep, python-dotenv to core).

</code_context>

<specifics>
## Specific Ideas

Implementation-ready guidance (with code) is in `.planning/research/ARCHITECTURE.md`, `STACK.md`, and `PITFALLS.md`. Follow the cross-cutting invariants in `SUMMARY.md`. Keep everything headless/CLI-testable — Streamlit comes in Phase 9.

</specifics>

<deferred>
## Deferred Ideas

- The UI button that triggers audio enhancement and the provider-selection UX are Phase 12 (Voz Page) — here we ship only the callable `enhance_audio()` function + the openai voice stage + the music mix backend.
- Streamlit wiring, progress, previews → Phase 9+.

</deferred>
