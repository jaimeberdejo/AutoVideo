# Architecture Research

**Domain:** Sequential CLI pipeline with resumable checkpoints, typed I/O, own orchestrator — Python 3.11+; v2.0.0 adds Streamlit UI layer that orchestrates the existing pipeline as a headless engine
**Researched:** 2026-05-29
**Confidence:** HIGH

---

## Standard Architecture

### System Overview (v2.0.0 — Studio Guiado)

```
┌────────────────────────────────────────────────────────────────┐
│                     Streamlit UI Layer                          │
│                 (src/avideo/ui/app.py + pages/)                 │
│                                                                 │
│  Phase 1      Phase 2       Phase 3      Phase 4     Phase 5-6 │
│  Contenido → Guion+Slides → Diapositivas → Voz → Extras+Ensam  │
│                                                                 │
│  st.session_state["phase"] — current phase                      │
│  st.session_state["workdir"] — active run workdir               │
│  Human-gate buttons: [Approve ✓] / [Re-generate ↻] per phase  │
└──────────┬────────────────────────────────────────────────────┘
           │  reads/writes via WorkdirManager
           │  runs stages via subprocess OR direct call
           │
┌──────────▼────────────────────────────────────────────────────┐
│                     State Layer (workdir/)                      │
│                                                                 │
│  JSON checkpoints (primary source of truth for UI)             │
│  context.json  storyboard.json  script.json  timings.json      │
│  verification_report.json  voice.json  assembly.json           │
│                                                                 │
│  Artifact dirs                    Done markers                  │
│  slides/  audio/  subs/           .context.done .storyboard... │
│  design_proposal/  slides_user/   (presence = phase complete)  │
│  output.mp4                                                     │
└──────────┬────────────────────────────────────────────────────┘
           │
┌──────────▼────────────────────────────────────────────────────┐
│              Pipeline Engine (existing — NOT rewritten)         │
│                                                                 │
│  CLI: avideo generate --level 4 --bullets ... --duration ...   │
│  Orchestrator: PIPELINE_STAGES loop, checkpoint/done logic     │
│  Stages: StageProtocol + CheckpointMixin (unchanged)           │
│                                                                 │
│  NEW stage slots:                                              │
│    voice provider: openai (new VoiceMode enum value)            │
│    assemble: music_mix pre-step (new FFmpeg filter in stage)    │
│    audio enhance: new standalone function (not a full stage)    │
└────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities (v2.0.0 delta — full table includes v1.60.0 entries)

| Component | Responsibility | Status | Communicates With |
|-----------|----------------|--------|-------------------|
| `ui/app.py` | Streamlit entry point; `st.navigation` router; initialize `session_state` | NEW | All UI pages |
| `ui/pages/phase_1.py` | Topic + duration form; bullet auto-gen (Claude) or manual; approve gate | NEW | WorkdirManager, AnthropicIntegration |
| `ui/pages/phase_2.py` | Storyboard + script review, edit, variation requests; approve gate | NEW | WorkdirManager, PipelineBridge |
| `ui/pages/phase_3.py` | Slide thumbnails; edit/variation UI; OR upload + vision-verify | NEW | WorkdirManager, PipelineBridge |
| `ui/pages/phase_4.py` | Voice provider selector; audio upload + enhance button | NEW | WorkdirManager, PipelineBridge |
| `ui/pages/phase_5.py` | Subtitles toggle, music-file upload, transition config | NEW | WorkdirManager |
| `ui/pages/phase_6.py` | Assemble trigger; st.video preview; download button | NEW | WorkdirManager, PipelineBridge |
| `ui/bridge.py` | `PipelineBridge`: runs long stages in a background thread; polls workdir checkpoints; exposes `run_stage()`, `is_done()`, `read_checkpoint()` | NEW | orchestrator, WorkdirManager |
| `ui/state.py` | `init_session_state()`, phase constants, enum for `RunStatus` | NEW | All UI pages |
| CLI (`cli.py`) | `avideo generate` — unchanged; now also callable headless by bridge | UNCHANGED | Orchestrator |
| Orchestrator | Sequential stage loop, approval gates — in headless mode (L4 always) | UNCHANGED | Stages, WorkdirManager |
| `stages/voice.py` | Dispatcher — adds `VoiceMode.openai` branch | MODIFIED | VoiceOpenAIStage (new) |
| `integrations/openai.py` | OpenAI Audio API thin wrapper | NEW | `openai` SDK |
| `stages/voice_openai.py` | OpenAI TTS stage producing `UnifiedTimings` | NEW | `integrations/openai.py` |
| `stages/assemble.py` | FFmpeg assembly — adds optional `music_path` ducking/fade pre-step | MODIFIED | `integrations/ffmpeg.py` |
| `integrations/ffmpeg.py` | `build_music_mix_args()` for ducking + fade | MODIFIED | subprocess |
| `utils/audio_enhance.py` | `enhance_audio(input_path, output_path)` — FFmpeg denoise + loudnorm | NEW | subprocess (ffmpeg) |
| All v1.60.0 stages | Unchanged contracts, unchanged checkpoints | UNCHANGED | — |

---

## Recommended Project Structure (v2.0.0 additions)

```
src/avideo/
├── cli.py                        # unchanged
├── orchestrator.py               # unchanged
├── models/
│   └── config.py                 # MODIFIED: VoiceMode.openai added
├── stages/
│   ├── voice.py                  # MODIFIED: openai branch added
│   ├── voice_openai.py           # NEW: OpenAI Audio TTS stage
│   └── assemble.py               # MODIFIED: music_path param + ducking
├── integrations/
│   ├── openai.py                 # NEW: openai TTS wrapper
│   └── ffmpeg.py                 # MODIFIED: music mix args
├── utils/
│   └── audio_enhance.py          # NEW: denoise + loudnorm helper
└── ui/                           # NEW: entire subtree
    ├── app.py                    # Streamlit entry point + st.navigation
    ├── state.py                  # session_state init, constants
    ├── bridge.py                 # PipelineBridge (thread + checkpoint poll)
    └── pages/
        ├── phase_1_contenido.py
        ├── phase_2_guion.py
        ├── phase_3_slides.py
        ├── phase_4_voz.py
        ├── phase_5_extras.py
        └── phase_6_ensamble.py
