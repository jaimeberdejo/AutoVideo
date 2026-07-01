---
phase: "08"
plan: "02"
subsystem: models/config
tags: [model-layer, openai-tts, background-music, pydantic, additive]
dependency_graph:
  requires: ["08-01"]
  provides: ["VoiceMode.openai", "RunConfig.openai_tts_model", "RunConfig.openai_tts_voice", "RunConfig.bg_music_path", "RunConfig.bg_music_volume", "RunConfig.bg_music_fade_out_s"]
  affects: ["src/avideo/stages/voice.py", "src/avideo/stages/assemble.py"]
tech_stack:
  added: ["openai>=2.38.0"]
  patterns: ["Pydantic Field with ge/le validation", "additive enum extension", "TDD RED/GREEN cycle"]
key_files:
  created:
    - tests/test_config_phase8.py
  modified:
    - src/avideo/models/config.py
    - pyproject.toml
    - uv.lock
decisions:
  - "All new RunConfig fields use Optional or have defaults to preserve full backward-compatibility with existing 303 tests"
  - "python-dotenv promoted from dev to core because CLI entry already calls load_dotenv() and production use requires it"
  - "openai>=2.38.0 added to core (not optional) because OpenAI TTS is a first-class voice mode in Wave 2"
metrics:
  duration_seconds: 126
  completed_date: "2026-05-29"
  tasks_completed: 2
  files_changed: 4
---

# Phase 8 Plan 02: Model Layer — VoiceMode.openai + RunConfig Phase 8 Fields

**One-liner:** Additive Pydantic model layer additions — VoiceMode.openai enum value + 5 new RunConfig fields (openai_tts_model, openai_tts_voice, bg_music_path, bg_music_volume, bg_music_fade_out_s) + openai>=2.38.0 in production deps.

## What Was Built

### Task 1: VoiceMode.openai + new RunConfig fields (TDD)

Added `openai = "openai"` to `VoiceMode` enum (line 24 of config.py), making `VoiceMode("openai")` valid and importable.

Added 5 new optional RunConfig fields with correct defaults and validation:

| Field | Type | Default | Constraints |
|-------|------|---------|-------------|
| `openai_tts_model` | `str` | `"tts-1"` | none |
| `openai_tts_voice` | `str` | `"nova"` | none |
| `bg_music_path` | `Optional[Path]` | `None` | none |
| `bg_music_volume` | `float` | `0.12` | `ge=0.0, le=1.0` |
| `bg_music_fade_out_s` | `float` | `3.0` | `ge=0.0` |

TDD cycle: 7 tests written first (RED — all failing), then config.py edited (GREEN — all 8 pass including the pre-existing sanity test).

### Task 2: pyproject.toml — openai dep + python-dotenv promotion

- Added `"openai>=2.38.0"` to `[project.dependencies]`
- Moved `"python-dotenv>=1.0"` from `[dependency-groups].dev` to `[project.dependencies]`
- Ran `uv sync` — resolves to openai 2.38.0; lockfile updated

## Verification

All three plan verification commands pass:
1. Import smoke: `VoiceMode.openai.value == 'openai'` — OK
2. New fields defaults: `bg_music_path is None`, `openai_tts_model=='tts-1'` — OK
3. Full test suite: 311 passed (303 baseline + 8 new Phase 8 tests), 0 failures

## Deviations from Plan

None — plan executed exactly as written.

## Threat Mitigations Applied

- **T-08-02-02 (OPENAI_API_KEY):** python-dotenv now in core deps; `load_dotenv()` already called at CLI entry (commit d10120d). Key never stored in RunConfig.
- **T-08-02-03 (bg_music_volume bounds):** `Field(ge=0.0, le=1.0)` enforced — validated by test_runconfig_bg_music_volume_too_high_raises and test_runconfig_bg_music_volume_negative_raises.
- **T-08-02-01 (bg_music_path disclosure):** `Optional[Path]` validated at model init, never logged.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries beyond what the plan's threat model already covers.

## Known Stubs

None — this plan is purely additive model/config layer; no UI rendering or data flow involved.

## Self-Check: PASSED

Files created/modified:
- `src/avideo/models/config.py` — FOUND
- `tests/test_config_phase8.py` — FOUND
- `pyproject.toml` — FOUND

Commits:
- `ab702ac` — test(08-02): RED phase tests — FOUND
- `25be2e4` — feat(08-02): config.py GREEN implementation — FOUND
- `622b1d7` — feat(08-02): pyproject.toml + lockfile — FOUND
