---
phase: 11-guion-slides-pages
verified: 2026-05-29T17:45:00Z
status: passed
score: 5/5
overrides_applied: 0
human_verification:
  - test: "Fase 2 auto-run: start avideo studio, approve bullets in Fase 1, advance to Fase 2. Verify the st.status box appears with 'Generando guion...' and each stage (Storyboard → Timing → Guion) shows progress, then transitions to the editor once done."
    expected: "Editor shows per-slide st.text_area widgets populated with narration text; no blank page or placeholder."
    why_human: "Fragment polling + background bridge threads cannot be exercised headlessly; st.fragment(run_every='2s') rerun cycle is a browser event."
  - test: "Fase 2 inline edit: edit the narration of one slide, click 'Guardar edicion slide N'. Confirm workdir/script.json updates with the new text and that downstream .done files (voice, align, subs, assemble) are absent."
    expected: "script.json contains the edited narration; downstream done-markers are cleared."
    why_human: "Requires live Streamlit session; session_state interaction with widget values cannot be unit-tested."
  - test: "Fase 2 variation: click 'Pedir variacion del guion'. Confirm only the scriptwriter stage re-runs (storyboard and timing done-markers remain), and after completion the editor repopulates with different narration text."
    expected: "Storyboard/timing .done files still present; new script.json content differs from before."
    why_human: "Requires observing bridge thread lifecycle and done-marker state in a live browser session."
  - test: "Fase 2 approval: click 'Aprobar guion'. Confirm the footer 'Aprobar y continuar' button becomes enabled and a browser refresh resumes at Fase 2 with the editor showing the approved script."
    expected: "scriptwriter.done file present after approval; wizard stays at Fase 2 on refresh with editor populated."
    why_human: "Navigation gate and session-state reconstruction require live browser interaction."
  - test: "Fase 3 auto mode: reach Fase 3 with 'Generar (auto)' selected. Confirm spinner appears, then PNG thumbnails load in a 3-column grid with badge labels (ok badges expected in auto mode since VerifyStage skips Claude Vision). Click 'Pedir variacion de slides' and confirm regeneration."
    expected: "Thumbnail grid with at least one column of images; all badges show ok; variation re-renders new thumbnails."
    why_human: "Slide rendering + Playwright Chromium + thumbnail display require live browser with workdir containing renders."
  - test: "Fase 3 upload mode: switch to 'Subir las mias', upload a PNG per slide slot. Confirm immediate write to workdir/slides_user/slide_XX.png (no page hang). Then click 'Verificar diapositivas (Claude Vision)' and confirm per-slide badges and issues display."
    expected: "Slides written to disk immediately on upload; verification report shows per-slide ok/warning/fail with Claude Vision issues."
    why_human: "Requires real ANTHROPIC_API_KEY, file uploader widget, and live browser for the UploadedFile lifecycle (Streamlit discards on next rerun)."
  - test: "Fase 3 re-upload: for a slide with a warning/fail verdict, re-upload a corrected PNG. Confirm old done-markers are cleared and re-verification is possible."
    expected: "'Volver a subir / re-verificar' button clears verify done-marker; fresh verification run starts."
    why_human: "Requires live browser session and Claude Vision API call."
  - test: "Wizard state persistence: in either Fase 2 or Fase 3, close the browser and reopen. Confirm the wizard resumes at the correct phase with correct state (checkpoints re-read from workdir, not session_state)."
    expected: "Phase and editor state match what was persisted to workdir; no blank reset."
    why_human: "Session-state reconstruction after browser close requires a live Streamlit server."
---

# Phase 11: Guion + Slides Pages Verification Report

