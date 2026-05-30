---
phase: 08-backend-integrations
reviewed: 2026-05-29T00:00:00Z
depth: deep
files_reviewed: 9
files_reviewed_list:
  - src/avideo/integrations/openai.py
  - src/avideo/stages/voice_openai.py
  - src/avideo/stages/voice.py
  - src/avideo/utils/audio_enhance.py
  - src/avideo/integrations/ffmpeg.py
  - src/avideo/stages/assemble.py
  - src/avideo/models/config.py
  - src/avideo/cli.py
  - pyproject.toml
findings:
  critical: 2
  warning: 5
  info: 2
  total: 9
status: issues_found
---

# Phase 08: Code Review Report

**Reviewed:** 2026-05-29
**Depth:** deep
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 8 adds OpenAI Audio TTS + whisper-1 STT (VOZ-02), ffmpeg background music mixing with sidechaincompress ducking (EXT-02/EXT-03), and an audio enhancement utility. The ffmpeg filter graph wiring is correct: sidechain order `[music_faded][narr_sc]sidechaincompress` properly keys the sidechain on narration, `amix=inputs=2:normalize=0` prevents narration gain loss, and fade timing uses `probe_duration()` on the real output rather than `config.duration`. The openai integration is structurally sound (lazy singleton, path traversal prevented by fixed filename template, 4096-char guard correct).

Two blockers were found, both in Step 8.5 of `AssembleStage`: (1) the QA report pre-written for the music path contains fabricated LUFS values that are unconditionally set to the target rather than measured, silently defeating QA-02 monitoring; and (2) the Rich QA table is never printed for music runs because `_run_qa` short-circuits before the `_print_qa_table` call.

---

## Critical Issues

### CR-01: qa_report.json contains fabricated LUFS values when music is mixed

**File:** `src/avideo/stages/assemble.py:264-272`

**Issue:** When `bg_music_path` is set, Step 8.5 pre-writes `qa_report.json` with `measured_lufs=target_lufs` and `normalized_lufs=target_lufs` (both hardcoded to `-16.0` by default). These values are never measured — the single-pass `loudnorm` filter is applied but its stderr is not parsed. The result is that `qa_report.json` always shows `measured: -16.0 LUFS / normalized: -16.0 LUFS` for every music run, regardless of the actual loudness of the mixed output. This silently disables QA-02 (loudness quality monitoring) for the music path and will mask any loudnorm misconfiguration or encoding anomaly.

**Fix:** Add `print_format=json` to the single-pass loudnorm filter, capture stderr, and parse it:

```python
# Step 8.5 single-pass loudnorm — add print_format=json so we can measure output
single_loudnorm_args: list[str] = [
    "ffmpeg", "-hide_banner", "-y",
    "-i", str(output_mp4),
    "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11:print_format=json",
    "-c:v", "copy",
    "-c:a", "aac",
    "-b:a", "192k",
    "-ar", "48000",
    "-movflags", "+faststart",
    str(norm_tmp),
]
single_proc = run_ffmpeg(single_loudnorm_args)
os.replace(str(norm_tmp), str(output_mp4))

# Parse actual loudness from the single-pass stderr
try:
    sp_measured = parse_loudnorm_json(single_proc.stderr)
    measured_lufs_music: float = sp_measured.get("input_i", target_lufs)
    normalized_lufs_music: float = target_lufs  # single-pass output ≈ target
except (ValueError, KeyError):
    measured_lufs_music = target_lufs
    normalized_lufs_music = target_lufs

actual_seconds = probe_duration(str(output_mp4))
music_qa = build_qa_report(
    target_seconds=float(config.duration),
    actual_seconds=actual_seconds,
    measured_lufs=measured_lufs_music,
    normalized_lufs=normalized_lufs_music,
)
```

---

### CR-02: Rich QA table is never printed when music is mixed

**File:** `src/avideo/stages/assemble.py:274-282` and `src/avideo/stages/assemble.py:315-317`

