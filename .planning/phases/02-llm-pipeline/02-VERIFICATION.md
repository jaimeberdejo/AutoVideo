---
phase: 02-llm-pipeline
verified: 2026-05-25T00:00:00Z
status: passed
score: 8/8 must-haves verified
overrides_applied: 0
verification_method: "Inline goal-backward verification by the autonomous orchestrator (account agent-session limit blocked spawning gsd-verifier; reset 19:30 Europe/Madrid). Evidence: 113-test suite green, grep-confirmed implementations per requirement, offline dry-run smoke."
---

# Phase 2: LLM Pipeline — Verification

**Goal:** A partir de bullets y duración el sistema genera un storyboard estructurado, calcula la distribución de tiempo por slide con presupuesto de palabras, y produce el guion completo calibrado — todo persistido como JSON validado con Pydantic.

**Status:** passed — 8/8 requirement-backed must-haves verified.

## Requirement coverage (evidence)

| Req | Truth | Evidence | Status |
|-----|-------|----------|--------|
| CTX-01 | Extracts text from .pdf/.pptx/.md | `stages/context.py` has `extract_pdf/extract_pptx/extract_md` + suffix dispatch; `tests/test_context.py` green | ✅ |
| CTX-02 | Optional context; no `--context` → pipeline unaffected | `ContextOutput(used=False)` path; `test_no_context` green | ✅ |
| STORY-01 | Storyboard via Anthropic (forced tool-use) | `stages/storyboard.py` calls `call_structured`; `claude-sonnet-4-6`; `tests/test_storyboard.py` (mocked) green | ✅ |
| STORY-02 | Pydantic-validated JSON, persisted as storyboard.json | `StoryboardOutput` via `model_validate`; orchestrator persists checkpoint; green | ✅ |
| TIME-01 | Content-weighted split, sum(seconds)==target | `stages/timing.py` `apportion_seconds` largest-remainder + clamps; exact-sum test green | ✅ |
| TIME-02 | word_budget=round(seconds*wpm/60), WPM configurable | timing.py word-budget logic; tested wpm∈{120,150,180} | ✅ |
| SCRIPT-01 | Narration tuned to budget, 1 calibration retry (no loop) | `stages/scriptwriter.py` ≤2 calls on >25% drift; `tests/test_scriptwriter.py` green | ✅ |
| SCRIPT-02 | Structured ScriptOutput, configured language (default es) | scriptwriter honors `config.language`; structured output; green | ✅ |

## Quality gates

- **Tests:** 113 passed (`uv run pytest -q`). Targeted: timing 19/19, scriptwriter 9/9, storyboard 9/9.
- **CLAUDE.md:** Pydantic v2, `import fitz`, `uv`, `claude-sonnet-4-6`, SDK `max_retries=3` (no hand-rolled retry).
- **Offline dry-run:** Rich cost table from `bullets.yaml`, no network, no `workdir/` created.
- **bullets.yaml gap closed:** `utils/bullets.py::load_bullets` now parses real bullets (was never parsed before Phase 2).
- **Pipeline wired:** `PIPELINE_STAGES` swaps real Context/Storyboard/Timing/Scriptwriter stages for the Phase-1 stubs; Slides/Verify/Voice/Align/Subs/Assemble remain stubs for later phases.

## Human verification (deferred, non-blocking)

A live run with a real `ANTHROPIC_API_KEY` to judge subjective storyboard/script quality is recommended before shipping, but all automated and structural checks pass. Mockable Anthropic calls satisfy TEST-01 readiness for Phase 7.
