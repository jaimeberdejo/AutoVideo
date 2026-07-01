# Phase 8: Backend Integrations - Pattern Map

**Mapped:** 2026-05-29
**Files analyzed:** 9 (6 new, 3 modified)
**Analogs found:** 9 / 9

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/avideo/integrations/openai.py` | integration | request-response | `src/avideo/integrations/elevenlabs.py` | exact |
| `src/avideo/stages/voice_openai.py` | stage | request-response | `src/avideo/stages/voice_elevenlabs.py` | exact |
| `src/avideo/stages/voice.py` (modify) | stage/dispatcher | request-response | `src/avideo/stages/voice.py` itself | exact |
| `src/avideo/utils/audio_enhance.py` | utility | file-I/O | `src/avideo/utils/subtitle_format.py` (pure fn) + `integrations/ffmpeg.run_ffmpeg` | role-match |
| `src/avideo/integrations/ffmpeg.py` (modify) | integration | file-I/O | `src/avideo/integrations/ffmpeg.py` itself (build_assemble_args) | exact |
| `src/avideo/stages/assemble.py` (modify) | stage | file-I/O | `src/avideo/stages/assemble.py` itself (_run_qa) | exact |
| `src/avideo/models/config.py` (modify) | model/config | — | `src/avideo/models/config.py` itself (RunConfig, VoiceMode) | exact |
| `tests/test_voice_openai.py` | test | — | `tests/test_voice_elevenlabs.py` | exact |
| `tests/test_audio_enhance.py` | test | — | `tests/test_assemble.py` (mocked ffmpeg) | role-match |

---

## Pattern Assignments

### `src/avideo/integrations/openai.py` (integration, request-response)

**Analog:** `src/avideo/integrations/elevenlabs.py` (lines 1-66)

**Imports pattern** (elevenlabs.py lines 20-28):
```python
from __future__ import annotations

import base64
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from avideo.models.timings import SlideTimings
```

**Lazy client singleton pattern** (elevenlabs.py lines 43-66):
```python
_client = None  # type: ignore[assignment]


def _get_client():
    """Return the lazily-instantiated ElevenLabs client.

    The client is created on first call, then cached.  Importing this module
    does NOT instantiate the client and therefore does NOT require
    ELEVENLABS_API_KEY to be set — keeping --dry-run and tests import-safe.
    ...
    """
    global _client
    if _client is None:
        from elevenlabs import ElevenLabs  # lazy import: SDK key read from env here (D-03)

        _client = ElevenLabs()
    return _client
```

Mirror this exactly for openai.py:
```python
_client = None

def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI  # lazy import
        _client = OpenAI(max_retries=3)   # elevenlabs SDK has internal retries; openai SDK needs explicit
    return _client
```

**Core function signature pattern** (elevenlabs.py lines 174-182) — use keyword-only args:
```python
def synthesize_slide(
    *,
    text: str,
    slide_index: int,
    voice_id: str,
    out_path: Path,
    model_id: str = MODEL_ID,
    output_format: str = OUTPUT_FORMAT,
) -> "SlideTimings":
```

**SlideTimings return pattern** (elevenlabs.py lines 244-250) — construct and return:
```python
return SlideTimings(
    slide_index=slide_index,
    audio_path=str(out_path),
    duration=duration,
    words=words,
)
```

**Security / key guard docstring comment** (elevenlabs.py module docstring lines 1-19):
```
Security (T-04-01):
- ELEVENLABS_API_KEY is ONLY read from the environment by the SDK.
  NEVER log the key or embed it in any output/checkpoint.
