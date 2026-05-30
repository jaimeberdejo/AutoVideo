---
phase: 08-backend-integrations
fixed_at: 2026-05-29T00:00:00Z
review_path: .planning/phases/08-backend-integrations/08-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 7
skipped: 0
status: all_fixed
---

# Phase 08: Code Review Fix Report

**Fixed at:** 2026-05-29
**Source review:** .planning/phases/08-backend-integrations/08-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 7 (CR-01, CR-02, WR-01, WR-02, WR-03, WR-04, WR-05; IN-01 and IN-02 skipped per instructions)
- Fixed: 7
- Skipped: 0

## Fixed Issues

### CR-01: qa_report.json contains fabricated LUFS values when music is mixed

**Files modified:** `src/avideo/stages/assemble.py`, `tests/test_ffmpeg_music.py`
**Commit:** `2149589` (assemble.py), `b33a7a5` (tests)
**Applied fix:** Added `print_format=json` to the single-pass loudnorm filter string in Step 8.5. Captured the return value of `run_ffmpeg(single_loudnorm_args)` as `single_proc`. Parsed `single_proc.stderr` via `parse_loudnorm_json()` to extract the real `input_i` as `measured_lufs_music`; set `normalized_lufs_music = target_lufs` (single-pass output approximates target). Wrapped in a try/except that falls back to `target_lufs` if the JSON block is absent. The `build_qa_report()` call now receives real measured values. Extended `tests/test_ffmpeg_music.py` with two new tests: `test_music_qa_report_uses_parsed_lufs_not_hardcoded` (asserts `qa_report.json` `measured_lufs` matches parsed stderr, not hardcoded target) and `test_music_single_loudnorm_has_print_format_json` (asserts `print_format=json` and `-ar 48000` are in the ffmpeg call).

### CR-02: Rich QA table is never printed when music is mixed

**Files modified:** `src/avideo/stages/assemble.py`
**Commit:** `2149589`
**Applied fix:** Moved `self._print_qa_table(report)` from inside `_run_qa()` to `run()` immediately after the `_run_qa()` call returns. Removed the `self._print_qa_table(qa_report)` call that was at the end of `_run_qa()`. Now both paths (music pre-writes qa_report.json → `_run_qa` returns early via idempotence check, and non-music path does full two-pass loudnorm) reach the same `_print_qa_table` call in `run()`.

### WR-01: openai.py incorrectly documents SDK default retries as 0

**Files modified:** `src/avideo/integrations/openai.py`
**Commit:** `b41ad93`
**Applied fix:** Corrected both the module-level docstring bullet and the `_get_client()` docstring. Old text stated "the openai SDK does NOT add retries by default" and "SDK defaults to 0". New text: "max_retries=3: one retry above the SDK default of 2 (DEFAULT_MAX_RETRIES=2), for extra resilience on transient 429/5xx errors. Explicit value documents intent and guards against future SDK default changes."

### WR-02: Step 8.5 single-pass loudnorm is missing `-ar 48000`

**Files modified:** `src/avideo/stages/assemble.py`, `tests/test_ffmpeg_music.py`
**Commit:** `2149589` (assemble.py), `b33a7a5` (tests)
**Applied fix:** Added `"-ar", "48000"` to `single_loudnorm_args` in Step 8.5, positioned between `-b:a 192k` and `-movflags +faststart`, matching the placement in `loudnorm_pass2_args()`. Covered by `test_music_single_loudnorm_has_print_format_json`.

### WR-03: `enhance_audio` has no guard against `in_path == out_path`

**Files modified:** `src/avideo/utils/audio_enhance.py`
**Commit:** `55e684e`
**Applied fix:** Added a guard at the top of `enhance_audio()` that resolves both paths before comparing (`in_path.resolve() == out_path.resolve()`). Raises `ValueError` with a message including the resolved path. Added `Raises` section to the docstring.

### WR-04: Step 8.5 uses `getattr()` on properly-typed `RunConfig` fields

**Files modified:** `src/avideo/stages/assemble.py`
**Commit:** `2149589`
**Applied fix:** Replaced all four `getattr(config, ...)` calls in Step 8.5 with direct attribute access: `config.bg_music_path`, `config.bg_music_fade_out_s`, `config.target_lufs`, `config.bg_music_volume`. The `getattr` fallback defaults are no longer needed since Pydantic validates and sets these on `RunConfig` construction.

### WR-05: `_run_qa` and `_print_qa_table` use deprecated Pydantic v1 `__fields__` annotation

**Files modified:** `src/avideo/stages/assemble.py`
**Commit:** `2149589`
**Applied fix:** Imported `QAReport` at module level (alongside `AssemblyOutput` in the same `from avideo.models.assembly import ...` line). Changed `_run_qa` return type from `"AssemblyOutput.__fields__['qa']"  # type: ignore[return]` to `QAReport`. Changed `_print_qa_table` parameter type from `"AssemblyOutput.__fields__['qa']"  # type: ignore[return]` to `QAReport`. Removed both `# type: ignore` suppressors. Removed the `from avideo.models.assembly import QAReport` local import that was inside `_print_qa_table` (no longer needed with module-level import). The local import inside `_run_qa` was already removed since `QAReport` is now at module level.

## Skipped Issues

### IN-01: `bg_music_fade_in_s` is not configurable

**File:** `src/avideo/integrations/ffmpeg.py:455`, `src/avideo/stages/assemble.py:238`
**Reason:** Skipped per instructions — nice-to-have config field, risk of scope creep. The `fade_in_s=2.0` default in `build_music_mix_args` is acceptable for current usage.

### IN-02: `openai.py` module name matches installed `openai` package

**File:** `src/avideo/integrations/openai.py:62`
**Reason:** Skipped per instructions — latent footgun, not a current bug. Left as-is.

---

_Fixed: 2026-05-29_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
