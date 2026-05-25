---
phase: 6
slug: slides-hybrid-verificador
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-26
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | pyproject.toml ([tool.pytest]) |
| **Quick run command** | `uv run pytest tests/test_slides_hybrid.py tests/test_verify.py -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run the quick command for the files touched.
- **End of each plan:** Run the full suite (`uv run pytest -q`) — must stay green (currently 274 passing baseline).
- **No real external calls in tests:** Mock the Anthropic vision call (`call_structured_with_images`) and PyMuPDF rasterization; never hit the network or launch Chromium.

---

## Validation Requirements by Requirement ID

| Req | Observable signal | Test strategy |
|-----|-------------------|---------------|
| **SLIDE-04** | `workdir/design_proposal/slide_XX.json` written per storyboard slide (title, bullets, visual_type, brief); pipeline pauses (hybrid) | Unit: hybrid stage writes N JSON briefs for N slides; mocked Claude proposal; assert files + content keys. |
| **SLIDE-05** | User slides ingested from `slides_user/slide_XX.{png\|pdf\|pptx}`; PDF rasterized via PyMuPDF; manual mode hard-fails on missing slides | Unit: PNG passthrough; PDF→PNG raster (mock fitz); manual mode raises RuntimeError listing missing indices. |
| **VERIFY-01** | Per-slide vision audit covering coverage/fidelity/fit; `call_structured_with_images` sends image-before-text base64 PNG blocks | Unit: mock vision call returns canned SlideVerdict; assert image content block shape (type image, base64, media_type image/png) and downscaling applied. |
| **VERIFY-02** | `workdir/verification_report.json` written atomically (tmp→rename) with per-slide status ok/warning/fail + issues + suggestions | Unit: report JSON exists, valid VerificationReport shape, statuses present. |
| **VERIFY-03** | auto → verifier skipped; L1/L2 → show report + pause/iterate; L3/L4 → continue if all ok, stop (exit) on any fail; warning never stops L3/L4 | Unit: level gating logic — auto skips; L4 with a `fail` verdict raises/exits; L4 all-ok continues; orchestrator full-run test patched for real VerifyStage. |

---

## Wave 0 (test scaffold)

- Create `tests/test_slides_hybrid.py` and `tests/test_verify.py` with fixtures: fake storyboard/script checkpoints, placeholder slide PNGs, canned vision `SlideVerdict` responses, mock `fitz` rasterizer.
- These tests define the contracts above (RED) before implementation (GREEN).

---

## Regression Guard

- Full suite must remain green (≥274 tests). Orchestrator full-run tests that now hit the real `SlidesDispatchStage`/`VerifyStage` must be patched (mock vision + raster), mirroring the Phase-5 `_fake_run_ffmpeg_factory` pattern in `tests/test_orchestrator.py`.
