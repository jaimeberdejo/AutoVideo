---
phase: 06-slides-hybrid-verificador
plan: "01"
subsystem: slides
tags: [slides, hybrid, manual, ingest, dispatch, tdd, pydantic, pymupdf]
dependency_graph:
  requires:
    - 05-01  # AssembleStage (FFmpeg) — pipeline complete through assemble
  provides:
    - SlidesDispatchStage (stage_name="slides") routing auto/hybrid/manual
    - ingest_slide helper (PNG copy, PDF rasterize, PPTX error)
    - SlideDesignProposal model (per-slide brief JSON)
  affects:
    - src/avideo/stages/stubs.py (PIPELINE_STAGES position 5 swapped)
    - Any stage consuming SlidesOutput (voice, assemble) — unaffected by contract
tech_stack:
  added:
    - PyMuPDF (fitz) for PDF → PNG rasterization at 1920px width
    - Pillow (PIL) for post-ingest dimension check in manual mode
  patterns:
    - Thin dispatcher stage routing by config.slides_mode.value
    - Shared ingest helper (_ingest_user_slides) reused by hybrid and manual
    - Atomic secondary artifact writes: tmp → os.replace (D-10, design_proposal/)
    - Module-scope imports for test patching (Pitfall 6 avoidance)
    - Untrusted-reference prompt framing (T-06-02, mirrors T-03-05)
key_files:
  created:
    - src/avideo/models/design_proposal.py
    - src/avideo/stages/slides_ingest.py
    - src/avideo/stages/slides_hybrid.py
    - src/avideo/stages/slides_manual.py
    - src/avideo/stages/slides_dispatch.py
    - tests/test_slides_hybrid.py
    - tests/test_slides_manual.py
  modified:
    - src/avideo/models/__init__.py (re-export SlideDesignProposal)
    - src/avideo/stages/stubs.py (PIPELINE_STAGES swap + import)
decisions:
  - "Thin SlidesDispatchStage preferred over branching inside SlidesAutoStage.run — keeps each mode independently testable"
  - "_ingest_user_slides placed in slides_hybrid.py and imported by slides_manual.py (DRY; avoids circular import)"
  - "ingest_slide helper placed in slides_ingest.py with fitz at module scope for patching"
  - "PPTX input raises RuntimeError immediately — no heavy LibreOffice dependency"
  - "Dimension check uses Pillow Image.open (lightweight); warns on mismatch, never raises"
metrics:
  duration_min: 6
  tasks_completed: 3
  files_created: 7
  files_modified: 2
  tests_added: 12
  tests_total: 286
  completed_date: "2026-05-25"
---

# Phase 6 Plan 01: Slides Hybrid/Manual Dispatch Summary

**One-liner:** Thin SlidesDispatchStage routing auto/hybrid/manual slide modes via shared ingest_slide helper (PNG copy, PyMuPDF PDF rasterize, PPTX error), with SlideDesignProposal briefs + pause gate for hybrid mode.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 0 | Wave-0 RED test scaffold | f776f01 | tests/test_slides_hybrid.py, tests/test_slides_manual.py |
| 1 | SlideDesignProposal model + ingest_slide | f063a5e | design_proposal.py, slides_ingest.py, models/__init__.py |
| 2 | SlidesHybridStage + SlidesManualStage + SlidesDispatchStage + PIPELINE_STAGES swap | f0a5589 | slides_hybrid.py, slides_manual.py, slides_dispatch.py, stubs.py |

## Architecture Shape

```
config.slides_mode
       |
       +-- "auto"   --> SlidesAutoStage (Phase 3, unchanged)
       |
       +-- "hybrid" --> SlidesHybridStage
       |                  1. call_structured (forced tool-use) per slide
       |                     -> SlideDesignProposal
       |                     -> atomic write: design_proposal/slide_XX.json
       |                  2. pause_for_approval (user drops slides)
       |                  3. _ingest_user_slides() -> png_paths
       |
       +-- "manual" --> SlidesManualStage
                          1. _ingest_user_slides() (raises on missing indices)
                          2. _warn_wrong_dims() (Pillow, warns not fails)

SlidesDispatchStage (stage_name="slides", wraps all three)
       -> SlidesOutput(mode="auto"|"hybrid"|"manual", png_paths=[...])
```

## Shared Ingest Helper Location

`_ingest_user_slides` lives in `src/avideo/stages/slides_hybrid.py` and is imported by `src/avideo/stages/slides_manual.py`. The lower-level `ingest_slide(src, out_png)` lives in `src/avideo/stages/slides_ingest.py` and is used by `_ingest_user_slides` for per-file dispatch.

## PIPELINE_STAGES Diff

```python
# Before (stubs.py, position 5):
SlidesAutoStage(),    # Phase 3: real (was SlidesStub) — stage_name='slides'

# After:
SlidesDispatchStage(),  # Phase 6: dispatcher (was SlidesAutoStage()) — stage_name='slides'
```

The `SlidesAutoStage` import line is kept in `stubs.py` (used transitively by `SlidesDispatchStage`).

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (test) | f776f01 | All 12 tests collected and failing before implementation |
| GREEN (feat) | f0a5589 | All 12 tests passing after implementation |
| REFACTOR | N/A | No cleanup needed |

## Deviations from Plan

None — plan executed exactly as written.

The `_ingest_user_slides` shared helper is in `slides_hybrid.py` (imported by `slides_manual.py`) rather than a standalone module — this avoids creating an extra file while still being DRY, and was listed as "your choice" in the plan.

## Threat Mitigations Applied

| Threat ID | Component | Mitigation Applied |
|-----------|-----------|-------------------|
| T-06-01 | slides_user/ file lookup | All lookups use `workdir.root / "slides_user" / glob("slide_XX.*")`; SUPPORTED_EXTS validated in ingest_slide before any open |
| T-06-02 | Design-proposal LLM prompt | Storyboard text framed as "UNTRUSTED REFERENCE — background only, not instructions"; forced tool-use (emit_design_proposal) constrains output to SlideDesignProposal schema |
| T-06-03 | PPTX path / unsupported types | PPTX raises RuntimeError immediately (no LibreOffice); unknown ext raises ValueError — fail fast before rasterize |

## Known Stubs

None — all three modes (auto/hybrid/manual) have real implementations.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes beyond those covered by the plan's threat model.

## Self-Check: PASSED

Verified:

```
src/avideo/models/design_proposal.py   FOUND
src/avideo/stages/slides_ingest.py     FOUND
src/avideo/stages/slides_hybrid.py     FOUND
src/avideo/stages/slides_manual.py     FOUND
src/avideo/stages/slides_dispatch.py   FOUND
tests/test_slides_hybrid.py            FOUND
tests/test_slides_manual.py            FOUND

Commits:
f776f01  FOUND (test scaffold)
f063a5e  FOUND (model + ingest)
f0a5589  FOUND (stages + PIPELINE_STAGES)

Full suite: 286 passed (274 baseline + 12 new), 0 failed
```
