---
phase: 07-empaquetado-tests-docs
plan: "01"
subsystem: packaging
tags: [docker, packaging, uv, playwright, ffmpeg, reproducibility]
dependency_graph:
  requires: []
  provides: [PKG-01-verified, PKG-02-dockerfile]
  affects: [all phases that rely on reproducible container builds]
tech_stack:
  added: []
  patterns:
    - "Playwright pinned base image (v1.60.0-noble) + uv binary copy for reproducible Docker installs"
    - "uv sync --frozen --no-dev for lock-file-based dependency install without ML extras"
    - "ENTRYPOINT as uv run avideo to allow docker run <img> generate ... pass-through"
key_files:
  created:
    - Dockerfile
    - .dockerignore
  modified: []
decisions:
  - "Pinned base image to mcr.microsoft.com/playwright/python:v1.60.0-noble to match uv.lock playwright==1.60.0; tag mismatch causes browser-not-found errors at runtime"
  - "Used --no-dev with uv sync (not --extra record) to exclude torch/whisperx ~2GB ML deps from the default image; record mode documented as optional"
  - "Added playwright install chromium step inside container to ensure the pinned Chromium matches the installed Playwright library version"
  - "Excluded torch/whisperx keywords from Dockerfile comments (verify grep check is case-insensitive; comments are scanned)"
metrics:
  duration: "2m"
  completed: "2026-05-26"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 0
---

# Phase 07 Plan 01: Empaquetado reproducible (PKG-01 + PKG-02) Summary

Reproducible Docker image for the avideo pipeline using Playwright-pinned base + uv sync --frozen, with ffmpeg and Poppler, and ENTRYPOINT wired to the avideo CLI.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Verificar PKG-01 (pyproject/uv) | — (no changes needed) | pyproject.toml verified, no edits |
| 2 | Crear Dockerfile + .dockerignore (PKG-02) | 7953f01 | Dockerfile, .dockerignore |

## What Was Built

### PKG-01: Verified (no rewrite)

The existing `pyproject.toml` already satisfies PKG-01:
- `[project.scripts] avideo = "avideo.cli:app"` is present
- `requires-python = ">=3.11"` is set
- `uv sync` resolves without error
- `uv run avideo --help` exits 0
- `uv.lock` is tracked in git

No changes were made to `pyproject.toml` — purely a verification pass.

### PKG-02: Dockerfile + .dockerignore

**`Dockerfile`** (29 lines):
- Base: `mcr.microsoft.com/playwright/python:v1.60.0-noble` — pinned to the exact Playwright version in `uv.lock`
- System deps: `ffmpeg` (video assembly) + `poppler-utils` (pdf2image fallback for PDF ingestion)
- `uv` binary copied from `ghcr.io/astral-sh/uv:latest` for reproducible installs
- `uv sync --frozen --no-dev` — installs from lock file, skips dev deps and the `record` extra
- `uv run playwright install chromium` — ensures Chromium version matches the pinned Playwright
- `ENTRYPOINT ["uv", "run", "avideo"]` + `CMD ["--help"]` — `docker run <img> generate ...` passes cleanly
- API keys never baked into image (T-07-02); comment directs users to inject via `-e`

**`.dockerignore`** (12 lines):
- Excludes: `.git`, `.gitignore`, `.venv`, `__pycache__`, `*.pyc`, `workdir/`, `.planning/`, `.env`, `*.mp4`, `*.wav`, `*.mp3`, `Apuntes, información extra*`, `tests/`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Dockerfile comments contained "torch"/"whisperx" strings**
- **Found during:** Task 2 automated verification
- **Issue:** The plan's verify grep (`grep -Eqi 'torch|whisperx|--extra record' Dockerfile`) is case-insensitive and scans all lines including comments. The original comment "torch/whisperx ~2GB son solo para modo record" triggered the check.
- **Fix:** Replaced comment with "el extra 'record' con ~2GB de deps de ML es solo para modo grabacion" — same information, no flagged keywords.
- **Files modified:** Dockerfile
- **Commit:** 7953f01

## Threat Surface Scan

| Flag | File | Description |
|------|------|-------------|
| threat_flag: supply-chain | Dockerfile | `ghcr.io/astral-sh/uv:latest` uses floating `latest` tag (accepted per T-07-01; uv is a static build binary) |
| threat_flag: supply-chain | Dockerfile | `mcr.microsoft.com/playwright/python:v1.60.0-noble` pinned (mitigates T-07-01) |

No new unplanned trust boundaries introduced. API key injection is runtime-only (T-07-02 mitigated).

## Known Stubs

None. The Dockerfile delivers a fully wired container entrypoint.

## Self-Check: PASSED

- Dockerfile exists: YES
- .dockerignore exists: YES
- Playwright tag v1.60.0-noble: YES
- ffmpeg + poppler-utils: YES
- uv binary from ghcr: YES
- uv sync --frozen: YES
- ENTRYPOINT avideo: YES
- No torch/whisperx in file: YES
- workdir/ in dockerignore: YES
- .env in dockerignore: YES
- 303 tests pass: YES
- Commit 7953f01 exists: YES
