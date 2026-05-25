# Architecture Research

**Domain:** Sequential CLI pipeline with resumable checkpoints, typed I/O, own orchestrator — Python 3.11+
**Researched:** 2026-05-25
**Confidence:** HIGH

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                          CLI Layer (typer)                            │
│  generate --bullets --duration --voice --slides-mode --level         │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │ RunConfig (pydantic)
┌────────────────────────────────▼─────────────────────────────────────┐
│                       Orchestrator (sequential)                       │
│                                                                       │
│  for stage in PIPELINE:                                               │
│    if stage.is_done(workdir):  continue   ← idempotency              │
│    if stage.needs_approval(level): pause  ← human-in-the-loop        │
│    output = stage.run(input_model, workdir)                           │
│    stage.mark_done(workdir, output)                                   │
└──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬─────────────┘
       │      │      │      │      │      │      │      │
┌──────▼─┐ ┌──▼───┐ ┌▼───┐ ┌▼────┐ ┌▼───┐ ┌▼────▼┐ ┌▼────┐ ┌▼────────┐
│context │ │story │ │tim │ │scri │ │sli │ │verify│ │voice│ │align/  │
│ingest  │ │board │ │ing │ │ptwr │ │des │ │(vis) │ │TTS/ │ │subs/   │
│        │ │      │ │    │ │iter │ │    │ │      │ │rec  │ │assemble│
└────────┘ └──────┘ └────┘ └─────┘ └────┘ └──────┘ └─────┘ └────────┘
       │      │      │      │      │      │      │      │
┌──────▼──────▼──────▼──────▼──────▼──────▼──────▼──────▼─────────────┐
│                         workdir/ (state layer)                        │
│                                                                       │
│  JSON checkpoints         Artifact files       Done markers           │
│  context.json             design_proposal/     .context.done          │
│  storyboard.json          slides/              .storyboard.done       │
│  script.json              slides_user/         .timing.done           │
│  verification_report.json audio/               .script.done           │
│  timings.json             subs/                .slides.done           │
│                           output.mp4            ...                   │
└──────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Communicates With |
|-----------|----------------|-------------------|
| CLI (`cli.py`) | Parse args, build `RunConfig`, call orchestrator | Orchestrator |
| Orchestrator (`orchestrator.py`) | Drive stage sequence, checkpoint checks, approval gates | All stages, workdir |
| Stage base (`stages/base.py`) | `StageProtocol`: `run()`, `is_done()`, `mark_done()` | Orchestrator |
| context (`stages/context.py`) | Ingest `.pptx`/`.pdf`/`.md`, extract text → `ContextOutput` | Orchestrator |
| storyboard (`stages/storyboard.py`) | Claude API → slide list → `StoryboardOutput` | Anthropic SDK |
| timing (`stages/timing.py`) | WPM math, duration budgets → `TimingOutput` | Pure logic |
| scriptwriter (`stages/scriptwriter.py`) | Claude API → per-slide narration → `ScriptOutput` | Anthropic SDK |
| slides_auto (`stages/slides_auto.py`) | Jinja2 + theme.yaml → HTML → Playwright → PNG | Playwright sync |
| slides_hybrid (`stages/slides_hybrid.py`) | Design proposal JSON, waits for user PNG upload | Orchestrator (pause) |
| slides_manual (`stages/slides_manual.py`) | Validates user-provided PNGs exist → passthrough | Filesystem |
| verify_slides (`stages/verify_slides.py`) | Claude vision → per-slide verdict → `VerificationReport` | Anthropic SDK |
| voice_elevenlabs (`stages/voice_elevenlabs.py`) | ElevenLabs `convert_with_timestamps` → WAV + char timings | ElevenLabs SDK |
| voice_record (`stages/voice_record.py`) | Export segmented script; ingest `slide_XX.wav` files | Filesystem |
| align (`stages/align.py`) | WhisperX forced-align → word-level timings (record only) | WhisperX (sync) |
| subtitles (`stages/subtitles.py`) | Timings → `.srt` + `.vtt` files | Pure logic |
| assemble (`stages/assemble.py`) | FFmpeg subprocess → final MP4 | FFmpeg subprocess |
| qa (`stages/qa.py`) | FFmpeg `loudnorm` + duration check → QA report | FFmpeg subprocess |

---

## Recommended Project Structure

