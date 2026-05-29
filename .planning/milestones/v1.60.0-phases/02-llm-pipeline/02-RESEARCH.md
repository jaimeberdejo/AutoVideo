# Phase 2: LLM Pipeline - Research

**Researched:** 2026-05-25
**Domain:** Anthropic SDK structured output (forced tool-use), document text extraction (PyMuPDF/python-pptx), deterministic timing apportionment (largest-remainder), pipeline stage integration
**Confidence:** HIGH (SDK + libraries verified against Context7 + official docs + PyPI registry)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Storyboard (Claude)**
- **D-01** El nº de slides lo decide Claude según densidad de contenido + duración objetivo (≈1 slide por 20-30 s), acotado a un rango razonable (min/max).
- **D-02** `visual_type` es un **Enum cerrado**: `title`, `bullets`, `chart`, `diagram`, `quote`, `comparison`, `image_icon`. Migrar `SlideSpec.visual_type` de `str` libre a este Enum (str, Enum).
- **D-03** Salida estructurada vía **tool-use forzado de Anthropic** (`tool_choice` forzado a una herramienta cuyo `input_schema` es el schema del storyboard) → JSON garantizado conforme al contrato.
- **D-04** El texto de contexto ingerido se inyecta en el prompt del storyboard, **truncado a un tope de tokens configurable**.

**Director de timing (Python puro, sin LLM)**
- **D-05** Distribución de duración **ponderada por contenido** (nº de bullets + longitud de caracteres del título+bullets), con **clamps min/máx por slide**.
- **D-06** La **suma de duraciones por slide es exactamente igual** a la duración objetivo: redondeo por **mayor resto (largest-remainder)**.
- **D-07** `word_budget` por slide = `round(seconds × wpm / 60)`; WPM configurable (por defecto 150, ya en `RunConfig`).
- **D-08** Lógica 100% determinista y testeable sin red.

**Guionista (Claude)**
- **D-09** Generación **whole-script en una sola llamada** (Claude ve todas las slides), con el **presupuesto de palabras por slide explícito** en el prompt.
- **D-10** **Calibración con 1 reintento**: si tras la 1ª generación alguna slide se desvía >25% de su presupuesto, una única regeneración pidiendo corrección; si sigue desviada, se acepta y se registra.
- **D-11** Tono natural para locución hablada, en el idioma configurado (por defecto `es`). Salida vía tool-use forzado.

**Integraciones y robustez**
- **D-12** Modelo: **Claude Sonnet más reciente** para storyboard y guion. Centralizado en `integrations/anthropic.py`.
- **D-13** **Reintentos con backoff exponencial** (combinando `max_retries` del SDK + manejo propio de 429/5xx), 3 intentos; errores finales se elevan como error claro (Rich).
- **D-14** `integrations/anthropic.py` expone un helper genérico "llamada con tool-use estructurado → modelo Pydantic" reutilizable.
- **D-15** Coste/tokens reales para `--dry-run`: `cost_estimator` estima tokens de storyboard+guion a partir de nº de bullets/duración.

### Claude's Discretion
- Estructura interna exacta de prompts (system vs user), nombres de las tools, valores concretos de los clamps min/máx de timing, tope exacto de truncado de contexto.

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CTX-01 | El usuario aporta `.pptx`/`.pdf`/`.md` y el sistema extrae su texto como referencia | PyMuPDF `fitz.open()` + `page.get_text("text")`; python-pptx `slide.shapes` + `has_text_frame`; markdown plain read (Standard Stack, Code Examples) |
| CTX-02 | El ingestor es opcional; sin contexto el pipeline funciona igual | `config.context is None` → `ContextOutput(used=False)`; storyboard prompt omits context block (Architecture Patterns) |
| STORY-01 | Genera storyboard (nº slides + título/puntos/tipo visual) con Anthropic a partir de bullets+duración | Forced tool-use `tool_choice={"type":"tool","name":...}`, `input_schema` from `StoryboardOutput.model_json_schema()` (Code Examples) |
| STORY-02 | Storyboard como JSON estructurado, validado Pydantic, persistido en `workdir/storyboard.json` | Extract `tool_use` block → `StoryboardOutput.model_validate(block.input)`; orchestrator writes checkpoint name `storyboard` (Code Examples, Integration) |
| TIME-01 | Reparte la duración total entre slides según densidad de contenido | Content-weighted split + largest-remainder; clamps min/max (Code Examples: timing) |
| TIME-02 | Calcula presupuesto de palabras por slide según WPM configurable (150) | `word_budget = round(seconds * wpm / 60)` (Code Examples: timing) |
| SCRIPT-01 | Genera narración por slide ajustada al presupuesto de palabras | Whole-script tool-use call w/ explicit per-slide budgets + 1 calibration retry on >25% drift (Architecture Patterns: scriptwriter) |
| SCRIPT-02 | Guion como JSON estructurado, en español, tono natural locución | Same forced tool-use helper, `ScriptOutput` schema, `language` from config (Code Examples) |
</phase_requirements>

## Summary

Phase 2 swaps four Phase-1 stubs (`context`, `storyboard`, `timing`, `scriptwriter`) for real implementations, keeping the exact `stage_name`/`checkpoint_name` contract so the orchestrator, WorkdirManager, and downstream phases are untouched. Two stages call Claude (`storyboard`, `scriptwriter`) and must produce contract-conformant JSON; one stage is pure deterministic Python (`timing`); one stage is pure I/O (`context` extraction). A new `integrations/anthropic.py` centralizes the client and a generic "forced tool-use → Pydantic model" helper reused by both LLM stages.

