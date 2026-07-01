# Phase 8: Backend Integrations - Research

**Researched:** 2026-05-29
**Domain:** Python pipeline extension — OpenAI Audio TTS + FFmpeg audio enhancement + FFmpeg background music mixing
**Confidence:** HIGH (all integration points verified against live source code; stack decisions carried from milestone research at HIGH confidence)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**OpenAI Audio TTS (VOZ-02)**
- New stage `stages/voice_openai.py` selected by a new `VoiceMode.openai` branch in the existing VoiceStage dispatcher; output contract is the SAME `UnifiedTimings` as elevenlabs/record (so subtitles/assembly are unchanged).
- Synthesis via `openai` SDK: `client.audio.speech.create(model="tts-1"/"gpt-4o-mini-tts", voice=<config>, input=<slide text>)`, one clip per slide, written to `workdir/audio/slide_XX.*`.
- OpenAI TTS returns NO timestamps → mandatory STT round-trip on the generated audio: `client.audio.transcriptions.create(model="whisper-1", response_format="verbose_json", timestamp_granularities=["word"])`. Use `whisper-1` specifically (gpt-4o-transcribe lacks word timestamps). Map word objects → existing WordTiming/UnifiedTimings.
- Enforce the 4096-char per-request limit per slide (split/guard); `OPENAI_API_KEY` from `.env`/config; lazy client, max_retries=3 (mirror the anthropic/elevenlabs integration pattern).
- New dep `openai>=2.38.0`; promote `python-dotenv` from dev to core dependencies.

**Audio Enhancement (VOZ-03)**
- FFmpeg-only — `utils/audio_enhance.py` as a plain function (NOT a pipeline stage), `enhance_audio(in_path, out_path)`. NO `noisereduce`/`pedalboard` (no compiled deps).
- Filter chain: conservative denoise `afftdn=nr=6:nf=-25` + `loudnorm` (do not use aggressive `arnndn`/`afftdn` defaults; no `.rnnn` model file).
- Non-destructive: writes a NEW output file; the original upload is never modified.
- CRITICAL: WhisperX/subtitle alignment always runs on the ORIGINAL unprocessed audio; the enhanced file is for the final video only.

**Background Music (EXT-02, EXT-03)**
- New `build_music_mix_args()` in `integrations/ffmpeg.py` + a new `RunConfig` field (e.g. `bg_music_path`, `bg_music_volume`) consumed by `AssembleStage`. PIPELINE_STAGES length/order unchanged.
- Mix: `amix=inputs=2:normalize=0` ALWAYS (never default normalize=1, which drops both tracks -6 dB); music level via explicit `volume=` (default ~0.10–0.15) before amix; ducking via `sidechaincompress` (music keyed by narration).
- Fades: `afade` in/out; fade-out timing computed from the ffprobe-MEASURED actual duration of the assembled video, not the config target.
- Loudness: exactly ONE loudnorm pass on the FINAL mixed track when music is present; skip the per-narration loudnorm in that path to avoid double-normalization/pumping.

### Claude's Discretion
- Exact OpenAI TTS model id (tts-1 vs gpt-4o-mini-tts) and default voice — pick sensible defaults, expose via config.
- Default music `volume` and `sidechaincompress` params — choose musical defaults; make configurable.
- Test structure mirroring existing `tests/` conventions (mock OpenAI SDK + ffmpeg subprocess; no real network/binary calls).

### Deferred Ideas (OUT OF SCOPE)
- The UI button that triggers audio enhancement and the provider-selection UX are Phase 12 (Voz Page) — here we ship only the callable `enhance_audio()` function + the openai voice stage + the music mix backend.
- Streamlit wiring, progress, previews → Phase 9+.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| VOZ-02 | OpenAI Audio sintetiza la voz por slide; round-trip STT (`whisper-1`, word-level) para subtítulos sincronizados | `integrations/openai.py` (lazy client, lazy import), `stages/voice_openai.py` (CheckpointMixin, source="openai"), `VoiceMode.openai` enum value, `VoiceStage` openai branch — all integration points identified in source |
| VOZ-03 | Para audios subidos por el usuario, mejora automática (denoise + normalización, FFmpeg); la alineación usa el audio original sin procesar | `utils/audio_enhance.py` standalone function; `afftdn=nr=6:nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11` via `run_ffmpeg()`; no new stage; alignment order critical |
| EXT-02 | Música de fondo (archivo) mezclada bajo narración con ducking + fade in/out | `build_music_mix_args()` in `integrations/ffmpeg.py`; `RunConfig.bg_music_path` + `bg_music_volume` new fields; consumed by `AssembleStage._run_music_mix()` |
| EXT-03 | La música no degrada el loudness de la narración — sola pasada loudnorm sobre la mezcla final | `AssembleStage._run_qa()` skips per-narration loudnorm when `config.bg_music_path` is set; single loudnorm on the mix output; `amix=inputs=2:normalize=0` enforced in builder |
</phase_requirements>

---

## Summary

Phase 8 is a pure backend extension of the existing v1.60.0 pipeline. It adds three independent capabilities that share zero UI code and are fully testable from the CLI and from pytest. The phase reads against a well-understood codebase: 303 passing tests, live source code read in this session, and HIGH-confidence milestone research already translated into locked decisions. No exploratory research is needed — this document translates existing decisions into precise, file-level planning guidance.

The three features map to four new or modified files plus two model changes. OpenAI Audio (`integrations/openai.py` + `stages/voice_openai.py`) follows the exact same lazy-client + retry pattern established in `integrations/elevenlabs.py`. Audio enhancement (`utils/audio_enhance.py`) is a three-line wrapper around `run_ffmpeg()` which already exists. Background music (`build_music_mix_args()` in `integrations/ffmpeg.py` + `AssembleStage` modification) slots into the existing arg-builder pattern — `build_assemble_args()` already returns a `list[str]` that maps cleanly to a new optional music-mix pre-pass or a filter_complex extension.

