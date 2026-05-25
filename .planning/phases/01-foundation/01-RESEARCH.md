# Phase 1: Foundation - Research

**Researched:** 2026-05-25
**Domain:** Python CLI skeleton — Pydantic models, Typer CLI, sequential orchestrator with resumable checkpoints, Rich UI
**Confidence:** HIGH

---

## Summary

Phase 1 delivers the fully executable end-to-end skeleton of the pipeline. No real content is generated (no LLM, no TTS, no Playwright, no FFmpeg) — all stages are stubs that write minimal valid Pydantic-serialized checkpoints. The phase establishes: (1) all Pydantic I/O contracts as the language boundary between stages, (2) WorkdirManager as the single authority for filesystem paths and done-markers, (3) the Typer CLI with all final flags already declared, (4) the sequential orchestrator that reads done-markers and approval levels before calling each stage.

The three plans map cleanly to build dependencies: models + workdir first (no external deps), then CLI (depends on models), then orchestrator (depends on CLI + models + workdir). This order ensures the orchestrator can be wired with stubs and tested end-to-end before any real API integration arrives in Phase 2.

The key technical risks in this phase are: (a) correct config-merge precedence (CLI flag > config.yaml > Pydantic default) using `pydantic-settings` with `YamlConfigSettingsSource`; (b) correct atomic checkpoint writes (tmp → rename) to prevent partial-state corruption on interrupt; (c) keeping approval-gate logic entirely in the orchestrator (stages must remain pure/promptless).

**Primary recommendation:** Use `pydantic-settings` `YamlConfigSettingsSource` + `settings_customise_sources` for config merge. `typing.Protocol` for `StageProtocol`. Atomic writes via `Path.write_text(tmp); tmp.rename(target)` on same filesystem. Trap `KeyboardInterrupt` in the orchestrator main loop, not in stages.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Orchestrator, checkpoints & levels:**
- Cada etapa stub escribe un checkpoint mínimo válido conforme a su contrato Pydantic de salida, de modo que el pipeline corre de extremo a extremo y pasa datos reales entre etapas.
- Reanudación/idempotencia mediante marcador `.done` por etapa + escritura atómica `tmp→rename`; re-ejecutar salta las etapas ya completas.
- Semántica de niveles: L1 = pausa tras cada etapa · L2 = pausa en checkpoints creativos (storyboard / script / slides / verify) · L3 = pausa solo ante warning/fail · L4 = nunca pausa (totalmente autónomo).
- Interfaz de etapa: `StageProtocol` (run/checkpoint) + `CheckpointMixin` (decisión registrada en STATE.md).

**CLI & config:**
- Precedencia de configuración: flag CLI > `config.yaml` > default Pydantic.
- `--dry-run`: tabla Rich con tokens y coste estimados por etapa + total; no genera audio ni vídeo.
- Errores de validación Pydantic: capturados y mostrados como mensaje Rich claro (campo + razón), no traceback crudo.
- Logging con handler Rich; `--verbose` para debug; progreso por etapa.

**Models & workdir layout:**
- `RunConfig` + contratos I/O tipados por etapa en `models.py`.
- Layout de workdir: JSON nombrado por etapa (`storyboard.json`, `timings.json`, `script.json`) + subdirectorios `slides/ audio/ subs/`; salida final `output.mp4`.
- Formato de checkpoint: `model_dump_json()` (Pydantic v2).
- App Typer con subcomando `generate` (deja sitio para más subcomandos en el futuro).

### Claude's Discretion

