# Phase 6: Slides Hybrid/Manual + Verificador - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning
**Mode:** Autonomous (smart-discuss; decisions at Claude's discretion per user authorization)

<domain>
## Phase Boundary

Implement the `hybrid` and `manual` slide modes (user supplies slides) and the Claude-Vision **verificador** that audits user-supplied slides for coverage, fidelity, and fit with the script — with L1–L4 differentiated behavior.

Requirements in scope: **SLIDE-04** (hybrid design proposal), **SLIDE-05** (ingest user slides, rasterizing pdf/pptx), **VERIFY-01** (vision audit: coverage/fidelity/fit/completeness), **VERIFY-02** (per-slide JSON report ok/warning/fail + issues + suggestions → `workdir/verification_report.json`), **VERIFY-03** (level behavior: auto skips verifier; L1/L2 show report + iterate; L3/L4 continue if all `ok`, stop on any `fail`).

Out of scope: EXPORT-01 (.pptx export, v2), packaging/tests/docs (Phase 7).
</domain>

<decisions>
## Implementation Decisions

### Slides-mode dispatch (SLIDE-04/05)
- The pipeline's `slides` stage must dispatch on `config.slides_mode`:
  - `auto` → existing `SlidesAutoStage` behavior (unchanged; Phase 3).
  - `hybrid` → generate a per-slide design-proposal brief, then require user slides.
  - `manual` → validate user slides are present, then ingest.
- Preferred shape: a thin dispatcher stage (`stage_name="slides"`) that delegates to the auto renderer or a new hybrid/manual ingest path, OR extend `SlidesAutoStage.run` to branch by mode. **Planner picks the cleaner option**; keep `stage_name="slides"`, `checkpoint_name="slides"`, and the `SlidesOutput(png_paths=[...], mode=...)` contract intact so downstream (voice/assemble) is unaffected. `workdir` already provisions `design_proposal/` and `slides_user/`.

### Hybrid design proposal (SLIDE-04)
- For each storyboard slide, write a JSON brief to `workdir/design_proposal/slide_XX.json` (title, bullets, suggested visual_type, layout/notes brief).
- **Mockup is optional → skip image mockups** (keep it offline/simple; JSON brief only). Reuse the existing auto-render path if a quick PNG mockup is trivial, but do not block on it.
- After writing proposals, the stage pauses (checkpoint / level gate) so the user can drop slides into `slides_user/`.

### User slide ingestion (SLIDE-05)
- Read `workdir/slides_user/slide_XX.{png|pdf|pptx}`.
- **PNG**: use directly (validate dimensions ~1920×1080; warn, don't hard-fail, on mismatch).
- **PDF**: rasterize per page → PNG with **PyMuPDF** (`fitz`), 1920-wide target.
- **PPTX**: full offline rasterization is hard (needs LibreOffice). **Decision: best-effort** — accept pptx but if no offline rasterizer is available, emit a clear error telling the user to export to PDF/PNG. Do NOT add a heavy system dependency. Planner may use `python-pptx` only for text/validation, not pixel render.
- Manual mode: hard-validate that the count of ingested slides == storyboard slide count before continuing (clear RuntimeError listing missing indices).

### Verificador — Claude Vision (VERIFY-01/02)
- `integrations/anthropic.py` currently exposes only text `call_structured`. **Add a vision-capable structured call** (e.g. `call_structured_with_images`) that accepts image paths and emits base64 PNG content blocks (`type:"base64"`, `media_type:"image/png"`, ≤20MB, downscale longest side to ~1568px before encoding — per CLAUDE.md anthropic notes). Keep forced tool-use (D-03) for structured JSON output.
- Verifier sends, per slide: the slide PNG + its storyboard `SlideSpec` (title/bullets/visual_type) + the slide's script narration → returns a `SlideVerdict(slide_index, status, issues[], suggestions[])`.
- Aggregate into `VerificationReport` and write `workdir/verification_report.json` atomically (tmp→rename, matching D-10 across the codebase). Reuse existing `models/verification.py` (`SlideVerdict`, `VerificationReport`); extend fields (issues/suggestions) if missing.
- Use the latest Claude vision model id (claude-opus-4-7 or the project's configured model) consistent with how `anthropic.py` resolves models.

### Level behavior (VERIFY-03)
- `auto` mode → verifier does NOT run (the orchestrator already skips, or VerifyStage returns a trivial all-`ok` report and the orchestrator's level/auto logic gates it). Confirm against `orchestrator.py` level handling.
- **L1/L2** → render the report (Rich table) and pause for the iterate loop (user fixes slides → re-verify). Reuse the existing `pause_for_approval` mechanism.
- **L3/L4** → continue automatically if every slide is `ok`; stop (raise/exit) if any slide is `fail`. `warning` does not stop L3/L4.

### Idempotence & checkpoints
- Replace `VerifyStub` in `PIPELINE_STAGES` with the real `VerifyStage` (keep `VerifyStub` class for tests, mirroring the Phase 4/5 swap pattern). `checkpoint_name="verification"`.
- Skip re-running the vision calls if `verification.json` + `verification_report.json` already exist (single idempotence boundary).

### Testing (autonomous mode — no real API/Chromium)
- Mock the anthropic vision call and PyMuPDF rasterization in tests. Provide canned `SlideVerdict` responses. Patch at the `avideo.stages.verify` import boundary (same pattern as the Phase-5 orchestrator test patches: `_fake_*` factories).
- Add a verify-stage end-to-end test + a slides hybrid/manual dispatch test. Patch any orchestrator full-run tests that now hit the real `VerifyStage`.
</decisions>

<code_context>
## Existing Code Insights

- `src/avideo/stages/stubs.py`: `VerifyStub` (placeholder, returns one `ok` verdict), `SlidesStub`; `PIPELINE_STAGES` order is context→storyboard→timing→scriptwriter→**slides**→**verify**→voice→align→subs→assemble. Mirror the Phase-4/5 stub-swap pattern (import real stage, replace in list, keep stub class, patch orchestrator tests).
- `src/avideo/stages/slides_auto.py`: `SlidesAutoStage` (auto render via Playwright) — the dispatch target / extension point.
- `src/avideo/integrations/anthropic.py`: `call_structured(*, system, user, tool_name, tool_description, output_model, max_tokens)` — **text only**, forced tool-use. Needs a vision variant.
- `src/avideo/integrations/playwright.py`: existing PNG render (`SlideRenderer`) for auto mode / optional mockups.
- `src/avideo/models/verification.py`: `SlideVerdict`, `VerificationReport` — extend with issues/suggestions if needed.
- `src/avideo/utils/workdir.py`: provisions `design_proposal/` and `slides_user/` subdirs already; provides checkpoint read/write + `mark_done`/`is_done` + atomic helpers.
- `src/avideo/orchestrator.py`: level/pause logic (`pause_for_approval`), `--level` 1-4, creative-stage gating. Verify behavior must hook into this.
- `src/avideo/cli.py`: `--slides-mode {auto|hybrid|manual}` flag already wired into `RunConfig.slides_mode`.
- Dependencies present per CLAUDE.md: `PyMuPDF` (fitz) for PDF raster, `pdf2image`/Poppler optional, `python-pptx` for pptx text.
</code_context>

<specifics>
## Specific Ideas

- Keep all FFmpeg/subprocess and file writes atomic + idempotent, consistent with Phases 3–5.
- Visuals constraint (CLAUDE.md): no AI/stock images — verifier only audits, it does not generate images.
- The verifier's vision payload must downscale PNGs before base64 to respect the ~1568px / 20MB API limits.
- Prefer extending existing models/stages over new parallel structures.
</specifics>

<deferred>
## Deferred Ideas

- Full offline `.pptx` → PNG rasterization (needs LibreOffice/headless office) — best-effort only; instruct user to export PDF/PNG if unsupported.
- Image mockups in the hybrid design proposal (JSON brief is sufficient for v1).
- EXPORT-01 (.pptx export) — v2, out of scope.
</deferred>