The highest-risk decision for planning is the loudnorm bypass in `AssembleStage._run_qa()`: when `config.bg_music_path` is set, the existing two-pass loudnorm must be skipped on the narration-only track and applied once on the final mixed output. This requires surgical modification to `assemble.py`'s `_run_qa()` without breaking the existing loudnorm path for the no-music case.

**Primary recommendation:** Build the three features in dependency order — (1) model changes (`RunConfig` + `VoiceMode`), (2) OpenAI integration, (3) audio enhancement utility, (4) music mix builder, (5) assemble extension — with mocked unit tests for each. The 303 existing tests remain green because all changes are additive (new enum value, new optional config fields, new functions) or branch-guarded.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| OpenAI TTS synthesis (per slide) | API/Backend (pipeline stage) | — | Mirrors elevenlabs stage pattern; pure I/O with no UI concern |
| Whisper-1 STT round-trip for timestamps | API/Backend (inside voice_openai stage) | — | Required to produce the same UnifiedTimings contract as ElevenLabs; done inside the stage, invisible to orchestrator |
| Audio enhancement (denoise+normalize) | Utility function (not a stage) | — | Stateless transform; called on demand, not in the PIPELINE_STAGES loop |
| Background music mixing | Pipeline stage (AssembleStage) | integrations/ffmpeg.py builder | Assembly already owns all audio mixing; music is an additional audio input, not a separate stage |
| Loudnorm bypass when music present | Pipeline stage (AssembleStage._run_qa) | — | The QA sub-step must conditionally skip per-narration loudnorm and apply it post-mix instead |
| New config fields | Model layer (models/config.py) | — | Pydantic settings pattern; consistent with existing RunConfig approach |

---

## Standard Stack

### Core (no changes — confirmed from pyproject.toml)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `openai` | `>=2.38.0` | OpenAI Audio TTS + Whisper-1 STT | NEW dep; official SDK; `audio.speech.create` + `audio.transcriptions.create` [VERIFIED: PyPI, milestone STACK.md] |
| `python-dotenv` | `>=1.0` | Load `OPENAI_API_KEY` at runtime | PROMOTE from `[dev]` to `[project.dependencies]`; already in dev group [VERIFIED: pyproject.toml line 63] |
| `ffmpeg` binary | `>=6.1` | `afftdn`, `sidechaincompress`, `afade`, `amix`, `loudnorm` filters | Already a hard dependency; all new filters are built-in to ffmpeg >=6.1 [VERIFIED: STACK.md, PITFALLS.md] |
| `pydantic` | `>=2.13.4` | `RunConfig` new optional fields | Already in dependencies; `Optional[Path]` fields with `None` default are additive and backward-compatible [VERIFIED: pyproject.toml] |

### No New Supporting Libraries

Per locked decisions: no `noisereduce`, `pedalboard`, `pydub`, `ffmpeg-python`, `ffmpeg-normalize`, or WhisperX for the OpenAI path. All audio processing is via `run_ffmpeg()` from `integrations/ffmpeg.py`.

**pyproject.toml changes:**

```toml
# In [project.dependencies] — ADD:
"openai>=2.38.0",
"python-dotenv>=1.0",

# In [dependency-groups] dev — REMOVE:
# "python-dotenv>=1.0",  ← move to project.dependencies above
```

---

## Architecture Patterns

### System Architecture Diagram

```
RunConfig
 (voice=openai,            AssembleStage.run()
  bg_music_path,           ├── reads voice checkpoint (UnifiedTimings)
  bg_music_volume)         ├── probe real durations (ffprobe)
        │                  ├── build_assemble_args() → ffmpeg encode
        │                  ├── if bg_music_path:
        ▼                  │     build_music_mix_args() → ffmpeg music mix
VoiceStage.run()           │     skip per-narration loudnorm
  │                        │     loudnorm pass-1+2 on mixed output
  ├── VoiceMode.elevenlabs → VoiceElevenlabsStage (unchanged)
  │
  ├── VoiceMode.record    → VoiceRecordStage (unchanged)
  │
  └── VoiceMode.openai   → VoiceOpenAIStage
          │
          ├── integrations/openai.py: synthesize_slide_openai()
          │     openai.audio.speech.create(model, voice, text)
          │     → write workdir/audio/slide_XX.mp3
          │
          └── integrations/openai.py: transcribe_slide_openai()
                openai.audio.transcriptions.create(
                  model="whisper-1",
                  response_format="verbose_json",
                  timestamp_granularities=["word"]
                )
                → map word objects → WordTiming → SlideTimings → UnifiedTimings


utils/audio_enhance.py
  enhance_audio(in_path, out_path)
    run_ffmpeg([
      "ffmpeg", "-i", in_path,
      "-af", "afftdn=nr=6:nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11",
      out_path
    ])
  NOTE: never called automatically by pipeline;
        called on demand (Phase 12 UI / direct function call)
```

### Recommended Project Structure

```
src/avideo/
├── models/
│   └── config.py              MODIFIED: VoiceMode.openai + RunConfig.bg_music_path + bg_music_volume
├── stages/
│   ├── voice.py               MODIFIED: add openai branch (3 lines)
│   └── voice_openai.py        NEW: VoiceOpenAIStage
├── integrations/
│   ├── openai.py              NEW: synthesize_slide_openai() + transcribe_slide_openai()
│   └── ffmpeg.py              MODIFIED: build_music_mix_args() + assemble loudnorm-bypass param
├── utils/
│   └── audio_enhance.py       NEW: enhance_audio(in_path, out_path)
└── stages/
    └── assemble.py            MODIFIED: music pre-pass + loudnorm bypass
tests/
├── test_voice_openai.py       NEW
├── test_audio_enhance.py      NEW
└── test_assemble.py           EXISTING: extend with music_mix_args tests
```