None specified — all implementation decisions in this phase were decided in the discussion.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CLI-01 | El usuario puede ejecutar `generate` con `--bullets` y `--duration` y obtener un vídeo MP4 final | Typer `@app.command()` with `Annotated[Path, typer.Option()]` for `--bullets` and `int` for `--duration`. Stubs write `output.mp4` marker. |
| CLI-02 | El usuario puede elegir la fuente de voz con `--voice {elevenlabs\|record}` | Typer `Enum` option (`VoiceMode = Enum('VoiceMode', ['elevenlabs', 'record'])`); stored in `RunConfig.voice`. |
| CLI-03 | El usuario puede elegir el modo de slides con `--slides-mode {auto\|hybrid\|manual}` | Typer `Enum` option (`SlidesMode`); stored in `RunConfig.slides_mode`. |
| CLI-04 | El usuario puede elegir el nivel de automatización con `--level {1..4}` | Typer `int` option with `min=1, max=4` via `typer.Option(min=1, max=4)`; stored in `RunConfig.level`. |
| CLI-05 | El usuario puede aportar un documento de contexto opcional con `--context` | `Optional[Path]` option; stage stub skips if `None`. |
| CLI-06 | El usuario puede ejecutar `--dry-run` para estimar tokens/coste sin generar audio/vídeo | `bool` flag in `RunConfig`; orchestrator checks `run_config.dry_run` before each stage. |
| CLI-07 | La configuración por defecto se lee de `config.yaml` y los flags de CLI la sobreescriben | `pydantic-settings` `YamlConfigSettingsSource` with `settings_customise_sources` priority: init > YAML > env. |
| CLI-08 | El progreso y los logs se muestran de forma legible con `rich` | `rich.console.Console`, `rich.progress.Progress`, Rich `logging.Handler` for `--verbose`; error formatting via `rich.table.Table`. |
| ORCH-01 | El pipeline ejecuta todas las etapas en orden de forma secuencial | `for stage in PIPELINE_STAGES: stage.run(workdir)` loop in `orchestrator.py`. |
| ORCH-02 | Cada etapa guarda su checkpoint en `./workdir/` y el pipeline puede reanudarse | Done-marker `.{stage}.done` checked at loop start; workdir JSON persists across runs. |
| ORCH-03 | Re-ejecutar una etapa ya completada no duplica trabajo (idempotencia, escritura atómica) | `workdir.is_done(stage_name)` check; `tmp_path.rename(target_path)` atomic write pattern. |
| ORCH-04 | Los niveles L1–L4 controlan en qué puntos el pipeline se pausa | `APPROVAL_THRESHOLDS` dict in orchestrator; `should_pause(event, level)` function; `rich_ui.pause_for_approval()` in utils. |
| ORCH-05 | La E/S entre etapas está tipada y validada con `pydantic` | Each stage reads from `SomeModel.model_validate_json(path.read_text())`; writes `path.write_text(output.model_dump_json())`. |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| CLI argument parsing, validation | CLI Layer (`cli.py`) | — | Typer owns all flag definitions; Pydantic validates the assembled RunConfig |
| Config file loading (config.yaml) | CLI Layer (`cli.py`) | `pydantic-settings` | Config merge happens at RunConfig construction, before orchestrator is called |
| Stage sequencing, skip logic | Orchestrator (`orchestrator.py`) | — | Single source of truth for pipeline order; stages have no knowledge of sequence |
| Checkpoint read/write, done markers | Storage Layer (`utils/workdir.py`) | Stage (calls workdir methods) | WorkdirManager is the only component that constructs filesystem paths |
| Approval gate logic (L1–L4) | Orchestrator (`orchestrator.py`) | `utils/rich_ui.py` | Orchestrator decides when to pause; rich_ui only does I/O; stages never pause |
| Stage I/O contracts (types) | Models Layer (`models/`) | — | Pydantic models are imported by stages and orchestrator; no circular deps |
| User prompts, progress, Rich output | Utils Layer (`utils/rich_ui.py`) | — | Isolated; mockable in tests without triggering actual prompts |
| Dry-run cost estimation | Utils Layer (`utils/cost_estimator.py`) | CLI Layer | Orchestrator calls cost_estimator when `dry_run=True`; no stage execution |

---

## Standard Stack

### Core (Phase 1 — all required)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.11+ | Language | Project requirement; 3.11.14 available via `uv python install 3.11` [VERIFIED: uv python list] |
| `pydantic` | `>=2.13.4` | I/O contracts, RunConfig validation | v2 active standard; `model_dump_json()` / `model_validate_json()` for atomic checkpoints [VERIFIED: PyPI 2026-05-25] |
| `pydantic-settings` | `>=2.14.1` | Config merge: CLI > YAML > default | `YamlConfigSettingsSource` + `settings_customise_sources` eliminates hand-rolled merging [VERIFIED: PyPI 2026-05-25] |
| `typer` | `>=0.25.1` | CLI subcommands, typed options | Standard for type-hint CLIs; `@app.command()` + `Annotated[T, typer.Option()]` [VERIFIED: PyPI 2026-05-25] |
| `rich` | `>=15.0.0` | Progress, logging, error tables | Typer's companion for UX; `Console`, `Progress`, `Table` for structured output [VERIFIED: PyPI 2026-05-25] |
| `pyyaml` | `>=6.0.3` | Parse `config.yaml` / `bullets.yaml` | Required by `YamlConfigSettingsSource`; `yaml.safe_load()` only [VERIFIED: PyPI] |

### Supporting (Phase 1)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | `>=8.x` (9.0.3 available) | Unit tests | Stage stub tests, WorkdirManager tests, config merge tests [VERIFIED: system] |
| `pytest-mock` | `>=3.x` | Mock Rich prompts in orchestrator tests | Patch `rich_ui.pause_for_approval` so tests don't block on stdin |
| `python-dotenv` | `>=1.0.0` | Load `.env` for API keys in dev | `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY` — needed even for stubs that print cost estimates |
| `uv` | `0.9.24` (installed) | Project init, venv, deps | `uv init`, `uv add`, `uv sync`, `uv run` — already installed [VERIFIED: system] |

**Installation (Wave 0 — project bootstrap):**

```bash
# Install Python 3.11 via uv (NOT yet installed on this machine)
uv python install 3.11

# Initialize project
cd /path/to/auto-video-narrado
uv init --python 3.11
echo "3.11" > .python-version

# Phase 1 core deps
uv add "pydantic>=2.13.4" "pydantic-settings>=2.14.1" "typer>=0.25.1" "rich>=15.0.0" "pyyaml>=6.0.3"

# Dev deps
uv add --dev "pytest>=8.0" "pytest-mock>=3.0" "python-dotenv>=1.0"
```

**Version verification (confirmed against PyPI 2026-05-25):**
```bash
# Verified versions:
# pydantic: 2.13.4 [VERIFIED: PyPI]
# pydantic-settings: 2.14.1 [VERIFIED: PyPI]
# typer: 0.25.1 [VERIFIED: PyPI]
# rich: 15.0.0 [VERIFIED: PyPI]
# Python 3.11.14: available via uv download [VERIFIED: uv python list]
```

---

## Architecture Patterns

### System Architecture Diagram

