# Quick Task 260531-npu: SEED-002 — variación dirigida (steerable variation) - Context

**Gathered:** 2026-05-31
**Status:** Ready for planning — architecture LOCKED with owner

<domain>
## Task Boundary

Implementar SEED-002: hoy "Pedir variación" en Fase 2 (Guion) y Fase 3 (Diapositivas)
re-genera A CIEGAS. Añadir un cuadro de texto libre + selector explícito de etapa para
que el usuario dirija la regeneración ("tono más cercano", "cambia el número de slides
a 4", "esquema de color azul").

Spec original: `.planning/seeds/SEED-002-steerable-variation.md`
</domain>

<decisions>
## Implementation Decisions (LOCKED — do not revisit)

### Enrutado: cuadro de texto + SELECTOR EXPLÍCITO de etapa
- NO clasificación de intención por LLM. El usuario marca el objetivo con un control
  (`st.radio`/`selectbox`) junto al `st.text_area`. El selector mapea objetivo → etapa.
- Fase 2 (Guion):
  - "Afinar tono/redacción" → re-ejecuta **scriptwriter** (camino barato actual).
  - "Cambiar nº de slides / estructura" → re-ejecuta **storyboard** (→timing→scriptwriter).
- Fase 3 (Diapositivas):
  - "Estilo visual / colores" → re-ejecuta **slides** (→verify).
  - Hueco "añadir imágenes" reservado para SEED-001 (NO implementar ahora).

### Transporte del feedback: checkpoint `workdir/feedback.json` (NO RunConfig)
- NO añadir campos a `RunConfig`. Razón: feedback es efímero/por-rerun/por-etapa, no
  parte de la identidad del run; meterlo en RunConfig ensucia la precedencia
  CLI>yaml>env, obliga a la UI a mutar config, y rompería retrocompat (419 tests).
- Modelo pequeño en `workdir/feedback.json`, keyed por etapa destino:
  `{ "storyboard": "...", "scriptwriter": "...", "slides": "..." }`.
- El pipeline CLI nunca escribe este archivo → 100% retrocompatible (feedback ausente
  = comportamiento idéntico al actual).

### Inyección en el prompt: bloque opcional localizado
- Cada `_build_prompts()` de `storyboard`, `scriptwriter`, `slides` gana un parámetro
  `feedback: str | None`. Si viene, se añade al final del user-prompt un bloque
  delimitado y prioritario (p.ej. `--- Instrucción del usuario (prioritaria) ---`).
- La firma de `call_structured` NO cambia.

### Enrutado vía done-markers (reutilizar motor existente)
- "Cambiar nº de slides" = borrar done-marker de `storyboard` + `invalidate_downstream`.
  El chaining por done-markers (ya existente, arreglado en sesión anterior) re-camina
  `storyboard → timing → scriptwriter` automáticamente. NO orquestación nueva.
- Nuevo dispatcher `pipeline_ops.rerun_with_feedback(workdir, config, target_stage, feedback)`:
  `write_feedback(target) → done_marker(target).unlink() → invalidate_downstream(target) → run_stage(first_stage)`.
- `rerun_scriptwriter` / `rerun_slides` actuales se vuelven casos particulares (feedback=None).

### Ciclo de vida: consumido una vez (idempotencia)
- La stage lee su feedback al inicio de `run()` y, tras una generación exitosa
  (`call_structured` OK), borra su propia entrada de `feedback.json`. Así un resume
  normal posterior no re-aplica feedback rancio; si crashea a mitad, sigue para reintento.

### Alcance confirmado por el owner (2026-05-31)
- SÍ incluir el caso "nº de slides → re-run storyboard" (ejemplo explícito del owner).
- DIFERIR Pexels / "más visual con imágenes" a SEED-001 (deja el hueco en el selector).
</decisions>

<specifics>
## Specific Ideas

Archivos a tocar (alcance de quick task):
- **Nuevo:** `src/avideo/models/feedback.py` (modelo) y/o helpers en
  `src/avideo/utils/workdir.py`: `write_feedback(stage, text)`,
  `read_feedback(stage) -> str | None`, `clear_feedback(stage)`.
- **Stages:** `src/avideo/stages/storyboard.py`, `scriptwriter.py`, y la stage de slides
  (`slides_auto.py` / `slides_dispatch.py`) → `_build_prompts` con `feedback` opcional +
  lectura/clear en `run()`.
- **`src/avideo/ui/pipeline_ops.py`:** `rerun_with_feedback` (+ refactor de los dos `rerun_*`).
- **UI:** `src/avideo/ui/pages/phase_2_guion.py` y `phase_3_slides.py` →
  `st.text_area` + `st.radio` selector en la sección de variación.
- **Tests:** prompt incluye feedback; selector enruta a la etapa correcta;
  feedback se consume una vez.

Invariantes del proyecto a respetar:
- `STAGE_ORDER = [..., storyboard, timing, scriptwriter, slides, ..., voice, ...]`.
- `pipeline_ops` NO importa Streamlit (debe ser testeable sin Streamlit).
- workdir = única fuente de verdad; session_state solo workdir_path + phase.
- Mantener idempotente + invalidar downstream tras re-run dirigido.
</specifics>

<canonical_refs>
## Canonical References

- `.planning/seeds/SEED-002-steerable-variation.md` (spec original + design nuances).
- `.planning/seeds/SEED-001-pexels-image-source.md` (cruce diferido para "más visual").
- Decisión D-01 (storyboard decide nº de slides) — por eso "nº slides" → storyboard.
- Decisión SCR-03 ("solo scriptwriter") — el caso storyboard la rompe a propósito.
</canonical_refs>