**Issue:** When `bg_music_path` is set, Step 8.5 pre-writes `qa_report.json`, then calls `_run_qa()`. Inside `_run_qa`, the first thing that executes is the idempotence check at line 316: `if qa_json.exists(): return`. This returns the `QAReport` immediately, before reaching the `_print_qa_table(qa_report)` call at line 376. The user receives zero terminal feedback (no Rich table) for music runs. Combined with CR-01, the QA sub-step is entirely invisible for the music path.

**Fix:** Move the `_print_qa_table` call to `run()`, outside `_run_qa`, so it fires unconditionally:

```python
# --- Step 9: QA sub-step ---
report = self._run_qa(
    workdir=workdir,
    output_mp4=output_mp4,
    qa_json=qa_json,
    config=config,
)
# Print QA table regardless of which path (music or two-pass) produced the report
self._print_qa_table(report)

# --- Step 10: Return ---
return AssemblyOutput(output_path=str(output_mp4), qa=report)
```

Then remove the `self._print_qa_table(qa_report)` call currently inside `_run_qa` at line 376 to avoid double-printing on the non-music path.

---

## Warnings

### WR-01: openai.py incorrectly documents SDK default retries as 0 (actual default is 2)

**File:** `src/avideo/integrations/openai.py:12` and `src/avideo/integrations/openai.py:54`

**Issue:** Both the module-level docstring and `_get_client()` docstring state "the openai SDK does NOT add retries by default" and "openai SDK defaults to 0". The installed SDK (`openai>=2.38.0`) sets `DEFAULT_MAX_RETRIES = 2` (verified in `.venv/lib/python3.11/site-packages/openai/_constants.py`). Setting `max_retries=3` is still beneficial (one extra retry over the default), but any operator who reads this comment will misunderstand the SDK's baseline behavior, which could lead to incorrect reasoning about failure modes or retry storms.

**Fix:** Correct the comments:

```python
# max_retries=3: one retry above the SDK default of 2, for extra resilience on
# transient 429/5xx errors. Explicit value documents intent and guards against
# future SDK default changes.
_client = OpenAI(max_retries=3)
```

---

### WR-02: Step 8.5 single-pass loudnorm is missing `-ar 48000`

**File:** `src/avideo/stages/assemble.py:249-258`

**Issue:** The inline `single_loudnorm_args` list in Step 8.5 does not include `-ar`, `"48000"`, while `loudnorm_pass2_args()` (the authoritative builder used in the non-music path) explicitly sets `-ar`, `"48000"`. If the music mix output has a sample rate other than 48 kHz (e.g., a 44.1 kHz music file mixed with 48 kHz narration), the single-pass loudnorm output may have a different sample rate than the two-pass path, producing an inconsistent encode across code paths.

**Fix:** Add `-ar`, `"48000"` to `single_loudnorm_args`:

```python
single_loudnorm_args: list[str] = [
    "ffmpeg", "-hide_banner", "-y",
    "-i", str(output_mp4),
    "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
    "-c:v", "copy",
    "-c:a", "aac",
    "-b:a", "192k",
    "-ar", "48000",          # match loudnorm_pass2_args for consistent sample rate
    "-movflags", "+faststart",
    str(norm_tmp),
]
```

---

### WR-03: `enhance_audio` has no guard against `in_path == out_path`

**File:** `src/avideo/utils/audio_enhance.py:25-44`

**Issue:** `enhance_audio(in_path, out_path)` passes both paths directly to `run_ffmpeg` without asserting `in_path != out_path`. If a caller supplies the same path for both arguments, FFmpeg (`-y` flag) will attempt to write the output while reading the input — behavior that is undefined and can corrupt or truncate the file. The docstring states "Must differ from in_path" but there is no runtime enforcement.

**Fix:** Add an assertion before calling `run_ffmpeg`:

```python
def enhance_audio(in_path: Path, out_path: Path) -> None:
    if in_path.resolve() == out_path.resolve():
        raise ValueError(
            f"enhance_audio: in_path and out_path must differ; both resolve to {in_path.resolve()}"
        )
    run_ffmpeg([...])
```

