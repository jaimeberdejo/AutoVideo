# Phase 1: Foundation - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 1 entrega el **esqueleto ejecutable de extremo a extremo** del pipeline: modelos Pydantic (RunConfig + contratos I/O de todas las etapas), WorkdirManager, CLI Typer (`avideo generate` con todos los flags), carga de `config.yaml`, y el orquestador secuencial con checkpoints reanudables/idempotentes y niveles de aprobación L1–L4. Todas las etapas reales (storyboard, slides, voz, montaje…) son **stubs** que escriben un checkpoint válido conforme a su contrato. No se genera contenido real (sin LLM, sin TTS, sin render, sin FFmpeg) — eso llega en fases posteriores.

</domain>

<decisions>
## Implementation Decisions

### Orchestrator, checkpoints & levels
- Cada etapa stub escribe un **checkpoint mínimo válido** conforme a su contrato Pydantic de salida, de modo que el pipeline corre de extremo a extremo y pasa datos reales entre etapas.
- Reanudación/idempotencia mediante **marcador `.done` por etapa** + escritura atómica `tmp→rename`; re-ejecutar salta las etapas ya completas.
- Semántica de niveles: **L1** = pausa tras cada etapa · **L2** = pausa en checkpoints creativos (storyboard / script / slides / verify) · **L3** = pausa solo ante warning/fail · **L4** = nunca pausa (totalmente autónomo).
- Interfaz de etapa: `StageProtocol` (run/checkpoint) + `CheckpointMixin` (decisión registrada en STATE.md).

### CLI & config
- Precedencia de configuración: **flag CLI > `config.yaml` > default Pydantic**.
- `--dry-run`: tabla Rich con tokens y coste estimados por etapa + total; no genera audio ni vídeo.
- Errores de validación Pydantic: capturados y mostrados como mensaje Rich claro (campo + razón), no traceback crudo.
- Logging con handler Rich; `--verbose` para debug; progreso por etapa.

### Models & workdir layout
- `RunConfig` + contratos I/O tipados por etapa en `models.py`.
- Layout de workdir: JSON nombrado por etapa (`storyboard.json`, `timings.json`, `script.json`) + subdirectorios `slides/ audio/ subs/`; salida final `output.mp4`.
- Formato de checkpoint: `model_dump_json()` (Pydantic v2).
- App Typer con subcomando `generate` (deja sitio para más subcomandos en el futuro).

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- Proyecto greenfield — no existe código fuente todavía. Esta fase crea la estructura base (`models.py`, `workdir.py`, `cli.py`, `orchestrator.py` y los stubs de `stages/`).

### Established Patterns
- Stack y convenciones fijados en CLAUDE.md: Python 3.11+, Pydantic v2, Typer, Rich, `uv`.
- Decisiones de arquitectura en STATE.md: orquestador propio secuencial (no LangGraph/n8n); `StageProtocol` + `CheckpointMixin`; FFmpeg por subprocess con lista de args (nunca `shell=True`).

### Integration Points
- Los stubs deben respetar los nombres de checkpoint que las fases 2–5 consumirán (`storyboard.json`, `timings.json`, `script.json`, `slides/`, `audio/`, `subs/`, `output.mp4`).
- `RunConfig` debe exponer ya todos los flags (`--voice`, `--slides-mode`, `--level`, `--context`, `--dry-run`, `--burn-subs`) aunque sus efectos completos lleguen después.

</code_context>

<specifics>
## Specific Ideas

- Comando de aceptación de la fase: `avideo generate --bullets bullets.yaml --duration 120` debe recorrer todas las etapas (stub) sin error.
- La reanudación debe verificarse con doble ejecución (interrumpir → relanzar → etapas completas se saltan).
- `--level 1` pausa tras cada etapa; `--level 4` nunca pausa.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