### Pattern 1: OpenAI Lazy Client (mirrors elevenlabs.py)

```python
# src/avideo/integrations/openai.py
from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from avideo.models.timings import SlideTimings

_client = None

def _get_client():
    """Lazy singleton — never instantiates at import time (no OPENAI_API_KEY needed for tests)."""
    global _client
    if _client is None:
        from openai import OpenAI  # lazy import
        _client = OpenAI(max_retries=3)  # mirror elevenlabs retry pattern
    return _client

def synthesize_slide_openai(
    *,
    text: str,
    slide_index: int,
    model: str,   # "tts-1" | "gpt-4o-mini-tts"
    voice: str,   # "alloy" | "echo" | "fable" | "onyx" | "nova" | "shimmer"
    out_path: Path,
) -> Path:
    """Synthesize one slide's narration via OpenAI Audio TTS.

    Enforces the 4096-char limit (Pitfall 18): raises ValueError if text exceeds it.
    Writes raw MP3 bytes to out_path. Returns out_path.
    """
    if len(text) > 4096:
        raise ValueError(
            f"Slide {slide_index} text is {len(text)} chars; OpenAI TTS limit is 4096. "
            "The storyboard WPM budget should keep slides well under this limit."
        )
    response = _get_client().audio.speech.create(
        model=model, voice=voice, input=text, response_format="mp3"
    )
    response.stream_to_file(str(out_path))
    return out_path

def transcribe_slide_openai(
    *,
    audio_path: Path,
    slide_index: int,
) -> "SlideTimings":
    """STT round-trip on the generated audio to obtain word-level timestamps.

    Uses whisper-1 with verbose_json + word granularity.
    NOTE: gpt-4o-transcribe does NOT support word timestamps (Pitfall 17).
    Returns SlideTimings with words populated.
    Duration is derived from the last word's end time or ffprobe fallback.
    """
    from avideo.models.timings import SlideTimings, WordTiming
    with open(audio_path, "rb") as f:
        result = _get_client().audio.transcriptions.create(
            file=f,
            model="whisper-1",
            response_format="verbose_json",
            timestamp_granularities=["word"],
        )
    words = [
        WordTiming(text=w.word, start=w.start, end=w.end)
        for w in (result.words or [])
    ]
    duration = words[-1].end if words else 0.0
    return SlideTimings(
        slide_index=slide_index,
        audio_path=str(audio_path),
        duration=duration,
        words=words,
    )
# Source: [VERIFIED: milestone research STACK.md, ARCHITECTURE.md]
```

### Pattern 2: VoiceOpenAIStage (mirrors VoiceElevenlabsStage)

```python
# src/avideo/stages/voice_openai.py
from avideo.integrations.openai import synthesize_slide_openai, transcribe_slide_openai
from avideo.models.script import ScriptOutput
from avideo.models.timings import UnifiedTimings
from avideo.stages.base import CheckpointMixin

class VoiceOpenAIStage(CheckpointMixin):
    stage_name: str = "voice"  # SAME checkpoint contract as ElevenLabs (D-12)

    def run(self, workdir, config) -> UnifiedTimings:
        script: ScriptOutput = workdir.read_checkpoint("script", ScriptOutput)
        audio_dir = workdir.root / "audio"
        audio_dir.mkdir(exist_ok=True)
        slides = []
        for slide in script.slides:
            out_path = audio_dir / f"slide_{slide.slide_index:02d}.mp3"
            # Step 1: synthesize
            synthesize_slide_openai(
                text=slide.narration,
                slide_index=slide.slide_index,
                model=getattr(config, "openai_tts_model", "tts-1"),
                voice=getattr(config, "openai_tts_voice", "nova"),
                out_path=out_path,
            )
            # Step 2: STT round-trip for word timestamps
            slide_timings = transcribe_slide_openai(
                audio_path=out_path,
                slide_index=slide.slide_index,
            )
            slides.append(slide_timings)
        return UnifiedTimings(source="openai", slides=slides)
# Source: [VERIFIED: existing VoiceElevenlabsStage pattern in source]
```

### Pattern 3: VoiceStage dispatcher extension (3-line change)

```python
# src/avideo/stages/voice.py — in VoiceStage.run(), after the record branch:
if config.voice == VoiceMode.openai:
    from avideo.stages.voice_openai import VoiceOpenAIStage  # lazy import
    return VoiceOpenAIStage().run(workdir, config)
# Source: [VERIFIED: existing voice.py dispatcher pattern in source]
```

### Pattern 4: audio_enhance.py (standalone utility)

```python
# src/avideo/utils/audio_enhance.py
from pathlib import Path
from avideo.integrations.ffmpeg import run_ffmpeg

def enhance_audio(in_path: Path, out_path: Path) -> None:
    """Denoise + loudnorm enhancement via FFmpeg. Non-destructive (writes to out_path).

    Filter chain (locked decision):
      afftdn=nr=6:nf=-25  — conservative FFT denoising (no model file, no arnndn)
      loudnorm=I=-16:TP=-1.5:LRA=11  — EBU R128 single-pass normalize

    IMPORTANT (Pitfall 22): alignment (WhisperX) always runs on the ORIGINAL in_path.
    out_path is only used for the final assembled video.

    Args:
        in_path: Original (unprocessed) audio file.
        out_path: New file for the enhanced output. Never overwrites in_path.
    """
    run_ffmpeg([
        "ffmpeg", "-hide_banner", "-y",
        "-i", str(in_path),
        "-af", "afftdn=nr=6:nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11",
        str(out_path),
    ])
# Source: [VERIFIED: milestone SUMMARY.md, PITFALLS.md Pitfall 22/23]
```