---

### WR-04: Step 8.5 uses `getattr()` on properly-typed `RunConfig` fields

**File:** `src/avideo/stages/assemble.py:226-247`

**Issue:** Step 8.5 accesses `RunConfig` fields via `getattr(config, "bg_music_path", None)`, `getattr(config, "bg_music_volume", 0.12)`, `getattr(config, "bg_music_fade_out_s", 3.0)`, and `getattr(config, "target_lufs", -16.0)`. All four are declared as typed fields on `RunConfig` (added in this phase). Using `getattr()` with fallback defaults bypasses Pydantic's validated defaults, hides the fields from static analysis, and silently uses stale fallbacks if a field is renamed. The defensive pattern is appropriate when an attribute might not exist on an unknown object type, but not for a concrete, typed model.

**Fix:** Access the fields directly:

```python
bg_music_path = config.bg_music_path
if bg_music_path and Path(str(bg_music_path)).exists():
    actual_dur = probe_duration(str(output_mp4))
    fade_out_s: float = config.bg_music_fade_out_s
    target_lufs: float = config.target_lufs
    music_volume: float = config.bg_music_volume
    ...
```

---

### WR-05: `_run_qa` return type annotation uses deprecated Pydantic v1 `__fields__` API

**File:** `src/avideo/stages/assemble.py:294` and `src/avideo/stages/assemble.py:380`

**Issue:** Both `_run_qa` and `_print_qa_table` carry the return/parameter type annotation `"AssemblyOutput.__fields__['qa']"`. In Pydantic v2, `__fields__` is a compatibility shim that returns `FieldInfo` objects (not the field type), so this annotation is semantically wrong. The correct annotation for both is `QAReport`. The `# type: ignore[return]` suppressor masks the error. This is a code-quality issue: it erodes type-checking coverage and contradicts the project's "typed" convention from CLAUDE.md.

**Fix:**

```python
from avideo.models.assembly import QAReport  # move to module-level import

def _run_qa(self, ...) -> QAReport:
    ...

def _print_qa_table(self, report: QAReport) -> None:
    ...
```

---

## Info

### IN-01: `bg_music_fade_in_s` is not configurable; magic number 2.0 hardcoded in two places

**File:** `src/avideo/integrations/ffmpeg.py:455` and `src/avideo/stages/assemble.py:238` (implicit via default)

**Issue:** `build_music_mix_args` has `fade_in_s: float = 2.0`. `AssembleStage.run()` never passes `fade_in_s`, so the fade-in is always 2 seconds with no way to configure it through `config.yaml` or CLI. `bg_music_fade_out_s` is correctly exposed as a `RunConfig` field and passed through, making the asymmetry obvious. This is a missing config field rather than a bug, but it creates an inconsistent user-facing API.

**Fix:** Add `bg_music_fade_in_s: float = Field(default=2.0, ge=0.0, ...)` to `RunConfig` and pass `fade_in_s=config.bg_music_fade_in_s` in Step 8.5.

---

### IN-02: `openai.py` module name matches installed `openai` package — safe but fragile

**File:** `src/avideo/integrations/openai.py:62`

**Issue:** The file is named `openai.py`. The lazy import inside `_get_client()` — `from openai import OpenAI` — resolves correctly to the installed `openai` package because the module's fully-qualified name is `avideo.integrations.openai`, not `openai`. However, any future refactor that adds `src/avideo/integrations/` to `sys.path` directly (e.g., via a test fixture or `PYTHONPATH` misconfiguration) would cause the import to shadow itself and fail with `ImportError: cannot import name 'OpenAI' from 'openai'`. This is a latent footgun, not a current bug.

**Fix:** Rename to `src/avideo/integrations/openai_audio.py` and update all import sites, or add a comment in `_get_client()` explicitly documenting why this cannot shadow despite the name match.

---

_Reviewed: 2026-05-29_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