```
auto-video-narrado/
├── pyproject.toml              # uv-managed, entry point: avideo
├── Dockerfile
├── config.yaml                 # default voice_id, WPM, theme path, etc.
├── src/
│   └── avideo/
│       ├── __init__.py
│       ├── cli.py              # typer app, RunConfig validation
│       ├── orchestrator.py     # sequential loop, checkpoint/approval logic
│       ├── models/             # all pydantic I/O contracts
│       │   ├── __init__.py
│       │   ├── config.py       # RunConfig (from CLI args + config.yaml)
│       │   ├── context.py      # ContextOutput
│       │   ├── storyboard.py   # StoryboardOutput, SlideSpec
│       │   ├── timing.py       # TimingOutput, SlideTiming
│       │   ├── script.py       # ScriptOutput, SlideScript
│       │   ├── slides.py       # SlidesOutput (paths to PNGs)
│       │   ├── verification.py # VerificationReport, SlideVerdict
│       │   ├── voice.py        # VoiceOutput, CharAlignment
│       │   └── assembly.py     # AssemblyOutput, QAReport
│       ├── stages/
│       │   ├── __init__.py
│       │   ├── base.py         # StageProtocol (typing.Protocol), CheckpointMixin
│       │   ├── context.py
│       │   ├── storyboard.py
│       │   ├── timing.py
│       │   ├── scriptwriter.py
│       │   ├── slides_auto.py
│       │   ├── slides_hybrid.py
│       │   ├── slides_manual.py
│       │   ├── verify_slides.py
│       │   ├── voice_elevenlabs.py
│       │   ├── voice_record.py
│       │   ├── align.py
│       │   ├── subtitles.py
│       │   ├── assemble.py
│       │   └── qa.py
│       ├── integrations/       # thin wrappers around external APIs/tools
│       │   ├── __init__.py
│       │   ├── anthropic.py    # Claude client (text + vision)
│       │   ├── elevenlabs.py   # TTS + timestamps client
│       │   ├── playwright.py   # sync_playwright wrapper, html→png
│       │   ├── whisperx.py     # load model + align wrapper
│       │   └── ffmpeg.py       # subprocess wrapper, builder pattern
│       ├── templates/
│       │   ├── slide_base.html.j2
│       │   └── theme.yaml
│       └── utils/
│           ├── workdir.py      # WorkdirManager: paths, done markers, JSON r/w
│           ├── rich_ui.py      # Rich console helpers, progress, approval prompts
│           └── cost_estimator.py  # --dry-run token/cost estimation
└── tests/
    ├── test_storyboard.py      # mocked Anthropic
    ├── test_timing.py
    └── test_slides_render.py   # single slide smoke test
```

### Structure Rationale

- **`models/`:** All Pydantic models live here, separated from stage logic. Stages import from `models/`; this prevents circular imports and makes contracts inspectable independently.
- **`stages/`:** One file per pipeline stage. Each is self-contained: knows how to run itself, check if already done, and write its checkpoint. The orchestrator does not contain business logic.
- **`integrations/`:** Thin adapters over external libraries (Playwright, FFmpeg, WhisperX, Anthropic, ElevenLabs). Stages call integrations, not SDKs directly. This isolates all subprocess/async boundaries to one layer, making mocking in tests trivial.
- **`utils/workdir.py`:** Single authority for all filesystem paths. Stages call `workdir.slides_dir()`, never build paths manually.

---

## Architectural Patterns

### Pattern 1: StageProtocol + CheckpointMixin

**What:** Every stage implements a `typing.Protocol` that enforces a uniform `run(input, workdir)` interface and a `CheckpointMixin` that manages the `.{stage}.done` marker file and JSON deserialization.

**When to use:** Always — the entire pipeline consistency depends on this contract.

**Trade-offs:** `typing.Protocol` (structural subtyping) is preferred over ABC here because stages are independent files loaded by name, and Protocol avoids the diamond-inheritance fragility of mixing ABC with Pydantic models.

