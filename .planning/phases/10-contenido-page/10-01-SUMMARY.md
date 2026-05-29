---
phase: 10-contenido-page
plan: "01"
subsystem: tests
tags: [tdd, red, bullets-gen, validation, yaml-round-trip]
dependency_graph:
  requires: []
  provides: [tests/test_bullets_gen.py]
  affects: [src/avideo/stages/bullets_gen.py]
tech_stack:
  added: []
  patterns: [deferred-import-RED, pytest-mock-seam]
key_files:
  created:
    - tests/test_bullets_gen.py
  modified: []
decisions:
  - "Deferred imports inside test bodies (same pattern as test_storyboard.py) so file collects before bullets_gen.py exists"
  - "Mock seam target: avideo.stages.bullets_gen.call_structured (import site, not avideo.integrations.anthropic)"
  - "types.SimpleNamespace used for mock return value (.bullets attribute) — avoids importing bullets_gen's BulletsListOutput model before it exists"
metrics:
  duration: ~4 min
  completed_date: "2026-05-29"
---

# Phase 10 Plan 01: RED Tests for bullets_gen Summary

RED test scaffolding for `generate_bullets()`, `validate_duration()`, and `bullets.yaml` round-trip — 11 tests across 3 classes that collect cleanly and fail with `ModuleNotFoundError` until Plan 02 implements `src/avideo/stages/bullets_gen.py`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write RED test file tests/test_bullets_gen.py | 39e9b22 | tests/test_bullets_gen.py (+230 lines) |

## Test Coverage Provided

### TestGenerateBullets (4 tests)
- `test_generate_bullets_calls_call_structured_once` — verifies call count == 1 and return value
- `test_generate_bullets_returns_list_of_strings` — isinstance check on return type
- `test_generate_bullets_default_n_from_duration` — confirms duration appears in call_structured kwargs
- `test_generate_bullets_no_real_network_call` — mock seam prevents real HTTP calls

### TestBulletsYamlRoundTrip (2 tests)
- `test_bullets_yaml_serialization_round_trip` — BulletsInput → model_dump → yaml.safe_dump → load_bullets round-trip equality
- `test_bullets_yaml_format_matches_engine_input` — confirms UI-output format == CLI --bullets input format

### TestDurationValidation (5 tests)
- `test_validate_duration_minimum_boundary` — 15 passes
- `test_validate_duration_maximum_boundary` — 1800 passes
- `test_validate_duration_below_min_raises` — 14 raises ValueError
- `test_validate_duration_above_max_raises` — 1801 raises ValueError
- `test_validate_duration_typical_value` — 120 passes

## Verification Results

```
pytest tests/test_bullets_gen.py --collect-only -q  → 11 tests collected (0 collection errors)
pytest tests/test_bullets_gen.py -x                 → FAIL ModuleNotFoundError (correct RED state)
pytest --ignore=tests/test_bullets_gen.py -q        → 350 passed, 5 warnings (baseline unbroken)
```

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None — this plan only creates test scaffolding. No source implementation added.

## Threat Flags

None — test file contains only mock return values (synthetic strings); no secrets, no real API keys exercised.

## Self-Check: PASSED

- tests/test_bullets_gen.py: FOUND
- commit 39e9b22: FOUND
- 11 tests collected: CONFIRMED
- 350 baseline tests green: CONFIRMED
- RED state (ModuleNotFoundError): CONFIRMED