```
bullets.yaml + CLI flags
        │
        ▼
┌───────────────────────────┐
│       cli.py (typer)      │  @app.command("generate")
│  parse flags → merge with │  Annotated[Path, typer.Option()] for --bullets
│  config.yaml via          │  YamlConfigSettingsSource for config.yaml
│  pydantic-settings        │  ValidationError → Rich table (never raw traceback)
└──────────┬────────────────┘
           │ RunConfig (pydantic BaseModel)
           ▼
┌───────────────────────────────────────────────────────────┐
│                    orchestrator.py                         │
│                                                           │
│  if dry_run:  cost_estimator.estimate_all(config) → exit  │
│                                                           │
│  for stage in PIPELINE_STAGES:                            │
│    if workdir.is_done(stage.name): continue   ← skip done │
│    if should_pause(stage.name, config.level):             │
│        rich_ui.pause_for_approval(stage.name) ← L1–L4    │
│    output = stage.run(workdir)                            │
│    workdir.mark_done(stage.name, output) ← atomic write   │
└──────────────────────────────┬────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │     PIPELINE_STAGES (all stubs in Phase 1)   │
        │                                              │
   [context]  [storyboard]  [timing]  [scriptwriter]  │
   [slides]   [verify]      [voice]   [align]          │
   [subs]     [assemble]    [qa]                       │
        │                                              │
        │  Each stub:                                  │
        │    - reads previous stage's JSON (if any)    │
        │    - writes minimal valid Pydantic JSON       │
        │    - returns output model instance            │
        └──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│     workdir/  (filesystem state)    │
│                                     │
│  context.json    .context.done      │
│  storyboard.json .storyboard.done   │
│  timings.json    .timing.done       │
│  script.json     .script.done       │
│  slides/         .slides.done       │
│  audio/          .voice.done        │
│  subs/           .subs.done         │
│  output.mp4      .assemble.done     │
└─────────────────────────────────────┘
```

### Recommended Project Structure

```
auto-video-narrado/
├── pyproject.toml              # uv-managed; entry point: avideo = "avideo.cli:app"
├── .python-version             # "3.11"
├── config.yaml                 # defaults: voice_id, wpm, level, slides_mode, etc.
├── bullets.yaml                # user input (example)
├── src/
│   └── avideo/
│       ├── __init__.py
│       ├── cli.py              # typer app + RunConfig merge logic
│       ├── orchestrator.py     # stage loop, checkpoint/approval logic
│       ├── models/
│       │   ├── __init__.py     # re-exports all models
│       │   ├── config.py       # RunConfig
│       │   ├── context.py      # ContextOutput
│       │   ├── storyboard.py   # StoryboardOutput, SlideSpec
│       │   ├── timing.py       # TimingOutput, SlideTiming
│       │   ├── script.py       # ScriptOutput, SlideScript
│       │   ├── slides.py       # SlidesOutput
│       │   ├── verification.py # VerificationReport, SlideVerdict
│       │   ├── voice.py        # VoiceOutput
│       │   └── assembly.py     # AssemblyOutput, QAReport
│       ├── stages/
│       │   ├── __init__.py
│       │   ├── base.py         # StageProtocol (typing.Protocol), CheckpointMixin
│       │   └── stubs.py        # All stub implementations for Phase 1
│       └── utils/
│           ├── __init__.py
│           ├── workdir.py      # WorkdirManager: paths, done markers, JSON r/w
│           ├── rich_ui.py      # Console, Progress, approval prompts, error tables
│           └── cost_estimator.py  # --dry-run estimation (static placeholder for Phase 1)
├── tests/
│   ├── conftest.py
│   ├── test_models.py          # RunConfig validation, I/O model round-trips
│   ├── test_workdir.py         # done markers, atomic writes
│   ├── test_cli.py             # CLI arg parsing, config merge
│   └── test_orchestrator.py   # stage skip, approval gates (mocked rich_ui)
└── workdir/                    # runtime state (gitignored)
```

**Note on `stages/stubs.py`:** In Phase 1 all stage implementations live in a single stubs file. Starting in Phase 2 each stage graduates to its own file in `stages/`. This keeps Phase 1 simpler without creating empty placeholder files.

### Pattern 1: RunConfig — CLI > YAML > Default via pydantic-settings

**What:** `RunConfig` extends `BaseSettings`. The CLI flags are passed as `init_settings` (highest priority); `config.yaml` is loaded via `YamlConfigSettingsSource`; Pydantic field defaults are lowest priority.

**When to use:** Always — this is the single point where all configuration is assembled and validated before the orchestrator starts.

**Example:**
```python
# Source: pydantic-settings docs + Context7 verification
from pathlib import Path
from enum import Enum
from typing import Optional
from pydantic_settings import BaseSettings, YamlConfigSettingsSource, PydanticBaseSettingsSource, SettingsConfigDict
from pydantic import Field

class VoiceMode(str, Enum):
    elevenlabs = "elevenlabs"
    record = "record"

class SlidesMode(str, Enum):
    auto = "auto"
    hybrid = "hybrid"
    manual = "manual"

class RunConfig(BaseSettings):
    # Required inputs
    bullets: Path
    duration: int = Field(gt=0, description="Target duration in seconds")

    # Optional config
    voice: VoiceMode = VoiceMode.elevenlabs
    slides_mode: SlidesMode = SlidesMode.auto
    level: int = Field(default=4, ge=1, le=4)
    context: Optional[Path] = None
    dry_run: bool = False
    burn_subs: bool = False
    verbose: bool = False
    workdir: Path = Path("workdir")
    voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # ElevenLabs default
    wpm: int = Field(default=150, gt=0)

    model_config = SettingsConfigDict(
        yaml_file="config.yaml",
        yaml_file_encoding="utf-8",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ):
        # Priority: CLI kwargs (init) > config.yaml > env > defaults
        return (
            init_settings,
            YamlConfigSettingsSource(settings_cls),
            env_settings,
        )
```