```python
# stages/base.py
from typing import Protocol, runtime_checkable
from pathlib import Path
from pydantic import BaseModel

class WorkdirManager:
    def __init__(self, root: Path): self.root = root
    def done_marker(self, stage: str) -> Path:
        return self.root / f".{stage}.done"
    def is_done(self, stage: str) -> bool:
        return self.done_marker(stage).exists()
    def mark_done(self, stage: str, output: BaseModel) -> None:
        self.done_marker(stage).touch()

@runtime_checkable
class StageProtocol(Protocol):
    stage_name: str
    def run(self, workdir: WorkdirManager) -> BaseModel: ...
    def is_done(self, workdir: WorkdirManager) -> bool: ...
```

### Pattern 2: JSON Checkpoint Files as the Contract Surface

**What:** Each stage reads its input exclusively from JSON files in `workdir/` (loaded via `Model.model_validate_json(path.read_text())`), writes its output to a JSON file, then touches the `.done` marker. The orchestrator never passes Python objects between stages — only `WorkdirManager` is threaded through.

**When to use:** Always. This enables resuming mid-pipeline without re-running upstream stages, and makes each stage independently testable with fixture JSON files.

**Trade-offs:** Slight overhead of JSON serialization for in-process data. Acceptable because stages are coarse-grained (the expensive work is API calls and Playwright/FFmpeg, not serialization).

```python
# Pattern: stage reads previous stage's JSON output
class ScriptwriterStage:
    stage_name = "script"
    def run(self, workdir: WorkdirManager) -> ScriptOutput:
        storyboard = StoryboardOutput.model_validate_json(
            (workdir.root / "storyboard.json").read_text()
        )
        timing = TimingOutput.model_validate_json(
            (workdir.root / "timings.json").read_text()
        )
        # ... call Claude, produce ScriptOutput
        output = ScriptOutput(slides=[...])
        (workdir.root / "script.json").write_text(output.model_dump_json(indent=2))
        return output
```

### Pattern 3: Approval Gate by Level (L1–L4)

**What:** The orchestrator holds a mapping of `(stage_name, approval_event) → minimum_level_required`. Before calling `stage.run()`, it checks whether the configured `--level` is below the threshold. If so, it calls `rich_ui.pause_for_approval(stage_name)` and waits for stdin.

**When to use:** Applied by the orchestrator — stages are unaware of levels. Stages are pure logic; the orchestrator decides whether to pause.

**Trade-offs:** Clean separation: stages don't carry approval logic, which means they can be called programmatically in tests without triggering interactive prompts.

```python
# orchestrator.py (simplified)
APPROVAL_THRESHOLDS: dict[str, int] = {
    "after_storyboard":         2,  # L1, L2 pause; L3, L4 skip
    "after_design_proposal":    1,  # all levels pause (hybrid/manual)
    "after_verify_slides_fail": 2,  # L1, L2 always pause on fail
    "after_verify_slides_ok":   4,  # only L4 never pauses even on ok
}

def should_pause(event: str, level: int) -> bool:
    return level <= APPROVAL_THRESHOLDS.get(event, 0)
```

**Level semantics:**
- L1: pause after every stage (fully supervised)
- L2: pause after storyboard, design proposal, verify (supervised creative steps)
- L3: auto-continue if `verify_slides` all `ok`; pause on any `fail`
- L4: fully automatic — no pauses

### Pattern 4: Data/Artifact Boundary

**What:** There are two kinds of stage outputs. JSON outputs (data) are Pydantic models written to `workdir/*.json`. Artifact outputs (binary) are files written to `workdir/slides/`, `workdir/audio/`, `workdir/subs/`, `workdir/output.mp4`. The done marker signals that the artifact directory is complete and stable.

**When to use:** The distinction matters for idempotency checks: a stage is "done" when its done marker exists, regardless of whether you can reconstruct the Python model. For artifact stages (slides, audio, assemble), the done marker additionally implies the artifact directory is complete.

```
Data checkpoints (JSON, re-parseable):
  workdir/context.json          → ContextOutput
  workdir/storyboard.json       → StoryboardOutput
  workdir/timings.json          → TimingOutput
  workdir/script.json           → ScriptOutput
  workdir/verification_report.json → VerificationReport

Artifact directories (binary, not re-parseable):
  workdir/design_proposal/      → slide_XX.json design specs
  workdir/slides/ (auto)        → slide_01.png … slide_N.png
  workdir/slides_user/          → user-provided PNGs (hybrid/manual)
  workdir/audio/                → slide_01.wav … slide_N.wav
  workdir/subs/                 → output.srt, output.vtt
  workdir/output.mp4            → final video
```

