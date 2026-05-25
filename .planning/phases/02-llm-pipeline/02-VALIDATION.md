---
phase: 2
slug: llm-pipeline
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-25
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-mock 3.15.1 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=`tests`, pythonpath=`src`) |
| **Quick run command** | `uv run pytest tests/test_timing.py tests/test_storyboard.py -x -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~5 seconds (Anthropic calls mocked; no network) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_<stage>.py -x -q` (the stage just touched)
- **After every plan wave:** Run `uv run pytest -q` (full suite must be green)
- **Before `/gsd-verify-work`:** Full suite green + offline smoke `avideo generate --bullets bullets.yaml --duration 120 --dry-run`
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Req | Behavior | Test Type | Automated Command | File Exists | Status |
|---------|-----|----------|-----------|-------------------|-------------|--------|
| CTX-01 | CTX-01 | Extract text from .pdf/.pptx/.md fixtures | unit (fixtures) | `uv run pytest tests/test_context.py -x -q` | ❌ W0 | ⬜ pending |
| CTX-02 | CTX-02 | No `--context` → `ContextOutput(used=False)` | unit | `uv run pytest tests/test_context.py -k no_context -x -q` | ❌ W0 | ⬜ pending |
| STORY-01 | STORY-01 | Storyboard stage calls helper → `StoryboardOutput` | unit (mock `call_structured`) | `uv run pytest tests/test_storyboard.py -x -q` | ❌ W0 | ⬜ pending |
| STORY-02 | STORY-02 | Output validates; orchestrator persists `storyboard.json` | unit + integration | `uv run pytest tests/test_storyboard.py -x -q` | ❌ W0 | ⬜ pending |
| TIME-01 | TIME-01 | Content-weighted split; sum(seconds)==duration, clamps active | unit (pure) | `uv run pytest tests/test_timing.py -k exact_sum -x -q` | ❌ W0 | ⬜ pending |
| TIME-02 | TIME-02 | word_budget==round(seconds*wpm/60) for wpm∈{120,150,180} | unit (pure) | `uv run pytest tests/test_timing.py -k word_budget -x -q` | ❌ W0 | ⬜ pending |
| SCRIPT-01 | SCRIPT-01 | Calibration retry fires once on >25% drift, never loops | unit (mock, 2 side_effects) | `uv run pytest tests/test_scriptwriter.py -x -q` | ❌ W0 | ⬜ pending |
| SCRIPT-02 | SCRIPT-02 | Output language honored; structured `ScriptOutput` | unit (mock) | `uv run pytest tests/test_scriptwriter.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Mocked vs fixture:**
- **Mocked (no network):** `call_structured` patched at the stage's import site (satisfies TEST-01).
- **Fixtures (real files):** tiny `.pdf`/`.pptx`/`.md` + an encrypted PDF fixture.
- **Pure (no mock/fixture):** timing apportionment — exact-sum invariant, clamps, word budgets (deterministic per D-08).

---

## Wave 0 Requirements

- [ ] `tests/test_context.py` — CTX-01, CTX-02 (incl. encrypted-PDF + empty-deck edges)
- [ ] `tests/test_storyboard.py` — STORY-01, STORY-02 (mock `call_structured`)
- [ ] `tests/test_timing.py` — TIME-01 (exact-sum + clamps), TIME-02 (word budget)
- [ ] `tests/test_scriptwriter.py` — SCRIPT-01 (calibration retry, no infinite loop), SCRIPT-02
- [ ] `tests/conftest.py` additions — `sample_pdf`, `sample_pptx`, `sample_md`, `encrypted_pdf` fixtures
- [ ] (optional) `tests/test_anthropic_integration.py` — `call_structured` extracts `tool_use` block from a faked `Message`

*(Framework already installed in Phase 1 — no install step needed.)*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real storyboard quality with a live key | STORY-01 | Requires ANTHROPIC_API_KEY + subjective quality judgment | `ANTHROPIC_API_KEY=... uv run avideo generate --bullets bullets.yaml --duration 120 --level 4`; inspect `workdir/storyboard.json` + `script.json` |
| `--context deck.pdf` extraction on a real deck | CTX-01 | Real document variety | Run with `--context <real.pdf>`; confirm `context.json` `used=true` and `text` non-empty |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