```

---

## Architectural Patterns

### Pattern 1: workdir Checkpoints as Source of Truth (NOT session_state)

**What:** The Streamlit UI never stores pipeline artifacts in `st.session_state`. The only things in `session_state` are: current phase index, path to active `workdir/`, UI-transient values (form inputs, edit buffers, approval status for the current session). All pipeline data — storyboard, script, slides paths, timings — is always read from `workdir/*.json` via `WorkdirManager.read_checkpoint()`.

**When to use:** Always, without exception. This is the key architectural decision for v2.0.0.

**Why:** Streamlit reruns the entire script on every widget interaction. If stage outputs lived in `session_state`, they would be re-serialised and re-deserialised on every button click. More importantly, if the user closes and re-opens the browser, or if Streamlit crashes, checkpoint-based state survives while `session_state` is lost. The existing pipeline already writes all state to `workdir/` — the UI is just a reader of that same truth.

**Trade-offs:** Every phase page must call `workdir.read_checkpoint(name, Model)` to get data. Slightly more I/O than session_state. Acceptable because checkpoints are small JSON files read in <1ms.

```python
# ui/pages/phase_2_guion.py (pattern example)
import streamlit as st
from avideo.utils.workdir import WorkdirManager
from avideo.models.script import ScriptOutput

def render():
    workdir = WorkdirManager(st.session_state["workdir_path"])

    # Read directly from checkpoint — do NOT cache in session_state
    if not workdir.is_done("scriptwriter"):
        st.info("Script not yet generated.")
        return

    script: ScriptOutput = workdir.read_checkpoint("script", ScriptOutput)
    for slide in script.slides:
        st.text_area(f"Slide {slide.slide_index}", value=slide.narration, key=f"narr_{slide.slide_index}")
```

### Pattern 2: PipelineBridge — Background Thread + Checkpoint Polling

**What:** Long-running pipeline steps (Playwright render, ElevenLabs TTS, FFmpeg encode) are executed in a Python `threading.Thread` launched by `PipelineBridge.run_stage()`. Streamlit uses `@st.fragment(run_every="2s")` to periodically poll whether the done marker exists, then updates the UI when the stage completes. The background thread writes to `workdir/` using `WorkdirManager` — it never calls Streamlit APIs directly.

**When to use:** Any stage that takes more than 2 seconds. In practice: slides render, voice synthesis, assembly.

**Why:** Streamlit re-executes the entire script on every interaction. If a long-running stage ran synchronously in the main script thread, the UI would be unresponsive and the browser would show a spinner for minutes. The background-thread pattern avoids this by decoupling execution from the rerun cycle. The polling fragment (`run_every`) gives the user live status without manual refresh.

**Concrete implementation:**

```python
# ui/bridge.py
import threading
from enum import Enum
from pathlib import Path
from avideo.utils.workdir import WorkdirManager
from avideo.stages.base import StageProtocol
from avideo.models.config import RunConfig

class RunStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"

_threads: dict[str, threading.Thread] = {}
_errors: dict[str, Exception] = {}

def run_stage(stage: StageProtocol, workdir: WorkdirManager, config: RunConfig) -> None:
    """Launch stage in a background thread. Idempotent: no-op if already running or done."""
    key = stage.stage_name
    if key in _threads and _threads[key].is_alive():
        return  # already running
    if workdir.is_done(key):
        return  # already done

    def _target():
        try:
            output = stage.run(workdir, config)
            workdir.write_checkpoint(stage.checkpoint_name, output)
            workdir.mark_done(key)
        except Exception as exc:
            _errors[key] = exc

    t = threading.Thread(target=_target, daemon=True)
    _threads[key] = t
    t.start()

def stage_status(stage_name: str, workdir: WorkdirManager) -> RunStatus:
    if stage_name in _errors:
        return RunStatus.ERROR
    if workdir.is_done(stage_name):
        return RunStatus.DONE
    if stage_name in _threads and _threads[stage_name].is_alive():
        return RunStatus.RUNNING
    return RunStatus.IDLE
```

```python
# ui/pages/phase_3_slides.py (polling fragment)
import streamlit as st
from avideo.ui.bridge import run_stage, stage_status, RunStatus
from avideo.stages.slides_auto import SlidesAutoStage

@st.fragment(run_every="2s")
def _poll_slides_status(workdir, config):
    status = stage_status("slides", workdir)
    if status == RunStatus.RUNNING:
        st.spinner("Rendering slides...")
        st.progress(0.5, text="Playwright is rendering PNGs...")
    elif status == RunStatus.DONE:
        slides_out = workdir.read_checkpoint("slides", SlidesOutput)
        cols = st.columns(min(4, len(slides_out.png_paths)))
        for i, path in enumerate(slides_out.png_paths):
            cols[i % 4].image(path, use_column_width=True)
        st.rerun()  # exit fragment loop once done
    elif status == RunStatus.ERROR:
        st.error("Slide render failed.")
```

**Important:** The background thread MUST NOT call any `st.*` function. Write to `workdir/`, write to a `threading.Event` or a shared dict that the main thread polls. Use `add_script_run_ctx` only if absolutely necessary (internal Streamlit API, not officially supported).

### Pattern 3: Phase Wizard with Mandatory Human Gate

**What:** The UI has a linear phase progression stored in `st.session_state["phase"]` (integer 1–6). Each phase page renders its content and ends with an "Approve" button that advances the phase. Phases cannot be skipped forward. Navigation backwards is read-only (user can review but not re-run past phases without resetting).

**When to use:** Always — the wizard is the core UX promise of Studio Guiado.

**Trade-offs:** Linear flow is simple to reason about but the user cannot jump to Phase 4 without completing Phase 3. This is intentional (the pipeline has real dependencies: no voice without a script, no assembly without audio). For power users, the existing CLI remains the escape hatch.

```python
# ui/state.py
PHASES = [
    (1, "Contenido"),
    (2, "Guion + Slides"),
    (3, "Diapositivas"),
    (4, "Voz"),
    (5, "Extras"),
    (6, "Ensamblaje"),
]

def init_session_state():
    if "phase" not in st.session_state:
        st.session_state["phase"] = 1
    if "workdir_path" not in st.session_state:
        st.session_state["workdir_path"] = None  # set on first run
    if "run_config" not in st.session_state:
        st.session_state["run_config"] = {}     # dict of RunConfig kwargs

def advance_phase():
    if st.session_state["phase"] < 6:
        st.session_state["phase"] += 1
        st.rerun()
```

### Pattern 4: Interactive Edit / Variation Loop

**What:** For phases 2 (guion) and 3 (slides in auto mode), the user can: (a) edit text/parameters inline, (b) click "Regenerate variation" which clears the done marker for that stage and relaunches it via `PipelineBridge`, or (c) approve and proceed. Clearing the done marker causes the orchestrator (or the bridge's direct stage call) to treat the stage as not done and re-run it.

**When to use:** Phases 2 and 3 only.

**Implementation:** To request a variation:
1. Clear done marker: `(workdir.root / ".scriptwriter.done").unlink(missing_ok=True)`
2. Optionally clear JSON checkpoint: `(workdir.root / "script.json").unlink(missing_ok=True)` (forces re-generation even if checkpoint exists)
3. Call `bridge.run_stage(ScriptwriterStage(), workdir, config)`
4. Fragment polling detects RUNNING → shows spinner; detects DONE → shows new script

**For inline edits (not regeneration):** The user edits a `st.text_area`; on confirm, write the edited text back to the checkpoint JSON using `workdir.write_checkpoint("script", modified_script_model)` and touch the done marker. The downstream stages (slides, voice) remain valid; clear their done markers only if the user requests a full re-render.

### Pattern 5: New Backend Pieces — Integration Points

**What:** The three new backend features (OpenAI Audio, audio enhancement, background music) slot into the pipeline without disrupting the existing stage sequence.

#### OpenAI Audio (new VoiceMode)

- `VoiceMode.openai` added to the `VoiceMode` enum in `models/config.py`
- `VoiceStage.run()` dispatcher gains an `openai` branch (alongside `elevenlabs` and `record`)
- New `stages/voice_openai.py` implements `CheckpointMixin`, `stage_name="voice"`, calls `integrations/openai.py`, returns `UnifiedTimings` — identical output contract to `VoiceElevenlabsStage`
- New `integrations/openai.py` wraps `openai.audio.speech.create(model="tts-1-hd", ...)` — OpenAI Audio does not return character-level timestamps, so word timing must be extracted via a lightweight WhisperX align pass (same as `record` mode). This means `openai` mode shares the `align` stage path.
- `OPENAI_API_KEY` loaded via `load_dotenv()` already in `cli.py`; UI sets via env or `.env` file

#### Audio Enhancement (uploaded audio, pre-assembly)

- NOT a pipeline stage — implemented as `utils/audio_enhance.py: enhance_audio(input_path, output_path)`, a plain function that runs FFmpeg `arnndn` (denoising) + loudnorm pass
- Called by Phase 4 UI page on button press: reads uploaded audio, calls `enhance_audio`, writes enhanced file to `workdir/audio/slide_XX_enhanced.mp3`, updates the voice checkpoint to reference the enhanced paths
- Does NOT modify PIPELINE_STAGES

#### Background Music (user-supplied file, Phase 5)

- `AssembleStage.run()` gains an optional `music_path: Optional[Path]` read from `RunConfig` (new field `bg_music: Optional[Path]`)
- `integrations/ffmpeg.py` gains `build_music_mix_args(music_path, ducking_db, fade_out_s)` returning a filter_complex string for FFmpeg amix + sidechaincompress (ducking) + afade (fade out)
- UI Phase 5 page: `st.file_uploader("Background music", type=["mp3","wav"])` → saves to `workdir/bg_music.mp3` → sets `st.session_state["run_config"]["bg_music"]` → used when triggering assembly
- The stage remains in PIPELINE_STAGES at position 9 (assemble); no new stage needed

---

## Data Flow

### Streamlit ↔ workdir Data Flow

```
Browser (user action)
    │  widget interaction triggers Streamlit rerun
    ▼
app.py (st.navigation → loads current phase page)
    │  reads st.session_state["phase"], ["workdir_path"], ["run_config"]
    ▼
phase_N_xxx.py
    │  1. read checkpoints via WorkdirManager.read_checkpoint(name, Model)
    │  2. render data (st.text_area, st.image, st.video, etc.)
    │  3. on user action: call PipelineBridge.run_stage() or edit checkpoint
    │  4. on Approve: advance_phase() → st.rerun()
    ▼
PipelineBridge (bridge.py)
    │  launches threading.Thread (no Streamlit calls inside thread)
    ▼
Stage.run(workdir, config)
    │  reads upstream checkpoints from workdir/
    │  calls integrations (Anthropic, ElevenLabs, Playwright, FFmpeg)
    │  writes output checkpoint atomically (tmp→rename)
    │  touches .{stage}.done marker
    ▼
workdir/ (filesystem)
    │
    └── @st.fragment(run_every="2s") polls workdir.is_done(stage_name)
        → on DONE: re-read checkpoint, render results, stop polling
```

### Phase → Pipeline Stage Mapping

| UI Phase | Pipeline Stages Triggered | Human Gate | Approval Unlocks |
|----------|--------------------------|------------|-----------------|
| Phase 1 — Contenido | (bullet generation via direct Claude call — not an existing stage) | Approve bullets | Phase 2 |
| Phase 2 — Guion | storyboard → timing → scriptwriter | Approve script | Phase 3 |
| Phase 3 — Diapositivas | slides (dispatch: auto/hybrid/manual) + verify | Approve slides | Phase 4 |
| Phase 4 — Voz | voice (elevenlabs / openai / record) + align | Approve audio | Phase 5 |
| Phase 5 — Extras | subs + (music config — no stage trigger; injected into assemble config) | Approve config | Phase 6 |
| Phase 6 — Ensamblaje | assemble | Download/done | — |

**Note on Phase 1:** Bullet auto-generation is a lightweight Claude call invoked directly from the UI (not a pipeline stage). It does NOT write a checkpoint — it populates `st.session_state["bullets_yaml"]` (edited/approved in the UI), then writes `workdir/bullets.yaml` before triggering Phase 2. This keeps the pipeline contract intact (`bullets` is a Path in `RunConfig`).

### Checkpoint Read Map per Phase Page

```
Phase 1:  reads nothing from workdir (upstream of pipeline)
Phase 2:  reads storyboard.json, script.json (after generation)
Phase 3:  reads storyboard.json, script.json (for context); reads slides/ dir (thumbnails)
          reads verification_report.json (after verify, hybrid/manual)
Phase 4:  reads script.json (script display); reads voice.json (audio paths)
Phase 5:  reads voice.json (audio paths for preview); reads subs/ (preview subtitles)
Phase 6:  reads assembly.json (output path); reads workdir/output.mp4 for st.video
```

---

## Long-Running Execution Model

### Decision: Background Thread (not subprocess) for Stage Calls

Use `threading.Thread` to call stage logic directly, not `subprocess.run("avideo generate ...")`.

**Rationale:**
- Direct stage calls avoid the subprocess startup overhead and CLI argument serialization
- The bridge can import and call individual stages (`SlidesAutoStage().run(workdir, config)`), allowing UI-triggered re-runs of individual stages without re-running the full pipeline
- Thread safety is safe here because the pipeline is single-user (localhost, one session) and each stage only writes to its own checkpoint paths — no shared mutable state between concurrent stages
- The background thread reads/writes `workdir/` (filesystem), which is inherently thread-safe at the atomic-rename level already implemented in `WorkdirManager.write_checkpoint`

**Exception: Full pipeline run.** When the user clicks "Run full pipeline" or runs headless from Phase 1, use `subprocess.Popen(["avideo", "generate", "--level", "4", ...])` to invoke the existing CLI. This is the escape hatch for batch runs and avoids re-importing the entire stage chain in the Streamlit process.

### Polling Strategy

```
Stage starts     Stage running          Stage done
    │                  │                    │
PipelineBridge.run_stage()
    │
    └── threading.Thread(target=stage.run) → writes workdir/
                                                   │
                       @st.fragment(run_every="2s") polls is_done()
                       → shows spinner while RUNNING
                       → re-reads checkpoint + re-renders on DONE
                       → st.rerun() to exit fragment auto-rerun
```

The `run_every="2s"` fragment is the correct Streamlit primitive for polling background jobs (HIGH confidence — official docs: `automate-fragment-reruns`). It re-executes only the fragment subtree (not the full page), keeping UI responsive.

---

## Integration Points

### New External Services

| Service | Integration Pattern | Stage/Module | Notes |
|---------|---------------------|--------------|-------|
| OpenAI Audio API | `openai.audio.speech.create(model="tts-1-hd", voice=..., input=...)` → bytes | `integrations/openai.py` → `stages/voice_openai.py` | No character timestamps from OpenAI → requires WhisperX align pass (same as record mode); `OPENAI_API_KEY` in `.env` |
| FFmpeg arnndn (denoising) | `ffmpeg -i input -af arnndn=m=cb.rnnn output` | `utils/audio_enhance.py` | arnndn model file must be bundled or downloaded; alternatively use `anlmdn` (no model file needed) |
| FFmpeg amix + ducking | `amix=inputs=2[...];asidechain...` filter_complex | `integrations/ffmpeg.py: build_music_mix_args()` | Injected into assemble stage args when `bg_music` is set |
| Streamlit (UI framework) | `streamlit run src/avideo/ui/app.py` | `ui/` subtree | `streamlit>=1.40.0` for `st.fragment(run_every=...)` support |

### Internal Boundaries (v2.0.0 additions)

| Boundary | Communication | Notes |
|----------|---------------|-------|
| UI page → WorkdirManager | Direct instantiation with `st.session_state["workdir_path"]` | WorkdirManager is stateless and safe to instantiate per-rerun |
| UI page → PipelineBridge | `bridge.run_stage(stage_instance, workdir, config)` | Bridge holds thread dict in module-level state (persists across reruns) |
| PipelineBridge → Stage | Direct Python call: `stage.run(workdir, config)` | Thread-safe because each stage owns its own checkpoint paths |
| Phase page → assemble | Reads `st.session_state["run_config"]` to build `RunConfig` with `bg_music` | `RunConfig` is constructed fresh each time assemble is triggered |
| UI app → CLI (full run) | `subprocess.Popen(["avideo", "generate", "--level", "4", ...])` | Used only for "run all" headless mode; individual phases use direct stage calls |

---

## Build Order (v2.0.0 — dependency-aware)

All existing pipeline code (Layers 0–9 from v1.60.0) is complete and frozen. Build new components in this sequence:

```
Layer A — New backend integrations (independent of UI)
  1. models/config.py: add VoiceMode.openai + RunConfig.bg_music field
  2. integrations/openai.py: OpenAI Audio API wrapper
  3. stages/voice_openai.py: VoiceOpenAIStage (CheckpointMixin, stage_name="voice")
  4. stages/voice.py: add openai dispatch branch
  5. utils/audio_enhance.py: enhance_audio() (FFmpeg arnndn/anlmdn + loudnorm)
  6. integrations/ffmpeg.py: build_music_mix_args() + integrate into build_assemble_args
  7. stages/assemble.py: read config.bg_music, call music mix if set

Layer B — UI foundation (no page logic, just structure)
  8. ui/state.py: PHASES constant, init_session_state(), advance_phase()
  9. ui/bridge.py: PipelineBridge — run_stage(), stage_status(), error accessor
  10. ui/app.py: st.navigation with 6 pages; session_state init; workdir setup
      → Validates: can load app, navigate between empty phase pages

Layer C — Phase pages in pipeline order (each unblocks the next)
  11. ui/pages/phase_1_contenido.py
      - Topic + duration form
      - Bullet auto-gen (direct Anthropic call)
      - Approve → write workdir/bullets.yaml, advance to Phase 2
  12. ui/pages/phase_2_guion.py
      - Trigger storyboard → timing → scriptwriter via bridge (3 stages)
      - Poll done markers; show spinner per stage
      - Editable script text areas
      - Variation button (clear done marker + re-run)
      - Approve → advance_phase()
  13. ui/pages/phase_3_slides.py
      - Trigger slides dispatch + verify via bridge
      - Poll; show PNG thumbnails (st.image) per slide
      - For hybrid/manual: st.file_uploader for user slides
      - Variation button (clear slides done + re-run)
      - Approve → advance_phase()
  14. ui/pages/phase_4_voz.py
      - Voice provider selector (elevenlabs / openai / record)
      - Trigger voice + align stages via bridge
      - st.audio preview per slide
      - File uploader for own audio (sets audio paths directly)
      - Enhance button → utils/audio_enhance.py
      - Approve → advance_phase()
  15. ui/pages/phase_5_extras.py
      - Subtitles toggle (burn_subs flag)
      - Music file uploader → save to workdir/bg_music.mp3
      - Transition crossfade slider
      - All stored in session_state["run_config"]
      - Approve → advance_phase() (no stage triggered here)
  16. ui/pages/phase_6_ensamble.py
      - Trigger assemble stage via bridge
      - Poll; st.video(workdir/output.mp4) on DONE
      - st.download_button for output.mp4

Layer D — Polish + entry point
  17. pyproject.toml: add streamlit + openai to dependencies
      Add [project.scripts]: avideo-studio = "avideo.ui.app:main"
  18. Dockerfile: add streamlit; EXPOSE 8501; CMD streamlit run ...
  19. Tests: bridge unit tests (thread launch, done detection); phase page smoke tests
```

**Critical dependency note:** Layer A (backend) is fully independent of the UI and can be built and tested before any Streamlit code. Layer B (UI foundation) must be complete before any Layer C page. Within Layer C, pages must be built in phase order because each page is acceptance-tested by running the phase end-to-end.

---

## Anti-Patterns (v2.0.0 additions)

### Anti-Pattern 6: Storing Pipeline Artifacts in session_state

**What people do:** `st.session_state["script"] = ScriptOutput(...)` after a stage runs.

**Why it's wrong:** session_state is lost on browser close, tab refresh, or Streamlit crash. Artifacts stored here cannot be resumed. The existing checkpoint mechanism already solves this — duplicating it in session_state creates a divergence risk.

**Do this instead:** Always read from `workdir.read_checkpoint(name, Model)`. Store only UI-transient values (current phase, form inputs) in session_state.

### Anti-Pattern 7: Calling Streamlit APIs from the Background Thread

**What people do:** `st.session_state["status"] = "done"` inside the thread function.

**Why it's wrong:** Streamlit session_state is not thread-safe. Writing to it from a background thread causes race conditions and undefined behavior (undocumented internal locking). The `add_script_run_ctx` workaround is an internal API and may break across Streamlit versions.

**Do this instead:** The background thread writes only to `workdir/` (via WorkdirManager). The main script thread reads `workdir/` via the polling fragment. No Streamlit API is ever called inside a thread.

### Anti-Pattern 8: Running the Full Pipeline for Single-Stage Variations

**What people do:** On "Regenerate script variation", call `subprocess.run(["avideo", "generate", ...])` which re-runs all stages from the beginning.

**Why it's wrong:** The full pipeline re-runs context ingestion, storyboard, timing, AND scriptwriter when only scriptwriter needs to re-run. This wastes API credits and is slow.

**Do this instead:** Use `PipelineBridge.run_stage(ScriptwriterStage(), ...)` directly. The orchestrator's done-marker logic means only stages without a done marker re-run. For interactive variations, clear only the target stage's done marker and checkpoint, then call the stage directly.

### Anti-Pattern 9: Using st.cache_data for Pipeline Checkpoints

**What people do:** `@st.cache_data def load_script(): return workdir.read_checkpoint(...)` to avoid re-reading on every rerun.

**Why it's wrong:** `st.cache_data` caches across sessions and across runs. After a variation re-generates the script, the cache still returns the old version. Cache invalidation requires explicit `st.cache_data.clear()`, which is easy to forget and hard to debug.

**Do this instead:** Read checkpoints directly each rerun. JSON reads are <1ms and do not benefit from caching. The background thread + done-marker polling already prevents redundant stage execution.

### Anti-Pattern 10: Blocking the Main Thread with Long Stage Calls

**What people do:** Call `SlidesAutoStage().run(workdir, config)` synchronously in the page's render function.

**Why it's wrong:** Streamlit renders by re-running the page script. A 30-second Playwright render in the main thread freezes the entire UI, prevents the user from interacting, and causes the browser to show a spinning indicator with no feedback.

**Do this instead:** Always use `PipelineBridge.run_stage()` for stages that take more than 2 seconds. Show `st.spinner()` or a `@st.fragment(run_every="2s")` progress poll while the thread runs.

---

## Scaling Considerations

This is a local, single-user tool (localhost, one Streamlit session). Concurrency and scaling are irrelevant. The relevant concerns are:

| Concern | Approach |
|---------|----------|
| Streamlit rerun frequency (every widget interaction) | Keep page render code cheap: only read checkpoints + display; no computation in main render path |
| Thread lifecycle management | Bridge tracks threads in module-level dict; daemon=True so threads die with the process |
| Workdir state across sessions | `workdir/` persists on disk; UI re-hydrates from checkpoints on page load |
| Multiple runs (different projects) | Each `Run` gets its own timestamped workdir; session_state["workdir_path"] points to the current one |

---

## Sources

- Streamlit session_state (HIGH confidence): https://docs.streamlit.io/develop/api-reference/caching-and-state
- Streamlit threading patterns (HIGH confidence): https://docs.streamlit.io/develop/concepts/app-design/multithreading
- `@st.fragment(run_every=...)` for background polling (HIGH confidence): https://docs.streamlit.io/develop/concepts/architecture/fragments
- `st.video()` for MP4 preview (HIGH confidence): https://docs.streamlit.io/develop/api-reference/media/video
- `st.image()` for PNG thumbnails (HIGH confidence): https://docs.streamlit.io/develop/api-reference/media/image
- OpenAI Audio API (MEDIUM confidence — training data; no character timestamps): https://platform.openai.com/docs/api-reference/audio/createSpeech
- FFmpeg arnndn filter (MEDIUM confidence): https://ffmpeg.org/ffmpeg-filters.html#arnndn
- FFmpeg amix + sidechaincompress for ducking (MEDIUM confidence): https://trac.ffmpeg.org/wiki/AudioChannelManipulation
- Existing architecture (HIGH confidence — source code): src/avideo/orchestrator.py, stages/base.py, utils/workdir.py

---

*Architecture research for: auto-video-narrado v2.0.0 — Streamlit UI + pipeline integration*
*Researched: 2026-05-29*