### Pattern 5: Integration Adapters (subprocess + sync wrappers)

**What:** All external I/O lives in `integrations/`. The rest of the codebase never directly calls `subprocess.run`, `sync_playwright`, or `whisperx.load_model`. This isolates side effects, makes testing via mocks trivial, and ensures consistent error handling.

**When to use:** Always — especially important for FFmpeg and Playwright which are subprocess/sync-heavy and fail in opaque ways.

---

## Data Flow

### Pipeline Data Flow (sequential, checkpoint-gated)

```
CLI args + config.yaml
    │
    ▼  RunConfig (pydantic)
Orchestrator
    │
    ├─► [context] → context.json (ContextOutput)
    │
    ├─► [storyboard] ← context.json → storyboard.json (StoryboardOutput)
    │       Claude API (text)
    │
    ├─► [timing] ← storyboard.json → timings.json (TimingOutput)
    │       Pure math (WPM × word_count)
    │
    ├─► [scriptwriter] ← storyboard.json + timings.json → script.json (ScriptOutput)
    │       Claude API (text)
    │
    ├─► [slides] ← script.json + storyboard.json + theme.yaml
    │   ├── auto:   Jinja2 → HTML → Playwright sync → PNG → workdir/slides/
    │   ├── hybrid: Claude → design_proposal/ → [PAUSE: user uploads PNGs]
    │   │           → workdir/slides_user/
    │   └── manual: validate workdir/slides_user/ exists and is complete
    │
    ├─► [verify_slides] ← script.json + slides/ → verification_report.json
    │       Claude vision API  (hybrid/manual only)
    │       [PAUSE on fail if level ≤ 2]
    │
    ├─► [voice]
    │   ├── elevenlabs: script.json → ElevenLabs API → audio/ + char timings
    │   └── record:     export script segments → [PAUSE: user records] → audio/
    │
    ├─► [align] ← audio/ + script.json → word-level timings (record mode only)
    │       WhisperX (synchronous, CPU/GPU)
    │
    ├─► [subtitles] ← timings.json OR align output → subs/output.srt + .vtt
    │       Pure string formatting
    │
    ├─► [assemble] ← slides/ + audio/ + subs/ → output.mp4
    │       FFmpeg subprocess (filter_complex concat + subtitles burn optional)
    │
    └─► [qa] ← output.mp4 → qa_report.json
            FFmpeg ffprobe + loudnorm analysis
```

### Timing Source per Voice Mode

```
voice=elevenlabs  →  ElevenLabs character timestamps → subtitles (no WhisperX)
voice=record      →  WhisperX forced alignment        → subtitles
```

### Key Data Flows

1. **Storyboard → everything downstream:** `StoryboardOutput.slides` is the master list of slides. All subsequent stages iterate over it; the count drives timing math, script length, slide filenames (`slide_01.png`, etc.).
2. **Timing → script calibration:** `SlideTiming.word_budget` (= duration_s × WPM / 60) is injected into the scriptwriter prompt so Claude targets the correct length per slide.
3. **Design proposal → slides_hybrid:** `design_proposal/slide_XX.json` is a structured Claude output (color palette, layout, icon names, text blocks) that the user reads to produce PNGs. It is data (JSON), not an artifact.
4. **Verification report → orchestrator decision:** `SlideVerdict.status ∈ {ok, warning, fail}` drives the L1–L4 gate logic. The orchestrator checks `any(v.status == "fail")` before deciding to pause.
5. **Char timings → subtitles:** ElevenLabs returns character-level start/end arrays. The subtitles stage groups them into word/phrase segments and writes SRT/VTT.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Anthropic Claude | Synchronous SDK (`anthropic.Anthropic().messages.create`); vision via `image` content block with base64 PNG | Always wrap in retry with exponential backoff; handle `RateLimitError`. Use `model_dump_json()` on response to log for debugging. |
| ElevenLabs TTS | Synchronous SDK (`client.text_to_speech.convert_with_timestamps`); returns `audio_base64` + `alignment.characters` arrays | Decode base64 and write WAV directly. `output_format=pcm_44100` avoids re-encoding before FFmpeg. |
| Playwright (HTML→PNG) | `sync_playwright()` context manager; launch Chromium, `page.goto(html_file_uri)`, `page.screenshot(path=, full_page=False, clip={w:1920, h:1080})` | Use `sync_playwright` (not async) because slides stage is called from synchronous orchestrator. One browser instance per pipeline run (reuse across slides). Do NOT use `async_playwright` in subprocess/thread — causes event loop conflicts. |
| WhisperX | Synchronous function calls (`whisperx.load_model`, `whisperx.align`); synchronous only — no async API | Heavy GPU/CPU load. Call from main thread. Only invoked in `record` mode. Load model once per pipeline run (cache in stage state). |
| FFmpeg | `subprocess.run(["ffmpeg", ...], capture_output=True, check=True)` with `CalledProcessError` handling | Build command as list (never shell=True). Wrap in `integrations/ffmpeg.py` with a fluent builder. Always capture stderr for error messages. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| CLI → Orchestrator | `RunConfig` Pydantic model | All user-specified options coerced and validated at this boundary |
| Orchestrator → Stage | `WorkdirManager` passed by reference; stage reads/writes its own JSON | Orchestrator does not pass Python models between stages |
| Stage → Model | `Model.model_validate_json(path.read_text())` for input; `path.write_text(output.model_dump_json())` for output | Pydantic is the only serialization mechanism |
| Stage → Integration | Direct function call (no queue/bus) | Integrations raise typed exceptions; stages catch and re-raise with context |
| Orchestrator → Rich UI | `rich_ui.pause_for_approval(stage, report)` → blocks on `input()` | Isolated in `utils/rich_ui.py`; mockable in tests via monkeypatching |