### Pattern 5: build_music_mix_args() in integrations/ffmpeg.py

The existing `build_assemble_args()` returns a `list[str]`. The music mix is a SEPARATE ffmpeg pass that takes the assembled output.mp4 + music file as inputs and produces the final mixed output. This keeps the existing `build_filtergraph()` pristine and avoids complicating the N-slide filtergraph.

```python
# src/avideo/integrations/ffmpeg.py — new function

def build_music_mix_args(
    video_path: str,
    music_path: str,
    output_path: str,
    *,
    music_volume: float = 0.12,
    fade_in_s: float = 2.0,
    fade_out_start: float,    # caller computes: actual_duration - fade_out_s
    fade_out_s: float = 3.0,
    ducking_threshold: float = 0.02,
    ducking_ratio: float = 10.0,
    ducking_attack: float = 50.0,
    ducking_release: float = 500.0,
) -> list[str]:
    """Build ffmpeg arg list to overlay background music on an assembled video.

    Mix strategy (all locked decisions):
      - amix=inputs=2:normalize=0  ALWAYS (Pitfall 19: normalize=1 drops narration -6dB)
      - music level set with volume= before amix (explicit, not amix internal gain)
      - sidechaincompress: narration keys the sidechain; music is compressed when voice active
      - afade: in at t=0, out starting at fade_out_start (computed from ffprobe real duration)
      - No new loudnorm here — caller (AssembleStage) runs loudnorm pass-1+2 on the output

    Security: all paths come from WorkdirManager; filter_complex is ONE list element.

    Args:
        video_path: Path to the assembled MP4 (narration only, already normalized if no music).
        music_path: Path to the user-supplied music file (any ffmpeg-readable format).
        output_path: Destination MP4 path (use .tmp for atomic rename by caller).
        music_volume: Linear gain for music before mix (0.12 ≈ -18 dB relative to 0dBFS).
        fade_in_s: Music fade-in duration in seconds.
        fade_out_start: Start time of the fade-out in seconds (ffprobe-measured, not config).
        fade_out_s: Music fade-out duration in seconds.
        ducking_threshold/ratio/attack/release: sidechaincompress params.

    Returns:
        list[str] for subprocess.run(..., shell=False).
    """
    filter_complex = (
        f"[0:a]asplit=2[narr_main][narr_sc];"
        f"[1:a]volume={music_volume},"
        f"afade=t=in:st=0:d={fade_in_s},"
        f"afade=t=out:st={fade_out_start}:d={fade_out_s}[music_faded];"
        f"[music_faded][narr_sc]sidechaincompress="
        f"threshold={ducking_threshold}:ratio={ducking_ratio}:"
        f"attack={ducking_attack}:release={ducking_release}[music_ducked];"
        f"[narr_main][music_ducked]amix=inputs=2:normalize=0[aout]"
    )
    return [
        "ffmpeg", "-hide_banner", "-y",
        "-i", video_path,
        "-i", music_path,
        "-filter_complex", filter_complex,
        "-map", "0:v",        # copy video stream unchanged
        "-map", "[aout]",
        "-c:v", "copy",       # no video re-encode
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",  # Pitfall 2: must re-add under -c:v copy
        output_path,
    ]
# Source: [VERIFIED: PITFALLS.md Pitfalls 19/20/21, STACK.md FFmpeg filter examples]
```

### Pattern 6: AssembleStage music extension (surgical modification)

The existing `AssembleStage.run()` has this flow:
1. Idempotence check
2. Read checkpoints
3. Validate counts
4. Measure real audio durations via ffprobe
5. Build ffmpeg args (build_assemble_args)
6. Run ffmpeg
7. Atomic rename
8. QA sub-step (_run_qa → loudnorm pass-1 + pass-2 + report)
9. Return AssemblyOutput

The music extension adds a step 7.5 (music mix pass) and modifies step 8 (skip loudnorm on narration, apply on mix):

```python
# In AssembleStage.run() — AFTER step 8 (atomic rename of assembled video):

if config.bg_music_path and Path(str(config.bg_music_path)).exists():
    # Step 7.5: music mix pass
    # CRITICAL: compute fade_out_start from REAL duration, not config.duration (Pitfall 21)
    actual_dur = probe_duration(str(output_mp4))
    fade_out_s = getattr(config, "bg_music_fade_out_s", 3.0)
    fade_out_start = max(0.0, actual_dur - fade_out_s)
    music_tmp = workdir.root / "output.music.tmp.mp4"
    music_args = build_music_mix_args(
        str(output_mp4),
        str(config.bg_music_path),
        str(music_tmp),
        music_volume=getattr(config, "bg_music_volume", 0.12),
        fade_out_start=fade_out_start,
        fade_out_s=fade_out_s,
    )
    run_ffmpeg(music_args)
    os.replace(str(music_tmp), str(output_mp4))  # atomic: music mix replaces narration-only

# QA loudnorm pass — modified:
# - when bg_music_path: skip per-narration loudnorm, run loudnorm on the MIXED output
# - when no bg_music_path: existing behavior (loudnorm on narration-only assembled output)
# This conditional is implemented inside _run_qa() by checking config.bg_music_path
```

**Key: `_run_qa()` does NOT change its loudnorm two-pass logic.** When music is added, the input to `_run_qa()` is already the mixed output.mp4. The existing loudnorm pass-1 + pass-2 on `output_mp4` is correct in both cases. The only special case is that the prior step (step 7.5) replaced output.mp4 with the mixed version before _run_qa is called. This means **zero changes to `_run_qa()`** — only the sequencing in `run()` changes.

