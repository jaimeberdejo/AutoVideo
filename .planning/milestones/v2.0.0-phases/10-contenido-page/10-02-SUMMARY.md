---
phase: 10-contenido-page
plan: "02"
subsystem: stages
tags: [tdd, green, bullets-gen, call-structured, pydantic, validation]
dependency_graph:
  requires: [tests/test_bullets_gen.py]
  provides: [src/avideo/stages/bullets_gen.py]
  affects: [src/avideo/ui/pages/phase_1_contenido.py]
tech_stack:
  added: []
  patterns: [call_structured-pydantic-output, module-level-mock-seam, tdd-green]
key_files:
  created:
    - src/avideo/stages/bullets_gen.py
  modified: []
decisions:
  - "Module-level import of call_structured mirrors storyboard.py exactly — enables pytest-mock patch at avideo.stages.bullets_gen.call_structured"
  - "BulletsListOutput uses Field(..., min_length=1) Pydantic v2 constraint to enforce non-empty list from Claude"
  - "Default n = max(2, min(20, duration_seconds // 30)) — 1 bullet per 30s, clamped 2-20"
  - "validate_duration() raises ValueError with both bounds in message for clear UX feedback"
metrics:
  duration: ~1 min
  completed_date: "2026-05-29"
---

# Phase 10 Plan 02: Implement bullets_gen.py Summary

GREEN phase: `src/avideo/stages/bullets_gen.py` with `generate_bullets()`, `validate_duration()`, and `BulletsListOutput` — turns all 11 RED tests from Plan 01 GREEN using the call_structured mock-seam pattern from storyboard.py.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement src/avideo/stages/bullets_gen.py | 25ec988 | src/avideo/stages/bullets_gen.py (+122 lines) |

## Verification Results

```
pytest tests/test_bullets_gen.py -v  → 11 passed, 5 warnings in 0.38s
pytest -q                            → 361 passed, 5 warnings in 3.53s
```

Done criteria confirmed:
- grep -c "def generate_bullets(" src/avideo/stages/bullets_gen.py → 1
- grep -c "def validate_duration(" src/avideo/stages/bullets_gen.py → 1
- grep -c "class BulletsListOutput" src/avideo/stages/bullets_gen.py → 1
- grep -c "from avideo.integrations.anthropic import call_structured" src/avideo/stages/bullets_gen.py → 1

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None — all three exports are fully implemented.

## Threat Flags

None — no new network endpoints, auth paths, or file access patterns introduced beyond what the plan's threat model covers (T-10-02-01 through T-10-02-03 all addressed).

## Self-Check: PASSED

- src/avideo/stages/bullets_gen.py: FOUND
- commit 25ec988: FOUND
- 11 tests GREEN: CONFIRMED
- 361 full suite passed (350 baseline + 11 new): CONFIRMED