The single most consequential finding: the installed `anthropic==0.104.1` SDK **already implements exponential backoff with jitter and `Retry-After` handling** on 408/409/429/5xx via `max_retries`. This means D-13's "manejo propio de 429/5xx" is largely redundant — set `max_retries=3` on the client (default is 2) and the SDK handles the backoff loop. The only custom retry needed is the **application-level calibration retry** (D-10, a semantic re-call, not a network retry). A second important finding: the SDK now ships a native `client.messages.parse(output_format=PydanticModel)` structured-output helper, but CONTEXT.md **locks forced tool-use** — so this research documents the tool-use path (D-03) and lists `messages.parse` only as an Alternatives-Considered entry, not a recommendation.

**Primary recommendation:** Build `integrations/anthropic.py` with a lazily-instantiated `Anthropic(max_retries=3)` client and a generic `call_structured(*, system, user, tool_name, tool_description, output_model, max_tokens) -> output_model` helper that (1) derives `input_schema` from `output_model.model_json_schema()`, (2) forces `tool_choice={"type":"tool","name":tool_name}`, (3) extracts the single `tool_use` content block, (4) validates with `output_model.model_validate(block.input)`. Mock this helper (not the raw HTTP) in tests. Use model `claude-sonnet-4-6`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Context document text extraction (CTX-01/02) | Stage (`stages/context.py`) | — | Pure local file I/O; no LLM, no network. Belongs in a stage that reads `config.context` and returns `ContextOutput`. |
| Bullets input parsing (`bullets.yaml`) | Stage (`stages/storyboard.py` or shared util) | — | **Not yet implemented anywhere** — `bullets.yaml` is currently never read. Storyboard consumes bullets, so parse there or in a small shared loader. |
| Storyboard generation (STORY-01/02) | Stage (`stages/storyboard.py`) | Integration (`integrations/anthropic.py`) | Stage owns prompt + business logic; integration owns the Anthropic client + tool-use plumbing. |
| Timing apportionment (TIME-01/02) | Stage (`stages/timing.py`) | — | Pure deterministic Python. No LLM, no network. Fully unit-testable offline. |
| Scriptwriting + calibration (SCRIPT-01/02) | Stage (`stages/scriptwriter.py`) | Integration (`integrations/anthropic.py`) | Stage owns calibration loop + prompt; integration owns the reusable tool-use helper. |
| Anthropic client + tool-use helper (D-12/13/14) | Integration (`integrations/anthropic.py`) | — | Single place to change model ID, retries, and structured-output mechanics. |
| Cost estimation for `--dry-run` (D-15) | Util (`utils/cost_estimator.py`) | — | Must be **offline / side-effect-free** (orchestrator runs it before any workdir is created). Heuristic only — never call the token-count API here. |
| Checkpoint persistence | Orchestrator + WorkdirManager | — | Already built. Stages return a model; orchestrator calls `write_checkpoint` → `mark_done`. Stages must NOT write checkpoints themselves. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `anthropic` | `0.104.1` (installed) | LLM calls: storyboard + scriptwriter via forced tool-use | Official SDK; built-in retry/backoff; native tool-use + Pydantic-friendly schema [VERIFIED: pypi.org/project/anthropic latest=0.104.1] |
| `pydantic` | `2.13.4` (installed) | I/O contracts + `model_json_schema()` for `input_schema` + `model_validate(dict)` | Already the project's contract layer; v2 `model_json_schema()` produces draft-2020-12 schemas the API accepts [VERIFIED: uv pip list] |
| `PyMuPDF` | `1.27.2.3` (CLAUDE.md pin) | PDF text extraction (CTX-01) | Superior page text extraction + handles encrypted PDFs via `authenticate()` [VERIFIED: pypi.org/project/PyMuPDF latest=1.27.2.3] |
| `python-pptx` | `1.0.2` (CLAUDE.md pin) | .pptx text extraction (CTX-01) | Standard pure-Python pptx reader; iterate `slide.shapes` + `has_text_frame` [VERIFIED: pypi.org/project/python-pptx latest=1.0.2] |
| `pyyaml` | `6.0.3` (installed) | Parse `bullets.yaml` (title + bullets list) | Already a dependency; `bullets.yaml` parsing is **net-new** in Phase 2 [VERIFIED: uv pip list] |
| `rich` | `15.0.0` (installed) | Clear error surfacing for final API failures (D-13) | Project convention; `console` already in `utils/rich_ui.py` [VERIFIED: uv pip list] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest-mock` | `3.15.1` (installed) | Mock the `call_structured` helper / Anthropic client in tests (TEST-01) | Always in stage tests that touch Claude [VERIFIED: uv pip list] |
| `python-dotenv` | `>=1.0` (dev dep) | Load `ANTHROPIC_API_KEY` from `.env` in local dev | Dev-only; the SDK reads `ANTHROPIC_API_KEY` from env automatically [VERIFIED: pyproject.toml] |

**Note on `fitz` import:** CLAUDE.md says "importar como `import fitz`". Both `import fitz` and `import pymupdf` work in 1.27.x (`fitz` is the legacy module name, still supported). Follow CLAUDE.md: `import fitz`. [CITED: github.com/pymupdf/pymupdf docs — both names valid]

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Forced tool-use (D-03, LOCKED) | `client.messages.parse(output_format=PydanticModel)` — native structured outputs | The SDK now has a first-class `parse()` that takes a Pydantic type and returns `ParsedMessage[T]` with typed `.parsed_output`. Cleaner than tool-use. **NOT recommended** — CONTEXT.md locks forced tool-use. Documented only so the planner knows it exists. [VERIFIED: Context7 /anthropics/anthropic-sdk-python — `messages.parse` signature] |
| Custom 429/5xx retry loop (part of D-13) | SDK built-in `max_retries` | SDK already retries 408/409/429/≥500 with exponential backoff + jitter + `Retry-After`. Custom HTTP retry is redundant. Keep custom logic ONLY for the calibration re-call (D-10). [VERIFIED: Context7 — `_should_retry`, `_calculate_retry_timeout`] |
| `tiktoken` / API `count_tokens` for dry-run | Char/word heuristic | `count_tokens` is a **network call** → violates the offline `--dry-run` contract. Use `chars/4` or word-count heuristic. [VERIFIED: Context7 — `count_tokens` is `POST /v1/messages/count_tokens`] |
| `import pymupdf` | `import fitz` | Functionally identical in 1.27.x; CLAUDE.md mandates `fitz`. |
| `pdf2image`/Poppler | PyMuPDF | Not needed in Phase 2 (no rasterization — that's the Phase 6 verifier). Phase 2 only needs PDF *text*. |

**Installation:** All Phase-2 LLM/ingestion deps are net-new to `pyproject.toml` (Phase 1 only installed pydantic/typer/rich/pyyaml). Add:
```bash
uv add anthropic PyMuPDF python-pptx
# python-dotenv already in dev group; pyyaml already core
```

**Version verification (2026-05-25, against PyPI):**
- `anthropic` latest = `0.104.1` (installed) ✓ [VERIFIED: pypi registry]
- `PyMuPDF` latest = `1.27.2.3` (matches CLAUDE.md pin) ✓ [VERIFIED: pypi registry]
- `python-pptx` latest = `1.0.2` (matches CLAUDE.md pin) ✓ [VERIFIED: pypi registry]

## Architecture Patterns

### System Architecture Diagram

```
                        config.context (.pdf/.pptx/.md, optional)
                                       │
   bullets.yaml ──┐                    ▼
 (title+bullets)  │            ┌───────────────┐
                  │            │  context stage │  fitz / python-pptx / read_text
                  │            │  → ContextOutput│  (used=False if no --context)
                  │            └───────┬────────┘
                  │                    │ text (truncated to token cap)
                  ▼                    ▼
            ┌──────────────────────────────────────┐
            │           storyboard stage            │
            │  build prompt(bullets, duration,      │
            │   context_text) → call_structured(    │   ┌──────────────────────┐
            │     tool=storyboard_schema, forced)   │──▶│ integrations/anthropic│
            │  → StoryboardOutput (slides+visual)   │◀──│  Anthropic(max_retries│
            └───────────────────┬──────────────────┘   │  =3) + tool_use helper│
                                │ storyboard.json       └──────────────────────┘
                                ▼                                  │
            ┌──────────────────────────────────────┐              │
            │     timing stage (PURE PYTHON)        │              │
            │  weights = f(#bullets, char_len)      │              │
            │  seconds = largest_remainder(weights, │              │
            │            target) w/ min/max clamps  │              │
            │  word_budget = round(sec*wpm/60)      │              │
            │  → TimingOutput (sum == target) ──────┼──▶ timings.json
            └───────────────────┬──────────────────┘              │
                                │ per-slide word budgets           │
                                ▼                                  │
            ┌──────────────────────────────────────┐              │
            │          scriptwriter stage           │              │
            │  prompt(all slides + per-slide budget)│──────────────┘
            │  → call_structured(script_schema)     │
            │  calibrate: if any slide >25% off →   │
            │    ONE re-call; else accept+log       │
            │  → ScriptOutput (es, natural) ────────┼──▶ script.json
            └──────────────────────────────────────┘

   --dry-run branch (orchestrator, BEFORE workdir): cost_estimator heuristic
     reads bullets count + duration → est. tokens/USD table (NO network, NO files)
```

File-to-implementation mapping is in Component Responsibilities below (not in the diagram).

### Component Responsibilities
| File | Responsibility | Replaces |
|------|----------------|----------|
| `src/avideo/integrations/__init__.py` | Package marker (net-new dir) | — |
| `src/avideo/integrations/anthropic.py` | Lazy `Anthropic(max_retries=3)` client; `call_structured()` helper; model constant `MODEL = "claude-sonnet-4-6"` | — |
| `src/avideo/stages/context.py` | `ContextStage` — extract text from .pdf/.pptx/.md → `ContextOutput`; truncate to token cap | `ContextStub` |
| `src/avideo/stages/storyboard.py` | `StoryboardStage` — read bullets.yaml, build prompt, call helper → `StoryboardOutput` | `StoryboardStub` |
| `src/avideo/stages/timing.py` | `TimingStage` — pure largest-remainder apportionment + word budgets → `TimingOutput` | `TimingStub` |
| `src/avideo/stages/scriptwriter.py` | `ScriptwriterStage` — whole-script call + 1 calibration retry → `ScriptOutput` | `ScriptwriterStub` |
| `src/avideo/models/storyboard.py` | Add `VisualType(str, Enum)`; change `SlideSpec.visual_type: VisualType` | — (enrich) |
| `src/avideo/utils/cost_estimator.py` | Replace static `STAGE_COSTS` with heuristic from bullets/duration | — (rewrite) |
| `src/avideo/stages/stubs.py` | Remove 4 stubs from `PIPELINE_STAGES`, import real stages instead | — (edit) |

### Recommended Project Structure
```
src/avideo/
├── integrations/          # NEW — external service clients
│   ├── __init__.py
│   └── anthropic.py       # client + call_structured() helper + MODEL const
├── stages/
│   ├── base.py            # unchanged (StageProtocol + CheckpointMixin)
│   ├── stubs.py           # edited — PIPELINE_STAGES imports real stages
│   ├── context.py         # NEW
│   ├── storyboard.py      # NEW
│   ├── timing.py          # NEW
│   └── scriptwriter.py    # NEW
├── models/
│   └── storyboard.py      # edited — VisualType enum
└── utils/
    └── cost_estimator.py  # rewritten — dynamic heuristic
```

### Pattern 1: Generic forced tool-use → Pydantic (the D-14 helper)
**What:** One reusable function that any LLM stage calls to get a validated Pydantic model back.
**When to use:** Both `storyboard` and `scriptwriter`.
**Example:**
```python
# Source: Context7 /anthropics/anthropic-sdk-python (tool_choice, input_schema, tool_use block)
# src/avideo/integrations/anthropic.py
from __future__ import annotations
from typing import TypeVar
import anthropic
from pydantic import BaseModel

MODEL = "claude-sonnet-4-6"  # latest Sonnet, dateless pinned snapshot [VERIFIED: platform.claude.com models overview]
T = TypeVar("T", bound=BaseModel)

_client: anthropic.Anthropic | None = None

def _get_client() -> anthropic.Anthropic:
    """Lazy singleton so importing this module never requires an API key
    (keeps --dry-run and tests import-safe). SDK reads ANTHROPIC_API_KEY from env."""
    global _client
    if _client is None:
        _client = anthropic.Anthropic(max_retries=3)  # SDK does exp backoff + jitter + Retry-After
    return _client

def call_structured(
    *, system: str, user: str, tool_name: str, tool_description: str,
    output_model: type[T], max_tokens: int = 8192,
) -> T:
    """Force Claude to emit JSON conforming to output_model, validated by Pydantic."""
    schema = output_model.model_json_schema()
    resp = _get_client().messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        tools=[{"name": tool_name, "description": tool_description, "input_schema": schema}],
        tool_choice={"type": "tool", "name": tool_name},  # FORCED tool-use (D-03)
    )
    for block in resp.content:
        if block.type == "tool_use" and block.name == tool_name:
            return output_model.model_validate(block.input)
    raise RuntimeError(f"Model did not return a tool_use block for {tool_name!r}")