```
Mirror this comment for OPENAI_API_KEY.

**Test mock seam:** The lazy `_get_client` function is the mock seam. Tests patch `avideo.integrations.openai._get_client`. This is different from elevenlabs where the SDK client has no `max_retries` arg — for openai.py pass `max_retries=3` explicitly inside the lazy factory.

---

### `src/avideo/stages/voice_openai.py` (stage, request-response)

**Analog:** `src/avideo/stages/voice_elevenlabs.py` (all 98 lines)

**Module docstring + imports pattern** (voice_elevenlabs.py lines 1-31):
```python
"""VoiceElevenlabsStage — per-slide TTS synthesis using ElevenLabs.
...
Mock point: synthesize_slide is imported at module scope so tests can patch
    ``avideo.stages.voice_elevenlabs.synthesize_slide`` without touching the
    integration layer (mirrors the storyboard.py / anthropic.py pattern).
...
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from avideo.integrations.elevenlabs import synthesize_slide  # module-scope mock point
from avideo.models.script import ScriptOutput
from avideo.models.timings import UnifiedTimings
from avideo.stages.base import CheckpointMixin

if TYPE_CHECKING:
    from avideo.models.config import RunConfig
    from avideo.utils.workdir import WorkdirManager
```

For voice_openai.py, import BOTH integration functions at module scope:
```python
from avideo.integrations.openai import synthesize_slide_openai, transcribe_slide_openai  # module-scope mock points
```

**Class + stage_name pattern** (voice_elevenlabs.py lines 34-53):
```python
class VoiceElevenlabsStage(CheckpointMixin):
    """..."""
    stage_name: str = "voice"   # CRITICAL: same checkpoint contract as ElevenLabs (D-12)
```

**run() method pattern** (voice_elevenlabs.py lines 55-97):
```python
def run(self, workdir: "WorkdirManager", config: "RunConfig") -> UnifiedTimings:
    script: ScriptOutput = workdir.read_checkpoint("script", ScriptOutput)  # type: ignore[assignment]

    slide_timings = []
    for slide in script.slides:
        # T-04-03: out_path constructed solely from workdir root + fixed template
        out_path = (
            workdir.root / "audio" / f"slide_{slide.slide_index:02d}.mp3"
        )
        timing = synthesize_slide(
            text=slide.narration,
            slide_index=slide.slide_index,
            voice_id=config.voice_id,
            out_path=out_path,
        )
        # Normalise audio_path to be relative to workdir.root for portability
        try:
            relative = str(out_path.relative_to(workdir.root))
        except ValueError:
            relative = str(out_path)
        timing = timing.model_copy(update={"audio_path": relative})

        slide_timings.append(timing)

    return UnifiedTimings(source="elevenlabs", slides=slide_timings)
```

For voice_openai.py: replace `synthesize_slide` call with two calls (`synthesize_slide_openai` then `transcribe_slide_openai`), and return `UnifiedTimings(source="openai", slides=slide_timings)`. The relative-path normalisation pattern stays identical.

---

### `src/avideo/stages/voice.py` (modify — add openai branch)

**Analog:** `src/avideo/stages/voice.py` itself (lines 59-73)

**Existing record branch pattern to mirror** (voice.py lines 59-71):
```python
if config.voice == VoiceMode.record:
    # D-06: lazy import of whisperx/sounddevice deps; only loaded in record mode.
    try:
        from avideo.stages.voice_record import VoiceRecordStage  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "Voice mode 'record' requires the optional 'record' extra. "
            ...
        ) from exc
    return VoiceRecordStage().run(workdir, config)

raise NotImplementedError(f"Unknown voice mode: {config.voice!r}")
```

The openai branch is simpler — no optional extra, no try/except needed:
```python
if config.voice == VoiceMode.openai:
    from avideo.stages.voice_openai import VoiceOpenAIStage  # noqa: PLC0415 — lazy: avoids openai import at module load
    return VoiceOpenAIStage().run(workdir, config)
```

Insert this before the final `raise NotImplementedError` line. The `VoiceElevenlabsStage` import at module-scope (line 22) stays; `VoiceOpenAIStage` must be lazy (inside the branch) to keep `openai` package unloaded during collection when `OPENAI_API_KEY` is absent.

---

### `src/avideo/utils/audio_enhance.py` (utility, file-I/O)

**Analog:** `src/avideo/integrations/ffmpeg.py` — the `run_ffmpeg()` call pattern (lines 454-475) and `src/avideo/utils/subtitle_format.py` — pure module docstring style (lines 1-29)

**Module docstring pattern** (subtitle_format.py lines 1-29) — explain pure/stateless nature:
```python
"""Subtitle format utilities — pure serialization and cue segmentation (SUB-01).

This module contains ONLY pure logic: no I/O, no network calls ...
"""
```

For audio_enhance.py follow the same convention:
```python
"""Audio enhancement utility — FFmpeg-based denoise + loudnorm (VOZ-03).

Standalone function (NOT a pipeline stage).  Called on demand.
Non-destructive: always writes to out_path; never modifies in_path.