### Anti-Patterns to Avoid

- **Adding `arnndn` as the denoise default:** `arnndn` requires a bundled `.rnnn` model file (it will fail with a missing file error at runtime). Use `afftdn` exclusively. [VERIFIED: PITFALLS.md Pitfall 23, SUMMARY.md Gaps]
- **`amix=inputs=2:normalize=1` (default):** Drops narration -6 dB silently (Pitfall 19). Always specify `normalize=0`.
- **Applying loudnorm before the music mix:** Produces pumping artifacts when the second loudnorm pass runs on already-normalized audio (Pitfall 20). The design above correctly applies loudnorm only once on the final mixed output.
- **Using `config.duration` for fade-out position:** The assembled video's actual duration differs from the target. Use `probe_duration(output_mp4)` AFTER the music mix step (Pitfall 21).
- **Using `gpt-4o-transcribe` for the STT round-trip:** It does not support word-level timestamps (Pitfall 17). The model must be `whisper-1`.
- **Instantiating `OpenAI()` at module import time:** Fails if `OPENAI_API_KEY` is not set (including test collection). Always use the lazy singleton pattern that mirrors `integrations/elevenlabs.py`.
- **Storing `UploadedFile` for music instead of writing to workdir immediately:** Phase 9+ concern, but the design here (music comes as a `Path` from `RunConfig.bg_music_path`) is correct for the headless phase.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OpenAI TTS word timestamps | Custom prosody estimator | `openai.audio.transcriptions.create(model="whisper-1", timestamp_granularities=["word"])` | Already in the `openai` SDK; accurate enough for subtitles; no new dependency |
| Audio normalization | Python scipy DSP | `run_ffmpeg(["ffmpeg", "-af", "loudnorm=..."])` | Already used in `assemble.py`; same pattern, zero new code |
| FFmpeg filter_complex construction | String concatenation with f-strings ad hoc | `build_music_mix_args()` function in `integrations/ffmpeg.py` | All FFmpeg builder functions are pure (no I/O, testable); same pattern as `build_assemble_args()` |
| Background music ducking | Python-level audio processing | `sidechaincompress` FFmpeg filter | Built into ffmpeg >=6.1; no model files; no extra deps |
| Per-slide 4096-char chunking of TTS text | Complex sentence splitter | Raise ValueError + document in code | The storyboard WPM budget (150 WPM × max 60s slide = 1500 chars) keeps all slides well below 4096; guard with a clear error, not a chunker |

---

## Common Pitfalls

### Pitfall 1: amix normalize=1 crushes narration loudness (Pitfall 19 in PITFALLS.md)
**What goes wrong:** Default `amix` (normalize=1) applies -6 dB to both inputs before mixing. The narration that was loudnorm-normalized to -16 LUFS becomes -22 LUFS. The QA loudnorm pass may not fully compensate.
**Why it happens:** FFmpeg amix default is `normalize=1` for power-equal mixing. The filter does not know that narration should be preserved at full gain.
**How to avoid:** Always `amix=inputs=2:normalize=0`. Control music level with `volume=X` BEFORE the amix. [VERIFIED: PITFALLS.md Pitfall 19]
**Warning signs:** QA report shows LUFS significantly below target even though no music bug is present.

### Pitfall 2: Double-normalization pumping artifact (Pitfall 20 in PITFALLS.md)
**What goes wrong:** The existing `_run_qa()` runs two-pass loudnorm on the assembled narration. If music is added but `_run_qa()` runs again on the mix without change, and the narration was already normalized, the second pass produces pumping.
**Why it happens:** Loudnorm is not idempotent on already-normalized audio — the measured values differ from the target because dynamic range is already compressed.
**How to avoid:** The design here inserts the music mix (step 7.5) BEFORE `_run_qa()`. The `_run_qa()` always runs on `output_mp4`, which is already the mixed file when music is present. So `_run_qa()` runs loudnorm exactly once on the final output. No changes to `_run_qa()` are needed. [VERIFIED: PITFALLS.md Pitfall 20]

### Pitfall 3: fade-out position computed from config.duration (Pitfall 21 in PITFALLS.md)
**What goes wrong:** Music fade-out starts at the wrong time if `config.duration` (target seconds) is used instead of the actual video duration (measured by ffprobe after assembly).
**Why it happens:** Real duration = sum of ffprobe-measured audio durations - (N-1) × crossfade. This differs from the target by ±5-15%.
**How to avoid:** Call `probe_duration(str(output_mp4))` AFTER the narration-only assembly (step 7), BEFORE building music_mix_args. Compute `fade_out_start = actual_dur - fade_out_s`. [VERIFIED: PITFALLS.md Pitfall 21]

### Pitfall 4: OpenAI STT round-trip uses gpt-4o-transcribe (Pitfall 17 in PITFALLS.md)
**What goes wrong:** Using `model="gpt-4o-transcribe"` in `audio.transcriptions.create()` does not return word-level timestamps. The `words` field is absent or empty. Subtitles are one block per slide.
**Why it happens:** OpenAI's newer transcription models do not expose word granularity via the API.
**How to avoid:** Always use `model="whisper-1"` for the STT round-trip. Hard-code this inside `transcribe_slide_openai()` — do not make it configurable. [VERIFIED: PITFALLS.md Pitfall 17, SUMMARY.md]

### Pitfall 5: arnndn denoise requires a bundled .rnnn model file
**What goes wrong:** `afftdn=nr=6:nf=-25` works with no model file. `arnndn` requires `m=/path/to/model.rnnn`. If the model file is absent, ffmpeg exits with error at runtime.
**Why it happens:** `arnndn` is a neural-network denoiser that needs a pre-trained weights file. The default filter has no built-in model.
**How to avoid:** Use `afftdn` exclusively. Never use `arnndn` in `enhance_audio()`. This is a locked decision. [VERIFIED: PITFALLS.md, SUMMARY.md Gaps section]