**CLI wires into RunConfig:**
```python
# Source: Typer docs [CITED: typer.tiangolo.com]
import typer
from typing import Annotated
from rich.console import Console

app = typer.Typer(rich_markup_mode="rich")
console = Console(stderr=True)

@app.command()
def generate(
    bullets: Annotated[Path, typer.Option("--bullets", exists=True, help="Path to bullets.yaml")],
    duration: Annotated[int, typer.Option("--duration", min=1, help="Target duration in seconds")],
    voice: Annotated[VoiceMode, typer.Option("--voice")] = VoiceMode.elevenlabs,
    slides_mode: Annotated[SlidesMode, typer.Option("--slides-mode")] = SlidesMode.auto,
    level: Annotated[int, typer.Option("--level", min=1, max=4)] = 4,
    context: Annotated[Optional[Path], typer.Option("--context")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    burn_subs: Annotated[bool, typer.Option("--burn-subs")] = False,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
):
    """Generate a narrated video from bullet points."""
    try:
        config = RunConfig(
            bullets=bullets, duration=duration, voice=voice,
            slides_mode=slides_mode, level=level, context=context,
            dry_run=dry_run, burn_subs=burn_subs, verbose=verbose,
        )
    except ValidationError as e:
        _display_validation_error(e)
        raise typer.Exit(1)

    from avideo.orchestrator import run_pipeline
    run_pipeline(config)
```

### Pattern 2: WorkdirManager — Single Path Authority

**What:** All filesystem path construction and done-marker checks go through `WorkdirManager`. Stages and the orchestrator never build paths manually.

**When to use:** Always. This is the contract: if a stage builds a path with `Path("workdir") / "storyboard.json"` directly, it is an anti-pattern.

```python
# Source: design from ARCHITECTURE.md + atomic write pattern [ASSUMED for tmp suffix]
from pathlib import Path
from pydantic import BaseModel

class WorkdirManager:
    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        for subdir in ("slides", "audio", "subs", "design_proposal", "slides_user"):
            (root / subdir).mkdir(exist_ok=True)

    # Data checkpoint paths
    def checkpoint_path(self, name: str) -> Path:
        return self.root / f"{name}.json"

    # Done marker paths
    def done_marker(self, stage: str) -> Path:
        return self.root / f".{stage}.done"

    def is_done(self, stage: str) -> bool:
        return self.done_marker(stage).exists()

    def mark_done(self, stage: str) -> None:
        """Touch done marker — call only after checkpoint is fully written."""
        self.done_marker(stage).touch()

    def write_checkpoint(self, name: str, model: BaseModel) -> None:
        """Atomic write: tmp → rename. Never leaves partial JSON on disk."""
        target = self.checkpoint_path(name)
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(model.model_dump_json(indent=2), encoding="utf-8")
        tmp.rename(target)  # atomic on same filesystem (POSIX + Windows NTFS)

    def read_checkpoint(self, name: str, model_class: type[BaseModel]) -> BaseModel:
        path = self.checkpoint_path(name)
        return model_class.model_validate_json(path.read_text(encoding="utf-8"))
```

### Pattern 3: StageProtocol + stub implementation

**What:** `typing.Protocol` enforces a uniform stage interface. Phase 1 stubs write minimal valid JSON conforming to each stage's output model.

**When to use:** Always — the protocol is the contract that Phase 2–5 stages must satisfy.

```python
# Source: Python PEP 544 + design from ARCHITECTURE.md [CITED: peps.python.org/pep-0544]
from typing import Protocol, runtime_checkable

@runtime_checkable
class StageProtocol(Protocol):
    stage_name: str

    def run(self, workdir: "WorkdirManager") -> BaseModel:
        """Execute stage logic. Read inputs from workdir. Write output to workdir.
        Returns the output model (but workdir.write_checkpoint + mark_done is
        called by the orchestrator, not here)."""
        ...

    def is_done(self, workdir: "WorkdirManager") -> bool:
        return workdir.is_done(self.stage_name)

# Example stub (all Phase 1 stages follow this shape):
class StoryboardStub:
    stage_name = "storyboard"

    def run(self, workdir: WorkdirManager) -> StoryboardOutput:
        # Minimal valid output that downstream stubs can consume
        return StoryboardOutput(
            slides=[
                SlideSpec(title="Stub Slide", bullets=["Bullet 1"], visual_type="text"),
            ],
            language="es",
        )

    def is_done(self, workdir: WorkdirManager) -> bool:
        return workdir.is_done(self.stage_name)
```

### Pattern 4: Orchestrator Loop with Approval Gates

**What:** The orchestrator is the only component that checks levels and prompts. Stages are always pure logic.

**When to use:** Always — embedding approval logic in stages is the #1 anti-pattern for this architecture.

```python
# Source: design from ARCHITECTURE.md (CONTEXT.md locked decision)
# L1=pause after every stage, L2=pause on creative checkpoints, L3=pause on fail, L4=never
CREATIVE_STAGES = {"storyboard", "script", "slides", "verify"}
FAIL_STAGES = {"verify"}  # stages that can produce a "fail" verdict

def should_pause(stage_name: str, level: int, has_fail: bool = False) -> bool:
    if level == 4:
        return False
    if level == 1:
        return True
    if level == 2:
        return stage_name in CREATIVE_STAGES
    if level == 3:
        return stage_name in FAIL_STAGES and has_fail
    return False

def run_pipeline(config: RunConfig) -> None:
    workdir = WorkdirManager(config.workdir)

    if config.dry_run:
        from avideo.utils.cost_estimator import estimate_all
        estimate_all(config)
        return

    for stage in PIPELINE_STAGES:
        if stage.is_done(workdir):
            console.print(f"[dim]Skipping {stage.stage_name} (already done)[/dim]")
            continue

        if should_pause(stage.stage_name, config.level):
            rich_ui.pause_for_approval(stage.stage_name)

        try:
            output = stage.run(workdir)
            workdir.write_checkpoint(stage.stage_name, output)
            workdir.mark_done(stage.stage_name)
            console.print(f"[green]Done:[/green] {stage.stage_name}")
        except KeyboardInterrupt:
            console.print(f"\n[yellow]Interrupted at {stage.stage_name}[/yellow]")
            raise typer.Exit(130)
```

