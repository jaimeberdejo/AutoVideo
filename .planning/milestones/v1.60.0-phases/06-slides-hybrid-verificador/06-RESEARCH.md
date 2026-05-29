# Phase 6: Slides Hybrid/Manual + Verificador - Research

**Researched:** 2026-05-26
**Domain:** Multi-mode slide dispatch (hybrid/manual) + Claude Vision verificador
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Slides-mode dispatch (SLIDE-04/05)**
- Stage keeps `stage_name="slides"`, `checkpoint_name="slides"`, and `SlidesOutput(png_paths=[...], mode=...)` contract.
- Preferred shape: thin dispatcher or extend `SlidesAutoStage.run` to branch by mode — planner picks the cleaner one.
- `workdir.design_proposal/` and `workdir.slides_user/` already provisioned.

**Hybrid design proposal (SLIDE-04)**
- Write per-slide JSON brief to `workdir/design_proposal/slide_XX.json`. JSON only — no image mockups.
- Stage pauses (checkpoint/level gate) after writing briefs so user can drop slides into `slides_user/`.

**User slide ingestion (SLIDE-05)**
- PNG: use directly; validate ~1920×1080, warn (not hard-fail) on mismatch.
- PDF: rasterize with PyMuPDF (`fitz`), 1920-wide target.
- PPTX: best-effort — accept, but raise a clear error if no offline rasterizer is available. `python-pptx` for text/validation only, not pixel render.
- Manual mode: hard-validate slide count == storyboard slide count; clear RuntimeError listing missing indices.

**Verificador — Claude Vision (VERIFY-01/02)**
- Add `call_structured_with_images` to `integrations/anthropic.py` — accepts image paths, emits base64 PNG content blocks (`type:"base64"`, `media_type:"image/png"`, ≤20MB, downscale longest side to ~1568px before encoding).
- Keep forced tool-use (D-03) for structured JSON output.
- Per slide: PNG + `SlideSpec` (title/bullets/visual_type) + narration → `SlideVerdict`.
- Aggregate → `VerificationReport`, write `workdir/verification_report.json` atomically (tmp→rename, D-10).
- Reuse `models/verification.py` (`SlideVerdict`, `VerificationReport`) — fields already include `issues` and `suggestions`.
- Use the project's configured model (`MODEL` constant in `anthropic.py`, currently `claude-sonnet-4-6`).

**Level behavior (VERIFY-03)**
- `auto` mode → verifier does NOT run.
- L1/L2 → render Rich table + `pause_for_approval` iterate loop.
- L3/L4 → continue if all `ok`; stop (raise/exit) if any `fail`; `warning` does not stop L3/L4.

**Idempotence & checkpoints**
- Replace `VerifyStub` in `PIPELINE_STAGES` with real `VerifyStage` (keep stub class for tests).
- `checkpoint_name="verification"`.
- Skip re-running if `verification.json` + `verification_report.json` already exist.

**Testing**
- Mock anthropic vision call and PyMuPDF rasterization. Canned `SlideVerdict` responses.
- Patch at `avideo.stages.verify` import boundary (pattern: `_fake_*` factories).
- Add verify-stage e2e test + hybrid/manual dispatch test.
- Patch orchestrator full-run tests that now hit real `VerifyStage`.

### Claude's Discretion
- Thin dispatcher stage vs. extending `SlidesAutoStage.run` — pick the cleaner shape.

### Deferred Ideas (OUT OF SCOPE)
- Full offline `.pptx` → PNG rasterization (LibreOffice/headless office).
- Image mockups in hybrid design proposal.
- EXPORT-01 (.pptx export) — v2.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SLIDE-04 | Hybrid mode: generate per-slide design-proposal JSON brief in `workdir/design_proposal/` | Confirmed: JSON brief only; pause gate via `pause_for_approval` after writing |
| SLIDE-05 | Hybrid/manual: ingest user slides from `workdir/slides_user/` (PNG direct, PDF via PyMuPDF, PPTX best-effort) | Confirmed: PyMuPDF `fitz` zoom-matrix approach; Pillow for downscale; pptx error path |
| VERIFY-01 | Claude Vision audit per slide: coverage, fidelity, fit with script/timing, completeness | Confirmed: `ImageBlockParam` base64 format verified from official docs + SDK source |
| VERIFY-02 | Per-slide JSON report (ok/warning/fail + issues + suggestions) → `workdir/verification_report.json` | Confirmed: existing `SlideVerdict` model already has issues/suggestions fields |
| VERIFY-03 | Level behavior: auto skips; L1/L2 iterate; L3/L4 continue if all ok, stop on fail | Confirmed: orchestrator already has `FAIL_STAGES`, `CREATIVE_STAGES`, and level=3 TODO comment |
</phase_requirements>

---

## Summary

