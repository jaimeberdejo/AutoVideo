---
phase: 13-extras-ensamblaje-polish
verified: 2026-05-29T18:30:00Z
status: human_needed
score: 5/5
overrides_applied: 0
human_verification:
  - test: "Run `uv run avideo studio` and confirm Streamlit opens at http://localhost:8501 showing the 6-phase wizard"
    expected: "Browser opens with the wizard; stepper shows 6 phases; no crash on startup"
    why_human: "Cannot programmatically launch and inspect a Streamlit UI without a running server; app.py raises StreamlitAPIException on module-scope st.set_page_config() outside a server"
  - test: "Navigate to Fase 5 in the wizard and confirm widgets are visible: burn_subs toggle, music file uploader (mp3/wav), volume slider (0.0-1.0), fade-out slider, crossfade slider (0-3s), 'Aprobar extras y continuar' button"
    expected: "All 5 widgets render without exceptions; approving with no extras selected advances to Fase 6"
    why_human: "Streamlit widget rendering requires a live server; smoke tests only verify the module imports without calling render()"
  - test: "Navigate to Fase 6 and confirm 'Montar vídeo' button is present; if prior phases are complete, click it and confirm FFmpeg progress appears without UI freeze while the assembly runs in background"
    expected: "Button visible; @st.fragment polling shows status updates every 2s without blocking interaction with other widgets; on completion st.video and st.download_button appear"
    why_human: "Non-blocking UI behavior (ASM-01) requires a running Streamlit server and actual FFmpeg execution to observe; cannot verify fragment polling or UI responsiveness programmatically"
  - test: "Optionally run `docker build -t avideo-test .` and confirm the image builds without errors"
    expected: "Build completes successfully; EXPOSE 8501 present in image metadata"
    why_human: "Docker build requires Docker daemon; not available in this environment"
---

# Phase 13: Extras + Ensamblaje + Polish — Verification Report

**Phase Goal:** El usuario puede configurar extras opcionales (subtítulos, música de fondo, transiciones), montar el vídeo final y descargarlo desde la UI; la app está empaquetada y testeada
**Verified:** 2026-05-29T18:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Fase 5 permits burn_subs toggle, music upload + volume slider + preview, crossfade config; approving persists to session_state["run_config"] | VERIFIED | `phase_5_extras.py` lines 48-162: st.toggle burn_subs, st.file_uploader mp3/wav, st.audio preview, st.slider volume (0-1, default 0.12), crossfade slider (0-3s); extras_to_run_config result merged into session_state["run_config"]; extras_approved gate at line 151 |
| 2 | Fase 6 mounts video via bridge integrating all extras; FFmpeg progress shown in real time without freezing UI | VERIFIED (code) / HUMAN NEEDED (behavior) | `phase_6_ensamble.py` lines 57-105: AssembleStage launched via `run_stage()`; `@st.fragment(run_every="2s")` def `_poll_assemble()` polls `stage_status("assemble", workdir)` every 2s; `st.status()` shown while RUNNING/IDLE; returns False until done — UI-freeze absence requires human confirmation |
| 3 | On assembly completion, st.video player + st.download_button for output.mp4 + QA report (duration deviation + LUFS) visible | VERIFIED | `phase_6_ensamble.py` lines 110-152: `st.video(str(output_mp4))`, `st.download_button(label="Descargar output.mp4", mime="video/mp4")`, `read_qa_report(workdir)` → `st.metric` for actual_seconds, duration_deviation, normalized_lufs/measured_lufs |
| 4 | `avideo studio` is an installable entry point; Dockerfile exposes port 8501 and documents headless launch | VERIFIED | `pyproject.toml` line 51: `avideo-studio = "avideo.cli:app"`; `cli.py` line 150: `def studio(...)` subcommand; `Dockerfile` line 16: `EXPOSE 8501`; Dockerfile lines 41-45: headless launch comment with `--server.headless=true --server.address=0.0.0.0` |
| 5 | Bridge tests, page smoke tests, and all 397 tests pass green alongside the prior 303-test suite | VERIFIED | `uv run python -m pytest -q` → **397 passed, 0 failed, 5 warnings**; test_page_smoke.py: 7/7 PASSED (all 6 page modules + count check); test_extras_pipeline_ops.py: 9/9 PASSED |

