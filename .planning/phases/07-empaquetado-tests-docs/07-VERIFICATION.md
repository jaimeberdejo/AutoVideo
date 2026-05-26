---
phase: 07-empaquetado-tests-docs
verified: 2026-05-26T00:00:00Z
status: passed
score: 10/10 must-haves verified
overrides_applied: 0
---

# Phase 07: Empaquetado, Tests y Docs — Verification Report

**Phase Goal:** El proyecto se puede instalar con `uv`, ejecutar reproduciblemente en Docker, tiene tests mínimos que validan el core del pipeline, y un README con instrucciones de instalación completas
**Verified:** 2026-05-26
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | El proyecto se instala con `uv sync` y `uv run avideo --help` sale 0 | VERIFIED | `uv run avideo --help` exits 0 confirmed. pyproject.toml has `[project.scripts] avideo = "avideo.cli:app"` and `requires-python = ">=3.11"`. `uv.lock` is tracked in git. |
| 2 | Existe un Dockerfile que pinea la base de Playwright a v1.60.0-noble e instala ffmpeg + poppler-utils | VERIFIED | Dockerfile line 3: `FROM mcr.microsoft.com/playwright/python:v1.60.0-noble`. Lines 6-8: `apt-get install -y --no-install-recommends ffmpeg poppler-utils`. |
| 3 | El Dockerfile copia el binario uv y ejecuta instalación reproducible desde uv.lock (--frozen) | VERIFIED | Line 11: `COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv`. Lines 22 and 28: two-stage `uv sync --frozen --no-dev` (first without project to cache deps layer, then with src). |
| 4 | El Dockerfile define ENTRYPOINT/CMD de forma que `docker run <img> generate ...` invoca el CLI avideo | VERIFIED | Lines 38-39: `ENTRYPOINT ["uv", "run", "avideo"]` + `CMD ["--help"]`. |
| 5 | torch/whisperx NO están en la imagen por defecto | VERIFIED | Dockerfile contains no mention of torch, whisperx, or --extra record (case-insensitive grep confirmed). |
| 6 | Un .dockerignore excluye .git, .venv, workdir/, .planning/ y assets locales grandes | VERIFIED | .dockerignore (13 lines) excludes .git, .venv, workdir/, .planning/, .env, *.mp4, *.wav, *.mp3. All required exclusions present. |
| 7 | El test de storyboard pasa con la API de Anthropic mockeada (sin llamada real ni API key) | VERIFIED | tests/test_storyboard.py patches `avideo.stages.storyboard.call_structured` at the correct import site. `assert mock_cs.called` explicitly confirms no real API call. 8 tests covering: return value, prompt content, language, visual_type enum, stage/checkpoint names, with/without context, duration in prompt. All pass. |
| 8 | El test de timing verifica reparto de duración (suma exacta + clamps) y presupuesto de palabras | VERIFIED | tests/test_timing.py has `test_exact_sum` (parametrized × 3), `test_exact_sum_clamps_active_still_holds`, `test_word_budget` (parametrized × wpm 120/150/180). Asserts `sum(seconds) == duration` exactly and `word_budget == round(seconds * wpm / 60)` for every slide. |
| 9 | El test de render de slide produce/valida un PNG 1920×1080 (o skip limpio sin Chromium) | VERIFIED | tests/test_slides_render.py: `pytest.importorskip("playwright")` at module level; `except PWError: pytest.skip(...)` at runtime. `assert img.size == (1920, 1080)`. Test ran and PASSED (Chromium available). |
| 10 | El README documenta instalación, configuración de env vars reales, flags REALES del CLI, modos/niveles, y Docker | VERIFIED | README.md (170 lines) has sections Installation, Configuration, Usage, Modes & Levels, Docker. All 9 real avideo generate flags documented (--bullets, --duration, --voice, --slides-mode, --level, --context, --dry-run, --burn-subs, --verbose). Non-avideo flags (--env-file, --rm, --extra, --index-url) appear only in docker/pip shell examples, not in the avideo flag table. |