CRITICAL: WhisperX/subtitle alignment always uses the ORIGINAL in_path.
out_path is for the final assembled video only.
"""
```

**Import pattern** (straight import of run_ffmpeg — same as assemble.py lines 54-61):
```python
from pathlib import Path
from avideo.integrations.ffmpeg import run_ffmpeg
```

**Function body** — delegates entirely to `run_ffmpeg` with a list[str] arg (shell=False implicit):
```python
def enhance_audio(in_path: Path, out_path: Path) -> None:
    run_ffmpeg([
        "ffmpeg", "-hide_banner", "-y",
        "-i", str(in_path),
        "-af", "afftdn=nr=6:nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11",
        str(out_path),
    ])
```

**Test mock seam:** patch `avideo.utils.audio_enhance.run_ffmpeg` (same import path used in the function body). See test_assemble.py lines 673-675 for the exact patch target pattern.

---

### `src/avideo/integrations/ffmpeg.py` (modify — add `build_music_mix_args()`)

**Analog:** `build_assemble_args()` in the same file (lines 236-318) — the arg-list builder pattern

**Function signature pattern** (build_assemble_args lines 236-248):
```python
def build_assemble_args(
    image_paths: list[str],
    audio_paths: list[str],
    durations: list[float],
    *,
    output_path: str,
    xfade: float,
    fps: int = 30,
    crf: int = 20,
    preset: str = "medium",
    burn_subs_path: Optional[str] = None,
) -> list[str]:
    """Build the complete ffmpeg arg list for video assembly (arg-list, NEVER shell=True).
    ...
    Security (T-05-01/T-05-02):
        - All paths come from WorkdirManager (fixed layout) or prior-phase checkpoints.
        - filter_complex is ONE list element — no shell interpretation.
        - No element is ever "shell=True".
    """
```

Mirror this signature style and security docstring comment for `build_music_mix_args()`. All params go through `**kwargs`-style keyword args after `*`. The function returns `list[str]`.

**Core arg list construction pattern** (build_assemble_args lines 275-317):
```python
args: list[str] = ["ffmpeg", "-hide_banner", "-y"]
# ... extend with inputs ...
args.extend(["-filter_complex", filtergraph])
args.extend(["-map", "[vout]", "-map", "[aout]"])
args.extend([
    "-c:v", "libx264",
    ...
    "-movflags", "+faststart",  # Pitfall 2: always re-add +faststart
])
args.append(output_path)
return args
```

For `build_music_mix_args()`, use the same `args: list[str] = ["ffmpeg", "-hide_banner", "-y"]` init and `args.append(output_path)` tail. The `-filter_complex` value is ONE list element (Pitfall 6).

**Placement:** Add the new function after `loudnorm_pass2_args()` (line 412) and before `parse_loudnorm_json()` (line 415) in the PURE BUILDERS section.

**Section marker comment to mirror** (ffmpeg.py line 24):
```
PURE BUILDERS — _input_normalize, build_filtergraph, build_assemble_args,
                probe_duration_args, loudnorm_pass1_args, loudnorm_pass2_args,
                parse_loudnorm_json
```
Update this docstring to include `build_music_mix_args`.

---

### `src/avideo/stages/assemble.py` (modify — music mix pre-pass + loudnorm sequencing)

**Analog:** `assemble.py` itself — `run()` method (lines 98-223) and `_run_qa()` (lines 225-317)

**Atomic rename pattern** (assemble.py lines 211-212):
```python
# --- Step 8: Atomic publish (D-10 — tmp → rename) ---
os.replace(str(tmp_mp4), str(output_mp4))
```

The music mix step follows the same tmp-then-replace pattern:
```python
music_tmp = workdir.root / "output.music.tmp.mp4"
# ... run_ffmpeg(music_args) writes to music_tmp ...
os.replace(str(music_tmp), str(output_mp4))  # atomic: music replaces narration-only
```

**probe_duration usage pattern** (assemble.py lines 186, _run_qa line 298):
```python
# Step 4: Measure real audio durations (ASMB-01 / D-02)
durations = [probe_duration(a) for a in audio_paths]
# ...
actual_seconds = probe_duration(str(output_mp4))
```

For fade_out_start: call `probe_duration(str(output_mp4))` AFTER step 8 (narration-only encode), BEFORE building music mix args. Same function already imported at top of file (line 59).

**getattr config access pattern** (_run_qa line 257):
```python
target_lufs = getattr(config, "target_lufs", -16.0)
```

Use the same `getattr(config, "bg_music_path", None)` and `getattr(config, "bg_music_volume", 0.12)` pattern for the new optional fields until `RunConfig` is updated, then switch to direct attribute access.

**Imports to add** (assemble.py lines 54-61 — extend the ffmpeg import block):
```python
from avideo.integrations.ffmpeg import (
    build_assemble_args,
    build_music_mix_args,   # ADD
    loudnorm_pass1_args,
    loudnorm_pass2_args,
    parse_loudnorm_json,
    probe_duration,
    run_ffmpeg,
)
```

**Step numbering + comment style** (assemble.py lines 133-222):
```python
# --- Step 7: Run ffmpeg (D-04 — list[str], never shell=True) ---
# --- Step 8: Atomic publish (D-10 — tmp → rename) ---
# --- Step 9: QA sub-step ...
```

Add as `# --- Step 8.5: Music mix pass (EXT-02) ---` between steps 8 and 9.

---

### `src/avideo/models/config.py` (modify — VoiceMode + RunConfig fields)

**Analog:** `src/avideo/models/config.py` itself (lines 20-103)

**VoiceMode enum pattern** (config.py lines 20-24):
```python
class VoiceMode(str, Enum):
    """TTS source selection."""

    elevenlabs = "elevenlabs"
    record = "record"
```

Add: `openai = "openai"` — one line, follows the same string-value pattern.

**RunConfig Field pattern** (config.py lines 64-72):
```python
crossfade_seconds: float = Field(
    default=0.5,
    ge=0,
    description="Crossfade duration between slides in seconds; 0 = hard cuts (D-03)",
)
target_lufs: float = Field(
    default=-16.0,
    description="EBU R128 loudness target for two-pass loudnorm in LUFS (D-06)",
)
```

New fields follow the same pattern:
```python
# OpenAI TTS settings (Phase 8)
openai_tts_model: str = Field(default="tts-1", description="OpenAI TTS model id")
openai_tts_voice: str = Field(default="nova", description="OpenAI TTS voice")

# Background music settings (Phase 8)
bg_music_path: Optional[Path] = Field(default=None, description="Path to background music file")
bg_music_volume: float = Field(default=0.12, ge=0.0, le=1.0, description="Music linear volume (0-1)")
bg_music_fade_out_s: float = Field(default=3.0, ge=0.0, description="Music fade-out duration in seconds")
```

All new fields have `None` defaults (for Optional) or safe numeric defaults — backward-compatible: existing `config.yaml` files that omit these fields will still parse cleanly.

---

### `tests/test_voice_openai.py` (new test file)

**Analog:** `tests/test_voice_elevenlabs.py` (all 241 lines)

**File header + import-deferral pattern** (test_voice_elevenlabs.py lines 1-16):
```python
"""Tests for VoiceElevenlabsStage and VoiceStage (Task 4 of 04-01).