### Pitfall 6: VoiceMode.openai breaks the existing record lazy-import guard
**What goes wrong:** Adding `VoiceMode.openai` to the dispatcher without using a lazy import causes the `openai` package to be imported at module load time. If `OPENAI_API_KEY` is not set, `OpenAI()` raises an error during test collection.
**Why it happens:** The existing `VoiceMode.record` uses a `try/from avideo.stages.voice_record import ...` inside the if-branch specifically to avoid importing whisperx/torch at module load. The same pattern must be applied for openai.
**How to avoid:** Use `from avideo.stages.voice_openai import VoiceOpenAIStage` INSIDE the openai branch of `VoiceStage.run()`, not at the top of the file. [VERIFIED: existing voice.py source, lines 62-63]

---

## Code Examples

### OpenAI SDK: speech.create (verified shape)

```python
# Source: [VERIFIED: milestone STACK.md OpenAI Audio TTS Integration Pattern]
from openai import OpenAI
client = OpenAI()  # reads OPENAI_API_KEY from env

response = client.audio.speech.create(
    model="tts-1",          # or "gpt-4o-mini-tts" — discretion: see below
    voice="nova",           # default; configurable via RunConfig.openai_tts_voice
    input=slide_text,       # <= 4096 chars (validated before call)
    response_format="mp3",
)
response.stream_to_file(str(out_path))
```

**Discretion note — model choice:** `tts-1` has lower latency (~1–3s per slide) and lower cost. `gpt-4o-mini-tts` has better prosody but 2–4× the latency. Default recommendation: `tts-1` with `RunConfig.openai_tts_model` field to override. [ASSUMED: relative latency comparison; exact numbers depend on OpenAI infrastructure at call time]

**Discretion note — default voice:** `nova` is described in OpenAI docs as natural and warm, suitable for narration. Other options: `alloy`, `echo`, `fable`, `onyx`, `shimmer`. Default: `"nova"`. [ASSUMED: voice quality judgement; verify by listening]

### OpenAI SDK: transcriptions.create (whisper-1 word timestamps)

```python
# Source: [VERIFIED: milestone PITFALLS.md Pitfall 17, SUMMARY.md]
with open(audio_path, "rb") as f:
    result = client.audio.transcriptions.create(
        file=f,
        model="whisper-1",                     # MUST be whisper-1; not gpt-4o-transcribe
        response_format="verbose_json",
        timestamp_granularities=["word"],
    )
# result.words is a list of objects with .word (str), .start (float), .end (float)
words = [WordTiming(text=w.word, start=w.start, end=w.end) for w in (result.words or [])]
```

### FFmpeg afftdn denoise filter

```bash
# Source: [VERIFIED: PITFALLS.md Pitfall 23, SUMMARY.md Conflict Resolution]
ffmpeg -hide_banner -y \
  -i input.wav \
  -af "afftdn=nr=6:nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11" \
  output_enhanced.wav
# nr=6 = conservative noise reduction (default is 12 — too aggressive)
# nf=-25 = noise floor in dB (below this = noise, above = speech)
# NOT arnndn — that requires a .rnnn model file (see Anti-patterns)
```

### FFmpeg music mix filter_complex

```bash
# Source: [VERIFIED: PITFALLS.md Pitfall 19, STACK.md FFmpeg Filters]
ffmpeg -hide_banner -y \
  -i assembled_narration.mp4 \
  -i background.mp3 \
  -filter_complex "
    [0:a]asplit=2[narr_main][narr_sc];
    [1:a]volume=0.12,
         afade=t=in:st=0:d=2.0,
         afade=t=out:st=<REAL_DUR-3.0>:d=3.0[music_faded];
    [music_faded][narr_sc]sidechaincompress=
         threshold=0.02:ratio=10:attack=50:release=500[music_ducked];
    [narr_main][music_ducked]amix=inputs=2:normalize=0[aout]
  " \
  -map 0:v -map "[aout]" \
  -c:v copy -c:a aac -b:a 192k \
  -movflags +faststart \
  output_with_music.mp4
# REAL_DUR = result of probe_duration(assembled_narration.mp4) — NOT config.duration
```

### RunConfig new fields