### Pattern 5: Pydantic ValidationError → Rich Table

**What:** Catch `ValidationError` at the CLI layer, render each error as a Rich table row (field, message), exit with code 1. Never let a raw traceback reach the user.

```python
# Source: pydantic docs [CITED: pydantic.dev/docs/validation/latest/errors/errors]
from pydantic import ValidationError
from rich.table import Table
from rich.console import Console

def _display_validation_error(e: ValidationError) -> None:
    console = Console(stderr=True)
    table = Table("Field", "Error", title="[red]Configuration Error[/red]")
    for err in e.errors():
        loc = " → ".join(str(x) for x in err["loc"])
        table.add_row(loc, err["msg"])
    console.print(table)
```

### Anti-Patterns to Avoid

- **Stages that call `input()` or `Console.input()`:** Approval logic belongs exclusively to the orchestrator. Stages are always callable without interaction (for tests and automated runs).
- **Passing Python models between stages in memory:** The orchestrator must only pass `WorkdirManager`. Each stage reads its inputs from the workdir filesystem. This is the resumability guarantee.
- **Touching the done marker before writing the checkpoint:** The done marker must be the *last* thing written. If the JSON write fails, the marker must not exist. This is the corruption-prevention guarantee.
- **Using `shell=True` in subprocess:** Not relevant in Phase 1 (no subprocess calls), but the convention is established here: subprocess calls (Phase 5) always use list args.
- **Calling `yaml.load()` without `Loader=yaml.SafeLoader`:** Always use `yaml.safe_load()` to prevent arbitrary code execution from malformed YAML config.
- **Storing API keys in `config.yaml`:** Only non-secret config (wpm, voice_id, level defaults). API keys go in `.env` / environment variables, loaded at runtime.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CLI flag parsing + help text | Manual `argparse` setup | `typer` `@app.command()` with `Annotated` | Auto-generates `--help`, type conversion, enum validation, `min`/`max` constraints |
| Config merge (CLI > YAML > default) | Manual dict merge with `|` operator | `pydantic-settings` `YamlConfigSettingsSource` + `settings_customise_sources` | Handles None-vs-default ambiguity, type coercion, missing-file graceful fallback |
| ValidationError formatting | String concatenation over `e.errors()` | Rich `Table` over `e.errors()` | Consistent per-field attribution; no missed errors from complex nested models |
| Atomic file writes | `open(path, 'w')` directly | `tmp.write_text()` then `tmp.rename(target)` | `rename()` is atomic on POSIX and NTFS when source and target are on the same filesystem |
| Stage interface enforcement | Duck-typing with no enforcement | `typing.Protocol` with `@runtime_checkable` | `isinstance(stage, StageProtocol)` check in orchestrator prevents silent mismatches |
| YAML parsing | Custom regex / line parsing | `pyyaml` `yaml.safe_load()` | Correct handling of multi-line strings, Unicode, null values |

**Key insight:** Every item in this list looks simple to hand-roll but has subtle edge cases that `pydantic-settings` / `typer` / `rich` already handle — especially config precedence and validation error formatting.

---

## Common Pitfalls

### Pitfall 1: `rename()` not atomic across filesystems

**What goes wrong:** If `workdir/` is on a different filesystem than `/tmp/` (e.g., network mount, Docker volume), `tmp.rename(target)` raises `OSError: [Errno 18] Invalid cross-device link`.

**Why it happens:** POSIX `rename()` is only atomic within the same filesystem. If temp file and target are on different devices, it falls back to copy+delete which is NOT atomic.

**How to avoid:** Create the temp file in the same directory as the target: `target.with_suffix(".json.tmp")`. Since both are in `workdir/`, they are always on the same filesystem.

**Warning signs:** `OSError: [Errno 18]` when writing first checkpoint. Common in Docker bind mounts if workdir is mapped from host.

---

### Pitfall 2: `pydantic-settings` `YamlConfigSettingsSource` requires `pyyaml` to be installed

**What goes wrong:** `YamlConfigSettingsSource` is only imported successfully if `pyyaml` is installed in the environment. If the user does `uv add pydantic-settings` without `pyyaml`, the import of `YamlConfigSettingsSource` raises `ImportError` at runtime, not at install time.

**Why it happens:** `pydantic-settings` keeps YAML support as a soft dependency to avoid forcing pyyaml on all users.

**How to avoid:** Always add both `pydantic-settings` and `pyyaml` together: `uv add "pydantic-settings>=2.14.1" "pyyaml>=6.0.3"`. Document this requirement in `pyproject.toml` dependencies.

**Warning signs:** `ImportError: No module named 'yaml'` when importing `YamlConfigSettingsSource`.

---

### Pitfall 3: Typer `Enum` option display — use `str, Enum` base