Covers VOICE-01:
  - VoiceElevenlabsStage.run reads script.json checkpoint, calls synthesize_slide
    once per slide, writes audio files, and returns UnifiedTimings(source="elevenlabs")
  - Mock point: avideo.stages.voice_elevenlabs.synthesize_slide (module-scope import)
  ...
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
```

All avideo imports deferred to inside test functions/methods (`from avideo... import ...` with `# noqa: PLC0415`).

**`_write_script` helper** (test_voice_elevenlabs.py lines 22-31) — identical helper needed:
```python
def _write_script(workdir_manager, slides):
    """Write a minimal script.json checkpoint to workdir."""
    from avideo.models.script import ScriptOutput, SlideScript

    script = ScriptOutput(
        slides=[SlideScript(slide_index=i, narration=n) for i, n in enumerate(slides)],
        language="es",
    )
    workdir_manager.write_checkpoint("script", script)
```

**Mock seam pattern** (test_voice_elevenlabs.py lines 73-77):
```python
mock_synth = mocker.patch(
    "avideo.stages.voice_elevenlabs.synthesize_slide",
    side_effect=_make_fake_synthesize(tmp_path),
)
```

For openai tests, patch the module-scope imports in voice_openai.py:
```python
mocker.patch("avideo.stages.voice_openai.synthesize_slide_openai", side_effect=...)
mocker.patch("avideo.stages.voice_openai.transcribe_slide_openai", return_value=...)
```

