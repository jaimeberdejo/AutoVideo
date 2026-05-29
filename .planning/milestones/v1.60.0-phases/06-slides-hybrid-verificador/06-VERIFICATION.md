---
phase: 06-slides-hybrid-verificador
verified: 2026-05-26T00:00:00Z
status: passed
score: 12/12 must-haves verified
overrides_applied: 0
---

# Phase 6: Slides Hybrid/Manual + Verificador Verification Report

**Phase Goal:** Los modos `hybrid` y `manual` permiten que el usuario aporte sus propias slides; el verificador usa Claude con visión para auditar cobertura, fidelidad y encaje con el guion — con comportamiento diferenciado según el nivel L1-L4
**Verified:** 2026-05-26
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | In hybrid mode the stage writes one design-proposal JSON brief per storyboard slide to workdir/design_proposal/slide_XX.json | VERIFIED | `SlidesHybridStage.run` loops over storyboard.slides, calls `call_structured`, writes atomically to `dp_dir / f"slide_{i:02d}.json"` via tmp→os.replace (slides_hybrid.py lines 128-157) |
| 2 | In hybrid mode the stage pauses (pause_for_approval) after writing briefs so the user can drop slides into slides_user/ | VERIFIED | `pause_for_approval("slides-design", ...)` called exactly once after the loop at slides_hybrid.py line 168 |
| 3 | In hybrid and manual modes user slides ingested from slides_user/: PNG copied, PDF rasterized via PyMuPDF at 1920px width, PPTX raises RuntimeError with export hint | VERIFIED | `ingest_slide` in slides_ingest.py lines 41-96: PNG→shutil.copy2; PDF→fitz.open+zoom+get_pixmap+save; PPTX→RuntimeError("Export ... to PDF or PNG"); unknown ext→ValueError |
| 4 | In manual mode the stage hard-fails with a RuntimeError listing missing indices when ingested slide count != storyboard slide count | VERIFIED | `_ingest_user_slides` in slides_hybrid.py lines 223-230 builds `missing` list and raises RuntimeError listing missing indices. SlidesManualStage delegates to this shared helper |
| 5 | The slides stage dispatches on config.slides_mode and keeps stage_name='slides', checkpoint_name='slides', and SlidesOutput(png_paths=[...], mode=...) intact | VERIFIED | SlidesDispatchStage.stage_name="slides" (line 52); routes by `config.slides_mode.value` to auto/hybrid/manual; all sub-stages return SlidesOutput. PIPELINE_STAGES[4] is SlidesDispatchStage confirmed by runtime check |
| 6 | In auto mode the dispatcher delegates to the unchanged SlidesAutoStage | VERIFIED | SlidesDispatchStage.run: `if mode == "auto": return self._auto.run(workdir, config)` (slides_dispatch.py line 81); SlidesAutoStage imported at module scope for test patching |
| 7 | downscale_png_for_api reduces a 1920x1080 PNG to <=1568px longest side and returns standard base64 PNG with no newlines | VERIFIED | image_utils.py lines 89-105: `MAX_LONG_SIDE=1568`, scale applied via `Image.LANCZOS`, `base64.standard_b64encode(raw).decode("utf-8")` — no newlines by definition of standard_b64encode |
| 8 | call_structured_with_images sends image content blocks BEFORE the text block, using base64 source with media_type 'image/png', plus forced tool-use to validate output against a Pydantic model | VERIFIED | anthropic.py lines 209-236: image blocks appended first, text block appended last; `"media_type": MEDIA_TYPE` where MEDIA_TYPE="image/png"; `tool_choice={"type":"tool","name":tool_name}` |
| 9 | VerifyStage runs one vision call per slide in hybrid/manual mode, emitting a SlideVerdict (status ok/warning/fail + issues + suggestions) per slide | VERIFIED | verify_slides.py lines 169-192: loop over storyboard.slides, one `call_structured_with_images` call per slide, `verdict.slide_index = i` defensive override, verdicts aggregated to VerificationReport |
| 10 | In auto mode VerifyStage does NOT make any vision call and returns a trivial all-ok report sized to the storyboard | VERIFIED | verify_slides.py lines 144-150: `if config.slides_mode.value == "auto": build all-ok report, write report json, return` — no call_structured_with_images call on that path |
| 11 | VerifyStage writes workdir/verification_report.json atomically (tmp then rename) as a human-readable artifact, distinct from verification.json checkpoint written by the orchestrator | VERIFIED | verify_slides.py lines 198-218: `_write_report_json` writes to `verification_report.json.tmp` then `os.replace` to `verification_report.json`; orchestrator separately calls `write_checkpoint("verification", output)` at orchestrator.py line 237 |
| 12 | After verify runs: auto skips gating; L1/L2 render the Rich report and pause to iterate (no mark-done on fail); L3 raises Exit(1) if any slide is fail; L4 continues silently; warning never stops L3/L4 | VERIFIED | orchestrator.py lines 202-235: mode=="auto"→pass; level 1/2→render+pause (on fail: Exit(1) before mark_done, on ok: pause_for_approval); level 3/4→Exit(1) on fail, continue silently on ok; warning never triggers Exit |

