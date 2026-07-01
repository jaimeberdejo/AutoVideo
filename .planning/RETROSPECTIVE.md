# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.60.0 — MVP Pipeline

**Shipped:** 2026-05-29
**Phases:** 7 | **Plans:** 18 | **Tasks:** 22 | **Commits:** 142

### What Was Built
- Pipeline `avideo generate` end-to-end: context → storyboard → timing → scriptwriter → slides → verify → voice → align → subs → assemble.
- Tres modos de slides (`auto` HTML/Playwright, `hybrid`, `manual`) y dos modos de voz (`elevenlabs` con timestamps, `record` con WhisperX), con verificador Claude Vision.
- Montaje FFmpeg (duraciones reales por ffprobe, crossfade, loudnorm EBU R128 de dos pasadas), subtítulos `.srt`/`.vtt`, e informe QA.
- Empaquetado con `uv` + `Dockerfile` reproducible (Playwright pineado + FFmpeg + Poppler) y 303 tests verdes con todas las APIs/binarios mockeados.

### What Worked
- **Construcción bottom-up con stubs primero (Phase 1):** tener el orquestador + contratos Pydantic + los 10 stubs end-to-end antes de implementar cada etapa permitió swaps incrementales (`Stub → Stage`) sin romper el pipeline.
- **Checkpoints atómicos e idempotentes (tmp→rename + done markers):** reanudar a mitad fue trivial y los tests de doble ejecución validaron la idempotencia.
- **Plan-checker y code-review atraparon defectos reales antes de mergear:** contradicción del gate L3/L4 (Phase 6), 4 blockers en Phase 6 (alpha PNG, fuga de recurso PDF, paridad de cuenta de slides, no-mark-done-on-fail) y un bug de orden de build en el Dockerfile (Phase 7).
- **Mocks estrictos en tests:** sin llamadas reales a Anthropic/ElevenLabs/Chromium/FFmpeg; los smoke tests de render/assemble se saltan limpiamente si faltan binarios.

### What Was Inefficient
- **STATE.md quedó desincronizado durante la ejecución** (campos como "Current focus: Phase 05" y "Progress 0%" persistieron tras completar el milestone) — requirió corrección manual al cierre.
- **El extractor automático de one-liners de los SUMMARY.md no produjo accomplishments usables** (devolvió literales "One-liner:", "Font:", etc.) — hubo que reescribir MILESTONES.md a mano. Los SUMMARY no siguen un formato de one-liner consistente.
- **El roadmap creció más allá del milestone (Phases 8–9 añadidas tras la auditoría)** mezcló alcance enviado con alcance futuro en REQUIREMENTS.md, complicando el archivado limpio.

### Patterns Established
- **Stub-first pipeline:** definir todos los contratos I/O + stubs antes de implementar; cada fase hace swap de su stub por la etapa real.
- **Validación de salidas de API externas antes del checkpoint:** p. ej. timestamps ElevenLabs estrictamente crecientes + retry≤3 antes de persistir.
- **FFmpeg siempre por subprocess con lista de args (nunca `shell=True`)**; fluent builder en `integrations/ffmpeg.py`.
- **Visuales 100% reproducibles:** SVG offline + gráficos por código; los medios del usuario (Phases 8–9) se aportan, nunca se generan con IA.

### Key Lessons
1. **Mantener STATE.md como artefacto vivo durante la ejecución, no solo al cierre** — o aceptar que el cierre de milestone lo reconcilia, pero entonces no confiar en sus campos a mitad de camino.
2. **Estandarizar el bloque "one-liner" en cada SUMMARY.md** para que la extracción automática de accomplishments funcione en el cierre de milestone.
3. **Congelar el alcance del milestone al pasar la auditoría;** las nuevas ideas van a un milestone/roadmap separado en lugar de ampliar el REQUIREMENTS.md ya auditado.

### Cost Observations
- Model mix: Opus para planificación/fixes, Sonnet para ejecución (perfil `balanced`, modo `yolo`).
- Notable: el coste de re-trabajo fue bajo gracias a plan-check + code-review por fase; los defectos se atraparon antes del merge en lugar de en integración.

---

## Milestone: v2.0.0 — Studio Guiado

**Shipped:** 2026-07-01
**Phases:** 6 (8–13) | **Plans:** 23 | **Commits:** 107 · 206 files changed · +23,813/-1,093 LOC

### What Was Built
- `avideo studio` — wizard Streamlit de 6 fases (Contenido, Guion, Diapositivas, Voz, Extras, Ensamblaje) sobre el pipeline existente como motor headless, con gate de aprobación humana obligatorio entre fases y `invalidate_downstream` al editar/regenerar aguas arriba.
- Estado reconstruido desde `workdir/*.json` (no `session_state`) — sobrevive a refrescos/cierres del navegador; etapas largas corren vía `PipelineBridge` (hilo daemon + polling) sin bloquear la UI.
- OpenAI Audio como tercer proveedor de voz (round-trip STT `whisper-1` para timestamps), mejora de audio no destructiva (denoise+loudnorm con preview antes/después), música de fondo (ducking+fade, loudnorm de una sola pasada), y verificador Claude Vision para slides subidas por el usuario.
- SEED-002: variación dirigida por feedback de texto en guion/storyboard/slides (en vez de "regenerar a ciegas").
- Suite de tests: 303 → 456 (incluye smoke tests de páginas y 5 tests E2E opcionales de navegador real).