```
**Notes:**
- `tool_choice={"type":"tool","name":...}` is the documented forced-tool syntax. [VERIFIED: Context7]
- With forced tool-use the response `stop_reason` is `"tool_use"` and content contains exactly one `tool_use` block. [VERIFIED: Context7 message.py — stop_reason values]
- `block.input` is already a parsed `dict` → feed directly to `model_validate`.

### Pattern 2: Closed Enum for `visual_type` (D-02)
**What:** Migrate `SlideSpec.visual_type` from free `str` to a closed `str, Enum`.
**Example:**
```python
# src/avideo/models/storyboard.py
from enum import Enum
from pydantic import BaseModel

class VisualType(str, Enum):
    title = "title"
    bullets = "bullets"
    chart = "chart"
    diagram = "diagram"
    quote = "quote"
    comparison = "comparison"
    image_icon = "image_icon"

class SlideSpec(BaseModel):
    title: str
    bullets: list[str]
    visual_type: VisualType = VisualType.bullets  # default changed from "text"
```
- Pydantic emits `{"enum": ["title","bullets",...]}` in `model_json_schema()`, which constrains Claude's tool output to valid values. [VERIFIED: Context7 pydantic json_schema]
- **Migration risk:** the Phase-1 stub default was `"text"`, which is NOT in the new enum. Any pre-existing `storyboard.json` checkpoint with `visual_type:"text"` will fail `model_validate_json` on resume. Acceptable (Phase-1 stub output is throwaway) but the planner should note: delete stale `workdir/storyboard.json` when upgrading.

### Pattern 3: Largest-remainder (Hamilton) apportionment (D-06)
**What:** Distribute integer/float seconds so the per-slide sum equals the target exactly.
**Example:**
```python
# src/avideo/stages/timing.py — pure, deterministic, no network
def apportion_seconds(weights: list[float], total: int) -> list[int]:
    """Largest-remainder method: integer seconds summing exactly to `total`."""
    wsum = sum(weights) or 1.0
    raw = [w / wsum * total for w in weights]
    floors = [int(x) for x in raw]
    remainder = total - sum(floors)            # 0 <= remainder < len(weights)
    # distribute the leftover to the largest fractional parts
    order = sorted(range(len(raw)), key=lambda i: raw[i] - floors[i], reverse=True)
    for i in order[:remainder]:
        floors[i] += 1
    return floors  # sum(floors) == total, guaranteed
