---
phase: 7
slug: empaquetado-tests-docs
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-26
---

# Phase 7 — Validation Strategy

## Test Infrastructure
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Quick run | `uv run pytest tests/test_storyboard.py tests/test_timing.py tests/test_slides_render.py -q` |
| Full suite | `uv run pytest -q` |

## Validation Requirements
| Req | Observable signal | Test strategy |
|-----|-------------------|---------------|
| PKG-01 | `uv sync` resolves; `uv run avideo --help` exits 0; uv.lock committed | CLI smoke: `uv run avideo --help` returns usage; pyproject has [project.scripts] avideo. |
| PKG-02 | Dockerfile exists, pins playwright base tag, installs ffmpeg+poppler, copies uv, uv sync --frozen | Static checks: grep Dockerfile for base image tag, `ffmpeg`, `poppler-utils`, `uv sync`, ENTRYPOINT. (Build not run in CI.) |
| TEST-01 | storyboard test with Anthropic mocked passes | `uv run pytest tests/test_storyboard.py -q` green; asserts no real API call. |
| TEST-02 | timing apportionment + word budget test passes | `uv run pytest tests/test_timing.py -q` green. |
| TEST-03 | slide HTML→PNG render test passes | `uv run pytest tests/test_slides_render.py -q` green. |
| DOC-01 | README has Installation, Configuration, Usage, Docker sections; flags match cli.py | grep README for required headings; flags cross-checked against cli.py. |

## Regression Guard
- Full suite stays green (≥303 tests).
