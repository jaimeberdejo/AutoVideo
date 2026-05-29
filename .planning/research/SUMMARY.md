# Project Research Summary

**Project:** Auto Video Narrado — v2.0.0 Studio Guiado
**Domain:** Python GUI-over-CLI — Streamlit wizard over an existing narrated-video pipeline
**Researched:** 2026-05-29
**Confidence:** HIGH (all four research files verified against PyPI, official docs, Context7, and existing source code)

---

## Executive Summary

Auto Video Narrado v2.0.0 adds a Streamlit-based guided studio on top of the complete, passing v1.60.0 pipeline. The pattern is well-established: Streamlit acts as a thin orchestration layer that reads from and writes to the existing `workdir/` checkpoint system, while all heavy computation continues to happen inside the existing stage objects. The pipeline is not rewritten; it is wrapped. Three new backend capabilities are added in parallel: OpenAI Audio as a third TTS provider, background music mixing with ducking, and audio enhancement for uploaded recordings. Each slots into the existing stage interfaces without disrupting the stage sequence.

The recommended approach is to build backend integrations first (before any UI code), then the UI foundation (bridge + session state), and then phase pages in pipeline order. This sequence is dependency-driven: the UI pages call stage objects that must already exist, and each phase page unblocks the next. The `PipelineBridge` (background thread + `@st.fragment` polling of done markers) is the most architecturally critical new piece and must be solid before any long-running stage is connected to the UI.

The top risks are: (1) pipeline artifacts stored in `st.session_state` instead of being read from `workdir/` on each rerun — this causes state divergence on page reload and is easy to get wrong; (2) long-running stages called synchronously in the Streamlit main thread, freezing the UI; (3) upstream checkpoint edits (e.g., script text changes) that do not cascade to invalidate downstream done markers, silently producing a video that does not match the current script; and (4) double-normalization artifacts when background music mixing is added to an assemble stage that already runs loudnorm. All four are preventable by design decisions made before writing UI code.

---

## Conflict Resolution

### Audio Enhancement: FFmpeg-only vs noisereduce + pedalboard

STACK.md recommends FFmpeg-only (`afftdn`/`arnndn` + `loudnorm` via subprocess). FEATURES.md proposes adding `noisereduce` + `pedalboard` as new Python-level dependencies.

**Decision: FFmpeg-only. Do not add `noisereduce` or `pedalboard`.**

Rationale:
- The project constraint is explicit: FFmpeg via subprocess, no MoviePy, no heavy audio libs. `noisereduce` adds scipy/numpy signal processing overhead; `pedalboard` adds a compiled C++ extension — both for a use case that `afftdn=nr=6:nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11` covers adequately.
- PITFALLS.md (Pitfall 22) establishes that audio enhancement must run on a separate preview file and that WhisperX alignment must run on the **unprocessed original**. This order is the same whether the enhancement is Python-level or FFmpeg-level; FFmpeg-only is simpler to implement and easier to tune.
- PITFALLS.md (Pitfall 23) warns that aggressive denoise produces metallic artefacts. Conservative FFmpeg defaults (`nr=6` not the default `nr=12`) deliver the same "suave por defecto" UX that FEATURES.md describes, without the extra dependency surface.
- The MVP definition in FEATURES.md defers audio enhancement to v2.x, not v2.0.0 launch. This further reduces the urgency of a richer Python-level stack.

**Implementation:** `utils/audio_enhance.py` calls `ffmpeg -i input -af "afftdn=nr=6:nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11" output` via subprocess. The UI shows a preview (`st.audio`) of the enhanced file before the user confirms. WhisperX alignment always runs on the original unprocessed file.

---

## Key Findings

### Recommended Stack

The v1.60.0 stack is unchanged. Two production dependencies are added and one is promoted:

- `streamlit>=1.58.0` — Python-only web UI framework; `st.session_state`, `st.fragment(run_every=...)`, `st.status`, `st.navigation` provide everything needed for the wizard; no JS or separate frontend
- `openai>=2.38.0` — official SDK; `audio.speech.create()` for TTS + `audio.transcriptions.create(model="whisper-1", response_format="verbose_json", timestamp_granularities=["word"])` for the mandatory STT round-trip
- `python-dotenv>=1.0` — promoted from `[dev]` to `[project.dependencies]`; the UI needs `OPENAI_API_KEY` at runtime

No new audio processing libraries. FFmpeg built-in filters (`afftdn`, `arnndn`, `sidechaincompress`, `afade`, `amix`, `loudnorm`) cover all v2 audio needs.

