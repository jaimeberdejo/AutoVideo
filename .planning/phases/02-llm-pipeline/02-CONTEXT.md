# Phase 2: LLM Pipeline - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 2 reemplaza los stubs de las etapas LLM por implementaciones reales: **ingesta de contexto** (PyMuPDF/python-pptx/markdown → `ContextOutput`), **storyboard** (Claude → `StoryboardOutput`), **director de timing** (lógica pura → `TimingOutput`) y **guionista** (Claude → `ScriptOutput`). Todo persistido como JSON validado con Pydantic en `workdir/` y reanudable desde cada checkpoint. NO incluye render de slides, voz, ni montaje (fases posteriores). El orquestador, modelos y CLI de Phase 1 ya existen y se reutilizan; estas etapas se enchufan en el loop existente sustituyendo los stubs.

</domain>

<decisions>
## Implementation Decisions

### Storyboard (Claude)
- **D-01** El nº de slides lo decide Claude según densidad de contenido + duración objetivo (≈1 slide por 20-30 s), acotado a un rango razonable (min/max) para evitar extremos.
- **D-02** `visual_type` es un **Enum** cerrado: `title`, `bullets`, `chart`, `diagram`, `quote`, `comparison`, `image_icon`. Esto da predecibilidad al render de Phase 3. Migrar `SlideSpec.visual_type` de `str` libre a este Enum (str, Enum).
- **D-03** Salida estructurada vía **tool-use forzado de Anthropic** (`tool_choice` forzado a una herramienta cuyo `input_schema` es el schema del storyboard) → JSON garantizado conforme al contrato, sin parseo frágil.
- **D-04** El texto de contexto ingerido (si existe) se inyecta en el prompt del storyboard, **truncado a un tope de tokens** configurable para no desbordar el contexto.

### Director de timing (Python puro, sin LLM)
- **D-05** Distribución de duración **ponderada por contenido** (nº de bullets + longitud de caracteres del título+bullets), con **clamps min/máx por slide** para que ninguna slide sea absurdamente corta/larga.
- **D-06** La **suma de duraciones por slide es exactamente igual** a la duración objetivo: se usa redondeo por **mayor resto (largest-remainder)** para absorber el drift de redondeo.
- **D-07** `word_budget` por slide = `round(seconds × wpm / 60)`; WPM configurable (por defecto 150, ya en `RunConfig`).
- **D-08** Lógica 100% determinista y testeable sin red (objetivo de TEST-02 en Phase 7).

### Guionista (Claude)
- **D-09** Generación **whole-script en una sola llamada** (Claude ve todas las slides → coherencia y transiciones naturales), con el **presupuesto de palabras por slide explícito** en el prompt.
- **D-10** **Calibración con 1 reintento**: si tras la 1ª generación alguna slide se desvía >25% de su presupuesto, se hace una única regeneración pidiendo corrección de longitud; si sigue desviada, se acepta y se registra (no bucle infinito).
- **D-11** Tono natural para **locución hablada**, en el idioma configurado (por defecto `es`). Salida vía tool-use forzado igual que el storyboard.

### Integraciones y robustez
- **D-12** Modelo: **Claude Sonnet más reciente** para storyboard y guion (balance coste/calidad). Centralizado en `integrations/anthropic.py` para poder cambiarlo en un sitio.
- **D-13** **Reintentos con backoff exponencial** (combinando `max_retries` del SDK + manejo propio de 429/5xx), 3 intentos; errores finales se elevan como error claro (Rich), no traceback.
- **D-14** `integrations/anthropic.py` expone un helper genérico de "llamada con tool-use estructurado → modelo Pydantic" reutilizable por storyboard y guionista.
- **D-15** Coste/tokens reales para `--dry-run`: `cost_estimator` se actualiza para estimar tokens de storyboard+guion a partir de nº de bullets/duración (sustituye los placeholders estáticos de Phase 1).

### Claude's Discretion
- Estructura interna exacta de prompts (system vs user), nombres de las tools, valores concretos de los clamps min/máx de timing, tope exacto de truncado de contexto — a criterio de Claude siguiendo estas decisiones y las convenciones del repo.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/avideo/models/{storyboard,timing,script,context}.py` — contratos Pydantic ya definidos (Phase 1). Phase 2 los implementa de verdad y puede **enriquecerlos** (p. ej. `visual_type` → Enum, añadir campos opcionales) manteniendo compatibilidad con el orquestador.
- `src/avideo/orchestrator.py` — loop secuencial con checkpoints atómicos (`write_checkpoint`→`mark_done`), gates L1-L4. Las etapas reales sustituyen a los stubs respetando `StageProtocol`.
- `src/avideo/stages/base.py` — `StageProtocol` + `CheckpointMixin`. Las nuevas etapas siguen este protocolo.
- `src/avideo/stages/stubs.py` — stubs actuales de `context/storyboard/timing/scriptwriter` a reemplazar.
- `src/avideo/utils/workdir.py` — `WorkdirManager` con `read_checkpoint`/`write_checkpoint`/`is_done`/`mark_done` y escritura atómica `os.replace`.
- `src/avideo/utils/cost_estimator.py` — a actualizar con estimación real de storyboard+guion.
- `src/avideo/models/config.py` — `RunConfig` (con `env_prefix="AVIDEO_"`), expone `wpm`, `language`, `context`, `duration`. `ANTHROPIC_API_KEY` se lee del entorno directamente (no por RunConfig).

### Established Patterns
- Pydantic v2 (`model_dump_json`/`model_validate_json`), tipado completo, docstrings, manejo de errores con Rich.
- Idempotencia: re-ejecutar una etapa con checkpoint `.done` la salta.
- Tests con pytest + pytest-mock; las llamadas a Anthropic se **mockean** en tests (TEST-01).

### Integration Points
- Nueva carpeta `src/avideo/integrations/` con `anthropic.py` (cliente + helper tool-use estructurado).
- Nueva carpeta de etapas reales: implementar en `src/avideo/stages/` (p. ej. `context.py`, `storyboard.py`, `timing.py`, `scriptwriter.py`) y registrarlas en el orquestador en lugar de los stubs.
- Checkpoints consumidos por fases siguientes: `storyboard.json` (Phase 3 slides), `timings.json` (Phase 4/5), `script.json` (Phase 4 voz).

</code_context>

<specifics>
## Specific Ideas

- Success criteria a cumplir: `--context deck.pdf` extrae texto; sin `--context` funciona igual; `storyboard.json` validado; `timings.json` con suma == duración objetivo; `script.json` en español ajustado a presupuesto.
- Reanudable desde cada checkpoint (storyboard → timing → script).
- Las llamadas a Anthropic deben ser mockeables para el test de storyboard de Phase 7 (TEST-01).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