**Score:** 5/5 truths verified (SC-4 and partial SC-2 have human-needed components)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/avideo/ui/pipeline_ops.py` | Three new helpers: write_uploaded_music, extras_to_run_config, read_qa_report | VERIFIED | Lines 253-338: all three functions present with full implementations, docstrings, path-traversal guard, broad exception catch |
| `src/avideo/ui/pages/phase_5_extras.py` | Real Fase 5 wizard page — EXT-01 | VERIFIED | 162-line implementation replacing 49-line placeholder; burn_subs toggle, music uploader, volume slider, crossfade slider, extras_to_run_config wired, session_state persisted |
| `src/avideo/ui/pages/phase_6_ensamble.py` | Real Fase 6 wizard page — ASM-01 + ASM-02 | VERIFIED | 168-line implementation; AssembleStage/SubtitlesStage via bridge, @st.fragment polling, st.video + st.download_button + QA metrics |
| `Dockerfile` | EXPOSE 8501 + headless launch documentation | VERIFIED | Line 16: `EXPOSE 8501`; lines 41-45: headless launch comment block |
| `tests/test_page_smoke.py` | Import smoke tests for all 6 pages + count sanity | VERIFIED | 53-line file; _PAGE_MODULES covers phases 1-6; 7 tests all PASSED |
| `tests/test_extras_pipeline_ops.py` | 9 RED→GREEN tests for write_uploaded_music, extras_to_run_config, read_qa_report | VERIFIED | 222-line file; 3 classes, 9 tests; all GREEN (uv run pytest confirms) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `phase_5_extras.py` | `avideo.ui.pipeline_ops.extras_to_run_config` | lazy import inside render() | WIRED | Line 128: `from avideo.ui.pipeline_ops import extras_to_run_config` called with all 5 kwargs |
| `phase_5_extras.py` | `session_state["run_config"]` | dict merge before approve gate | WIRED | Lines 139-142: rc_dict updated with extras_kwargs, assigned to `st.session_state["run_config"]` |
| `phase_5_extras.py` | `pipeline_ops.write_uploaded_music` | lazy import on file upload | WIRED | Lines 71-73: deferred import + call on `uploaded_music is not None` branch |
| `phase_6_ensamble.py` | `avideo.stages.assemble.AssembleStage` | run_stage via PipelineBridge | WIRED | Lines 78-83: lazy import of AssembleStage + `_run_stage(AssembleStage(), workdir, config)` |
| `phase_6_ensamble.py` | `workdir.root / "output.mp4"` | st.video + st.download_button | WIRED | Lines 110-122: existence check + st.video + st.download_button |
| `phase_6_ensamble.py` | `avideo.ui.pipeline_ops.read_qa_report` | lazy import, renders QAReport as st.metric | WIRED | Lines 131-152: deferred import + 3 st.metric widgets for duration/deviation/LUFS |
| `app.py` | all 6 phase modules | `_PHASE_MODULES` dict, dispatches render() | WIRED | Lines 128-152: all 6 pages imported and keyed 1-6; `_PHASE_MODULES[current_phase].render(workdir)` |
| `Dockerfile` | `avideo studio` CLI entry point | `ENTRYPOINT ["uv", "run", "avideo"]` + documented CMD override | WIRED | ENTRYPOINT unchanged; headless launch documented in comment block |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `phase_5_extras.py` | `burn_subs`, `bg_music_volume`, `crossfade_seconds` | st.toggle/st.slider widget values | Yes — widget values from user interaction | FLOWING |
| `phase_5_extras.py` | `rc_dict["bg_music_path"]` | `write_uploaded_music()` return value → path on disk | Yes — real filesystem write at workdir/music/ | FLOWING |
| `phase_6_ensamble.py` | `assemble_done` | `workdir.is_done("assemble")` | Yes — checks done-marker file existence | FLOWING |
| `phase_6_ensamble.py` | `qa` (QAReport) | `read_qa_report(workdir)` → `qa_report.json` written by AssembleStage | Yes — reads real JSON output of AssembleStage | FLOWING |
| `phase_6_ensamble.py` | `output_mp4` | `workdir.root / "output.mp4"` written by AssembleStage | Yes — real file produced by FFmpeg via AssembleStage | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 397 tests pass | `uv run python -m pytest -q` | 397 passed, 0 failed, 5 warnings | PASS |
| phase_5_extras importable headlessly | `uv run python -c "import importlib; m = importlib.import_module('avideo.ui.pages.phase_5_extras'); print(callable(m.render))"` | True | PASS |
| phase_6_ensamble importable headlessly | `uv run python -c "import importlib; m = importlib.import_module('avideo.ui.pages.phase_6_ensamble'); print(callable(m.render))"` | True | PASS |
| Three new pipeline_ops helpers importable | `uv run python -c "from avideo.ui.pipeline_ops import write_uploaded_music, extras_to_run_config, read_qa_report; print('OK')"` | all three helpers importable: OK | PASS |
| pyproject.toml has avideo-studio entry | `grep -c "avideo-studio" pyproject.toml` | 1 | PASS |
| Dockerfile has EXPOSE 8501 | `grep -c "EXPOSE 8501" Dockerfile` | 1 | PASS |
| 7 page smoke tests pass | `uv run python -m pytest tests/test_page_smoke.py -v` | 7/7 PASSED | PASS |
| avideo studio UI launch + Fase 5/6 widget rendering | manual launch required | NOT TESTED | SKIP (human needed) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| EXT-01 | 13-02-PLAN.md | User configures subtitle burn, bg music upload + volume, crossfade | SATISFIED | phase_5_extras.py: all 5 widgets wired; approve gate persists to session_state["run_config"] |
| ASM-01 | 13-03-PLAN.md | System mounts final video automatically via bridge, integrating voice + extras; progress shown | SATISFIED (code) | phase_6_ensamble.py: AssembleStage launched via run_stage, @st.fragment polling non-blocking; UI-freeze absence is human-needed |
| ASM-02 | 13-03-PLAN.md | Final video shown in UI to play and download; QA report (duration deviation + LUFS) available | SATISFIED | phase_6_ensamble.py: st.video + st.download_button + 3 st.metric widgets; read_qa_report wired |

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `phase_5_extras.py` module-level | `import streamlit as st` at top of file | Info | Acceptable — Streamlit pages must import st at module scope; render() body uses lazy imports for all heavy deps; smoke tests confirm headless import succeeds because st is available in the test environment via uv |
| `phase_6_ensamble.py` module-level | Same pattern — `import streamlit as st` at top | Info | Same as above — expected and necessary |

No blockers found. No TODO/FIXME/placeholder comments. No empty return stubs. All return values wired to real data (widget state, filesystem, stage outputs).

### Human Verification Required

#### 1. avideo studio launches with 6-phase wizard

**Test:** Run `uv run avideo studio` from the project root
**Expected:** Browser opens at http://localhost:8501 showing the wizard with all 6 phases in the stepper; no crash on startup
**Why human:** app.py calls `st.set_page_config()` at module scope, which raises `StreamlitAPIException` outside a running Streamlit server; cannot be smoke-tested without a live server

#### 2. Fase 5 widget rendering (EXT-01 visual confirmation)

**Test:** Navigate to Fase 5 in the wizard (complete or skip earlier phases)
**Expected:** burn_subs toggle visible; music file uploader (mp3/wav) visible; volume slider (0.0-1.0) visible; fade-out slider (0-10s) visible; crossfade slider (0-3s) visible; "Aprobar extras y continuar" button visible and clickable; approving with no extras selected advances wizard to Fase 6
**Why human:** Streamlit widget rendering and click interactions require a live server; smoke tests only verify module-level import without calling render()

#### 3. Fase 6 non-blocking FFmpeg progress (ASM-01 behavioral)

**Test:** With all prior phases completed, click "Montar vídeo" in Fase 6
**Expected:** FFmpeg assembly runs in background thread; @st.fragment updates every 2s showing "Montando vídeo..." status; UI remains interactive during assembly; on completion st.video player + st.download_button + QA metrics appear
**Why human:** Non-blocking behavior requires observing concurrent UI responsiveness during a real FFmpeg run; cannot verify fragment polling or threading behavior programmatically without a running server

#### 4. Docker build (optional)

**Test:** Run `docker build -t avideo-test .` from the project root
**Expected:** Build completes without errors; `docker inspect avideo-test | grep 8501` shows EXPOSE 8501
**Why human:** Docker daemon required; not available in this verification environment

### Gaps Summary

No automated gaps found. All 5 roadmap success criteria are satisfied at the code level:

- SC-1 (EXT-01): phase_5_extras.py is fully implemented with all required widgets and approve gate
- SC-2 (ASM-01): phase_6_ensamble.py has non-blocking bridge launch + fragment polling — behavioral confirmation is human-needed
- SC-3 (ASM-02): st.video + st.download_button + QA st.metric widgets are wired and data-flowing
- SC-4 (packaging): avideo-studio entry in pyproject.toml; EXPOSE 8501 + headless docs in Dockerfile — live launch is human-needed
- SC-5 (tests): 397 passed, 0 failed — VERIFIED automated

4 human-verification items remain (UI rendering, non-blocking behavior, Docker build). These are inherently visual/runtime concerns that cannot be verified programmatically.

---

_Verified: 2026-05-29T18:30:00Z_
_Verifier: Claude (gsd-verifier)_
