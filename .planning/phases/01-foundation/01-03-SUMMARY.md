---
phase: 01-foundation
plan: "03"
subsystem: orchestrator
tags: [python, orchestrator, stages, protocol, tdd, rich, pydantic]
dependency_graph:
  requires:
    - avideo package importable on Python 3.11 (01-01)
    - RunConfig BaseSettings with CLI/YAML/default merge (01-01)
    - Pydantic I/O contracts for all pipeline stages (01-01)
    - WorkdirManager atomic checkpoint writes and done markers (01-01)
    - avideo.cli Typer app with generate subcommand and all nine flags (01-02)
    - avideo.utils.rich_ui Console + ValidationError table + RichHandler logging (01-02)
  provides:
    - StageProtocol @runtime_checkable Protocol (stage_name, checkpoint_name, run, is_done)
    - CheckpointMixin providing is_done and checkpoint_name property defaults
    - 10 Phase-1 stub stages in canonical order (context→assemble)
    - PIPELINE_STAGES canonical ordered list
    - AssembleStub creates workdir/output.mp4 marker
    - run_pipeline sequential loop with skip-done, approval gates, dry-run branch
    - should_pause L1-L4 level semantics (exact)
    - pause_for_approval Confirm.ask gate in rich_ui
    - make_progress transient Progress bar in rich_ui
    - estimate_all Rich Table cost estimate in cost_estimator
  affects: [all downstream phases 2-5, phase acceptance command]
tech_stack:
  added: []
  patterns:
    - typing.Protocol @runtime_checkable for stage interface enforcement
    - CheckpointMixin providing is_done/checkpoint_name so stubs stay pure
    - checkpoint_name property override for stages where name != checkpoint file
    - Pitfall-4 ordering: write_checkpoint → mark_done, never reversed
    - KeyboardInterrupt trapped at orchestrator loop, not in stages
    - Transient Rich Progress wraps stage loop (CLI-08)
    - TDD RED/GREEN per task; shared test_orchestrator.py with task-grouped sections
key_files:
  created:
    - src/avideo/stages/__init__.py
    - src/avideo/stages/base.py
    - src/avideo/stages/stubs.py
    - src/avideo/orchestrator.py
    - src/avideo/utils/cost_estimator.py
    - tests/test_orchestrator.py
  modified:
    - src/avideo/utils/rich_ui.py (appended pause_for_approval + make_progress)
decisions:
  - "checkpoint_name as a @property on CheckpointMixin (not a class attr) allows per-instance override without metaclass complexity"
  - "PIPELINE_STAGES module-level list — single source of truth for pipeline order (orchestrator + tests both import it)"
  - "pause_for_approval is a module-level function in rich_ui (not a class method) so monkeypatch works without special fixtures"
  - "estimate_all imported at module level in orchestrator (not lazy) because cost_estimator has no side effects on import"
  - "AlignStub/SubsStub reuse TimingOutput/ScriptOutput shapes for Phase-1 placeholder checkpoints; Phase 4 will replace with dedicated models"
metrics:
  duration_seconds: 0
  completed_date: "2026-05-25"
  tasks_completed: 2
  files_created: 6
---

# Phase 01 Plan 03: Orchestrator and Stage Stubs Summary

**One-liner:** Sequential orchestrator with 10 stub stages, L1-L4 approval gates, atomic checkpoint ordering (Pitfall-4), idempotent resume, and dry-run cost table.

## What Was Built

### Task 1: StageProtocol + CheckpointMixin + all Phase-1 stub stages (TDD)

**RED commit (1d118d7):** Stage/protocol/stub tests + all Task 2 orchestrator tests in `tests/test_orchestrator.py`.

**GREEN commit (8e77944):**

- `stages/base.py`: `@runtime_checkable class StageProtocol(Protocol)` with `stage_name: str`, `checkpoint_name: str`, `run(workdir, config) -> BaseModel`, `is_done(workdir) -> bool`. `class CheckpointMixin` with `stage_name = ""`, `checkpoint_name` property defaulting to `stage_name`, and `is_done()` delegation to `workdir.is_done(self.stage_name)`.
- `stages/stubs.py`: 10 stub classes (ContextStub, StoryboardStub, TimingStub, ScriptwriterStub, SlidesStub, VerifyStub, VoiceStub, AlignStub, SubsStub, AssembleStub). Each subclasses `CheckpointMixin`. Four stubs override `checkpoint_name` (timing→timings, scriptwriter→script, verify→verification, assemble→assembly). `AssembleStub.run` touches `workdir/output.mp4` then returns `AssemblyOutput`. `PIPELINE_STAGES` list in canonical order.
- `stages/__init__.py`: re-exports `StageProtocol`, `CheckpointMixin`, `PIPELINE_STAGES`.

### Task 2: Orchestrator loop + rich_ui additions + cost_estimator (TDD)

**GREEN commit (b87d205):**

