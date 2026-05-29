# Phase 7: Empaquetado + Tests + Docs - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning
**Mode:** Autonomous (decisions at Claude's discretion per user authorization)

<domain>
## Phase Boundary

Make the project installable + reproducible: `uv`-managed `pyproject.toml` with the `avideo` entry point, a reproducible `Dockerfile` (Playwright browsers + FFmpeg + Poppler), the three minimal core tests, and a complete `README.md`.

Requirements in scope: **PKG-01** (uv-managed pyproject install), **PKG-02** (reproducible Dockerfile w/ Playwright pinned + FFmpeg + Poppler), **TEST-01** (storyboard test, Anthropic mocked), **TEST-02** (timing director test), **TEST-03** (slide render → PNG test), **DOC-01** (README: install + config + usage).

Out of scope: EXPORT-01 (.pptx export, v2), CI pipelines, publishing to PyPI.
</domain>

<decisions>
## Implementation Decisions

### Current state (DO NOT recreate what exists — verify/extend instead)
- `pyproject.toml` ALREADY exists: `[project] name="avideo"`, `requires-python=">=3.11"`, `[project.scripts] avideo = "avideo.cli:app"`, `[build-system]`, and optional extras. **PKG-01 is largely satisfied** — the plan should VERIFY (not rewrite): `uv sync` resolves; `uv run avideo --help` works; dependencies are pinned/compatible with the CLAUDE.md stack table; `uv.lock` is present and committed.
- The three minimal tests ALREADY exist: `tests/test_storyboard.py`, `tests/test_timing.py`, `tests/test_slides_render.py` (303 tests pass total). **TEST-01/02/03 are likely satisfied** — the plan should VERIFY each one actually covers its requirement (storyboard with Anthropic mocked; timing apportionment + word budget; slide HTML→PNG render) and ADD a focused test only if a gap exists. Do not duplicate existing coverage.

### Real work to deliver
- **PKG-02 — Dockerfile (NEW, primary deliverable):** Multi-stage-friendly, per CLAUDE.md:
  - Base: `mcr.microsoft.com/playwright/python:v1.60.0-noble` (PIN to match the installed playwright version — verify `playwright` version in uv.lock and align the tag).
  - `apt-get install -y ffmpeg poppler-utils` (FFmpeg for assembly, Poppler for pdf2image fallback).
  - Copy uv binary: `COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv`.
  - `uv sync --frozen` (or `--no-dev`) for reproducible install from `uv.lock`.
  - Install Playwright browser(s): `uv run playwright install chromium` (browsers already in the base image, but ensure the pinned Chromium matches).
  - WhisperX/torch is record-mode only and heavy — make it OPTIONAL (document a build arg or separate extra; do NOT bloat the default image with torch unless trivial). Default image must run `auto` mode end-to-end (storyboard→slides→voice(elevenlabs)→assemble).
  - Set `ENTRYPOINT`/`CMD` so `docker run <img> avideo ...` works; `WORKDIR /app`.
  - Add a `.dockerignore` (exclude `.git`, `.venv`, `workdir/`, `.planning/`, large local assets).
- **DOC-01 — README.md (NEW, primary deliverable):** Sections:
  - Project intro (one-paragraph: bullets + duration → narrated video).
  - Installation: `uv sync`, `uv run playwright install chromium`, system deps (FFmpeg, Poppler; WhisperX/torch note for record mode).
  - Configuration: `.env` with `ANTHROPIC_API_KEY` + `ELEVENLABS_API_KEY`; `bullets.yaml` and `theme.yaml` formats.
  - Usage: the main `avideo` CLI flags (slides-mode auto/hybrid/manual, level 1-4, voice mode, duration), with 2-3 concrete example invocations.
  - Docker usage: build + run.
  - Modes & levels overview (L1-L4, auto/hybrid/manual, elevenlabs/record).
  - Keep it accurate to the ACTUAL CLI flags in `src/avideo/cli.py` — read that file and document the real options (no invented flags).

### Conventions
- No new runtime dependencies unless required; reuse what's in pyproject/uv.lock.
- README must reflect the real CLI surface (read cli.py) and the real env-var names.
- Dockerfile must be buildable in principle and pin the Playwright image to the installed version.
</decisions>

<code_context>
## Existing Code Insights

- `pyproject.toml`: `[project.scripts] avideo = "avideo.cli:app"` — entry point already wired.
- `src/avideo/cli.py`: `app = typer.Typer(...)` — the real CLI; READ THIS for the actual flags/options to document in README.
- `CLAUDE.md`: full tech-stack table + Docker recipe (Playwright base image, FFmpeg, Poppler, uv copy, torch CPU index) + env vars (`ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`). This is the authoritative source for the Dockerfile and README install steps — no external research needed.
- Tests: `tests/test_storyboard.py` (TEST-01), `tests/test_timing.py` (TEST-02), `tests/test_slides_render.py` (TEST-03) already exist; 303 tests pass.
- `uv.lock` present (committed) — verify the playwright pin for the Docker base tag.
</code_context>

<specifics>
## Specific Ideas

- Pin the Playwright Docker image tag to the exact installed playwright version (mismatch = browsers not found).
- Keep torch/WhisperX out of the default Docker image (record mode only) to avoid multi-GB bloat; document the optional install.
- README examples must use real flags from cli.py.
</specifics>

<deferred>
## Deferred Ideas

- PyPI publishing / release automation — out of scope.
- CI workflow files — out of scope.
- EXPORT-01 (.pptx export) — v2.
- GPU WhisperX Docker variant — document only, don't build.
</deferred>