```python
# src/avideo/models/config.py additions
# In VoiceMode enum:
openai = "openai"   # new value

# In RunConfig class (all Optional with None default — backward-compatible):
openai_tts_model: str = Field(default="tts-1", description="OpenAI TTS model id")
openai_tts_voice: str = Field(default="nova", description="OpenAI TTS voice")
bg_music_path: Optional[Path] = Field(default=None, description="Path to background music file")
bg_music_volume: float = Field(default=0.12, ge=0.0, le=1.0, description="Music linear volume (0-1)")
bg_music_fade_out_s: float = Field(default=3.0, ge=0.0, description="Music fade-out duration in seconds")
# Source: [VERIFIED: existing RunConfig fields in models/config.py — same Pydantic Field pattern]
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ElevenLabs only for TTS | Three providers: ElevenLabs / OpenAI / record | Phase 8 (v2.0.0) | `VoiceMode` enum gains third value; dispatcher adds one branch |
| No audio enhancement | `enhance_audio()` utility (FFmpeg afftdn + loudnorm) | Phase 8 (v2.0.0) | Callable on demand; not in PIPELINE_STAGES |
| Narration-only assembly | Optional background music via `build_music_mix_args()` | Phase 8 (v2.0.0) | AssembleStage gains conditional music-mix step; loudnorm stays single-pass |
| `python-dotenv` in dev only | `python-dotenv` in core deps | Phase 8 (v2.0.0) | `load_dotenv()` available at runtime in all environments |

**Deprecated/outdated:**
- Nothing deprecated in this phase. All changes are additive.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `tts-1` has lower latency than `gpt-4o-mini-tts` (~1-3s vs 2-4s per slide) | Code Examples | Wrong model chosen as default; user can override via config |
| A2 | `nova` is the best OpenAI voice for Spanish narration | Code Examples | Suboptimal voice quality; user can override via `openai_tts_voice` |
| A3 | `sidechaincompress` default params (threshold=0.02, ratio=10, attack=50, release=500) produce natural-sounding ducking | Pattern 5 | Ducking too aggressive or too subtle; all params are configurable |
| A4 | `bg_music_volume=0.12` (≈ -18 dBFS) is an appropriate default music level relative to narration | Pattern 5 | Music too loud or too quiet; `bg_music_volume` is a RunConfig field |

**All claims tagged `[VERIFIED]` in this document are confirmed against live source code, official docs, or milestone research verified against those sources. The four `[ASSUMED]` items above are judgment calls about defaults — none block implementation; all are configurable by the user.**

---

## Open Questions

1. **whisper-1 Spanish quality for word timestamps**
   - What we know: `whisper-1` supports word-level timestamps via `verbose_json`; milestone research notes quality is "acceptable but not perfect for Spanish" [VERIFIED: SUMMARY.md Gaps section]
   - What's unclear: Whether Spanish narration (generated by a TTS model) will produce accurate enough word timestamps for subtitle quality
   - Recommendation: Accept as a known limitation; document in stage docstring; the fallback (WhisperX) is already in the `[record]` optional group if quality is insufficient

2. **`response_format` for OpenAI speech.create — does `stream_to_file()` handle aac/flac too?**
   - What we know: `response_format="mp3"` is the standard choice; the SDK's `stream_to_file()` writes whatever bytes the API returns
   - What's unclear: Whether `mp3` or `aac` produces better quality for the subsequent whisper-1 round-trip
   - Recommendation: Default to `mp3` (consistent with ElevenLabs path; ffmpeg handles it natively); no investigation needed

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `ffmpeg` binary | `enhance_audio()`, `build_music_mix_args()` | [ASSUMED: present — it's a hard dep and 303 tests pass against it] | >=6.1 | No fallback; skip test with `pytest.mark.skipif(not ffmpeg_available())` |
| `openai>=2.38.0` | `VoiceOpenAIStage` | Not yet installed — ADD to pyproject.toml | 2.38.0 | — |
| `python-dotenv>=1.0` | `OPENAI_API_KEY` loading | In `[dev]` group — PROMOTE to `[project.dependencies]` | 1.0+ | — |
| `OPENAI_API_KEY` env var | `integrations/openai.py` lazy client | Not checked at import; lazy singleton avoids startup failure | — | Unit tests mock the client; integration tests skip if key absent |

**Missing dependencies with no fallback:** None blocking (openai added via `uv add`; ffmpeg already present).

**Missing dependencies with fallback:** `OPENAI_API_KEY` — tests mock the client; key absence only blocks real API calls.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >=8.0 (already installed) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` testpaths=["tests"] pythonpath=["src"] |
| Quick run command | `uv run pytest tests/test_voice_openai.py tests/test_audio_enhance.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VOZ-02 | `VoiceOpenAIStage.run()` returns `UnifiedTimings(source="openai")` with words populated | unit (mocked) | `uv run pytest tests/test_voice_openai.py::test_run_returns_unified_timings -x` | Wave 0 |
| VOZ-02 | `VoiceStage` dispatches to `VoiceOpenAIStage` when `config.voice == VoiceMode.openai` | unit (mocked) | `uv run pytest tests/test_voice_openai.py::test_voice_stage_dispatches_openai -x` | Wave 0 |
| VOZ-02 | `synthesize_slide_openai()` raises `ValueError` when text > 4096 chars | unit | `uv run pytest tests/test_voice_openai.py::test_4096_char_limit -x` | Wave 0 |
| VOZ-02 | `transcribe_slide_openai()` maps word objects to `WordTiming` list | unit (mocked) | `uv run pytest tests/test_voice_openai.py::test_transcribe_maps_word_objects -x` | Wave 0 |
| VOZ-02 | `integrations/openai._get_client()` does NOT instantiate at import time | unit | `uv run pytest tests/test_voice_openai.py::test_lazy_client_not_instantiated_at_import -x` | Wave 0 |
| VOZ-03 | `enhance_audio()` calls `run_ffmpeg` with correct afftdn+loudnorm filter string | unit (mocked ffmpeg) | `uv run pytest tests/test_audio_enhance.py::test_enhance_calls_run_ffmpeg -x` | Wave 0 |
| VOZ-03 | `enhance_audio()` writes to out_path, not in_path (non-destructive) | unit | `uv run pytest tests/test_audio_enhance.py::test_nondestructive -x` | Wave 0 |
| EXT-02 | `build_music_mix_args()` contains `amix=inputs=2:normalize=0` | unit (pure builder) | `uv run pytest tests/test_assemble.py::test_music_mix_args_normalize_0 -x` | Wave 0 |
| EXT-02 | `build_music_mix_args()` contains `volume=<configured_value>` before `amix` | unit | `uv run pytest tests/test_assemble.py::test_music_mix_args_volume -x` | Wave 0 |
| EXT-02 | `AssembleStage.run()` calls `build_music_mix_args` when `config.bg_music_path` is set | unit (mocked ffmpeg) | `uv run pytest tests/test_assemble.py::test_assemble_triggers_music_mix -x` | Wave 0 |
| EXT-03 | Loudnorm runs exactly once when music is present (on the mixed output, not the narration-only) | unit (spy on run_ffmpeg) | `uv run pytest tests/test_assemble.py::test_single_loudnorm_with_music -x` | Wave 0 |
| EXT-03 | Loudnorm still runs on narration-only output when no music | regression | `uv run pytest tests/test_assemble.py -x` (existing tests) | Exists |

### Test Seams (how to mock)

**OpenAI SDK:**
```python
# Patch the lazy client factory — import path matches the lazy-import pattern
mocker.patch("avideo.integrations.openai._get_client", return_value=mock_openai_client)
# Mock speech.create response
mock_openai_client.audio.speech.create.return_value = mock_speech_response
mock_speech_response.stream_to_file = lambda path: Path(path).write_bytes(b"\xff\xe3\x10\x00")
# Mock transcriptions.create response
mock_openai_client.audio.transcriptions.create.return_value = types.SimpleNamespace(
    words=[types.SimpleNamespace(word="hola", start=0.0, end=0.4)]
)
```

**FFmpeg (enhance_audio + music mix):**
```python
# Patch run_ffmpeg at the integrations.ffmpeg level (same as existing test_assemble.py pattern)
mocker.patch("avideo.utils.audio_enhance.run_ffmpeg")
mocker.patch("avideo.integrations.ffmpeg.run_ffmpeg")
# For build_music_mix_args: it's a pure builder (no I/O) — test directly, no mock needed
```

**probe_duration (for music fade-out position):**
```python
mocker.patch("avideo.integrations.ffmpeg.probe_duration", return_value=42.5)
```

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_voice_openai.py tests/test_audio_enhance.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q` (must keep all 303 existing tests green)
- **Phase gate:** Full suite green (303 + new tests) before `/gsd-verify-work`