- `orchestrator.py`: `CREATIVE_STAGES = frozenset({"storyboard", "scriptwriter", "slides", "verify"})` (real stage_names). `FAIL_STAGES = frozenset({"verify"})`. `should_pause(stage_name, level, has_fail) -> bool` implementing L1-L4 exactly. `run_pipeline(config)`: workdir instantiation → dry_run branch → stage loop with skip-done, approval gate, `output = stage.run()` → `write_checkpoint` → `mark_done` → console.print (Pitfall-4 order), KeyboardInterrupt → Exit(130), Progress wrapper.
- `rich_ui.py` additions: `pause_for_approval(stage_name, reason)` using `Confirm.ask`; raises `typer.Abort` on decline. `make_progress()` returns transient `Progress(SpinnerColumn, TextColumn)`.
- `cost_estimator.py`: `STAGE_COSTS` dict (static Phase-1 placeholders, one entry per stage). `estimate_all(config)` builds Rich Table ("Stage", "Est. tokens", "Est. cost (USD)"), adds one row per stage from STAGE_COSTS plus TOTAL summary row, prints to console. Returns None; runs no stage.

## Commits

| Task | Commit | Message |
|------|--------|---------|
| Task 1 RED | 1d118d7 | test(01-03): add failing tests for stage protocol, stubs, and orchestrator loop (TDD RED) |
| Task 1 GREEN | 8e77944 | feat(01-03): implement StageProtocol, CheckpointMixin, and all Phase-1 stub stages (TDD GREEN) |
| Task 2 GREEN | b87d205 | feat(01-03): implement orchestrator loop, approval gates, cost_estimator, and rich_ui additions (TDD GREEN) |

## Test Results

```
43 passed in 0.19s
```

- `tests/test_orchestrator.py`: 17 tests — pipeline order, Protocol isinstance, stub outputs (storyboard, context, assemble), checkpoint_name overrides, full run, idempotency, resume, L1/L2/L4 gate counts, dry-run no-mp4, Pitfall-4 (exception leaves is_done=False)
- `tests/test_cli.py`: 11 tests (unchanged from 01-02)
- `tests/test_models.py`: 8 tests (unchanged from 01-01)
- `tests/test_workdir.py`: 7 tests (unchanged from 01-01)

## TDD Gate Compliance

- RED gate: commit `1d118d7` (`test(01-03): ...`) — present
- GREEN gate: commit `8e77944` + `b87d205` — present, after RED commit
- REFACTOR gate: not needed — code is clean

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

## Known Stubs

All 10 PIPELINE_STAGES are intentional Phase-1 stubs; real implementations arrive in Phases 2-5. Each stub's docstring notes the phase that will replace it:
- context: Phase 3 (real .pptx/.pdf/.md extraction)
- storyboard: Phase 2 (Anthropic API)
- timing: Phase 2 (proportional duration allocation)
- scriptwriter: Phase 2 (Anthropic API, WPM-calibrated)
- slides: Phase 3 (Jinja2 + Playwright)
- verify: Phase 6 (Claude vision)
- voice: Phase 4 (ElevenLabs API)
- align: Phase 4 (WhisperX)
- subs: Phase 4 (subtitle generator)
- assemble: Phase 5 (FFmpeg)

## Threat Flags

No new threat surface beyond the plan's threat model. T-01-08, T-01-09, and T-01-10 all mitigated:
- T-01-08: Pitfall-4 ordering enforced (`write_checkpoint` always before `mark_done`); test_orch_mark_done_not_called_on_exception verifies this.
- T-01-09: L1/L2/L4 gate counts verified by dedicated tests (10, 4, 0 respectively); CREATIVE_STAGES frozen with real stage_names.
- T-01-10: KeyboardInterrupt trapped → clean message + Exit(130); mark_done cannot be called on interrupt.

## Self-Check: PASSED

- [x] `src/avideo/stages/base.py` exists with `StageProtocol`, `Protocol`, `runtime_checkable`, `CheckpointMixin`, `checkpoint_name`
- [x] `src/avideo/stages/stubs.py` exists with `PIPELINE_STAGES`, `output.mp4`
- [x] `src/avideo/orchestrator.py` exists with `run_pipeline`, `should_pause`, `CREATIVE_STAGES`, `scriptwriter`, `estimate_all`, `config.dry_run`
- [x] `src/avideo/utils/rich_ui.py` has both `pause_for_approval` and `show_validation_error`
- [x] `src/avideo/utils/cost_estimator.py` has `estimate_all` and `Table`
- [x] `tests/test_orchestrator.py` has `output.mp4`
- [x] `write_checkpoint` appears before `mark_done` in orchestrator.py
- [x] Pipeline order: `['context','storyboard','timing','scriptwriter','slides','verify','voice','align','subs','assemble']`
- [x] All stages satisfy `isinstance(s, StageProtocol)`
- [x] Commit 1d118d7 exists (RED)
- [x] Commit 8e77944 exists (Task 1 GREEN)
- [x] Commit b87d205 exists (Task 2 GREEN)
- [x] `uv run pytest tests/ -v --tb=short` → 43 passed
