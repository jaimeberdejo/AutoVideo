---
phase: "02-llm-pipeline"
plan: "02"
subsystem: llm-storyboard
tags: [python, anthropic, tool-use, structured-output, pydantic, enum, tdd]

dependency_graph:
  requires:
    - "02-01: BulletsInput + load_bullets() + ContextStage (context checkpoint)"
    - "01-03: WorkdirManager, CheckpointMixin, StageProtocol, RunConfig"
  provides:
    - "call_structured() helper (consumed by 02-03 scriptwriter)"
    - "VisualType enum — closed enum for predictable render phase values"
    - "StoryboardStage — real LLM storyboard from bullets + duration via Anthropic"
  affects:
    - "02-03: scriptwriter reuses call_structured() and imports StoryboardOutput"
    - "03: slides renderer gets VisualType values not free strings"
    - "stubs.py: StoryboardStub updated to use VisualType.bullets default"

tech_stack:
  added: []
  patterns:
    - "Lazy _get_client() singleton: import avideo.integrations.anthropic never needs ANTHROPIC_API_KEY"
    - "Forced tool-use: tool_choice={type:tool,name:...} + input_schema=model.model_json_schema()"
    - "block.input dict → model_validate() (never json.loads a text block)"
    - "VisualType(str,Enum) with 7 values; SlideSpec.visual_type: VisualType = VisualType.bullets"
    - "Mock point: from avideo.integrations.anthropic import call_structured at module scope"
    - "Context as untrusted reference: T-02-06 prompt injection mitigation"
    - "CTX-02 guard: FileNotFoundError on missing context checkpoint → proceed without"

key_files:
  created:
    - "src/avideo/integrations/__init__.py — package marker"
    - "src/avideo/integrations/anthropic.py — lazy client + call_structured() + MODEL constant"
    - "src/avideo/stages/storyboard.py — StoryboardStage real LLM implementation"
    - "tests/test_anthropic_integration.py — 5 tests: call_structured helper (TEST-01)"
    - "tests/test_storyboard.py — 9 tests: STORY-01/02 coverage with mocked call_structured"
  modified:
    - "src/avideo/models/storyboard.py — added VisualType enum; SlideSpec.visual_type migrated"
    - "src/avideo/models/__init__.py — export VisualType (additive)"
    - "src/avideo/stages/stubs.py — StoryboardStub: visual_type='text' → default VisualType.bullets"
    - "tests/test_models.py — fix storyboard roundtrip test: visual_type='text' → VisualType.bullets"
    - "tests/test_workdir.py — fix checkpoint roundtrip test: visual_type='text' → VisualType.bullets"

decisions:
  - "MODEL='claude-sonnet-4-6' in integrations/anthropic.py — single change point (D-12)"
  - "max_retries=3 on Anthropic() client; SDK handles exp backoff + Retry-After (D-13)"
  - "call_structured default max_tokens=8192 — ample for storyboard; scale for scriptwriter (A3)"
  - "VisualType default is VisualType.bullets (not 'text'); stale Phase-1 storyboard.json must be deleted"
  - "Context injected with untrusted-reference framing in system prompt (T-02-06)"
  - "StoryboardStage NOT wired into PIPELINE_STAGES — stub swap deferred to 02-03 (single-owner rule)"

metrics:
  duration_seconds: 641
  completed_date: "2026-05-25"
  tasks_completed: 3
  files_changed: 10
---

# Phase 02 Plan 02: Anthropic Integration + StoryboardStage Summary

**One-liner:** Centralized Anthropic client with forced-tool-use helper + real StoryboardStage generating structured slides from bullets via Claude claude-sonnet-4-6.

## What Was Built

This plan introduced the `integrations/anthropic.py` module (lazy client + generic `call_structured()` helper) and replaced the Phase-1 `StoryboardStub` logic with a real `StoryboardStage` that reads `bullets.yaml`, injects optional context, and produces a schema-validated `StoryboardOutput` via forced tool-use. The `visual_type` field was migrated from a free `str` to the closed `VisualType` enum.

### integrations/anthropic.py

`src/avideo/integrations/anthropic.py` implements:

- `MODEL = "claude-sonnet-4-6"` — single constant for storyboard and scriptwriter (D-12).
- `_client: Anthropic | None = None` + `_get_client()` lazy singleton — importing the module never requires `ANTHROPIC_API_KEY` (T-02-07, Pitfall 4).
- `call_structured(*, system, user, tool_name, tool_description, output_model, max_tokens=8192) -> T` — generic forced-tool-use → Pydantic helper (D-14):
  - Derives `input_schema` from `output_model.model_json_schema()` (Pydantic v2 draft-2020-12).
  - Forces `tool_choice={"type":"tool","name":tool_name}` (D-03).
  - Extracts `block.input` dict from the `tool_use` content block → `model_validate()`.
  - Raises `RuntimeError` with actionable message if no matching block (T-02-09).
  - `max_retries=3` on the SDK handles 429/5xx exponential backoff — no custom loop (D-13).