**What goes wrong:** When using a plain `Enum` (not `str, Enum`) for CLI options, Typer displays the internal Python representation (`VoiceMode.elevenlabs`) in error messages instead of the string value (`elevenlabs`), making user-facing errors confusing.

**Why it happens:** Typer uses the enum's `__str__` for display. `str, Enum` inherits `__str__` from `str`, giving clean display.

**How to avoid:** Always define CLI-facing enums as `class VoiceMode(str, Enum)` — not `class VoiceMode(Enum)`.

**Warning signs:** Error messages show `VoiceMode.elevenlabs` instead of `'elevenlabs'` in help text or validation errors.

---

### Pitfall 4: Done marker checked AFTER exception in stage

**What goes wrong:** If a stage raises an exception partway through its run, the orchestrator might catch the exception and touch the done marker anyway (if error handling is in the wrong place), causing the stage to be skipped on the next run with incomplete output.

**Why it happens:** Exception handling in the orchestrator loop at the wrong granularity.

**How to avoid:** The `workdir.mark_done()` call must only happen on the happy path, after `workdir.write_checkpoint()` succeeds. Any exception propagation must skip the `mark_done()` call. Pattern:

```python
output = stage.run(workdir)          # can raise
workdir.write_checkpoint(name, output)  # can raise
workdir.mark_done(name)               # only reached if both above succeed
```

Never wrap these three lines in a try/except that marks done in the except branch.

---

### Pitfall 5: Python 3.11 not installed — `uv init` will auto-download but might fail in offline environments

**What goes wrong:** `uv init --python 3.11` on a machine without Python 3.11 installed will attempt to download it from the `uv` managed Python registry. In offline environments (CI without internet, air-gapped Docker build), this download fails silently or with a non-obvious error.

**Why it happens:** Python 3.11 is not currently installed on the development machine (verified: only 3.9, 3.12, 3.13, 3.14 found). [VERIFIED: `uv python list --only-installed`]

**How to avoid:** Wave 0 of Plan 01-01 must include `uv python install 3.11` as the first step, before `uv init`. Verify with `uv python list --only-installed | grep 3.11`.

**Warning signs:** `uv init` completes but `python --version` in the venv shows 3.13 instead of 3.11.

---

### Pitfall 6: `pydantic-settings` does NOT handle `Optional[Path]` None-vs-missing correctly by default

**What goes wrong:** If `config.yaml` omits an optional field (e.g., `context:`), and the CLI doesn't pass the flag, `pydantic-settings` may fail to distinguish "key absent from YAML" from "key set to None in CLI". The field gets overridden by the wrong priority.

**Why it happens:** `init_settings` (CLI kwargs) has highest priority. If the CLI passes `context=None` explicitly, it overrides the YAML value. For optional fields that can legitimately be `None`, this is correct behavior, but if you have `Optional[Path]` with no default and the user didn't pass it, Typer passes `None` which is treated as explicit init.

**How to avoid:** Set `default=None` on optional Pydantic fields. For `context`, define as `context: Optional[Path] = None` — Typer's default `None` and the model default `None` will agree. Test the merge behavior for each optional field.

---

## Code Examples

### Verified patterns from official sources

#### RunConfig with YAML source priority

```python
# Source: pydantic-settings docs [CITED: pydantic-settings GitHub]
from pydantic_settings import BaseSettings, YamlConfigSettingsSource, SettingsConfigDict

class RunConfig(BaseSettings):
    model_config = SettingsConfigDict(yaml_file="config.yaml", extra="ignore")

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings,
                                   env_settings, dotenv_settings, file_secret_settings):
        return (init_settings, YamlConfigSettingsSource(settings_cls), env_settings)
```

#### Typer Path option with existence check

```python
# Source: Typer docs [CITED: typer.tiangolo.com/reference/parameters]
from pathlib import Path
from typing import Annotated
import typer

@app.command()
def generate(
    bullets: Annotated[Path, typer.Option("--bullets", exists=True, file_okay=True,
                                          dir_okay=False, help="Path to bullets.yaml")],
):
    ...
```

#### Atomic checkpoint write

```python
# Source: ARCHITECTURE.md design + POSIX atomic rename guarantee [ASSUMED for NTFS claim]
def write_checkpoint(self, name: str, model: BaseModel) -> None:
    target = self.root / f"{name}.json"
    tmp = target.with_suffix(".json.tmp")  # same directory = same filesystem
    tmp.write_text(model.model_dump_json(indent=2), encoding="utf-8")
    tmp.rename(target)  # atomic on POSIX; atomic on NTFS for same-volume rename
```

#### Pydantic ValidationError → Rich Table

```python
# Source: pydantic docs error handling [CITED: pydantic.dev]
from pydantic import ValidationError
from rich.table import Table
from rich.console import Console

def show_validation_error(e: ValidationError, console: Console) -> None:
    table = Table("Field", "Error", title="[red bold]Configuration Error[/red bold]",
                  border_style="red")
    for err in e.errors():
        loc = " → ".join(str(x) for x in err["loc"])
        table.add_row(f"[bold]{loc}[/bold]", err["msg"])
    console.print(table)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pydantic` v1 `.dict()` / `.json()` | v2 `model_dump()` / `model_dump_json()` / `model_validate_json()` | Pydantic 2.0 (2023) | All checkpoints must use v2 API — v1 methods raise `PydanticDeprecationWarning` and will be removed |