```
- Apply min/max clamps BEFORE or AFTER apportionment carefully: clamping after can break the exact-sum invariant. Recommended order: (1) compute raw weights, (2) clamp the *weights* (not the seconds), (3) apportion. If clamping seconds post-apportionment, re-run a redistribution pass on the unclamped slides to restore the exact sum. The planner should pick one approach and unit-test the exact-sum invariant.
- `TimingOutput.seconds` is `float` in the model; emit `float(int_seconds)` to keep the contract while preserving exact integer sums.

### Pattern 4: Scriptwriter calibration retry (D-10)
**What:** One semantic re-call (not a network retry) if any slide deviates >25% from its word budget.
```python
def _max_drift(script, budgets) -> float:
    return max(abs(len(s.narration.split()) - b) / b for s, b in zip(script.slides, budgets) if b)

def run(self, workdir, config):
    budgets = [t.word_budget for t in timing.slides]
    script = call_structured(..., output_model=ScriptOutput)
    if _max_drift(script, budgets) > 0.25:
        script = call_structured(..., user=correction_prompt(script, budgets), output_model=ScriptOutput)
        # accept whatever comes back even if still off — NO infinite loop (D-10)
    return script
```

### Anti-Patterns to Avoid
- **Calling `count_tokens` (network) in `cost_estimator`** — breaks the offline `--dry-run` contract. Use a heuristic.
- **Instantiating `Anthropic()` at module import** — forces an API key to exist just to import the module, breaking `--dry-run` and tests. Use lazy `_get_client()`.
- **Stages calling `workdir.write_checkpoint` / `mark_done`** — the orchestrator owns that (Pitfall-4 ordering). Stages only `return` a model.
- **Hand-rolling 429/5xx retry on top of the SDK** — double backoff; let `max_retries=3` do it.
- **Parsing tool output with `json.loads(text_block)`** — forced tool-use puts structured data in `block.input` (a dict), not in a text block. Read `block.input`.
- **Clamping seconds after apportionment without re-balancing** — silently breaks `sum == target` (the core TIME-01 invariant).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Exponential backoff for 429/5xx | Custom retry+sleep loop | SDK `Anthropic(max_retries=3)` | SDK already does jitter + `Retry-After` + correct status-code set [VERIFIED: Context7] |
| JSON schema from a model | Hand-written schema dict | `output_model.model_json_schema()` | Pydantic emits draft-2020-12 the API accepts; stays in sync with the model |
| Structured-output parsing | Regex/`json.loads` on text | `block.input` dict + `model_validate` | Forced tool-use guarantees a parsed dict; no fragile parsing |
| PDF text extraction | Manual stream parsing | `fitz` `page.get_text("text")` | Handles layout, encodings, encrypted PDFs |
| .pptx text extraction | Unzip + XML parse | `python-pptx` `shape.text_frame` | Handles shape types, placeholders, runs |
| Exact-sum rounding | Naive `round()` per slide | Largest-remainder | Naive rounding drifts; sum won't equal target |

**Key insight:** The two genuinely custom pieces in Phase 2 are (a) the largest-remainder apportionment with clamps and (b) the calibration retry semantics. Everything else (retries, schema, parsing, extraction) is a one-liner against an existing library.

## Common Pitfalls

### Pitfall 1: `bullets.yaml` is never parsed in the current codebase
**What goes wrong:** Planners assume bullets flow into the storyboard already. They do not — `cli.py` only validates the *path* exists; no stage reads the file. The Phase-1 stub hardcodes `"Bullet 1"`.
**Why it happens:** Phase 1 was stubs-only; the real consumer (storyboard) didn't exist yet.
**How to avoid:** The storyboard stage (or a small shared loader) must `yaml.safe_load(config.bullets)` → `{title, bullets: list[str]}`. Add a test fixture (`minimal_bullets` already exists in `conftest.py`).
**Warning signs:** Storyboard prompt has no real bullet content.

### Pitfall 2: New `VisualType` enum breaks resume on old checkpoints
**What goes wrong:** A `storyboard.json` written by the Phase-1 stub has `visual_type:"text"`, not in the new enum → `ValidationError` on resume.
**How to avoid:** Document that upgrading invalidates Phase-1 stub checkpoints; delete `workdir/` (or just `storyboard.json` + `.storyboard.done`) before the first real run.
**Warning signs:** `ValidationError` on `visual_type` when re-running over an old workdir.

### Pitfall 3: Clamping seconds breaks the exact-sum invariant (TIME-01)
**What goes wrong:** You apportion to exact sum, then clamp slides under a minimum → sum no longer equals target.
**How to avoid:** Clamp weights pre-apportionment, OR re-balance the slack after clamping. Add an explicit `assert sum(seconds) == target` unit test (TEST-02).
**Warning signs:** `total_seconds != sum(slide.seconds)`; downstream FFmpeg duration mismatch.

### Pitfall 4: Module-level Anthropic client breaks dry-run and tests
**What goes wrong:** `client = anthropic.Anthropic()` at import time raises if `ANTHROPIC_API_KEY` is unset, breaking `--dry-run` (which should need no key) and CI tests.
**How to avoid:** Lazy `_get_client()`; mock the `call_structured` helper in tests so no key/network is touched.
**Warning signs:** Import errors in tests; `--dry-run` fails without a key.

### Pitfall 5: Encrypted or empty PDF/PPTX
**What goes wrong:** `fitz.open(encrypted.pdf)` opens but `get_text` returns nothing until `authenticate()`; an empty deck yields empty text and a useless storyboard prompt.
**How to avoid:** After opening a PDF, check `doc.needs_pass` — if true and no password, raise a clear Rich error (or skip with `used=False` + warning). For empty extracted text, log a warning and proceed as if no context (CTX-02 semantics). [VERIFIED: Context7 — `needs_pass`, `authenticate`]
**Warning signs:** Storyboard ignores a context file the user clearly passed.

### Pitfall 6: `notes_slide` access creates an empty notes slide as a side effect
**What goes wrong:** Reading `slide.notes_slide` *creates* a notes slide if absent — a mutation while "just reading".
**How to avoid:** Guard with `if slide.has_notes_slide:` before touching `notes_slide`. [VERIFIED: Context7 python-pptx — `has_notes_slide`]

### Pitfall 7: `max_tokens` too small truncates the script tool call
**What goes wrong:** Whole-script generation for many slides can exceed a small `max_tokens`, truncating the `tool_use` block → invalid/partial JSON → `ValidationError`.
**How to avoid:** Size `max_tokens` generously for the scriptwriter (e.g. 8192+), scaled by total word budget. Sonnet 4.6 max output is 64k tokens, so headroom is ample. [VERIFIED: platform.claude.com — Sonnet 4.6 max output 64k]
**Warning signs:** `stop_reason == "max_tokens"`; truncated narration.

## Code Examples

### Context extraction (CTX-01) — dispatch by suffix
```python
# Source: Context7 /pymupdf/pymupdf + /websites/python-pptx_readthedocs_io_en
# src/avideo/stages/context.py
from pathlib import Path
import fitz                       # PyMuPDF (CLAUDE.md mandates `import fitz`)
from pptx import Presentation

