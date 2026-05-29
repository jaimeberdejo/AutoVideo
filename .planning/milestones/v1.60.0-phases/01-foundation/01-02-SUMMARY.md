---
phase: 01-foundation
plan: "02"
subsystem: cli
tags: [python, typer, rich, pydantic, cli, tdd]
dependency_graph:
  requires:
    - avideo package importable on Python 3.11 (01-01)
    - RunConfig BaseSettings with CLI/YAML/default merge (01-01)
    - Pydantic I/O contracts for all pipeline stages (01-01)
  provides:
    - avideo.cli Typer app with generate subcommand and all nine flags
    - avideo.utils.rich_ui Console + ValidationError table + RichHandler logging
    - CLI > config.yaml > default precedence proven by test
    - Clean validation-error display (no raw tracebacks)
  affects: [01-03, all downstream phases that invoke the CLI]
tech_stack:
  added: []
  patterns:
    - Typer @app.callback() enables multi-subcommand mode with single command registered
    - Optional flags default to None so only user-supplied values override config.yaml
    - Orchestrator lazy-imported inside generate() so tests can stub via sys.modules injection
    - TDD RED/GREEN cycle with test commit preceding feat commit
key_files:
  created:
    - src/avideo/cli.py
    - tests/test_cli.py
  modified:
    - src/avideo/utils/rich_ui.py (Task 1, committed in prior partial run as 1f3bcb3)
decisions:
  - "Use @app.callback() to force Typer into multi-subcommand mode — single @app.command() flattens the CLI, breaking subcommand routing"
  - "Optional flags typed as Optional[T] with Typer default None so unset values fall through to YamlConfigSettingsSource (CLI > YAML > default)"
  - "Lazy import of avideo.orchestrator inside generate() body allows sys.modules stub injection in tests without a real orchestrator.py"
metrics:
  duration_seconds: 480
  completed_date: "2026-05-25"
  tasks_completed: 2
  files_created: 2
---

# Phase 01 Plan 02: CLI and Rich UI Summary

**One-liner:** Typer multi-subcommand CLI with nine pipeline flags wired into RunConfig and Rich validation-error rendering, TDD green.

## What Was Built

### Task 1: rich_ui — Console, ValidationError table, logging setup (committed 1f3bcb3)

- `console = Console(stderr=True)` — module-level, errors/status to stderr to avoid polluting piped stdout
- `show_validation_error(e, console)` — renders ALL Pydantic errors as a `rich.table.Table` with "Field" and "Error" columns; loc joined by " → "; never lets a raw traceback reach the user
- `setup_logging(verbose)` — configures root logger with `RichHandler`; DEBUG + rich tracebacks when verbose=True, INFO + compact tracebacks otherwise
- Full type hints and docstrings; no pause_for_approval or progress helpers (reserved for plan 01-03)

### Task 2: Typer CLI generate subcommand + config-merge precedence (TDD)

**RED commit (27cbe87):** 11 tests in `tests/test_cli.py` covering:
- CLI-01: basic `generate --bullets --duration 120` exits 0 (orchestrator stubbed)
- CLI-01: missing --bullets exits non-zero
- CLI-04: `--level 5` exits non-zero; output never contains "Traceback"
- CLI-03/02: `--slides-mode hybrid` and `--voice record` captured in RunConfig
- CLI-07: CLI `--level 1` overrides config.yaml level (precedence test)
- CLI-05: `--context <path>` sets RunConfig.context; omit → None
- CLI-06: `--dry-run` sets RunConfig.dry_run True
- `--burn-subs` sets RunConfig.burn_subs True
- Orchestrator stubbed via `monkeypatch.setitem(sys.modules, "avideo.orchestrator", ...)` — no real orchestrator.py required

**GREEN commit (7a4bf0b):** `src/avideo/cli.py` with:
- `app = typer.Typer(rich_markup_mode="rich")` with `@app.callback()` to enable multi-subcommand mode
- `@app.command()` `def generate(...)` with nine `Annotated` options
- Required: `--bullets` (exists=True, file_okay=True, dir_okay=False) and `--duration` (min=1)
- Optional with default None: `--voice`, `--slides-mode`, `--level`, `--context` — unset values fall through to config.yaml
- Boolean flags with False default: `--dry-run`, `--burn-subs`, `--verbose`
- Body: `setup_logging(verbose)` → build kwargs (None-filtered for optionals) → `RunConfig(**kwargs)` → `show_validation_error` on ValidationError → `raise typer.Exit(1)` → `import avideo.orchestrator as _orch; _orch.run_pipeline(config)`

## Commits

| Task | Commit | Message |
|------|--------|---------|
| Task 1 | 1f3bcb3 | feat(01-02): add rich_ui with Console, ValidationError table, and RichHandler logging |
| Task 2 RED | 27cbe87 | test(01-02): add failing CLI tests (TDD RED) |
| Task 2 GREEN | 7a4bf0b | feat(01-02): implement Typer CLI generate subcommand (TDD GREEN) |

## Test Results

```
26 passed in 0.15s
```

- `tests/test_cli.py`: 11 tests — all nine flags, config-merge precedence (CLI-07), ValidationError path, enum flags, boolean flags
- `tests/test_models.py` + `tests/test_workdir.py`: 15 tests (unchanged from 01-01)

## TDD Gate Compliance

- RED gate: commit `27cbe87` (`test(01-02): ...`) — present
- GREEN gate: commit `7a4bf0b` (`feat(01-02): ...`) — present, after RED commit
- REFACTOR gate: not needed — code is clean

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking Issue] Added @app.callback() to enable multi-subcommand routing**
- **Found during:** Task 2 GREEN (first test run after creating cli.py)
- **Issue:** Typer flattens a single `@app.command()` into a root command, making `runner.invoke(app, ["generate", ...])` fail with "Got unexpected extra argument (generate)"
- **Fix:** Added `@app.callback()` `def _main()` before the `generate` command, which triggers Typer's multi-subcommand mode and routes "generate" as a named subcommand
- **Files modified:** `src/avideo/cli.py`
- **Commit:** 7a4bf0b (included in GREEN commit)

## Known Stubs

- `avideo.orchestrator.run_pipeline` — invoked at end of `generate()` but the real module does not exist yet. Plan 01-03 creates it. Tests stub it via `sys.modules` injection. This is intentional and tracked.

## Threat Flags

No new threat surface beyond the plan's threat model (T-01-05, T-01-06, T-01-07 all mitigated as specified):
- T-01-05: Path traversal — Typer `exists=True, file_okay=True, dir_okay=False` on --bullets and --context
- T-01-06: Out-of-range values — Typer `min/max` on --level and --duration; RunConfig Field validators double-guard
- T-01-07: Raw traceback — ValidationError caught → show_validation_error → Exit(1); test asserts "Traceback" not in output

## Self-Check: PASSED