---

## Scaling Considerations

This is a single-user, single-run CLI tool. Scaling questions are irrelevant. The relevant concurrency considerations are:

| Concern | Approach |
|---------|----------|
| Playwright blocking orchestrator | Use sync API; one browser instance reused across all slides. No threading needed. |
| WhisperX memory (GPU/CPU) | Load model once (lazy-init on first `align` call); release after stage completes. |
| ElevenLabs per-slide API calls | Call sequentially per slide; SDK is synchronous. Batch is not supported by the timestamps endpoint. |
| FFmpeg large video | FFmpeg runs in subprocess — no blocking concern; `check=True` gives clean errors. |
| Claude API rate limits | Exponential backoff in `integrations/anthropic.py`; `tenacity` library is appropriate here. |

---

## Construction Order (Build Dependencies)

Build in this sequence — each layer unblocks the next:

```
Layer 0 — Foundation (no dependencies)
  1. models/           — All Pydantic I/O contracts (no external deps)
  2. utils/workdir.py  — WorkdirManager (Path operations only)
  3. stages/base.py    — StageProtocol, done-marker logic

Layer 1 — Pure logic stages (depend only on models + workdir)
  4. stages/timing.py  — Pure math, no external calls
  5. stages/subtitles.py — Pure string formatting (SRT/VTT generation)

Layer 2 — Orchestrator skeleton (enables integration testing of stages)
  6. cli.py + orchestrator.py  — RunConfig, stage loop, checkpoint checks, approval gates
     (start with stubs for all stages → wire real stages as they are built)

Layer 3 — LLM stages (depend on Anthropic SDK)
  7. integrations/anthropic.py
  8. stages/storyboard.py
  9. stages/scriptwriter.py

Layer 4 — Slides (depends on storyboard + script + Playwright)
  10. integrations/playwright.py   — sync_playwright html→png wrapper
  11. stages/slides_auto.py        — Jinja2 + theme.yaml + playwright
  12. stages/slides_hybrid.py      — Design proposal generation + approval pause
  13. stages/slides_manual.py      — PNG validation passthrough

Layer 5 — Verification (depends on slides + Claude vision)
  14. stages/verify_slides.py      — rasterize slides, Claude vision batch call

Layer 6 — Audio (depends on script + ElevenLabs)
  15. integrations/elevenlabs.py   — TTS + timestamps wrapper
  16. stages/voice_elevenlabs.py
  17. stages/voice_record.py       — Export + ingest pattern

Layer 7 — Alignment (depends on audio, record mode only)
  18. integrations/whisperx.py     — load_model + align wrapper
  19. stages/align.py

Layer 8 — Assembly (depends on slides + audio + subtitles + FFmpeg)
  20. integrations/ffmpeg.py       — subprocess builder
  21. stages/assemble.py
  22. stages/qa.py

Layer 9 — Polish
  23. utils/rich_ui.py             — Progress, approval prompts, QA report display
  24. utils/cost_estimator.py      — --dry-run token/cost estimation
  25. context stage (optional ingestor: PyMuPDF, python-pptx)
```