def extract_pdf(path: Path) -> str:
    doc = fitz.open(path)
    if doc.needs_pass:            # encrypted, no password supplied
        doc.close()
        raise ValueError(f"PDF is password-protected: {path}")
    text = "\n".join(page.get_text("text") for page in doc)
    doc.close()
    return text

def extract_pptx(path: Path) -> str:
    prs = Presentation(str(path))
    parts: list[str] = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                parts.append(shape.text_frame.text)
        if slide.has_notes_slide:          # guard — don't create empty notes
            parts.append(slide.notes_slide.notes_text_frame.text)
    return "\n".join(p for p in parts if p.strip())

def extract_md(path: Path) -> str:
    return path.read_text(encoding="utf-8")

_DISPATCH = {".pdf": extract_pdf, ".pptx": extract_pptx,
             ".md": extract_md, ".markdown": extract_md}
```

### Token-cap truncation for context injection (D-04)
```python
# Heuristic: ~4 chars/token. Truncate raw text to a configurable char budget.
def truncate_to_tokens(text: str, max_tokens: int) -> str:
    max_chars = max_tokens * 4
    return text if len(text) <= max_chars else text[:max_chars]
```
*(The token cap value is Claude's discretion per CONTEXT.md; expose as a constant or config.)*

### Timing word budget (TIME-02)
```python
def word_budget(seconds: float, wpm: int) -> int:
    return round(seconds * wpm / 60)     # D-07