**Score:** 10/10 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pyproject.toml` | [project.scripts] avideo entry, requires-python>=3.11 | VERIFIED | Entry point `avideo = "avideo.cli:app"` present. `requires-python = ">=3.11"` present. uv.lock tracked in git. |
| `Dockerfile` | Playwright v1.60.0-noble base, ffmpeg + poppler-utils, uv binary, uv sync --frozen, ENTRYPOINT avideo | VERIFIED | 39 lines. All required elements present. Two-stage uv sync pattern (--no-install-project then full install). No torch/whisperx. |
| `.dockerignore` | Excludes workdir/, .env, .git, assets | VERIFIED | 13 lines. All required exclusions present. |
| `tests/test_storyboard.py` | TEST-01: mocker.patch at call_structured | VERIFIED | 8 test methods. Correct mock site. `assert mock_cs.called` confirms no real API call. |
| `tests/test_timing.py` | TEST-02: word_budget assertions, exact-sum parametrized | VERIFIED | Parametrized `test_exact_sum` × 3 scenarios, `test_word_budget` × 3 wpm values, clamp tests. |
| `tests/test_slides_render.py` | TEST-03: render_to_png, assert (1920, 1080), graceful skip | VERIFIED | `assert img.size == (1920, 1080)` at line 85. Dual skip guards (importorskip + PWError catch). |
| `README.md` | Installation, Configuration, Usage, Modes & Levels, Docker sections | VERIFIED | 170 lines, 6 sections, all flags match cli.py generate(). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| Dockerfile | uv.lock | `uv sync --frozen` | VERIFIED | Two `uv sync --frozen --no-dev` calls in Dockerfile (lines 22, 28). Lock file copied into image via `COPY pyproject.toml uv.lock ./`. |
| Dockerfile ENTRYPOINT | avideo CLI | `ENTRYPOINT ["uv", "run", "avideo"]` | VERIFIED | ENTRYPOINT at line 38, CMD ["--help"] at line 39. |
| tests/test_storyboard.py | avideo.stages.storyboard.call_structured | `mocker.patch` | VERIFIED | `mocker.patch("avideo.stages.storyboard.call_structured", return_value=fake)` — correct import site. |
| tests/test_timing.py | avideo.stages.timing.apportion_seconds / TimingStage | import + asserts | VERIFIED | Direct imports of `apportion_seconds`, `TimingStage`, `MIN_SECONDS`, `MAX_SECONDS`. |
| tests/test_slides_render.py | avideo.integrations.playwright.SlideRenderer | render_to_png | VERIFIED | `from avideo.integrations.playwright import SlideRenderer` + `renderer.render_to_png(_MINIMAL_HTML, out_png)`. |
| README.md (Usage) | src/avideo/cli.py (flags) | flags documented == generate() options | VERIFIED | All 9 `avideo generate` flags in README match the 9 flags in cli.py generate(). Non-avideo flags appear only in shell/docker examples. |
| README.md (Configuration) | .env | ANTHROPIC_API_KEY / ELEVENLABS_API_KEY | VERIFIED | Both env var names present verbatim in README Configuration section. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `uv run avideo --help` exits 0 | `uv run avideo --help` | exit code 0 | PASS |
| Full test suite: 303 passed, 0 failures | `uv run python -m pytest -q` | `303 passed, 5 warnings in 3.42s` | PASS |
| Dockerfile has no torch/whisperx | case-insensitive grep | no matches | PASS |
| README flags match cli.py | manual cross-check | 9 avideo flags documented, 0 invented | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PKG-01 | 07-01-PLAN.md | El proyecto se instala con `pyproject.toml` gestionado con `uv` | SATISFIED | pyproject.toml has correct entry point and requires-python; uv.lock committed; `uv run avideo --help` exits 0. |
| PKG-02 | 07-01-PLAN.md | Un Dockerfile reproducible con Playwright (versión alineada), FFmpeg y Poppler | SATISFIED | Dockerfile pins v1.60.0-noble, installs ffmpeg+poppler-utils, uses uv sync --frozen, ENTRYPOINT avideo. |
| TEST-01 | 07-02-PLAN.md | Test del storyboard con la API de Anthropic mockeada | SATISFIED | tests/test_storyboard.py: 8 tests, mocker.patch at correct site, assert mock_cs.called, all pass. |
| TEST-02 | 07-02-PLAN.md | Test del director de timing (reparto de duración + presupuesto de palabras) | SATISFIED | tests/test_timing.py: exact-sum invariant parametrized × 3, word_budget parametrized × 3 wpm, clamp tests, all pass. |
| TEST-03 | 07-02-PLAN.md | Test de render de una slide a PNG | SATISFIED | tests/test_slides_render.py: assert img.size == (1920, 1080), dual skip guards, passed in this environment. |
| DOC-01 | 07-03-PLAN.md | README.md con instalación, Playwright browsers, FFmpeg, y ejemplos de uso | SATISFIED | README.md 170 lines: Installation + Configuration + Usage + Modes & Levels + Docker, real flags, real env vars, 3 concrete examples. |

### Anti-Patterns Found

No blockers or warnings found.

| File | Pattern | Severity | Assessment |
|------|---------|----------|------------|
| Dockerfile | `ghcr.io/astral-sh/uv:latest` uses floating `latest` tag | Info | Accepted per T-07-01 (uv is a static build binary; documented in 07-01-SUMMARY.md). Not a blocker. |
| README.md | `--env-file`, `--extra`, `--rm` appear in grep of all README flags | Info | These flags appear only in `docker run` and `pip install` shell examples, not in the `avideo generate` flags table. No invented avideo flags. |

### Human Verification Required

None. All must-haves are verifiable programmatically and confirmed.

---

_Verified: 2026-05-26T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