| `click` for CLIs | `typer` with `Annotated` type hints | typer 0.9+ (2023) | `Annotated[T, typer.Option()]` is now the canonical pattern; positional `= typer.Option(...)` is legacy |
| Manual YAML loading + dict merge | `pydantic-settings` `YamlConfigSettingsSource` | pydantic-settings 2.2+ (2024) | Native YAML settings source eliminates hand-rolled merge code and None-vs-absent ambiguity |
| `argparse` + `click` for CLIs | `typer` with rich integration | 2022+ | `Typer(rich_markup_mode="rich")` enables Rich markup in all help text automatically |

**Deprecated/outdated:**
- `pydantic` `.json()` method: replaced by `model_dump_json()`; raises `PydanticDeprecationWarning` in v2
- `pydantic` `@validator` decorator: replaced by `@field_validator` in v2
- `pydantic` `class Config:`: replaced by `model_config = SettingsConfigDict(...)` in v2
- `typer.Option(...)` as default value (positional): replaced by `Annotated[T, typer.Option()]`

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `tmp.rename(target)` is atomic on Windows NTFS for same-volume rename | Pattern 2, Pitfall 1 | On some NTFS configurations, rename may not be atomic; use `os.replace()` instead for cross-platform guarantee |
| A2 | `YamlConfigSettingsSource` is included in `pydantic-settings>=2.14.1` without extra install | Standard Stack | If it requires `pydantic-settings[yaml]` extra, `uv add` command needs `"pydantic-settings[yaml]>=2.14.1"` |
| A3 | `uv python install 3.11` will succeed in the project's internet-connected dev environment | Environment Availability | Offline CI or restrictive firewall would require pre-bundled Python |

**If this table is empty:** Not empty — three assumptions remain. Confirm A1 and A2 before Wave 0 of Plan 01-01.

---

## Open Questions

1. **`pydantic-settings[yaml]` vs `pydantic-settings` extra install**
   - What we know: `YamlConfigSettingsSource` exists in pydantic-settings 2.14.1 per API docs [CITED: pydantic.dev]
   - What's unclear: Whether `pyyaml` import is automatic or requires an `[yaml]` extra at install time
   - Recommendation: Plan 01-02 Wave 0 should include a quick import test: `python -c "from pydantic_settings import YamlConfigSettingsSource"` and adjust install command if it fails

2. **`os.replace()` vs `Path.rename()` for atomic writes on Windows**
   - What we know: POSIX `rename()` is atomic on same-filesystem. `Path.rename()` calls POSIX `rename()` on Unix.
   - What's unclear: NTFS atomic guarantee for `Path.rename()` vs `os.replace()` (which calls `MoveFileExW` with `MOVEFILE_REPLACE_EXISTING`)
   - Recommendation: Use `os.replace(str(tmp), str(target))` in `WorkdirManager.write_checkpoint()` — it is guaranteed atomic on both POSIX and Windows

3. **Minimal stub outputs for downstream stubs**
   - What we know: Each stub must write a valid Pydantic JSON so the next stub can `model_validate_json()` it
   - What's unclear: Whether Plan 01-03 should define ALL stub outputs (requiring all models to be complete) or just the ones needed for stage-to-stage data flow
   - Recommendation: Define all I/O models in Plan 01-01 even if they have `Optional` fields everywhere; stubs in Plan 01-03 write minimal values for required fields only

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11 | Project requirement | Download required | 3.11.14 via `uv python install 3.11` | — (no fallback; project requires >=3.11) |
| uv | Project bootstrap | ✓ | 0.9.24 | — |
| pytest | Tests | ✓ (system) | 9.0.3 | — |
| pydantic | Core | Needs uv install | 2.13.4 (PyPI) | — |
| pydantic-settings | Config merge | Needs uv install | 2.14.1 (PyPI) | — |
| pyyaml | YAML parsing | ✓ (system conda env) | Available | — |
| typer | CLI | ✓ (system) but wrong version | 0.25.1 available via uv | Use project venv, not system |
| rich | UI | Not in current env | 15.0.0 available | — |

**Missing dependencies with no fallback:**
- Python 3.11 (project requirement): must run `uv python install 3.11` before `uv init`

**Missing dependencies with fallback:**
- None — all deps are installable via `uv add`