### Wave 0 Gaps

The following test files do not yet exist and must be created before implementation tasks:

- [ ] `tests/test_voice_openai.py` — covers VOZ-02 (VoiceOpenAIStage, lazy client, 4096-char guard, transcription mapping)
- [ ] `tests/test_audio_enhance.py` — covers VOZ-03 (enhance_audio, non-destructive, afftdn filter string)
- [ ] New test cases in `tests/test_assemble.py` — covers EXT-02/EXT-03 (music_mix_args normalize=0 assertion, single loudnorm pass assertion)

No new framework install needed — pytest + pytest-mock are already in `[dev]`.

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | n/a — CLI tool, no auth layer |
| V3 Session Management | no | n/a |
| V4 Access Control | no | n/a |
| V5 Input Validation | yes | 4096-char guard in `synthesize_slide_openai()`; `bg_music_path` comes from RunConfig (Pydantic-validated Path) |
| V6 Cryptography | no | API keys read from env; never logged, never embedded in checkpoints |

### Known Threat Patterns for this Phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API key logged in debug output | Information Disclosure | Mirror existing pattern: never log `OPENAI_API_KEY`; log only metadata (slide_index, char count) |
| Path traversal via `bg_music_path` | Tampering | `bg_music_path` is a Pydantic `Optional[Path]` — validated at model init; `build_music_mix_args()` takes a string from the caller, not from user input directly |
| Shell injection via filter_complex | Tampering/Elevation | `filter_complex` is ONE list element passed to `subprocess.run(args, shell=False)` — same pattern as existing `build_assemble_args()`; no shell interpretation |
| `synthesize_slide_openai()` called with > 4096 chars | Data corruption (silent truncation) | Hard ValueError guard before the API call; no silent truncation |

---

## Sources

### Primary (HIGH confidence)
- Existing source code (read in this session): `src/avideo/stages/voice.py`, `voice_elevenlabs.py`, `integrations/ffmpeg.py`, `integrations/elevenlabs.py`, `models/config.py`, `models/timings.py`, `stages/assemble.py`, `stages/base.py`, `pyproject.toml`, `tests/conftest.py`
- `.planning/research/SUMMARY.md` — milestone cross-cutting invariants (HIGH confidence, researched 2026-05-29)
- `.planning/research/STACK.md` — library versions + FFmpeg filter examples (HIGH confidence, researched 2026-05-29)
- `.planning/research/ARCHITECTURE.md` — build order + integration points (HIGH confidence, researched 2026-05-29)
- `.planning/research/PITFALLS.md` — Pitfalls 17–23 for v2.0.0 audio/TTS capabilities (HIGH confidence, researched 2026-05-29)
- `.planning/phases/08-backend-integrations/08-CONTEXT.md` — locked decisions (definitive authority for this phase)

### Secondary (MEDIUM confidence)
- [OpenAI Speech-to-text: word timestamps](https://platform.openai.com/docs/guides/speech-to-text/timestamps) — whisper-1 supports word granularity; gpt-4o-transcribe does not
- [FFmpeg amix normalize parameter](https://ffmpeg.org/ffmpeg-filters.html) — `normalize=0` behavior confirmed
- [FFmpeg afftdn filter docs](https://ayosec.github.io/ffmpeg-filters-docs/8.0/Filters/Audio/afftdn.html) — `nr` and `nf` parameter semantics

### Tertiary (LOW confidence)
- None. All claims in this research are either VERIFIED against source code or CITED from milestone research (which itself was HIGH confidence).

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — openai version from PyPI; ffmpeg filters from official docs; all other deps unchanged in live pyproject.toml
- Architecture: HIGH — integration points verified by reading every affected source file in this session
- Pitfalls: HIGH — carried from PITFALLS.md which is verified against official docs and v1.60.0 production code

**Research date:** 2026-05-29
**Valid until:** 2026-06-28 (stable stack; openai SDK API shape unlikely to break; ffmpeg filter flags are stable)