Phase 6 adds two new code paths branching from the existing `slides` stage and wires in the long-deferred `verify` stage. The hybrid/manual ingest path reads user-supplied slides (PNG/PDF/PPTX) from `workdir/slides_user/`, normalizing everything to a list of PNG paths that downstream stages (voice, assemble) already expect. The verificador calls Claude with image content blocks — base64-encoded PNGs combined with forced-tool-use — to emit a `VerificationReport` per run. The orchestrator already has all the infrastructure needed (level logic, `pause_for_approval`, `FAIL_STAGES` frozenset, and an explicit `TODO(Phase 6)` comment); the only orchestrator change needed is wiring the post-verify L3 verdict check.

**Primary recommendation:** Implement a thin `SlidesDispatchStage` wrapper that instantiates and delegates to `SlidesAutoStage`, `SlidesHybridStage`, or `SlidesManualStage` based on `config.slides_mode`. This is cleaner than branching inside `SlidesAutoStage.run` because it keeps each mode independently testable without Chromium. Add `VerifyStage` as a standalone class in `stages/verify_slides.py`, replacing `VerifyStub` in `PIPELINE_STAGES`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Design proposal generation (SLIDE-04) | Pipeline stage (Python) | Anthropic API | LLM generates JSON briefs; pipeline writes them to `design_proposal/` |
| User slide ingest + normalization (SLIDE-05) | Pipeline stage (Python) | PyMuPDF, Pillow | All format conversion happens in the ingest stage before downstream sees it |
| Image downscaling for API (VERIFY-01) | Integration helper (`integrations/anthropic.py`) | Pillow | Downscaling belongs at the integration boundary, not in the stage |
| Vision API call with forced tool-use (VERIFY-01) | `integrations/anthropic.py` | — | Same integration module owns all Anthropic calls (D-14 pattern) |
| Verdict aggregation + report write (VERIFY-02) | `stages/verify_slides.py` | WorkdirManager | Atomic write via tmp→rename (D-10 pattern); stage owns the report |
| Level-gate logic post-verify (VERIFY-03) | `orchestrator.py` | — | Orchestrator is the only component that pauses or fails the pipeline |
| Slide count validation (SLIDE-05) | `stages/slides_manual.py` | — | Validation is part of ingest, not the orchestrator |

---

## Standard Stack

All packages are already installed in the project. No new dependencies required.

### Core (already in pyproject.toml)
| Library | Installed Version | Purpose | Why Standard |
|---------|------------------|---------|--------------|
| `anthropic` | 0.104.1 | Vision API calls (ImageBlockParam) | Project's LLM client — extend with image content blocks |
| `fitz` (PyMuPDF) | 1.27.2.3 | Rasterize PDF pages → PNG | Already used in Phase 2 context ingest; verified for pixmap API |
| `python-pptx` | 1.0.2 | PPTX text extraction + slide count validation | Already used in Phase 2 context ingest |
| `Pillow` | 12.2.0 | Downscale PNGs to ≤1568px longest-side before base64 encoding | Already a dev dep; only dep for image resize in this phase |
| `pydantic` v2 | (via project) | `SlideVerdict`, `VerificationReport`, `DesignProposal` models | Project's I/O contract layer |
| `rich` | (via project) | Render verification report table at L1/L2 | Already used for all CLI output |

**No new packages to install.** [VERIFIED: uv run python -c "import fitz, pptx, anthropic, PIL; print('ok')" — all importable in project venv]

---

## Architecture Patterns

### System Architecture Diagram

```
config.slides_mode
       │
       ├─ "auto" ──────────→ SlidesAutoStage (unchanged, Phase 3)
       │
       ├─ "hybrid" ─────────→ SlidesHybridStage
       │                         │
       │                         ├─ call_structured → DesignProposal JSON per slide
       │                         │   write → workdir/design_proposal/slide_XX.json
       │                         │
       │                         └─ pause_for_approval (L2+ gate)
       │                              (user drops slides → workdir/slides_user/)
       │                         ↓ [resumes after user approval]
       │                         ingest slides_user/ → png_paths[]
       │
       └─ "manual" ─────────→ SlidesManualStage
                                 │
                                 ├─ validate slide count == storyboard count
                                 └─ ingest slides_user/ → png_paths[]

       (both hybrid + manual share ingest helper)
       ↓
SlidesOutput(png_paths=[...], mode="hybrid"|"manual")
       ↓
VerifyStage (only runs in hybrid/manual; skips in auto mode)
       │
       ├─ read slides/slide_XX.png (from SlidesOutput checkpoint)
       ├─ read storyboard.json (SlideSpec per slide)
       ├─ read script.json (narration per slide)
       │
       └─ for each slide:
            call_structured_with_images(
                images=[slide_png_path],
                system=..., user=...,
                tool_name="emit_verdict",
                output_model=SlideVerdict,
            )
            → SlideVerdict(slide_index, status, issues[], suggestions[])
       │
       └─ VerificationReport(slides=[...])
            → write workdir/verification_report.json (atomic tmp→rename)
            → orchestrator reads report, applies L1/L2/L3/L4 gate
```

### Recommended Project Structure