**Critical note:** The system currently has Python 3.13.5 active (miniconda). All project work must happen inside the `uv`-managed virtual environment. Plan 01-01 Wave 0 must create the venv with `uv init --python 3.11` to isolate from the system Python.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 (system) + pytest-mock |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — Wave 0 |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -v --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CLI-01 | `avideo generate --bullets b.yaml --duration 120` runs without error | smoke | `uv run pytest tests/test_cli.py::test_generate_runs_end_to_end -x` | ❌ Wave 0 |
| CLI-02 | `--voice record` sets `RunConfig.voice = VoiceMode.record` | unit | `uv run pytest tests/test_models.py::test_runconfig_voice -x` | ❌ Wave 0 |
| CLI-03 | `--slides-mode hybrid` accepted by CLI | unit | `uv run pytest tests/test_cli.py::test_slides_mode_option -x` | ❌ Wave 0 |
| CLI-04 | `--level 5` rejected with error | unit | `uv run pytest tests/test_cli.py::test_level_validation -x` | ❌ Wave 0 |
| CLI-07 | YAML field overridden by CLI flag | unit | `uv run pytest tests/test_cli.py::test_config_merge_precedence -x` | ❌ Wave 0 |
| CLI-07 | Pydantic error shows Rich table, not traceback | unit | `uv run pytest tests/test_cli.py::test_validation_error_display -x` | ❌ Wave 0 |
| CLI-08 | Rich progress displayed during pipeline run | unit | `uv run pytest tests/test_orchestrator.py::test_rich_progress -x` | ❌ Wave 0 |
| ORCH-02 | Re-run skips completed stages | unit | `uv run pytest tests/test_orchestrator.py::test_stage_skip_on_done -x` | ❌ Wave 0 |
| ORCH-03 | Atomic write: partial write leaves no done marker | unit | `uv run pytest tests/test_workdir.py::test_atomic_write_no_partial -x` | ❌ Wave 0 |
| ORCH-04 | L1 pauses after every stage | unit | `uv run pytest tests/test_orchestrator.py::test_level1_pauses -x` | ❌ Wave 0 |
| ORCH-04 | L4 never pauses | unit | `uv run pytest tests/test_orchestrator.py::test_level4_no_pause -x` | ❌ Wave 0 |
| ORCH-05 | Stage output validates as Pydantic model | unit | `uv run pytest tests/test_models.py::test_storyboard_output_roundtrip -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/ -x -q` (fail-fast, quick)
- **Per wave merge:** `uv run pytest tests/ -v --tb=short`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/conftest.py` — shared fixtures (tmp workdir, minimal bullets.yaml, minimal config.yaml)
- [ ] `tests/test_models.py` — covers ORCH-05, CLI-02, CLI-03
- [ ] `tests/test_workdir.py` — covers ORCH-02, ORCH-03
- [ ] `tests/test_cli.py` — covers CLI-01, CLI-04, CLI-07, CLI-08
- [ ] `tests/test_orchestrator.py` — covers ORCH-04, CLI-08
- [ ] `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]`
- [ ] Framework install: `uv add --dev "pytest>=8.0" "pytest-mock>=3.0"` — installed after `uv init`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No — Phase 1 has no auth | — |
| V3 Session Management | No | — |
| V4 Access Control | No | — |
| V5 Input Validation | Yes — bullets path, config.yaml path, duration range | pydantic `Field(gt=0)`, typer `exists=True` for paths, `min/max` for integers |
| V6 Cryptography | No — no crypto in Phase 1 | — |

### Known Threat Patterns for {stack}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via `--bullets` / `--context` | Tampering | Typer `exists=True` resolves the path; pydantic validates it is a file; workdir paths built by WorkdirManager only |
| API key exposure in `config.yaml` | Information Disclosure | `config.yaml` in `.gitignore`; API keys only via env vars / `.env`; pydantic-settings env source for secrets |
| YAML injection via `config.yaml` | Tampering | Always `yaml.safe_load()` (via pydantic-settings `YamlConfigSettingsSource`); never `yaml.load()` without Loader |

---

## Project Constraints (from CLAUDE.md)

- **Language:** Python 3.11+ — mandatory
- **Pydantic:** v2 only (`model_dump_json`, `model_validate_json`) — v1 methods forbidden
- **CLI:** `typer` + `rich` — argparse and click are not acceptable
- **Config/logs:** `pydantic`, `pyyaml`, `rich` — all three required for Phase 1
- **Package management:** `pyproject.toml` managed with `uv` — pip/poetry not acceptable
- **Tests:** `pytest` only
- **Code quality:** Modular, typed, docstrings, clear error handling, resumable and idempotent
- **No MoviePy, no LangChain/LangGraph, no n8n** — explicitly excluded
- **No images from AI or stock** — not relevant in Phase 1 (no slide generation)

---

## Sources

### Primary (HIGH confidence)

- `pydantic-settings` GitHub + PyPI — `YamlConfigSettingsSource`, `settings_customise_sources`, version 2.14.1 [VERIFIED: PyPI 2026-05-25]
- Typer official docs — `@app.command()`, `Annotated` options, `Path` validation [CITED: typer.tiangolo.com, Context7 /websites/typer_tiangolo]
- Pydantic v2 official docs — `ValidationError.errors()`, `model_dump_json()`, `model_validate_json()` [CITED: pydantic.dev, Context7 /websites/pydantic_dev_validation]
- Python PEP 544 — `typing.Protocol` structural subtyping [CITED: peps.python.org/pep-0544]
- `uv python list --only-installed` — Python 3.11 not installed, 3.11.14 downloadable [VERIFIED: system]
- PyPI version checks — pydantic 2.13.4, pydantic-settings 2.14.1, typer 0.25.1 [VERIFIED: PyPI curl 2026-05-25]
- `.planning/research/ARCHITECTURE.md` — architectural patterns (StageProtocol, CheckpointMixin, workdir layout) [CITED: project research]
- `.planning/phases/01-foundation/01-CONTEXT.md` — locked implementation decisions [CITED: project]

### Secondary (MEDIUM confidence)

- WebSearch — `pydantic-settings YamlConfigSettingsSource` — confirmed exists in current release, example patterns [CITED: iifx.dev, pydantic-settings issue #366]
- `.planning/research/PITFALLS.md` — pitfall #10 (non-idempotent pipeline) relevant to orchestrator design [CITED: project research]

### Tertiary (LOW confidence)

- NTFS atomic rename guarantee for `Path.rename()` — training knowledge, not verified against Microsoft docs [ASSUMED]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified against PyPI 2026-05-25
- Architecture: HIGH — patterns from CONTEXT.md locked decisions + existing architecture research
- Config merge patterns: HIGH — verified against pydantic-settings docs + Context7
- Typer patterns: HIGH — verified against official Typer docs via Context7
- Pitfalls: HIGH — based on existing PITFALLS.md research + Phase 1 specific additions
- Atomic write on NTFS: LOW — ASSUMED, recommend using `os.replace()` to be safe

**Research date:** 2026-05-25
**Valid until:** 2026-06-25 (stable libraries — pydantic, typer, rich change infrequently)