```

### Mocking the LLM in tests (TEST-01) with pytest-mock
```python
# tests/test_storyboard.py
from avideo.models import StoryboardOutput, SlideSpec
from avideo.models.storyboard import VisualType

def test_storyboard_stage(mocker, tmp_workdir, minimal_bullets):
    fake = StoryboardOutput(slides=[SlideSpec(title="A", bullets=["x"],
                                              visual_type=VisualType.bullets)], language="es")
    # Patch the helper where the STAGE imports it (not where it's defined)
    mocker.patch("avideo.stages.storyboard.call_structured", return_value=fake)
    # ... construct stage + config, run, assert output == fake, no network touched
```

### `--dry-run` cost heuristic (D-15), offline
```python
# src/avideo/utils/cost_estimator.py — NO network, NO files
# Sonnet 4.6 pricing: $3 / MTok input, $15 / MTok output [VERIFIED: platform.claude.com]
def estimate_storyboard_tokens(num_bullets: int, duration: int) -> tuple[int, int]:
    est_slides = max(3, min(20, round(duration / 25)))   # ~1 slide / 25s (D-01)
    in_tok = 400 + num_bullets * 30                       # prompt + bullets
    out_tok = est_slides * 120                            # ~120 tok/slide structured
    return in_tok, out_tok
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Parse model JSON from a text block with `json.loads` | Forced tool-use → `block.input` dict (D-03), or `messages.parse(output_format=Model)` | Tool-use GA 2024; `parse()` helper in recent SDK | No fragile text parsing; schema-validated output |
| Hand-rolled retry loops | SDK `max_retries` w/ built-in backoff+jitter | Long-standing in SDK | D-13's custom 429/5xx handling is mostly redundant |
| `import fitz` only | `import pymupdf` (new) or `import fitz` (legacy alias) | PyMuPDF 1.24+ | Both work; CLAUDE.md mandates `fitz` |
| Dated-only model IDs | Dateless pinned snapshots (`claude-sonnet-4-6`) | Claude 4.6 generation | Use `claude-sonnet-4-6` directly; it's a pinned snapshot, not evergreen |

**Deprecated/outdated:**
- `claude-sonnet-4-20250514` / `claude-opus-4-20250514`: **deprecated, retire 2026-06-15**. Do NOT use. [VERIFIED: platform.claude.com models overview]
- pydantic v1 `.json()`/`.dict()`: use v2 `model_json_schema()`/`model_validate()` (project already on v2).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `~4 chars/token` is an adequate truncation/estimation heuristic for Spanish text | Code Examples (truncation, cost) | Slightly off token caps / cost estimates; not load-bearing — only affects `--dry-run` numbers and context-fit margin |
| A2 | Phase-1 stub `storyboard.json` (with `visual_type:"text"`) can be safely discarded on upgrade | Pitfall 2 | If a user has a real in-progress run, deleting loses work — but Phase-1 output is by definition stub/throwaway |
| A3 | `max_tokens=8192` is sufficient for whole-script generation at typical durations | Pitfall 7, helper default | Long videos (many slides) may need more; mitigated by Sonnet's 64k ceiling and scaling by word budget |
| A4 | The cost-estimator slide-count formula (`duration/25`) matches what Claude will actually produce (D-01) | Code Examples (cost) | Estimate-only; real slide count is Claude's call. Dry-run is advisory, not contractual |
| A5 | `block.input` is always a fully-parsed dict under forced tool-use (never partial) when `stop_reason != "max_tokens"` | Pattern 1 | If truncated, `model_validate` raises — caught and surfaced as a clear error; mitigated by A3/Pitfall 7 |