```
src/avideo/
├── integrations/
│   └── anthropic.py           # add call_structured_with_images()
├── stages/
│   ├── slides_auto.py         # unchanged (Phase 3)
│   ├── slides_hybrid.py       # NEW: design proposal + ingest
│   ├── slides_manual.py       # NEW: validate count + ingest
│   ├── slides_dispatch.py     # NEW: thin dispatcher stage_name="slides"
│   └── verify_slides.py       # NEW: real VerifyStage (replaces VerifyStub)
├── models/
│   ├── verification.py        # SlideVerdict + VerificationReport (already exist; no change needed)
│   └── design_proposal.py     # NEW: DesignProposal pydantic model (per-slide brief)
└── utils/
    └── image_utils.py         # NEW: downscale_for_api(path) → base64 str helper
```

### Pattern 1: Vision content block format (ImageBlockParam)

**What:** An image block in the `content` list of a user message, combining with a text block for the instruction.
**When to use:** Any time a PNG file must be sent to Claude for visual analysis.

```python
# Source: https://platform.claude.com/docs/en/docs/build-with-claude/vision (VERIFIED 2026-05-26)
import base64
import anthropic

client = anthropic.Anthropic()

# Read and encode the image
image_data = base64.standard_b64encode(Path(png_path).read_bytes()).decode("utf-8")

message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",   # must be exact string
                        "data": image_data,           # standard base64, no line breaks
                    },
                },
                {"type": "text", "text": "Analyze this slide."},
            ],
        }
    ],
)
```

### Pattern 2: call_structured_with_images — extend the existing helper

**What:** A new function in `integrations/anthropic.py` that combines an image block list with the forced-tool-use pattern already in `call_structured`.
**When to use:** All vision calls from `VerifyStage`.

```python
# Source: VERIFIED from official docs + existing call_structured pattern in codebase
def call_structured_with_images(
    *,
    system: str,
    user: str,
    image_paths: list[Path],          # PNGs already downscaled to ≤1568px
    tool_name: str,
    tool_description: str,
    output_model: type[T],
    max_tokens: int = 4096,
) -> T:
    """Forced tool-use call with image content blocks (vision)."""
    schema = output_model.model_json_schema()

    # Build content: images first, then text (images-before-text is best practice per docs)
    content: list[dict] = []
    for path in image_paths:
        encoded = base64.standard_b64encode(Path(path).read_bytes()).decode("utf-8")
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": encoded,
            },
        })
    content.append({"type": "text", "text": user})

    resp = _get_client().messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": content}],
        tools=[{"name": tool_name, "description": tool_description, "input_schema": schema}],
        tool_choice={"type": "tool", "name": tool_name},  # D-03: forced tool-use
    )
    for block in resp.content:
        if block.type == "tool_use" and block.name == tool_name:
            return output_model.model_validate(block.input)
    raise RuntimeError(
        f"Model did not return tool_use block for {tool_name!r}. "
        f"stop_reason={getattr(resp, 'stop_reason', 'unknown')!r}."
    )
```

### Pattern 3: PyMuPDF rasterization to target pixel width

**What:** Compute the zoom factor from page points to target pixels, then render via `get_pixmap`.
**When to use:** Any `.pdf` file ingested in hybrid/manual slide mode.

```python
# Source: VERIFIED via fitz.Page.get_pixmap help() + PyMuPDF docs on Context7
import fitz  # PyMuPDF

TARGET_WIDTH_PX = 1920

def rasterize_pdf_page(pdf_path: Path, page_index: int, out_png: Path) -> None:
    doc = fitz.open(str(pdf_path))
    page = doc[page_index]
    zoom = TARGET_WIDTH_PX / page.rect.width
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    pix.save(str(out_png))
    doc.close()
```

### Pattern 4: Downscale PNG for API (Pillow)

**What:** Ensure the longest side is ≤ 1568 px before base64-encoding for the Anthropic API. This is the limit for non-Opus models; Sonnet 4.6 is a non-Opus model.
**When to use:** In `image_utils.downscale_for_api()` before calling `call_structured_with_images`.

**Important finding:** 1920×1080 slides are above the 1568px threshold. They WILL be auto-downscaled by the API, but pre-downscaling client-side reduces payload size significantly (1568×882 PNG ≈ 6KB vs 1920×1080 ≈ much larger). Always pre-downscale.

```python
# Source: VERIFIED via PIL Image.resize + Anthropic docs on image limits
from pathlib import Path
from PIL import Image
import io, base64

MAX_LONG_SIDE = 1568  # px — Anthropic non-Opus model limit (VERIFIED 2026-05-26)
MAX_BYTES = 20 * 1024 * 1024  # 20MB hard limit

def downscale_png_for_api(png_path: Path) -> str:
    """Return base64-encoded PNG, downscaled to ≤ MAX_LONG_SIDE px on longest side."""
    img = Image.open(png_path).convert("RGB")
    w, h = img.size
    if max(w, h) > MAX_LONG_SIDE:
        scale = MAX_LONG_SIDE / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw = buf.getvalue()
    if len(raw) > MAX_BYTES:
        raise ValueError(f"Image {png_path} is {len(raw)/1e6:.1f}MB after downscale; ≤20MB required.")
    return base64.standard_b64encode(raw).decode("utf-8")
```