**Phase Goal:** El usuario puede revisar y aprobar el guion slide a slide (con edicion inline y variaciones) y las diapositivas generadas (con thumbnails, badges de QC y la opcion de subir las suyas)
**Verified:** 2026-05-29T17:45:00Z
**Status:** passed
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | On entering Fase 2, the system auto-runs storyboard+timing+scriptwriter via bridge; user sees per-stage progress | VERIFIED | `phase_2_guion.py` `render()` checks each done-marker sequentially, calls `run_stage()` for the next pending stage (lines 55-73), uses `@st.fragment(run_every="2s")` to poll and rerun. Import succeeds. No placeholder body. |
| 2 | User can edit any slide's narration inline; changes are persisted and downstream checkpoints invalidated | VERIFIED | `st.text_area` per slide with `"narration_{idx}"` key; `_save_edited_script()` calls `persist_edited_script(workdir, updated_script)` which calls `write_checkpoint("script", ...)` THEN `invalidate_downstream("scriptwriter")` (correct Pitfall-4 order confirmed at lines 101-102 of pipeline_ops.py). |
| 3 | Variation button re-runs ONLY the scriptwriter stage (not storyboard/timing) | VERIFIED | `rerun_scriptwriter()` in pipeline_ops.py: (1) deletes only `.scriptwriter.done` marker, (2) calls `invalidate_downstream("scriptwriter")`, (3) calls `run_stage(ScriptwriterStage(), ...)`. Test `test_rerun_scriptwriter_invalidates_only_from_scriptwriter` asserts `invalidate_downstream` is called with exactly `"scriptwriter"`. 9/9 pipeline_ops tests GREEN. |
| 4 | Fase 3 mode radio selects auto vs upload; auto shows thumbnails+QC badges; variation re-runs slides only | VERIFIED | `phase_3_slides.py` `render()` has `st.radio("Modo de diapositivas", ...)` routing to `_render_auto()` or `_render_upload()`. Auto path: `SlidesDispatchStage` + `VerifyStage` via bridge, thumbnail grid with `badge_for_verdict()` badges. Variation: `rerun_slides()` from pipeline_ops. grep counts: st.radio=1, st.image=3, rerun_slides=2, badge_for_verdict|VerificationReport=9. |
| 5 | Upload mode writes slides immediately via `write_uploaded_slide`, runs Claude Vision QC, shows per-slide report; re-upload is possible | VERIFIED | `_render_upload()`: per-slide `st.file_uploader`; calls `write_uploaded_slide(workdir, expected_name, uploaded.read())` immediately on upload (guards Streamlit discard-on-rerun); "Verificar diapositivas" runs `SlidesDispatchStage` + `VerifyStage`; shows per-slide badges + issues; "Volver a subir / re-verificar" calls `workdir.invalidate_downstream("slides")` then `st.rerun()`. Path-traversal guard: ValueError on `"/"`, `"\\"`, `".."` prefix (line 133 pipeline_ops.py; test `test_write_uploaded_slide_rejects_path_traversal` GREEN). |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/avideo/ui/pipeline_ops.py` | 5 exported functions (rerun_scriptwriter, rerun_slides, persist_edited_script, write_uploaded_slide, badge_for_verdict) | VERIFIED | Exists, 5 `def` at module scope, no Streamlit import, full implementation. Commit 698089f. |
| `src/avideo/ui/pages/phase_2_guion.py` | Real Fase 2 page replacing Phase 9 placeholder; `render(workdir) -> bool` | VERIFIED | Exists, substantive SCR-01..04 implementation (201 lines), no placeholder body, imports cleanly. Commit fa296c4. |
| `src/avideo/ui/pages/phase_3_slides.py` | Real Fase 3 page replacing Phase 9 placeholder; `render(workdir) -> bool` | VERIFIED | Exists, substantive SLD-01..03 implementation (369 lines), no placeholder body, imports cleanly. Commit 9c90810. |
| `tests/test_pipeline_ops.py` | 9 RED tests from Plan 01, all GREEN | VERIFIED | 9/9 tests pass. All contracts covered: invalidate scope, write ordering, path traversal, badge mapping. Commit d1a6606. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `pipeline_ops.py` | `avideo.ui.bridge.run_stage` | Module-scope import as mock seam | WIRED | `from avideo.ui.bridge import run_stage` at module level (line 18); `run_stage()` called in `rerun_scriptwriter` and `rerun_slides`. |
| `pipeline_ops.py` | `WorkdirManager.invalidate_downstream` | Direct call | WIRED | `workdir.invalidate_downstream("scriptwriter")` in `rerun_scriptwriter` (line 50) and `persist_edited_script` (line 102); `workdir.invalidate_downstream("slides")` in `rerun_slides` (line 77). |
| `phase_2_guion.py` | `avideo.ui.pipeline_ops.rerun_scriptwriter` | "Pedir variacion" button | WIRED | `from avideo.ui.pipeline_ops import rerun_scriptwriter` inside variation button handler (line 117); called immediately after clearing cached narrations. |
| `phase_2_guion.py` | `avideo.ui.pipeline_ops.persist_edited_script` | "Guardar edicion" per-slide button | WIRED | `_save_edited_script()` helper calls `persist_edited_script(workdir, updated_script)` (line 200); used by both "Guardar edicion" buttons and the approval gate. |
| `phase_2_guion.py` | `avideo.ui.bridge.run_stage / stage_status` | Auto-run storyboard->timing->scriptwriter | WIRED | `from avideo.ui.bridge import RunStatus, get_error, run_stage, stage_status` at module top (line 20); `run_stage()` called 3 times in auto-run block; `stage_status()` called in `_show_pipeline_progress()`. |
| `phase_3_slides.py` | `avideo.ui.pipeline_ops.rerun_slides` | "Pedir variacion de slides" button (auto mode) | WIRED | `from avideo.ui.pipeline_ops import rerun_slides` in `_render_auto()` variation button handler (line 173); `rerun_slides(workdir, config)` called after `invalidate_downstream("slides")`. |
| `phase_3_slides.py` | `avideo.ui.pipeline_ops.write_uploaded_slide` | `st.file_uploader` on-upload handler | WIRED | `from avideo.ui.pipeline_ops import write_uploaded_slide` in `_render_upload()` (line 207); called immediately on `uploaded is not None` with `expected_name` (not raw user filename — T-11-04-01 mitigated). |
| `phase_3_slides.py` | `avideo.models.verification.VerificationReport` | `workdir.read_checkpoint("verification", VerificationReport)` | WIRED | Imported and used in both `_render_auto()` (line 140) and `_render_upload()` (line 293); `badge_for_verdict(verdict)` applied per slide. |
| `app.py` `_PHASE_MODULES` | `phase_3_slides` module | Router entry `3: phase_3_slides` | WIRED | `_PHASE_MODULES = {1: ..., 2: phase_2_guion, 3: phase_3_slides, 4: ..., 5: ..., 6: ...}` — no orphaned or duplicate mapping for phase 3. All 6 phases covered. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `phase_2_guion.py` | `script: ScriptOutput` | `workdir.read_checkpoint("script", ScriptOutput)` | Yes — reads scriptwriter checkpoint JSON written by `ScriptwriterStage` | FLOWING |
| `phase_3_slides.py` auto path | `slides_out: SlidesOutput` | `workdir.read_checkpoint("slides", SlidesOutput)` | Yes — reads SlidesDispatchStage checkpoint; `png_paths` rendered by Playwright | FLOWING |
| `phase_3_slides.py` auto path | `report: VerificationReport` | `workdir.read_checkpoint("verification", VerificationReport)` | Yes — reads VerifyStage checkpoint; `slides[].status` from Claude Vision or auto-ok | FLOWING |
| `phase_3_slides.py` upload path | `sb: StoryboardOutput` | `workdir.read_checkpoint("storyboard", StoryboardOutput)` | Yes — reads storyboard checkpoint for slide count; try/except guards missing checkpoint | FLOWING |
| `pipeline_ops.py` `persist_edited_script` | `edited: ScriptOutput` | Caller passes user-edited narrations from session_state | Yes — `workdir.write_checkpoint("script", edited)` writes to disk immediately | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| pipeline_ops.py imports without Streamlit | `uv run python -c "from avideo.ui.pipeline_ops import rerun_scriptwriter, rerun_slides, persist_edited_script, write_uploaded_slide, badge_for_verdict; print('OK')"` | "OK" | PASS |
| phase_2_guion.py imports cleanly | `uv run python -c "from avideo.ui.pages.phase_2_guion import render; print('OK')"` | "OK" | PASS |
| phase_3_slides.py imports cleanly | `uv run python -c "from avideo.ui.pages.phase_3_slides import render; print('OK')"` | "OK" | PASS |
| app.py imports with no ImportError (router covers 6 phases) | `uv run python -c "import avideo.ui.app; print('OK')"` | "OK" (Streamlit bare-mode warnings only — expected) | PASS |
| Full test suite (370 tests) | `uv run pytest -q` | 370 passed, 5 warnings | PASS |
| pipeline_ops 9 tests all GREEN | `uv run pytest tests/test_pipeline_ops.py -v` | 9/9 passed | PASS |
| persist_edited_script write ordering (write before invalidate) | grep lines 101-102 pipeline_ops.py | `write_checkpoint` at line 101, `invalidate_downstream` at line 102 | PASS |
| Path traversal guard | `test_write_uploaded_slide_rejects_path_traversal` | pytest PASSED | PASS |
| badge_for_verdict mapping | `test_badge_ok`, `test_badge_warning`, `test_badge_fail` | All pytest PASSED | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SCR-01 | 11-03 | Auto-generate storyboard+timing+guion from duration | SATISFIED | `render()` sequentially launches `StoryboardStage`, `TimingStage`, `ScriptwriterStage` via bridge on entry if not done; fragment polling shows live progress |
| SCR-02 | 11-03 | User edits slide narration directly in UI | SATISFIED | `st.text_area` per slide (key `narration_{idx}`); "Guardar edicion" calls `persist_edited_script`; edits cached in `scr_edited_narrations` session_state |
| SCR-03 | 11-03 | User can request guion variation (Claude regeneration) | SATISFIED | "Pedir variacion del guion" button calls `rerun_scriptwriter(workdir, config)` which resets only scriptwriter done-marker; storyboard/timing untouched |
| SCR-04 | 11-03 | Approved guion persisted; downstream invalidated | SATISFIED | "Aprobar guion" calls `_save_edited_script()` then `workdir.mark_done("scriptwriter")`; `persist_edited_script` calls `invalidate_downstream("scriptwriter")` before returning |
| SLD-01 | 11-04 | User chooses auto or upload mode | SATISFIED | `st.radio("Modo de diapositivas", ["Generar (auto)", "Subir las mias"], horizontal=True)`; mode persisted in `session_state["sld_mode"]` and `rc_dict["slides_mode"]` |
| SLD-02 | 11-04 | Auto mode: thumbnails + badges + variation | SATISFIED | `_render_auto()` launches `SlidesDispatchStage` + `VerifyStage`; reads `SlidesOutput.png_paths`; 3-column `st.image` grid with `badge_for_verdict()` labels; variation button calls `rerun_slides()` |
| SLD-03 | 11-04 | Upload mode: Claude Vision QC; per-slide report; re-upload | SATISFIED | `_render_upload()`: per-slide `st.file_uploader`; `write_uploaded_slide` immediately on upload; "Verificar" runs `VerifyStage`; per-slide verdict+issues displayed; "Volver a subir" resets via `invalidate_downstream("slides")` |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | — | — | No TODOs, FIXMEs, empty returns, or placeholder stubs found in Phase 11 files |

Note: `phase_4_voz.py`, `phase_5_extras.py`, and `phase_6_ensamble.py` are intentional placeholders from Phase 9 delivery. They are correctly NOT in Phase 11 scope.

### Human Verification Required

The following browser-interactive behaviors cannot be verified headlessly and require a live `avideo studio` session:

#### 1. Fase 2 Auto-Run Pipeline Progress

**Test:** Start `uv run avideo studio`, complete Fase 1 (approve bullets), advance to Fase 2.
**Expected:** `st.status` box appears showing "Storyboard: pendiente / Timing: pendiente / Guion: pendiente", then each transitions to "Generando..." and finally to "Listo:" as stages complete. Once all done, per-slide narration editors appear.
**Why human:** `@st.fragment(run_every="2s")` polling loop and background bridge threads require a live Streamlit server + browser interaction.

#### 2. Fase 2 Inline Edit + Downstream Invalidation

**Test:** In Fase 2 editor, modify one slide's narration text and click "Guardar edicion slide N".
**Expected:** `workdir/script.json` updates with the new narration; downstream `.done` files (voice, align, subs, assemble) are absent from workdir.
**Why human:** `session_state["scr_edited_narrations"]` values are driven by widget state which can only be tested in a real Streamlit session.

#### 3. Fase 2 Variation (Scriptwriter-Only)

**Test:** Click "Pedir variacion del guion". Observe that storyboard and timing `.done` files remain present in workdir while only scriptwriter reruns.
**Expected:** New narration text appears in editor; `workdir/.storyboard.done` and `workdir/.timing.done` still exist; `workdir/.scriptwriter.done` was deleted and re-created.
**Why human:** Done-marker state inspection requires access to a live workdir while the wizard is running.

#### 4. Fase 2 Approval + Browser Refresh

**Test:** Click "Aprobar guion". Confirm footer "Aprobar y continuar" becomes enabled. Then refresh the browser and confirm wizard resumes at Fase 2 with the editor populated (not a blank page).
**Expected:** `workdir/.scriptwriter.done` present; `render()` returns `True`; workdir reconstruction on refresh re-reads `script.json` correctly.
**Why human:** Navigation gate (`gate_met` -> footer button enable) and session-state reconstruction are live-browser behaviors.

#### 5. Fase 3 Auto Mode Thumbnails + Badges

**Test:** Reach Fase 3 with "Generar (auto)" selected (or advance from Fase 2). Confirm spinner progress appears, then a 3-column grid of PNG thumbnails loads with badge labels (expect all "✅" in auto mode).
**Expected:** PNG thumbnail grid rendered; badge labels visible; no blank or error state.
**Why human:** Playwright slide rendering + `st.image()` with file paths require a running Streamlit server with actual rendered PNG files in workdir.

#### 6. Fase 3 Upload Mode + Claude Vision QC

**Test:** Switch to "Subir las mias". Upload PNG files per slide slot. Verify each file appears immediately in workdir/slides_user/. Click "Verificar diapositivas (Claude Vision)". Confirm per-slide badges and issues display with actual Claude Vision output.
**Expected:** Files written synchronously on upload; verification runs with real ANTHROPIC_API_KEY; per-slide report with ok/warning/fail verdicts and issue text shown.
**Why human:** `st.file_uploader` UploadedFile lifecycle (discarded on next rerun), Claude Vision API call, and live workdir state all require browser + valid API key.

#### 7. Fase 3 Re-Upload Flow

**Test:** After a verification run with a warning/fail slide, click "Volver a subir / re-verificar". Confirm done-markers are cleared and re-upload + re-verify is possible.
**Expected:** "Volver a subir" clears verify done-marker; fresh upload slots appear; clicking "Verificar" again runs a new Claude Vision pass.
**Why human:** Sequential re-verification state requires live bridge thread management.

#### 8. Wizard State Persistence Across Browser Close/Reopen

**Test:** Mid-way through Fase 2 or 3, close the browser and reopen `localhost:8501`. Confirm the wizard resumes at the correct phase.
**Expected:** `workdir_phase_from_done_markers(workdir)` restores the correct phase; editor content re-read from `script.json`; no blank reset.
**Why human:** Browser close clears session_state; state reconstruction from done-markers requires live workdir with real done files.

### Gaps Summary

No programmatic gaps found. All 5 must-have truths are VERIFIED at all four levels (exists, substantive, wired, data flowing). The full test suite passes (370/370). All commits confirmed in git log. All imports succeed.

The `human_needed` status reflects that 8 behaviors require live browser + Streamlit + real workdir state to confirm end-to-end function. These are inherent to a Streamlit wizard and cannot be exercised headlessly.

---

*Verified: 2026-05-29T17:45:00Z*
*Verifier: Claude (gsd-verifier)*

## Post-hoc Real Browser Verification (2026-07-01)

The `human_needed` items above were resolved via live browser UAT (Chrome MCP + Playwright, real Anthropic/OpenAI/ffmpeg calls, not mocked) in a dedicated verification session. See `.planning/phases/11-guion-slides-pages/11-UAT.md` for the specific test results and `.planning/v2.0.0-BROWSER-VERIFICATION.md` for the full report, including 3 blocker bugs found and fixed during that session (none visible to the mocked unit-test suite). Status upgraded from `human_needed` to `passed` based on this evidence.

---
