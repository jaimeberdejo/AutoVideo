---
phase: "02-llm-pipeline"
plan: "01"
subsystem: ingestion
tags: [python, ingestion, pymupdf, python-pptx, yaml, pydantic, tdd]

dependency_graph:
  requires:
    - "01-03: WorkdirManager, orchestrator, stubs, models skeleton"
  provides:
    - "BulletsInput model + load_bullets() loader (consumed by 02-02, 02-03)"
    - "ContextStage real extraction (consumed by 02-02 storyboard prompt)"
  affects:
    - "02-02: storyboard stage reads bullets via load_bullets + context via ContextStage"
    - "02-03: cost_estimator reads bullets via load_bullets for bullet-count heuristic"

tech_stack:
  added:
    - "anthropic==0.104.1 — Anthropic SDK (required by 02-02/02-03)"
    - "pymupdf==1.27.2.3 — PDF text extraction via fitz"
    - "python-pptx==1.0.2 — .pptx text extraction"
  patterns:
    - "PyMuPDF suffix dispatch: import fitz; needs_pass guard; page.get_text('text')"
    - "python-pptx: has_notes_slide guard before notes_slide access (Pitfall 6)"
    - "_DISPATCH map keyed on Path.suffix for open-for-extension suffix routing"
    - "Lazy fixture imports in conftest (import fitz / from pptx inside fixture body)"
    - "BulletsInput: yaml.safe_load → model_validate (no arbitrary object construction)"

key_files:
  created:
    - "src/avideo/models/bullets.py — BulletsInput(title, bullets) Pydantic model"
    - "src/avideo/utils/bullets.py — load_bullets(path) shared loader"
    - "src/avideo/stages/context.py — ContextStage real extraction (pdf/pptx/md)"
    - "tests/test_bullets.py — 5 tests: load_bullets + BulletsInput coverage"
    - "tests/test_context.py — 8 tests: CTX-01/CTX-02 coverage incl. encrypted + empty edges"
  modified:
    - "pyproject.toml — added anthropic, pymupdf, python-pptx deps"
    - "uv.lock — updated lockfile"
    - "src/avideo/models/__init__.py — export BulletsInput"
    - "tests/conftest.py — added sample_md, sample_pdf, sample_pptx, encrypted_pdf fixtures"

decisions:
  - "CONTEXT_TOKEN_CAP=6000 (Claude's discretion per CONTEXT.md D-04; ~24k chars headroom under 1M window)"
  - "Empty extracted text returns used=False with Rich warning (CTX-02 semantics, Pitfall 5)"
  - "Lazy conftest fixture imports to decouple test collection from dep install order"
  - "ContextStage does NOT wire into PIPELINE_STAGES — stub swap deferred to 02-03 (single-owner rule)"
  - "load_bullets uses yaml.safe_load + model_validate (T-02-05: no arbitrary YAML objects)"

metrics:
  duration_seconds: 272
  completed_date: "2026-05-25"
  tasks_completed: 3
  files_changed: 9
---

# Phase 02 Plan 01: Context Ingestion + Bullets Loader Summary

**One-liner:** Real context ingestion (PyMuPDF/python-pptx/markdown) with suffix dispatch + BulletsInput loader closing the bullets.yaml parsing gap from Phase 1.

## What Was Built

This plan replaced the Phase-1 `ContextStub` with a real `ContextStage` that extracts text from `.pdf`, `.pptx`, and `.md` documents, and created the shared `BulletsInput` model + `load_bullets()` loader that Phase-2 plans (02-02, 02-03) depend on.

Three new runtime dependencies were added: `anthropic==0.104.1`, `pymupdf==1.27.2.3`, `python-pptx==1.0.2`.

### ContextStage

`src/avideo/stages/context.py` implements:

- `extract_pdf`: `import fitz`; `needs_pass` guard raises `ValueError` on encrypted PDFs; iterates pages with `page.get_text("text")`; closes doc.
- `extract_pptx`: `Presentation(str(path))`; iterates shapes with `has_text_frame`; guards `has_notes_slide` before touching `notes_slide` (Pitfall 6).
- `extract_md`: `path.read_text(encoding="utf-8")`.
- `_DISPATCH`: `{".pdf": ..., ".pptx": ..., ".md": ..., ".markdown": ...}` — suffix allow-list validated before file open (T-02-01).
- `CONTEXT_TOKEN_CAP = 6000` + `truncate_to_tokens()` — ~4 chars/token heuristic (D-04, T-02-02).
- Empty extraction → `used=False` + Rich warning (CTX-02, Pitfall 5). Never logs raw content (T-02-04).

`stage_name = "context"` is identical to ContextStub — orchestrator and workdir contract unchanged.

### BulletsInput + load_bullets

`src/avideo/models/bullets.py` — `BulletsInput(title: str, bullets: list[str])` Pydantic model, exported from `avideo.models`.

`src/avideo/utils/bullets.py` — `load_bullets(path) -> BulletsInput`: `yaml.safe_load` + `model_validate`; surfaces missing keys as `ValidationError`.

## TDD Gate Compliance

- RED commit: `7518f61` — `test(02-01): add failing tests for context + bullets (RED)`
- GREEN commits:
  - `6c9b965` — `feat(02-01): add deps + BulletsInput model + load_bullets loader`
  - `480ba01` — `feat(02-01): ContextStage real extraction replacing ContextStub`
- No REFACTOR pass needed — implementation was clean on first pass.

## Test Results

All 57 tests pass (zero regressions):
- `tests/test_bullets.py`: 5 tests — happy path, missing keys, model fields, export
- `tests/test_context.py`: 8 tests — no context, md, pdf, pptx, encrypted PDF, truncation, unsupported suffix, stage_name
- Existing 44 tests: all green

## Deviations from Plan

None — plan executed exactly as written.

The DeprecationWarnings from PyMuPDF's SWIG internals (`SwigPyPacked`, `SwigPyObject`) are third-party library internals, out of scope, and do not affect functionality.

## Known Stubs

`ContextStage` is NOT yet wired into `PIPELINE_STAGES` (still uses `ContextStub` there). This is intentional per the plan: "Do NOT wire into PIPELINE_STAGES here — the stub swap for all four stages happens once in 02-03 to keep stubs.py single-owner." This stub in `stubs.py` will be replaced in plan 02-03.

## Threat Flags

None — no new network endpoints, auth paths, or schema changes at trust boundaries were introduced. All mitigations from the threat register were applied (T-02-01 through T-02-04).

## Self-Check: PASSED

Files created/exist:
- src/avideo/models/bullets.py: FOUND
- src/avideo/utils/bullets.py: FOUND
- src/avideo/stages/context.py: FOUND
- tests/test_bullets.py: FOUND
- tests/test_context.py: FOUND

Commits exist:
- 7518f61: FOUND (RED: test scaffolding)
- 6c9b965: FOUND (GREEN: BulletsInput + load_bullets)
- 480ba01: FOUND (GREEN: ContextStage)