### Pattern 5: Orchestrator L3 post-verify verdict check

**What:** After `VerifyStage.run()` returns, the orchestrator checks for `fail` verdicts and conditionally stops or pauses.
**When to use:** In `orchestrator.py`'s main loop, in the block where `stage.stage_name == "verify"`.

The `orchestrator.py` already has the TODO comment at line 82: `# level == 3: post-run verdict check not yet implemented (Phase 6 TODO)`. The fix:

```python
# Source: VERIFIED by reading orchestrator.py lines 56-83 + CONTEXT.md decisions
# In orchestrator.run_pipeline(), after:
#   output = stage.run(workdir, config)
# Add for the "verify" stage:

if stage.stage_name == "verify":
    from avideo.models.verification import VerificationReport
    report: VerificationReport = output  # type: ignore[assignment]
    has_fail = any(v.status == "fail" for v in report.slides)
    has_issue = has_fail or any(v.status == "warning" for v in report.slides)

    if config.slides_mode.value == "auto":
        pass  # verifier skipped in auto mode — VerifyStage returns trivial report
    elif config.level in (1, 2):
        # L1/L2: show report + iterate
        _render_verification_report(report)   # Rich table helper
        pause_for_approval("verify")           # existing mechanism
    elif config.level == 3:
        # update should_pause to return False for "verify" at L3 (pre-run gate)
        # but still check post-run:
        if has_fail:
            console.print("[red]Verification failed — stopping (L3).[/red]")
            raise typer.Exit(1)
    # L4: continue silently regardless of verdict
```

**Key insight:** The existing `should_pause` function already returns `False` for `level==3` (line 83). The post-run verdict check is a separate code path in the orchestrator loop, not a `should_pause` concern.

### Pattern 6: SlidesDispatchStage — thin dispatcher

**What:** A stage that delegates to the correct sub-stage based on `config.slides_mode`. Keeps `stage_name="slides"` so the `PIPELINE_STAGES` list and orchestrator are unchanged.

```python
# Source: VERIFIED by reading stubs.py, slides_auto.py, orchestrator.py patterns
class SlidesDispatchStage(CheckpointMixin):
    stage_name: str = "slides"

    def __init__(self, theme_path: Path | None = None) -> None:
        self._auto = SlidesAutoStage(theme_path=theme_path)
        self._hybrid = SlidesHybridStage()
        self._manual = SlidesManualStage()

    def run(self, workdir: WorkdirManager, config: RunConfig) -> SlidesOutput:
        mode = config.slides_mode.value
        if mode == "auto":
            return self._auto.run(workdir, config)
        elif mode == "hybrid":
            return self._hybrid.run(workdir, config)
        elif mode == "manual":
            return self._manual.run(workdir, config)
        else:
            raise ValueError(f"Unknown slides_mode: {mode!r}")
```

In `stubs.py`, replace `SlidesAutoStage()` with `SlidesDispatchStage()` in `PIPELINE_STAGES`.

### Pattern 7: VerifyStage — skip logic for auto mode

**What:** The verify stage must silently return a trivial all-ok report when `config.slides_mode == "auto"`, mirroring what `VerifyStub` currently does. This avoids a conditional in the orchestrator.

```python
class VerifyStage(CheckpointMixin):
    stage_name: str = "verify"

    @property
    def checkpoint_name(self) -> str:
        return "verification"

    def run(self, workdir: WorkdirManager, config: RunConfig) -> VerificationReport:
        if config.slides_mode.value == "auto":
            # Auto mode: verifier does not run (VERIFY-03)
            storyboard = workdir.read_checkpoint("storyboard", StoryboardOutput)
            return VerificationReport(
                slides=[SlideVerdict(slide_index=i, status="ok")
                        for i in range(len(storyboard.slides))]
            )
        # hybrid / manual: run the real vision verifier
        ...
```

### Anti-Patterns to Avoid

- **Branching inside `SlidesAutoStage.run`:** Adding hybrid/manual logic inside the existing auto stage couples unrelated concerns and forces mocking Playwright in hybrid/manual tests. Use the dispatcher pattern.
- **Hard-failing on 1920x1080 PNG input:** The spec says warn, not fail. A 1920×1080 PNG is valid input in auto mode; the 1568px cap is a vision API constraint, not a user slide constraint.
- **Building the image content list in the stage rather than the integration layer:** Downscaling + encoding belongs in `integrations/anthropic.py` (via the helper in `utils/image_utils.py`). This keeps stages testable without Pillow/base64 logic.
- **Calling `workdir.mark_done` inside the stage:** The orchestrator does this (Pitfall-4). Stages must never call `mark_done`.
- **Adding vision-augmented report to workdir via `write_checkpoint`:** The `verification_report.json` is a SECOND artifact (human-readable rich report) distinct from the `verification.json` checkpoint. Write `verification.json` via `workdir.write_checkpoint("verification", report)` as normal; write `verification_report.json` manually inside the stage using atomic tmp→rename (D-10 pattern).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF page rasterization | Custom subprocess+ghostscript | `fitz.Page.get_pixmap(matrix=...)` | PyMuPDF is already installed; it handles all PDF versions, embedded fonts, and transparency |
| Image downscaling | Custom numpy pixel ops | `PIL.Image.resize(..., Image.LANCZOS)` | Pillow is already installed; LANCZOS is the standard high-quality downscale filter |
| Base64 encoding | Custom chunking | `base64.standard_b64encode(bytes).decode()` | Standard library; the API needs standard (not urlsafe) base64 without newlines |
| JSON schema from Pydantic model | Custom schema extraction | `output_model.model_json_schema()` | Already the pattern in `call_structured`; produces draft-2020-12 that Anthropic API accepts |
| Vision API image blocks | Custom dict construction per-call | `call_structured_with_images()` helper | Single tested entry point; consistent `images-before-text` ordering |