**Score:** 12/12 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/avideo/models/design_proposal.py` | SlideDesignProposal pydantic model | VERIFIED | class SlideDesignProposal with slide_index, title, bullets, visual_type, layout_notes, suggested_colors=[] |
| `src/avideo/stages/slides_ingest.py` | ingest_slide helper (PNG/PDF/PPTX→PNG) | VERIFIED | def ingest_slide with SUPPORTED_EXTS frozenset, fitz at module scope, TARGET_WIDTH_PX=1920 |
| `src/avideo/stages/slides_hybrid.py` | SlidesHybridStage + _ingest_user_slides | VERIFIED | class SlidesHybridStage(CheckpointMixin), stage_name="slides", plus shared _ingest_user_slides helper |
| `src/avideo/stages/slides_manual.py` | SlidesManualStage — count validation + ingest | VERIFIED | class SlidesManualStage(CheckpointMixin), stage_name="slides", delegates to _ingest_user_slides, runs _warn_wrong_dims |
| `src/avideo/stages/slides_dispatch.py` | SlidesDispatchStage — routes by config.slides_mode | VERIFIED | class SlidesDispatchStage(CheckpointMixin), stage_name="slides", builds auto/hybrid/manual sub-stages on __init__ |
| `src/avideo/utils/image_utils.py` | downscale_png_for_api + MAX_LONG_SIDE/MAX_BYTES/MEDIA_TYPE constants | VERIFIED | All constants present; downscale_png_for_api implemented with LANCZOS resize and standard_b64encode |
| `src/avideo/integrations/anthropic.py` | call_structured_with_images vision + forced tool-use helper | VERIFIED | Function added alongside call_structured; imports downscale_png_for_api at module scope |
| `src/avideo/stages/verify_slides.py` | VerifyStage real verifier (replaces VerifyStub) | VERIFIED | class VerifyStage(CheckpointMixin), stage_name="verify", checkpoint_name property="verification", _write_report_json atomic |
| `src/avideo/orchestrator.py` | post-verify L1/L2/L3/L4 verdict gate + _render_verification_report | VERIFIED | _render_verification_report renders Rich table; gate block at lines 202-235; typer.Exit re-raised before broad except; TODO(Phase 6) cleared |
| `tests/test_slides_hybrid.py` | Wave-0 RED tests for hybrid + dispatch | VERIFIED | test_hybrid_writes_design_proposals, test_hybrid_calls_call_structured, test_hybrid_pauses_after_proposals, test_hybrid_returns_slides_output, test_dispatch_auto_delegates_to_auto present |
| `tests/test_slides_manual.py` | Wave-0 RED tests for ingest helper + manual | VERIFIED | test_ingest_png_copies, test_ingest_pdf_rasterizes, test_ingest_pptx_raises, test_ingest_unsupported_raises, test_manual_validates_count, test_manual_returns_slides_output present |
| `tests/test_verify_slides.py` | Wave-0 RED tests for VerifyStage | VERIFIED | test_verify_auto_mode_skips, test_verify_calls_per_slide, test_verify_writes_report_json, test_verify_report_json_atomic_no_tmp, test_verify_propagates_fail_status present |
| `tests/test_image_utils.py` | Wave-0 RED tests for downscale helper | VERIFIED | test_downscale_reduces_1920, test_downscale_leaves_small_image, test_downscale_returns_standard_base64, test_downscale_media_type_constant present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| slides_dispatch.py | config.slides_mode | branch on config.slides_mode.value | WIRED | Lines 79-86: `mode = config.slides_mode.value; if mode == "auto": ... "hybrid": ... "manual": ...` |
| slides_hybrid.py | avideo.integrations.anthropic.call_structured | module-scope import + call per slide | WIRED | `from avideo.integrations.anthropic import call_structured` at module scope; called in loop at line 129 |
| stubs.py | SlidesDispatchStage | PIPELINE_STAGES position 4 (0-indexed) | WIRED | `SlidesDispatchStage()` at line 297; runtime confirms PIPELINE_STAGES[4].stage_name=="slides" |
| verify_slides.py | avideo.integrations.anthropic.call_structured_with_images | module-scope import + one call per slide PNG | WIRED | `from avideo.integrations.anthropic import call_structured_with_images` at module scope; called at line 180 |
| anthropic.py | avideo.utils.image_utils.downscale_png_for_api | module-scope import + encode each image path | WIRED | `from avideo.utils.image_utils import MEDIA_TYPE, downscale_png_for_api` at module scope; called at line 211 |
| orchestrator.py | VerificationReport.slides[].status | post-run verdict check after stage_name=="verify" | WIRED | `has_fail = any(v.status == "fail" for v in report.slides)` at line 204; branches on config.level |
| stubs.py | VerifyStage | PIPELINE_STAGES position 5 (0-indexed) | WIRED | `VerifyStage()` at line 298; runtime confirms PIPELINE_STAGES[5] is VerifyStage with stage_name="verify", checkpoint_name="verification" |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| SlidesHybridStage | storyboard (from checkpoint) + briefs (from LLM) | workdir.read_checkpoint("storyboard") + call_structured per slide | Yes — real storyboard read; LLM response validated as SlideDesignProposal | FLOWING |
| SlidesManualStage | png_paths (from _ingest_user_slides) | slides_user/ glob + ingest_slide | Yes — actual file copy/rasterize | FLOWING |
| VerifyStage | verdicts (from call_structured_with_images per slide) | storyboard + slides + script checkpoints + PNG files | Yes — real PNG files base64-encoded, real LLM response validated as SlideVerdict | FLOWING |
| orchestrator | report (VerificationReport returned by VerifyStage) | stage.run output | Yes — live VerificationReport; has_fail computed from actual verdict statuses | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite passes | `uv run python -m pytest -q 2>&1 \| tail -3` | 303 passed, 5 warnings in 3.55s | PASS |
| PIPELINE_STAGES[4] is SlidesDispatchStage with stage_name="slides" | `uv run python -c "from avideo.stages.stubs import PIPELINE_STAGES; print(type(PIPELINE_STAGES[4]).__name__, PIPELINE_STAGES[4].stage_name)"` | SlidesDispatchStage slides | PASS |
| PIPELINE_STAGES[5] is VerifyStage with stage_name="verify", checkpoint_name="verification" | `uv run python -c "from avideo.stages.stubs import PIPELINE_STAGES; s=PIPELINE_STAGES[5]; print(type(s).__name__, s.stage_name, s.checkpoint_name)"` | VerifyStage verify verification | PASS |
| TODO(Phase 6) cleared in orchestrator | `grep "TODO(Phase 6)" src/avideo/orchestrator.py` | no output (empty) | PASS |
| L1 pause count (auto mode) still 10 | test_orch_level1_pauses_each_stage | 2 passed | PASS |
| L2 pause count (auto mode) still 4 | test_orch_level2_pauses_creative_stages | 2 passed | PASS |
| L3/L4 fail verdict → Exit(1) | test_orch_level3_verify_fail_exits, test_orch_level4_verify_fail_exits | 5 passed | PASS |
| L3/L4 all-ok → pipeline completes | test_orch_level3_verify_ok_continues, test_orch_level4_verify_ok_continues | passed | PASS |
| L2 hybrid verify → single post-run pause | test_orch_level2_verify_pauses | passed | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SLIDE-04 | 06-01 | In hybrid mode, generate design-proposal JSON brief per slide to workdir/design_proposal/ | SATISFIED | SlidesHybridStage writes slide_XX.json atomically; tests test_hybrid_writes_design_proposals, test_hybrid_calls_call_structured pass |
| SLIDE-05 | 06-01 | In hybrid/manual modes, ingest user slides from slides_user/ (PNG copy, PDF rasterize via PyMuPDF, PPTX error); manual hard-fails on count mismatch | SATISFIED | ingest_slide in slides_ingest.py; _ingest_user_slides raises RuntimeError on missing indices; _warn_wrong_dims warns on non-1920x1080; all test_manual_* and test_ingest_* pass |
| VERIFY-01 | 06-02 | Per-slide Claude Vision audit via base64 PNG content blocks (image-before-text, media_type image/png) downscaled to <=1568px | SATISFIED | call_structured_with_images builds image blocks before text; downscale_png_for_api enforces 1568px limit; one call per slide in verify_slides.py |
| VERIFY-02 | 06-02 | Verification report JSON written atomically per-slide (ok/warning/fail + issues + suggestions) at workdir/verification_report.json | SATISFIED | _write_report_json uses tmp→os.replace; VerificationReport(slides=[SlideVerdict(...)]) written; tests test_verify_writes_report_json and test_verify_report_json_atomic_no_tmp pass |
| VERIFY-03 | 06-02 | auto: skips verifier; L1/L2: render + pause to iterate; L3/L4: stop on fail, continue if all ok; warning never stops L3/L4 | SATISFIED | orchestrator post-run gate implemented; auto→pass; L1/L2→render+Exit(1) on fail or pause on ok; L3/L4→Exit(1) on fail; warning ignored; all verify-gate orchestrator tests pass |

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| None found | — | — | — |

No TODO/FIXME/placeholder comments, no `return null`/`return []` stubs, no empty implementations, no hardcoded empty props flowing to rendering detected in the phase-6 files.

### Human Verification Required

None. All behaviors are verifiable programmatically through the test suite and static code inspection.

### Gaps Summary

No gaps. All 12 must-have truths are VERIFIED against actual codebase evidence:

- SLIDE-04 (hybrid design proposals + pause): SlidesHybridStage fully implemented with atomic JSON writes and pause_for_approval gate.
- SLIDE-05 (user slide ingest: PNG/PDF/PPTX + manual count validation): slides_ingest.py + shared _ingest_user_slides fully implemented.
- VERIFY-01 (Claude Vision per-slide audit with base64 PNG, images-before-text): call_structured_with_images + downscale_png_for_api fully implemented.
- VERIFY-02 (verification_report.json written atomically with per-slide verdicts): VerifyStage._write_report_json fully implemented.
- VERIFY-03 (auto skip; L1/L2 render+pause/exit; L3/L4 stop on fail): orchestrator post-run gate fully implemented and tested.
- PIPELINE_STAGES: SlidesDispatchStage at position 4, VerifyStage at position 5 — confirmed at runtime.
- Full test suite: 303 passed, 0 failed (17 new tests in this phase).

---

_Verified: 2026-05-26_
_Verifier: Claude (gsd-verifier)_