**Lazy client import-safety test** (test_voice_elevenlabs.py lines 173-180):
```python
def test_synthesize_slide_imported_at_module_scope(self):
    """Mock point: synthesize_slide must be imported at module scope in voice_elevenlabs."""
    import avideo.stages.voice_elevenlabs as mod

    assert hasattr(mod, "synthesize_slide"), (
        "synthesize_slide must be imported at module scope..."
    )
```

Mirror this for both `synthesize_slide_openai` and `transcribe_slide_openai` in the openai stage module.

**SimpleNamespace mock pattern** (conftest.py lines 121-131) — use `types.SimpleNamespace` for mock API responses:
```python
# For transcriptions.create response:
mock_result = types.SimpleNamespace(
    words=[types.SimpleNamespace(word="hola", start=0.0, end=0.4)]
)
```

**RunConfig construction pattern** (test_voice_elevenlabs.py lines 81-83):
```python
bullets = tmp_path / "b.yaml"
bullets.write_text("title: T\nbullets:\n  - x\n", encoding="utf-8")
config = RunConfig(bullets=bullets, duration=60, voice_id="test-voice")
```

For openai tests add `voice=VoiceMode.openai` to the RunConfig constructor.

**Dispatcher test pattern** (test_voice_elevenlabs.py lines 200-223) — test that VoiceStage dispatches to the new branch:
```python
def test_elevenlabs_dispatches_to_voice_elevenlabs_stage(self, tmp_path, mocker):
    ...
    config = RunConfig(bullets=bullets, duration=60, voice=VoiceMode.elevenlabs)
    result = VoiceStage().run(wm, config)
    assert result.source == "elevenlabs"
```

Mirror: `config = RunConfig(..., voice=VoiceMode.openai)` → `assert result.source == "openai"`.

---

### `tests/test_audio_enhance.py` (new test file)

**Analog:** `tests/test_assemble.py` — the `patch("avideo.integrations.ffmpeg.subprocess.run")` / mocked ffmpeg pattern (test_assemble.py lines 93-119, 270-310)

**Module-level imports pattern** (test_assemble.py lines 1-28):
```python
"""Wave-0 test scaffold for Phase 5 FFmpeg assembly...

All imports from avideo.integrations.ffmpeg and avideo.stages.assemble are
deferred to INSIDE each test body so the collection does not error before
the modules exist (mirrors tests/test_slides_render.py pattern).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
```

**Mock run_ffmpeg pattern** (test_assemble.py lines 673-675):
```python
with patch("avideo.stages.assemble.run_ffmpeg", side_effect=fake_run_ffmpeg), \
     patch("avideo.stages.assemble.probe_duration", side_effect=fake_probe_duration):
```

For audio_enhance.py tests, patch the module-level name:
```python
mocker.patch("avideo.utils.audio_enhance.run_ffmpeg")
```

**Pure builder test pattern (no mock needed)** (test_assemble.py lines 194-263):
```python
def test_build_assemble_args_returns_list():
    from avideo.integrations.ffmpeg import build_assemble_args
    args = build_assemble_args(...)
    assert isinstance(args, list)
    assert all(isinstance(a, str) for a in args)
```

`build_music_mix_args()` is a pure builder (no I/O). Test it directly in `tests/test_assemble.py` without any mock:
```python
def test_music_mix_args_normalize_0():
    from avideo.integrations.ffmpeg import build_music_mix_args
    args = build_music_mix_args(
        "/tmp/assembled.mp4", "/tmp/music.mp3", "/tmp/out.mp4",
        music_volume=0.12, fade_in_s=2.0, fade_out_start=40.0, fade_out_s=3.0,
    )
    args_str = " ".join(args)
    assert "amix=inputs=2:normalize=0" in args_str
```

**skipif ffmpeg guard pattern** (test_assemble.py lines 506-509):
```python
@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed — smoke test skipped",
)
```

Use the same guard for any real-ffmpeg smoke test in test_audio_enhance.py.

---

## Shared Patterns