### What Worked
- **Auditoría de milestone con `human_needed` explícito en vez de forzar un veredicto prematuro:** 5/6 fases quedaron marcadas `human_needed` tras la auditoría de código, dejando claro que faltaba una verificación real en navegador antes de poder cerrar — evitó dar por bueno algo no probado.
- **Sesión de UAT real en navegador (Chrome MCP + Playwright, APIs reales, FFmpeg real) antes de cerrar el milestone:** encontró 3 bugs bloqueantes que ningún test mockeado había atrapado (pérdida de contexto de tema en retry del guionista, nombre de fichero temporal de FFmpeg rompiendo autodetección de formato, `run_config` no sobrevivía a un refresco) — confirma que los mocks no sustituyen una pasada real end-to-end para una UI stateful.
- **`invalidate_downstream` como único punto de invalidación:** centralizar la lógica de "qué checkpoints quedan obsoletos" en un método de `WorkdirManager` evitó lógica de invalidación duplicada/inconsistente en cada página.

### What Was Inefficient
- **El roadmap mezcló ideas nuevas (Pexels/SEED-001) con el alcance auditado**, obligando a retirarlas explícitamente del roadmap (2026-05-29) y aparcarlas en una rama separada (`feature/pexels-slides`) para no contaminar el REQUIREMENTS.md ya en auditoría — mismo patrón de inefficiency que v1.60.0, aún sin resolver estructuralmente.
- **Rutas secundarias de la UI (subida de audio propio + mejora, subida de slides + QC, subida de música) no se ejercitaron en la sesión de UAT real** — se priorizó el camino feliz (OpenAI TTS + auto-slides) para llegar a un vídeo completo dentro del presupuesto de contexto disponible; quedan como deuda de verificación, no de implementación.
- **Auditoría de integración con sweep parcial** (varios requirement chains no se re-trazaron individualmente por límite de contexto) — aceptado como riesgo bajo pero es la segunda vez que un pase de auditoría se corta por presupuesto en vez de por alcance real.

### Patterns Established
- **Wizard gate pattern:** cada página de fase implementa `render(workdir) -> bool`; solo avanza si el usuario aprueba explícitamente.
- **Bridge + polling para etapas largas:** `PipelineBridge` lanza un hilo daemon, la página hace polling de `RunStatus` sin bloquear Streamlit.
- **Reconstrucción de estado 100% desde disco:** `session_state` nunca es la fuente de verdad de progreso — solo cachea workdir/fase actual.
- **Mejora de contenido no destructiva con preview antes/después** (audio, y por extensión cualquier transformación futura de un asset ya aprobado).
- **Feedback de texto dirigido en vez de "regenerar y cruzar los dedos"** (SEED-002) — patrón reutilizable para cualquier etapa que dependa de un LLM.

### Key Lessons
1. **Una auditoría de código no sustituye una verificación real en navegador para una app stateful con checkpoints** — los 3 bugs bloqueantes de esta milestone solo aparecieron con APIs reales y un navegador real; reservar tiempo/presupuesto explícito para esa pasada antes de intentar cerrar.
2. **Cuando surja una idea nueva a mitad de milestone, sacarla del roadmap activo de inmediato (rama separada + nota en Out of Scope)** en vez de dejarla flotando hasta el cierre — ya pasó en v1.60.0 y v2.0.0.
3. **Las rutas secundarias de una UI multi-modo (proveedor B, C, D) necesitan su propio checklist de UAT explícito** — el camino feliz no las cubre gratis y quedan como deuda silenciosa si no se listan aparte.

### Cost Observations
- Model mix: Opus para planificación/fixes, Sonnet para ejecución (perfil `balanced`, modo `yolo`) — sin cambios respecto a v1.60.0.
- Notable: la mayor parte del trabajo de implementación (fases 8–13) se completó en una sesión (2026-05-29); la UAT real en navegador y el cierre de auditoría se hicieron en una sesión separada un mes después (2026-07-01), lo que dejó STATE.md con handoffs explícitos entre sesiones — patrón útil a repetir cuando la verificación real requiere una sesión dedicada de navegador.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.60.0 | 7 | 18 | Baseline: pipeline secuencial stub-first con plan-check + code-review por fase |
| v2.0.0 | 6 | 23 | UI Streamlit sobre el pipeline existente; auditoría con veredicto `human_needed` explícito hasta UAT real en navegador con APIs/FFmpeg reales |

### Cumulative Quality

| Milestone | Tests | External calls in tests | Zero-Dep Additions |
|-----------|-------|-------------------------|--------------------|
| v1.60.0 | 303 passing | 0 (todo mockeado) | — |
| v2.0.0 | 456 passing | 5 tests E2E opcionales (`AVIDEO_E2E=1`) con navegador/APIs reales | Streamlit, openai SDK |

### Top Lessons (Verified Across Milestones)

1. **Ideas nuevas a mitad de milestone deben salir del roadmap activo de inmediato** (rama separada + nota explícita en Out of Scope) — observado en v1.60.0 (Phases 8–9 retiradas) y v2.0.0 (SEED-001/Pexels retirado a `feature/pexels-slides`).
2. **Auditorías de código no sustituyen verificación real cuando hay estado persistente y APIs externas de verdad** — confirmado en v2.0.0: 3 bugs bloqueantes solo visibles en una sesión de UAT real en navegador.