**Version constraints that matter:**
- `streamlit>=1.58.0` requires Python >=3.10 (satisfied by project's Python 3.11+)
- `openai>=2.38.0` is compatible with `anthropic>=0.104.1` (both use `httpx`; no conflict)
- `st.fragment(run_every=...)` requires Streamlit >=1.37 (satisfied by >=1.58.0)
- `st.dialog` for back-navigation confirmation requires Streamlit >=1.32 (satisfied)

### Expected Features

**Must have (v2.0.0 launch):**
- Wizard with 6 gated phases and visual stepper
- Phase gating: Approve button disabled until phase output is valid; confirmation dialog before navigating back
- `invalidate_downstream(from_stage)` on back navigation and on any checkpoint edit
- Auto-bullet generation from topic (Claude) + `st.data_editor` for in-place editing
- Editable script per slide (`st.text_area`) with real-time WPM indicator and variation button
- Slide thumbnails grid with ok/warning/fail badges from `verification_report.json`
- Voice provider selector: ElevenLabs / OpenAI Audio / own recording
- `@st.fragment(run_every="2s")` progress polling for all long-running stages
- `st.video(str(path))` path-based for video preview in Phase 6
- File upload written to disk immediately on receipt
- Background music: file uploader + volume slider; FFmpeg `sidechaincompress` ducking + `afade`; `amix=normalize=0`

**Should have (P1/P2 — high value, moderate complexity):**
- OpenAI Audio TTS with mandatory Whisper STT round-trip for subtitles
- Interactive slide variation loop (clear done marker + relaunch stage via bridge)
- Cost-per-phase estimator surfaced in UI
- Full-size slide thumbnail on click (`st.dialog` modal)

**Defer to v2.x:**
- Audio enhancement UI button (`utils/audio_enhance.py` ships but UI button deferred)
- Project history / multiple workdir management
- `theme.yaml` visual editor (color picker)
- `.pptx` export button from UI

**Anti-features (explicitly out of scope):**
- Multi-user / auth (single-user localhost by design)
- Real-time video streaming during generation
- `st.audio_input` for in-browser recording (WebM/Opus degrades WhisperX quality)
- Auto-advance between phases without human confirmation

### Architecture Approach

The architecture is a three-tier stack: Streamlit UI layer → `workdir/` filesystem (sole source of truth) → Pipeline engine (existing, unmodified). The UI never stores pipeline artifacts in `st.session_state`; it reads from `workdir/*.json` on every rerun. Long-running stages run in background threads via `PipelineBridge`; the Streamlit main thread polls done markers via `@st.fragment(run_every="2s")`. The background thread never calls any `st.*` API.

**Major components:**

1. `ui/app.py` — Streamlit entry point with `st.navigation`; initializes session state with `workdir_path` (string) and `phase` (int 1–6)
2. `ui/bridge.py` — `PipelineBridge`: launches stage in `threading.Thread`, polls `workdir.is_done()`, exposes `run_stage()` / `stage_status()` / error accessor; module-level thread dict persists across reruns
3. `ui/state.py` — `PHASES` constant, `init_session_state()`, `advance_phase()`, `invalidate_downstream(workdir, from_stage)`
4. `ui/pages/phase_N_*.py` — one file per phase; reads checkpoints from `WorkdirManager`, renders UI, dispatches to `PipelineBridge`
5. `stages/voice_openai.py` — new stage implementing `CheckpointMixin`, same output contract as `VoiceElevenlabsStage` (`UnifiedTimings`); calls `integrations/openai.py`
6. `utils/audio_enhance.py` — plain function, not a stage; `enhance_audio(input, output)` via FFmpeg `afftdn` + `loudnorm`; alignment always runs on original
7. `integrations/ffmpeg.py` — extended with `build_music_mix_args()` returning `filter_complex` string; `amix=normalize=0` + `sidechaincompress` + `afade`
8. `stages/assemble.py` — extended to read `RunConfig.bg_music`; single loudnorm pass on the final mix only when music is present

### Critical Pitfalls

1. **UI main-thread blocking (Pitfall 13)** — Any stage call >2 s in the Streamlit script thread freezes the entire UI. Prevention: `PipelineBridge.run_stage()` + `@st.fragment(run_every="2s")`. This must be established before connecting any stage to the UI.

2. **Pipeline artifacts in `st.session_state` (Pitfall 14 + Anti-Pattern 6)** — `session_state` is lost on browser reload. Prevention: `session_state` holds only `workdir_path` (string) and `phase` (int); everything else is read from `workdir/` on every rerun.

3. **Downstream done markers not invalidated after upstream edit (Pitfall 24)** — Editing the script and saving to `workdir/script.json` leaves `.voice.done` and `.assemble.done` intact; the pipeline serves the old video. Prevention: implement `WorkdirManager.invalidate_downstream(from_stage)` before building any editable UI widget.

4. **OpenAI TTS has no timestamps — mandatory STT round-trip (Pitfall 17)** — `openai.audio.speech.create()` returns audio only. For subtitles, call `openai.audio.transcriptions.create(model="whisper-1", response_format="verbose_json", timestamp_granularities=["word"])`. Note: `gpt-4o-transcribe` does NOT support word timestamps.

5. **`amix` with `normalize=1` reduces narration by -6 dB (Pitfall 19)** — Default `amix` behavior applies gain reduction to both inputs. Prevention: always `amix=inputs=2:normalize=0`; control music level via `volume=X` before the `amix`; loudnorm runs once on the final combined output only.

6. **`st.file_uploader` loses the file on the next rerun (Pitfall 16)** — If the uploader widget is not rendered in the next rerun, Streamlit discards the `UploadedFile` from memory. Prevention: write to `workdir/` immediately on upload.

7. **Double-normalization pumping artifact (Pitfall 20)** — The existing assemble stage already runs loudnorm (two passes). Adding background music and running loudnorm again produces dynamic compression artefacts. Prevention: when `bg_music` is set, skip per-narration loudnorm and run the single two-pass loudnorm only on the final mix.

---

## Cross-Cutting Themes for the Roadmapper

These constraints must be respected across all phases — they are invariants, not per-phase concerns.

### 1. `workdir` checkpoints are the sole source of truth

`st.session_state` holds only `workdir_path` (string), `phase` (int 1–6), and ephemeral form inputs. Everything else — storyboard, script, slides paths, timings, voice output — is read from `workdir/*.json` via `WorkdirManager.read_checkpoint(name, Model)` on every Streamlit rerun. This makes the UI resilient to page reloads, reconnects, and Streamlit crashes.

**Corollary — checkpoint invalidation:** Any UI action that modifies an upstream checkpoint must immediately call `WorkdirManager.invalidate_downstream(from_stage)`, deleting all done markers for stages after `from_stage`. Implement this in `WorkdirManager` before building any editable widget.

### 2. Long-running stages run off the Streamlit script thread

Stages that take >2 s (slides render, TTS synthesis, FFmpeg assembly) are launched via `PipelineBridge.run_stage()` in a background `threading.Thread`. The thread writes only to `workdir/` and never calls any `st.*` API. Progress is displayed via `@st.fragment(run_every="2s")` polling `workdir.is_done(stage_name)`.

### 3. OpenAI Audio TTS requires a mandatory STT round-trip for subtitles

OpenAI TTS returns audio bytes with no timing data. Word-level timestamps for subtitle generation must be obtained by calling `openai.audio.transcriptions.create(model="whisper-1", ...)` on the generated audio. This adds 10–30 s per slide and must be designed into `VoiceOpenAIStage` from day one. If subtitles are disabled, the STT round-trip can be skipped and `timings.json` filled with proportional duration estimates.

### 4. Background music: single loudnorm pass on the final mix

When background music is present: (a) music level is controlled with `volume=X` before `amix`; (b) `amix=inputs=2:normalize=0` always; (c) ducking via `sidechaincompress`; (d) `afade` timing calculated from `ffprobe`-measured actual duration, not target duration; (e) loudnorm two-pass runs on the final mix only; per-narration loudnorm is skipped.

### 5. Audio enhancement: align on original, enhance for output only

`utils/audio_enhance.py` produces an enhanced file for the final video only. WhisperX alignment always runs on the original unprocessed audio. The enhanced file replaces the original only after alignment timestamps have been written to `timings.json`.

---

## Implications for Roadmap

### Suggested Phase Structure (7 phases)

#### Phase 1: Backend integrations (no UI)

**Rationale:** UI pages call stage objects that must exist and be tested first. All three new backend capabilities are independent of each other and of the UI.

**Delivers:**
- `VoiceMode.openai` in `models/config.py` + `RunConfig.bg_music` field
- `integrations/openai.py` — OpenAI Audio API wrapper
- `stages/voice_openai.py` — `VoiceOpenAIStage` with STT round-trip; same `UnifiedTimings` output contract as ElevenLabs stage
- `stages/voice.py` — openai dispatch branch
- `utils/audio_enhance.py` — `enhance_audio()` via FFmpeg `afftdn=nr=6:nf=-25` + `loudnorm`
- `integrations/ffmpeg.py` — `build_music_mix_args()` with `amix=normalize=0` + `sidechaincompress` + `afade`
- `stages/assemble.py` — reads `config.bg_music`; skips per-narration loudnorm when music is present; single loudnorm on final mix

**Avoids:** Pitfalls 17, 18, 19, 20, 21, 22

**Research flags:** Standard patterns — ARCHITECTURE.md provides concrete implementation for each; no additional research needed

---

#### Phase 2: UI foundation — bridge + state layer

**Rationale:** The bridge and state module are shared by all six phase pages. Build and validate in isolation before connecting any page.

**Delivers:**
- `ui/state.py` — `PHASES` constant, `init_session_state()`, `advance_phase()`
- `WorkdirManager.invalidate_downstream(from_stage)` — deletes done markers for all stages after a given stage
- `ui/bridge.py` — `PipelineBridge`: `run_stage()`, `stage_status()`, `RunStatus` enum, error accessor; module-level thread dict with `daemon=True`
- `ui/app.py` — `st.navigation` router with 6 empty phase pages; workdir setup; session state initialization
- Workdir lockfile (`workdir/.lock`) preventing two-tab state corruption

**Avoids:** Pitfalls 13, 14, 24, 26; Anti-Patterns 6, 7, 9, 10

---

#### Phase 3: Phase 1 page — Contenido

**Rationale:** First phase page; no upstream stage dependencies; validates the wizard navigation pattern end-to-end before adding complex stage integrations.

**Delivers:**
- `ui/pages/phase_1_contenido.py`
- Topic + duration form with validation
- Bullet auto-generation (direct Claude call with `st.spinner`; not a pipeline stage)
- `st.data_editor` for bullet editing
- Approve gate: writes `workdir/bullets.yaml`, advances to Phase 2

---

#### Phase 4: Phase 2 + 3 pages — Guion and Slides

**Rationale:** These two phases share the same "edit + variation + invalidate" pattern. Build them together.

**Delivers:**
- `ui/pages/phase_2_guion.py` — triggers storyboard → timing → scriptwriter via bridge; editable `st.text_area` per slide; variation button clears scriptwriter done marker + relaunches; WPM indicator; Approve gate
- `ui/pages/phase_3_slides.py` — triggers slides dispatch + verify via bridge; PNG thumbnail grid; badge ok/warning/fail from `verification_report.json`; variation loop; file uploader for hybrid/manual; Approve gate

**Avoids:** Pitfall 24 (downstream invalidation on edit); Anti-Pattern 8 (full pipeline re-run for single stage variation)

---

#### Phase 5: Phase 4 page — Voz

**Rationale:** Voice is the most technically complex phase (three provider paths + OpenAI STT round-trip). Build after slides so upstream checkpoints are exercised.

**Delivers:**
- `ui/pages/phase_4_voz.py`
- `st.radio` provider selector: ElevenLabs / OpenAI Audio / own recording
- ElevenLabs path: voice_id config → bridge → `st.audio` per slide
- OpenAI Audio path: voice selector (9 voices) → `VoiceOpenAIStage` via bridge → STT round-trip → `st.audio`; informational latency note
- Own recording path: per-slide file uploader → immediate write to `workdir/audio_user/`; optional enhance button → `enhance_audio()` → side-by-side `st.audio` preview; WhisperX alignment on original
- Approve gate: `timings.json` present and all slides have non-empty word timestamps

**Avoids:** Pitfalls 16, 17, 18, 22, 23

---

#### Phase 6: Phase 5 + 6 pages — Extras and Assembly

**Rationale:** Extras only stores config; Assembly is terminal and depends on all upstream outputs. Pair them.

**Delivers:**
- `ui/pages/phase_5_extras.py` — subtitles toggle + burn-subs checkbox; music file uploader (written to `workdir/bg_music.*` immediately); volume slider; transition crossfade selector; all stored in `st.session_state["run_config"]`; Approve gate (always enabled)
- `ui/pages/phase_6_ensamble.py` — triggers assemble via bridge (with full `run_config`); `@st.fragment(run_every="2s")` progress; `st.video(str(output_path))` path-based on DONE; `st.download_button`

**Avoids:** Pitfalls 19, 20, 21, 25

---

#### Phase 7: Polish, entry point, Docker, tests

**Delivers:**
- `pyproject.toml`: `streamlit>=1.58.0`, `openai>=2.38.0` to `[project.dependencies]`; `python-dotenv>=1.0` promoted; `avideo-studio` entry point
- `.streamlit/config.toml`: `server.address = "127.0.0.1"`; `server.maxUploadSize = 100`
- Dockerfile: `EXPOSE 8501`; `CMD` with `--server.headless=true --server.address=0.0.0.0`
- Unit tests: bridge thread launch, done-marker detection, `invalidate_downstream` correctness, phase page smoke tests, music mix args (`normalize=0` assertion), audio enhance output validation

**Avoids:** Security mistake (Streamlit exposed on 0.0.0.0 in dev)

---

### Phase Ordering Rationale

- Backend before UI: phase pages call stage objects; those objects must exist and be independently tested
- Bridge before pages: all pages share `PipelineBridge`; its correctness is a precondition for all page work
- Phase pages in pipeline order: each page reads checkpoints written by the previous phase; building in order allows end-to-end testing as each page lands
- Phase 5 (Extras) paired with Phase 6 (Assembly): Extras stores only config that Assembly consumes; they form a logical unit
- Polish/Docker last: no user-visible value until the full flow is exercisable end-to-end

### Research Flags

Phases needing deeper research: none. All four research files are HIGH confidence with verified, implementation-ready API patterns. ARCHITECTURE.md (Layer A → D build order) maps directly onto the 7-phase structure above.

Standard patterns (skip additional research): all phases.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified on PyPI (May 2026); no version conflicts between new and existing deps |
| Features | HIGH / MEDIUM* | *OpenAI Audio TTS no-timestamps is community-confirmed; STT round-trip workaround is HIGH confidence |
| Architecture | HIGH | Patterns drawn from existing source code + official Streamlit/threading docs |
| Pitfalls | HIGH | 26 pitfalls verified; v1 pitfalls confirmed in v1.60.0 production audit; v2 pitfalls verified against official docs |

**Overall confidence:** HIGH

### Gaps to Address During Implementation

- **FFmpeg `arnndn` model file** — `arnndn` requires a bundled `.rnnn` model file. Use `afftdn` (no model file, FFT-based, more predictable artefacts) as the default in `audio_enhance.py`; `arnndn` as an optional upgrade.
- **`whisper-1` Spanish word-timestamp quality** — Acceptable but not perfect for Spanish. If subtitle quality is inadequate, fallback is WhisperX (already in the `[record]` optional group). Not a blocking gap.
- **WPM calibration for Spanish + ElevenLabs** — Carried forward from v1.60.0 technical debt. Not a v2.0.0 blocker.
- **Lockfile cross-platform** — `fcntl.flock` is Unix/macOS only. Acceptable given the project targets macOS + Docker (Linux) for v2.0.0.

---

## Sources

### Primary (HIGH confidence)

- Context7 `/streamlit/streamlit` — `st.session_state`, `st.fragment(run_every=...)`, `st.status`, `st.navigation`, `st.dialog`, `st.file_uploader`, threading
- Context7 `/openai/openai-python` — `audio.speech.create()`, `audio.transcriptions.create()`, whisper-1 word timestamps
- Context7 `/anthropic/anthropic-sdk-python` — vision, structured outputs
- Context7 `/playwright/playwright-python` — `Page.screenshot()`, `animations='disabled'`
- [streamlit · PyPI](https://pypi.org/project/streamlit/) — v1.58.0 verified May 2026
- [openai · PyPI](https://pypi.org/project/openai/) — v2.38.0 verified May 2026
- [FFmpeg Filters Documentation](https://ffmpeg.org/ffmpeg-filters.html) — `afftdn`, `sidechaincompress`, `afade`, `loudnorm`, `amix`
- [Streamlit threading docs](https://docs.streamlit.io/develop/concepts/design/multithreading)
- [Streamlit st.fragment docs](https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment)
- Existing source code: `src/avideo/orchestrator.py`, `stages/base.py`, `utils/workdir.py` (v1.60.0 passing audit)

### Secondary (MEDIUM confidence)

- [OpenAI TTS no timestamps — community forum](https://community.openai.com/t/timestamped-captions-for-tts-api-feature-request/538339)
- [OpenAI speech-to-text word timestamps](https://platform.openai.com/docs/guides/speech-to-text/timestamps) — `whisper-1` supports word granularity; `gpt-4o-transcribe` does not
- [ElevenLabs: Speech Timestamp Stagnation Bug #607](https://github.com/elevenlabs/elevenlabs-python/issues/607)
- [FFmpeg sidechaincompress ducking (mailing list Nov 2024)](https://ffmpeg.org/pipermail/ffmpeg-user/2024-November/058872.html)

---

*Research completed: 2026-05-29*
*Ready for roadmap: yes*
