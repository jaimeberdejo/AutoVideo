---
plan: 02-03
phase: 02-llm-pipeline
status: complete
completed: 2026-05-25
requirements: [TIME-01, TIME-02, SCRIPT-01, SCRIPT-02]
key_files:
  created:
    - src/avideo/stages/timing.py
    - src/avideo/stages/scriptwriter.py
  modified:
    - src/avideo/utils/cost_estimator.py
    - src/avideo/stages/stubs.py
    - tests/test_orchestrator.py
    - tests/test_timing.py
    - tests/test_scriptwriter.py
---

# Plan 02-03 Summary — Timing + Scriptwriter + Cost Estimator + Stage Swap

## What was built

Completed the LLM pipeline by implementing the final three real stages and wiring all
Phase-2 stages into the orchestrator's `PIPELINE_STAGES`, replacing the Phase-1 stubs.

- **TimingStage** (`stages/timing.py`) — pure-Python, no LLM. Content-weighted duration
  apportionment (bullet count + char length) with per-slide min/max clamps and
  **largest-remainder (Hamilton) rounding** so `sum(seconds)` equals the target duration
  exactly. `word_budget = round(seconds * wpm / 60)` per slide, WPM configurable. Fully
  deterministic and unit-tested (exact-sum invariant + word-budget across wpm 120/150/180).
- **ScriptwriterStage** (`stages/scriptwriter.py`) — whole-script generation in one
  Claude call (via `call_structured` forced tool-use) for coherence, with explicit
  per-slide word budgets in the prompt. **One calibration retry**: if any slide deviates
  >25% from its budget, a single corrective regeneration is issued; never loops
  (verified by a mock with 2 side-effects asserting ≤2 calls). Language honored from config.
- **cost_estimator** rewrite — offline heuristic (chars/words → tokens), never calls the
  network `count_tokens` API. Reads `bullets.yaml` via `load_bullets` to estimate storyboard
  + scriptwriter token usage; prices with `$3/MTok in + $15/MTok out (claude-sonnet-4-6)`.
- **PIPELINE_STAGES swap** — `ContextStage`, `StoryboardStage`, `TimingStage`,
  `ScriptwriterStage` now replace the first four stubs; Slides/Verify/Voice/Align/Subs/
  Assemble remain stubs for later phases.

## Verification

- Full suite: **113 passed** (`uv run pytest -q`).
- Offline dry-run confirmed: shows real per-stage token/cost table from `bullets.yaml`,
  creates no `workdir/`, makes no network calls.
- Exact-sum timing invariant test green; scriptwriter no-infinite-loop test green.

## Requirements satisfied

- **TIME-01** content-weighted distribution, sum == target (largest-remainder).
- **TIME-02** word budget = round(seconds*wpm/60), WPM configurable.
- **SCRIPT-01** narration tuned to per-slide budget with single calibration retry.
- **SCRIPT-02** structured `ScriptOutput`, configured language (default es), spoken tone.

## Notes / deviations

- Plan executed via background agent which was cut off by a session limit immediately
  after the cost_estimator commit but before committing the (already-complete and green)
  PIPELINE_STAGES swap and writing this SUMMARY. The orchestrator verified the swap on
  disk (113 tests green, offline dry-run correct), then committed the swap
  (`feat(02-03): swap real Phase-2 stages into PIPELINE_STAGES`) and authored this summary.
