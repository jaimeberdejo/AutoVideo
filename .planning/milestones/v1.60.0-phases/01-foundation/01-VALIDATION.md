---
phase: 1
slug: foundation
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-25
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 (system) + pytest-mock |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — Wave 0 installs |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -v --tb=short`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-0 | 01-01 | 1 | CLI-07 | T-01-01 / V5 | Path args use Typer `exists=True` | smoke | `uv run python -c "import avideo"` | ❌ W0 | ⬜ pending |
| 01-01-1 | 01-01 | 1 | ORCH-05, CLI-02, CLI-03 | — | Pydantic v2 models only | unit | `uv run pytest tests/test_models.py -x -q` | ❌ W0 | ⬜ pending |
| 01-01-2 | 01-01 | 1 | ORCH-02, ORCH-03 | T-01-02 / V5 | Atomic tmp→rename; no partial writes | unit | `uv run pytest tests/test_workdir.py -x -q` | ❌ W0 | ⬜ pending |
| 01-02-1 | 01-02 | 2 | CLI-08 | — | Rich output correct | unit | `uv run python -c "from avideo.utils.rich_ui import RichUI; RichUI()"` | ❌ W0 | ⬜ pending |
| 01-02-2 | 01-02 | 2 | CLI-01..08 | T-01-03 / V5 | CLI flags map to RunConfig; Pydantic errors shown via Rich | unit | `uv run pytest tests/test_cli.py -x -q` | ❌ W0 | ⬜ pending |
| 01-03-1 | 01-03 | 3 | ORCH-01..04, CLI-06 | — | L1-L4 gate logic; dry-run table; idempotent stubs | unit | `uv run pytest tests/test_orchestrator.py -x -q -k "not acceptance"` | ❌ W0 | ⬜ pending |
| 01-03-2 | 01-03 | 3 | all CLI+ORCH | — | Full stub pipeline end-to-end | integration | `uv run pytest tests/test_orchestrator.py -x -q` | ❌ W0 | ⬜ pending |
| 01-03-3 | 01-03 | 3 | all | — | Human acceptance checkpoint | manual | n/a | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — shared fixtures (tmp workdir, minimal bullets.yaml, minimal config.yaml)
- [ ] `tests/test_models.py` — stubs for ORCH-05, CLI-02, CLI-03
- [ ] `tests/test_workdir.py` — stubs for ORCH-02, ORCH-03
- [ ] `tests/test_cli.py` — stubs for CLI-01, CLI-04, CLI-07, CLI-08
- [ ] `tests/test_orchestrator.py` — stubs for ORCH-04, CLI-08
- [ ] `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]`
- [ ] `uv add --dev "pytest>=8.0" "pytest-mock>=3.0"` — installed after `uv init`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Pipeline pauses at each stage for user input | ORCH-04 (L1) | Requires interactive terminal session | Run `avideo generate --bullets bullets.yaml --duration 120 --level 1`; confirm pause + prompt appears after each stage |
| `--dry-run` table shows per-stage token/cost estimate | CLI-06 | Visual output verification | Run `avideo generate --bullets bullets.yaml --duration 120 --dry-run`; confirm Rich table displays without executing pipeline |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