**Critical dependency note:** The orchestrator skeleton (Layer 2) should be built before any external-dependency stage. This lets you wire stages in with stubs and run the pipeline end-to-end (with mocked outputs) from day one, which validates the checkpoint/resumption logic before any real API calls.

---

## Anti-Patterns

### Anti-Pattern 1: Passing Python Objects Between Stages

**What people do:** Orchestrator holds stage outputs in memory and passes them as arguments to the next stage.

**Why it's wrong:** Breaks resumption — if the process crashes, the in-memory state is gone. Also makes each stage depend on the orchestrator's calling convention rather than the filesystem contract.

**Do this instead:** Each stage reads its inputs from `workdir/*.json` and writes its output to `workdir/*.json`. The orchestrator only calls `stage.run(workdir)`.

### Anti-Pattern 2: `async_playwright` in a Sync Orchestrator

**What people do:** Use `async_playwright` for slides generation because it "feels more modern," which requires wrapping in `asyncio.run()`.

**Why it's wrong:** `asyncio.run()` creates a new event loop each call. If WhisperX or ElevenLabs integrations also try to use async internally, event loop conflicts arise. Known Playwright issue: `async_playwright` context manager hangs on exit when process pools are involved.

**Do this instead:** Use `sync_playwright()` with a `with` block. Playwright's sync API is fully supported and avoids all event loop management. Keep one browser instance open for the duration of the slides stage.

### Anti-Pattern 3: Shell=True for FFmpeg

**What people do:** `subprocess.run(f"ffmpeg -i {input} -o {output}", shell=True)`.

**Why it's wrong:** Path injection risk if any filename comes from user input. Also makes argument quoting error-prone and hard to test.

**Do this instead:** Always pass a list: `subprocess.run(["ffmpeg", "-i", str(input_path), str(output_path)], check=True, capture_output=True)`. Build complex FFmpeg filter graphs programmatically in `integrations/ffmpeg.py`.

### Anti-Pattern 4: Done Marker as a Lock (Not a Receipt)

**What people do:** Check the done marker before AND after stage execution, treating it as a mutex.

**Why it's wrong:** Done markers are idempotency receipts, not locks. This pipeline is single-process; no locking is needed. Treating them as locks adds complexity and can mask partial failure (e.g., JSON written but PNG missing).

**Do this instead:** Mark done only after ALL outputs (JSON + artifacts) are confirmed written. If a stage fails mid-way, the done marker is never written, so the next run retries the full stage. For artifact-heavy stages (slides, audio), use a temp directory and atomic rename.

### Anti-Pattern 5: Embedding Approval Logic in Stages

**What people do:** Stage code calls `rich.prompt.Confirm.ask("Continue?")` inside `stage.run()`.

**Why it's wrong:** Stages become untestable in automated contexts. Level behavior is scattered across files.

**Do this instead:** Stages are pure logic — they never prompt. The orchestrator is the only place that calls `rich_ui.pause_for_approval()`, keyed on the level and the stage name.

---

## Sources

- Pydantic model serialization (HIGH confidence): https://docs.pydantic.dev/latest/concepts/serialization/
- ElevenLabs `convert_with_timestamps` API (HIGH confidence): https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps
- Playwright Python sync vs async (HIGH confidence): https://playwright.dev/python/docs/library
- Playwright async context manager known issue: https://github.com/microsoft/playwright-python/issues/1074
- WhisperX Python API (HIGH confidence — official README): https://github.com/m-bain/whisperX
- Python checkpoint patterns (MEDIUM confidence): https://github.com/a-rahimi/python-checkpointing
- Idempotent pipeline patterns (MEDIUM confidence): https://www.prefect.io/blog/the-importance-of-idempotent-data-pipelines-for-resilience
- Python Protocol vs ABC (HIGH confidence): https://peps.python.org/pep-0544/
- FFmpeg subprocess Python best practices (MEDIUM confidence): https://www.gumlet.com/learn/ffmpeg-python/

---

*Architecture research for: auto-video-narrado — sequential CLI pipeline with checkpoints*
*Researched: 2026-05-25*