### Authentication / API Key Guard
**Source:** `src/avideo/integrations/elevenlabs.py` module docstring (lines 1-19) + `src/avideo/integrations/anthropic.py` module docstring (lines 1-17)
**Apply to:** `src/avideo/integrations/openai.py`
```
Security:
- OPENAI_API_KEY is ONLY read from the environment by the SDK.
  NEVER log the key or embed it in any output/checkpoint.
- Client is lazy — importing this module NEVER requires OPENAI_API_KEY.
  The SDK reads the key from the environment only when the first call is made.
```

### Lazy Import + Global Singleton
**Source:** `src/avideo/integrations/elevenlabs.py` lines 43-66
**Apply to:** `src/avideo/integrations/openai.py`
```python
_client = None

def _get_client():
    global _client
    if _client is None:
        from <sdk> import <Client>  # lazy import — key read from env only here
        _client = <Client>(max_retries=3)
    return _client
```
This is the only pattern that keeps import-time safe for tests without `OPENAI_API_KEY`.

### Subprocess Never shell=True
**Source:** `src/avideo/integrations/ffmpeg.py` lines 454-475 (run_ffmpeg) + docstring line 11 ("D-04")
**Apply to:** `src/avideo/utils/audio_enhance.py`, `build_music_mix_args()` in ffmpeg.py, assemble.py music step
```python
run_ffmpeg([...])  # always a list[str]; shell=False is the implicit subprocess default
```

### Atomic Tmp-Then-Rename
**Source:** `src/avideo/stages/assemble.py` lines 198-212, 259-281
**Apply to:** `src/avideo/stages/assemble.py` music mix step
```python
tmp_path = workdir.root / "output.music.tmp.mp4"
run_ffmpeg(build_music_mix_args(..., output_path=str(tmp_path), ...))
os.replace(str(tmp_path), str(output_mp4))
```
Temp filename ends in `.mp4` (not `.tmp`) — ffmpeg refuses to mux when extension is `.tmp` (see assemble.py comment at line 196).

### CheckpointMixin Stage Class
**Source:** `src/avideo/stages/base.py` lines 72-99 + `src/avideo/stages/voice_elevenlabs.py` lines 34-53
**Apply to:** `src/avideo/stages/voice_openai.py`
```python
class VoiceOpenAIStage(CheckpointMixin):
    stage_name: str = "voice"   # MUST match VoiceElevenlabsStage — same checkpoint contract

    def run(self, workdir: "WorkdirManager", config: "RunConfig") -> UnifiedTimings:
        ...
```

### Deferred Imports in Test Files
**Source:** `tests/test_assemble.py` lines 37-38 (`# noqa: PLC0415` pattern)
**Apply to:** `tests/test_voice_openai.py`, `tests/test_audio_enhance.py`, new cases in `tests/test_assemble.py`
```python
def test_something():
    from avideo.stages.voice_openai import VoiceOpenAIStage  # noqa: PLC0415
    ...
```
All avideo module imports inside test function/method bodies, never at the top of the test file.

### RunConfig Pydantic Field with Default
**Source:** `src/avideo/models/config.py` lines 64-72
**Apply to:** New fields in `RunConfig` (openai_tts_model, openai_tts_voice, bg_music_path, bg_music_volume, bg_music_fade_out_s)
```python
new_field: type = Field(default=<value>, description="...")
```
Optional[Path] fields use `Field(default=None, ...)`. All new fields must have defaults so existing `config.yaml` files (and 303 existing tests) remain unaffected.

### Relative Audio Path in Checkpoint
**Source:** `src/avideo/stages/voice_elevenlabs.py` lines 88-93
**Apply to:** `src/avideo/stages/voice_openai.py`
```python
try:
    relative = str(out_path.relative_to(workdir.root))
except ValueError:
    relative = str(out_path)  # fallback if out_path is not under root
timing = timing.model_copy(update={"audio_path": relative})
```
Timings must store workdir-relative paths for checkpoint portability. Copy this block verbatim.

---

## No Analog Found

All files have close matches in the codebase. No files fall into this category.

---

## Metadata

**Analog search scope:** `src/avideo/integrations/`, `src/avideo/stages/`, `src/avideo/models/`, `src/avideo/utils/`, `tests/`
**Files scanned:** 11 source files + 3 test files read in full
**Pattern extraction date:** 2026-05-29