**Key insight:** Every component needed (PDF raster, image resize, base64, forced tool-use, atomic file write) is already available in the project's installed dependencies and existing patterns.

---

## Common Pitfalls

### Pitfall 1: PPTX Rasterization Misunderstanding
**What goes wrong:** Trying to render `.pptx` to PNG using `python-pptx` — the library has no rendering capability. Attempting subprocess LibreOffice will fail silently on macOS dev environments.
**Why it happens:** `python-pptx` is named "presentation" but is a text/DOM manipulation library only.
**How to avoid:** For `.pptx` input, use `python-pptx` only to validate slide count and extract text. Emit a clear `RuntimeError` instructing the user to export to PDF or PNG manually. Check the file extension and raise early.
**Warning signs:** Any import of `pptx.util.Inches` or `pptx.oxml` being used to "render" a slide.

### Pitfall 2: Image Size vs. API Token Cost
**What goes wrong:** Sending 1920×1080 PNGs without pre-downscaling. The API auto-downscales them internally but the base64 payload is much larger (≈ 6–8MB per PNG vs. ≈ 6KB after downscale to 1568px).
**Why it happens:** Developer assumes the API handles it transparently.
**How to avoid:** Always downscale to ≤ 1568px longest-side in `downscale_png_for_api()` before encoding. Verified: a 1920×1080 PNG downscaled to 1568×882 is 6KB as base64. [VERIFIED: local Python test 2026-05-26]
**Warning signs:** Base64 payload strings over 1MB per image in the request body.

### Pitfall 3: `media_type` must be exact string
**What goes wrong:** Using `"image/PNG"` (uppercase) or `"png"` instead of `"image/png"` in the image block source.
**Why it happens:** The API field is case-sensitive.
**How to avoid:** Always hardcode `"image/png"` (lowercase). Store this in a module-level constant in `image_utils.py`. [VERIFIED: official docs Python example uses `"image/png"` lowercase]

### Pitfall 4: Orchestrator L3 gate is a post-run check, not a pre-run pause
**What goes wrong:** Implementing the L3 verify gate as `should_pause("verify", level=3) → True`, which would pause BEFORE the verifier runs.
**Why it happens:** Misreading the `should_pause` function's intent — it governs pre-stage approval gates.
**How to avoid:** The L3 verdict check must be added AFTER `output = stage.run(workdir, config)` in the orchestrator's stage loop, reading the returned `VerificationReport`. The `should_pause` function must keep returning `False` for level=3 (current behavior at line 83 of `orchestrator.py`).