### VisualType enum (D-02)

`src/avideo/models/storyboard.py` adds:

- `VisualType(str, Enum)` with 7 values: `title`, `bullets`, `chart`, `diagram`, `quote`, `comparison`, `image_icon`.
- `SlideSpec.visual_type: VisualType = VisualType.bullets` — default changed from `"text"` (not in enum).
- Migration note documented: delete stale `workdir/storyboard.json` (+ `.storyboard.done`) before first real run.

### StoryboardStage

`src/avideo/stages/storyboard.py` implements:

- `StoryboardStage(CheckpointMixin)` with `stage_name = "storyboard"` (identical to stub — checkpoint contract preserved).
- `run()` calls `load_bullets(config.bullets)` → `BulletsInput` (closes the Phase-1 Pitfall 1 gap).
- Reads context checkpoint via `workdir.read_checkpoint("context", ContextOutput)` — `FileNotFoundError` caught and treated as no-context (CTX-02 robustness).
- System prompt includes `{language}` and visual layout guidelines for all 7 enum values.
- User prompt embeds title, duration, bullets list, and (when present) context text framed as untrusted reference material (T-02-06 prompt injection mitigation).
- `call_structured` imported at module scope → mockable at `avideo.stages.storyboard.call_structured` in tests (TEST-01).
- Stage does NOT write checkpoints (orchestrator owns that — Pitfall 4).
- Not yet wired into `PIPELINE_STAGES` (deferred to 02-03 along with the other stub swaps).

## TDD Gate Compliance

- RED commit: `089ccd2` — `test(02-02): add failing tests for integration + storyboard (RED)`
- GREEN commits:
  - `06c3b52` — `feat(02-02): integrations/anthropic.py + VisualType enum (GREEN)`
  - `25db4d6` — `feat(02-02): StoryboardStage real Anthropic storyboard (GREEN)`
- No REFACTOR pass needed — implementation was clean on first pass.

## Test Results

All 71 tests pass (zero regressions):
- `tests/test_anthropic_integration.py`: 5 tests — call_structured extraction, RuntimeError on missing block, wrong tool name, forced tool_choice in API call, import without API key
- `tests/test_storyboard.py`: 9 tests — mock return, bullet text in prompt, language honored, VisualType enum, stage_name, checkpoint_name, without context, with context, duration in prompt
- Existing 57 tests: all green

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] VisualType enum migration broke 3 pre-existing tests using visual_type="text"**

- **Found during:** Task 1 (GREEN phase) — running full suite after adding VisualType enum
- **Issue:** `test_models.py::test_storyboard_output_roundtrip`, `test_workdir.py::test_write_and_read_checkpoint_roundtrip`, `test_orchestrator.py` tests all used `visual_type="text"` which is NOT in the new enum. Also `StoryboardStub` in `stubs.py` hardcoded `visual_type="text"`.
- **Fix:** Updated all 3 test files to use `VisualType.bullets`; updated `StoryboardStub` to omit `visual_type` (letting the new default `VisualType.bullets` apply).
- **Files modified:** `tests/test_models.py`, `tests/test_workdir.py`, `src/avideo/stages/stubs.py`
- **Commit:** `06c3b52` (included in Task 1 commit)

This was the exact migration risk documented as Pitfall 2 in the research — applied as a Rule 1 auto-fix since the tests were directly caused by the Task 1 enum change.

## Known Stubs

`StoryboardStage` is NOT yet wired into `PIPELINE_STAGES` (still uses `StoryboardStub` there). This is intentional: the stub swap for all four Phase-2 stages happens once in 02-03 to keep `stubs.py` single-owner.

## Threat Flags

None — no new network endpoints, file access patterns, or schema changes at trust boundaries beyond those in the plan's threat model. All threat register mitigations were applied:

- T-02-06: Context framed as untrusted reference material in system prompt.
- T-02-07: Lazy `_get_client()` — API key never required at import; never embedded in models.
- T-02-08: Context already truncated to `CONTEXT_TOKEN_CAP` by ContextStage; `max_tokens=8192` bounds output.
- T-02-09: `RuntimeError` raised on missing `tool_use` block — clear error, not silent failure.

## Self-Check: PASSED

Files created/exist:
- src/avideo/integrations/__init__.py: FOUND
- src/avideo/integrations/anthropic.py: FOUND
- src/avideo/stages/storyboard.py: FOUND
- tests/test_anthropic_integration.py: FOUND
- tests/test_storyboard.py: FOUND

Commits exist:
- 089ccd2: FOUND (RED: test scaffolding)
- 06c3b52: FOUND (GREEN: integrations + VisualType enum)
- 25db4d6: FOUND (GREEN: StoryboardStage)
