---
phase: 01-foundation
plan: "01"
subsystem: foundation
tags: [python, pydantic, uv, models, workdir, tdd]
dependency_graph:
  requires: []
  provides:
    - avideo package importable on Python 3.11
    - RunConfig BaseSettings with CLI/YAML/default merge
    - Pydantic I/O contracts for all pipeline stages
    - WorkdirManager atomic checkpoint writes and done markers
  affects: [01-02, 01-03, all downstream phases]
tech_stack:
  added:
    - Python 3.11.14 via uv
    - pydantic 2.13.4
    - pydantic-settings 2.14.1
    - typer 0.25.1
    - rich 15.0.0
    - pyyaml 6.0.3
    - pytest 9.0.3
    - pytest-mock 3.15.1
  patterns:
    - Pydantic BaseSettings with YamlConfigSettingsSource for CLI>YAML>default precedence
    - Atomic writes via os.replace (same-filesystem tmp→target, no partial JSON)
    - Done markers (.stage.done) gate is_done independently of checkpoint content
key_files:
  created:
    - pyproject.toml
    - .python-version
    - config.yaml
    - bullets.yaml
    - .gitignore
    - uv.lock
    - src/avideo/models/config.py
    - src/avideo/models/context.py
    - src/avideo/models/storyboard.py
    - src/avideo/models/timing.py
    - src/avideo/models/script.py
    - src/avideo/models/slides.py
    - src/avideo/models/verification.py
    - src/avideo/models/voice.py
    - src/avideo/models/assembly.py
    - src/avideo/models/__init__.py
    - src/avideo/utils/workdir.py
    - tests/conftest.py
    - tests/test_models.py
    - tests/test_workdir.py
  modified: []
decisions:
  - "Use os.replace (not Path.rename) for atomic writes — cross-platform POSIX+NTFS guarantee"
  - "Tmp file in same directory as target ensures same-filesystem rename is always atomic"
  - "dependency-groups.dev used instead of deprecated tool.uv.dev-dependencies"
  - "pydantic-settings plain (no [yaml] extra) works with pyyaml installed separately"
metrics:
  duration_seconds: 247
  completed_date: "2026-05-25"
  tasks_completed: 3
  files_created: 20
---

# Phase 01 Plan 01: Project Bootstrap and Data Layer Summary

**One-liner:** uv project on Python 3.11 with Pydantic v2 I/O contracts for all pipeline stages and atomic WorkdirManager via os.replace.

## What Was Built

### Task 0: Bootstrap uv project
- Installed Python 3.11.14 via `uv python install 3.11`
- Initialized uv project with `--lib --name avideo` scaffold
- Configured `pyproject.toml` with correct entry point, pytest config, and `dependency-groups`
- Installed 5 core deps and 3 dev deps
- Created `config.yaml` (no secrets), `bullets.yaml` example, and `.gitignore`
- Verified `YamlConfigSettingsSource` imports successfully

### Task 1: Pydantic I/O contracts (TDD)
- `RunConfig(BaseSettings)`: duration>0 (gt=0), level 1–4 (ge=1/le=4), str-Enum coercion, YAML source with init>YAML>env priority
- 8 stage output models (ContextOutput, StoryboardOutput, TimingOutput, ScriptOutput, SlidesOutput, VerificationReport, VoiceOutput, AssemblyOutput) all round-trip via `model_dump_json`/`model_validate_json`
- `models/__init__.py` re-exports all 14 names with `__all__`
- 8 tests in `test_models.py` — all green

### Task 2: WorkdirManager (TDD)
- Single path authority: `checkpoint_path`, `done_marker`, subdirectory creation
- Atomic write: tmp file in same directory → `os.replace` (not `Path.rename`)
- Done-marker lifecycle: `is_done` / `mark_done` independent of checkpoint content
- Interrupted-write test: monkeypatches `os.replace` to raise OSError, asserts no partial file and no done marker
- 7 tests in `test_workdir.py` — all green

## Commits

| Task | Commit | Message |
|------|--------|---------|
| Task 0 | 9d96c25 | chore(01-01): bootstrap uv project on Python 3.11 with core deps |
| Task 1 | e770c39 | feat(01-01): add Pydantic I/O contracts for all pipeline stages |
| Task 2 | 691c390 | feat(01-01): implement WorkdirManager with atomic writes and done markers |

## Test Results

```
15 passed in 0.06s
```

- `tests/test_models.py`: 8 tests — RunConfig validation + stage output round-trips
- `tests/test_workdir.py`: 7 tests — subdirs, checkpoint r/w, done markers, atomic write, interrupt simulation

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

### Minor Adjustments

**1. [Rule 1 - Bug] Used `dependency-groups` instead of deprecated `tool.uv.dev-dependencies`**
- Found during: Task 0
- Issue: `uv sync` emitted deprecation warning for `[tool.uv.dev-dependencies]`
- Fix: Switched to PEP 735 `[dependency-groups]` which is the current standard
- Files modified: `pyproject.toml`
- Commit: 9d96c25

## Known Stubs

None — this plan creates data contracts only, no stub implementations.

## Threat Flags

No new threat surface beyond what is in the plan's threat model.

## Self-Check: PASSED

- [x] `pyproject.toml` exists with `requires-python = ">=3.11"` and `avideo = "avideo.cli:app"`
- [x] `src/avideo/models/config.py` exists with `class RunConfig(BaseSettings)`
- [x] `src/avideo/utils/workdir.py` exists with `os.replace`
- [x] `tests/test_workdir.py` exists with `def test_` and `os.replace` monkeypatch
- [x] Commit 9d96c25 exists (Task 0)
- [x] Commit e770c39 exists (Task 1)
- [x] Commit 691c390 exists (Task 2)
- [x] `uv run pytest tests/ -x -q` → 15 passed
