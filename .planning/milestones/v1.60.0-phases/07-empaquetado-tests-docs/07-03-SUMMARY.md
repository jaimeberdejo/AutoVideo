---
phase: 07-empaquetado-tests-docs
plan: "03"
subsystem: docs
tags: [readme, documentation, cli, docker, installation]
dependency_graph:
  requires: []
  provides: [DOC-01]
  affects: [README.md]
tech_stack:
  added: []
  patterns: [cli-documentation, docker-run-env-injection]
key_files:
  created:
    - README.md
  modified: []
decisions:
  - "Documented only real avideo generate flags from cli.py (no invented flags)"
  - "Docker usage shows both -e and --env-file patterns for API key injection"
  - "record mode installation note placed in Installation section with torch-first caveat"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-26"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 7 Plan 3: README (DOC-01) Summary

**One-liner:** Complete README.md with accurate CLI flags (read from cli.py), install/config/Docker sections, and modes/levels overview — no invented flags.

## What Was Built

Created `/README.md` (170 lines) with six sections:

1. **Intro paragraph** — bullets + duration -> narrated slide video, SVG-only visuals.
2. **Installation** — system deps (FFmpeg/Poppler via brew/apt), `uv sync` + `playwright install chromium`, optional record-mode torch/whisperx install (~2 GB).
3. **Configuration** — `.env` file with `ANTHROPIC_API_KEY` + `ELEVENLABS_API_KEY`, `bullets.yaml` real format (title + bullets list), `config.yaml` real keys (voice, slides_mode, level, wpm, voice_id, language) with CLI > YAML > default precedence note, `theme.yaml` mention.
4. **Usage** — full flag table for `avideo generate` (9 flags: --bullets, --duration, --voice, --slides-mode, --level, --context, --dry-run, --burn-subs, --verbose) + 3 concrete invocation examples.
5. **Modes & Levels** — slides (auto/hybrid/manual), voice (elevenlabs/record), level 1-4 table.
6. **Docker** — build command, run with `-e` and `--env-file`, note that image covers auto+elevenlabs only.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write README.md (DOC-01) | bdbd764 | README.md (created, 170 lines) |
| 2 | Validate flags match cli.py | bdbd764 | README.md (no changes — all flags verified correct) |

## Verification Results

- All 9 flags in the Usage section verified against `src/avideo/cli.py` generate() function.
- Cross-check: CLI flags = `--bullets`, `--burn-subs`, `--context`, `--dry-run`, `--duration`, `--level`, `--slides-mode`, `--verbose`, `--voice` — all 9 documented, zero invented.
- Non-avideo flags (`--env-file`, `--rm`, `--extra`, `--index-url`) appear only in Docker/installation shell examples, not in the avideo Usage section.
- Full test suite: 303 passed (0 failures).
- Section grep checks: Installation, Configuration, Usage, Docker, `avideo generate`, `playwright install chromium`, `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`, `--slides-mode`, `--duration` — all present.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — README documents the real, fully implemented CLI surface.

## Threat Flags

None — no new network endpoints, auth paths, or schema changes introduced. Documentation correctly instructs users to use `.env` (not committed) and Docker `-e`/`--env-file` injection (never baking secrets into the image), satisfying T-07-06.

## Self-Check: PASSED

- README.md exists: FOUND
- Commit bdbd764 exists: FOUND
- 303 tests pass: CONFIRMED
- All flags match cli.py generate() options: CONFIRMED