## Open Questions

1. **Where should `bullets.yaml` parsing live?**
   - What we know: It's currently parsed nowhere; the storyboard stage is the consumer.
   - What's unclear: Inline in `storyboard.py` vs a shared `utils/bullets.py` loader (also useful for the cost estimator's bullet count).
   - Recommendation: Small shared loader `load_bullets(path) -> BulletsInput` (Pydantic model with `title: str`, `bullets: list[str]`) — reused by both the storyboard stage and `cost_estimator`. Add a `BulletsInput` model alongside the others.

2. **Min/max clamp values for per-slide timing (Claude's discretion per CONTEXT.md).**
   - What we know: Clamps prevent absurdly short/long slides; must not break exact-sum.
   - Recommendation: Start with min ~8s, max ~45s as constants in `timing.py`; unit-test that the exact-sum invariant holds with clamps active. Document the chosen values in the plan.

3. **Context token cap value (Claude's discretion).**
   - Recommendation: Default cap ~6000 tokens (~24k chars) injected context — generous headroom under Sonnet's 1M window while keeping prompt focused. Expose as a module constant for easy tuning.

4. **Does the scriptwriter need the storyboard *and* the timing word budgets, or just the budgets?**
   - Recommendation: Pass both — storyboard gives content/coherence (D-09: "Claude ve todas las slides"), timing gives per-slide word budgets (D-09: "presupuesto explícito"). The scriptwriter stage must read both `storyboard.json` and `timings.json` checkpoints via `workdir.read_checkpoint`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `anthropic` (Python pkg) | storyboard, scriptwriter | ✓ | 0.104.1 | — (required) |
| `PyMuPDF`/`fitz` | context PDF extraction | ✗ (not yet added) | — | `uv add PyMuPDF` |
| `python-pptx` | context PPTX extraction | ✗ (not yet added) | — | `uv add python-pptx` |
| `pyyaml` | bullets.yaml parsing | ✓ | 6.0.3 | — |
| `pytest` / `pytest-mock` | tests | ✓ | 9.0.3 / 3.15.1 | — |
| `ANTHROPIC_API_KEY` (env/.env) | live Claude calls | runtime/user-supplied | — | Tests mock the helper → no key needed for CI |
| Network access to api.anthropic.com | live storyboard/script runs | runtime | — | `--dry-run` and tests need no network |

**Missing dependencies with no fallback:** None blocking — `PyMuPDF` and `python-pptx` install cleanly via `uv add` (both pure-wheel on PyPI; PyMuPDF ships manylinux/macOS wheels).
**Missing dependencies with fallback:** `ANTHROPIC_API_KEY` absent → all tests still pass by mocking `call_structured`; only live runs require the key.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest` 9.0.3 + `pytest-mock` 3.15.1 |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options]` (testpaths=`tests`, pythonpath=`src`) |
| Quick run command | `uv run pytest tests/test_timing.py tests/test_storyboard.py -x -q` |
| Full suite command | `uv run pytest -q` |
| Existing fixtures | `tests/conftest.py`: `tmp_workdir`, `minimal_bullets`, `minimal_config` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CTX-01 | Extract text from .pdf/.pptx/.md fixtures | unit (fixture files) | `pytest tests/test_context.py -x` | ❌ Wave 0 |
| CTX-02 | No `--context` → `ContextOutput(used=False)`; pipeline unaffected | unit | `pytest tests/test_context.py::test_no_context -x` | ❌ Wave 0 |
| STORY-01 | Storyboard stage calls helper, returns `StoryboardOutput` | unit (mock `call_structured`) | `pytest tests/test_storyboard.py -x` | ❌ Wave 0 |
| STORY-02 | Output validates against contract; orchestrator persists `storyboard.json` | unit + integration | `pytest tests/test_storyboard.py -x` | ❌ Wave 0 |
| TIME-01 | Content-weighted split; **sum(seconds) == duration** (clamps active) | unit (pure, no mock) | `pytest tests/test_timing.py::test_exact_sum -x` | ❌ Wave 0 |
| TIME-02 | `word_budget == round(seconds*wpm/60)` for wpm in {120,150,180} | unit (pure) | `pytest tests/test_timing.py::test_word_budget -x` | ❌ Wave 0 |
| SCRIPT-01 | Calibration retry fires once on >25% drift, never loops | unit (mock helper, 2 side_effects) | `pytest tests/test_scriptwriter.py -x` | ❌ Wave 0 |
| SCRIPT-02 | Output language honored; structured `ScriptOutput` | unit (mock helper) | `pytest tests/test_scriptwriter.py -x` | ❌ Wave 0 |

**Mocked vs fixture:**
- **Mocked (no network):** `call_structured` (patched at the stage's import site, e.g. `avideo.stages.storyboard.call_structured`). This satisfies TEST-01 ("API de Anthropic mockeada"). For a deeper test, mock `_get_client().messages.create` to return a fake `Message` with a `tool_use` block.
- **Fixtures (real files):** tiny `.pdf` (generate with `fitz` in a fixture or commit a 1-page sample), `.pptx` (generate with `python-pptx` in a fixture), `.md` (write inline). An **encrypted PDF** fixture for Pitfall 5. Reuse `minimal_bullets`.
- **Pure (no mock, no fixture):** timing apportionment — the highest-value tests (exact-sum invariant, clamp behavior, word budgets). Deterministic per D-08.

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_<stage>.py -x -q` (the stage just touched).
- **Per wave merge:** `uv run pytest -q` (full suite, must be green).
- **Phase gate:** Full suite green before `/gsd-verify-work`; manual smoke `avideo generate --bullets bullets.yaml --duration 120 --dry-run` (offline) + one live run if a key is available.

### Wave 0 Gaps
- [ ] `tests/test_context.py` — covers CTX-01, CTX-02 (incl. encrypted-PDF + empty-deck edge cases)
- [ ] `tests/test_storyboard.py` — covers STORY-01, STORY-02 (mock `call_structured`)
- [ ] `tests/test_timing.py` — covers TIME-01 (exact-sum + clamps), TIME-02 (word budget)
- [ ] `tests/test_scriptwriter.py` — covers SCRIPT-01 (calibration retry, no infinite loop), SCRIPT-02
- [ ] `tests/conftest.py` additions — `sample_pdf`, `sample_pptx`, `sample_md`, `encrypted_pdf` fixtures
- [ ] (optional) `tests/test_anthropic_integration.py` — `call_structured` extracts `tool_use` block correctly with a fully-faked `Message`

*(Framework already installed — no install step needed.)*

## Security Domain

> CLI tool reading local files + calling Anthropic over HTTPS. No web server, no auth, no DB. Lightweight surface; included for completeness.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No user auth (single-user CLI) |
| V3 Session Management | no | Stateless CLI |
| V4 Access Control | no | Local-only |
| V5 Input Validation | yes | Pydantic validates all stage I/O; validate `config.context` suffix against the dispatch allow-list before extraction; guard encrypted/empty docs |
| V6 Cryptography | no | No crypto implemented; HTTPS handled by the SDK |
| V8 Data Protection | yes | `ANTHROPIC_API_KEY` from env/`.env`; **never log the key**; ensure `.env` is gitignored; do not write the key into checkpoints |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API key leaked in logs / checkpoints / tracebacks | Information Disclosure | Key lives only in env; never put it in `RunConfig` or any model; Rich error messages must not echo it |
| Malicious/oversized context file (zip bomb in .pptx, huge PDF) | Denial of Service | Truncate extracted text to the token cap (D-04); consider a file-size guard before opening |
| Prompt injection via context document content | Tampering | Context is reference material only; the storyboard prompt should frame it as untrusted reference, not instructions. Low impact (single-user, no downstream privilege) |
| Path traversal via `--context` | Tampering | Typer already validates `exists=True, file_okay=True, dir_okay=False`; suffix allow-list adds a second check |

## Sources

### Primary (HIGH confidence)
- Context7 `/anthropics/anthropic-sdk-python` — `messages.create`/`messages.parse`, `tool_choice`/`tools`/`input_schema`, `tool_use` block + `stop_reason`, `_should_retry`/`_calculate_retry_timeout`, `DEFAULT_MAX_RETRIES=2`, client init `max_retries`/`api_key`
- Context7 `/pymupdf/pymupdf` — `fitz.open`, `page.get_text("text")`, `Document.needs_pass`, `authenticate()`
- Context7 `/websites/python-pptx_readthedocs_io_en` — `slide.shapes`, `has_text_frame`, `text_frame.text`, `has_notes_slide`/`notes_slide`
- Context7 `/pydantic/pydantic` — `model_json_schema()`, enum schema generation, `WithJsonSchema`
- platform.claude.com/docs/en/about-claude/models/overview — `claude-sonnet-4-6` ID, pricing ($3/$15 MTok), 1M ctx / 64k output, deprecations (Sonnet 4 EOL 2026-06-15)
- PyPI registry (2026-05-25) — `anthropic` 0.104.1, `PyMuPDF` 1.27.2.3, `python-pptx` 1.0.2
- Codebase: `orchestrator.py`, `stages/base.py`, `stages/stubs.py`, `utils/workdir.py`, `utils/cost_estimator.py`, `models/*.py`, `cli.py`, `conftest.py`, `config.json`

### Secondary (MEDIUM confidence)
- WebSearch (verified against Wikipedia + multiple PyPI packages) — largest-remainder / Hamilton method algorithm
- WebSearch (verified against official models overview) — latest Claude Sonnet model ID

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every version verified against PyPI; APIs verified via Context7.
- Architecture/integration: HIGH — read all relevant existing code; stage contract is explicit and stable.
- Anthropic tool-use mechanics: HIGH — Context7 + official docs; model ID confirmed on platform.claude.com.
- Timing apportionment: HIGH — algorithm is well-established and trivially unit-testable.
- Pitfalls: HIGH — derived from reading the actual codebase (e.g. bullets.yaml never parsed) plus verified library edge cases.

**Research date:** 2026-05-25
**Valid until:** ~2026-06-25 (stable). Watch: Sonnet 4 retirement 2026-06-15 (already on 4.6, unaffected); anthropic SDK minor bumps may add structured-output ergonomics but won't break the tool-use path.