### Pitfall 5: Idempotence check must cover BOTH checkpoint files
**What goes wrong:** Checking only `is_done("verify")` — which depends on `verification.json` — but not checking if `verification_report.json` also exists. If the run was interrupted after `write_checkpoint` but before writing the report, the done-marker is missing but `verification.json` exists.
**Why it happens:** The standard `is_done()` / `mark_done()` idiom only covers the primary checkpoint.
**How to avoid:** In `VerifyStage.run`, check `workdir.is_done("verify")` first (idempotence via orchestrator's normal loop). The orchestrator skips the stage entirely if done. The `verification_report.json` is a secondary artifact written inside the stage before returning — it is idempotent by overwrite.

### Pitfall 6: Test mocking — patch at the stage import boundary
**What goes wrong:** Patching `avideo.integrations.anthropic.call_structured_with_images` instead of `avideo.stages.verify_slides.call_structured_with_images`.
**Why it happens:** Forgetting the Python import rebinding rule (patch where the name is used, not where it's defined).
**How to avoid:** Import `call_structured_with_images` at module scope in `verify_slides.py` (same pattern as `slides_auto.py` line 41). Tests patch `avideo.stages.verify_slides.call_structured_with_images`.

### Pitfall 7: VerifyStub left in PIPELINE_STAGES after swap
**What goes wrong:** Importing `VerifyStage` in `stubs.py` but forgetting to swap it in `PIPELINE_STAGES`, leaving `VerifyStub()` in position 5.
**Why it happens:** The stub swap pattern requires two changes: (1) import the real class, (2) replace in the list.
**How to avoid:** `test_pipeline_order` and `test_stub_run_returns_pydantic_basemodel` in `test_orchestrator.py` will fail if the swap is incorrect — these tests already run the full pipeline and check the stage at position 5.

### Pitfall 8: Full-pipeline orchestrator test needs a mock for VerifyStage
**What goes wrong:** `test_orch_full_run_all_stages_done` and related tests in `test_orchestrator.py` will now hit the real `VerifyStage`, which requires reading slide PNG files that don't exist in the test's tmp_path.
**Why it happens:** The tests previously relied on `VerifyStub` which always returned a trivial report.
**How to avoid:** After swapping `VerifyStage` into `PIPELINE_STAGES`, patch `avideo.stages.verify_slides.call_structured_with_images` in all existing orchestrator full-run tests. Add a `_fake_verify_factory()` helper to `test_orchestrator.py` following the `_fake_run_ffmpeg_factory()` pattern.

---

## Code Examples

### DesignProposal model (new)
```python
# Source: VERIFIED by reading models/verification.py + CONTEXT.md decisions
from pydantic import BaseModel

class SlideDesignProposal(BaseModel):
    """Per-slide design brief written to workdir/design_proposal/slide_XX.json."""
    slide_index: int
    title: str
    bullets: list[str]
    visual_type: str           # from VisualType enum value
    layout_notes: str          # free-text design guidance for the user
    suggested_colors: list[str] = []   # optional hex color hints
```

### Slide ingest helper (shared by hybrid + manual)
```python
# Source: VERIFIED via fitz docs (Context7) + local test 2026-05-26
from pathlib import Path

SUPPORTED_EXTS = {".png", ".pdf", ".pptx"}

def ingest_slide(src: Path, out_png: Path) -> None:
    """Normalize a user-supplied slide to a PNG file at out_png."""
    ext = src.suffix.lower()
    if ext == ".png":
        import shutil
        shutil.copy2(src, out_png)
    elif ext == ".pdf":
        import fitz
        doc = fitz.open(str(src))
        page = doc[0]
        zoom = 1920 / page.rect.width
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        pix.save(str(out_png))
        doc.close()
    elif ext == ".pptx":
        raise RuntimeError(
            f"PPTX rasterization is not supported offline. "
            f"Please export '{src.name}' to PDF or PNG and place in slides_user/."
        )
    else:
        raise ValueError(f"Unsupported file type: {ext!r}. Supported: {SUPPORTED_EXTS}")
```

### Verify report Rich table rendering
```python
# Source: ASSUMED (Rich Table API pattern consistent with existing rich_ui.py usage)
from rich.table import Table
from avideo.utils.rich_ui import console
from avideo.models.verification import VerificationReport

STATUS_STYLE = {"ok": "green", "warning": "yellow", "fail": "red"}

def render_verification_report(report: VerificationReport) -> None:
    table = Table(title="Verification Report", show_lines=True)
    table.add_column("Slide", style="dim")
    table.add_column("Status")
    table.add_column("Issues")
    table.add_column("Suggestions")
    for v in report.slides:
        style = STATUS_STYLE.get(v.status, "white")
        table.add_row(
            str(v.slide_index),
            f"[{style}]{v.status}[/{style}]",
            "\n".join(v.issues),
            "\n".join(v.suggestions),
        )
    console.print(table)
```

---

## Runtime State Inventory

No rename/refactor involved. SKIPPED per instructions.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `character_start_times_ms` (ElevenLabs SDK 1.x) | `character_start_times_seconds` (SDK 2.x) | SDK v2 | Already handled in Phase 4 |
| `images` up to 5MB limit (old Claude models) | 20MB limit + auto-downscale to native resolution | Current API | Phase 6 benefit: 20MB limit is permissive enough for 1920×1080 PNGs |
| Vision limited to specific beta headers | Vision in standard `messages.create` | Claude Sonnet 3+ | No beta header needed for `claude-sonnet-4-6` |

**Deprecated / not applicable:**
- `pdf2image` (requires system Poppler): not needed — PyMuPDF handles PDF rasterization fully without Poppler and is already installed.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `claude-sonnet-4-6` supports vision (image content blocks) without a beta header | Pattern 1 | If wrong, the API call will fail with a 400 error; fix is adding a beta header or using a different model |
| A2 | `Rich.Table` is the appropriate rendering primitive for the verification report at L1/L2 | Code Examples (Rich table) | Low risk — Rich Table is the standard in the existing codebase; style is cosmetic |
| A3 | `suggested_colors` field in `SlideDesignProposal` is useful to include | Code Examples (DesignProposal) | Low risk — field is optional; removing it has no downstream impact |

All critical technical claims (API image format, PyMuPDF zoom, Pillow downscale, orchestrator level logic) were verified via tool calls against installed packages and official documentation.

---

## Open Questions (RESOLVED)

1. **Should the hybrid pause be a `pause_for_approval` call or a checkpoint-based re-entry?**
   - What we know: `pause_for_approval` blocks on user input (Confirm.ask). The hybrid flow needs the user to place files in `slides_user/` THEN resume.
   - What's unclear: Should the pipeline terminate cleanly with a message ("Run again to continue after placing your slides") or block indefinitely?
   - RESOLVED: Use `pause_for_approval("slides-design")` with a descriptive message instructing the user to place slides and press Enter. This matches existing L1/L2 behavior and keeps the process alive.

2. **Does the verifier run slide-by-slide (one API call per slide) or in a single batch call?**
   - What we know: The CONTEXT.md says "per slide: the slide PNG + its SlideSpec + narration → SlideVerdict". This implies N separate calls.
   - What's unclear: Whether the planner should design for batch (multiple images per call) to reduce API latency.
   - RESOLVED: One call per slide — simpler error handling, easier idempotence (skip slides that already have verdicts), and more predictable token usage. The decision in CONTEXT.md supports this.

3. **`verification_report.json` vs. `verification.json` — are these two separate files?**
   - What we know: The CONTEXT.md says "write `workdir/verification_report.json`". `workdir.write_checkpoint("verification", report)` writes `workdir/verification.json`. Both are VerificationReport.
   - What's unclear: Are they the same content written to two different paths, or different models?
   - RESOLVED: Write the VerificationReport to both paths: `write_checkpoint("verification", report)` for the orchestrator's idempotence logic, and also write `verification_report.json` atomically (tmp→rename) for human-readable access. Same content, two paths.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `fitz` (PyMuPDF) | PDF rasterization (SLIDE-05) | ✓ | 1.27.2.3 | — |
| `PIL` (Pillow) | PNG downscale before base64 | ✓ | 12.2.0 | — |
| `python-pptx` | PPTX slide count validation | ✓ | 1.0.2 | — |
| `anthropic` | Vision API calls | ✓ | 0.104.1 | — |
| `pydantic` v2 | DesignProposal + models | ✓ | (via project) | — |
| ANTHROPIC_API_KEY | Vision API calls | runtime env | — | Error on first call (lazy client) |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | `pyproject.toml` (detected: 274 tests passing) |
| Quick run command | `uv run pytest tests/test_slides_hybrid.py tests/test_slides_manual.py tests/test_verify_slides.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SLIDE-04 | Hybrid stage writes one JSON brief per slide to `design_proposal/` | unit | `pytest tests/test_slides_hybrid.py::test_hybrid_writes_design_proposals -x` | ❌ Wave 0 |
| SLIDE-04 | Hybrid stage calls LLM for design proposal (mocked) | unit | `pytest tests/test_slides_hybrid.py::test_hybrid_calls_call_structured -x` | ❌ Wave 0 |
| SLIDE-04 | Hybrid stage pauses for approval (level gate) | unit | `pytest tests/test_slides_hybrid.py::test_hybrid_pauses_after_proposals -x` | ❌ Wave 0 |
| SLIDE-05 | PNG input is copied directly without rasterization | unit | `pytest tests/test_slides_manual.py::test_ingest_png_copies -x` | ❌ Wave 0 |
| SLIDE-05 | PDF input is rasterized via PyMuPDF to 1920px width | unit | `pytest tests/test_slides_manual.py::test_ingest_pdf_rasterizes -x` | ❌ Wave 0 |
| SLIDE-05 | PPTX input raises clear RuntimeError | unit | `pytest tests/test_slides_manual.py::test_ingest_pptx_raises -x` | ❌ Wave 0 |
| SLIDE-05 | Manual mode hard-fails when slide count mismatches storyboard | unit | `pytest tests/test_slides_manual.py::test_manual_validates_count -x` | ❌ Wave 0 |
| SLIDE-05 | Warn (not fail) on non-1920×1080 PNG dimensions | unit | `pytest tests/test_slides_manual.py::test_manual_warns_wrong_dims -x` | ❌ Wave 0 |
| VERIFY-01 | `call_structured_with_images` builds correct image content block | unit | `pytest tests/test_anthropic_integration.py::TestCallStructuredWithImages -x` | ❌ Wave 0 |
| VERIFY-01 | `downscale_png_for_api` produces ≤1568px longest-side output | unit | `pytest tests/test_image_utils.py::test_downscale_reduces_1920 -x` | ❌ Wave 0 |
| VERIFY-01 | VerifyStage skips vision calls in auto mode | unit | `pytest tests/test_verify_slides.py::test_verify_auto_mode_skips -x` | ❌ Wave 0 |
| VERIFY-01 | VerifyStage calls vision API once per slide in hybrid mode | unit | `pytest tests/test_verify_slides.py::test_verify_calls_per_slide -x` | ❌ Wave 0 |
| VERIFY-02 | VerificationReport written atomically to `verification.json` | unit | `pytest tests/test_verify_slides.py::test_verify_writes_checkpoint -x` | ❌ Wave 0 |
| VERIFY-02 | `verification_report.json` written atomically | unit | `pytest tests/test_verify_slides.py::test_verify_writes_report_json -x` | ❌ Wave 0 |
| VERIFY-03 | L3 with all-ok report continues without pause | integration | `pytest tests/test_orchestrator.py::test_orch_level3_verify_ok_continues -x` | ❌ Wave 0 |
| VERIFY-03 | L3 with fail verdict raises Exit(1) | integration | `pytest tests/test_orchestrator.py::test_orch_level3_verify_fail_exits -x` | ❌ Wave 0 |
| VERIFY-03 | L1/L2 shows report and calls pause_for_approval | integration | `pytest tests/test_orchestrator.py::test_orch_level2_verify_pauses -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_slides_hybrid.py tests/test_slides_manual.py tests/test_verify_slides.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q` (full suite — currently 274 tests; must stay green)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_slides_hybrid.py` — covers SLIDE-04 (hybrid dispatch + LLM brief + pause)
- [ ] `tests/test_slides_manual.py` — covers SLIDE-05 (ingest helper: PNG/PDF/PPTX + count validation)
- [ ] `tests/test_verify_slides.py` — covers VERIFY-01/02 (vision call mocked + report write)
- [ ] `tests/test_image_utils.py` — covers downscale helper (≤1568px, base64, 20MB guard)
- [ ] Extend `tests/test_anthropic_integration.py` — add `TestCallStructuredWithImages` class
- [ ] Extend `tests/test_orchestrator.py` — add L3/L4 verify-verdict tests + patch `VerifyStage` in existing full-run tests

**Existing infrastructure that covers Phase 6 indirectly:**
- `test_orchestrator.py::test_pipeline_order` — will verify `VerifyStage` is in position 5 after swap
- `test_orchestrator.py::test_orch_full_run_all_stages_done` — will fail until `VerifyStage` is mocked in that test

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | Pydantic v2 `model_validate` on all LLM outputs; slide index range checked |
| V6 Cryptography | no | — |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via slide content (storyboard text injected into vision prompt) | Tampering | Frame storyboard/script as "UNTRUSTED REFERENCE" in system prompt (existing T-03-05 pattern) |
| Path traversal in `slides_user/` file lookup | Tampering | Resolve all paths via `workdir.root / "slides_user" / filename`; validate suffix is in SUPPORTED_EXTS |
| Oversized user PNG causing OOM in Pillow | DoS | Check file size before `Image.open`; apply MAX_BYTES guard in `downscale_png_for_api` |

---

## Sources

### Primary (HIGH confidence)
- `anthropic==0.104.1` — verified installed via `uv run python -c "import anthropic; print(anthropic.__version__)"`
- `fitz (PyMuPDF)==1.27.2.3` — verified installed; `Page.get_pixmap(matrix=..., alpha=False)` API confirmed via `help()`
- `PIL (Pillow)==12.2.0` — verified installed; `Image.resize(LANCZOS)` + `io.BytesIO` pattern confirmed via local test
- Official Anthropic Vision docs (https://platform.claude.com/docs/en/docs/build-with-claude/vision) — ImageBlockParam format, 1568px limit for non-Opus, 20MB limit, images-before-text ordering
- Context7 `/anthropics/anthropic-sdk-python` — ImageBlockParam type, ToolError with image blocks pattern
- Context7 `/pymupdf/pymupdf` — `get_pixmap(matrix=...)`, `get_pixmap(dpi=...)`, Matrix zoom constructor
- Codebase: `src/avideo/integrations/anthropic.py` — existing `call_structured` pattern (forced tool-use, D-03/D-14)
- Codebase: `src/avideo/orchestrator.py` — `should_pause`, `CREATIVE_STAGES`, `FAIL_STAGES`, TODO(Phase 6) comment
- Codebase: `src/avideo/stages/stubs.py` — `VerifyStub`, `PIPELINE_STAGES` stub-swap pattern
- Codebase: `src/avideo/models/verification.py` — `SlideVerdict` (issues/suggestions already present), `VerificationReport`
- Codebase: `src/avideo/utils/workdir.py` — atomic write pattern (tmp→rename), `design_proposal/` and `slides_user/` confirmed provisioned

### Secondary (MEDIUM confidence)
- PyMuPDF Context7 docs — zoom calculation (TARGET_WIDTH / page.rect.width) confirmed via local test showing 1920×2718 output for A4 at zoom=3.23

### Tertiary (LOW confidence — flagged in Assumptions Log)
- claude-sonnet-4-6 vision capability without beta header (A1) — inferred from official docs stating vision is in standard `messages.create` for current models; not tested live in this session

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified installed in project venv
- Architecture patterns: HIGH — all patterns verified against existing codebase and official API docs
- Pitfalls: HIGH — derived from reading actual code (stubs.py, orchestrator.py, slides_auto.py) and known API constraints
- Vision API format: HIGH — verified from official docs + SDK source (ImageBlockParam structure)
- Image size limits: HIGH — verified from official Anthropic vision docs (1568px for non-Opus, 20MB hard limit)

**Research date:** 2026-05-26
**Valid until:** 2026-06-25 (Anthropic API limits and model IDs can change; re-verify MODEL constant before execution)
